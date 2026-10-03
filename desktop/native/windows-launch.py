"""Bounded, explicit desktop launch; ordinary CLI commands never use this path."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def process_image(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise OSError("Cannot identify the answering resident")
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise OSError("Cannot resolve the answering resident executable")
        return Path(buffer.value).resolve()
    finally:
        kernel.CloseHandle(handle)


def probe(resident, session, operation="status"):
    result = subprocess.run(
        [str(resident), "call", "--profile", "user", "--instance", "desktop",
         "--session-id", str(session), "--timeout-ms", "500"],
        input=json.dumps({"operation": operation}), capture_output=True,
        encoding="utf-8", timeout=2, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        return None
    value = json.loads(result.stdout)
    if value.get("schema") != "machine-control/v0" or value.get("accepted") is not True:
        raise RuntimeError("The desktop endpoint refused discovery")
    return value


def main():
    root = Path(__file__).resolve().parent.parent
    executable = root / "machine-control.exe"
    resident = root / "runtime/machine-control-windows.exe"
    session = wintypes.DWORD()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)) or not session.value:
        raise RuntimeError("Start Machine Control in an interactive Windows user session")
    if not executable.is_file() or not resident.is_file():
        raise RuntimeError("Desktop installation is incomplete; repair this installation")
    deadline = time.monotonic() + 15
    status = probe(resident, session.value)
    if status is None:
        # Breakaway must succeed: silently retaining a kill-on-close caller job
        # would claim successful startup while tying the app to the agent task.
        subprocess.Popen([str(executable), "--background"],
                         cwd=root,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True,
                         creationflags=(subprocess.DETACHED_PROCESS |
                                        subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000))
        while time.monotonic() < deadline:
            status = probe(resident, session.value)
            if status is not None:
                break
            time.sleep(0.1)
    if status is None:
        raise RuntimeError("App launch requested, but desktop readiness was not confirmed within 15 seconds")
    data = status.get("data", {})
    if data.get("desktopProduct") is not True or process_image(data.get("processId", 0)) != resident.resolve():
        raise RuntimeError("Another or unidentified installation owns the desktop endpoint; no app was replaced")
    access = "unknown"
    try:
        grant = probe(resident, session.value, "grant.status")
        if grant:
            access = "on" if grant.get("data", {}).get("grant") else "off"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        pass
    print(f"Machine Control is running. Desktop access is {access}.")
    if not data.get("ready"):
        print("The interactive desktop is not ready for control.")
    print("\nAgent instructions: machine-control agent instructions"
          "\nAvailable commands: machine-control --help"
          "\nInstallation details: machine-control agent identity --paths")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Machine Control startup failed: {error}", file=sys.stderr)
        print("Read offline guidance with: machine-control agent instructions", file=sys.stderr)
        raise SystemExit(1)
