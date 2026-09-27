#!/usr/bin/env python3
"""Read-only, evidence-based stages for a Linux Windows factory candidate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
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


def mac_seed_media_ready(value: str) -> bool:
    if not private_file(value):
        return False
    try:
        with open(value, "rb") as media:
            media.seek(16 * 2048)
            descriptor = media.read(2048)
        if (len(descriptor) != 2048 or descriptor[1:6] != b"CD001" or
                descriptor[40:72].decode("ascii").rstrip("\x00 ") != "WINVM_SEED"):
            return False
    except (OSError, UnicodeDecodeError):
        return False
    listed, names = command("bsdtar", "-tf", value, timeout=30)
    normalized = {name.lstrip("./").upper().split(";")[0]
                  for name in names.splitlines()} if listed else set()
    essential = {"AUTOUNATTEND.XML", "BOOTSTRAP-FIRST-LOGON.PS1",
                 "BOOTSTRAP-OPENSSH.PS1", "CONTROLLER.PUB", "STARTUP.NSH"}
    installer = any(name == "VIRTIO-WIN-GUEST-TOOLS.EXE" or
                    re.fullmatch(r"UTM-GUEST-TOOLS-[A-Z0-9._-]+\.EXE", name)
                    for name in normalized)
    return essential.issubset(normalized) and installer


def mac_boot_media_ready(value: str, expected_script: Path) -> bool:
    if not private_file(value):
        return False
    try:
        media = Path(value).read_bytes()
        expected = expected_script.read_bytes()
        if (len(media) < 1024 * 1024 or media[510:512] != b"\x55\xaa" or
                media[54:62] != b"FAT12   "):
            return False
        sector = int.from_bytes(media[11:13], "little")
        cluster_sectors = media[13]
        reserved = int.from_bytes(media[14:16], "little")
        fats = media[16]
        root_entries = int.from_bytes(media[17:19], "little")
        fat_sectors = int.from_bytes(media[22:24], "little")
        if (sector != 512 or not cluster_sectors or not reserved or
                fats != 2 or not root_entries or not fat_sectors):
            return False
        fat = media[reserved * sector:(reserved + fat_sectors) * sector]
        root_start = (reserved + fats * fat_sectors) * sector
        root_sectors = (root_entries * 32 + sector - 1) // sector
        data_start = root_start + root_sectors * sector
        root = media[root_start:root_start + root_entries * 32]
        if len(root) != root_entries * 32:
            return False
        label = False
        script = None
        for index in range(0, len(root), 32):
            entry = root[index:index + 32]
            if entry[0] in (0, 0xe5):
                continue
            if entry[11] & 0x08 and entry[:11].rstrip() == b"WINVM_BOOT":
                label = True
            if entry[:11] == b"STARTUP NSH" and entry[11] == 0x20:
                script = entry
        if not label or script is None:
            return False
        size = int.from_bytes(script[28:32], "little")
        if size != len(expected) or not size:
            return False
        cluster = int.from_bytes(script[26:28], "little")
        content = bytearray()
        seen: set[int] = set()
        while len(content) < size:
            if cluster < 2 or cluster in seen or cluster >= 0xff8:
                return False
            seen.add(cluster)
            offset = data_start + (cluster - 2) * cluster_sectors * sector
            content.extend(media[offset:offset + cluster_sectors * sector])
            fat_offset = cluster + cluster // 2
            if fat_offset + 1 >= len(fat):
                return False
            pair = fat[fat_offset] | (fat[fat_offset + 1] << 8)
            cluster = (pair >> 4) & 0xfff if cluster & 1 else pair & 0xfff
        return content[:size] == expected and cluster >= 0xff8
    except OSError:
        return False


def utm_destination(name: str, factory_root: Path) -> tuple[bool, str]:
    if not name:
        return False, "candidate_name_missing"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}", name):
        return False, "candidate_name_invalid"
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return False, "mac_arm64_host_required"
    if any(not shutil.which(tool) for tool in
           ("jq", "bsdtar", "hdiutil", "osascript", "wimlib-imagex")):
        return False, "utm_factory_tool_missing"
    utmctl = os.environ.get("WINVM_UTMCTL", "/Applications/UTM.app/Contents/MacOS/utmctl")
    if not os.access(utmctl, os.X_OK):
        return False, "utm_cli_unavailable"
    listed, inventory = command(utmctl, "list", timeout=15)
    lines = inventory.splitlines()
    if not listed or not lines or not lines[0].startswith("UUID "):
        return False, "utm_library_unverified"
    scripted, count = command("osascript", "-e",
                              'tell application "UTM" to count virtual machines',
                              timeout=15)
    if not scripted or count.strip() != str(len(lines) - 1):
        return False, "utm_scripting_unavailable"
    for line in lines[1:]:
        match = re.fullmatch(r"[0-9A-Fa-f-]{36}\s+\S+\s+(.+)", line)
        if not match:
            return False, "utm_inventory_unverified"
        if match.group(1) == name:
            return False, "candidate_already_registered"
    if (factory_root / "export" / f"{name}.utm").exists():
        return False, "factory_staging_exists"
    return True, "utm_host_and_destination_verified"


def preflight(repo: Path, provider: Path, options: argparse.Namespace,
              provider_name: str = "libvirt-linux") -> dict:
    """Inspect only host media and the unused provider destination."""
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
        ready = (mac_seed_media_ready(str(seed)) if provider_name == "utm-macos"
                 else seed_media_ready(str(seed)))
        if ready:
            stages.append(stage("seed-media", "complete", "private_seed_shape_verified"))
        else:
            stages.append(stage("seed-media", "blocked", "seed_media_invalid"))
    elif inputs_valid:
        stages.append(stage("seed-media", "action_required", "seed_iso_missing",
                            "scripts/image-factory.sh", "render-seed",
                            "arm64" if provider_name == "utm-macos" else "amd64",
                            "APPLIANCE_USER", str(image_index), "windows-11-pro",
                            "PRIVATE_SECRET_FILE", "CONTROLLER_PUBLIC_KEY",
                            "PRIVATE_UTM_GUEST_TOOLS_ISO" if
                            provider_name == "utm-macos" else
                            "PRIVATE_VIRTIO_WIN_ISO"))
    else:
        stages.append(stage("seed-media", "blocked", "seed_inputs_required"))

    if provider_name == "utm-macos":
        boot = factory_root / "winvm-boot.img"
        if boot.exists():
            ready = mac_boot_media_ready(
                str(boot), repo / "guests/windows/image-factory/startup.nsh")
            stages.append(stage("boot-media", "complete" if ready else "blocked",
                                "private_fat_startup_verified" if ready else
                                "boot_image_invalid"))
        elif inputs_valid:
            stages.append(stage("boot-media", "action_required",
                                "boot_image_missing", "scripts/image-factory.sh",
                                "render-seed", "arm64", "APPLIANCE_USER",
                                str(image_index), "windows-11-pro",
                                "PRIVATE_SECRET_FILE", "CONTROLLER_PUBLIC_KEY",
                                "PRIVATE_UTM_GUEST_TOOLS_ISO"))
        else:
            stages.append(stage("boot-media", "blocked", "seed_inputs_required"))

    name = options.name or (os.environ.get("WINVM_LIBVIRT_DOMAIN_NAME", "")
                            if provider_name == "libvirt-linux" else "")
    if provider_name == "utm-macos":
        ready, reason = utm_destination(name, factory_root)
        stages.append(stage("destination", "complete" if ready else
                            "action_required" if reason == "candidate_name_missing"
                            else "blocked", reason))
    elif not name:
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
                            ".factory.local/winvm-seed.iso",
                            *([".factory.local/winvm-boot.img"]
                              if provider_name == "utm-macos" else [])))
    else:
        stages.append(stage("create", "blocked", "preflight_incomplete"))
    return {"schema": STAGE_SCHEMA, "provider": provider_name,
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


def inspect(repo: Path, provider: Path, identifier: str,
            provider_name: str = "libvirt-linux") -> dict:
    stages: list[dict] = []
    identity = json_command(str(provider), "assert-target", "inspect", "--json")
    if not identity or identity.get("identity_pin") != "verified" or identity.get("role") != "candidate":
        stages.append(stage("identity", "blocked", "candidate_identity_unverified",
                            "bin/winvm", "pin-target", "candidate", "PRIVATE_NAME"))
        return {"schema": STAGE_SCHEMA, "provider": provider_name, "stages": stages}
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
    return {"schema": STAGE_SCHEMA, "provider": provider_name, "stages": stages}


def main() -> int:
    provider_name = os.environ.get("WINVM_PROVIDER")
    if provider_name not in ("libvirt-linux", "utm-macos"):
        print("Factory stages require Linux libvirt or Mac UTM", file=sys.stderr)
        return 1
    repo = Path(os.environ["WINVM_REPO_DIR"])
    provider = repo / f"providers/{provider_name}/provider.sh"
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
        print(json.dumps(preflight(repo, provider, options, provider_name),
                         sort_keys=True))
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
    print(json.dumps(inspect(repo, provider, identifier, provider_name),
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
