#!/usr/bin/env python3
"""Guest-only real-browser keyboard effects, using an isolated test profile."""
import http.server
import json
import os
from pathlib import Path
import plistlib
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request


def main():
    model = subprocess.check_output(["/usr/sbin/sysctl", "-n", "hw.model"]).decode().strip()
    assert model.startswith("VirtualMac"), "Tart guest required"
    root = Path(sys.argv[1])
    root.mkdir(exist_ok=False)
    candidates = [
        Path.home() / "mc-cft/chrome-mac-arm64/Google Chrome for Testing.app",
        Path("/Applications/Google Chrome for Testing.app"),
    ]
    apps = [path for path in candidates if path.exists()]
    assert apps, "Install the separately identified Chrome for Testing fixture first"
    app = apps[0]
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    assert info["CFBundleIdentifier"] == "com.google.chrome.for.testing", "Separate test browser identity required"
    binary = app / "Contents/MacOS" / info["CFBundleExecutable"]
    received = []
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path.startswith("/effect?"):
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                received.append(query.get("value", [""])[0])
                data = b"ok"
            else:
                data = (b"<title>Keyboard smoke</title><input id=f autofocus>"
                        b"<script>f.oninput=()=>fetch('/effect?value='+encodeURIComponent(f.value));</script>")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    resident = Path.home() / "Applications/Machine Control.app/Contents/MacOS/macui"
    socket = Path.home() / "Library/Application Support/MachineControl/control.sock"

    def wait(predicate, label):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        raise AssertionError(label)

    process = None
    last_result = None
    pages = None
    try:
        process = subprocess.Popen([
            str(binary), "--user-data-dir=" + str(root / "profile"),
            "--remote-debugging-port=0", "--no-first-run", "--no-default-browser-check", "--no-proxy-server",
            "--use-mock-keychain", "--password-store=basic", "--force-renderer-accessibility", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

        def control(operation, **fields):
            nonlocal last_result
            request = dict(operation=operation, target=str(process.pid), provider="macos-native", **fields)
            result = json.loads(subprocess.check_output([
                str(resident), "request", str(socket), json.dumps(request),
            ], timeout=20))
            last_result = result
            assert result.get("accepted"), result.get("errorCode")
            if operation == "input.key":
                assert result["data"]["activeLayoutId"] == "com.apple.keylayout.Dvorak", "Browser changed the active input source"
            return result

        def key(value):
            return control("input.key", key=value)

        def text(value):
            return control("input.text", text=value)

        wait(lambda: (root / "profile/DevToolsActivePort").exists(), "browser debug readiness")
        port = (root / "profile/DevToolsActivePort").read_text().splitlines()[0]

        def pages():
            with urllib.request.urlopen("http://127.0.0.1:" + port + "/json/list", timeout=2) as response:
                return [page for page in json.load(response) if page["type"] == "page"]

        url = "http://127.0.0.1:" + str(server.server_address[1]) + "/"
        with urllib.request.urlopen(url, timeout=2) as response:
            assert b"Keyboard smoke" in response.read(), "Fixture HTTP server unavailable"
        key("cmd+l")
        text(url)
        key("return")
        wait(lambda: any(page["url"] == url and page["title"] == "Keyboard smoke" for page in pages()), "Command-L navigation")
        sample = "Browser Dvorak é日本語"
        text(sample)
        wait(lambda: sample in received, "browser literal text effect")
        key("cmd+a")
        key("cmd+c")
        key("right")
        key("cmd+v")
        wait(lambda: sample + sample in received, "browser copy and paste effect")
        key("cmd+t")
        wait(lambda: len(pages()) == 2, "Command-T new tab")
        key("cmd+w")
        wait(lambda: len(pages()) == 1, "Command-W close tab")
        print(json.dumps({"passed": True, "application": "Chrome for Testing", "navigation": True,
                          "typing": True, "clipboard": True, "newTab": True, "closeTab": True}))
    except Exception:
        diagnostic = {"lastInput": last_result, "requests": requests}
        if pages is not None:
            try:
                diagnostic["pages"] = [{"url": page["url"], "title": page["title"]} for page in pages()]
            except Exception:
                pass
        print(json.dumps(diagnostic), file=sys.stderr)
        raise
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        server.shutdown()
        server.server_close()
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
