#!/usr/bin/env python3
"""Headed Chrome native-messaging acceptance, with HTTP effect oracles."""

import argparse
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

parser = argparse.ArgumentParser()
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--chrome", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
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
if data.exists():
    raise SystemExit("Acceptance requires an unused app-data directory; preserve existing installations")


def report(complete=False, failure=None):
    args.output.write_text(json.dumps({"complete": complete, "passed": complete and not failure,
                                      "failure": failure, "checks": checks}, indent=2))


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
    if not select.select([child.stdout], [], [], 8)[0]:
        raise AssertionError("Operator timed out")
    return json.loads(child.stdout.readline())


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
    check("browser denied while Off", call("browser.tabs")["errorCode"] == "approval_required")
    extension = operator("browser.setup")["extensionPath"]
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
                               url], stdout=log, stderr=log, start_new_session=True)
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
    check("replacement starts Off", call("browser.tabs")["errorCode"] == "approval_required")
    check("replacement grant", operator("arm", scopes=["browser"], duration=10)["ok"])
    check("replacement rejects old reference", call("browser.click", reference=button["reference"])["errorCode"] == "stale_reference")
    check("replacement provider usable", call("browser.tabs")["accepted"])
    report(complete=True)
except BaseException as error:
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
        chrome.wait(10)
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
