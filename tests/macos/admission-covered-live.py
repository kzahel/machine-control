#!/usr/bin/env python3
"""Opt-in two-task Mac covered-admission trial using existing operator consent.

The caller prepares an awake, open-lid console, native grants and one isolated
fixture. This runner never installs, arms access, handles passwords or unlocks
for recovery. A separately invoked native lock helper is required only when
starting unlocked. All observations and effects use the selected live channel;
a separate native probe verifies relock before the next task begins.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
import machine_control as mc
from control_session import ControlSession


def run(args):
    _, target = mc.select_target(mc.load_registry(args.registry)[0], args.target)
    target = {**target, "_claimId": args.claim, "environment": {
        **target.get("environment", {}), "MACHINE_CONTROL_CLAIM_ID": args.claim}}
    mc.require_selected_claim(target)

    def discovery(operation):
        result, _, _ = mc.run_adapter(target, ["control", json.dumps({"operation": operation})])
        value = json.loads(result.stdout)
        if not value.get("accepted"):
            raise AssertionError(value.get("errorCode", "Discovery refused"))
        return value["data"]

    def independent_lock():
        result = subprocess.run([args.session_probe], capture_output=True, check=True, timeout=5)
        return json.loads(result.stdout)["desktopState"] == "locked"

    def oracle():
        return json.loads(Path(args.fixture_state).read_text())

    def await_state(predicate, seconds=45):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if predicate():
                return
            time.sleep(.1)
        raise AssertionError("Expected bounded state not observed")

    def require_effect(result):
        if not result.get("accepted"):
            raise AssertionError(result.get("errorCode", "Native effect refused"))
        return result.get("data")

    initial = discovery("status")
    readiness = initial["lockedUse"]
    if not readiness["enabled"] or not readiness["helperHealthy"] or readiness["pausedUntilManualUnlock"]:
        raise AssertionError("Existing covered-use readiness is required")
    grant = discovery("grant.status")["grant"]
    if not grant or grant["lifetime"] != "until_stopped" or not {"observe", "control"}.issubset(grant["scopes"]):
        raise AssertionError("Existing Until I turn it off observation/control consent is required")
    fixture_pid = oracle()["pid"]
    if initial["desktopState"] == "unlocked":
        if not args.session_lock:
            raise AssertionError("Starting unlocked requires an explicit native lock helper")
        def quiet():
            reasons = discovery("grant.status")["availability"]["blockingReasons"]
            if any(reason not in {"physical_activity", "activity_unknown"} for reason in reasons):
                raise AssertionError("Operator pause or safety block prevents this lock trial")
            return not reasons
        print("Waiting for physical quiet before the bounded lock trial", flush=True)
        await_state(quiet, seconds=120)
        value = json.loads(subprocess.run([args.session_lock, "--lock"], capture_output=True,
                                         check=True, timeout=10).stdout)
        if value.get("lockedObserved") is not True:
            raise AssertionError("Native helper did not independently observe lock")
    elif initial["desktopState"] != "locked":
        raise AssertionError("Existing console must be unlocked or locked")
    if not independent_lock():
        raise AssertionError("Independent native probe did not observe initial lock")
    print("Native OS lock observed; starting two fresh covered tasks", flush=True)
    sessions = []
    for number in (1, 2):
        before = oracle()["count"]
        try:
            with ControlSession(target, reason="Validate unattended covered fixture task",
                                wait=120, duration=90) as owner:
                active = owner.wait()
                sessions.append(active["sessionId"])
                await_state(lambda: discovery("status")["lockedUse"]["phase"] == "active")
                covered = discovery("status")["lockedUse"]
                if covered["coveredDisplays"] < 1:
                    raise AssertionError("No protective display cover observed")
                started = time.monotonic()
                snapshot = require_effect(owner.call({"operation": "snapshot", "provider": "macos-native",
                    "target": args.fixture, "maxDepth": 6, "maxElements": 500}))
                view = owner.status()
                print(f"Task {number}: snapshot latency={time.monotonic() - started:.2f}s; "
                      f"owner state={view['state']}; reason={view.get('terminalReason')}; "
                      f"blockers={view.get('blockingReasons')}", flush=True)
                button = next(item for item in snapshot["elements"]
                    if item.get("label") == "Increment" or item.get("identifier") == "fixture.increment")
                require_effect(owner.call({"operation": "action", "provider": "macos-native",
                    "action": "press", "reference": button["reference"]}))
                await_state(lambda: oracle()["count"] == before + 1, seconds=5)
                if oracle()["pid"] != fixture_pid:
                    raise AssertionError("Independent fixture identity changed")
                print(f"Task {number}: protected cover observed; independent AX delta=1", flush=True)
                if args.end_mode == "disconnect":
                    # Kill only this runner's byte adapter. The resident and
                    # independent guardian remain alive to perform cleanup.
                    owner.process.terminate()
                    owner.process.wait(timeout=5)
                    owner.close(cancel=False)
        finally:
            await_state(independent_lock)
            await_state(lambda: discovery("status")["lockedUse"]["controlSessionId"] is None)
        final = discovery("status")["lockedUse"]
        if final["coveredDisplays"] != 0 or final["pausedUntilManualUnlock"]:
            raise AssertionError("Covered task did not cleanly release after relock")
        retained = discovery("grant.status")["grant"]
        if not retained or retained["grantId"] != grant["grantId"] or retained["lifetime"] != "until_stopped":
            raise AssertionError("Normal completion changed operator consent")
        print(f"Task {number}: independent OS relock; Until I turn it off retained", flush=True)
    if len(set(sessions)) != 2:
        raise AssertionError("Successive tasks reused an active session")
    print("PASS: two fresh queue activations, effects, independent relocks and retained consent", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", help="Private common target registry")
    parser.add_argument("--target", default="host")
    parser.add_argument("--claim", required=True)
    parser.add_argument("--fixture", default="org.machine-control.fixture")
    parser.add_argument("--fixture-state", required=True)
    parser.add_argument("--session-probe", required=True)
    parser.add_argument("--session-lock", help="Explicit native lock helper for an unlocked start")
    parser.add_argument("--end-mode", choices=("cancel", "disconnect"), default="cancel")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
