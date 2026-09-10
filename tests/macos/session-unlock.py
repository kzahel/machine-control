#!/usr/bin/env python3
"""Live acceptance on an explicitly claimed, disposable, SIP-enabled Mac guest.

Requires the resident, opted-in unlock provider, normal UI consent, active
virtual display, and AppKit fixture. No outer input or credentials are used.
Install/restore lifecycle and normal password fallback are separate cells.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--registry")
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    command = [str(root / "bin/machine-control")]
    if options.registry:
        command += ["--registry", options.registry]
    command += ["--target", options.target, "--claim", options.claim]

    def call(*args):
        result = subprocess.run(command + list(args), capture_output=True,
                                text=True, timeout=45)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"stdout": result.stdout, "returncode": result.returncode}

    def raw(request, local=False):
        return call("desktop", "raw-local" if local else "raw", json.dumps(request))

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        print("PASS:", label, flush=True)

    def status():
        result = call("desktop", "status")
        check(result.get("accepted"), "resident status accepted")
        return result["data"]

    def fixture_ref(local=False):
        result = raw({"operation": "snapshot", "target": "org.machine-control.fixture",
                      "query": "Increment", "projection": "compact",
                      "provider": "macos-native"}, local)
        return next(item["reference"] for item in result["data"]["elements"]
                    if item.get("identifier") == "fixture.increment")

    def counter():
        result = call("testbed", "--", "fixture-state")
        if "stdout" in result:
            result = json.loads(result["stdout"])
        return result["count"]

    doctor = call("target", "doctor")
    check(doctor["states"]["outer"] == "prohibited", "outer UI prohibited")
    check(doctor["ready"], "ordinary desktop ready before test")
    sip = call("os", "--", "/usr/bin/csrutil", "status")
    check("enabled" in sip.get("stdout", "") and "disabled" not in sip.get("stdout", ""), "SIP enabled")
    check(status()["unlock"]["installation"] == "healthy", "unlock provider installed")
    check(raw({"operation": "application.launch", "applicationId": "org.machine-control.fixture"}).get("accepted"), "fixture launched")
    for local in [False, True]:
        old = fixture_ref(local)
        before = counter()
        raw({"operation": "input.key", "key": "ctrl-cmd-q", "provider": "macos-native"}, local)
        time.sleep(1)
        locked = status()
        check(locked["desktopState"] == "locked" and locked["unlock"]["readiness"] == "ready", "locked and unlock ready")
        doctor = call("target", "doctor")
        check(not doctor["ready"] and doctor["states"]["desktop"] == "locked"
              and doctor["states"]["administration"] == "ready", "doctor separates lock from administration")
        for provider in ["macos-native", "cua"]:
            for operation, fields in [("input.key", {"key": "a"}), ("input.click", {"x": 300, "y": 300})]:
                result = raw({"operation": operation, "target": "org.machine-control.fixture", "provider": provider, **fields}, local)
                check(result.get("errorCode") == "desktop_not_unlocked" and result.get("delivery") == "refused", "locked input refuses before posting")
        check(counter() == before, "locked fixture has no input effect")
        stale = raw({"operation": "session.unlock", "requestId": str(uuid.uuid4()),
                     "expectedDesktopGeneration": "stale"}, local)
        check(stale.get("errorCode") == "stale_generation", "stale unlock refused")
        identifier = str(uuid.uuid4())
        request = {"operation": "session.unlock", "requestId": identifier,
                   "expectedDesktopGeneration": locked["desktopGeneration"],
                   "expectedHelperGeneration": locked["unlock"]["helperGeneration"]}
        result = raw(request, local)
        check(result.get("effect") == "confirmed" and result.get("actualRoute") == "guest.broker/macos.authorization-plugin", "native password-free unlock")
        unlocked = status()
        check(unlocked["desktopState"] == "unlocked" and unlocked["desktopGeneration"] != locked["desktopGeneration"], "OS unlock and generation change")
        result = raw({"operation": "action", "reference": old, "action": "press"}, local)
        check(result.get("errorCode") == "stale_reference", "pre-lock reference invalidated")
        raw({"operation": "action", "reference": fixture_ref(local), "action": "press"}, local)
        check(counter() == before + 1, "fresh AX action has independent file effect")
        request["expectedDesktopGeneration"] = unlocked["desktopGeneration"]
        check(raw(request, local).get("errorCode") == "unlock_request_replayed_or_limit", "duplicate request cannot rearm")
        request["requestId"] = str(uuid.uuid4())
        noop = raw(request, local)
        check(noop.get("delivery") == "not_applicable" and noop.get("data", {}).get("alreadyUnlocked"), "already unlocked is a no-input no-op")
    check(call("target", "doctor")["ready"], "ordinary readiness restored")
    print("Session unlock conformance passed; target remains unlocked.")


if __name__ == "__main__":
    main()
