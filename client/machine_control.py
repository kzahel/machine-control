#!/usr/bin/env python3
"""Target-selecting client for testbed and resident machine control."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform as host_platform
import re
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
CANDIDATE_ASSERTION_SCHEMA = "machine-control-candidate-assertion/v0"
WORKSPACE_CAPABILITIES_SCHEMA = "machine-control-workspace-capabilities/v0"
WORKSPACE_RESULT_SCHEMA = "machine-control-workspace/v0"
MAINTENANCE_CAPABILITIES_SCHEMA = "machine-control-maintenance-capabilities/v0"
MAINTENANCE_RESULT_SCHEMA = "machine-control-maintenance/v0"
CLIENT_VERSION = "0.2.0"
CONTROLLER_PLATFORMS = {"darwin", "linux", "windows"}
LAUNCHERS = {"auto", "direct", "python", "powershell", "bash"}
WORKSPACE_INTENTS = {"persistent", "isolated", "candidate"}
WORKSPACE_MECHANISMS = {
    "existing_instance",
    "provider_disposable_overlay",
    "filesystem_cow_clone",
    "qcow_backing_overlay",
    "full_copy",
    "fresh_provision",
}

DEFAULT_TARGETS: dict[str, dict[str, Any]] = {
    "windows": {
        "platform": "windows",
        "profile": "windows-11-desktop",
        "controllerPlatforms": ["darwin"],
        "launcher": "direct",
        "workspaceDefaultIntent": "persistent",
        "command": [str(ROOT / "platforms" / "windows" / "bin" / "winvm")],
    },
    "macos": {
        "platform": "macos",
        "profile": "macos-aqua-tart",
        "controllerPlatforms": ["darwin"],
        "launcher": "direct",
        "workspaceDefaultIntent": "persistent",
        "command": [str(ROOT / "platforms" / "macos" / "bin" / "macvm")],
    },
    "linux": {
        "platform": "linux",
        "profile": "ubuntu-gnome-wayland",
        "controllerPlatforms": ["darwin"],
        "launcher": "direct",
        "workspaceDefaultIntent": "persistent",
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

MAINTENANCE_ADAPTERS: dict[str, dict[str, str]] = {
    "windows": {
        "orchestrationSchema":
            "machine-control-windows-post-update-orchestration/v0",
        "postUpdateSchema": "machine-control-windows-post-update/v0",
        "certificationSchema":
            "machine-control-windows-appliance-certification/v0",
    },
    "macos": {
        "orchestrationSchema":
            "machine-control-macos-post-update-orchestration/v0",
        "postUpdateSchema": "machine-control-macos-post-update/v0",
        "certificationSchema":
            "machine-control-macos-appliance-certification/v0",
    },
    "linux": {
        "orchestrationSchema":
            "machine-control-linux-post-update-orchestration/v0",
        "postUpdateSchema": "machine-control-linux-post-update/v0",
        "certificationSchema":
            "machine-control-linux-appliance-certification/v0",
    },
}

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
        workspace_default_intent = value.get("workspaceDefaultIntent")
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
        if (
            workspace_default_intent is not None
            and workspace_default_intent not in WORKSPACE_INTENTS
        ):
            raise ClientError(
                "invalid_registry",
                f"Target '{alias}' has an invalid workspaceDefaultIntent",
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
        if workspace_default_intent is not None:
            targets[alias]["workspaceDefaultIntent"] = workspace_default_intent
    return targets


def target_view(alias: str, target: dict[str, Any]) -> dict[str, Any]:
    current = controller_platform()
    view = {
        "logicalTarget": alias,
        "platform": target["platform"],
        "profile": target["profile"],
        "interface": target.get("interface", "machine-control-v0"),
        "controllerPlatform": current,
        "controllerPlatforms": list(target["controllerPlatforms"]),
        "controllerSupported": current in target["controllerPlatforms"],
    }
    if "workspaceDefaultIntent" in target:
        view["workspaceDefaultIntent"] = target["workspaceDefaultIntent"]
    if "_workspaceHandle" in target:
        view["workspaceHandle"] = target["_workspaceHandle"]
    return view


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
    input_text: str | None = None,
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
            input=input_text,
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


def _nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_workspace_capabilities(value: Any) -> dict[str, Any]:
    top_keys = {"schema", "intents", "limits", "storage", "extensions"}
    if (
        not isinstance(value, dict)
        or value.get("schema") != WORKSPACE_CAPABILITIES_SCHEMA
        or set(value) != top_keys
    ):
        raise ClientError(
            "invalid_workspace_capabilities",
            f"Workspace capabilities must use {WORKSPACE_CAPABILITIES_SCHEMA}",
            1,
        )
    intents = value.get("intents")
    if not isinstance(intents, dict) or set(intents) != WORKSPACE_INTENTS:
        raise ClientError(
            "invalid_workspace_capabilities",
            "Workspace capabilities must describe every portable intent",
            1,
        )
    mechanism_keys = {
        "kind",
        "costClass",
        "sourceMustBeStopped",
        "concurrentWithSource",
    }
    for intent_name, intent in intents.items():
        if not isinstance(intent, dict) or set(intent) != {
            "availability", "retention", "mechanisms", "reasons"
        }:
            raise ClientError(
                "invalid_workspace_capabilities",
                f"Workspace intent '{intent_name}' is invalid",
                1,
            )
        availability = intent.get("availability")
        retention = intent.get("retention")
        mechanisms = intent.get("mechanisms")
        reasons = intent.get("reasons")
        if availability not in {"available", "unavailable"}:
            raise ClientError(
                "invalid_workspace_capabilities",
                f"Workspace intent '{intent_name}' availability is invalid",
                1,
            )
        expected_retention = (
            "discardOnRelease" if intent_name == "isolated" else "retained"
        )
        if retention != expected_retention:
            raise ClientError(
                "invalid_workspace_capabilities",
                f"Workspace intent '{intent_name}' retention is invalid",
                1,
            )
        if (
            not isinstance(mechanisms, list)
            or (availability == "available") != bool(mechanisms)
            or not isinstance(reasons, list)
            or not all(isinstance(reason, str) and reason for reason in reasons)
        ):
            raise ClientError(
                "invalid_workspace_capabilities",
                f"Workspace intent '{intent_name}' support detail is invalid",
                1,
            )
        seen: set[str] = set()
        for mechanism in mechanisms:
            if not isinstance(mechanism, dict) or set(mechanism) != mechanism_keys:
                raise ClientError(
                    "invalid_workspace_capabilities",
                    f"Workspace intent '{intent_name}' mechanism is invalid",
                    1,
                )
            kind = mechanism.get("kind")
            if kind not in WORKSPACE_MECHANISMS or kind in seen:
                raise ClientError(
                    "invalid_workspace_capabilities",
                    f"Workspace intent '{intent_name}' mechanism kind is invalid",
                    1,
                )
            seen.add(kind)
            if mechanism.get("costClass") not in {
                "overlay", "copy_on_write", "full_copy", "unknown"
            } or not all(
                isinstance(mechanism.get(field), bool)
                for field in ("sourceMustBeStopped", "concurrentWithSource")
            ):
                raise ClientError(
                    "invalid_workspace_capabilities",
                    f"Workspace intent '{intent_name}' mechanism detail is invalid",
                    1,
                )
    limits = value.get("limits")
    if not isinstance(limits, dict) or set(limits) != {
        "maxTemporaryWorkspaces",
        "maxRetainedWorkspaces",
        "fullCopyFallback",
    }:
        raise ClientError(
            "invalid_workspace_capabilities", "Workspace limits are invalid", 1
        )
    if (
        not _nonnegative_integer(limits.get("maxTemporaryWorkspaces"))
        or not _nonnegative_integer(limits.get("maxRetainedWorkspaces"))
        or limits["maxRetainedWorkspaces"] < 1
        or limits.get("fullCopyFallback")
        not in {"prohibited", "explicit", "allowed"}
    ):
        raise ClientError(
            "invalid_workspace_capabilities", "Workspace limits are invalid", 1
        )
    storage = value.get("storage")
    if not isinstance(storage, dict) or not set(storage).issubset(
        {"measurement", "freeBytes"}
    ) or "measurement" not in storage:
        raise ClientError(
            "invalid_workspace_capabilities", "Workspace storage is invalid", 1
        )
    free_bytes = storage.get("freeBytes")
    if storage.get("measurement") not in {
        "exact", "estimate", "unavailable"
    } or (free_bytes is not None and not _nonnegative_integer(free_bytes)):
        raise ClientError(
            "invalid_workspace_capabilities", "Workspace storage is invalid", 1
        )
    if not isinstance(value.get("extensions"), dict):
        raise ClientError(
            "invalid_workspace_capabilities",
            "Workspace extensions must be an object",
            1,
        )
    return value


def _valid_workspace_handle(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(
        r"w-[A-Za-z0-9][A-Za-z0-9._-]{7,127}", value
    ) is not None


def _validate_workspace_item(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {
        "handle", "intent", "actualMechanism", "retention", "state", "cleanup"
    }:
        raise ClientError(
            "invalid_workspace_result", "Workspace inventory item is invalid", 1
        )
    if (
        not _valid_workspace_handle(value.get("handle"))
        or value.get("intent") not in WORKSPACE_INTENTS
        or value.get("actualMechanism") not in WORKSPACE_MECHANISMS
        or value.get("retention") not in {"retained", "discardOnRelease"}
        or value.get("state") not in {"off", "running", "unknown"}
        or value.get("cleanup") not in {"none", "release", "pending"}
    ):
        raise ClientError(
            "invalid_workspace_result", "Workspace inventory item is invalid", 1
        )


def validate_workspace_result(value: Any, operation: str) -> dict[str, Any]:
    allowed_keys = {
        "schema", "operation", "accepted", "uncertainty", "data",
        "errorCode", "message",
    }
    if (
        not isinstance(value, dict)
        or value.get("schema") != WORKSPACE_RESULT_SCHEMA
        or value.get("operation") != operation
        or not set(value).issubset(allowed_keys)
        or not isinstance(value.get("accepted"), bool)
        or value.get("uncertainty") not in {"none", "bounded", "unknown"}
        or not isinstance(value.get("data"), dict)
    ):
        raise ClientError(
            "invalid_workspace_result",
            f"Workspace result must use {WORKSPACE_RESULT_SCHEMA}",
            1,
        )
    data = value["data"]
    if not value["accepted"]:
        if (
            data
            or not isinstance(value.get("errorCode"), str)
            or not value["errorCode"]
            or not isinstance(value.get("message"), str)
            or not value["message"]
        ):
            raise ClientError(
                "invalid_workspace_result", "Workspace refusal is invalid", 1
            )
        return value
    if "errorCode" in value or "message" in value:
        raise ClientError(
            "invalid_workspace_result", "Accepted workspace result has an error", 1
        )
    if operation == "acquire":
        if set(data) != {
            "handle", "requestedIntent", "actualMechanism", "retention",
            "cleanup", "storage",
        } or not _valid_workspace_handle(data.get("handle")):
            raise ClientError(
                "invalid_workspace_result", "Workspace acquisition is invalid", 1
            )
        storage = data.get("storage")
        if (
            data.get("requestedIntent") not in WORKSPACE_INTENTS
            or data.get("actualMechanism") not in WORKSPACE_MECHANISMS
            or data.get("retention") not in {"retained", "discardOnRelease"}
            or data.get("cleanup")
            not in {"none", "explicitRelease", "providerDiscardOnStop"}
            or not isinstance(storage, dict)
            or set(storage) != {"costClass", "measurement", "preflight"}
            or storage.get("costClass")
            not in {"overlay", "copy_on_write", "full_copy", "unknown"}
            or storage.get("measurement")
            not in {"exact", "estimate", "unavailable"}
            or storage.get("preflight") not in {"pass", "warn", "unavailable"}
        ):
            raise ClientError(
                "invalid_workspace_result", "Workspace acquisition is invalid", 1
            )
    elif operation == "inventory":
        if set(data) != {"workspaces", "counts"}:
            raise ClientError(
                "invalid_workspace_result", "Workspace inventory is invalid", 1
            )
        workspaces = data.get("workspaces")
        counts = data.get("counts")
        if (
            not isinstance(workspaces, list)
            or not isinstance(counts, dict)
            or set(counts) != {"temporary", "retained"}
            or not all(_nonnegative_integer(counts.get(key)) for key in counts)
        ):
            raise ClientError(
                "invalid_workspace_result", "Workspace inventory is invalid", 1
            )
        for item in workspaces:
            _validate_workspace_item(item)
    elif operation == "release":
        if (
            set(data) != {"handle", "disposition"}
            or not _valid_workspace_handle(data.get("handle"))
            or data.get("disposition")
            not in {"retained", "discarded", "alreadyAbsent"}
        ):
            raise ClientError(
                "invalid_workspace_result", "Workspace release is invalid", 1
            )
    elif operation == "gc":
        if set(data) != {"dryRun", "candidates", "count"}:
            raise ClientError(
                "invalid_workspace_result", "Workspace GC result is invalid", 1
            )
        candidates = data.get("candidates")
        if (
            data.get("dryRun") is not True
            or not isinstance(candidates, list)
            or not _nonnegative_integer(data.get("count"))
            or data["count"] != len(candidates)
        ):
            raise ClientError(
                "invalid_workspace_result", "Workspace GC result is invalid", 1
            )
        for item in candidates:
            _validate_workspace_item(item)
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


def readiness_observation(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "ready": value["ready"],
        "states": value["states"],
        "resident": value.get("resident"),
    }


def ensure_ready(alias: str, target: dict[str, Any]) -> int:
    initial, _ = doctor(alias, target)
    elapsed_ms = initial["adapter"]["elapsedMs"]
    actions: list[dict[str, str]] = []
    final = initial
    completion = "ready" if initial["ready"] else "repair_required"

    if not initial["ready"] and initial["states"]["power"] in {
        "off", "suspended", "starting"
    }:
        if "up" not in initial["lifecycleOperations"]:
            raise ClientError(
                "readiness_start_unsupported",
                "The target does not declare an ordinary start operation",
            )
        try:
            _, _, start_ms = run_adapter(target, ["up"])
            elapsed_ms += start_ms
            actions.append({
                "id": "start",
                "adapterOperation": "up",
                "status": "completed",
            })
        except ClientError as error:
            if error.code != "adapter_failed":
                raise
            actions.append({
                "id": "start",
                "adapterOperation": "up",
                "status": "reportedFailed",
            })
            final, _ = doctor(alias, target)
            elapsed_ms += final["adapter"]["elapsedMs"]
            data = {
                "ready": final["ready"],
                "completion": (
                    "ready_with_adapter_error"
                    if final["ready"]
                    else "action_failed"
                ),
                "initial": readiness_observation(initial),
                "actions": actions,
                "final": readiness_observation(final),
                "uncertainty": "bounded",
                "errorCode": "readiness_action_reported_failure",
            }
            emit(target_result(
                alias, target, "ensure-ready", data, elapsed_ms
            ))
            return 0 if final["ready"] else 1
        final, _ = doctor(alias, target)
        elapsed_ms += final["adapter"]["elapsedMs"]
        completion = "ready" if final["ready"] else "repair_required"

    data: dict[str, Any] = {
        "ready": final["ready"],
        "completion": completion,
        "initial": readiness_observation(initial),
        "actions": actions,
        "final": readiness_observation(final),
        "uncertainty": "none",
    }
    if not final["ready"]:
        data["errorCode"] = "readiness_repair_required"
        if (
            target.get("interface", "machine-control-v0") == "machine-control-v0"
            and target["platform"] in MAINTENANCE_ADAPTERS
        ):
            data["recommendedActions"] = [{
                "operation": "maintenance.audit",
                "profile": "development",
                "mutatesTarget": False,
            }]
    emit(target_result(alias, target, "ensure-ready", data, elapsed_ms))
    return 0 if final["ready"] else 1


def candidate_assertion(target: dict[str, Any]) -> tuple[dict[str, Any], int]:
    _, parsed, elapsed_ms = run_adapter(target, ["candidate-status", "--json"])
    if not isinstance(parsed, dict) or parsed.get("schema") != CANDIDATE_ASSERTION_SCHEMA:
        raise ClientError(
            "invalid_candidate_assertion",
            "Candidate assertion has an invalid schema",
            1,
        )
    expected = {
        "identityPin": "verified",
        "role": "candidate",
        "workspaceOwnership": "clear",
    }
    if any(parsed.get(key) != value for key, value in expected.items()):
        raise ClientError(
            "candidate_not_qualified",
            "The adapter did not verify an unowned exact candidate target",
            1,
        )
    power = parsed.get("powerState")
    if power not in POWER_STATES:
        raise ClientError(
            "invalid_candidate_assertion",
            "Candidate assertion has an invalid power state",
            1,
        )
    if set(parsed) != {
        "schema", "identityPin", "role", "powerState", "workspaceOwnership"
    }:
        raise ClientError(
            "invalid_candidate_assertion",
            "Candidate assertion contains unexpected fields",
            1,
        )
    return parsed, elapsed_ms


def candidate_result(
    alias: str,
    target: dict[str, Any],
    operation: str,
    assertion: dict[str, Any],
    readiness: dict[str, Any],
    actions: list[dict[str, str]],
    elapsed_ms: int,
    eligible: bool,
) -> dict[str, Any]:
    return target_result(
        alias,
        target,
        operation,
        {
            "identityPin": assertion["identityPin"],
            "role": assertion["role"],
            "workspaceOwnership": assertion["workspaceOwnership"],
            "readiness": readiness_observation(readiness),
            "actions": actions,
            "finalPowerState": assertion["powerState"],
            "eligibleForPrivatePromotion": eligible,
            "uncertainty": "none",
        },
        elapsed_ms,
    )


def handle_candidate(
    alias: str, target: dict[str, Any], operation: str
) -> int:
    if "_workspaceHandle" in target:
        raise ClientError(
            "candidate_inventory_target_required",
            "Candidate promotion requires the private inventory target, "
            "not a workspace handle",
        )
    assertion, elapsed_ms = candidate_assertion(target)
    if assertion["powerState"] != "running":
        raise ClientError(
            "candidate_must_be_running",
            "Candidate validation requires a running exact target",
            1,
        )
    readiness, _ = doctor(alias, target)
    elapsed_ms += readiness["adapter"]["elapsedMs"]
    if not readiness["ready"]:
        emit(candidate_result(
            alias, target, operation, assertion, readiness, [], elapsed_ms, False
        ))
        return 1
    if operation == "validate-candidate":
        emit(candidate_result(
            alias, target, operation, assertion, readiness, [], elapsed_ms, False
        ))
        return 0

    _, _, shutdown_ms = run_adapter(target, ["shutdown"])
    stopped, stopped_ms = candidate_assertion(target)
    elapsed_ms += shutdown_ms + stopped_ms
    if stopped["powerState"] != "off":
        raise ClientError(
            "candidate_not_stopped",
            "Candidate did not reach the required stopped handoff state",
            1,
        )
    actions = [{
        "id": "clean-shutdown",
        "adapterOperation": "shutdown",
        "status": "completed",
    }]
    emit(candidate_result(
        alias, target, operation, stopped, readiness, actions, elapsed_ms, True
    ))
    return 0


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


def maintenance_spec(target: dict[str, Any]) -> dict[str, str]:
    if target.get("interface", "machine-control-v0") != "machine-control-v0":
        raise ClientError(
            "unsupported_maintenance_interface",
            "This target does not expose the appliance maintenance interface",
        )
    spec = MAINTENANCE_ADAPTERS.get(target["platform"])
    if spec is None:
        raise ClientError(
            "unsupported_maintenance_platform",
            "This platform does not declare appliance maintenance operations",
        )
    return spec


def maintenance_capabilities(
    alias: str, target: dict[str, Any]
) -> dict[str, Any]:
    maintenance_spec(target)
    return {
        "schema": MAINTENANCE_CAPABILITIES_SCHEMA,
        "target": target_view(alias, target),
        "profiles": ["runtime", "development"],
        "operations": {
            "audit": {
                "availability": "available",
                "mutatesTarget": False,
                "requiresExactCandidate": False,
                "reboot": "prohibited",
            },
            "repair": {
                "availability": "available",
                "mutatesTarget": True,
                "requiresExactCandidate": True,
                "reboot": "optional_explicit",
            },
            "certify": {
                "availability": "available",
                "mutatesTarget": True,
                "requiresExactCandidate": True,
                "reboot": "required",
                "requiresCleanCommittedSource": True,
            },
        },
    }


def _maintenance_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ClientError(
            "invalid_maintenance_result",
            "Platform maintenance checks must be an array",
            1,
        )
    allowed = {
        "id", "required", "status", "healthy", "observed", "state", "repair"
    }
    projected: list[dict[str, Any]] = []
    for check in value:
        if not isinstance(check, dict) or not isinstance(check.get("id"), str):
            raise ClientError(
                "invalid_maintenance_result",
                "Platform maintenance checks are invalid",
                1,
            )
        item = {key: check[key] for key in allowed if key in check}
        if not all(
            isinstance(item.get(key), bool)
            for key in ("required", "healthy")
            if key in item
        ) or not all(
            isinstance(item.get(key), str)
            for key in ("status", "observed", "state", "repair")
            if key in item
        ):
            raise ClientError(
                "invalid_maintenance_result",
                "Platform maintenance check fields are invalid",
                1,
            )
        projected.append(item)
    return projected


def validate_maintenance_result(
    value: Any,
    target: dict[str, Any],
    operation: str,
    profile: str,
    reboot_requested: bool = False,
) -> dict[str, Any]:
    spec = maintenance_spec(target)
    schema_key = (
        "certificationSchema" if operation == "certify" else "orchestrationSchema"
    )
    if not isinstance(value, dict) or value.get("schema") != spec[schema_key]:
        raise ClientError(
            "invalid_maintenance_result",
            f"Platform maintenance must return {spec[schema_key]}",
            1,
        )
    if not isinstance(value.get("healthy"), bool):
        raise ClientError(
            "invalid_maintenance_result",
            "Platform maintenance healthy must be boolean",
            1,
        )

    if operation == "certify":
        if value["healthy"] and (
            value.get("profile") != profile or value.get("final_power") != "off"
        ):
            raise ClientError(
                "invalid_maintenance_result",
                "Healthy certification did not prove its profile and stopped state",
                1,
            )
        if value["healthy"]:
            source = value.get("source")
            guest = value.get("guest_checks")
            reboot = value.get("reboot")
            reboot_observed = isinstance(reboot, dict) and any(
                reboot.get(key) is True
                for key in (
                    "observed", "changedBootIdObserved",
                    "changedBootEpochObserved",
                )
            )
            if (
                not isinstance(source, dict)
                or not all(
                    isinstance(source.get(key), str) and source[key]
                    for key in ("revision", "archive_sha256")
                )
                or not isinstance(guest, dict)
                or guest.get("healthy") is not True
                or guest.get("source_digest_match") is not True
                or guest.get("portable_checks") != "passed"
                or guest.get("native_checks") != "passed"
                or guest.get("staging_removed") is not True
                or not reboot_observed
            ):
                raise ClientError(
                    "invalid_maintenance_result",
                    "Healthy certification evidence is incomplete",
                    1,
                )
        return value

    if value.get("operation") != operation:
        raise ClientError(
            "invalid_maintenance_result",
            "Platform maintenance operation does not match the request",
            1,
        )
    reboot = value.get("reboot")
    if not isinstance(reboot, dict) or not all(
        isinstance(reboot.get(key), bool) for key in ("requested", "observed")
    ) or reboot.get("requested") is not reboot_requested:
        raise ClientError(
            "invalid_maintenance_result",
            "Platform maintenance reboot evidence is invalid",
            1,
        )
    post_update = value.get("post_update")
    if post_update is not None:
        if (
            not isinstance(post_update, dict)
            or post_update.get("schema") != spec["postUpdateSchema"]
            or post_update.get("profile") != profile
            or not isinstance(post_update.get("healthy"), bool)
        ):
            raise ClientError(
                "invalid_maintenance_result",
                "Platform post-update evidence is invalid",
                1,
            )
        _maintenance_checks(post_update.get("checks"))
    doctor_result = value.get("doctor")
    if doctor_result is not None and (
        not isinstance(doctor_result, dict)
        or doctor_result.get("schema") != DOCTOR_SCHEMA
        or not isinstance(doctor_result.get("ready"), bool)
    ):
        raise ClientError(
            "invalid_maintenance_result",
            "Platform maintenance doctor evidence is invalid",
            1,
        )
    if value["healthy"] and (
        not isinstance(post_update, dict)
        or post_update.get("healthy") is not True
        or not isinstance(doctor_result, dict)
        or doctor_result.get("ready") is not True
        or (reboot_requested and reboot.get("observed") is not True)
    ):
        raise ClientError(
            "invalid_maintenance_result",
            "Healthy maintenance evidence is incomplete",
            1,
        )
    return value


def _maintenance_projection(
    value: dict[str, Any], operation: str, profile: str
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "profile": profile,
        "healthy": value["healthy"],
        "platformResultSchema": value["schema"],
    }
    if operation != "certify":
        data["route"] = value.get("route", "unknown")
        data["reboot"] = value["reboot"]
        post_update = value.get("post_update")
        if isinstance(post_update, dict):
            data["checks"] = _maintenance_checks(post_update["checks"])
            repairs = post_update.get("repairs")
            if isinstance(repairs, list):
                data["repairs"] = [
                    {
                        key: item[key]
                        for key in ("id", "status")
                        if key in item
                    }
                    for item in repairs
                    if isinstance(item, dict)
                ]
        doctor_result = value.get("doctor")
        if isinstance(doctor_result, dict):
            data["readiness"] = {
                "ready": doctor_result["ready"],
                "states": doctor_result.get("states", {}),
            }
    else:
        source = value.get("source")
        if isinstance(source, dict):
            data["source"] = {
                key: source[key]
                for key in ("revision", "archive_sha256")
                if isinstance(source.get(key), str)
            }
        reboot = value.get("reboot")
        data["reboot"] = {
            "observed": bool(
                isinstance(reboot, dict)
                and (
                    reboot.get("observed") is True
                    or reboot.get("changedBootIdObserved") is True
                    or reboot.get("changedBootEpochObserved") is True
                )
            )
        }
        guest = value.get("guest_checks")
        if isinstance(guest, dict):
            data["guestChecks"] = {
                key: guest[key]
                for key in (
                    "schema", "healthy", "source_digest_match",
                    "portable_checks", "native_checks", "staging_removed",
                    "failure",
                )
                if key in guest
            }
        if isinstance(value.get("final_power"), str):
            data["finalPower"] = value["final_power"]
        if isinstance(value.get("failed_stage"), str):
            data["failedStage"] = value["failed_stage"]
    if isinstance(value.get("failure"), str):
        data["failure"] = value["failure"]
    return data


def handle_maintenance(
    alias: str, target: dict[str, Any], arguments: list[str]
) -> int:
    if not arguments:
        raise ClientError("usage", "maintenance requires an operation")
    operation = arguments[0]
    if operation == "capabilities":
        if len(arguments) != 1:
            raise ClientError("usage", "maintenance capabilities takes no options")
        emit(maintenance_capabilities(alias, target))
        return 0
    if operation not in {"audit", "repair", "certify"}:
        raise ClientError(
            "unsupported_maintenance_operation",
            f"Unsupported maintenance operation '{operation}'",
        )
    maintenance_spec(target)
    profile = "development"
    reboot = False
    index = 1
    while index < len(arguments):
        option = arguments[index]
        if option == "--profile" and index + 1 < len(arguments):
            profile = arguments[index + 1]
            if profile not in {"development", "runtime"}:
                raise ClientError(
                    "invalid_maintenance_profile",
                    "Maintenance profile must be development or runtime",
                )
            index += 2
            continue
        if option == "--reboot":
            reboot = True
            index += 1
            continue
        raise ClientError("usage", f"Unsupported maintenance option '{option}'")
    if reboot and operation != "repair":
        raise ClientError(
            "invalid_maintenance_reboot",
            "--reboot is valid only with maintenance repair",
        )
    if operation in {"repair", "certify"} and "_workspaceHandle" in target:
        raise ClientError(
            "maintenance_inventory_target_required",
            "Maintenance mutation requires the exact private inventory target",
        )
    adapter_arguments = (
        ["appliance-certify", "--profile", profile, "--json"]
        if operation == "certify"
        else [
            "post-update", operation, "--profile", profile,
            *(["--reboot"] if reboot else []), "--json",
        ]
    )
    completed, parsed, elapsed_ms = run_adapter(
        target, adapter_arguments, accept_json_failure=True
    )
    value = validate_maintenance_result(
        parsed, target, operation, profile, reboot_requested=reboot
    )
    emit({
        "schema": MAINTENANCE_RESULT_SCHEMA,
        "operation": f"maintenance.{operation}",
        "accepted": True,
        "target": target_view(alias, target),
        "adapter": {
            "kind": "authoritative_testbed",
            "elapsedMs": elapsed_ms,
        },
        "data": _maintenance_projection(value, operation, profile),
    })
    return 0 if completed.returncode == 0 and value["healthy"] else 1


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
        "ensure-ready",
        "validate-candidate",
        "prepare-promotion",
    }
    if native_device:
        allowed.add("reboot")
        allowed.difference_update({
            "ensure-ready", "validate-candidate", "prepare-promotion"
        })
    if operation not in allowed or len(arguments) != 1:
        raise ClientError(
            "unsupported_target_operation",
            f"Unsupported target operation '{operation}'",
        )
    if operation == "doctor":
        value, exit_code = doctor(alias, target)
        emit(value)
        return exit_code
    if operation == "ensure-ready":
        return ensure_ready(alias, target)
    if operation in {"validate-candidate", "prepare-promotion"}:
        return handle_candidate(alias, target, operation)
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
            "usage", "Invalid command arguments"
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


def ios_request(arguments: list[str]) -> dict[str, Any]:
    if not arguments:
        raise ClientError("usage", "ios requires an operation")
    command, rest = arguments[0], arguments[1:]
    if command in {"capabilities", "home"}:
        if rest:
            raise ClientError("usage", f"ios {command} accepts no arguments")
        return {
            "operation": (
                "capabilities" if command == "capabilities" else "navigation.home"
            )
        }
    if command == "runner":
        if not rest or rest[0] != "prepare":
            raise ClientError("usage", "ios runner requires prepare")
        options = parse_options(
            rest[1:], [(('--refresh',), {"action": "store_true"})]
        )
        return {"operation": "runner.prepare", "refresh": options.refresh}
    if command == "application":
        if not rest or rest[0] not in {"install", "launch", "terminate"}:
            raise ClientError(
                "usage", "ios application requires install, launch, or terminate"
            )
        action, values = rest[0], rest[1:]
        if action == "install":
            if len(values) != 1:
                raise ClientError(
                    "usage", "ios application install requires PATH.app"
                )
            return {"operation": "application.install", "path": values[0]}
        if action == "launch":
            options = parse_options(
                values,
                [
                    (("application",), {}),
                    (("--relaunch",), {"action": "store_true"}),
                ],
            )
            return {
                "operation": "application.launch",
                "application": options.application,
                "relaunch": options.relaunch,
            }
        options = parse_options(values, [(("application",), {"nargs": "?"})])
        request: dict[str, Any] = {"operation": "application.terminate"}
        if options.application:
            request["application"] = options.application
        return request
    if command == "snapshot":
        options = parse_options(
            rest,
            [
                (("--interactive", "-i"), {"action": "store_true"}),
                (("--depth", "-d"), {"type": int}),
                (("--scope", "-s"), {}),
            ],
        )
        request = {
            "operation": "semantic.snapshot",
            "interactive": options.interactive,
        }
        if options.depth is not None:
            request["depth"] = options.depth
        if options.scope is not None:
            request["scope"] = options.scope
        return request
    if command in {"press", "fill"}:
        definitions: list[tuple[tuple[str, ...], dict[str, Any]]] = [
            (("target",), {}),
        ]
        if command == "fill":
            definitions.append((("text",), {}))
        definitions.append((("--settle",), {"action": "store_true"}))
        options = parse_options(rest, definitions)
        request = {
            "operation": f"semantic.{command}",
            "target": options.target,
            "settle": options.settle,
        }
        if command == "fill":
            request["text"] = options.text
        return request
    raise ClientError(
        "unsupported_ios_command", f"Unsupported iOS command '{command}'"
    )


def handle_ios(
    alias: str, target: dict[str, Any], arguments: list[str]
) -> int:
    if target["platform"] != "ios" or target.get("interface") != "native":
        raise ClientError(
            "unsupported_ios_target",
            "The ios command family requires a native physical-iOS target",
        )
    request = ios_request(arguments)
    serialized = json.dumps(request, separators=(",", ":"), ensure_ascii=False)
    completed, parsed, elapsed_ms = run_adapter(
        target,
        ["control"],
        accept_json_failure=True,
        input_text=serialized,
    )
    value = validate_resident(parsed, "ios")
    value = add_client_projection(
        value,
        alias,
        target,
        str(request["operation"]),
        len(serialized.encode("utf-8")),
        len(completed.stdout.strip().encode("utf-8")),
        elapsed_ms,
        False,
    )
    emit(value)
    return 0 if value["accepted"] else 1


def _workspace_adapter_call(
    target: dict[str, Any], arguments: list[str]
) -> tuple[Any, int]:
    try:
        _, parsed, elapsed_ms = run_adapter(
            target, arguments, accept_json_failure=True
        )
    except ClientError as error:
        if error.code == "adapter_failed":
            raise ClientError(
                "workspace_adapter_failed",
                "The authoritative adapter could not complete the workspace request",
                error.exit_code,
            ) from error
        raise
    if parsed is None:
        raise ClientError(
            "invalid_workspace_result",
            "The authoritative adapter returned no workspace JSON",
            1,
        )
    return parsed, elapsed_ms


def _workspace_intent(arguments: list[str]) -> str | None:
    if not arguments:
        return None
    if len(arguments) == 1 and arguments[0].startswith("--intent="):
        return arguments[0].partition("=")[2]
    if len(arguments) == 2 and arguments[0] == "--intent":
        return arguments[1]
    raise ClientError(
        "usage", "workspace acquire accepts only --intent INTENT"
    )


def handle_workspace(
    alias: str, target: dict[str, Any], arguments: list[str]
) -> int:
    if target.get("_workspaceHandle") is not None:
        raise ClientError(
            "workspace_selection_conflict",
            "Workspace management cannot run through an already selected workspace",
        )
    if target.get("interface", "machine-control-v0") != "machine-control-v0":
        raise ClientError(
            "unsupported_workspace_interface",
            "This target does not expose the VM workspace interface",
        )
    if not arguments:
        raise ClientError("usage", "workspace requires an operation")
    operation, rest = arguments[0], arguments[1:]
    if operation == "capabilities":
        if rest:
            raise ClientError(
                "usage", "workspace capabilities accepts no arguments"
            )
        parsed, elapsed_ms = _workspace_adapter_call(
            target, ["workspace-capabilities", "--json"]
        )
        value = validate_workspace_capabilities(parsed)
        default_intent = target.get("workspaceDefaultIntent")
        if default_intent is not None:
            value["defaultIntent"] = default_intent
        value["target"] = target_view(alias, target)
        value["adapter"] = {
            "kind": "authoritative_testbed",
            "elapsedMs": elapsed_ms,
        }
        emit(value)
        return 0
    if operation == "acquire":
        intent = _workspace_intent(rest) or target.get("workspaceDefaultIntent")
        if intent is None:
            raise ClientError(
                "workspace_intent_required",
                "Workspace intent is required because this target has no default",
            )
        if intent not in WORKSPACE_INTENTS:
            raise ClientError(
                "invalid_workspace_intent",
                f"Unsupported workspace intent '{intent}'",
            )
        adapter_arguments = [
            "workspace-acquire", "--intent", intent, "--json"
        ]
    elif operation == "inventory":
        if rest:
            raise ClientError("usage", "workspace inventory accepts no arguments")
        adapter_arguments = ["workspace-inventory", "--json"]
    elif operation == "release":
        if len(rest) != 1 or not _valid_workspace_handle(rest[0]):
            raise ClientError(
                "invalid_workspace_handle",
                "workspace release requires one opaque workspace handle",
            )
        adapter_arguments = [
            "workspace-release", "--handle", rest[0], "--json"
        ]
    elif operation == "gc":
        if rest != ["--dry-run"]:
            raise ClientError(
                "workspace_gc_requires_dry_run",
                "Workspace garbage collection currently requires --dry-run",
            )
        adapter_arguments = ["workspace-gc", "--dry-run", "--json"]
    else:
        raise ClientError(
            "unsupported_workspace_operation",
            f"Unsupported workspace operation '{operation}'",
        )
    parsed, elapsed_ms = _workspace_adapter_call(target, adapter_arguments)
    value = validate_workspace_result(parsed, operation)
    if (
        operation == "acquire"
        and value["accepted"]
        and value["data"]["requestedIntent"] != intent
    ):
        raise ClientError(
            "workspace_intent_mismatch",
            "Adapter workspace intent does not match the request",
            1,
        )
    value["target"] = target_view(alias, target)
    value["adapter"] = {
        "kind": "authoritative_testbed",
        "elapsedMs": elapsed_ms,
    }
    emit(value)
    return 0 if value["accepted"] else 1


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
                       [--target ALIAS] [--workspace HANDLE] COMMAND ...

Commands:
  inventory list|status|guide|doctor  Use the private deployment inventory
  targets                         List logical targets without private paths
  target status|up|suspend|shutdown|force-stop|reboot|doctor|capabilities
         ensure-ready|validate-candidate|prepare-promotion
  maintenance capabilities|audit|repair [--reboot]|certify [--profile ...]
  workspace capabilities|acquire|inventory|release|gc --dry-run
  desktop status|capabilities|applications|windows|snapshot|action|capture
  desktop input text|key|click|move|drag|scroll
  desktop application launch|activate|terminate
  desktop call|call-local JSON     Translate a common resident request
  desktop raw|raw-local JSON       Send a provider-native resident request
  desktop artifact HANDLE [PATH]   Fetch a bounded resident artifact
  ios capabilities|runner prepare [--refresh]
  ios application install|launch|terminate
  ios snapshot|press|fill|home     Typed physical-iOS XCTest operations
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
        "workspace": None,
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
            ("--workspace", "workspace"),
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
        if known.workspace is not None:
            if not _valid_workspace_handle(known.workspace):
                raise ClientError(
                    "invalid_workspace_handle",
                    "--workspace requires an opaque workspace handle",
                )
            target = {
                **target,
                "environment": {
                    **target.get("environment", {}),
                    "MACHINE_CONTROL_WORKSPACE_HANDLE": known.workspace,
                },
                "_workspaceHandle": known.workspace,
            }
        if operation == "target":
            return handle_target(alias, target, remainder[1:])
        if operation == "maintenance":
            return handle_maintenance(alias, target, remainder[1:])
        if operation == "workspace":
            return handle_workspace(alias, target, remainder[1:])
        if operation == "desktop":
            return handle_desktop(alias, target, remainder[1:])
        if operation == "ios":
            return handle_ios(alias, target, remainder[1:])
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
