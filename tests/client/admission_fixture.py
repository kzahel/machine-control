"""Deterministic protocol peer for SDK lifecycle fixtures; no OS control."""
import json
import os
from pathlib import Path
import sys

state = "offered"
sequence = 0
remaining = 60
resumed_polls = 0
activations = 0
mode = os.environ.get("MC_ADMISSION_FIXTURE", "ready")
version = "v1" if mode == "legacy-v1" else "v2"
schema = "machine-control-admission/" + version
channel_schema = "machine-control-admission-channel/" + version
record = Path(os.environ["MC_ADMISSION_RECORD"])

def event(name):
    with record.open("a") as stream:
        stream.write(name + "\n")

def view():
    return dict(schema=schema, revision=1, intentId="fixture-intent", state=state,
        offerGeneration=1, blockingReasons=[], resourceGenerations={"desktop":1} if state == "active" else {},
        sessionId=("fixture-session" + str(activations) if mode == "resumed" else "fixture-session") if state == "active" else None, terminalReason="cancelled" if state == "ended" else None)

for line in sys.stdin.buffer:
    request = json.loads(line)
    operation = request["operation"]
    if (mode == "sequenced" or mode.startswith("outer")) and operation != "control.open":
        if request.get("requestSequence") != sequence + 1:
            break
        sequence += 1
    if operation == "control.open" and mode == "prepared-required":
        if request.get("preparedConsole") is not True or request.get("surfaces") != ["desktop"]:
            break
        event("prepared-console")
    event(operation)
    if mode == "malformed":
        print('{"schema":"obsolete"}', flush=True)
        break
    if operation == "control.open" and mode in {"paused", "outer-paused"}:
        state = "paused"
    elif operation == "control.open" and mode == "renewable-clock":
        remaining = request['durationSeconds']
    elif operation == "control.accept":
        state = "active"
        activations += 1
    elif mode == "resumed" and operation == "control.status" and activations == 1:
        resumed_polls += 1
        state = "paused" if resumed_polls == 1 else "offered"
    elif operation == "control.cancel":
        state = "ended"
    elif operation == "control.heartbeat" and mode == "renewable-clock" and state == "active":
        # Advance a deterministic provider clock across the old task cutoff.
        remaining -= 600
        event('elapsed:600')
        if remaining <= 0:
            state = "ended"
    data = view()
    if mode == "resumed": data["waitRemainingSeconds"] = 2
    if mode.startswith("renewable"):
        data.update(renewal="owner_connection/v1", activeRemainingSeconds=remaining)
    if operation == "control.renew":
        assert request['sessionId'] == 'fixture-session' and request['resourceGenerations'] == {'desktop':1}
        if mode == "renewable-refused":
            print(json.dumps(dict(schema=channel_schema, requestId=request["requestId"],
                                  accepted=False, errorCode="access_ended")), flush=True)
            continue
        remaining = request['durationSeconds']
        data['activeRemainingSeconds'] = remaining
    if mode == "sequenced" or mode.startswith("outer"): data["requestSequencing"] = "strict"
    if mode.startswith("outer"): data["outerRecovery"] = "borrowed_exact_claim/v1"
    if operation == "control.dispatch":
        event("effect")
        if mode.startswith("outer"): event(request["request"]["operation"])
        uncertain = mode in {"uncertain", "uncertain-accepted"}
        data = dict(schema="machine-control/v0", accepted=mode != "uncertain",
            actualRoute="fixture", generation="fixture-generation", hostInterference="none", elapsedMs=0,
            operation=request["request"]["operation"], requestId=request["requestId"],
            delivery="confirmed", effect="unknown" if uncertain else "observed",
            uncertainty="interrupted_after_possible_dispatch" if uncertain else "none")
        if mode == "unverified" and request["request"]["operation"] == "type":
            data.update(effect="unverifiable", uncertainty="Independent application effect not supplied",
                        retrySafety="observe_before_retry")
    if operation == "control.dispatch" and mode.startswith("outer"):
        data["data"] = {"reference":"fixture-outer-reference"}
        if mode == "outer-refused" and request["request"]["operation"] == "outer.step":
            data.update(accepted=False, errorCode="outer_claim_changed_or_expired", uncertainty="interrupted_after_possible_dispatch")
    print(json.dumps(dict(schema=channel_schema, requestId=request["requestId"], accepted=True, data=data)), flush=True)
event("EOF")
