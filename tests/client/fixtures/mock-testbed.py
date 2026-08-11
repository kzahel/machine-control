#!/usr/bin/env python3

import json
import os
from pathlib import Path
import sys


arguments = sys.argv[1:]
if path := os.environ.get("MACHINE_CONTROL_MOCK_LOG"):
    Path(path).write_text(json.dumps(arguments), encoding="utf-8")
command = arguments[0] if arguments else ""

if command == "doctor" and arguments[1:] == ["--json"]:
    if os.environ.get("MACHINE_CONTROL_MOCK_BAD_DOCTOR"):
        print('{"schema":"wrong"}')
        raise SystemExit(1)
    ready = not bool(os.environ.get("MACHINE_CONTROL_MOCK_NOT_READY"))
    print(json.dumps({
        "schema": "machine-control-doctor/v0",
        "ready": ready,
        "target": {
            "platform": os.environ.get(
                "MACHINE_CONTROL_MOCK_PLATFORM", "linux"
            ),
            "profile": "fixture"
        },
        "states": {
            "power": "running" if ready else "off",
            "administration": "ready" if ready else "unavailable",
            "desktop": "unlocked" if ready else "no_session",
            "resident": "ready" if ready else "unavailable",
            "semantic": "ready" if ready else "unavailable",
            "capture": "ready" if ready else "unavailable",
            "input": "ready" if ready else "unavailable",
            "outer": "prohibited"
        },
        "resident": {
            "contract": "machine-control/v0",
            "generation": "fixture-generation"
        } if ready else None,
        "checks": [{
            "id": "fixture",
            "status": "pass" if ready else "fail"
        }],
        "lifecycleOperations": [
            "status", "up", "suspend", "shutdown", "force-stop"
        ],
        "extensions": {}
    }))
    raise SystemExit(0 if ready else 1)

if command == "status":
    print("running")
elif command in {"up", "suspend", "shutdown", "force-stop"}:
    print("private-adapter-detail")
elif command in {"control", "control-local"}:
    request = json.loads(arguments[1])
    print(json.dumps({
        "schema": "machine-control/v0",
        "requestId": request.get("requestId", "fixture-request"),
        "operation": request["operation"],
        "accepted": True,
        "actualRoute": "fixture/resident",
        "generation": "fixture-generation",
        "delivery": "confirmed",
        "effect": "not_applicable",
        "hostInterference": "none",
        "uncertainty": "none",
        "elapsedMs": 1,
        "data": {"request": request}
    }))
elif command in {"artifact", "artifact-fetch"}:
    print(
        arguments[2]
        if len(arguments) > 2
        else "/tmp/fixture-artifact.png"
    )
elif command in {"ps", "exec"}:
    print(json.dumps(arguments[1:]))
else:
    print("unsupported", file=sys.stderr)
    raise SystemExit(2)
