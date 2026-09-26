#!/usr/bin/env python3
"""Read-only, evidence-based stages for a Linux Windows factory candidate."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


STAGE_SCHEMA = "winvm-factory-stages/v0"
UUID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
ATTESTATION_MAX_AGE_SECONDS = 4 * 60 * 60


def command(*arguments: str, timeout: int = 80) -> tuple[bool, str]:
    environment = os.environ.copy()
    environment["WINVM_SSH_ALLOW_START"] = "false"
    try:
        result = subprocess.run(
            arguments, capture_output=True, text=True, env=environment,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return result.returncode == 0, result.stdout


def json_command(*arguments: str, timeout: int = 80,
                 allow_failure_json: bool = False) -> dict | None:
    accepted, output = command(*arguments, timeout=timeout)
    if not accepted and not allow_failure_json:
        return None
    try:
        document = json.loads(output)
    except json.JSONDecodeError:
        return None
    return document if isinstance(document, dict) else None


def stage(name: str, state: str, evidence: str, *next_command: str) -> dict:
    return {
        "name": name,
        "state": state,
        "evidence": evidence,
        "nextCommand": list(next_command) if next_command else None,
    }


def attestation_path(identifier: str) -> Path:
    root = Path(os.environ.get(
        "WINVM_FACTORY_STAGE_STATE_DIR",
        str(Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
            / "machine-control/windows-factory-stages"),
    ))
    return root / identifier / "first-logon.json"


def attested(identifier: str) -> bool:
    path = attestation_path(identifier)
    try:
        if path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
            return False
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    observed = data.get("observedAt")
    if type(observed) not in (int, float):
        return False
    age = time.time() - observed
    return (0 <= age <= ATTESTATION_MAX_AGE_SECONDS
            and data.get("schema") == "winvm-factory-first-logon-attestation/v0"
            and data.get("targetId") == identifier
            and data.get("completed") is True)


def attest_first_logon(provider: Path, identifier: str) -> int:
    if not UUID.fullmatch(identifier):
        print("Exact candidate identity is not pinned", file=sys.stderr)
        return 1
    identity = json_command(str(provider), "assert-target", "inspect", "--json")
    if not identity or identity.get("identity_pin") != "verified" or identity.get("role") != "candidate":
        print("Exact candidate assertion failed", file=sys.stderr)
        return 1
    status = json_command(str(provider), "factory-status", "--json")
    if not status or status.get("schema") != "winvm-image-factory-status/v0" or status.get("state") != "complete":
        print("First-logon completion is not independently attested", file=sys.stderr)
        return 1
    path = attestation_path(identifier)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".first-logon-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as output:
            json.dump({
                "schema": "winvm-factory-first-logon-attestation/v0",
                "targetId": identifier,
                "completed": True,
                "observedAt": time.time(),
            }, output)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("first-logon completion attested for the exact candidate")
    return 0


def inspect(repo: Path, provider: Path, identifier: str) -> dict:
    stages: list[dict] = []
    identity = json_command(str(provider), "assert-target", "inspect", "--json")
    if not identity or identity.get("identity_pin") != "verified" or identity.get("role") != "candidate":
        stages.append(stage("identity", "blocked", "candidate_identity_unverified",
                            "bin/winvm", "pin-target", "candidate", "PRIVATE_NAME"))
        return {"schema": STAGE_SCHEMA, "provider": "libvirt-linux", "stages": stages}
    stages.append(stage("identity", "complete", "exact_candidate_pin_verified"))

    power_ok, power_text = command(str(provider), "status", timeout=10)
    power = power_text.strip() if power_ok else "unknown"
    media = json_command(str(provider), "factory-media-status")
    media_stage = media.get("stage") if media and media.get("schema") == "winvm-factory-media-status/v0" else None
    live_install = None
    if power == "started":
        live_install = json_command(str(provider), "factory-status", "--json")
    installed = (live_install is not None and
                 live_install.get("schema") == "winvm-image-factory-status/v0" and
                 live_install.get("state") == "complete")
    historical = attested(identifier)
    if installed and historical:
        stages.append(stage("first-logon", "complete", "guest_completion_attested"))
    elif installed:
        stages.append(stage("first-logon", "action_required",
                            "guest_completion_observed_not_recorded",
                            "bin/winvm", "factory-stages", "attest-first-logon"))
    elif live_install and live_install.get("state") in ("pending", "finalizing"):
        stages.append(stage("first-logon", "waiting", "guest_installation_in_progress",
                            "bin/winvm", "factory-status", "--json"))
    elif historical and power != "started":
        stages.append(stage("first-logon", "complete", "prior_exact_candidate_attestation"))
    else:
        stages.append(stage("first-logon", "blocked", "completion_not_observed",
                            "bin/winvm", "up" if power != "started" else "factory-status",
                            *([] if power != "started" else ["--json"])))

    ssh_ready = False
    if power == "started" and installed:
        ssh_ready, _ = command(str(provider), "ssh-exec", "exit 0", timeout=20)
    if ssh_ready:
        stages.append(stage("transport", "complete", "key_only_ssh_connected"))
    elif installed:
        stages.append(stage("transport", "action_required", "ssh_not_connected",
                            "bin/winvm", "trust-ssh-host-key"))
    else:
        stages.append(stage("transport", "blocked", "first_logon_not_ready"))

    if media_stage == "detached":
        stages.append(stage("media", "complete", "no_removable_factory_media"))
    elif media_stage in ("installer_and_seed", "seed_only"):
        if not historical or (power == "started" and not installed):
            stages.append(stage("media", "blocked", "first_logon_attestation_required"))
        elif power == "started":
            stages.append(stage("media", "action_required", "candidate_must_stop",
                                "bin/winvm", "shutdown"))
        else:
            action = ("factory-detach-installer" if media_stage == "installer_and_seed"
                      else "factory-detach-media")
            stages.append(stage("media", "action_required", media_stage,
                                "bin/winvm", action))
    else:
        stages.append(stage("media", "blocked", "media_shape_unverified"))

    credentials = json_command(str(repo / "scripts/credential.sh"), "status", "--json")
    if not credentials or credentials.get("schema") != "winvm-credential-status/v0":
        stages.append(stage("credential", "blocked", "secret_store_unavailable"))
    elif credentials.get("rotationPending"):
        stages.append(stage("credential", "blocked", "rotation_pending_requires_resolution"))
    elif credentials.get("loginPassword") != "stored":
        stages.append(stage("credential", "action_required", "login_password_missing",
                            "bin/winvm", "credential", "store", "PRIVATE_SECRET_FILE"))
    elif power != "started" or not ssh_ready:
        stages.append(stage("credential", "unverified", "password_stored_guest_unavailable",
                            *(["bin/winvm", "up"] if power != "started" else [])))
    else:
        valid, _ = command(str(repo / "bin/winvm"), "credential", "verify", timeout=80)
        stages.append(stage("credential", "complete" if valid else "blocked",
                            "stored_password_guest_verified" if valid else "credential_verification_failed"))

    if power != "started" or not ssh_ready:
        stages.append(stage("resident", "blocked", "guest_administration_unavailable"))
    else:
        doctor = json_command(str(repo / "bin/winvm"), "doctor", "--json",
                              timeout=100, allow_failure_json=True)
        doctor_valid = bool(doctor and doctor.get("schema") == "machine-control-doctor/v0")
        states = doctor.get("states", {}) if doctor_valid else {}
        resident_ready = all(states.get(name) == "ready" for name in
                             ("administration", "resident", "semantic", "capture", "input"))
        if not doctor_valid:
            stages.append(stage("resident", "blocked", "resident_doctor_unavailable",
                                "bin/winvm", "doctor", "--json"))
        elif resident_ready and states.get("desktop") == "unlocked":
            stages.append(stage("resident", "complete", "full_doctor_ready"))
        elif resident_ready and states.get("desktop") == "locked":
            stages.append(stage("resident", "action_required", "resident_ready_desktop_locked",
                                "bin/winvm", "login"))
        else:
            stages.append(stage("resident", "action_required", "resident_not_ready",
                                "bin/winvm", "post-update", "audit", "--json"))
    return {"schema": STAGE_SCHEMA, "provider": "libvirt-linux", "stages": stages}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("--json", "attest-first-logon"):
        print("Usage: winvm factory-stages --json|attest-first-logon", file=sys.stderr)
        return 2
    if os.environ.get("WINVM_PROVIDER") != "libvirt-linux":
        print("Factory stages currently require the Linux libvirt provider", file=sys.stderr)
        return 1
    identifier = os.environ.get("WINVM_EXPECTED_UTM_ID", "")
    if not UUID.fullmatch(identifier):
        print("Exact candidate identity is not pinned", file=sys.stderr)
        return 1
    repo = Path(os.environ["WINVM_REPO_DIR"])
    claim_id = os.environ.get("MACHINE_CONTROL_CLAIM_ID", "")
    if not claim_id or not command(
        str(repo / "bin/winvm"), "claim-check", "--claim-id", claim_id,
        "--json", timeout=10
    )[0]:
        print("An exclusive exact-candidate claim is required", file=sys.stderr)
        return 1
    provider = repo / "providers/libvirt-linux/provider.sh"
    if sys.argv[1] == "attest-first-logon":
        return attest_first_logon(provider, identifier)
    print(json.dumps(inspect(repo, provider, identifier), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
