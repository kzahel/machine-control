#!/usr/bin/env python3
"""Read-only native KVM Ubuntu factory stage projection."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
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


def private_seed(path: Path, user: str, public_key: str) -> bool:
    try:
        if not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            return False
    except OSError:
        return False
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
            and users[0].get("name") == user
            and users[0].get("lock_passwd") is True
            and users[0].get("ssh_authorized_keys") == [public_key]
            and seed.get("ssh_pwauth") is False)


def preflight(args: argparse.Namespace) -> dict:
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
    if inputs and private_seed(seed, user, key_value):
        stages.append(stage("seed-media", "complete", "private_cidata_shape_verified"))
    else:
        stages.append(stage("seed-media", "action_required" if inputs else "blocked",
                            "private_cidata_seed_missing_or_invalid",
                            *("scripts/image-factory.sh", "render-seed",
                              "APPLIANCE_USER", "CONTROLLER_PUBLIC_KEY") if inputs else ()))
    name = args.name or os.environ.get("LINUXVM_LIBVIRT_DOMAIN_NAME", "")
    destination = document(str(PROVIDER), "factory-preflight", name) if name else {}
    ready = (destination.get("schema") == "machine-control-libvirt-factory-preflight/v0"
             and destination.get("kind") == "linux" and destination.get("ready") is True)
    reason = destination.get("reason") if destination else "candidate_name_missing"
    if not isinstance(reason, str) or not re.fullmatch(r"[a-z_]+", reason):
        reason = "destination_unavailable"
    stages.append(stage("destination", "complete" if ready else "blocked",
                        "kvm_pool_and_destination_verified" if ready else reason))
    prepared = all(item["state"] == "complete" for item in stages)
    stages.append(stage("create", "action_required" if prepared else "blocked",
                        "factory_inputs_ready" if prepared else "preflight_incomplete",
                        *("bin/linuxvm", "factory-create", "PRIVATE_NAME",
                          "PRIVATE_CLOUD_IMAGE", ".factory.local/linuxvm-seed.iso")
                        if prepared else ()))
    return {"schema": SCHEMA, "provider": "libvirt-linux", "phase": "precreation",
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
    cloud = {}
    boot_id = ""
    if agent:
        cloud = document(str(CLI), "exec", "--", "cloud-init", "status", "--format=json")
        ok, boot_id = call(str(CLI), "exec", "--", "cat", "/proc/sys/kernel/random/boot_id")
        if not ok or not re.fullmatch(r"[0-9a-f-]{36}", boot_id.strip()):
            boot_id = ""
    cloud_done = cloud.get("status") == "done" and bool(boot_id)
    cloud_error = cloud.get("status") == "error"
    stages.append(stage("cloud-init", "complete" if cloud_done else
                        "blocked" if cloud_error else "waiting",
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
    media = document(str(PROVIDER), "factory-media-status")
    shape = media.get("stage") if media.get("schema") == "linuxvm-factory-media-status/v0" else None
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
    if os.environ.get("LINUXVM_PROVIDER") != "libvirt-linux":
        parser.error("native Linux factory stages require libvirt-linux")
    report = preflight(args) if args.command == "preflight" else candidate()
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
