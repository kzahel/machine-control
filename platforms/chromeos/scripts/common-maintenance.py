#!/usr/bin/env python3
"""Compose ChromeOS post-update operations for the common maintenance API."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
POST_UPDATE = Path(os.environ.get(
    "CHROMEOS_MAINTENANCE_POST_UPDATE",
    SCRIPT_DIR / "post-update.sh",
))
DOCTOR = Path(os.environ.get(
    "CHROMEOS_MAINTENANCE_DOCTOR",
    SCRIPT_DIR / "common-doctor.py",
))
ORCHESTRATION_SCHEMA = (
    "machine-control-chromeos-post-update-orchestration/v0"
)
POST_UPDATE_SCHEMA = "machine-control-chromeos-post-update/v0"

CHECK_PREFIXES = (
    ("SSH is reachable", "ssh_connection"),
    ("SSH is unreachable", "ssh_connection"),
    ("No ChromeOS update", "update_state"),
    ("ChromeOS update", "update_state"),
    ("Stateful VT2 SSH fallback", "stateful_ssh_fallback"),
    ("Rootfs", "rootfs_writable"),
    ("SSH autostart", "ssh_autostart"),
    ("Incompatible SSH autostart", "ssh_autostart"),
    ("Current ChromeOS release", "release_prepared"),
    ("Current boot applied the closed-lid", "power_policy_boot_persistence"),
    ("Current boot lacks closed-lid", "power_policy_boot_persistence"),
    ("Current boot", "ssh_boot_persistence"),
    ("Remote debugging", "devtools_configuration"),
    ("DevTools port", "devtools_listener"),
    ("Closed-lid power policy helper", "power_policy_helper"),
    ("Always-awake power policy self-healing guard", "power_policy_guard"),
    ("Closed-lid availability policy", "closed_lid_availability"),
)


def invoke(
    path: Path,
    *arguments: str,
    json_output: bool,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    environment = {
        **os.environ,
        "CHROMEOS_OUTPUT": "json" if json_output else "text",
    }
    completed = subprocess.run(
        [str(path), *arguments],
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    value: Any = {}
    if json_output:
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError:
            value = {}
    return completed, value if isinstance(value, dict) else {}


def audit() -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    return invoke(POST_UPDATE, json_output=True)


def common_doctor() -> dict[str, Any]:
    _, value = invoke(DOCTOR, json_output=True)
    if value.get("schema") == "machine-control-doctor/v0" and isinstance(
        value.get("ready"), bool
    ):
        return value
    return {
        "schema": "machine-control-doctor/v0",
        "ready": False,
        "states": {},
    }


def check_identifier(name: str, index: int) -> str:
    for prefix, identifier in CHECK_PREFIXES:
        if name.startswith(prefix):
            return identifier
    return f"platform_check_{index + 1}"


def project_audit(
    value: dict[str, Any],
    mode: str,
    repairs: list[dict[str, str]],
) -> dict[str, Any]:
    raw_checks = value.get("checks")
    checks: list[dict[str, Any]] = []
    if isinstance(raw_checks, list):
        for index, check in enumerate(raw_checks):
            if not isinstance(check, dict):
                continue
            name = check.get("name")
            raw_status = check.get("status")
            if not isinstance(name, str) or raw_status not in {"ok", "warn", "fail"}:
                continue
            status = {"ok": "pass", "warn": "warn", "fail": "fail"}[raw_status]
            checks.append({
                "id": check_identifier(name, index),
                "required": True,
                "status": status,
                "healthy": status == "pass",
            })
    if not checks:
        checks = [{
            "id": "platform_audit",
            "required": True,
            "status": "fail",
            "healthy": False,
        }]
    return {
        "schema": POST_UPDATE_SCHEMA,
        "mode": mode,
        "profile": "runtime",
        "healthy": value.get("ok") is True,
        "checks": checks,
        "repairs": repairs,
    }


def has_failed_check(value: dict[str, Any], prefix: str) -> bool:
    checks = value.get("checks")
    return isinstance(checks, list) and any(
        isinstance(check, dict)
        and check.get("status") == "fail"
        and isinstance(check.get("name"), str)
        and check["name"].startswith(prefix)
        for check in checks
    )


def guided_recovery_required(value: dict[str, Any]) -> bool:
    return (
        value.get("status") == "update_pending"
        or has_failed_check(value, "Rootfs verification")
    )


def emit_result(
    operation: str,
    raw_audit: dict[str, Any],
    repairs: list[dict[str, str]],
    reboot_requested: bool,
    reboot_observed: bool,
    failure: str | None,
) -> int:
    post_update = project_audit(raw_audit, operation, repairs)
    healthy = (
        post_update["healthy"]
        and (not reboot_requested or reboot_observed)
        and failure is None
    )
    result: dict[str, Any] = {
        "schema": ORCHESTRATION_SCHEMA,
        "operation": operation,
        "profile": "runtime",
        "route": "ssh_target_native",
        "healthy": healthy,
        "reboot": {
            "requested": reboot_requested,
            "observed": reboot_observed,
        },
        "post_update": post_update,
        "doctor": common_doctor(),
    }
    if failure is not None:
        result["failure"] = failure
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0 if healthy else 1


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("operation", choices=("audit", "repair"))
    parser.add_argument("--profile", required=True)
    parser.add_argument("--reboot", action="store_true")
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    if arguments.profile != "runtime":
        parser.error("ChromeOS maintenance supports only the runtime profile")
    if arguments.reboot and arguments.operation != "repair":
        parser.error("--reboot is valid only with repair")
    if not arguments.json:
        parser.error("structured --json output is required")
    return arguments


def main() -> int:
    arguments = parse_arguments()
    _, before = audit()
    if arguments.operation == "audit":
        failure = None if before.get("ok") is True else (
            str(before.get("status"))
            if isinstance(before.get("status"), str)
            else "platform_audit_failed"
        )
        return emit_result("audit", before, [], False, False, failure)

    repairs: list[dict[str, str]] = []
    if before.get("status") == "ssh_unreachable":
        repairs.append({"id": "active_image", "status": "refused"})
        return emit_result(
            "repair", before, repairs, arguments.reboot, False,
            "ssh_unreachable",
        )
    if guided_recovery_required(before):
        repairs.append({
            "id": "active_image",
            "status": "guided_recovery_required",
        })
        return emit_result(
            "repair", before, repairs, arguments.reboot, False,
            "guided_recovery_required",
        )

    after = before
    if before.get("status") not in {"ready", "reboot_verification_required"}:
        repair, _ = invoke(POST_UPDATE, "--repair", "-y", json_output=False)
        _, after = audit()
        repairs.append({
            "id": "active_image",
            "status": (
                "completed"
                if after.get("status") in {"ready", "reboot_verification_required"}
                else "incomplete"
            ),
        })
        if repair.returncode not in {0, 1} and after.get("ok") is not True:
            return emit_result(
                "repair", after, repairs, arguments.reboot, False,
                "active_image_repair_failed",
            )
    else:
        repairs.append({"id": "active_image", "status": "not_needed"})

    reboot_observed = False
    if arguments.reboot:
        if after.get("status") not in {"ready", "reboot_verification_required"}:
            return emit_result(
                "repair", after, repairs, True, False,
                "reboot_precondition_failed",
            )
        proof, _ = invoke(
            POST_UPDATE, "--verify-reboot", "-y", json_output=False
        )
        _, after = audit()
        reboot_observed = proof.returncode == 0 and after.get("ok") is True
        repairs.append({
            "id": "ssh_boot_persistence",
            "status": "completed" if reboot_observed else "failed",
        })

    failure: str | None = None
    if after.get("ok") is not True:
        failure = (
            str(after.get("status"))
            if isinstance(after.get("status"), str)
            else "post_repair_audit_failed"
        )
    elif arguments.reboot and not reboot_observed:
        failure = "reboot_proof_failed"
    return emit_result(
        "repair", after, repairs, arguments.reboot, reboot_observed, failure
    )


if __name__ == "__main__":
    raise SystemExit(main())
