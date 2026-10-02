#!/usr/bin/env python3
"""Prove real native approval expiry through the installed Mac CLI.

Dedicated appliance only. The caller stages and authenticates the exact app,
starts a separate approval-policy candidate and standing-policy observer, owns
both target claims, and restores policy, processes and power afterward.
"""

import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

parser = argparse.ArgumentParser(description=__doc__)
for name in ("target", "claim", "client", "socket", "host-claim",
             "observer-app", "observer-socket"):
    parser.add_argument("--" + name, required=True)
args = parser.parse_args()
controller = [str(Path(__file__).resolve().parents[2] / "bin/machine-control"),
              "--target", args.target, "--claim", args.claim, "os", "--"]
client = ["/usr/bin/env", "MACHINE_CONTROL_HOST_SOCKET=" + args.socket,
          args.client, "--target", "host", "--claim", args.host_claim,
          "desktop", "raw"]
pending = None


def command(arguments):
    response = subprocess.run(controller + arguments, capture_output=True,
                              text=True, timeout=30)
    assert response.returncode in (0, 1), "Unexpected transport failure"
    return json.loads(response.stdout)


def candidate(operation, **fields):
    return command(client + [json.dumps(dict(operation=operation, **fields))])


def observer(operation, **fields):
    return command([args.observer_app + "/Contents/MacOS/macui", "request",
                    args.observer_socket, json.dumps(dict(operation=operation, **fields))])


def accepted(value):
    assert value["accepted"] and value["hostInterference"] == "none", value.get("errorCode")
    return value.get("data", {})


def press(pid, label):
    deadline = time.monotonic() + 10
    while True:
        elements = accepted(observer("snapshot", target=str(pid), query=label,
                                     projection="compact", maxDepth=30,
                                     maxElements=500))["elements"]
        matches = [element for element in elements
                   if element["role"] == "AXButton" and element["label"] == label]
        if len(matches) == 1:
            assert matches[0]["enabled"]
            accepted(observer("action", reference=matches[0]["reference"], action="press"))
            return
        assert time.monotonic() < deadline, "Approval button not uniquely observed"
        time.sleep(0.2)


try:
    state = accepted(candidate("status"))
    pid = state["processId"]
    assert accepted(observer("status"))["deployment"]["policy"]["grantMode"] == "standing"
    status = accepted(candidate("grant.status"))
    assert status["policy"]["grantMode"] == "approval" and status["grant"] is None
    assert status["pendingRequest"] is None
    assert candidate("snapshot", target="org.machine-control.fixture")["errorCode"] == "approval_required"
    request = dict(operation="grant.request", requestId=str(uuid.uuid4()),
                   scopes=["observe"], reason="Bounded installed CLI native grant expiry",
                   durationSeconds=60, timeoutSeconds=120)
    pending = subprocess.Popen(controller + client + [json.dumps(request)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 15
    while accepted(candidate("grant.status"))["pendingRequest"] is None:
        assert pending.poll() is None and time.monotonic() < deadline
        time.sleep(0.2)
    press(pid, "Allow access")
    output, diagnostics = pending.communicate(timeout=30)
    assert pending.returncode == 0 and not diagnostics
    grant = accepted(json.loads(output))["grant"]
    pending = None
    assert grant["scopes"] == ["observe"] and grant["lifetime"] == "timed"
    assert grant["expiresAt"] is not None and 0 < grant["remainingSeconds"] <= 60
    accepted(candidate("snapshot", target="org.machine-control.fixture"))
    print("PASS visible native approval and installed CLI observation with a timed grant", flush=True)
    deadline = time.monotonic() + 75
    while True:
        status = accepted(candidate("grant.status"))
        if status["grant"] is None:
            break
        assert time.monotonic() < deadline, "Native grant failed to expire"
        time.sleep(1)
    assert status["lastEnded"]["reason"] == "expired"
    result = candidate("snapshot", target="org.machine-control.fixture")
    assert not result["accepted"] and result["errorCode"] == "approval_required"
    assert accepted(candidate("status"))["processId"] == pid
    print("PASS actual native grant expiry refuses observation without restarting the resident", flush=True)
finally:
    try:
        if pending is not None and pending.poll() is None:
            press(pid, "Deny")
            pending.communicate(timeout=10)
    finally:
        if pending is not None and pending.poll() is None:
            pending.terminate()
            pending.communicate(timeout=10)
        accepted(candidate("grant.revoke"))
print("PASS pending approval resolved and candidate access disarmed", flush=True)
