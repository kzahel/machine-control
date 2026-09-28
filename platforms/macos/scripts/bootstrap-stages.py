#!/usr/bin/env python3
"""Read-only, evidence-based Tart bootstrap stages."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys


SCHEMA = "macvm-bootstrap-stages/v0"
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/macvm"
PROVIDER = ROOT / "providers/tart-macos/provider.sh"


def command(*arguments: str, timeout: int = 30) -> tuple[bool, str]:
    try:
        result = subprocess.run(arguments, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return result.returncode == 0, result.stdout


def document(*arguments: str, timeout: int = 30) -> dict | list | None:
    _, output = command(*arguments, timeout=timeout)
    try:
        result = json.loads(output)
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, (dict, list)) else None


def stage(name: str, state: str, evidence: str,
          action: str | None = None, *next_command: str) -> dict:
    return {"name": name, "state": state, "evidence": evidence,
            "nextActionId": action,
            "nextCommand": list(next_command) if next_command else None}


def exact_configuration() -> bool:
    name = os.environ.get("MACVM_NAME", "")
    return (bool(name) and name == os.environ.get("MACVM_EXPECTED_NAME") and
            os.environ.get("MACVM_REQUIRE_MUTATION_GUARD") == "true" and
            os.environ.get("MACVM_TARGET_ROLE") == "candidate")


def host_permissions() -> dict | None:
    data = document(str(PROVIDER), "host-permissions", timeout=60)
    if (isinstance(data, dict) and type(data.get("screenCapture")) is bool and
            type(data.get("postEvent")) is bool):
        return {"screenCapture": data["screenCapture"],
                "postEvent": data["postEvent"]}
    return None


def stored_credential() -> bool:
    path = os.environ.get("MACVM_ADMIN_SECRET_FILE", "")
    if not path:
        return False
    try:
        secret = Path(path)
        info = secret.lstat()
        return (stat.S_ISREG(info.st_mode) and
                info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o600 and info.st_size > 0)
    except OSError:
        return False


def preflight(kind: str) -> dict:
    stages: list[dict] = []
    host_ready = platform.system() == "Darwin" and platform.machine() == "arm64"
    tart = os.environ.get("MACVM_TART", "/opt/homebrew/bin/tart")
    host_ready = host_ready and os.access(tart, os.X_OK)
    stages.append(stage("host", "complete" if host_ready else "blocked",
                        "mac_arm64_tart_ready" if host_ready else
                        "mac_arm64_tart_required"))
    configured = exact_configuration()
    stages.append(stage("target-config", "complete" if configured else "blocked",
                        "exact_candidate_name_guarded" if configured else
                        "exact_candidate_configuration_required"))
    available = None
    exists = False
    if host_ready and configured:
        available = document(tart, "list", "--format", "json", timeout=20)
        if isinstance(available, list) and all(
                isinstance(item, dict) and isinstance(item.get("Name"), str)
                for item in available):
            exists = any(item["Name"] == os.environ["MACVM_NAME"]
                         for item in available)
        else:
            available = None
    if not host_ready or not configured:
        stages.append(stage("vm", "blocked", "host_and_configuration_required"))
    elif available is None:
        stages.append(stage("vm", "unverified", "tart_inventory_unavailable"))
    elif exists:
        stages.append(stage("vm", "complete", "configured_vm_registered"))
    else:
        create = (("tart", "clone", "PREPARED_IMAGE", "PRIVATE_NAME")
                  if kind == "prepared" else
                  ("tart", "create", "--from-ipsw=PRIVATE_IPSW", "PRIVATE_NAME"))
        stages.append(stage("vm", "action_required", "configured_vm_absent",
                            "create_guarded_vm", *create))
    permissions = host_permissions() if host_ready else None
    if permissions is None:
        stages.append(stage("host-consent", "unverified",
                            "host_permissions_unavailable"))
    elif permissions["screenCapture"] and permissions["postEvent"]:
        stages.append(stage("host-consent", "complete",
                            "host_outer_bootstrap_permissions_granted"))
    else:
        stages.append(stage("host-consent", "human_required",
                            "host_outer_bootstrap_permission_missing",
                            "grant_host_screen_and_input_consent"))
    return {"schema": SCHEMA, "phase": "precreation", "kind": kind,
            "stages": stages, "hostPermissions": permissions}


def inspect(kind: str) -> dict:
    stages: list[dict] = []
    identity = document(str(CLI), "candidate-status", "--json", timeout=30)
    exact = bool(isinstance(identity, dict) and
                 identity.get("schema") == "machine-control-candidate-assertion/v0" and
                 identity.get("identityPin") == "verified" and
                 identity.get("role") == "candidate")
    stages.append(stage("identity", "complete" if exact else "blocked",
                        "exact_candidate_guard_verified" if exact else
                        "candidate_identity_unverified"))
    if not exact:
        return {"schema": SCHEMA, "phase": "candidate", "kind": kind,
                "stages": stages}

    doctor = document(str(CLI), "doctor", "--json", timeout=60)
    valid_doctor = bool(isinstance(doctor, dict) and
                        doctor.get("schema") == "machine-control-doctor/v0")
    states = doctor.get("states", {}) if valid_doctor else {}
    power = states.get("power", "unknown")
    running = power == "running"
    stages.append(stage("power", "complete" if running else
                        "action_required" if power in ("off", "suspended") else
                        "unverified", "vm_running" if running else
                        "vm_stopped" if power in ("off", "suspended") else
                        "vm_power_unverified",
                        "start_vm" if power in ("off", "suspended") else None,
                        *(("bin/macvm", "up") if power in ("off", "suspended") else ())))
    agent = running and states.get("administration") == "ready"
    if agent:
        agent_stage = stage("guest-agent", "complete", "guest_command_ready")
    elif not running:
        agent_stage = stage("guest-agent", "waiting", "running_vm_required")
    elif kind == "vanilla":
        agent_stage = stage("guest-agent", "human_required",
                            "setup_assistant_or_guest_agent_required",
                            "complete_setup_and_install_guest_agent")
    else:
        agent_stage = stage("guest-agent", "blocked",
                            "prepared_guest_agent_unavailable",
                            "repair_prepared_guest_agent")
    stages.append(agent_stage)

    credentials = stored_credential()
    if credentials:
        credential_stage = stage("credential", "complete",
                                 "private_login_secret_file_present")
    elif kind == "vanilla" and not running:
        credential_stage = stage("credential", "waiting",
                                 "guest_account_setup_required")
    else:
        credential_state = "human_required" if kind == "vanilla" else "action_required"
        credential_stage = stage("credential", credential_state,
                                 "guest_login_secret_missing",
                                 "record_guest_login_secret")
    stages.append(credential_stage)

    permissions = host_permissions()
    health = document(str(CLI), "ui", "health", timeout=45) if agent else None
    trusted = health.get("accessibilityTrusted") if isinstance(health, dict) else None
    host_policy = states.get("outer")
    host_permissions_ready = bool(permissions and permissions["screenCapture"]
                                  and permissions["postEvent"])
    claim_class = None
    if host_policy not in ("prohibited", "unavailable") and host_permissions_ready:
        claim_status = document(str(CLI), "claim-status", "--json", timeout=10)
        held = (claim_status.get("data", {}).get("claim")
                if isinstance(claim_status, dict) else None)
        if isinstance(held, dict) and held.get("claimId") == os.environ.get(
                "MACHINE_CONTROL_CLAIM_ID") and held.get("useClass") in (
                "ordinary", "disruptive"):
            claim_class = held["useClass"]
    outer_host_ready = host_permissions_ready and claim_class == "disruptive"
    if agent and trusted is True:
        stages.append(stage("outer-bootstrap", "complete",
                            "guest_inner_route_ready"))
    elif host_policy == "prohibited":
        stages.append(stage("outer-bootstrap", "blocked",
                            "host_outer_bootstrap_prohibited"))
    elif host_policy == "unavailable":
        stages.append(stage("outer-bootstrap", "human_required",
                            "host_session_required_for_outer_bootstrap",
                            "unlock_host_session"))
    elif permissions is None:
        stages.append(stage("outer-bootstrap", "unverified",
                            "host_permissions_unavailable"))
    elif not host_permissions_ready:
        stages.append(stage("outer-bootstrap", "human_required",
                            "host_outer_bootstrap_permission_missing",
                            "grant_host_screen_and_input_consent"))
    elif claim_class is None:
        stages.append(stage("outer-bootstrap", "unverified",
                            "claim_use_class_unverified"))
    elif claim_class != "disruptive":
        stages.append(stage("outer-bootstrap", "action_required",
                            "disruptive_claim_required",
                            "reacquire_disruptive_claim"))
    else:
        stages.append(stage("outer-bootstrap", "complete",
                            "host_outer_bootstrap_ready"))

    tools_ready = agent and command(str(CLI), "exec", "/bin/bash", "-c",
                                    "/usr/bin/xcrun --find swiftc >/dev/null && "
                                    "/bin/test -x /usr/bin/codesign", timeout=40)[0]
    stages.append(stage("guest-tools", "complete" if tools_ready else
                        "human_required" if agent else "blocked",
                        "guest_build_tools_ready" if tools_ready else
                        "guest_build_tools_missing" if agent else
                        "guest_agent_required",
                        "install_guest_command_line_tools" if agent and
                        not tools_ready else None))

    if kind == "vanilla" and not agent and running:
        stages.append(stage("administrator-authorization", "human_required",
                            "setup_assistant_administrator_required",
                            "complete_setup_assistant_as_human"))
    elif agent and not tools_ready:
        stages.append(stage("administrator-authorization", "human_required",
                            "command_line_tools_authorization_required",
                            "authorize_guest_tools_install_as_human"))
    elif not agent:
        stages.append(stage("administrator-authorization", "waiting",
                            "guest_administration_required"))
    else:
        stages.append(stage("administrator-authorization", "complete",
                            "no_administrator_handoff_pending"))

    resident = states.get("resident") == "ready"
    stages.append(stage("resident", "complete" if resident else
                        "action_required" if tools_ready else "blocked",
                        "resident_ready" if resident else
                        "resident_deployment_required" if tools_ready else
                        "guest_tools_required",
                        "bootstrap_resident" if tools_ready and not resident else None,
                        *(("bin/macvm", "bootstrap", "--profile", "development")
                          if tools_ready and not resident else ())))

    stages.append(stage("accessibility", "complete" if trusted is True else
                        "action_required" if trusted is False and
                        kind == "prepared" and credentials and outer_host_ready else
                        "human_required" if trusted is False else "unverified",
                        "guest_accessibility_granted" if trusted is True else
                        "guest_accessibility_consent_required" if trusted is False else
                        "guest_accessibility_unverified",
                        "grant_guest_accessibility" if trusted is False else None,
                        *(("bin/macvm", "authorize-ui")
                          if trusted is False else ())))

    capture = states.get("capture")
    display = doctor.get("extensions", {}).get("displayState") if valid_doctor else None
    if capture == "ready":
        capture_stage = stage("capture", "complete", "guest_capture_ready")
    elif not resident:
        capture_stage = stage("capture", "waiting", "resident_required_for_capture")
    elif states.get("desktop") == "unlocked" and display == "active":
        capture_stage = stage("capture", "action_required" if outer_host_ready else
                              "human_required",
                              "guest_screen_recording_consent_required",
                              "grant_guest_screen_recording", "bin/macvm",
                              "control", '{"operation":"capture","scope":"display"}')
    else:
        capture_stage = stage("capture", "unverified",
                              "guest_capture_prerequisites_unverified")
    stages.append(capture_stage)

    desktop = states.get("desktop", "unknown")
    direct = document(str(CLI), "ui", "session-state", timeout=30) if agent else None
    direct_desktop = (direct.get("desktopState") if isinstance(direct, dict) and
                      direct.get("observationSource") == "iokit.console-session"
                      else None)
    stale_resident = (desktop == "unknown" and direct_desktop == "unlocked" and
                      resident)
    stages.append(stage("desktop", "complete" if desktop == "unlocked" else
                        "action_required" if stale_resident else
                        "human_required" if desktop == "locked" else
                        "unverified",
                        "aqua_unlocked" if desktop == "unlocked" else
                        "resident_session_observation_stale" if stale_resident else
                        "aqua_login_required" if desktop == "locked" else
                        "aqua_state_unverified",
                        "restart_resident" if stale_resident else
                        "sign_in_to_guest" if desktop == "locked" else
                        "inspect_guest_session" if desktop == "unknown" else None,
                        *(("bin/macvm", "ui", "resident-restart")
                          if stale_resident else
                          ("bin/macvm", "post-update", "audit", "--profile",
                           "development", "--json")
                          if desktop == "unknown" and agent else ())))
    ready = valid_doctor and doctor.get("ready") is True
    stages.append(stage("doctor", "complete" if ready else "unverified",
                        "full_doctor_ready" if ready else
                        "doctor_readiness_unverified",
                        None if ready else "recheck_doctor",
                        *(("bin/macvm", "doctor", "--json") if not ready else ())))
    return {"schema": SCHEMA, "phase": "candidate", "kind": kind,
            "stages": stages, "hostPermissions": permissions}


def main() -> int:
    parser = argparse.ArgumentParser(prog="macvm bootstrap-stages")
    parser.add_argument("phase", nargs="?", choices=["preflight"])
    parser.add_argument("--kind", required=True, choices=["prepared", "vanilla"])
    parser.add_argument("--json", action="store_true", required=True)
    args = parser.parse_args()
    if args.phase == "preflight":
        report = preflight(args.kind)
    else:
        claim = os.environ.get("MACHINE_CONTROL_CLAIM_ID", "")
        if not claim or not command(str(CLI), "claim-check", "--claim-id",
                                    claim, "--json", timeout=10)[0]:
            print("An exclusive exact-candidate claim is required", file=sys.stderr)
            return 1
        report = inspect(args.kind)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
