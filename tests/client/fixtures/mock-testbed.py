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
    target_platform = os.environ.get(
        "MACHINE_CONTROL_MOCK_PLATFORM", "linux"
    )
    is_device = target_platform in {"android", "ios", "quest"}
    states = {
        "power": "running" if ready else "off",
        "administration": "ready" if ready else "unavailable",
        "semantic": "ready" if ready else "unavailable",
        "capture": "ready" if ready else "unavailable",
        "input": "ready" if ready else "unavailable",
        "outer": "ready" if is_device else "prohibited"
    }
    if is_device:
        states.update({
            "connection": "ready" if ready else "unavailable",
            "boot": "ready" if ready else "unavailable",
            "interaction": "unlocked" if ready else "unknown",
            "runner": "ready" if ready else "unavailable",
        })
    else:
        states.update({
            "desktop": "unlocked" if ready else "no_session",
            "resident": "ready" if ready else "unavailable",
        })
    print(json.dumps({
        "schema": "machine-control-doctor/v0",
        "ready": ready,
        "target": {
            "platform": target_platform,
            **({"kind": "device", "deviceClass": "fixture"} if is_device else {}),
            "profile": "fixture"
        },
        "states": states,
        "resident": {
            "contract": "machine-control/v0",
            "generation": "fixture-generation"
        } if ready else None,
        "checks": [{
            "id": "fixture",
            "status": "pass" if ready else "fail"
        }],
        "lifecycleOperations": (
            ["status", "doctor", "capabilities", "reboot"]
            if is_device
            else ["status", "up", "suspend", "shutdown", "force-stop"]
        ),
        "extensions": {}
    }))
    raise SystemExit(0 if ready else 1)

if command == "status":
    print("running")
elif command == "probe":
    print("ready")
elif command in {"up", "suspend", "shutdown", "force-stop", "reboot"}:
    print("private-adapter-detail")
elif command in {"control", "control-local"}:
    request = json.loads(arguments[1])
    result = {
        "schema": "machine-control/v0",
        "requestId": request.get("requestId", "fixture-request"),
        "operation": request["operation"],
        "accepted": True,
        "actualRoute": "fixture/resident",
        "generation": "fixture-generation",
        "delivery": "confirmed",
        "effect": "not_applicable",
        "uncertainty": "none",
        "elapsedMs": 1,
        "data": {"request": request}
    }
    if not os.environ.get("MACHINE_CONTROL_MOCK_OMIT_HOST_INTERFERENCE"):
        result["hostInterference"] = "none"
    print(json.dumps(result))
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
