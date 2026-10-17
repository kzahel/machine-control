"""Source-native enrolled Windows desktop acceptance on a claimed appliance.

Requires completed native enrollment, an initially unlocked console and no
other desktop instance. This fixture never receives or reads a password. The
controller owns enrollment, independent account/logon observations, restoration,
normal shutdown and claim release. Leaves Windows locked after its final task.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "client"))
from control_session import ControlSession


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failure-hold", type=int, choices=range(0, 121), default=0)
    args = parser.parse_args()
    exe = Path(os.environ["ProgramFiles"]) / "MachineControlDesktopUac/machine-control-windows.exe"
    args.output.mkdir(parents=True, exist_ok=True)
    session = ctypes.c_uint()
    assert ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
    child = owner = None
    checks = []
    report = {"passed": False, "checks": checks, "runtimeSha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
              "operatorRoute": "inherited_native_operator"}
    log = (args.output / "actor.log").open("w", encoding="utf-8")

    def check(label, value):
        assert value, label
        checks.append(label)
        report["phase"] = label
        print(label, flush=True)

    def wait(predicate, seconds=45):
        deadline = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() >= deadline:
                raise TimeoutError("Independent state did not reach expected effect")
            time.sleep(.2)

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

    def console_identity():
        # Independent WTS account/session readback plus this surviving native
        # task's token logon LUID. No account value is written to the report.
        fields = []
        for kind in (5, 7):
            pointer = ctypes.c_void_p()
            size = ctypes.c_uint()
            assert ctypes.windll.wtsapi32.WTSQuerySessionInformationW(
                None, session.value, kind, ctypes.byref(pointer), ctypes.byref(size))
            try:
                fields.append(ctypes.wstring_at(pointer.value))
            finally:
                ctypes.windll.wtsapi32.WTSFreeMemory(pointer)
        token = ctypes.c_void_p()
        assert ctypes.windll.advapi32.OpenProcessToken(ctypes.c_void_p(-1), 8, ctypes.byref(token))
        try:
            statistics = ctypes.create_string_buffer(64)
            size = ctypes.c_uint()
            assert ctypes.windll.advapi32.GetTokenInformation(token, 10, statistics, len(statistics), ctypes.byref(size))
            logon = statistics.raw[8:16]
        finally:
            ctypes.windll.kernel32.CloseHandle(token)
        return (ctypes.windll.kernel32.WTSGetActiveConsoleSessionId(), *fields, logon)

    def operator(method, **fields):
        child.stdin.write(json.dumps(dict(method=method, **fields)) + "\n")
        child.stdin.flush()
        reply = json.loads(child.stdout.readline())
        assert reply.get("ok"), (method, reply)
        return reply

    def direct(operation, **fields):
        reply = subprocess.run([str(exe), "call", "--profile", "user", "--instance", "desktop",
            "--session-id", str(session.value)], input=json.dumps(dict(operation=operation, **fields)),
            capture_output=True, text=True, timeout=90)
        assert reply.returncode == 0 and reply.stdout.strip(), (operation, reply.returncode)
        return json.loads(reply.stdout)

    def new_owner():
        value = ControlSession({"command": [str(exe), "channel", "--profile", "user", "--instance", "desktop",
            "--session-id", str(session.value)]}, scopes=["observe", "control"], reason="Native enrollment fixture",
            prepared_console=True, wait=90, duration=120)
        try:
            value.wait()
            return value
        except BaseException:
            report["admissionFailure"] = value.view
            value.close()
            raise

    try:
        check("initial console unlocked", not locked())
        original_identity = console_identity()
        child = subprocess.Popen([str(exe), "desktop"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
        operator("hello", processId=os.getpid())
        state = operator("state")["state"]["lockedUse"]
        check("native enrollment ready", state["permissionReady"] and state["credentialSource"] == "service_enrolled_password")
        vault = Path(os.environ["ProgramData"]) / "MachineControlUnlock/desktop/credential.dpapi"
        try:
            with vault.open("rb"):
                pass
        except PermissionError:
            check("ordinary resident identity cannot read credential ciphertext", True)
        else:
            raise AssertionError("Credential store readable by ordinary caller")
        operator("locked_use", enabled=True)
        check("enrollment setup grants no ordinary access", direct("grant.status")["data"].get("grant") is None)
        check("unowned enrolled unlock refused", not direct("session.unlock")["accepted"])
        check("ordinary JSON credential route refused", not direct("session.unlock", credentialKind="password")["accepted"])
        operator("arm", scopes=["observe", "control"], duration=600)
        # Ordinary tasks keep their unlocked origin; the prepared option does
        # not let them acquire later relock or automatic credential authority.
        owner = new_owner()
        try:
            refusal = owner.call({"operation": "session.unlock"})
            check("unlocked-origin automatic unlock refused", not refusal["accepted"])
        except Exception as error:
            check("unlocked-origin automatic unlock refused", getattr(error, "code", None) == "task_did_not_start_locked")
        owner.close(); owner = None
        check("ordinary completion leaves console unlocked", not locked())
        for finish in ("owner", "stop"):
            assert ctypes.windll.user32.LockWorkStation()
            wait(locked)
            report["phase"] = finish + ": opening locked owner"
            owner = new_owner()
            check(finish + ": ordinary dispatch refused while locked", not owner.call({"operation": "windows"})["accepted"])
            result = owner.call({"operation": "session.unlock"})
            report[finish + "Unlock"] = result
            check(finish + ": enrolled unlock independently confirmed", result["accepted"] and result["effect"] == "confirmed" and not locked())
            check(finish + ": same console account, session and task logon", console_identity() == original_identity)
            observed = owner.call({"operation": "windows"})
            check(finish + ": ordinary window observation after unlock", observed["accepted"])
            if finish == "stop":
                operator("stop")
            owner.close(); owner = None
            wait(locked)
            wait(lambda: operator("state")["state"]["lockedUse"]["phase"] == "idle")
            check(finish + ": owner end relocks before cleanup", locked())
        check("fresh tasks reused enrollment without credential input", direct("capabilities")["data"]["lockedUse"]["permissionReady"])
        report["passed"] = True
    except BaseException as error:
        report["failure"] = str(error)
        report["failureCode"] = getattr(error, "code", type(error).__name__)
        (args.output / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if args.failure_hold:
            time.sleep(args.failure_hold)
        raise
    finally:
        if owner:
            owner.close()
        if child and child.poll() is None:
            child.stdin.close()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=5)
        (args.output / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        log.close()


if __name__ == "__main__":
    main()
