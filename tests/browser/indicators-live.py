#!/usr/bin/env python3
"""Guest-local, headed Chrome for Testing indicator acceptance.

The caller owns doctor/claim/power and any resident grant approval. This runner
uses a fresh test-browser profile, the real native host and resident, an HTTP
page oracle, and an independent CDP connection to the extension worker to
observe Chrome's own tab/group state and arrange simulated user edits.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import urlopen

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--chrome", type=Path, required=True)
p.add_argument("--extension", type=Path, required=True)
p.add_argument("--host-executable", type=Path, required=True)
p.add_argument("--socket", type=Path, required=True)
p.add_argument("--cdp-client", type=Path, required=True)
p.add_argument("--claim", required=True)
p.add_argument("--client", type=Path, help="Use the installed control CLI for operations")
p.add_argument("--output", type=Path, required=True)
args = p.parse_args()
spec = importlib.util.spec_from_file_location("cdp_client", args.cdp_client)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
checks = []
oracles = {}
browser = observer = server = None
extension_id = "ncbfifkjllmnkkjmomjohinigfgdocjc"


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})
    if not value:
        raise AssertionError(name)


def poll(fn, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(.15)
    raise AssertionError("Timed out waiting for independent browser state")


def call(operation, **params):
    if args.client:
        prefix = [str(args.client), "--target", "host", "--claim", args.claim]
        if operation in {"browser.tabs", "browser.release", "browser.snapshot", "browser.click", "browser.capture"}:
            command = [*prefix, "browser", operation.split(".")[1]]
            for name, flag in [("tabId", "--tab"), ("reference", "--reference")]:
                if name in params:
                    command += [flag, str(params[name])]
        else:
            command = [*prefix, "desktop", "raw", json.dumps({"operation": operation, **params})]
        result = subprocess.run(command, env={**os.environ,
            "MACHINE_CONTROL_HOST_SOCKET": str(args.socket)}, capture_output=True,
            text=True, timeout=45)
        assert result.returncode in (0, 1), result.stderr
        reply = json.loads(result.stdout)
    else:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(40)
            client.connect(str(args.socket))
            client.sendall(json.dumps({"operation": operation, "claimId": args.claim, **params}).encode() + b"\n")
            reply = json.loads(client.makefile("rb").readline(32 * 1024 * 1024))
    if not reply.get("accepted"):
        raise AssertionError((operation, reply.get("errorCode"), reply.get("message")))
    return reply.get("data", {})


def js(expression):
    result = observer.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
    if result.get("exceptionDetails"):
        raise AssertionError(result["exceptionDetails"])
    return result.get("result", {}).get("value")


def tab(tab_id):
    return js(f"chrome.tabs.get({tab_id})")


def marker(path):
    return oracles.get(path, {}).get("marked", False)


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        oracles[data["path"]] = data
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        print("Fixture GET", self.path, flush=True)
        path = urlsplit(self.path).path
        if path.endswith(".svg"):
            data = b'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="orange"/></svg>'
            content_type = "image/svg+xml"
        else:
            link = "" if path in ("/missing", "/adopt") else '<link rel="icon" href="/site.svg">'
            data = ('''<!doctype html><html><head><title>Browser indicator fixture</title>''' + link + '''</head><body>
<button onclick="document.querySelector('link[rel=icon]').href='/updated.svg'">Change site icon</button>
<script>
function report() {
 const icons=[...document.querySelectorAll('link[rel~=icon]')];
 fetch('/oracle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
  path:location.pathname, marked:icons.some(x=>x.hasAttribute('data-machine-control-icon')),
  hrefs:icons.map(x=>x.getAttribute('href')), title:document.title
 })});
}
new MutationObserver(report).observe(document.head,{childList:true,subtree:true,attributes:true});
report();
</script></body></html>''').encode()
            content_type = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


failure = None
with tempfile.TemporaryDirectory(prefix="mc-indicator-browser-") as scratch:
    root = Path(scratch).resolve()
    try:
        profile = root / "profile"
        hosts = profile / "NativeMessagingHosts"
        hosts.mkdir(parents=True)
        (hosts / "org.machine_control.browser.json").write_text(json.dumps({
            "name": "org.machine_control.browser", "description": "Machine Control fixture host",
            "path": str(args.host_executable), "type": "stdio",
            "allowed_origins": [f"chrome-extension://{extension_id}/"],
        }))
        extension = root / "extension"
        shutil.copytree(args.extension, extension)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://localhost:{server.server_port}"
        with urlopen(url + "/probe", timeout=5) as response:
            print("Fixture probe", response.status, flush=True)
        with (root / "chrome.log").open("w") as log:
            browser = subprocess.Popen([str(args.chrome), "--user-data-dir=" + str(profile),
                "--remote-debugging-port=0", "--no-first-run", "--no-default-browser-check",
                "--use-mock-keychain", "--no-proxy-server",
                "--disable-extensions-except=" + str(extension), "--load-extension=" + str(extension),
                url + "/existing"], stdout=log, stderr=log, start_new_session=True)
        port_file = profile / "DevToolsActivePort"
        poll(lambda: port_file.exists())
        port = int(port_file.read_text().splitlines()[0])

        # Set Developer mode through Chrome's own settings API. Hand-written
        # Preferences are not trusted for this protected setting on current Mac
        # Chrome. This applies only to the disposable test-browser profile.
        browser_cdp = module.CDP(f"ws://127.0.0.1:{port}" + port_file.read_text().splitlines()[1])
        settings_id = browser_cdp.call("Target.createTarget", url="chrome://extensions/")["targetId"]
        def settings_page():
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
                targets = json.load(response)
            return next((module.CDP(t["webSocketDebuggerUrl"]) for t in targets if t["id"] == settings_id), None)
        settings = poll(settings_page)
        try:
            settings.call("Runtime.evaluate", expression="new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))", awaitPromise=True)
            def developer_mode():
                value = settings.call("Runtime.evaluate", expression="new Promise(r=>chrome.developerPrivate.getProfileConfiguration(r))", awaitPromise=True, returnByValue=True)
                return value.get("result", {}).get("value", {}).get("inDeveloperMode")
            poll(developer_mode)
        finally:
            settings.close()
            browser_cdp.call("Target.closeTarget", targetId=settings_id)
            browser_cdp.close()

        def connect_worker():
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
                targets = json.load(response)
            workers = [t for t in targets if t["type"] == "service_worker" and extension_id in t["url"]]
            return module.CDP(workers[0]["webSocketDebuggerUrl"]) if workers else None

        observer = poll(connect_worker)
        poll(lambda: call("capabilities").get("browser", {}).get("connected"))
        call("application.activate", target=str(browser.pid))
        existing = poll(lambda: next((t["tabId"] for t in call("browser.tabs")["tabs"]
                                     if t["url"] == url + "/existing"), None))
        poll(lambda: "/existing" in oracles)
        check("enumeration does not mark tabs", not marker("/existing"))
        group = js(f"chrome.tabs.group({{tabIds:[{existing}]}})")
        js(f"chrome.tabGroups.update({group},{{title:'User fixture',color:'red'}})")
        call("browser.snapshot", tabId=existing)
        poll(lambda: marker("/existing"))
        check("existing user group preserved", tab(existing)["groupId"] == group)
        check("Chrome tab strip receives SVG favicon", tab(existing)["favIconUrl"].startswith("data:image/svg+xml,"))
        if args.client:
            image = call("browser.capture", tabId=existing)
            artifact = Path(image["artifactPath"])
            fetched = root / "browser.png"
            command = [str(args.client), "--target", "host", "--claim", args.claim,
                "desktop", "artifact", str(artifact), str(fetched)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            check("installed CLI retrieves browser PNG", result.returncode == 0 and
                  json.loads(result.stdout)["accepted"] and fetched.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")
            artifact.unlink()
        new = call("browser.navigate", url=url + "/new", newTab=True, active=False)["tab"]["tabId"]
        poll(lambda: marker("/new"))
        managed = js(f"chrome.tabGroups.get({tab(new)['groupId']})")
        check("new tab named blue group", managed["title"] == "Machine Control" and managed["color"] == "blue")
        # Re-present Chrome and allow it to paint before reviewing the tab
        # strip; an earlier activation did not guarantee a fresh window frame.
        call("application.activate", target=str(browser.pid))
        time.sleep(3)
        image = call("capture", target=str(browser.pid), scope="window")
        artifact = Path(image["artifactPath"])
        shutil.copyfile(artifact, args.output.with_suffix(".png"))
        artifact.unlink()
        check("target-native window capture retained for tab-strip review", True)
        check("existing user group metadata unchanged", js(f"chrome.tabGroups.get({group})")["title"] == "User fixture")
        call("browser.navigate", tabId=new, url=url + "/next")
        poll(lambda: marker("/next"))
        check("marker survives document navigation", True)
        snap = call("browser.snapshot", tabId=existing)
        button = next(e for e in snap["elements"] if e["name"] == "Change site icon")
        call("browser.click", reference=button["reference"])
        time.sleep(.5)
        check("marker survives site icon mutation", marker("/existing"))
        missing = call("browser.navigate", url=url + "/missing", newTab=True, active=False)["tab"]["tabId"]
        poll(lambda: marker("/missing"))
        check("page without icon has fallback marker", True)
        # Arrange a person's edit, using the independent worker observer.
        js(f"chrome.tabGroups.update({managed['id']},{{title:'Kept by user'}})")
        call("browser.release")
        poll(lambda: not marker("/existing") and not marker("/next") and not marker("/missing"))
        check("release restores site's newer icon", oracles["/existing"]["hrefs"] == ["/updated.svg"])
        poll(lambda: oracles["/missing"]["hrefs"] == [])
        check("release removes created fallback link", True)
        poll(lambda: "M7%204%20L25" not in tab(missing).get("favIconUrl", ""))
        check("Chrome clears cached fallback pointer", True)
        check("release preserves renamed group", tab(new)["groupId"] == managed["id"])
        check("release preserves original user group", tab(existing)["groupId"] == group)
        # Prove cleanup of an unchanged owned group separately.
        clean = call("browser.navigate", url=url + "/clean", newTab=True, active=False)["tab"]["tabId"]
        poll(lambda: marker("/clean"))
        call("browser.release")
        poll(lambda: not marker("/clean"))
        check("release ungroups unchanged owned tab", tab(clean)["groupId"] == -1)
        adopted = call("browser.navigate", url=url + "/adopt", newTab=True, active=False)["tab"]["tabId"]
        poll(lambda: marker("/adopt"))
        js(f"chrome.tabs.update({adopted},{{active:true}})")
        time.sleep(.5)
        button = next(e for e in call("browser.snapshot", tabId=adopted)["elements"]
                      if e["name"] == "Change site icon")
        call("browser.click", reference=button["reference"])
        time.sleep(.5)
        call("browser.release")
        poll(lambda: not marker("/adopt"))
        check("site adoption of fallback icon is preserved", oracles["/adopt"]["hrefs"] == ["/updated.svg"])
        # A cancelled debugger cannot perform DOM cleanup. The independent
        # content expiry must restore it without another agent operation.
        call("browser.snapshot", tabId=existing)
        poll(lambda: marker("/existing"))
        js(f"chrome.debugger.detach({{tabId:{existing}}})")
        poll(lambda: not marker("/existing"), 18)
        check("cancelled debugger marker expires independently", True)
        # Reload terminates the worker/native host. The new worker recovers
        # its recorded groups/DOM before connecting to the real resident.
        restart = call("browser.navigate", url=url + "/restart", newTab=True, active=False)["tab"]["tabId"]
        poll(lambda: marker("/restart"))
        observer.call("Runtime.evaluate", expression="setTimeout(()=>chrome.runtime.reload(),100)")
        observer.close()
        observer = None
        # MV3 reload can leave the worker dormant until its reconnect alarm.
        poll(lambda: not marker("/restart"), 20)
        observer = poll(connect_worker, 85)
        poll(lambda: call("capabilities").get("browser", {}).get("connected"))
        check("worker restart restores owned grouping", tab(restart)["groupId"] == -1)
        check("native host reconnects after worker restart", True)
        call("browser.snapshot", tabId=existing)
        poll(lambda: marker("/existing"))
        check("control resumes with current resident authority", True)
        call("browser.release")
        poll(lambda: not marker("/existing"))
    except BaseException as error:
        import traceback
        failure = repr(error)
        diagnostic = traceback.format_exc()
        if (root / "chrome.log").exists():
            diagnostic += "\n" + (root / "chrome.log").read_text()
        try:
            diagnostic += "\nResident tabs: " + json.dumps(call("browser.tabs"))
            if observer:
                diagnostic += "\nChrome tabs: " + json.dumps(js("chrome.tabs.query({})"))
            image = call("capture", target=str(browser.pid), scope="window")
            artifact = Path(image["artifactPath"])
            shutil.copyfile(artifact, args.output.with_name(args.output.stem + "-failure.png"))
            artifact.unlink()
        except BaseException as probe_error:
            diagnostic += "\nProbe failure: " + repr(probe_error)
        args.output.with_suffix(".log").write_text(diagnostic)
    finally:
        if observer:
            observer.close()
        if browser:
            # Terminate and reap the separately identified browser/process group.
            import signal
            try:
                os.killpg(browser.pid, signal.SIGTERM)
                browser.wait(10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(browser.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                browser.wait(10)
        if server:
            server.shutdown()
            server.server_close()
        args.output.write_text(json.dumps({"passed": failure is None, "checks": checks, "failure": failure}, indent=2) + "\n")
        print(json.dumps({"passed": failure is None, "checks": len(checks), "failure": failure}))
if failure:
    raise SystemExit(1)
