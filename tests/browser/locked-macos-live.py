#!/usr/bin/env python3
"""Guest-only browser feasibility probe; deliberately leaves the guest locked.

Caller owns doctor, an exclusive ordinary claim, and final guest shutdown or
authorized unlock. Requires a standing appliance observer. Optional isolated
workstation validation uses real native consent, pressed through that observer.
Never enables covered unlock. Uses Chrome for Testing only.
"""
import argparse
import concurrent.futures
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lock", action="store_true", required=True)
    parser.add_argument("--workstation-app", type=Path,
                        help="Source-native browser-locked-fixture app; requires native approval through the appliance")
    args = parser.parse_args()
    assert subprocess.check_output(["sysctl", "-n", "hw.model"]).decode().startswith("VirtualMac")
    app = Path.home() / "mc-cft/chrome-mac-arm64/Google Chrome for Testing.app"
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    assert info["CFBundleIdentifier"] == "com.google.chrome.for.testing"
    executable = Path.home() / "Applications/Machine Control.app/Contents/MacOS/macui"
    resident_socket = Path.home() / "Library/Application Support/MachineControl/control.sock"
    spec = importlib.util.spec_from_file_location("cdp", args.source_root / "platforms/chromeos/cdp.py")
    cdp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cdp)
    checks = []

    def check(name, value):
        assert value, name
        checks.append(name)
        print("PASS:", name, flush=True)

    def poll(fn, timeout=25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = fn()
            if value:
                return value
            time.sleep(.15)
        raise AssertionError("Timed out waiting for fixture state")

    def raw(operation, path=None, **fields):
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(20)
            connection.connect(str(path or resident_socket))
            connection.sendall(json.dumps(dict(operation=operation, claimId=args.claim, **fields)).encode() + b"\n")
            result = json.loads(connection.makefile("rb").readline(32 * 1024 * 1024))
        return result

    def call(operation, **fields):
        result = raw(operation, **fields)
        assert result.get("accepted"), (operation, result.get("errorCode"))
        return result.get("data", {})

    def locked():
        roots = plistlib.loads(subprocess.check_output(["ioreg", "-a", "-l", "-d", "1"]))
        root = roots[0] if isinstance(roots, list) else roots
        value = root.get("IOConsoleLocked")
        assert isinstance(value, bool), "Independent lock observation unavailable"
        return value

    initial = call("status")
    check("standing appliance authority", initial["deployment"]["policy"]["grantMode"] == "standing")
    check("initial console unlocked", not locked())
    check("covered unlock disabled", not initial["lockedUse"]["enabled"])
    effects = {"count": 0, "text": None, "navigation": False}

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if self.path == "/increment":
                effects["count"] += 1
            elif self.path == "/text":
                effects["text"] = body.decode()
            self.send_response(204)
            self.end_headers()

        def do_GET(self):
            effects["navigation"] |= self.path == "/second"
            body = b'''<!doctype html><title>Locked browser fixture</title>
<body style="background:#9ee"><h1>Locked browser fixture</h1>
<button onclick="fetch('/increment',{method:'POST'})">Increment</button>
<input aria-label="Fixture text" oninput="fetch('/text',{method:'POST',body:this.value})">
<a href="/second">Next page</a></body>'''
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    browser = candidate = None
    base_socket = resident_socket
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="mc-browser-locked-") as scratch:
            root = Path(scratch)
            if args.workstation_app:
                candidate_info = plistlib.loads((args.workstation_app / "Contents/Info.plist").read_bytes())
                executable = args.workstation_app / "Contents/MacOS/macui"
                resident_socket = Path(candidate_info["MCFixtureSocket"])
                assert not resident_socket.exists(), "Candidate endpoint must be unused"
                with (args.output / "candidate.log").open("w") as log:
                    candidate = subprocess.Popen([str(executable)], stdin=subprocess.PIPE,
                        stdout=log, stderr=log, text=True)
                poll(resident_socket.exists)
                poll(lambda: call("status")["desktopState"] == "unlocked")
                check("workstation starts without approval or lock opt-in",
                      call("grant.status")["grant"] is None and not call("status")["browserWhileLocked"]["enabled"])
                candidate.stdin.write("enable\n"); candidate.stdin.flush()
                poll(lambda: call("status")["browserWhileLocked"]["enabled"])
            profile = root / "profile"
            hosts = profile / "NativeMessagingHosts"
            hosts.mkdir(parents=True)
            extension = root / "extension"
            shutil.copytree(args.source_root / "providers/chrome-extension", extension)
            (hosts / "org.machine_control.browser.json").write_text(json.dumps({
                "name": "org.machine_control.browser", "description": "Locked browser fixture",
                "path": str(executable), "type": "stdio",
                "allowed_origins": ["chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/"],
            }))
            url = f"http://127.0.0.1:{server.server_port}"
            browser = subprocess.Popen([str(app / "Contents/MacOS" / info["CFBundleExecutable"]),
                "--user-data-dir=" + str(profile), "--remote-debugging-port=0", "--no-first-run",
                "--no-default-browser-check", "--use-mock-keychain", "--no-proxy-server",
                "--disable-extensions-except=" + str(extension), "--load-extension=" + str(extension),
                url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            port_file = profile / "DevToolsActivePort"
            poll(port_file.exists)
            port, endpoint = port_file.read_text().splitlines()[:2]
            browser_cdp = cdp.CDP(f"ws://127.0.0.1:{port}{endpoint}")
            settings_id = browser_cdp.call("Target.createTarget", url="chrome://extensions/")["targetId"]
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
                target = next(t for t in json.load(response) if t["id"] == settings_id)
            settings = cdp.CDP(target["webSocketDebuggerUrl"])
            try:
                settings.call("Runtime.evaluate", expression="new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))", awaitPromise=True)
            finally:
                settings.close()
                browser_cdp.call("Target.closeTarget", targetId=settings_id)
                browser_cdp.close()
            poll(lambda: call("status")["browser"]["connected"])
            if candidate:
                check("preference alone grants no browser access", raw("browser.tabs").get("errorCode") == "approval_required")
                # Real native consent, pressed by the independent appliance
                # resident. The fixture's operator channel cannot approve.
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    approval = pool.submit(call, "grant.request", scopes=["observe", "control", "browser"],
                        reason="Verify browser access while locked", durationSeconds=300, timeoutSeconds=120)
                    poll(lambda: call("grant.status")["pendingRequest"])
                    def allow_button():
                        result = raw("snapshot", path=base_socket, target=str(candidate.pid),
                            query="Allow", projection="compact", maxDepth=30, maxElements=600)
                        return next((e["reference"] for e in result.get("data", {}).get("elements", [])
                                     if e.get("label") == "Allow" and e.get("role") == "AXButton"), None)
                    button = poll(allow_button)
                    assert raw("action", path=base_socket, reference=button, action="press")["accepted"]
                    approval.result(timeout=30)
                check("native workstation approval", call("grant.status")["grant"] is not None)
                granted = call("grant.status")["grant"]
            tab = poll(lambda: next((t["tabId"] for t in call("browser.tabs")["tabs"] if t["url"].rstrip("/") == url), None))
            check("unlocked browser baseline", bool(call("browser.snapshot", tabId=tab)["elements"]))
            # Native lock only; no root helper, password, or unlock request.
            ctypes.CDLL("/System/Library/PrivateFrameworks/login.framework/login").SACLockScreenImmediate()
            poll(locked)
            time.sleep(1)
            check("OS independently reports locked", locked())
            check("resident observes lock", call("status")["desktopState"] == "locked")
            if candidate:
                check("workstation approval identity and expiry retained",
                      all(call("grant.status")["grant"][key] == granted[key] for key in ["grantId", "expiresAt"]))
                check("locked desktop observation fenced", raw("capture", scope="display").get("errorCode") == "desktop_locked_browser_only")
                check("locked desktop input fenced", raw("input.key", key="a").get("errorCode") == "desktop_locked_browser_only")
                check("DevTools still needs separate approval", raw("browser.eval", expression="1").get("errorCode") == "approval_required")
                check("new approval still requires unlock", raw("grant.request", scopes=["devtools"], reason="extra").get("errorCode") == "approval_unavailable_while_locked")
                with socket.socket(socket.AF_UNIX) as owner:
                    owner.settimeout(15)
                    owner.connect(str(resident_socket))
                    stream = owner.makefile("rb")
                    sequence = 0
                    def exchange(operation, **fields):
                        nonlocal sequence
                        sequence += 1
                        owner.sendall(json.dumps(dict(operation=operation, requestId=operation,
                            requestSequence=sequence, **fields)).encode() + b"\n")
                        reply = json.loads(stream.readline())
                        assert reply.get("accepted"), (operation, reply.get("errorCode"))
                        return reply.get("data", {})
                    offer = exchange("control.open", schema="machine-control-admission/v1", scopes=["browser"],
                        reason="Locked browser owner", durationSeconds=60, waitSeconds=30)
                    if offer["state"] != "offered":
                        offer = poll(lambda: (value if (value := exchange("control.status"))["state"] == "offered" else None))
                    active = exchange("control.accept", offerGeneration=offer["offerGeneration"])
                    response = exchange("control.dispatch", sessionId=active["sessionId"],
                        resourceGenerations=active["resourceGenerations"], request={"operation":"browser.tabs"})
                    check("browser owner admitted without covered unlock", response.get("accepted") and locked())
                    exchange("control.cancel")
            check("locked tab enumeration", any(t["tabId"] == tab for t in call("browser.tabs")["tabs"]))
            snapshot = call("browser.snapshot", tabId=tab)
            check("locked browser AX snapshot", bool(snapshot["elements"]))
            def reference(label):
                return next(e["reference"] for e in call("browser.snapshot", tabId=tab)["elements"] if e.get("name") == label)
            call("browser.click", reference=reference("Increment"))
            poll(lambda: effects["count"] == 1)
            check("locked click independent HTTP effect", effects["count"] == 1 and locked())
            call("browser.type", reference=reference("Fixture text"), text="Locked café 世界")
            poll(lambda: effects["text"] == "Locked café 世界")
            check("locked typing independent HTTP effect", locked())
            capture = call("browser.capture", tabId=tab)
            image = Path(capture["artifactPath"]).read_bytes()
            check("locked tab PNG capture", image.startswith(b"\x89PNG\r\n\x1a\n") and len(image) > 1000)
            (args.output / "locked-tab.png").write_bytes(image)
            call("browser.navigate", tabId=tab, url=url + "/second")
            poll(lambda: effects["navigation"])
            check("locked navigation independent HTTP effect", locked())
            call("browser.release", tabId=tab)
            check("reattach while locked", bool(call("browser.snapshot", tabId=tab)["elements"]) and locked())
            final = call("status")
            check("no covered unlock or control session", final["desktopState"] == "locked" and final["lockedUse"]["controlSessionId"] is None)
            if candidate:
                candidate.stdin.write("pause\n"); candidate.stdin.flush()
                poll(lambda: raw("browser.tabs").get("errorCode") == "access_paused")
                check("Pause fences locked browser access", locked())
                candidate.stdin.write("resume\n"); candidate.stdin.flush()
                poll(lambda: raw("browser.tabs").get("accepted"))
                check("Resume preserves approval", call("grant.status")["grant"]["grantId"] == granted["grantId"])
                candidate.stdin.write("disable\n"); candidate.stdin.flush()
                poll(lambda: call("grant.status")["grant"] is None)
                check("disabling preference revokes retained access", raw("browser.tabs").get("errorCode") == "approval_required" and locked())
            (args.output / "result.json").write_text(json.dumps({"checks": checks, "effects": effects,
                "captureSha256": hashlib.sha256(image).hexdigest(), "finalLocked": locked(),
                "macOS": subprocess.check_output(["sw_vers", "-productVersion"]).decode().strip(),
                "browser": subprocess.check_output([str(app / "Contents/MacOS" / info["CFBundleExecutable"]), "--version"]).decode().strip()}, indent=2))
    finally:
        if candidate is not None:
            if candidate.poll() is None:
                try:
                    candidate.stdin.write("quit\n"); candidate.stdin.flush()
                except BrokenPipeError:
                    pass
            try:
                candidate.wait(timeout=10)
            except subprocess.TimeoutExpired:
                candidate.kill(); candidate.wait()
        if browser is not None:
            try:
                os.killpg(browser.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                browser.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(browser.pid, signal.SIGKILL)
                browser.wait()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
