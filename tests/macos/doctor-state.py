#!/usr/bin/env python3
"""Exercise the actual read-only doctor projection with isolated OS fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="mc-doctor-state-") as directory:
    work = Path(directory)
    shutil.copy(ROOT / "platforms/macos/scripts/doctor-json.sh", work / "doctor-json.sh")
    (work / "common.sh").write_text('''
MACVM_REPO_DIR=/unused
MACVM_FORBID_OUTER_UI=true
macvm_state() { printf '%s' "$FIXTURE_POWER"; }
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
    current = dict(schema="machine-control/v0", accepted=True, generation="resident",
        data=dict(desktopState="locked", desktopGeneration="desktop", observationSource="iokit.console-session",
                  inputState="unavailable", semanticState="unavailable", captureState="ready", unlock=unlock))
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
        print(name + ": passed")
