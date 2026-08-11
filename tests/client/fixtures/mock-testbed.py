#!/usr/bin/env python3

import json
import os
from pathlib import Path
import sys


arguments = sys.argv[1:]
if path := os.environ.get("MACHINE_CONTROL_MOCK_LOG"):
    Path(path).write_text(json.dumps(arguments), encoding="utf-8")
command = arguments[0] if arguments else ""
state_path_value = os.environ.get("MACHINE_CONTROL_MOCK_STATE_FILE")
state_path = Path(state_path_value) if state_path_value else None
power_state = (
    state_path.read_text(encoding="utf-8").strip()
    if state_path is not None and state_path.exists()
    else "running"
)
expected_workspace = os.environ.get("MACHINE_CONTROL_MOCK_EXPECT_WORKSPACE")
if expected_workspace is not None and os.environ.get(
    "MACHINE_CONTROL_WORKSPACE_HANDLE"
) != expected_workspace:
    print("workspace selector was not forwarded", file=sys.stderr)
    raise SystemExit(2)

if command == "workspace-capabilities" and arguments[1:] == ["--json"]:
    value = {
        "schema": "machine-control-workspace-capabilities/v0",
        "intents": {
            "persistent": {
                "availability": "available",
                "retention": "retained",
                "mechanisms": [{
                    "kind": "existing_instance",
                    "costClass": "unknown",
                    "sourceMustBeStopped": False,
                    "concurrentWithSource": True,
                }],
                "reasons": [],
            },
            "isolated": {
                "availability": "available",
                "retention": "discardOnRelease",
                "mechanisms": [{
                    "kind": "provider_disposable_overlay",
                    "costClass": "overlay",
                    "sourceMustBeStopped": True,
                    "concurrentWithSource": False,
                }],
                "reasons": [],
            },
            "candidate": {
                "availability": "available",
                "retention": "retained",
                "mechanisms": [{
                    "kind": "full_copy",
                    "costClass": "full_copy",
                    "sourceMustBeStopped": True,
                    "concurrentWithSource": True,
                }],
                "reasons": [],
            },
        },
        "limits": {
            "maxTemporaryWorkspaces": 1,
            "maxRetainedWorkspaces": 2,
            "fullCopyFallback": "explicit",
        },
        "storage": {
            "measurement": "estimate",
            "freeBytes": 1073741824,
        },
        "extensions": {},
    }
    if os.environ.get("MACHINE_CONTROL_MOCK_BAD_WORKSPACE_CAPABILITIES"):
        value["intents"].pop("isolated")
    print(json.dumps(value))
    raise SystemExit(0)

if command == "workspace-acquire":
    intent = arguments[2] if len(arguments) == 4 else ""
    if os.environ.get("MACHINE_CONTROL_MOCK_WORKSPACE_REFUSAL"):
        print(json.dumps({
            "schema": "machine-control-workspace/v0",
            "operation": "acquire",
            "accepted": False,
            "uncertainty": "none",
            "errorCode": "intent_unavailable",
            "message": "The requested workspace intent is unavailable",
            "data": {},
        }))
        raise SystemExit(1)
    mechanisms = {
        "persistent": ("existing_instance", "retained", "none", "unknown"),
        "isolated": (
            "provider_disposable_overlay",
            "discardOnRelease",
            "providerDiscardOnStop",
            "overlay",
        ),
        "candidate": (
            "full_copy", "retained", "explicitRelease", "full_copy"
        ),
    }
    mechanism, retention, cleanup, cost = mechanisms[intent]
    data = {
        "handle": f"w-fixture-{intent}",
        "requestedIntent": intent,
        "actualMechanism": mechanism,
        "retention": retention,
        "cleanup": cleanup,
        "storage": {
            "costClass": cost,
            "measurement": "estimate",
            "preflight": "pass",
        },
    }
    if os.environ.get("MACHINE_CONTROL_MOCK_PRIVATE_WORKSPACE_FIELD"):
        data["providerVmName"] = "private-vm-fixture"
    print(json.dumps({
        "schema": "machine-control-workspace/v0",
        "operation": "acquire",
        "accepted": True,
        "uncertainty": "none",
        "data": data,
    }))
    raise SystemExit(0)

if command == "workspace-inventory" and arguments[1:] == ["--json"]:
    print(json.dumps({
        "schema": "machine-control-workspace/v0",
        "operation": "inventory",
        "accepted": True,
        "uncertainty": "none",
        "data": {
            "workspaces": [{
                "handle": "w-fixture-isolated",
                "intent": "isolated",
                "actualMechanism": "provider_disposable_overlay",
                "retention": "discardOnRelease",
                "state": "running",
                "cleanup": "release",
            }],
            "counts": {"temporary": 1, "retained": 0},
        },
    }))
    raise SystemExit(0)

if command == "workspace-release" and len(arguments) == 4:
    print(json.dumps({
        "schema": "machine-control-workspace/v0",
        "operation": "release",
        "accepted": True,
        "uncertainty": "none",
        "data": {
            "handle": arguments[2],
            "disposition": "discarded",
        },
    }))
    raise SystemExit(0)

if command == "workspace-gc" and arguments[1:] == ["--dry-run", "--json"]:
    print(json.dumps({
        "schema": "machine-control-workspace/v0",
        "operation": "gc",
        "accepted": True,
        "uncertainty": "none",
        "data": {
            "dryRun": True,
            "candidates": [],
            "count": 0,
        },
    }))
    raise SystemExit(0)

if command in {"post-update", "maintenance"}:
    operation = arguments[1] if len(arguments) > 1 else ""
    profile = (
        arguments[arguments.index("--profile") + 1]
        if "--profile" in arguments
        else "development"
    )
    platform_name = (
        "chromeos"
        if command == "maintenance"
        else os.environ.get("MACHINE_CONTROL_MOCK_PLATFORM", "linux")
    )
    malformed = bool(os.environ.get("MACHINE_CONTROL_MOCK_BAD_MAINTENANCE"))
    healthy = not bool(os.environ.get("MACHINE_CONTROL_MOCK_UNHEALTHY_MAINTENANCE"))
    value = {
        "schema": (
            "wrong"
            if malformed
            else f"machine-control-{platform_name}-post-update-orchestration/v0"
        ),
        "operation": operation,
        "route": "fixture_guest_transport",
        "healthy": healthy,
        "reboot": {
            "requested": "--reboot" in arguments,
            "observed": "--reboot" in arguments and healthy,
        },
        "post_update": {
            "schema": f"machine-control-{platform_name}-post-update/v0",
            "mode": operation,
            "profile": profile,
            "healthy": healthy,
            "boot_epoch_utc": "private-observation-must-not-project",
            "checks": [{
                "id": "fixture_service",
                "required": True,
                "status": "pass" if healthy else "fail",
                "observed": "ready" if healthy else "unavailable",
                "privateDetail": "must-not-project",
            }],
            "repairs": (
                [{"id": "fixture_service", "status": "not_needed"}]
                if operation == "repair"
                else []
            ),
        },
        "doctor": {
            "schema": "machine-control-doctor/v0",
            "ready": (
                healthy
                and not bool(os.environ.get(
                    "MACHINE_CONTROL_MOCK_MAINTENANCE_DOCTOR_NOT_READY"
                ))
            ),
            "states": {"power": "running"},
        },
    }
    if not healthy:
        value["failure"] = "fixture_unhealthy"
    print(json.dumps(value))
    raise SystemExit(0 if healthy else 1)

if command == "appliance-certify":
    profile = (
        arguments[arguments.index("--profile") + 1]
        if "--profile" in arguments
        else "development"
    )
    platform_name = os.environ.get("MACHINE_CONTROL_MOCK_PLATFORM", "linux")
    healthy = not bool(os.environ.get("MACHINE_CONTROL_MOCK_UNHEALTHY_MAINTENANCE"))
    value = {
        "schema": f"machine-control-{platform_name}-appliance-certification/v0",
        "healthy": healthy,
        "profile": profile,
        "source": {
            "revision": "0123456789abcdef",
            "archive_sha256": "0" * 64,
        },
        "reboot": {
            "observed": healthy,
            "privateBootEpoch": "must-not-project",
        },
        "guest_checks": {
            "schema": f"machine-control-{platform_name}-appliance-guest-certification/v0",
            "healthy": healthy,
            "source_digest_match": healthy,
            "portable_checks": "passed" if healthy else "failed",
            "native_checks": "passed" if healthy else "not_run",
            "staging_removed": True,
            "privateStage": "must-not-project",
        },
        "final_power": "off" if healthy else "running",
    }
    if not healthy:
        value["failed_stage"] = "guest_checks"
    print(json.dumps(value))
    raise SystemExit(0 if healthy else 1)

if (
    (command == "doctor" and arguments[1:] == ["--json"])
    or (command == "common-doctor" and arguments[1:] == [])
):
    if os.environ.get("MACHINE_CONTROL_MOCK_BAD_DOCTOR"):
        print('{"schema":"wrong"}')
        raise SystemExit(1)
    ready = (
        power_state == "running"
        and not bool(os.environ.get("MACHINE_CONTROL_MOCK_NOT_READY"))
    )
    target_platform = os.environ.get(
        "MACHINE_CONTROL_MOCK_PLATFORM", "linux"
    )
    is_device = target_platform in {"android", "ios", "quest"}
    reported_power = (
        power_state
        if state_path is not None
        else ("running" if ready else "off")
    )
    states = {
        "power": reported_power,
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
        if target_platform == "chromeos":
            states["boot"] = "ready" if ready else "unavailable"
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
            else (
                []
                if target_platform == "chromeos"
                else ["status", "up", "suspend", "shutdown", "force-stop"]
            )
        ),
        "extensions": {}
    }))
    raise SystemExit(0 if ready else 1)

if command == "candidate-status" and arguments[1:] == ["--json"]:
    print(json.dumps({
        "schema": "machine-control-candidate-assertion/v0",
        "identityPin": "verified",
        "role": "candidate",
        "powerState": power_state,
        "workspaceOwnership": "clear",
    }))
    raise SystemExit(0)

if command == "status":
    print(power_state)
elif command == "probe":
    print("ready")
elif command in {"up", "suspend", "shutdown", "force-stop", "reboot"}:
    if command == "up" and os.environ.get("MACHINE_CONTROL_MOCK_UP_FAIL"):
        print("private-adapter-failure", file=sys.stderr)
        raise SystemExit(1)
    if state_path is not None:
        next_state = {
            "up": "running",
            "suspend": "suspended",
            "shutdown": "off",
            "force-stop": "off",
            "reboot": "running",
        }[command]
        state_path.write_text(next_state, encoding="utf-8")
    print("private-adapter-detail")
elif command in {"control", "control-local"}:
    request = (
        json.load(sys.stdin)
        if len(arguments) == 1
        else json.loads(arguments[1])
    )
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
