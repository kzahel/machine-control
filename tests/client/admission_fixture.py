"""Deterministic protocol peer for SDK lifecycle fixtures; no OS control."""
import json
import os
from pathlib import Path
import sys

schema = "machine-control-admission/v1"
state = "offered"
sequence = 0
mode = os.environ.get("MC_ADMISSION_FIXTURE", "ready")
record = Path(os.environ["MC_ADMISSION_RECORD"])

def event(name):
    with record.open("a") as stream:
        stream.write(name + "\n")

def view():
    return dict(schema=schema, revision=1, intentId="fixture-intent", state=state,
        offerGeneration=1, blockingReasons=[], resourceGenerations={"desktop":1} if state == "active" else {},
        sessionId="fixture-session" if state == "active" else None, terminalReason="cancelled" if state == "ended" else None)

for line in sys.stdin.buffer:
    request = json.loads(line)
    operation = request["operation"]
    if (mode == "sequenced" or mode.startswith("outer")) and operation != "control.open":
        if request.get("requestSequence") != sequence + 1:
            break
        sequence += 1
    event(operation)
    if mode == "malformed":
        print('{"schema":"obsolete"}', flush=True)
        break
    if operation == "control.open" and mode in {"paused", "outer-paused"}:
        state = "paused"
    elif operation == "control.accept":
        state = "active"
    elif operation == "control.cancel":
        state = "ended"
    data = view()
    if mode == "sequenced" or mode.startswith("outer"): data["requestSequencing"] = "strict"
    if mode.startswith("outer"): data["outerRecovery"] = "borrowed_exact_claim/v1"
    if operation == "control.dispatch":
        event("effect")
        if mode.startswith("outer"): event(request["request"]["operation"])
        data = dict(schema="machine-control/v0", accepted=mode != "uncertain",
            operation=request["request"]["operation"], requestId=request["requestId"],
            delivery="confirmed", effect="observed" if mode != "uncertain" else "unknown",
            uncertainty="none" if mode != "uncertain" else "interrupted_after_possible_dispatch")
    if operation == "control.dispatch" and mode.startswith("outer"):
        data["data"] = {"reference":"fixture-outer-reference"}
        if mode == "outer-refused" and request["request"]["operation"] == "outer.step":
            data.update(accepted=False, errorCode="outer_claim_changed_or_expired", uncertainty="interrupted_after_possible_dispatch")
    print(json.dumps(dict(schema="machine-control-admission-channel/v1", requestId=request["requestId"], accepted=True, data=data)), flush=True)
event("EOF")
