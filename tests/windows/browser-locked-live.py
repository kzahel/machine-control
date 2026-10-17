"""Source-native Windows workstation browser acceptance; leaves OS locked.

Run only inside an exclusively claimed test VM. The controller owns staging,
native launch, power restoration and claim release. Uses Chrome for Testing,
real native approval, inherited local operator commands and independent HTTP
effects. Never installs or invokes a protected unlock provider.
"""
import argparse
import base64
import concurrent.futures
import ctypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import winreg
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "client"))
from control_session import ControlSession
from cdp_socket import CdpSocket


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--chrome", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    exe = args.runtime / "machine-control-windows.exe"
    session = ctypes.c_uint()
    assert ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
    assert session.value > 0, "Launch through the target's interactive-session runner"
    checks = []
    effects = {"clicks": 0, "text": ""}
    child = chrome = owner = websocket = None
    log = (args.output / "actor.log").open("w")
    profile = args.output / "profile"
    local = Path(os.environ["LOCALAPPDATA"]) / "MachineControl"
    manifest = local / "packages/desktop/browser-host.json"
    preference = local / "presentation/desktop-browser-while-locked.json"
    saved = {path: path.read_bytes() if path.exists() else None for path in [manifest, preference]}
    key_path = r"Software\Google\Chrome\NativeMessagingHosts\org.machine_control.browser"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as key:
            old_key = winreg.QueryValueEx(key, "")[0]
    except FileNotFoundError:
        old_key = None

    def save(passed=False, error=None):
        (args.output / "result.json").write_text(json.dumps({"passed": passed, "checks": checks,
            "effects": effects, "failure": error}, indent=2), encoding="utf-8")

    def check(label, value):
        assert value, label
        checks.append(label)
        save()
        print(label, flush=True)

    def poll(fn, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = fn()
            if value:
                return value
            time.sleep(.2)
        raise AssertionError("Timed out waiting for independent state")

    def operator(method, **fields):
        child.stdin.write(json.dumps(dict(method=method, **fields)) + "\n")
        child.stdin.flush()
        reply = json.loads(child.stdout.readline())
        assert reply.get("ok") or (method == "browser.setup" and
            reply.get("error") == "Browser registered; clipboard unavailable"), (method, reply.get("error"))
        return reply

    def direct(operation, **fields):
        reply = subprocess.run([str(exe), "call", "--profile", "user", "--instance", "desktop",
            "--session-id", str(session.value)], input=json.dumps(dict(operation=operation, **fields)),
            capture_output=True, text=True, timeout=150)
        return json.loads(reply.stdout)

    def start_owner(scopes):
        value = ControlSession({"command": [str(exe), "channel", "--profile", "user", "--instance", "desktop",
            "--session-id", str(session.value)]}, scopes=scopes, reason="Locked browser fixture", wait=90, duration=180)
        try:
            value.wait()
        except BaseException:
            value.close()
            raise
        return value

    def call(operation, **fields):
        reply = owner.call(dict(operation=operation, **fields))
        assert reply.get("accepted"), (operation, reply.get("errorCode"))
        return reply.get("data", {})

    def locked():
        pointer = ctypes.c_void_p()
        size = ctypes.c_uint()
        api = ctypes.windll.wtsapi32
        assert api.WTSQuerySessionInformationW(None, session.value, 25, ctypes.byref(pointer), ctypes.byref(size))
        try:
            assert size.value >= 20
            flags = ctypes.c_int.from_address(pointer.value + 16).value
            assert flags in (0, 1)
            return flags == 0
        finally:
            api.WTSFreeMemory(pointer)

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            body = b'''<!doctype html><meta charset="utf-8"><title>Locked Windows browser fixture</title>
<body style="background:#cef"><h1>Locked Windows browser fixture</h1>
<button onclick="fetch('/increment',{method:'POST'})">Increment</button>
<input aria-label="Fixture text" oninput="fetch('/text',{method:'POST',body:this.value})"></body>'''
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if self.path == "/increment":
                effects["clicks"] += 1
            elif self.path == "/text":
                effects["text"] = body.decode()
            self.send_response(204)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/"
    try:
        check("initial OS unlocked", not locked())
        child = subprocess.Popen([str(exe), "desktop"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=log, text=True)
        operator("hello", processId=os.getpid())
        poll(lambda: operator("state")["state"].get("availability", {}).get("healthy", True))
        check("no initial grant", direct("grant.status")["data"].get("grant") is None)
        operator("browser_while_locked", enabled=True)
        check("preference grants no authority", direct("browser.tabs").get("errorCode") == "approval_required")
        operator("browser.setup")
        chrome = subprocess.Popen([str(args.chrome), "--user-data-dir=" + str(profile), "--no-first-run",
            "--no-default-browser-check", "--disable-gpu", "--enable-logging=stderr", "--use-mock-keychain", "--remote-debugging-port=0",
            "--disable-extensions-except=" + str(args.runtime / "browser-extension"),
            "--load-extension=" + str(args.runtime / "browser-extension"), url], stdout=log, stderr=log)
        port_file = profile / "DevToolsActivePort"
        def debug_address():
            try:
                lines = port_file.read_text().splitlines()
            except OSError:
                return None
            return lines[:2] if len(lines) >= 2 and lines[0].isdigit() else None
        port, path = poll(debug_address, 180)
        check("test browser running", chrome.poll() is None)
        browser_debug = CdpSocket("ws://127.0.0.1:" + port + path, timeout=60)
        settings_id = browser_debug.call("Target.createTarget", {"url": "chrome://extensions/"})["result"]["targetId"]
        with urlopen("http://127.0.0.1:" + port + "/json/list", timeout=5) as response:
            settings_page = next(p for p in json.load(response) if p["id"] == settings_id)
        settings_debug = CdpSocket(settings_page["webSocketDebuggerUrl"], timeout=60)
        try:
            configured = settings_debug.call("Runtime.evaluate", {"expression": "new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))", "awaitPromise": True})
            check("test browser developer mode", "exceptionDetails" not in configured.get("result", {}))
        finally:
            settings_debug.close()
            browser_debug.call("Target.closeTarget", {"targetId": settings_id})
            browser_debug.close()
        poll(lambda: operator("state")["state"]["browser"]["connected"])
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pending = pool.submit(direct, "grant.request", scopes=["observe", "control", "browser", "devtools"],
                reason="Verify browser control behind the Windows lock screen", durationSeconds=600, timeoutSeconds=120)
            poll(lambda: operator("state")["state"].get("pending"))
            script = r'''Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;
$condition=[Windows.Automation.AndCondition]::new(
[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ProcessIdProperty,PID),
[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'Allow'),
[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button));
$deadline=[DateTime]::UtcNow.AddSeconds(15); do {$button=[Windows.Automation.AutomationElement]::RootElement.FindFirst([Windows.Automation.TreeScope]::Descendants,$condition); if($button){break}; Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $deadline);
if(!$button){throw 'Native approval button missing'}; $button.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()'''.replace("PID", str(child.pid))
            encoded = base64.b64encode(script.encode("utf-16-le")).decode()
            subprocess.run(["powershell.exe", "-NoProfile", "-EncodedCommand", encoded], check=True, timeout=25, stdout=log, stderr=log)
            check("real native approval", pending.result(timeout=30)["accepted"])
        original = direct("grant.status")["data"]["grant"]
        owner = start_owner(["browser"])
        tab = poll(lambda: next((t["tabId"] for t in call("browser.tabs")["tabs"] if t["url"] == url), None))
        check("unlocked browser baseline", bool(call("browser.snapshot", tabId=tab)["elements"]))
        owner.close(); owner = None
        assert ctypes.windll.user32.LockWorkStation()
        poll(locked)
        poll(lambda: operator("state")["state"]["browserWhileLocked"]["active"])
        grant = direct("grant.status")["data"]["grant"]
        check("same approval and bounded remaining lifetime", grant["grantId"] == original["grantId"] and grant["remainingSeconds"] <= original["remainingSeconds"])
        check("desktop capture refused while locked", not direct("screenshot").get("accepted"))
        check("new locked desktop approval refused", direct("grant.request", scopes=["control"], reason="locked expansion").get("errorCode") == "approval_unavailable_while_locked")
        owner = start_owner(["browser"])
        snap = call("browser.snapshot", tabId=tab)
        button = next(e["reference"] for e in snap["elements"] if e["name"] == "Increment" and e["role"] == "button")
        entry = next(e["reference"] for e in snap["elements"] if e["name"] == "Fixture text" and e["role"] == "textbox")
        call("browser.click", reference=button)
        poll(lambda: effects["clicks"] == 1)
        check("locked click independent HTTP effect", locked())
        call("browser.type", reference=entry, text="Locked café 世界")
        poll(lambda: effects["text"] == "Locked café 世界")
        check("locked Unicode independent HTTP effect", locked())
        image = call("browser.capture", tabId=tab)
        source = Path(direct("status")["data"]["artifactRoot"]) / (image["artifactId"] + ".png")
        (args.output / "locked-tab.png").write_bytes(source.read_bytes())
        check("locked browser PNG", source.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        operator("pause")
        owner.close(); owner = None
        check("Pause fences browser", direct("browser.tabs").get("errorCode") == "access_paused")
        operator("resume")
        owner = start_owner(["browser", "devtools"])
        check("Resume retains approval", direct("grant.status")["data"]["grant"]["grantId"] == original["grantId"])
        endpoint = call("browser.endpoint")["devtoolsEndpoint"].replace("<tabId>", str(tab))
        websocket = CdpSocket(endpoint, timeout=60)
        result = websocket.call("Runtime.evaluate", {"expression": "document.title", "returnByValue": True})
        check("live DevTools behind lock", "Locked Windows browser fixture" in json.dumps(result) and locked())
        websocket.close(); websocket = None
        owner.close(); owner = None
        operator("browser_while_locked", enabled=False)
        check("disable revokes retained grant", direct("grant.status")["data"].get("grant") is None)
        check("OS remains locked and no unlock helper was armed", locked())
        save(True)
    except BaseException as error:
        if child and child.poll() is None:
            try:
                print(json.dumps(operator("state")["state"].get("browser")), file=log, flush=True)
            except Exception:
                pass
        save(False, str(error))
        raise
    finally:
        if websocket:
            websocket.close()
        if owner:
            owner.close()
        if chrome:
            subprocess.run(["taskkill.exe", "/PID", str(chrome.pid), "/T", "/F"], stdout=log, stderr=log)
            chrome.wait(timeout=15)
        if child and child.poll() is None:
            child.stdin.close()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
        server.shutdown(); server.server_close()
        for path, previous in saved.items():
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous)
        if old_key is None:
            try:
                winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, key_path, winreg.KEY_WOW64_32KEY)
            except FileNotFoundError:
                pass
        else:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE | winreg.KEY_WOW64_32KEY) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, old_key)
        log.close()


if __name__ == "__main__":
    main()
