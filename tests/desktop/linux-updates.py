#!/usr/bin/env python3
"""Signed AppImage replacement through an explicitly built localhost sender."""

import argparse
import concurrent.futures
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time

parser = argparse.ArgumentParser()
for name in ["app", "incoming", "tls-cert", "tls-key", "runtime", "output"]:
    parser.add_argument("--" + name, type=Path, required=True)
parser.add_argument("--revision", required=True)
parser.add_argument("--chrome", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.runtime))
import linuxui
from gi.repository import Gio, GLib

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
endpoint = Path(os.environ["XDG_RUNTIME_DIR"]) / "machine-control-desktop/desktop.sock"
checks = []
log = args.output.with_suffix(".log").open("w")
process = chrome = server = browser_server = None
effects = {"clicks": 0, "text": ""}
tampered = True
pause_download = False
download_started = threading.Event()
download_allowed = threading.Event()
profile = args.output.with_suffix(".profile")
data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "machine-control"
config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
manifests = [config / n / "NativeMessagingHosts/org.machine_control.browser.json"
             for n in ["google-chrome", "google-chrome-for-testing", "chromium"]]
saved = {p: (p.read_bytes(), p.stat().st_mode & 0o777) if p.exists() else None for p in manifests}
if data.exists():
    raise SystemExit("Preserve existing browser installation; acceptance requires unused app data")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def report(complete=False, failure=None):
    args.output.write_text(json.dumps({"complete": complete, "passed": complete and not failure,
                                      "failure": failure, "checks": checks}, indent=2))


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})
    report()
    if not value:
        raise AssertionError(name)


def poll(fn, timeout=25):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            value = fn()
            if value:
                return value
        except (OSError, linuxui.UIError, GLib.Error):
            pass
        time.sleep(.15)
    raise AssertionError("Timed out waiting for native update effect")


def call(operation, **params):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(35)
        client.connect(str(endpoint))
        client.sendall(json.dumps({"operation": operation, **params}).encode() + b"\n")
        return json.loads(client.makefile("rb").readline(24 * 1024 * 1024))


def nodes(app="machine-control"):
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)
    root = linuxui.choose_application(linuxui.desktop(), app)
    root.clear_cache()
    return list(linuxui.walk(root, 25, 2000))


def widget(label, app="machine-control"):
    found = [n for n, i in nodes(app) if i["name"] == label and i["role"] == "push button"]
    return found[0] if len(found) == 1 else None


def press(label, app="machine-control"):
    check("native UI " + label, poll(lambda: widget(label, app)).do_action(0))
    time.sleep(.25)


def errors():
    values = []
    for node, info in nodes():
        values.append(info["name"])
        if "Text" in info["interfaces"]:
            values.append(linuxui.safe(lambda: linuxui.Atspi.Text.get_text(node, 0, -1), ""))
    return " ".join(values).lower()


def dbus(dest, path, interface, method, params):
    return bus.call_sync(dest, path, interface, method, params, None, Gio.DBusCallFlags.NONE, 3000, None).unpack()


def menu(label):
    items = dbus("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.freedesktop.DBus.Properties", "Get",
                 GLib.Variant("(ss)", ("org.kde.StatusNotifierWatcher", "RegisteredStatusNotifierItems")))[0]
    for item in items:
        if "@" not in item:
            continue
        dest, path = item.split("@", 1)
        props = dbus(dest, path, "org.freedesktop.DBus.Properties", "GetAll", GLib.Variant("(s)", ("org.kde.StatusNotifierItem",)))[0]
        if props.get("Id") != "tray-icon tray app control":
            continue
        layout = dbus(dest, props["Menu"], "com.canonical.dbusmenu", "GetLayout", GLib.Variant("(iias)", (0, -1, [])))[1]
        def find(node):
            identifier, fields, children = node
            if fields.get("label", "").replace("_", "").replace(" Machine Control", "").rstrip("…") == label:
                return identifier
            for child in children:
                value = find(child)
                if value is not None:
                    return value
            return None
        identifier = find(layout)
        if identifier is None:
            raise AssertionError("Missing tray item")
        dbus(dest, props["Menu"], "com.canonical.dbusmenu", "Event",
             GLib.Variant("(isvu)", (identifier, "clicked", GLib.Variant("i", 0), 0)))
        time.sleep(.3)
        return
    raise AssertionError("Missing native tray")


class Feed(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        print("HTTPS fixture request:", self.path, file=log, flush=True)
        if self.path.startswith("/updates/"):
            body = json.dumps({"version": "0.5.0", "notes": "Linux update acceptance",
                               "pub_date": "2026-10-02T00:00:00Z", "platforms": {
                                   "linux-x86_64": {"url": "https://localhost:42467/download",
                                     "signature": Path(str(args.incoming) + ".sig").read_text().strip()}}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/download":
            corrupt = tampered
            self.send_response(200)
            self.send_header("Content-Length", str(args.incoming.stat().st_size + (8 if corrupt else 0)))
            self.end_headers()
            with args.incoming.open("rb") as source:
                self.wfile.write(source.read(65536))
                self.wfile.flush()
                download_started.set()
                if pause_download and not download_allowed.wait(30):
                    return
                shutil.copyfileobj(source, self.wfile)
                if corrupt:
                    self.wfile.write(b"tampered")
        else:
            self.send_error(404)


class BrowserFixture(BaseHTTPRequestHandler):
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
            body = b"ok"
        else:
            body = b'''<!doctype html><title>Installed Linux browser fixture</title>
<button onclick="fetch('/effect?click=1')">Increment</button>
<input aria-label="Fixture text" oninput="fetch('/effect?text='+encodeURIComponent(this.value))">'''
        self.send_response(200)
        self.send_header("Content-Type", "text/html;charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


try:
    check("no predecessor", not endpoint.exists())
    args.app.chmod(args.app.stat().st_mode | 0o100)
    before = digest(args.app)
    identity = json.loads(subprocess.check_output([str(args.app), "--identity"], text=True))
    check("explicit signed sender fixture", identity["version"] == "0.4.8" and identity["purpose"] == "update_sender_fixture")
    server = ThreadingHTTPServer(("127.0.0.1", 42467), Feed)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(args.tls_cert, args.tls_key)
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    process = subprocess.Popen([str(args.app)], stdout=log, stderr=log, start_new_session=True)
    poll(lambda: endpoint.exists())
    poll(lambda: widget("Settings"))
    check("sender Off", call("status")["data"]["grant"] is None)
    press("Settings")
    press("Check for updates")
    poll(lambda: widget("Install and restart"))
    press("Install and restart")
    poll(lambda: "signature" in errors(), 45)
    check("tampered download rejected", digest(args.app) == before)
    check("tamper leaves resident Off", call("status")["data"]["grant"] is None)

    tampered = False
    pause_download = True
    download_started.clear()
    press("Install and restart")
    check("real download started", download_started.wait(10))
    with concurrent.futures.ThreadPoolExecutor() as pool:
        pending = pool.submit(call, "grant.request", scopes=["observe", "control"], durationSeconds=90,
                              reason="Update race refusal fixture")
        press("Allow", app="machine-control-approval")
        check("grant armed during download", pending.result()["accepted"])
    download_allowed.set()
    poll(lambda: "stop access" in errors(), 45)
    check("native replacement gate refuses active access", digest(args.app) == before and call("status")["data"]["grant"] is not None)
    menu("Stop access")
    check("Stop clears race grant", call("status")["data"]["grant"] is None)
    menu("Open")
    press("Permissions")
    press("Set up")
    profile.mkdir()
    hosts = profile / "NativeMessagingHosts"
    hosts.mkdir()
    shutil.copyfile(manifests[1], hosts / manifests[1].name)
    chrome = subprocess.Popen([str(args.chrome), "--user-data-dir=" + str(profile), "--no-first-run",
                               "--no-default-browser-check", "--password-store=basic", "--disable-gpu",
                               "--ozone-platform=wayland", "--load-extension=" + str(data / "extension"),
                               "--disable-extensions-except=" + str(data / "extension"), "about:blank"],
                              stdout=log, stderr=log, start_new_session=True)
    # Optional browser scope is approved through the visible native dialog.
    with concurrent.futures.ThreadPoolExecutor() as pool:
        pending = pool.submit(call, "grant.request", scopes=["browser"], durationSeconds=90,
                              reason="Browser-open replacement fixture")
        press("Allow", app="machine-control-approval")
        check("native browser grant", pending.result()["accepted"])
    poll(lambda: call("browser.tabs").get("accepted"), 35)
    check("installed Chrome native host connected", True)
    browser_generation = call("status")["generation"]
    menu("Stop access")
    menu("Settings")
    pause_download = False
    press("Check for updates")
    poll(lambda: widget("Install and restart"))
    press("Install and restart")
    poll(lambda: digest(args.app) == digest(args.incoming), 60)
    check("exact signed incoming bytes installed", True)
    poll(lambda: call("status")["generation"] != browser_generation, 40)
    check("automatic relaunch with access Off", call("status")["data"]["grant"] is None)
    check("exact incoming source", call("status")["data"]["sourceRevision"] == args.revision)
    new = json.loads(subprocess.check_output([str(args.app), "--identity"], text=True))
    check("new compiled version and production purpose", new["version"] == "0.5.0" and new["purpose"] == "candidate")
    check("browser survives replacement", chrome.poll() is None)
    check("old generation refused", call("browser.tabs", expectedGeneration=browser_generation)["errorCode"] == "stale_generation")
    poll(lambda: widget("Settings"), 35)
    with concurrent.futures.ThreadPoolExecutor() as pool:
        pending = pool.submit(call, "grant.request", scopes=["browser"], durationSeconds=30,
                              reason="Post-update browser reconnect")
        press("Allow", app="machine-control-approval")
        check("new owner native approval", pending.result()["accepted"])
    poll(lambda: call("browser.tabs").get("accepted"), 35)
    check("browser reconnects after replacement", True)
    browser_server = ThreadingHTTPServer(("127.0.0.1", 0), BrowserFixture)
    threading.Thread(target=browser_server.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:" + str(browser_server.server_port) + "/"
    tabs = call("browser.tabs")["data"]["tabs"]
    check("unambiguous isolated browser tab", len(tabs) == 1)
    tab = tabs[0]["tabId"]
    check("updated browser navigate", call("browser.navigate", tabId=tab, url=url)["accepted"])
    poll(lambda: any(t["url"] == url for t in call("browser.tabs")["data"]["tabs"]))
    snapshot = poll(lambda: call("browser.snapshot", tabId=tab).get("data", {}).get("elements"))
    button = next(n for n in snapshot if n["name"] == "Increment" and n["role"] == "button")
    entry = next(n for n in snapshot if n["name"] == "Fixture text" and n["role"] == "textbox")
    check("updated browser click delivery", call("browser.click", reference=button["reference"])["accepted"])
    poll(lambda: effects["clicks"] == 1)
    check("updated independent browser click effect", True)
    check("updated browser Unicode delivery", call("browser.type", reference=entry["reference"],
          text="Updated Linux 世界 café")["accepted"])
    poll(lambda: effects["text"] == "Updated Linux 世界 café")
    check("updated independent browser Unicode effect", True)
    capture = call("browser.capture", tabId=tab)
    check("updated browser capture", capture["accepted"])
    artifact = capture["data"]["artifact"]
    check("updated browser capture hash", digest(Path(artifact["guestPath"])) == artifact["sha256"])
    check("updated browser DevTools remains separate", call("browser.eval", tabId=tab,
          expression="1+1")["errorCode"] == "approval_required")
    menu("Stop access")
    menu("Quit")
    poll(lambda: not endpoint.exists())
    check("updated Quit removes endpoint", True)
    report(complete=True)
except BaseException as error:
    try:
        print("Native update diagnostics:", errors(), file=log, flush=True)
    except Exception:
        pass
    report(complete=True, failure=str(error))
    raise
finally:
    download_allowed.set()
    if endpoint.exists():
        try:
            menu("Stop access")
            menu("Quit")
        except Exception:
            pass
    if process and process.poll() is None:
        try:
            process.wait(5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, 15)
            process.wait(5)
    if chrome:
        if chrome.poll() is None:
            os.killpg(chrome.pid, 15)
        chrome.wait(10)
    if server:
        server.shutdown()
        server.server_close()
    if browser_server:
        browser_server.shutdown()
        browser_server.server_close()
    shutil.rmtree(profile, ignore_errors=True)
    shutil.rmtree(data, ignore_errors=True)
    for path, previous in saved.items():
        if previous:
            path.write_bytes(previous[0])
            path.chmod(previous[1])
        else:
            path.unlink(missing_ok=True)
