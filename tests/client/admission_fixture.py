"""Deterministic protocol peer for SDK lifecycle fixtures; no OS control."""
import json
import os
from pathlib import Path
import sys

schema = "machine-control-admission/v1"
state = "offered"
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
    event(operation)
    if mode == "malformed":
        print('{"schema":"obsolete"}', flush=True)
        break
    if operation == "control.open" and mode == "paused":
        state = "paused"
    elif operation == "control.accept":
        state = "active"
    elif operation == "control.cancel":
        state = "ended"
    data = view()
    if operation == "control.dispatch":
        event("effect")
        data = dict(schema="machine-control/v0", accepted=mode != "uncertain",
            operation=request["request"]["operation"], requestId=request["requestId"],
            delivery="confirmed", effect="observed" if mode != "uncertain" else "unknown",
            uncertainty="none" if mode != "uncertain" else "interrupted_after_possible_dispatch")
    print(json.dumps(dict(schema="machine-control-admission-channel/v1", requestId=request["requestId"], accepted=True, data=data)), flush=True)
event("EOF")
