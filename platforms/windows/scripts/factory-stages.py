#!/usr/bin/env python3
"""Read-only, evidence-based stages for a Linux Windows factory candidate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
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


def readable_file(value: str, *, minimum: int = 1) -> bool:
    if not value:
        return False
    try:
        path = Path(value)
        return (path.is_file() and os.access(path, os.R_OK)
                and path.stat().st_size >= minimum)
    except OSError:
        return False


def private_file(value: str) -> bool:
    if not readable_file(value):
        return False
    try:
        return stat.S_IMODE(Path(value).stat().st_mode) == 0o600
    except OSError:
        return False


def seed_media_ready(value: str) -> bool:
    if not private_file(value):
        return False
    volume_ok, volume = command("isoinfo", "-d", "-i", value, timeout=20)
    files_ok, files = command("isoinfo", "-f", "-i", value, timeout=20)
    listed = set(files.upper().splitlines()) if files_ok else set()
    return (volume_ok and "Volume id: WINVM_SEED" in volume and
            {"/AUTOUNATTEND.XML;1", "/BOOTSTRAP_FIRST_LOGON.PS1;1",
             "/BOOTSTRAP_OPENSSH.PS1;1", "/CONTROLLER.PUB;1",
             "/VIRTIO_WIN_GUEST_TOOLS.EXE;1"}.issubset(listed))


def preflight(repo: Path, provider: Path, options: argparse.Namespace) -> dict:
    """Inspect only host media and the unused libvirt destination."""
    stages: list[dict] = []
    factory_root = Path(os.environ.get(
        "WINVM_FACTORY_LOCAL_ROOT", str(repo / ".factory.local"),
    ))
    source = options.source_iso or ""
    if readable_file(source, minimum=1024 * 1024 * 1024):
        valid, _ = command(str(repo / "scripts/image-factory.sh"),
                           "validate-media", source, timeout=20)
        stages.append(stage("source-media", "complete" if valid else "blocked",
                            "source_iso_plausible" if valid else "source_iso_invalid"))
    else:
        stages.append(stage("source-media", "action_required",
                            "source_iso_missing_or_unreadable"))

    image_index = None
    if stages[0]["state"] == "complete":
        catalog = json_command(str(repo / "scripts/image-catalog.py"), source,
                               timeout=240)
        images = catalog.get("images") if catalog and catalog.get("schema") == "winvm-image-catalog/v0" else None
        pro = [item.get("index") for item in images or []
               if isinstance(item, dict) and item.get("name") == "Windows 11 Pro"
               and item.get("flags") == "Professional"
               and isinstance(item.get("index"), int)]
        if len(pro) == 1:
            image_index = pro[0]
            item = stage("image-index", "complete", "unique_windows_11_pro_catalog_entry")
            item["imageIndex"] = image_index
            stages.append(item)
        else:
            stages.append(stage("image-index", "blocked",
                                "windows_11_pro_catalog_unverified"))
    else:
        stages.append(stage("image-index", "blocked", "source_iso_required"))

    prepared = factory_root / "windows-install-noprompt.iso"
    if prepared.exists():
        verification = (json_command(str(repo / "scripts/verify-prepared-media.py"),
                                     source, str(prepared), timeout=120)
                        if stages[0]["state"] == "complete" else None)
        if verification and verification.get("schema") == "winvm-prepared-media-verification/v0" and verification.get("ready") is True:
            stages.append(stage("prepared-media", "complete",
                                "source_identical_outside_efi_and_no_prompt_loader_exact"))
        else:
            reason = verification.get("reason", "prepared_media_unverified") if verification else "prepared_media_unverified"
            stages.append(stage("prepared-media", "blocked", reason))
    elif stages[0]["state"] == "complete":
        stages.append(stage("prepared-media", "action_required",
                            "prepared_iso_missing", "scripts/image-factory.sh",
                            "prepare-install-media", "PRIVATE_WINDOWS_ISO"))
    else:
        stages.append(stage("prepared-media", "blocked", "source_iso_required"))

    public_key = options.public_key or ""
    tools = options.guest_tools_iso or ""
    secret = options.secret_file or ""
    user = options.user or ""
    inputs_valid = (readable_file(public_key) and
                    readable_file(tools, minimum=1024 * 1024) and
                    private_file(secret) and
                    re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,31}", user) and
                    image_index is not None)
    stages.append(stage("seed-inputs", "complete" if inputs_valid else "action_required",
                        "seed_inputs_present" if inputs_valid else
                        "seed_inputs_missing_or_invalid"))

    seed = factory_root / "winvm-seed.iso"
    if seed.exists():
        if seed_media_ready(str(seed)):
            stages.append(stage("seed-media", "complete", "private_seed_shape_verified"))
        else:
            stages.append(stage("seed-media", "blocked", "seed_media_invalid"))
    elif inputs_valid:
        stages.append(stage("seed-media", "action_required", "seed_iso_missing",
                            "scripts/image-factory.sh", "render-seed", "amd64",
                            "APPLIANCE_USER", str(image_index), "windows-11-pro",
                            "PRIVATE_SECRET_FILE", "CONTROLLER_PUBLIC_KEY",
                            "PRIVATE_VIRTIO_WIN_ISO"))
    else:
        stages.append(stage("seed-media", "blocked", "seed_inputs_required"))

    name = options.name or os.environ.get("WINVM_LIBVIRT_DOMAIN_NAME", "")
    if not name:
        stages.append(stage("destination", "action_required", "candidate_name_missing"))
    else:
        result = json_command(str(provider), "factory-preflight", name, timeout=30)
        if result and result.get("schema") == "machine-control-libvirt-factory-preflight/v0" and result.get("ready") is True:
            stages.append(stage("destination", "complete",
                                "kvm_pool_and_destination_verified"))
        else:
            reason = result.get("reason", "unavailable") if result else "unavailable"
            if not isinstance(reason, str) or not re.fullmatch(r"[a-z_]+", reason):
                reason = "unavailable"
            stages.append(stage("destination", "blocked", reason))

    if all(item["state"] == "complete" for item in stages):
        stages.append(stage("create", "action_required", "media_and_destination_ready",
                            "bin/winvm", "factory-create", "PRIVATE_NAME",
                            ".factory.local/windows-install-noprompt.iso",
                            ".factory.local/winvm-seed.iso"))
    else:
        stages.append(stage("create", "blocked", "preflight_incomplete"))
    return {"schema": STAGE_SCHEMA, "provider": "libvirt-linux",
            "phase": "precreation", "stages": stages}


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
    agent_ready = power == "started" and command(
        str(provider), "factory-agent-ready", timeout=10,
    )[0]
    if agent_ready:
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
    elif power == "started" and live_install is None:
        stages.append(stage("first-logon", "waiting",
                            "guest_agent_or_first_logon_not_yet_observed",
                            "bin/winvm", "factory-status", "--json"))
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
        stages.append(stage("bootstrap", "blocked", "guest_administration_unavailable"))
        stages.append(stage("resident", "blocked", "guest_administration_unavailable"))
        stages.append(stage("maintenance", "unverified", "running_guest_required"))
    else:
        doctor = json_command(str(repo / "bin/winvm"), "doctor", "--json",
                              timeout=100, allow_failure_json=True)
        doctor_valid = bool(doctor and doctor.get("schema") == "machine-control-doctor/v0")
        states = doctor.get("states", {}) if doctor_valid else {}
        resident_ready = all(states.get(name) == "ready" for name in
                             ("administration", "resident", "semantic", "capture", "input"))
        if resident_ready:
            stages.append(stage("bootstrap", "complete", "resident_components_ready"))
        elif media_stage != "detached":
            stages.append(stage("bootstrap", "blocked", "factory_media_detachment_required"))
        elif stages[-1]["name"] == "credential" and stages[-1]["state"] != "complete":
            stages.append(stage("bootstrap", "blocked", "credential_verification_required"))
        elif not doctor_valid:
            stages.append(stage("bootstrap", "blocked", "doctor_result_unavailable"))
        else:
            support_ok, support_text = command(
                str(provider), "ssh-exec", "if (Test-Path -LiteralPath "
                "'C:\\ProgramData\\MachineControl\\runtime\\support\\post-update.ps1') "
                "{ 'present' } else { 'absent' }", timeout=30,
            )
            support_state = ([support_text.strip().splitlines()[-1].strip()]
                             if support_ok and support_text.strip() else [])
            if support_state == ["present"]:
                stages.append(stage("bootstrap", "action_required",
                                    "installed_components_need_repair",
                                    "bin/winvm", "post-update", "repair", "--json"))
            elif support_state == ["absent"]:
                stages.append(stage("bootstrap", "action_required",
                                    "resident_installation_required",
                                    "bin/winvm", "bootstrap", "--profile",
                                    "development"))
            else:
                stages.append(stage("bootstrap", "blocked",
                                    "installed_support_state_unverified"))
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
        if not resident_ready:
            stages.append(stage("maintenance", "blocked", "resident_readiness_required"))
        else:
            audit = json_command(str(repo / "bin/winvm"), "post-update", "audit",
                                 "--json", timeout=100, allow_failure_json=True)
            if not audit or audit.get("schema") != "machine-control-windows-post-update-orchestration/v0":
                stages.append(stage("maintenance", "blocked", "post_update_audit_unavailable"))
            elif audit.get("healthy") is True:
                stages.append(stage("maintenance", "complete", "healthy_post_update_audit"))
            elif any(item.get("id") == "pending_reboot" and item.get("healthy") is False
                     for item in (audit.get("post_update") or {}).get("checks", [])
                     if isinstance(item, dict)):
                stages.append(stage("maintenance", "action_required", "pending_reboot",
                                    "bin/winvm", "post-update", "repair", "--reboot", "--json"))
            else:
                stages.append(stage("maintenance", "action_required",
                                    "installed_maintenance_unhealthy", "bin/winvm",
                                    "post-update", "repair", "--json"))
    return {"schema": STAGE_SCHEMA, "provider": "libvirt-linux", "stages": stages}


def main() -> int:
    if os.environ.get("WINVM_PROVIDER") != "libvirt-linux":
        print("Factory stages currently require the Linux libvirt provider", file=sys.stderr)
        return 1
    repo = Path(os.environ["WINVM_REPO_DIR"])
    provider = repo / "providers/libvirt-linux/provider.sh"
    if len(sys.argv) >= 2 and sys.argv[1] == "preflight":
        parser = argparse.ArgumentParser(prog="winvm factory-stages preflight")
        parser.add_argument("--json", action="store_true", required=True)
        parser.add_argument("--source-iso")
        parser.add_argument("--guest-tools-iso")
        parser.add_argument("--secret-file")
        parser.add_argument("--public-key")
        parser.add_argument("--user")
        parser.add_argument("--name")
        options = parser.parse_args(sys.argv[2:])
        print(json.dumps(preflight(repo, provider, options), sort_keys=True))
        return 0
    if len(sys.argv) != 2 or sys.argv[1] not in ("--json", "attest-first-logon"):
        print("Usage: winvm factory-stages preflight --json [OPTIONS] | --json | attest-first-logon", file=sys.stderr)
        return 2
    identifier = os.environ.get("WINVM_EXPECTED_UTM_ID", "")
    if not UUID.fullmatch(identifier):
        print("Exact candidate identity is not pinned", file=sys.stderr)
        return 1
    claim_id = os.environ.get("MACHINE_CONTROL_CLAIM_ID", "")
    if not claim_id or not command(
        str(repo / "bin/winvm"), "claim-check", "--claim-id", claim_id,
        "--json", timeout=10
    )[0]:
        print("An exclusive exact-candidate claim is required", file=sys.stderr)
        return 1
    if sys.argv[1] == "attest-first-logon":
        return attest_first_logon(provider, identifier)
    print(json.dumps(inspect(repo, provider, identifier), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
