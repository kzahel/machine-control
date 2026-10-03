"""Native installer/PATH lifecycle in a dedicated, exclusively claimed VM.

An optional metadata-preservation mode leaves an existing inactive installation
in place. Restores registry state in finally; never prints private PATH values.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import winreg

PREFERENCE = r"Software\MachineControl\Installer"
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Machine Control"
PRODUCT = r"Software\machine-control\Machine Control"
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def real_console(command):
    """Create an owned console without propagating this runner's log handles."""
    class Startup(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("reserved", wintypes.LPWSTR),
                    ("desktop", wintypes.LPWSTR), ("title", wintypes.LPWSTR),
                    ("geometry", wintypes.DWORD * 7), ("flags", wintypes.DWORD),
                    ("show", wintypes.WORD), ("reservedSize", wintypes.WORD),
                    ("reservedBytes", ctypes.c_void_p), ("input", wintypes.HANDLE),
                    ("output", wintypes.HANDLE), ("error", wintypes.HANDLE)]
    class Process(ctypes.Structure):
        _fields_ = [("process", wintypes.HANDLE), ("thread", wintypes.HANDLE),
                    ("pid", wintypes.DWORD), ("tid", wintypes.DWORD)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
        ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(Startup), ctypes.POINTER(Process)]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    startup, process = Startup(), Process()
    startup.size = ctypes.sizeof(startup)
    # CREATE_NEW_CONSOLE, no STARTF_USESTDHANDLES and no handle inheritance.
    if not kernel.CreateProcessW(str(command[0]), ctypes.create_unicode_buffer(subprocess.list2cmdline(command)),
                                 None, None, False, 0x10, None, None,
                                 ctypes.byref(startup), ctypes.byref(process)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if kernel.WaitForSingleObject(process.process, 40000) != 0:
            kernel.TerminateProcess(process.process, 1)
            kernel.WaitForSingleObject(process.process, 5000)
            raise RuntimeError("Real-console test timed out")
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(process.process, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return code.value
    finally:
        kernel.CloseHandle(process.thread)
        kernel.CloseHandle(process.process)


def tree(key):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            children, count, _ = winreg.QueryInfoKey(handle)
            return ([winreg.EnumValue(handle, i) for i in range(count)],
                    {winreg.EnumKey(handle, i): tree(key + "\\" + winreg.EnumKey(handle, i))
                     for i in range(children)})
    except FileNotFoundError:
        return None


def replace_tree(key, saved):
    current = tree(key)
    if current is not None:
        for child in current[1]:
            replace_tree(key + "\\" + child, None)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
    if saved is not None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as handle:
            for name, value, kind in saved[0]:
                winreg.SetValueEx(handle, name, 0, kind, value)
        for child, values in saved[1].items():
            replace_tree(key + "\\" + child, values)


def read(key, name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            return winreg.QueryValueEx(handle, name)
    except FileNotFoundError:
        return None


def restore(key, name, value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as handle:
        if value is None:
            try:
                winreg.DeleteValue(handle, name)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(handle, name, 0, value[1], value[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--fixture", type=Path,
                        help="Also run interactive startup/control acceptance")
    parser.add_argument("--preserve-registration", action="store_true",
                        help="Temporarily hide and restore an inactive installation's registry metadata")
    args = parser.parse_args()
    if read(UNINSTALL, "UninstallString") and not args.preserve_registration:
        raise RuntimeError("Existing desktop installation registered; use an isolated test appliance")
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    active = subprocess.run([str(powershell), "-NoProfile", "-Command",
                             "if(Get-Process machine-control -ErrorAction SilentlyContinue){exit 1}"], timeout=20)
    if active.returncode:
        raise RuntimeError("A desktop operator is already running; refusing installer lifecycle tests")
    metadata = {key: tree(key) for key in (UNINSTALL, PRODUCT)}
    startup = read(RUN, "Machine Control")
    original_path = read("Environment", "Path")
    original_preference = read(PREFERENCE, "AddToPath")
    # Keep a controller-local recovery record as well as finally cleanup. These
    # installer keys contain strings/DWORDs, not authorization material.
    args.evidence.with_suffix(".registry-backup.json").write_text(json.dumps({
        "metadata": metadata, "startup": startup, "path": original_path,
        "preference": original_preference}, indent=2), encoding="utf-8")
    evidence = {"passed": False, "unsignedDeveloperBuild": True, "checks": []}
    with tempfile.TemporaryDirectory(prefix="mc installer ") as temporary:
        install = Path(temporary) / "Machine Control Ω"

        def registered():
            value = read("Environment", "Path")
            return [] if value is None else value[0].split(";")

        def setup(option=None):
            command = [str(args.installer), "/S", "/NS"]
            if option is not None:
                command.append("/ADDTOPATH=" + str(option))
            # NSIS requires an unquoted /D= suffix, last on the command line.
            # No shell interprets it; quotes are illegal in Windows paths.
            line = subprocess.list2cmdline(command) + " /D=" + str(install)
            subprocess.run(line, executable=str(args.installer), check=True, timeout=180)
            assert (install / "machine-control.exe").is_file()

        def uninstall():
            executable = install / "uninstall.exe"
            if executable.is_file():
                # _?= avoids NSIS's detached temporary copy: wait for the real
                # uninstaller, including its registry deletion, before restore.
                line = subprocess.list2cmdline([str(executable), "/S"]) + " _?=" + str(install)
                subprocess.run(line, executable=str(executable), check=True, timeout=90)
                assert not (install / "machine-control.exe").exists(), "Uninstaller did not finish"
                executable.unlink(missing_ok=True)

        try:
            if args.preserve_registration:
                replace_tree(UNINSTALL, None)
            stale = os.environ.copy()
            setup(1)
            assert registered().count(str(install)) == 1
            assert os.environ == stale, "Installer unexpectedly changed the caller environment"
            fresh = dict(stale)
            system = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                    r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
            with system:
                machine_path = winreg.QueryValueEx(system, "Path")[0]
            fresh["PATH"] = os.path.expandvars(machine_path + ";" + read("Environment", "Path")[0])
            result = subprocess.run([os.environ["COMSPEC"], "/d", "/c", "chcp 65001 >nul & where machine-control"],
                                    env=fresh, capture_output=True, encoding="utf-8", check=True, timeout=20)
            assert str(install / "machine-control.exe").casefold() in result.stdout.casefold()
            evidence["checks"].append("fresh PATH resolves command; existing environment stays stale")
            setup()
            assert registered().count(str(install)) == 1
            setup(0)
            assert str(install) not in registered()
            setup()
            assert str(install) not in registered()
            evidence["checks"].append("repair is idempotent and retains opt-out")
            setup(1)
            run = subprocess.run([sys.executable, str(args.source / "tests/windows/discovery.py"),
                                  "--install", str(install)], capture_output=True,
                                 encoding="utf-8", check=True, timeout=120)
            evidence["discovery"] = json.loads(run.stdout)
            if args.fixture:
                console = Path(temporary) / "console.json"
                console_run = real_console([str(powershell),
                    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(args.source / "tests/windows/discovery-console.ps1"),
                    "-Install", str(install), "-EvidencePath", str(console)])
                if console.exists():
                    evidence["console"] = json.loads(console.read_text(encoding="utf-8-sig"))
                assert console_run == 0 and evidence.get("console", {}).get("passed"), "Real-console discovery failed"
                session = Path(temporary) / "session.json"
                powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
                session_run = subprocess.run([str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                str(args.source / "tests/windows/discovery-session.ps1"),
                                "-Install", str(install), "-Source", str(args.source),
                                "-Fixture", str(args.fixture), "-EvidencePath", str(session)],
                               timeout=180)
                if session.exists():
                    evidence["session"] = json.loads(session.read_text(encoding="utf-8-sig"))
                assert session_run.returncode == 0 and evidence.get("session", {}).get("passed"), "Interactive discovery failed"
            uninstall()
            assert read("Environment", "Path") == original_path
            evidence["checks"].append("uninstall restores the original PATH exactly")
            evidence["passed"] = True
        except Exception as error:
            evidence["error"] = str(error)
            raise
        finally:
            try:
                uninstall()
            finally:
                restore("Environment", "Path", original_path)
                restore(PREFERENCE, "AddToPath", original_preference)
                restore(RUN, "Machine Control", startup)
                for key, saved in metadata.items():
                    replace_tree(key, saved)
                    assert tree(key) == saved, "Installer metadata was not restored"
                evidence["registryRestored"] = True
                args.evidence.write_text(json.dumps(evidence, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
