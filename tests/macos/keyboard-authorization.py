#!/usr/bin/env python3
"""Real SecurityAgent authorization across six claimed Tart keyboard profiles.

Uses only the canonical stored credential transport. Never retries a failed or
uncertain submission. The caller owns VM power and claim cleanup.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

spec = importlib.util.spec_from_file_location("keyboard", Path(__file__).with_name("keyboard-layouts.py"))
keyboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keyboard)
FIXTURE = "org.machine-control.admin-fixture"
REQUESTER = "Machine Control Admin Fixture"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="macos")
    parser.add_argument("--claim", default=os.environ.get("MACHINE_CONTROL_CLAIM_ID"))
    parser.add_argument("--credential-testbed", default="macvm", help="Private inventory credential entry")
    args = parser.parse_args()
    if not args.claim:
        parser.error("--claim or MACHINE_CONTROL_CLAIM_ID is required")
    repo = Path(__file__).resolve().parents[2]
    binary = repo / "bin/machine-control"
    base = [str(binary), "--target", args.target, "--claim", args.claim]
    runtime_env = dict(os.environ, MACVM_FORBID_OUTER_UI="true")

    def mc(*argv):
        result = subprocess.run([*base, *map(str, argv)], env=runtime_env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=180)
        # Do not echo opaque provider output or private deployment paths.
        assert result.returncode == 0, "Common CLI operation failed: " + str(argv[0])
        return result.stdout

    def testbed(*argv):
        return mc("testbed", "--", *argv)

    generation = None
    checks = 0

    def control(operation, accepted=True, **fields):
        nonlocal generation, checks
        value = json.loads(testbed("control", json.dumps(dict(operation=operation, **fields))))
        assert value.get("accepted") == accepted, "Unexpected resident result: " + value.get("errorCode", operation)
        assert value.get("hostInterference") == "none"
        if generation is None:
            generation = value["generation"]
        assert value["generation"] == generation, "Resident restarted during authorization matrix"
        checks += 1
        return value

    def guest(code, *argv):
        return json.loads(testbed("exec", "/usr/bin/python3", "-c", code, *argv))

    def environment(*argv):
        return json.loads(testbed("exec", helper, *argv))

    def state():
        return json.loads(testbed("admin-fixture-state"))

    def wait_state(status):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            value = state()
            if value.get("status") == status:
                return value
            assert value.get("status") not in ["failed", "cancelled"], "Fixture authorization failed"
            time.sleep(.1)
        raise AssertionError("Fixture effect missing: " + status)

    doctor = json.loads(mc("target", "doctor"))
    assert doctor.get("ready") and doctor["target"]["profile"] == "macos-aqua-tart", "Healthy Tart target required"
    inventory = json.loads(subprocess.check_output([str(binary), "inventory", "credentials", args.credential_testbed, "--json"], env=runtime_env))
    credentials = [c for t in inventory["testbeds"] for c in t["credentials"]
                   if c["id"] == "guest-login-password" and c["environment"] == "MACVM_ADMIN_SECRET_FILE"]
    assert len(credentials) == 1 and credentials[0]["state"] == "ready", "Canonical stored appliance credential required"
    setup = guest('from pathlib import Path; import json,subprocess; h=Path.home(); '
                  'assert subprocess.check_output(["/usr/sbin/sysctl","-n","hw.model"]).decode().startswith("VirtualMac"); '
                  'print(json.dumps({"helper":str(h/"Library/Application Support/machine-control-keyboard/environment"),'
                  '"fixtureExists":(h/"Applications/Machine Control Admin Fixture.app").exists(),'
                  '"cacheExists":(h/"Library/Caches/machine-control-admin-fixture").exists()}))')
    assert not setup["fixtureExists"] and not setup["cacheExists"], "Refusing an inherited authorization fixture"
    helper = setup["helper"]
    initial = environment("status")
    mapping = keyboard.normalized_hid_mapping(initial["modifierMapping"])
    before = json.loads(testbed("host-state"))
    deployed = False
    active = False
    try:
        deployed = True
        testbed("deploy-admin-fixture")
        for layout in keyboard.LAYOUTS:
            for modifiers in ["default", "swapped"]:
                environment("remap", modifiers)
                environment("select", layout)
                testbed("reset-admin-fixture")
                active = True
                control("application.launch", applicationId=FIXTURE)
                requested = wait_state("requested")
                context = requested["requestId"]
                # A wrong requester cannot acquire a credential lease.
                refusal = control("authorization.begin", accepted=False, expectedRequester="Different Requester", contextId=context)
                assert refusal["errorCode"] == "authorization_sheet_unavailable"
                lease = control("authorization.begin", expectedRequester=REQUESTER, contextId=context, timeoutMs=120000)["data"]["leaseId"]
                # Select after the sheet appears; input-source-per-app behavior
                # must not silently qualify a different layout.
                selected = environment("select", layout)
                assert selected["inputSourceId"] == layout
                assert selected["modifierProfile"] == ("alternate" if modifiers == "swapped" else "standard")
                submitted = json.loads(testbed("authorization-submit", "--stored", lease))
                assert submitted.get("accepted"), "Credential submission refused; no retry"
                assert submitted["generation"] == generation and submitted["hostInterference"] == "none"
                assert submitted["delivery"] == "confirmed" and submitted["effect"] == "confirmed", "Authentication effect uncertain; no retry"
                assert submitted["data"]["sheetDismissed"] and submitted["data"]["attemptConsumed"]
                assert submitted["data"]["keyboardDelivery"] == "owner_process"
                completed = wait_state("completed")
                assert completed["requestId"] == context and completed["authorized"] and completed["commandCompleted"]
                active = False
                reused = control("authorization.cancel", accepted=False, leaseId=lease)
                assert reused["errorCode"] == "authorization_lease_used"
                flags = environment("status")
                assert flags["inputSourceId"] == layout
                assert flags["hidFlags"] & keyboard.MODIFIERS == 0 and flags["sessionFlags"] & keyboard.MODIFIERS == 0
                print(json.dumps(dict(layout=layout, mapping=modifiers, authenticated=True,
                                      privilegedOracle=True, keyboardDelivery="owner_process")), flush=True)
        after = json.loads(testbed("host-state"))
        print(json.dumps(dict(passed=True, cells=6, residentChecks=checks,
                              **keyboard.host_observation(before, after))), flush=True)
    finally:
        try:
            if active:
                # Cancellation is cleanup, never another credential attempt.
                control("application.terminate", target=FIXTURE)
            if deployed:
                testbed("remove-admin-fixture")
        finally:
            environment("select", initial["inputSourceId"])
            testbed("exec", "/usr/bin/hidutil", "property", "--set", json.dumps({"UserKeyMapping": mapping}))


if __name__ == "__main__":
    main()
