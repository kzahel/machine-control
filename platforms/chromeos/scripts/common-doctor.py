#!/usr/bin/env python3
"""Project legacy ChromeOS health into the common minimized doctor schema."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
LEGACY_DOCTOR = Path(os.environ.get(
    "CHROMEOS_COMMON_DOCTOR_LEGACY",
    SCRIPT_DIR / "doctor.sh",
))
POST_UPDATE = Path(os.environ.get(
    "CHROMEOS_COMMON_DOCTOR_POST_UPDATE",
    SCRIPT_DIR / "post-update.sh",
))


def invoke(path: Path, *arguments: str) -> dict[str, Any]:
    environment = {**os.environ, "CHROMEOS_OUTPUT": "json"}
    completed = subprocess.run(
        [str(path), *arguments],
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def status_with_prefix(value: dict[str, Any], *prefixes: str) -> str | None:
    checks = value.get("checks")
    if not isinstance(checks, list):
        return None
    for check in checks:
        if not isinstance(check, dict):
            continue
        name = check.get("name")
        status = check.get("status")
        if (
            isinstance(name, str)
            and isinstance(status, str)
            and any(name.startswith(prefix) for prefix in prefixes)
        ):
            return status
    return None


def common_check(
    checks: list[dict[str, str]],
    identifier: str,
    ready: bool,
    ready_summary: str,
    unavailable_summary: str,
    *,
    unavailable_status: str = "fail",
) -> None:
    checks.append({
        "id": identifier,
        "status": "pass" if ready else unavailable_status,
        "summary": ready_summary if ready else unavailable_summary,
    })


def main() -> int:
    legacy = invoke(LEGACY_DOCTOR)
    maintenance = invoke(POST_UPDATE)

    ssh_ready = (
        status_with_prefix(legacy, "SSH connection to") == "ok"
        or maintenance.get("status") not in {None, "ssh_unreachable"}
    )
    session_ready = (
        status_with_prefix(legacy, "ChromeOS user session active") == "ok"
    )
    python_ready = status_with_prefix(legacy, "Remote Python available") == "ok"
    client_ready = status_with_prefix(legacy, "client.py deployed") == "ok"
    resident_ready = ssh_ready and python_ready and client_ready
    devtools_configured = (
        status_with_prefix(legacy, "Remote debugging configured") == "ok"
    )
    devtools_listening = (
        status_with_prefix(legacy, "DevTools port 9222 listening") == "ok"
    )
    semantic_ready = (
        session_ready and devtools_configured and devtools_listening
    )
    capture_ready = resident_ready
    input_ready = resident_ready
    boot_automatic = (
        status_with_prefix(
            maintenance,
            "Current boot automatically started SSH",
        ) == "ok"
    )
    rootfs_status = status_with_prefix(
        maintenance,
        "Rootfs is writable",
        "Rootfs verification is enabled",
    )
    if rootfs_status == "ok":
        rootfs_verification = "disabled"
    elif rootfs_status == "fail":
        rootfs_verification = "enabled"
    else:
        rootfs_verification = "unknown"
    maintenance_ready = maintenance.get("ok") is True
    boot_ready = ssh_ready and boot_automatic and maintenance_ready

    power = "running" if ssh_ready else "unknown"
    administration = "ready" if ssh_ready else "unavailable"
    desktop = "unlocked" if session_ready else (
        "locked" if ssh_ready else "unknown"
    )
    resident = "ready" if resident_ready else "unavailable"
    semantic = "ready" if semantic_ready else "unavailable"
    capture = "ready" if capture_ready else "unavailable"
    input_state = "ready" if input_ready else "unavailable"
    boot = "ready" if boot_ready else (
        "degraded" if ssh_ready else "unavailable"
    )

    ready = all((
        ssh_ready,
        boot_ready,
        session_ready,
        resident_ready,
        semantic_ready,
        capture_ready,
        input_ready,
    ))

    checks: list[dict[str, str]] = []
    common_check(
        checks, "connection", ssh_ready,
        "SSH administration is reachable",
        "SSH administration is unreachable",
    )
    common_check(
        checks, "ssh_boot_persistence", boot_ready,
        "Current boot has automatic SSH startup evidence",
        "Current boot lacks healthy automatic SSH startup evidence",
    )
    if rootfs_verification == "disabled":
        common_check(
            checks, "rootfs_verification", True,
            "Active root image is writable",
            "",
        )
    elif rootfs_verification == "enabled":
        common_check(
            checks, "rootfs_verification", False,
            "",
            "Rootfs verification is enabled on the active image",
        )
    else:
        common_check(
            checks, "rootfs_verification", False,
            "",
            "Active rootfs verification state is unavailable",
            unavailable_status="warn",
        )
    common_check(
        checks, "desktop_session", session_ready,
        "ChromeOS profile session is unlocked",
        "ChromeOS profile session is locked or unavailable",
    )
    common_check(
        checks, "resident", resident_ready,
        "Target-native client prerequisites are ready",
        "Target-native client prerequisites are unavailable",
    )
    common_check(
        checks, "semantic", semantic_ready,
        "Chrome desktop semantics are ready",
        "Chrome desktop semantics are unavailable",
    )
    common_check(
        checks, "capture", capture_ready,
        "Target-native capture prerequisites are ready",
        "Target-native capture prerequisites are unavailable",
    )
    common_check(
        checks, "input", input_ready,
        "Target-native input prerequisites are ready",
        "Target-native input prerequisites are unavailable",
    )
    common_check(
        checks, "outer_policy", True,
        "Ordinary outer UI is prohibited",
        "Ordinary outer UI policy is unavailable",
    )

    raw_update_state = maintenance.get("status")
    update_state = {
        "update_pending": "pending_reboot",
        "ready": "idle",
        "reboot_verification_required": "idle",
        "repair_required": "repair_required",
        "ssh_unreachable": "unknown",
    }.get(raw_update_state, "unknown")
    if boot_automatic:
        boot_persistence = "automatic_current_boot"
    elif status_with_prefix(maintenance, "Current boot started SSH manually"):
        boot_persistence = "manual_current_boot"
    else:
        boot_persistence = "unproven_current_boot"

    value = {
        "schema": "machine-control-doctor/v0",
        "ready": ready,
        "target": {
            "platform": "chromeos",
            "kind": "desktop",
            "profile": "chromeos-developer-device",
        },
        "states": {
            "power": power,
            "connection": "ready" if ssh_ready else "unavailable",
            "boot": boot,
            "administration": administration,
            "desktop": desktop,
            "resident": resident,
            "semantic": semantic,
            "capture": capture,
            "input": input_state,
            "outer": "prohibited",
        },
        "resident": (
            {
                "contract": "chromeos-native-cli/v0",
                "generation": "unavailable",
            }
            if resident_ready else None
        ),
        "checks": checks,
        "lifecycleOperations": [],
        "extensions": {
            "administrationRoute": "ssh",
            "residentPlacement": "target_native",
            "desktopSession": "chromeos_profile",
            "profileState": "unlocked" if session_ready else "locked",
            "sshBootPersistence": boot_persistence,
            "rootfsVerification": rootfs_verification,
            "updateState": update_state,
            "captureProbe": "configured_not_exercised",
            "outerRecovery": "physical_vt2_explicit",
        },
    }
    print(json.dumps(value, separators=(",", ":"), sort_keys=True))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
