#!/usr/bin/env python3
"""Headed Chrome native-messaging acceptance, with HTTP effect oracles."""

import argparse
import importlib.util
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import shutil
import socket
import subprocess
import threading
import time
from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--chrome", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--locked", action="store_true", help="Also exercise browser-only approval while GNOME is locked; caller owns final shutdown")
parser.add_argument("--no-sandbox", action="store_true", help="Explicit isolated-VM fixture only; do not change the OS sandbox policy")
parser.add_argument("--cdp-client", type=Path, help="Enable developer mode in a current disposable test-browser profile")
args = parser.parse_args()
checks = []
effects = {"clicks": 0, "text": ""}
child = chrome = server = None
profile = args.output.with_suffix(".profile")
log = args.output.with_suffix(".log").open("w")
config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "machine-control"
paths = [config / name / "NativeMessagingHosts/org.machine_control.browser.json"
         for name in ["google-chrome", "google-chrome-for-testing", "chromium"]]
saved = {path: (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None for path in paths}
preference = config / "machine-control/browser-while-locked-desktop.json"
saved[preference] = (preference.read_bytes(), preference.stat().st_mode & 0o777) if preference.exists() else None
if data.exists():
    raise SystemExit("Acceptance requires an unused app-data directory; preserve existing installations")


def report(complete=False, failure=None):
    args.output.write_text(json.dumps({"complete": complete, "passed": complete and not failure,
                                      "failure": failure, "checks": checks, "effects": effects}, indent=2))


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})
    report()
    if not value:
        raise AssertionError(name)


def poll(fn, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError("Timed out waiting for browser state or independent effect")


def operator(method, **params):
    child.stdin.write(json.dumps({"method": method, **params}) + "\n")
    child.stdin.flush()
    if not select.select([child.stdout], [], [], 30)[0]:
        raise AssertionError("Operator timed out")
    reply = json.loads(child.stdout.readline())
    if method == "arm" and reply.get("ok"):
        poll(lambda: operator("state")["state"].get("safetyNoticeReady", True))
    return reply


def call(operation, **params):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(35)
        client.connect(str(endpoint))
        client.sendall(json.dumps({"operation": operation, **params}).encode() + b"\n")
        result = json.loads(client.makefile("rb").readline(24 * 1024 * 1024))
        print(operation, json.dumps(result), file=log, flush=True)
        return result


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path.startswith("/effect?"):
            from urllib.parse import parse_qs, urlsplit
            values = parse_qs(urlsplit(self.path).query)
            if "click" in values:
                effects["clicks"] += 1
            if "text" in values:
                effects["text"] = values["text"][0]
            content = b"ok"
        else:
            content = b'''<!doctype html><title>Linux browser fixture</title>
<button onclick="fetch('/effect?click=1')">Increment</button>
<input aria-label="Fixture text" oninput="fetch('/effect?text='+encodeURIComponent(this.value))">'''
        self.send_response(200)
        self.send_header("Content-Type", "text/html;charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


try:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:" + str(server.server_port) + "/"
    child = subprocess.Popen(["/usr/bin/python3", str(args.runtime / "desktop.py")],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
    check("private handshake", operator("hello", processId=os.getpid(), executable="/usr/bin/true")["ok"])
    endpoint = Path(operator("state")["state"]["socket"])
    poll(lambda: operator("state")["state"].get("safetyAvailable", True) and
         operator("state")["state"]["permissions"]["accessibility"])
    poll(lambda: call("status")["data"]["ready"])
    check("browser denied while Off", call("browser.tabs")["errorCode"] == "approval_required")
    extension = operator("browser.setup", bundled=True)["extensionPath"]
    # Linux resolves user native hosts beneath Chrome's selected user-data
    # directory. This is a separately identified test browser and profile.
    hosts = profile / "NativeMessagingHosts"
    hosts.mkdir(parents=True)
    shutil.copyfile(paths[1], hosts / paths[1].name)
    chrome = subprocess.Popen([str(args.chrome), "--user-data-dir=" + str(profile),
                               "--no-first-run", "--no-default-browser-check",
                               "--password-store=basic",
                               "--disable-gpu", "--ozone-platform=wayland",
                               "--disable-extensions-except=" + extension, "--load-extension=" + extension,
                               *(["--no-sandbox"] if args.no_sandbox else []),
                               *(["--remote-debugging-port=0"] if args.cdp_client else []),
                               url], stdout=log, stderr=log, start_new_session=True)
    if args.cdp_client:
        spec = importlib.util.spec_from_file_location("fixture_cdp", args.cdp_client)
        cdp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cdp)
        port_file = profile / "DevToolsActivePort"
        poll(port_file.exists)
        port, path = port_file.read_text().splitlines()[:2]
        root_cdp = cdp.CDP("ws://127.0.0.1:" + port + path)
        settings_id = root_cdp.call("Target.createTarget", url="chrome://extensions/")["targetId"]
        with urlopen("http://127.0.0.1:" + port + "/json/list", timeout=5) as response:
            page = next(p for p in json.load(response) if p["id"] == settings_id)
        settings_cdp = cdp.CDP(page["webSocketDebuggerUrl"])
        try:
            settings_cdp.call("Runtime.evaluate", expression="new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))", awaitPromise=True)
        finally:
            settings_cdp.close()
            root_cdp.call("Target.closeTarget", targetId=settings_id)
            root_cdp.close()
    poll(lambda: operator("state")["state"]["browser"]["connected"], 30)
    check("real Chrome native messaging connected", True)
    check("observe does not grant browser", operator("arm", scopes=["observe"], duration=120)["ok"]
          and call("browser.tabs")["errorCode"] == "approval_required")
    check("browser scope", operator("arm", scopes=["browser"], duration=120)["ok"])
    tabs = poll(lambda: [t for t in call("browser.tabs").get("data", {}).get("tabs", []) if t["url"] == url], 45)
    tab = tabs[0]["tabId"]
    check("fixture tab found", True)
    check("DevTools separate", call("browser.eval", tabId=tab, expression="1+1")["errorCode"] == "approval_required")
    snap = call("browser.snapshot", tabId=tab)
    check("AX browser snapshot", snap["accepted"])
    elements = snap["data"]["elements"]
    button = next(e for e in elements if e["name"] == "Increment" and e["role"] == "button")
    entry = next(e for e in elements if e["name"] == "Fixture text" and e["role"] == "textbox")
    check("browser click delivery", call("browser.click", reference=button["reference"])["accepted"])
    poll(lambda: effects["clicks"] == 1)
    check("independent click effect", effects["clicks"] == 1)
    check("browser Unicode delivery", call("browser.type", reference=entry["reference"], text="Linux 世界 café")["accepted"])
    poll(lambda: effects["text"] == "Linux 世界 café")
    check("independent Unicode effect", True)
    image = call("browser.capture", tabId=tab)
    check("browser capture", image["accepted"])
    artifact = image["data"]["artifact"]
    check("browser capture hash", hashlib.sha256(Path(artifact["guestPath"]).read_bytes()).hexdigest() == artifact["sha256"])
    check("upload explicitly unavailable", call("browser.upload", reference=entry["reference"], files=[])["errorCode"] == "unsupported_operation")
    check("DevTools scope", operator("arm", scopes=["browser", "devtools"], duration=120)["ok"])
    check("grant invalidates old reference", call("browser.click", reference=button["reference"])["errorCode"] == "stale_reference")
    evaluation = call("browser.eval", tabId=tab, expression="document.title")
    check("DevTools evaluation", evaluation["accepted"] and evaluation["data"]["value"] == "Linux browser fixture")
    if not args.locked:
        snap = call("browser.snapshot", tabId=tab)
        button = next(e for e in snap["data"]["elements"] if e["name"] == "Increment" and e["role"] == "button")
        check("Stop", operator("stop")["ok"])
        check("Stop revokes browser", call("browser.click", reference=button["reference"])["errorCode"] == "approval_required")
        check("browser remains alive", chrome.poll() is None)
        check("Quit", operator("quit")["ok"])
        child.wait(5)
        check("browser survives operator Quit", chrome.poll() is None)
        child = subprocess.Popen(["/usr/bin/python3", str(args.runtime / "desktop.py")],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
        check("replacement handshake", operator("hello", processId=os.getpid(), executable="/usr/bin/true")["ok"])
        poll(lambda: operator("state")["state"]["browser"]["connected"], 30)
        check("extension reconnects to new owner", True)
        poll(lambda: call("status")["data"]["ready"])
        check("replacement starts Off", call("browser.tabs")["errorCode"] == "approval_required")
        check("replacement grant", operator("arm", scopes=["browser"], duration=10)["ok"])
        check("replacement rejects old reference", call("browser.click", reference=button["reference"])["errorCode"] == "stale_reference")
        check("replacement provider usable", call("browser.tabs")["accepted"])
    if args.locked:
        from gi.repository import Gio, GLib
        check("locked browser preference defaults off", not operator("state")["state"]["browserWhileLocked"]["enabled"])
        check("enable browser lock preference", operator("browser_while_locked", enabled=True)["ok"])
        check("mixed grant", operator("arm", scopes=["observe", "control", "browser"], duration=120)["ok"])
        original = operator("state")["state"]["deployment"]["grant"]
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        user_path = system.call_sync("org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
            "GetUser", GLib.Variant("(u)", (os.getuid(),)), GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, 1000, None).unpack()[0]
        session_path = system.call_sync("org.freedesktop.login1", user_path, "org.freedesktop.DBus.Properties", "Get",
            GLib.Variant("(ss)", ("org.freedesktop.login1.User", "Display")), GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 1000, None).unpack()[0][1]
        def independently_locked():
            return system.call_sync("org.freedesktop.login1", session_path, "org.freedesktop.DBus.Properties", "Get",
                GLib.Variant("(ss)", ("org.freedesktop.login1.Session", "LockedHint")), GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 1000, None).unpack()[0] is True
        try:
            bus.call_sync("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", "Lock", None, None, Gio.DBusCallFlags.NONE, 1000, None)
        except GLib.Error as error:
            # GNOME may withhold this reply during the transition. Only the
            # independent logind observation below establishes a real lock.
            if not error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.TIMED_OUT):
                raise
        check("independent OS lock observed", poll(independently_locked, 45))
        poll(lambda: operator("state")["state"]["browserWhileLocked"]["active"], 45)
        current = operator("state")["state"]["deployment"]["grant"]
        check("same approval retained without deadline extension", current["grantId"] == original["grantId"] and current["remainingSeconds"] <= original["remainingSeconds"])
        check("locked desktop observation refused", call("capture").get("errorCode") == "desktop_locked_browser_only")
        check("locked desktop input refused", call("input.key", key="a").get("errorCode") == "desktop_locked_browser_only")
        check("new locked approval refused", call("grant.request", scopes=["devtools"], reason="Additional locked access").get("errorCode") == "approval_unavailable_while_locked")
        check("locked DevTools remains separate", call("browser.eval", tabId=tab, expression="1").get("errorCode") == "approval_required")
        snap = call("browser.snapshot", tabId=tab)
        check("locked page snapshot", snap["accepted"])
        button = next(e for e in snap["data"]["elements"] if e["name"] == "Increment" and e["role"] == "button")
        entry = next(e for e in snap["data"]["elements"] if e["name"] == "Fixture text" and e["role"] == "textbox")
        before = effects["clicks"]
        check("locked click accepted", call("browser.click", reference=button["reference"])["accepted"])
        poll(lambda: effects["clicks"] == before + 1)
        check("locked click independent HTTP effect", independently_locked())
        check("locked Unicode typing accepted", call("browser.type", reference=entry["reference"], text="Locked café 世界")["accepted"])
        poll(lambda: effects["text"].endswith("Locked café 世界"))
        check("locked typing independent HTTP effect", independently_locked())
        image = call("browser.capture", tabId=tab)
        check("locked tab capture", image["accepted"])
        artifact = image["data"]["artifact"]
        args.output.with_suffix(".locked.png").write_bytes(Path(artifact["guestPath"]).read_bytes())
        check("locked Pause", operator("pause")["ok"] and call("browser.tabs").get("errorCode") == "access_paused")
        check("locked Resume", operator("resume")["ok"] and call("browser.tabs")["accepted"])
        check("disable revokes retained grant", operator("browser_while_locked", enabled=False)["ok"] and operator("state")["state"]["deployment"]["grant"] is None)
        check("OS remains locked after browser task", independently_locked())
    report(complete=True)
except BaseException as error:
    if child and child.poll() is None:
        try:
            print("failure state", json.dumps(operator("state")), file=log, flush=True)
        except Exception:
            pass
    report(complete=True, failure=str(error))
    raise
finally:
    if child and child.poll() is None:
        child.stdin.close()
        try:
            child.wait(5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    if chrome:
        if chrome.poll() is None:
            os.killpg(chrome.pid, 15)
        try:
            chrome.wait(10)
        except subprocess.TimeoutExpired:
            os.killpg(chrome.pid, 9)
            chrome.wait()
    if server:
        server.shutdown()
        server.server_close()
    shutil.rmtree(profile, ignore_errors=True)
    shutil.rmtree(data, ignore_errors=True)
    for path, previous in saved.items():
        if previous:
            path.write_bytes(previous[0])
            path.chmod(previous[1])
        else:
            path.unlink(missing_ok=True)
