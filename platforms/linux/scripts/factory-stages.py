#!/usr/bin/env python3
"""Read-only Ubuntu factory stage projection for libvirt and UTM."""

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


SCHEMA = "linuxvm-factory-stages/v0"
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/linuxvm"
PROVIDER = ROOT / "providers/libvirt-linux/provider.sh"


def call(*args: str, timeout: int = 30) -> tuple[bool, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return result.returncode == 0, result.stdout


def document(*args: str, timeout: int = 30) -> dict:
    ok, output = call(*args, timeout=timeout)
    if not ok:
        return {}
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def stage(name: str, state: str, evidence: str, *next_command: str) -> dict:
    return {"name": name, "state": state, "evidence": evidence,
            "nextCommand": list(next_command) if next_command else None}


def private_seed(path: Path, user: str, public_key: str, provider: str) -> bool:
    try:
        if not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            return False
    except OSError:
        return False
    if provider == "utm-macos":
        try:
            with path.open("rb") as image:
                image.seek(16 * 2048)
                descriptor = image.read(2048)
            if (descriptor[1:6] != b"CD001" or
                    descriptor[40:72].rstrip(b" \x00").upper() != b"CIDATA"):
                return False
        except OSError:
            return False
        ok, listing = call("bsdtar", "-tf", str(path))
        files = {line.removeprefix("./") for line in listing.splitlines()}
        files.discard(".")
        if not ok or {"user-data", "meta-data"} != files:
            return False
        ok, content = call("bsdtar", "-xOf", str(path), "user-data")
        meta_ok, metadata = call("bsdtar", "-xOf", str(path), "meta-data")
        if not meta_ok:
            return False
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            return False
        if meta.get("instance-id") != "machine-control-linux-" + user:
            return False
    else:
        ok, info = call("isoinfo", "-d", "-i", str(path))
        if not ok or "volume id: cidata" not in info.lower():
            return False
        ok, listing = call("isoinfo", "-f", "-i", str(path))
        if not ok or not {"/USER_DAT.;1", "/META_DAT.;1"}.issubset(
                set(listing.upper().splitlines())):
            return False
        ok, content = call("isoinfo", "-x", "/USER_DAT.;1", "-i", str(path))
    if not ok or not content.startswith("#cloud-config\n"):
        return False
    try:
        seed = json.loads(content.split("\n", 1)[1])
    except json.JSONDecodeError:
        return False
    users = seed.get("users")
    return (isinstance(users, list) and len(users) == 1
            and isinstance(users[0], dict)
            and users[0].get("name") == user
            and users[0].get("lock_passwd") is True
            and users[0].get("ssh_authorized_keys") == [public_key]
            and seed.get("ssh_pwauth") is False)


def utm_destination(name: str, factory_root: Path) -> tuple[bool, str]:
    if not name:
        return False, "candidate_name_missing"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}", name):
        return False, "candidate_name_invalid"
    required = ("qemu-img", "jq", "bsdtar", "hdiutil", "osascript")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return False, "mac_arm64_host_required"
    if any(not shutil.which(tool) for tool in required):
        return False, "utm_factory_tool_missing"
    utmctl = os.environ.get("LINUXVM_UTMCTL", "/Applications/UTM.app/Contents/MacOS/utmctl")
    if not os.access(utmctl, os.X_OK):
        return False, "utm_cli_unavailable"
    ok, listing = call(utmctl, "list", timeout=15)
    lines = listing.splitlines()
    if not ok or not lines or not lines[0].startswith("UUID ") or len(lines) == 1:
        return False, "utm_library_unverified"
    script_ok, count = call("osascript", "-e",
                            'tell application "UTM" to count virtual machines',
                            timeout=15)
    if not script_ok or count.strip() != str(len(lines) - 1):
        return False, "utm_scripting_unavailable"
    for line in lines[1:]:
        match = re.fullmatch(r"[0-9A-Fa-f-]{36}\s+\S+\s+(.+)", line)
        if not match:
            return False, "utm_inventory_unverified"
        if match.group(1) == name:
            return False, "candidate_already_registered"
    if ((factory_root / f"{name}-system.qcow2").exists()
            or (factory_root / "export" / f"{name}.utm").exists()):
        return False, "factory_staging_exists"
    return True, "utm_host_and_destination_verified"


def preflight(args: argparse.Namespace, provider: str) -> dict:
    stages = []
    image = args.cloud_image or ""
    ok, _ = call(str(ROOT / "scripts/image-factory.sh"),
                 "validate-cloud-image", image) if image else (False, "")
    stages.append(stage("cloud-image", "complete" if ok else "action_required",
                        "qcow2_shape_verified" if ok else "cloud_image_unavailable_or_invalid"))
    user = args.user or ""
    key = args.public_key or ""
    try:
        key_value = Path(key).read_text().strip() if key else ""
    except OSError:
        key_value = ""
    inputs = bool(re.fullmatch(r"[a-z_][a-z0-9_-]{0,30}", user)
                  and re.fullmatch(r"(?:ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa) [A-Za-z0-9+/=]+(?: .*)?", key_value))
    stages.append(stage("seed-inputs", "complete" if inputs else "action_required",
                        "key_only_seed_inputs_present" if inputs else "seed_inputs_missing"))
    factory_root = Path(os.environ.get("LINUXVM_FACTORY_LOCAL_ROOT",
                                       str(ROOT / ".factory.local")))
    seed = factory_root / "linuxvm-seed.iso"
    if seed.exists():
        valid_seed = inputs and private_seed(seed, user, key_value, provider)
        stages.append(stage("seed-media", "complete" if valid_seed else "blocked",
                            "private_cidata_shape_verified" if valid_seed else
                            "private_cidata_seed_invalid"))
    elif inputs:
        stages.append(stage("seed-media", "action_required", "private_cidata_seed_missing",
                            "scripts/image-factory.sh", "render-seed",
                            "APPLIANCE_USER", "CONTROLLER_PUBLIC_KEY"))
    else:
        stages.append(stage("seed-media", "blocked", "seed_inputs_required"))
    if provider == "utm-macos":
        ready, reason = utm_destination(args.name or "", factory_root)
    else:
        name = args.name or os.environ.get("LINUXVM_LIBVIRT_DOMAIN_NAME", "")
        destination = document(str(PROVIDER), "factory-preflight", name) if name else {}
        ready = (destination.get("schema") == "machine-control-libvirt-factory-preflight/v0"
                 and destination.get("kind") == "linux" and destination.get("ready") is True)
        reason = destination.get("reason") if destination else "candidate_name_missing"
        if not isinstance(reason, str) or not re.fullmatch(r"[a-z_]+", reason):
            reason = "destination_unavailable"
        if ready:
            reason = "kvm_pool_and_destination_verified"
    stages.append(stage("destination", "complete" if ready else
                        "action_required" if reason == "candidate_name_missing" else "blocked",
                        reason))
    prepared = all(item["state"] == "complete" for item in stages)
    stages.append(stage("create", "action_required" if prepared else "blocked",
                        "factory_inputs_ready" if prepared else "preflight_incomplete",
                        *("bin/linuxvm", "factory-create", "PRIVATE_NAME",
                          "PRIVATE_CLOUD_IMAGE", ".factory.local/linuxvm-seed.iso")
                        if prepared else ()))
    return {"schema": SCHEMA, "provider": provider, "phase": "precreation",
            "stages": stages}


def candidate() -> dict:
    stages = []
    identity = document(str(CLI), "candidate-status", "--json")
    valid = (identity.get("schema") == "machine-control-candidate-assertion/v0"
             and identity.get("identityPin") == "verified"
             and identity.get("role") == "candidate")
    stages.append(stage("identity", "complete" if valid else "blocked",
                        "exact_candidate_pin_verified" if valid else "exact_candidate_required"))
    if not valid:
        return {"schema": SCHEMA, "provider": "libvirt-linux", "stages": stages}
    power = identity.get("powerState")
    if power == "off":
        stages.append(stage("power", "action_required", "candidate_off",
                            "bin/linuxvm", "up"))
    elif power == "running":
        stages.append(stage("power", "complete", "candidate_running"))
    else:
        stages.append(stage("power", "blocked", "candidate_power_unknown"))
    agent, _ = call(str(PROVIDER), "factory-agent-ready", timeout=10) if power == "running" else (False, "")
    stages.append(stage("guest-agent", "complete" if agent else "waiting",
                        "qga_responsive" if agent else "qga_not_yet_responsive"))
    media = document(str(PROVIDER), "factory-media-status")
    shape = media.get("stage") if media.get("schema") == "linuxvm-factory-media-status/v0" else None
    cloud = {}
    boot_id = ""
    if agent:
        cloud = document(str(CLI), "exec", "--", "cloud-init", "status", "--format=json")
        ok, boot_id = call(str(CLI), "exec", "--", "cat", "/proc/sys/kernel/random/boot_id")
        if not ok or not re.fullmatch(r"[0-9a-f-]{36}", boot_id.strip()):
            boot_id = ""
    prior_complete = False
    if agent and cloud.get("status") == "disabled" and shape == "detached":
        ok, instance_id = call(str(CLI), "exec", "--", "cat",
                               "/var/lib/cloud/data/instance-id")
        finished, _ = call(str(CLI), "exec", "--", "test", "-f",
                           "/var/lib/cloud/instance/boot-finished")
        prior_complete = (ok and finished and instance_id.strip().startswith(
            "machine-control-linux-"))
    cloud_done = bool(boot_id) and (cloud.get("status") == "done" or prior_complete)
    cloud_error = cloud.get("status") == "error"
    stages.append(stage("cloud-init", "complete" if cloud_done else
                        "blocked" if cloud_error else "waiting",
                        "prior_nocloud_completion_on_disk" if prior_complete else
                        "completed_in_observed_boot" if cloud_done else
                        "cloud_init_error" if cloud_error else "cloud_init_pending"))
    if boot_id:
        stages[-1]["bootId"] = boot_id.strip()
    doctor = document(str(CLI), "doctor", "--json") if agent and cloud_done else {}
    resident = doctor.get("ready") is True
    stages.append(stage("resident", "complete" if resident else
                        "action_required" if cloud_done else "blocked",
                        "full_doctor_ready" if resident else
                        "bootstrap_required" if cloud_done else "cloud_init_required",
                        *("bin/linuxvm", "bootstrap", "--profile", "development")
                        if cloud_done and not resident else ()))
    if shape == "detached":
        stages.append(stage("media", "complete", "exact_seed_detached"))
    elif shape == "seed_only":
        stages.append(stage("media", "action_required" if power == "off" else "waiting",
                            "seed_attached", *("bin/linuxvm", "factory-detach-media")
                            if power == "off" else ()))
    else:
        stages.append(stage("media", "blocked", "factory_media_unverified"))
    stages.append(stage("final-stop", "complete" if power == "off" and shape == "detached"
                        else "action_required" if resident and shape == "detached" else "blocked",
                        "source_stopped" if power == "off" and shape == "detached"
                        else "clean_shutdown_required" if resident and shape == "detached"
                        else "resident_and_detached_media_required",
                        *("bin/linuxvm", "shutdown") if resident and shape == "detached" and power == "running" else ()))
    return {"schema": SCHEMA, "provider": "libvirt-linux", "stages": stages}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    pre = sub.add_parser("preflight")
    pre.add_argument("--cloud-image")
    pre.add_argument("--public-key")
    pre.add_argument("--user")
    pre.add_argument("--name")
    pre.add_argument("--json", action="store_true")
    current = sub.add_parser("inspect")
    current.add_argument("--json", action="store_true")
    args = parser.parse_args()
    provider = os.environ.get("LINUXVM_PROVIDER")
    if provider not in ("libvirt-linux", "utm-macos"):
        parser.error("factory stages require libvirt-linux or utm-macos")
    if args.command != "preflight" and provider != "libvirt-linux":
        parser.error("claimed UTM candidate stages are not available yet")
    report = preflight(args, provider) if args.command == "preflight" else candidate()
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
