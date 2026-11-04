"""Qualify staged Settings startup against the matching protected companion.

Run as the ordinary interactive user on a claimed Windows appliance. The
controller owns helper staging, cold boot, credentials, restoration and power.
This actor grants no access and reads no credential. It owns only its app,
unique instance, WebView data and resulting private evidence.
"""
import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("This actor requires Windows")
    args.output.mkdir(parents=True, exist_ok=True)
    instance = "companion-" + uuid.uuid4().hex
    webview = args.output / "webview"
    state = Path(os.environ["LOCALAPPDATA"]) / "MachineControl/workstation" / instance
    assert not webview.exists() and not state.exists()
    bundled = args.install / "runtime/machine-control-windows.exe"
    installed = Path(os.environ["ProgramFiles"]) / "MachineControlDesktopUac/machine-control-windows.exe"
    product = json.loads((bundled.parent / "build.json").read_text())
    assert not product["sourceDirty"]
    report = {"passed": False, "checks": [], "productSourceRevision": product["sourceRevision"],
              "actorSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    app = None
    child_handle = None
    log = (args.output / "actor.log").open("w", encoding="utf-8")
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
        ctypes.POINTER(ctypes.c_wchar), ctypes.POINTER(ctypes.c_uint)]
    assert kernel.SetPriorityClass(ctypes.c_void_p(-1), 32)
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]

    def check(value, label):
        assert value, label
        report["checks"].append(label)
        print(label, flush=True)

    def powershell(script):
        result = subprocess.run(["pwsh.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand",
            base64.b64encode(script.encode("utf-16-le")).decode()], capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise RuntimeError("Owned process observation or cleanup failed")
        return result.stdout

    def direct(operation):
        value = subprocess.run([str(bundled), "call", "--profile", "user", "--instance", instance,
            "--session-id", str(session.value)], input=json.dumps({"operation": operation}),
            capture_output=True, text=True, timeout=8)
        return json.loads(value.stdout) if value.stdout.strip() else {}

    try:
        session = ctypes.c_uint()
        assert kernel.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
        pointer, size = ctypes.c_void_p(), ctypes.c_uint()
        assert ctypes.windll.wtsapi32.WTSQuerySessionInformationW(
            None, session.value, 25, ctypes.byref(pointer), ctypes.byref(size))
        try:
            check(size.value >= 20 and ctypes.c_int.from_address(pointer.value + 16).value == 1,
                  "Initially unlocked console independently observed")
        finally:
            ctypes.windll.wtsapi32.WTSFreeMemory(pointer)
        check(installed.is_file(), "Protected companion is installed before startup")
        # Do not prehash the images: that would warm the full file cache before
        # the app's own verification after the controller's cold boot.
        started = time.monotonic()
        app = subprocess.Popen([str(args.install / "machine-control.exe"), "--settings", "--presentation", "minimal",
            "--instance", instance], stdout=log, stderr=log, env={**os.environ,
                "WEBVIEW2_USER_DATA_FOLDER": str(webview),
                "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--force-renderer-accessibility"})
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            assert app.poll() is None, "Staged Settings exited during startup"
            try:
                status = direct("status")
                caps = direct("capabilities") if status.get("accepted") else {}
            except (subprocess.TimeoutExpired, ValueError):
                status, caps = {}, {}
            if caps.get("accepted") and caps["data"]["browser"]["available"]:
                break
            time.sleep(.2)
        else:
            raise TimeoutError("Matching companion Settings startup did not become ready")
        report["startupSeconds"] = round(time.monotonic() - started, 3)
        check(status["data"]["desktopProduct"] and status["data"]["integrityRid"] == 8192,
              "Settings owns an ordinary Medium desktop resident")
        native_pid = status["data"]["processId"]
        child_handle = kernel.OpenProcess(0x00101000, False, native_pid)
        assert child_handle
        image, capacity = ctypes.create_unicode_buffer(32768), ctypes.c_uint(32768)
        assert kernel.QueryFullProcessImageNameW(child_handle, 0, image, ctypes.byref(capacity))
        rows = json.loads(powershell("$ProgressPreference='SilentlyContinue';@(" +
            "Get-CimInstance Win32_Process -Filter 'ProcessId=" + str(native_pid) +
            "'|Select-Object ParentProcessId)|ConvertTo-Json -AsArray -Compress"))
        check(len(rows) == 1 and rows[0]["ParentProcessId"] == app.pid
              and Path(image.value).resolve() == installed.resolve(),
              "The app actually selected its matching protected companion")
        def digest(path):
            value = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(128 * 1024): value.update(chunk)
            return value.hexdigest()
        report["runtimeSha256"] = digest(bundled)
        check(digest(installed) == report["runtimeSha256"],
              "Installed and bundled companion images match completely")
        check(caps["data"]["controlSession"]["schema"] == "machine-control-admission/v2",
              "The installed companion runs the shared v2 policy")
        grant = direct("grant.status")
        check(grant["accepted"] and not grant["data"]["effectiveScopes"],
              "Matching-helper startup creates no ordinary authority")
        report["passed"] = True
    except BaseException as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        cleanup = True
        if app and app.poll() is None:
            subprocess.run(["taskkill.exe", "/PID", str(app.pid), "/T", "/F"], stdout=log, stderr=log)
            try:
                app.wait(timeout=15)
            except subprocess.TimeoutExpired:
                cleanup = False
        if child_handle:
            cleanup = kernel.WaitForSingleObject(child_handle, 5000) == 0 and cleanup
            kernel.CloseHandle(child_handle)
        try:
            literal = "'" + str(webview).replace("'", "''") + "'"
            powershell("$ProgressPreference='SilentlyContinue';$path=" + literal + ";" +
                "Get-CimInstance Win32_Process|Where-Object {$_.Name -eq 'msedgewebview2.exe' -and " +
                "$_.CommandLine -and $_.CommandLine.Contains($path)}|ForEach-Object {& taskkill.exe /PID $_.ProcessId /T /F *> $null}")
            for path in (webview, state):
                for attempt in range(25):
                    try:
                        if path.exists(): shutil.rmtree(path)
                        break
                    except OSError:
                        if attempt == 24: raise
                        time.sleep(.2)
        except BaseException:
            cleanup = False
        report["cleanup"] = cleanup and (app is None or app.poll() is not None)
        (args.output / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        log.close()
    assert report["cleanup"], "Owned startup fixture cleanup did not complete"


if __name__ == "__main__":
    main()
