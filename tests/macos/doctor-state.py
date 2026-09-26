#!/usr/bin/env python3
"""Exercise the actual read-only doctor projection with isolated OS fixtures."""
import json
import os
from pathlib import Path
import shutil
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
import machine_control  # noqa: E402

# Exercise the real suspend policy against a fixture host session.
suspend_blockers = re.search(
    r"^macvm_suspend_blockers\(\) \{\n.*?^\}\n",
    (ROOT / "platforms/macos/scripts/common.sh").read_text(),
    re.MULTILINE | re.DOTALL,
).group(0)
with tempfile.TemporaryDirectory(prefix="mc-doctor-state-") as directory:
    work = Path(directory)
    shutil.copy(ROOT / "platforms/macos/scripts/doctor-json.sh", work / "doctor-json.sh")
    (work / "common.sh").write_text('''
MACVM_REPO_DIR=/unused
MACVM_FORBID_OUTER_UI=true
MACVM_SUSPENDABLE="${FIXTURE_SUSPENDABLE:-true}"
macvm_state() { printf '%s' "$FIXTURE_POWER"; }
macvm_host_session_state() { printf '%s\\n' "${FIXTURE_HOST_SESSION:-unlocked}"; }
''' + suspend_blockers + '''
macvm_remote_ui_binary() { printf /fixture/macui; }
macvm_exec() {
    if [[ "$1" == /usr/bin/true ]]; then return 0; fi
    printf '%s' "$FIXTURE_OBSERVATION"
}
macvm_resident_request() {
    [[ "$FIXTURE_RESIDENT" != absent ]] || return 1
    printf '%s' "$FIXTURE_RESIDENT"
}
''')
    unlock = dict(support="experimental", installation="missing", policy="unknown",
                  callerEligibility="unknown", readiness="unavailable", reasons=["unlock_not_installed"])
    lock_screen = dict(captureState="ready", accessibilityState="unverified",
        nativeKeyboardPermission="granted", ordinaryInputPolicy="blocked_while_locked",
        credentialEntry="not_implemented", observationRequiresUnlockHelper=False)
    current = dict(schema="machine-control/v0", accepted=True, generation="resident",
        data=dict(desktopState="locked", desktopGeneration="desktop", observationSource="iokit.console-session",
                  inputState="unavailable", semanticState="unavailable", captureState="ready", unlock=unlock, lockScreen=lock_screen))
    legacy = dict(schema="machine-control/v0", accepted=True, generation="legacy",
                  data=dict(desktopState="unlocked", semanticState="ready", captureState="ready"))
    cases = [
        ("current_locked", "running", "locked", current, "locked", "ready", "missing"),
        ("stopped_resident", "running", "locked", "absent", "locked", "unavailable", "unknown"),
        ("legacy_unproven", "running", "unknown", legacy, "unknown", "ready", "unknown"),
        ("powered_off", "off", "unlocked", current, "unknown", "unavailable", "unknown"),
    ]
    for name, power, observed, resident, desktop, reachable, installation in cases:
        env = dict(os.environ, FIXTURE_POWER=power,
            FIXTURE_OBSERVATION=json.dumps(dict(desktopState=observed)),
            FIXTURE_RESIDENT=resident if isinstance(resident, str) else json.dumps(resident))
        result = subprocess.run(["bash", str(work / "doctor-json.sh")], env=env,
                                capture_output=True, text=True, check=False)
        value = json.loads(result.stdout)
        assert value["states"]["desktop"] == desktop, (name, value)
        assert value["states"]["resident"] == reachable, (name, value)
        assert value["extensions"]["unlock"]["installation"] == installation, (name, value)
        assert value["ready"] is False, (name, value)
        projection = value["extensions"]["lockScreen"]
        if name == "current_locked":
            assert projection == lock_screen, value
            assert value["states"]["input"] == "unavailable", value
            assert any(check["id"] == "lock_screen" and "granted" in check["summary"]
                       for check in value["checks"]), value
        else:
            assert projection["captureState"] == "unknown", value
            assert projection["nativeKeyboardPermission"] == "unknown", value
        print(name + ": passed")

    suspend_cases = [
        ("suspend_available", "running", "true", "unlocked", [], "pass", None),
        ("suspend_host_locked", "running", "true", "locked",
         ["host_session_locked"], "warn", None),
        ("suspend_disabled", "running", "false", "unlocked",
         ["disabled_by_configuration"], "skip", None),
        ("resume_host_locked", "suspended", "true", "locked",
         ["host_session_locked"], "warn", "fail"),
        ("resume_disabled", "suspended", "false", "unlocked",
         ["disabled_by_configuration"], "skip", "fail"),
        ("resume_unlocked", "suspended", "true", "unlocked", [], "pass", "pass"),
    ]
    for name, power, suspendable, host, reasons, suspend_check, resume_check in suspend_cases:
        env = dict(os.environ, FIXTURE_POWER=power, FIXTURE_SUSPENDABLE=suspendable,
            FIXTURE_HOST_SESSION=host,
            FIXTURE_OBSERVATION=json.dumps(dict(desktopState="unlocked")),
            FIXTURE_RESIDENT=json.dumps(current))
        result = subprocess.run(["bash", str(work / "doctor-json.sh")], env=env,
                                capture_output=True, text=True, check=False)
        value = machine_control.validate_doctor(json.loads(result.stdout))
        lifecycle = value["extensions"]["lifecycle"]
        available = not reasons
        assert lifecycle["suspend"]["reasons"] == reasons, (name, value)
        assert lifecycle["suspend"]["availability"] == (
            "available" if available else "unavailable"), (name, value)
        assert ("suspend" in value["lifecycleOperations"]) == available, (name, value)
        assert lifecycle["defaultDownAction"] == "guest-shutdown", (name, value)
        assert value["extensions"]["hostSession"]["state"] == host, (name, value)
        checks = {check["id"]: check["status"] for check in value["checks"]}
        assert checks["suspend"] == suspend_check, (name, value)
        assert checks.get("resume") == resume_check, (name, value)
        print(name + ": passed")
