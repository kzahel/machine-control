#!/usr/bin/env python3
"""Target-selecting client for testbed and resident machine control."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform as host_platform
import shutil
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGET_SCHEMA = "machine-control-targets/v0"
DOCTOR_SCHEMA = "machine-control-doctor/v0"
RESULT_SCHEMA = "machine-control/v0"
TARGET_RESULT_SCHEMA = "machine-control-target/v0"
CLIENT_VERSION = "0.2.0"
CONTROLLER_PLATFORMS = {"darwin", "linux", "windows"}
LAUNCHERS = {"auto", "direct", "python", "powershell", "bash"}

DEFAULT_TARGETS: dict[str, dict[str, Any]] = {
    "windows": {
        "platform": "windows",
        "profile": "windows-11-desktop",
        "controllerPlatforms": ["darwin"],
        "launcher": "direct",
        "command": [str(ROOT / "platforms" / "windows" / "bin" / "winvm")],
    },
    "macos": {
        "platform": "macos",
        "profile": "macos-aqua-tart",
        "controllerPlatforms": ["darwin"],
        "launcher": "direct",
        "command": [str(ROOT / "platforms" / "macos" / "bin" / "macvm")],
    },
    "linux": {
        "platform": "linux",
        "profile": "ubuntu-gnome-wayland",
        "controllerPlatforms": ["darwin"],
        "launcher": "direct",
        "command": [str(ROOT / "platforms" / "linux" / "bin" / "linuxvm")],
    },
    "chromeos": {
        "platform": "chromeos",
        "profile": "chromeos-developer-device",
        "interface": "native",
        "controllerPlatforms": ["darwin", "linux"],
        "launcher": "direct",
        "command": [str(ROOT / "platforms" / "chromeos" / "bin" / "chromeos")],
    },
    "ios": {
        "platform": "ios",
        "profile": "ios-coredevice-xctest",
        "interface": "native",
        "controllerPlatforms": ["darwin"],
        "launcher": "direct",
        "command": [str(ROOT / "platforms" / "ios" / "bin" / "ios-device")],
    },
    "quest": {
        "platform": "quest",
        "profile": "quest-adb-device",
        "interface": "native",
        "controllerPlatforms": ["darwin", "linux", "windows"],
        "launcher": "python",
        "command": [str(ROOT / "platforms" / "quest" / "quest.py")],
    },
    "android": {
        "platform": "android",
        "profile": "android-handheld-adb",
        "interface": "native",
        "controllerPlatforms": ["darwin", "linux", "windows"],
        "launcher": "python",
        "command": [str(ROOT / "platforms" / "android" / "android_device.py")],
    },
    "steamdeck": {
        "platform": "steamdeck",
        "profile": "steamos-devkit-device",
        "interface": "native",
        "controllerPlatforms": ["darwin", "linux"],
        "launcher": "direct",
        "command": [str(ROOT / "platforms" / "steamdeck" / "bin" / "steamdeck")],
    },
}

SUPPORTED_PLATFORMS = {
    "windows", "macos", "linux", "chromeos", "ios", "android", "quest",
    "steamdeck"
}
DEVICE_DOCTOR_PLATFORMS = {"android", "ios", "quest"}

POWER_STATES = {"off", "starting", "running", "suspended", "unknown"}
READINESS_STATES = {"ready", "degraded", "unavailable", "unknown"}
DESKTOP_STATES = {"unlocked", "locked", "protected", "no_session", "unknown"}
INTERACTION_STATES = {
    "unlocked", "locked", "protected", "no_session", "unknown"
}
OUTER_STATES = {
    "ready", "observation_only", "prohibited", "unavailable", "unknown"
}


class ClientError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 2):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def controller_platform(system: str | None = None) -> str:
    value = (system or host_platform.system()).strip().lower()
    aliases = {
        "darwin": "darwin",
        "linux": "linux",
        "windows": "windows",
    }
    if value not in aliases:
        raise ClientError(
            "controller_platform_unsupported",
            f"Unsupported controller platform '{value or 'unknown'}'",
        )
    return aliases[value]


def path_command_available(value: str) -> bool:
    path = Path(value).expanduser()
    path_like = path.is_absolute() or path.parent != Path(".")
    if not path_like:
        return shutil.which(value) is not None
    if not path.is_file():
        return False
    return os.name == "nt" or os.access(path, os.X_OK)


def launcher_command(command: list[str], launcher: str) -> list[str] | None:
    if not command:
        return None
    selected = launcher
    suffix = Path(command[0]).suffix.lower()
    if selected == "auto":
        if suffix == ".py":
            selected = "python"
        elif suffix == ".ps1":
            selected = "powershell"
        else:
            selected = "direct"
    if selected == "python":
        return [sys.executable, *command]
    if selected == "powershell":
        executable = shutil.which("pwsh") or shutil.which("powershell.exe")
        if executable is None:
            return None
        return [executable, "-NoLogo", "-NoProfile", "-File", *command]
    if selected == "bash":
        executable = shutil.which("bash")
        return [executable, *command] if executable is not None else None
    if selected == "direct" and path_command_available(command[0]):
        return list(command)
    return None


def controller_supported(target: dict[str, Any]) -> bool:
    return controller_platform() in target["controllerPlatforms"]


def resolved_adapter_command(target: dict[str, Any]) -> list[str] | None:
    return launcher_command(target["command"], target.get("launcher", "auto"))


def emit(value: Any) -> None:
    print(json.dumps(value, separators=(",", ":"), sort_keys=True))


def refusal(operation: str, code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "machine-control-client-error/v0",
        "operation": operation,
        "accepted": False,
        "errorCode": code,
        "message": message,
    }


def provider_path(path_text: str | None = None) -> Path | None:
    value = path_text or os.environ.get("MACHINE_CONTROL_INVENTORY_PROVIDER")
    if value:
        return Path(value).expanduser().resolve()
    candidate = ROOT.parent / "dotfiles" / "testbeds" / "testbeds.py"
    return candidate if candidate.is_file() else None


def provider_command(path: Path) -> list[str]:
    command = launcher_command([str(path)], "auto")
    if command is None:
        raise ClientError(
            "inventory_provider_unavailable",
            "Private inventory provider launcher is unavailable",
        )
    return command


def provider_registry(path: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [*provider_command(path), "machine-control-registry"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ClientError(
            "inventory_provider_failed",
            "Private inventory provider could not be executed",
        ) from error
    if completed.returncode != 0:
        raise ClientError(
            "inventory_provider_failed",
            "Private inventory provider rejected the registry request",
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ClientError(
            "inventory_provider_failed",
            "Private inventory provider returned invalid JSON",
        ) from error
    if not isinstance(value, dict):
        raise ClientError(
            "inventory_provider_failed",
            "Private inventory provider returned an invalid registry",
        )
    return value


def load_registry(
    path_text: str | None, provider_text: str | None = None
) -> dict[str, dict[str, Any]]:
    path: Path | None = None
    document: dict[str, Any] | None = None
    if path_text:
        path = Path(path_text).expanduser().resolve()
    elif os.environ.get("MACHINE_CONTROL_TARGETS_FILE"):
        path = Path(
            os.environ["MACHINE_CONTROL_TARGETS_FILE"]
        ).expanduser().resolve()
    elif (ROOT / "targets.local.json").exists():
        path = ROOT / "targets.local.json"
    else:
        inventory_provider = provider_path(provider_text)
        if inventory_provider is not None:
            document = provider_registry(inventory_provider)

    targets = {key: dict(value) for key, value in DEFAULT_TARGETS.items()}
    if path is None and document is None:
        return targets
    if path is not None:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ClientError(
                "invalid_registry", f"Target registry could not be read: {error}"
            ) from error
    assert document is not None
    if not isinstance(document, dict) or document.get("schema") != TARGET_SCHEMA:
        raise ClientError(
            "invalid_registry", f"Target registry must use {TARGET_SCHEMA}"
        )
    if document.get("includeDefaults", False) is not True:
        targets = {}
    configured = document.get("targets")
    if not isinstance(configured, dict):
        raise ClientError(
            "invalid_registry", "Target registry targets must be an object"
        )
    for alias, value in configured.items():
        if not isinstance(alias, str) or not alias or not isinstance(value, dict):
            raise ClientError(
                "invalid_registry",
                "Every target must have a nonempty alias and object value",
            )
        platform = value.get("platform")
        profile = value.get("profile")
        command = value.get("command")
        interface = value.get("interface", "machine-control-v0")
        environment = value.get("environment", {})
        controller_platforms = value.get("controllerPlatforms")
        launcher = value.get("launcher", "auto")
        if platform not in SUPPORTED_PLATFORMS:
            raise ClientError(
                "invalid_registry", f"Target '{alias}' has an unsupported platform"
            )
        if interface not in {"machine-control-v0", "native"}:
            raise ClientError(
                "invalid_registry", f"Target '{alias}' has an invalid interface"
            )
        if (
            not isinstance(controller_platforms, list)
            or not controller_platforms
            or not all(
                isinstance(item, str) and item in CONTROLLER_PLATFORMS
                for item in controller_platforms
            )
            or len(set(controller_platforms)) != len(controller_platforms)
        ):
            raise ClientError(
                "invalid_registry",
                f"Target '{alias}' has invalid controllerPlatforms",
            )
        if launcher not in LAUNCHERS:
            raise ClientError(
                "invalid_registry", f"Target '{alias}' has an invalid launcher"
            )
        if not isinstance(profile, str) or not profile:
            raise ClientError(
                "invalid_registry", f"Target '{alias}' requires a profile"
            )
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(item, str) and item for item in command)
        ):
            raise ClientError(
                "invalid_registry", f"Target '{alias}' requires a command array"
            )
        if not isinstance(environment, dict) or not all(
            isinstance(key, str)
            and key
            and isinstance(item, str)
            for key, item in environment.items()
        ):
            raise ClientError(
                "invalid_registry", f"Target '{alias}' has an invalid environment"
            )
        resolved = list(command)
        command_path = Path(resolved[0]).expanduser()
        if command_path.parent != Path(".") and not command_path.is_absolute():
            if path is None:
                raise ClientError(
                    "invalid_registry",
                    f"Target '{alias}' provider command must be absolute",
                )
            resolved[0] = str((path.parent / command_path).resolve())
        targets[alias] = {
            "platform": platform,
            "profile": profile,
            "interface": interface,
            "controllerPlatforms": list(controller_platforms),
            "launcher": launcher,
            "command": resolved,
            "environment": dict(environment),
        }
    return targets


def target_view(alias: str, target: dict[str, Any]) -> dict[str, Any]:
    current = controller_platform()
    return {
        "logicalTarget": alias,
        "platform": target["platform"],
        "profile": target["profile"],
        "interface": target.get("interface", "machine-control-v0"),
        "controllerPlatform": current,
        "controllerPlatforms": list(target["controllerPlatforms"]),
        "controllerSupported": current in target["controllerPlatforms"],
    }


def command_available(target: dict[str, Any]) -> bool:
    return controller_supported(target) and resolved_adapter_command(target) is not None


def select_target(
    targets: dict[str, dict[str, Any]], alias: str | None
) -> tuple[str, dict[str, Any]]:
    if not alias:
        raise ClientError("target_required", "--target is required")
    if alias not in targets:
        raise ClientError(
            "target_not_found", f"Logical target '{alias}' is not configured"
        )
    target = targets[alias]
    if not controller_supported(target):
        raise ClientError(
            "controller_platform_unsupported",
            f"Testbed adapter for '{alias}' does not support this controller platform",
        )
    if resolved_adapter_command(target) is None:
        raise ClientError(
            "adapter_unavailable", f"Testbed adapter for '{alias}' is unavailable"
        )
    return alias, target


def run_adapter(
    target: dict[str, Any],
    arguments: list[str],
    *,
    accept_json_failure: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Any | None, int]:
    command = resolved_adapter_command(target)
    if command is None:
        raise ClientError("adapter_unavailable", "Testbed adapter is unavailable")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [*command, *arguments],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, **target.get("environment", {})},
        )
    except OSError as error:
        raise ClientError(
            "adapter_failed", f"Testbed adapter could not execute: {error}"
        ) from error
    elapsed_ms = int((time.monotonic() - started) * 1000)
    parsed = None
    if completed.stdout.strip():
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            pass
    if completed.returncode != 0 and not (
        accept_json_failure and parsed is not None
    ):
        raise ClientError(
            "adapter_failed",
            f"Testbed adapter command failed with exit code {completed.returncode}",
            1,
        )
    return completed, parsed, elapsed_ms


def validate_doctor(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != DOCTOR_SCHEMA:
        raise ClientError(
            "invalid_doctor_result", f"Doctor must return {DOCTOR_SCHEMA}", 1
        )
    if not isinstance(value.get("ready"), bool):
        raise ClientError(
            "invalid_doctor_result", "Doctor ready must be boolean", 1
        )
    target = value.get("target")
    states = value.get("states")
    checks = value.get("checks")
    operations = value.get("lifecycleOperations")
    if not isinstance(target, dict) or not all(
        isinstance(target.get(key), str) and target[key]
        for key in ("platform", "profile")
    ):
        raise ClientError(
            "invalid_doctor_result", "Doctor target is incomplete", 1
        )
    if not isinstance(states, dict):
        raise ClientError("invalid_doctor_result", "Doctor states are missing", 1)
    common = {
        "power": POWER_STATES,
        "administration": READINESS_STATES,
        "semantic": READINESS_STATES,
        "capture": READINESS_STATES,
        "input": READINESS_STATES,
        "outer": OUTER_STATES,
    }
    for name, values in common.items():
        if states.get(name) not in values:
            raise ClientError(
                "invalid_doctor_result", f"Doctor state '{name}' is invalid", 1
            )
    kind = target.get("kind", "desktop")
    if kind == "desktop":
        specialized = {
            "desktop": DESKTOP_STATES,
            "resident": READINESS_STATES,
        }
    elif kind == "device":
        specialized = {
            "connection": READINESS_STATES,
            "boot": READINESS_STATES,
            "interaction": INTERACTION_STATES,
            "runner": READINESS_STATES,
        }
    else:
        raise ClientError(
            "invalid_doctor_result", "Doctor target kind is invalid", 1
        )
    for name, values in specialized.items():
        if states.get(name) not in values:
            raise ClientError(
                "invalid_doctor_result", f"Doctor state '{name}' is invalid", 1
            )
    if not isinstance(checks, list) or any(
        not isinstance(check, dict)
        or not isinstance(check.get("id"), str)
        or check.get("status") not in {"pass", "warn", "fail", "skip"}
        for check in checks
    ):
        raise ClientError("invalid_doctor_result", "Doctor checks are invalid", 1)
    if not isinstance(operations, list) or not all(
        isinstance(item, str) for item in operations
    ):
        raise ClientError(
            "invalid_doctor_result", "Doctor lifecycle operations are invalid", 1
        )
    if not isinstance(value.get("extensions"), dict):
        raise ClientError(
            "invalid_doctor_result", "Doctor extensions must be an object", 1
        )
    return value


def validate_resident(value: Any, platform: str) -> dict[str, Any]:
    required = {
        "schema",
        "requestId",
        "operation",
        "accepted",
        "actualRoute",
        "generation",
        "hostInterference",
        "uncertainty",
        "elapsedMs",
    }
    if not isinstance(value, dict) or value.get("schema") != RESULT_SCHEMA:
        raise ClientError(
            "invalid_resident_result", f"Resident must return {RESULT_SCHEMA}", 1
        )
    compatibility_fields = []
    if platform == "windows" and "hostInterference" not in value:
        value["hostInterference"] = "none"
        compatibility_fields.append("hostInterference")
    missing = sorted(required - value.keys())
    if missing:
        raise ClientError(
            "invalid_resident_result",
            f"Resident result is missing: {', '.join(missing)}",
            1,
        )
    if not isinstance(value.get("accepted"), bool):
        raise ClientError(
            "invalid_resident_result", "Resident accepted must be boolean", 1
        )
    if compatibility_fields:
        value["_clientCompatibilityFields"] = compatibility_fields
    return value


def normalize_power(raw: str) -> str:
    lowered = raw.strip().lower()
    if lowered in {"started", "running"}:
        return "running"
    if lowered in {"stopped", "off"}:
        return "off"
    if lowered in {"suspended", "paused", "saved"}:
        return "suspended"
    if lowered == "starting":
        return "starting"
    return "unknown"


def target_result(
    alias: str,
    target: dict[str, Any],
    operation: str,
    data: dict[str, Any],
    elapsed_ms: int,
) -> dict[str, Any]:
    return {
        "schema": TARGET_RESULT_SCHEMA,
        "operation": f"target.{operation}",
        "accepted": True,
        "target": target_view(alias, target),
        "adapter": {
            "kind": "authoritative_testbed",
            "elapsedMs": elapsed_ms,
        },
        "data": data,
    }


def doctor(alias: str, target: dict[str, Any]) -> tuple[dict[str, Any], int]:
    completed, parsed, elapsed_ms = run_adapter(
        target, ["doctor", "--json"], accept_json_failure=True
    )
    del completed
    value = validate_doctor(parsed)
    if value["target"]["platform"] != target["platform"]:
        raise ClientError(
            "doctor_target_mismatch",
            "Doctor platform does not match selected target",
            1,
        )
    value["target"] = {**value["target"], "logicalTarget": alias}
    value["adapter"] = {
        "kind": "authoritative_testbed",
        "elapsedMs": elapsed_ms,
    }
    return value, 0 if value["ready"] else 1


def handle_target(
    alias: str, target: dict[str, Any], arguments: list[str]
) -> int:
    if not arguments:
        raise ClientError("usage", "target requires an operation")
    operation = arguments[0]
    native_device = (
        target.get("interface", "machine-control-v0") == "native"
        and target["platform"] in DEVICE_DOCTOR_PLATFORMS
    )
    if (
        target.get("interface", "machine-control-v0") != "machine-control-v0"
        and not native_device
    ):
        raise ClientError(
            "unsupported_target_operation",
            "This target uses its native testbed interface; use inventory for "
            "readiness or testbed -- for platform commands",
        )
    allowed = {
        "status",
        "up",
        "suspend",
        "shutdown",
        "force-stop",
        "doctor",
        "capabilities",
    }
    if native_device:
        allowed.add("reboot")
    if operation not in allowed or len(arguments) != 1:
        raise ClientError(
            "unsupported_target_operation",
            f"Unsupported target operation '{operation}'",
        )
    if operation == "doctor":
        value, exit_code = doctor(alias, target)
        emit(value)
        return exit_code
    if native_device:
        value, _ = doctor(alias, target)
        if operation == "status":
            emit(
                target_result(
                    alias,
                    target,
                    operation,
                    {
                        "ready": value["ready"],
                        "states": value["states"],
                        "extensions": value["extensions"],
                    },
                    value["adapter"]["elapsedMs"],
                )
            )
            return 0
        if operation == "capabilities":
            emit(
                target_result(
                    alias,
                    target,
                    operation,
                    {
                        "lifecycleOperations": value["lifecycleOperations"],
                        "outerState": value["states"]["outer"],
                        "targetKind": value["target"].get("kind", "device"),
                    },
                    value["adapter"]["elapsedMs"],
                )
            )
            return 0
        if operation not in value["lifecycleOperations"]:
            raise ClientError(
                "unsupported_target_operation",
                f"Target '{alias}' does not support lifecycle operation '{operation}'",
            )
        completed, _, elapsed_ms = run_adapter(target, [operation])
        del completed
        after, _ = doctor(alias, target)
        emit(
            target_result(
                alias,
                target,
                operation,
                {
                    "ready": after["ready"],
                    "states": after["states"],
                    "extensions": after["extensions"],
                },
                elapsed_ms + after["adapter"]["elapsedMs"],
            )
        )
        return 0
    if operation == "capabilities":
        value, _ = doctor(alias, target)
        emit(
            target_result(
                alias,
                target,
                operation,
                {
                    "lifecycleOperations": value["lifecycleOperations"],
                    "outerState": value["states"]["outer"],
                },
                value["adapter"]["elapsedMs"],
            )
        )
        return 0
    completed, _, elapsed_ms = run_adapter(target, [operation])
    raw_state = completed.stdout.strip() if operation == "status" else ""
    if operation != "status":
        status_completed, _, status_elapsed = run_adapter(target, ["status"])
        raw_state = status_completed.stdout.strip()
        elapsed_ms += status_elapsed
    emit(
        target_result(
            alias,
            target,
            operation,
            {
                "powerState": normalize_power(raw_state),
                "adapterState": raw_state,
            },
            elapsed_ms,
        )
    )
    return 0


def parse_options(
    arguments: list[str],
    definitions: list[tuple[tuple[str, ...], dict[str, Any]]],
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    for flags, settings in definitions:
        parser.add_argument(*flags, **settings)
    try:
        return parser.parse_args(arguments)
    except SystemExit as error:
        raise ClientError(
            "usage", "Invalid desktop command arguments"
        ) from error


def desktop_request(arguments: list[str]) -> tuple[dict[str, Any], bool]:
    if not arguments:
        raise ClientError("usage", "desktop requires an operation")
    command, rest = arguments[0], arguments[1:]
    if command in {"call", "call-local", "raw", "raw-local"}:
        if len(rest) != 1:
            raise ClientError(
                "usage", f"desktop {command} requires one JSON object"
            )
        try:
            request = json.loads(rest[0])
        except json.JSONDecodeError as error:
            raise ClientError(
                "invalid_request", f"Request is not valid JSON: {error}"
            ) from error
        if not isinstance(request, dict) or not isinstance(
            request.get("operation"), str
        ):
            raise ClientError(
                "invalid_request", "Request must be an object with operation"
            )
        return request, command in {"call-local", "raw-local"}
    if command in {"status", "capabilities", "applications"}:
        if rest:
            raise ClientError(
                "usage", f"desktop {command} accepts no arguments"
            )
        return {"operation": command}, False
    if command == "windows":
        options = parse_options(
            rest, [(('--target',), {"dest": "target"})]
        )
        request = {"operation": "windows"}
        if options.target is not None:
            request["target"] = options.target
        return request, False
    if command == "snapshot":
        options = parse_options(
            rest,
            [
                (("--target",), {"required": True}),
                (("--query",), {}),
                (
                    ("--projection",),
                    {"choices": ["compact", "full"], "default": "compact"},
                ),
                (("--max-depth",), {"type": int}),
                (("--max-elements",), {"type": int}),
            ],
        )
        request = {
            "operation": "snapshot",
            "target": options.target,
            "projection": options.projection,
        }
        for name, key in (
            ("query", "query"),
            ("max_depth", "maxDepth"),
            ("max_elements", "maxElements"),
        ):
            value = getattr(options, name)
            if value is not None:
                request[key] = value
        return request, False
    if command == "action":
        options = parse_options(
            rest,
            [
                (("--reference",), {"required": True}),
                (
                    ("--action",),
                    {
                        "required": True,
                        "choices": ["press", "focus", "set_value"],
                    },
                ),
                (("--text",), {}),
            ],
        )
        request = {
            "operation": "action",
            "reference": options.reference,
            "action": options.action,
        }
        if options.text is not None:
            request["text"] = options.text
        return request, False
    if command == "capture":
        options = parse_options(
            rest,
            [
                (
                    ("--scope",),
                    {"choices": ["display", "window"], "default": "display"},
                ),
                (("--target",), {}),
                (("--window-id",), {"type": int}),
            ],
        )
        request = {"operation": "capture", "scope": options.scope}
        if options.target is not None:
            request["target"] = options.target
        if options.window_id is not None:
            request["windowId"] = options.window_id
        return request, False
    if command == "input":
        if not rest:
            raise ClientError("usage", "desktop input requires a kind")
        kind, values = rest[0], rest[1:]
        if kind in {"text", "key"} and len(values) == 1:
            return {"operation": f"input.{kind}", kind: values[0]}, False
        if kind in {"click", "move"} and len(values) in {2, 3}:
            request = {
                "operation": f"input.{kind}",
                "x": int(values[0]),
                "y": int(values[1]),
            }
            if kind == "click" and len(values) == 3:
                request["button"] = values[2]
            return request, False
        if kind == "drag" and len(values) == 4:
            return {
                "operation": "input.drag",
                "x": int(values[0]),
                "y": int(values[1]),
                "x2": int(values[2]),
                "y2": int(values[3]),
            }, False
        if kind == "scroll" and len(values) == 2:
            return {
                "operation": "input.scroll",
                "deltaX": int(values[0]),
                "deltaY": int(values[1]),
            }, False
        raise ClientError(
            "usage", f"Invalid desktop input {kind} arguments"
        )
    if command == "application":
        if not rest or rest[0] not in {"launch", "activate", "terminate"}:
            raise ClientError(
                "usage",
                "desktop application requires launch, activate, or terminate",
            )
        action, values = rest[0], rest[1:]
        options = parse_options(
            values,
            [
                (("--application-id",), {}),
                (("--target",), {}),
                (("--executable",), {}),
                (("--argument",), {"action": "append", "default": []}),
                (("--expect-target",), {}),
                (("--unit",), {}),
                (("--process-id",), {"type": int}),
            ],
        )
        request: dict[str, Any] = {
            "operation": f"application.{action}"
        }
        fields = {
            "applicationId": options.application_id,
            "target": options.target,
            "executablePath": options.executable,
            "expectTarget": options.expect_target,
            "unit": options.unit,
            "processId": options.process_id,
        }
        request.update(
            {key: value for key, value in fields.items() if value is not None}
        )
        if options.executable:
            request["command"] = [options.executable, *options.argument]
            if options.argument:
                request["argumentsList"] = options.argument
        return request, False
    raise ClientError(
        "unsupported_desktop_command",
        f"Unsupported desktop command '{command}'",
    )


def translate_request(platform: str, request: dict[str, Any]) -> dict[str, Any]:
    translated = dict(request)
    operation = str(request.get("operation", ""))
    if platform == "windows":
        operation_map = {
            "application.launch": "app.launch",
            "application.activate": "app.activate",
            "capture": "screenshot",
            "input.click": "click",
            "input.key": "key",
            "input.text": "type",
            "window.close": "window.state",
        }
        if operation == "action":
            action = request.get("action")
            if action == "press":
                operation_map["action"] = "invoke"
            elif action == "set_value":
                operation_map["action"] = "set.value"
        translated["operation"] = operation_map.get(operation, operation)
        if "windowId" in translated:
            translated["hwnd"] = translated.pop("windowId")
        if operation == "window.close":
            translated["state"] = "closed"
        command = translated.pop("command", None)
        arguments_list = translated.pop("argumentsList", None)
        if operation == "application.launch" and command:
            translated.setdefault("executablePath", command[0])
            if arguments_list:
                translated.setdefault(
                    "arguments", subprocess.list2cmdline(arguments_list)
                )
    elif platform == "linux" and operation == "action":
        action = request.get("action")
        if action == "focus":
            translated["operation"] = "focus"
        elif action == "set_value":
            translated["operation"] = "set_value"
            translated["value"] = translated.get("text", "")
    return translated


def add_client_projection(
    value: dict[str, Any],
    alias: str,
    target: dict[str, Any],
    requested_operation: str,
    request_bytes: int,
    result_bytes: int,
    elapsed_ms: int,
    local: bool,
) -> dict[str, Any]:
    value["client"] = {
        "version": CLIENT_VERSION,
        "logicalTarget": alias,
        "platform": target["platform"],
        "profile": target["profile"],
        "placement": (
            "guest_local_cli" if local else "outside_testbed_adapter"
        ),
        "requestedOperation": requested_operation,
        "residentOperation": value["operation"],
        "requestBytes": request_bytes,
        "resultBytes": result_bytes,
        "transportElapsedMs": elapsed_ms,
        "compatibilityProjection": value.pop(
            "_clientCompatibilityFields", []
        ),
    }
    return value


def artifact(
    alias: str, target: dict[str, Any], arguments: list[str]
) -> int:
    if not 1 <= len(arguments) <= 2:
        raise ClientError(
            "usage", "desktop artifact requires HANDLE [OUTPUT]"
        )
    command = (
        "artifact-fetch" if target["platform"] == "macos" else "artifact"
    )
    completed, _, elapsed_ms = run_adapter(target, [command, *arguments])
    path = completed.stdout.strip()
    if not path:
        raise ClientError(
            "artifact_failed", "Artifact adapter returned no output path", 1
        )
    emit(
        {
            "schema": "machine-control-artifact/v0",
            "accepted": True,
            "target": target_view(alias, target),
            "handle": arguments[0],
            "outputPath": path,
            "adapter": {
                "kind": "authoritative_testbed",
                "elapsedMs": elapsed_ms,
            },
        }
    )
    return 0


def handle_desktop(
    alias: str, target: dict[str, Any], arguments: list[str]
) -> int:
    if target.get("interface", "machine-control-v0") != "machine-control-v0":
        raise ClientError(
            "unsupported_desktop_interface",
            "This target does not expose the common desktop interface",
        )
    if arguments and arguments[0] == "artifact":
        return artifact(alias, target, arguments[1:])
    raw = bool(arguments and arguments[0] in {"raw", "raw-local"})
    request, local = desktop_request(arguments)
    translated = request if raw else translate_request(target["platform"], request)
    serialized = json.dumps(
        translated, separators=(",", ":"), ensure_ascii=False
    )
    command = "control-local" if local else "control"
    completed, parsed, elapsed_ms = run_adapter(
        target, [command, serialized], accept_json_failure=True
    )
    value = validate_resident(parsed, target["platform"])
    value = add_client_projection(
        value,
        alias,
        target,
        str(request["operation"]),
        len(serialized.encode("utf-8")),
        len(completed.stdout.strip().encode("utf-8")),
        elapsed_ms,
        local,
    )
    emit(value)
    return 0 if value["accepted"] else 1


def exec_escape(
    target: dict[str, Any], arguments: list[str], *, os_escape: bool
) -> int:
    values = list(arguments)
    if values and values[0] == "--":
        values = values[1:]
    if not values:
        raise ClientError(
            "usage", "Escape hatch requires arguments after --"
        )
    adapter = resolved_adapter_command(target)
    if adapter is None:
        raise ClientError("adapter_unavailable", "Testbed adapter is unavailable")
    if not os_escape:
        command = [*adapter, *values]
    elif target["platform"] == "windows":
        command = [*adapter, "ps", *values]
    elif target["platform"] == "macos":
        command = [*adapter, "exec", *values]
    elif target["platform"] == "linux":
        command = [*adapter, "exec", "--", *values]
    else:
        raise ClientError(
            "unsupported_os_escape",
            "This target does not expose a generic guest OS command route",
        )
    try:
        return subprocess.run(
            command,
            check=False,
            env={**os.environ, **target.get("environment", {})},
        ).returncode
    except OSError as error:
        raise ClientError(
            "adapter_failed", f"Testbed adapter could not execute: {error}"
        ) from error


def run_inventory(path_text: str | None, arguments: list[str]) -> int:
    path = provider_path(path_text)
    if path is None:
        raise ClientError(
            "inventory_provider_unavailable",
            "No private inventory provider is configured",
        )
    if not arguments:
        raise ClientError("usage", "inventory requires a provider command")
    return subprocess.run(
        [*provider_command(path), *arguments], check=False
    ).returncode


def usage() -> str:
    return """Usage: machine-control [--registry PATH] [--inventory-provider PATH]
                       [--target ALIAS] COMMAND ...

Commands:
  inventory list|status|guide|doctor  Use the private deployment inventory
  targets                         List logical targets without private paths
  target status|up|suspend|shutdown|force-stop|reboot|doctor|capabilities
  desktop status|capabilities|applications|windows|snapshot|action|capture
  desktop input text|key|click|move|drag|scroll
  desktop application launch|activate|terminate
  desktop call|call-local JSON     Translate a common resident request
  desktop raw|raw-local JSON       Send a provider-native resident request
  desktop artifact HANDLE [PATH]   Fetch a bounded resident artifact
  testbed -- ARG...                Explicit testbed escape hatch
  os -- ARG...                     Explicit guest administration escape hatch
"""


def parse_global_options(
    arguments: list[str],
) -> tuple[argparse.Namespace, list[str]]:
    """Parse only options before COMMAND.

    Desktop operations also use ``--target`` for an application or window.
    Keeping the global parse bounded by COMMAND prevents that resource selector
    from replacing the logical machine selector.
    """
    values: dict[str, Any] = {
        "registry": None,
        "inventory_provider": None,
        "target": None,
        "help": False,
    }
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == "--help":
            values["help"] = True
            index += 1
            continue
        matched = False
        for option, name in (
            ("--registry", "registry"),
            ("--inventory-provider", "inventory_provider"),
            ("--target", "target"),
        ):
            if token == option:
                if index + 1 >= len(arguments):
                    raise ClientError("usage", f"{option} requires a value")
                values[name] = arguments[index + 1]
                index += 2
                matched = True
                break
            if token.startswith(f"{option}="):
                value = token.partition("=")[2]
                if not value:
                    raise ClientError("usage", f"{option} requires a value")
                values[name] = value
                index += 1
                matched = True
                break
        if matched:
            continue
        break
    return argparse.Namespace(**values), arguments[index:]


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    remainder: list[str] = []
    try:
        known, remainder = parse_global_options(arguments)
        if known.help or not remainder:
            print(usage(), end="")
            return 0 if known.help else 2
        operation = remainder[0]
        if operation == "inventory":
            return run_inventory(known.inventory_provider, remainder[1:])
        targets = load_registry(known.registry, known.inventory_provider)
        if operation == "targets":
            if len(remainder) != 1:
                raise ClientError("usage", "targets accepts no arguments")
            emit(
                {
                    "schema": TARGET_SCHEMA,
                    "targets": [
                        {
                            **target_view(alias, target),
                            "adapterAvailable": command_available(target),
                        }
                        for alias, target in sorted(targets.items())
                    ],
                }
            )
            return 0
        alias, target = select_target(targets, known.target)
        if operation == "target":
            return handle_target(alias, target, remainder[1:])
        if operation == "desktop":
            return handle_desktop(alias, target, remainder[1:])
        if operation == "testbed":
            return exec_escape(target, remainder[1:], os_escape=False)
        if operation == "os":
            return exec_escape(target, remainder[1:], os_escape=True)
        raise ClientError(
            "unsupported_command", f"Unsupported command '{operation}'"
        )
    except ClientError as error:
        emit(
            refusal(
                remainder[0] if remainder else "client",
                error.code,
                str(error),
            )
        )
        return error.exit_code
    except ValueError:
        emit(
            refusal(
                operation, "invalid_number", "A numeric argument is invalid"
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
