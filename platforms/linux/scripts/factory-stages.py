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
import signal
import stat
import subprocess
import tempfile
import time


SCHEMA = "linuxvm-factory-stages/v0"
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/linuxvm"
PROVIDER = ROOT / "providers/libvirt-linux/provider.sh"
UTM_PROVIDER = ROOT / "providers/utm-macos/provider.sh"
ATTESTATION_MAX_AGE = 24 * 60 * 60


def call(*args: str, timeout: int = 30) -> tuple[bool, str]:
    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True,
                                   start_new_session=True)
    except OSError:
        return False, ""
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        return False, ""
    return process.returncode == 0, output


def document(*args: str, timeout: int = 30,
             allow_failure_json: bool = False) -> dict:
    ok, output = call(*args, timeout=timeout)
    if not ok and not allow_failure_json:
        return {}
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def stage(name: str, state: str, evidence: str, *next_command: str) -> dict:
    return {"name": name, "state": state, "evidence": evidence,
            "nextCommand": list(next_command) if next_command else None}


def credential_stage(power: str) -> dict:
    observation = document(str(CLI), "credential", "status", "--json",
                           allow_failure_json=True)
    ready = (observation.get("schema") == "linuxvm-credential-handoff/v0"
             and observation.get("ready") is True
             and (observation.get("profile"), observation.get("evidence")) in (
                 ("password", "guest_password_hash_verified"),
                 ("password-free", "explicit_locked_password_profile_verified")))
    return stage("credential-handoff", "complete" if ready else "blocked",
                 observation["evidence"] if ready else "credential_handoff_required",
                 *("bin/linuxvm", "credential", "verify", "--json")
                 if not ready and power == "running" else ())


def promotion_stage(stages: list[dict]) -> dict:
    complete = all(next(item for item in stages if item["name"] == name)["state"]
                   == "complete" for name in ("final-stop", "credential-handoff"))
    return stage("promotion", "complete" if complete else "blocked",
                 "stopped_source_and_credential_verified" if complete else
                 "stopped_source_and_credential_required")


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
    stages.append(credential_stage(power))
    stages.append(promotion_stage(stages))
    return {"schema": SCHEMA, "provider": "libvirt-linux", "stages": stages}


def utm_exec(*arguments: str, timeout: int = 20) -> tuple[bool, str]:
    utmctl = os.environ.get("LINUXVM_UTMCTL", "/Applications/UTM.app/Contents/MacOS/utmctl")
    name = os.environ.get("LINUXVM_UTM_NAME", "")
    if not name:
        return False, ""
    return call(utmctl, "exec", name, "--cmd", *arguments, timeout=timeout)


def cloud_observation() -> tuple[str, str, bool]:
    utmctl = os.environ.get("LINUXVM_UTMCTL", "/Applications/UTM.app/Contents/MacOS/utmctl")
    name = os.environ.get("LINUXVM_UTM_NAME", "")
    cloud = document(utmctl, "exec", name, "--cmd", "/usr/bin/cloud-init",
                     "status", "--format=json", timeout=20,
                     allow_failure_json=True)
    status = cloud.get("status", "")
    if not status:
        # UTM can return before cloud-init's Python process emits stdout.
        # Its completed state is also recorded in read-only runtime files.
        runtime = document(utmctl, "exec", name, "--cmd", "/usr/bin/cat",
                           "/run/cloud-init/status.json", timeout=20).get("v1", {})
        result = document(utmctl, "exec", name, "--cmd", "/usr/bin/cat",
                          "/run/cloud-init/result.json", timeout=20).get("v1", {})
        if not isinstance(runtime, dict):
            runtime = {}
        if not isinstance(result, dict):
            result = {}
        phases = ("init-local", "init", "modules-config", "modules-final")
        records = [runtime.get(phase) for phase in phases]
        if result.get("errors") or any(isinstance(record, dict) and
                                       record.get("errors") for record in records):
            status = "error"
        elif (isinstance(result.get("datasource"), str)
              and "DataSourceNoCloud" in result["datasource"]
              and result.get("errors") == []
              and all(isinstance(record, dict) and isinstance(
                  record.get("finished"), (int, float)) for record in records)):
            status = "done"
        elif utm_exec("/usr/bin/test", "-f", "/run/cloud-init/disabled")[0]:
            status = "disabled"
    ok, boot_id = utm_exec("/usr/bin/cat", "/proc/sys/kernel/random/boot_id")
    if not ok or not re.fullmatch(r"[0-9a-f-]{36}", boot_id.strip()):
        boot_id = ""
    ok, instance_id = utm_exec("/usr/bin/cat", "/var/lib/cloud/data/instance-id")
    finished, _ = utm_exec("/usr/bin/test", "-f",
                           "/var/lib/cloud/instance/boot-finished")
    matching = bool(ok and finished and instance_id.strip().startswith(
        "machine-control-linux-"))
    return status, boot_id.strip(), matching


def attestation_path(identifier: str) -> Path:
    base = Path(os.environ.get("LINUXVM_FACTORY_ATTESTATION_DIR",
                            str(Path.home() / ".local/state/machine-control/linux-factory")))
    return base / f"{identifier.lower()}.json"


def attested(identifier: str) -> bool:
    try:
        record = json.loads(attestation_path(identifier).read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(record, dict):
        return False
    observed = record.get("observedAt")
    if type(observed) not in (int, float):
        return False
    age = time.time() - observed
    return (record.get("schema") == "linuxvm-cloud-init-attestation/v0"
            and record.get("targetId") == identifier.lower()
            and 0 <= age <= ATTESTATION_MAX_AGE
            and isinstance(record.get("bootId"), str)
            and re.fullmatch(r"[0-9a-f-]{36}", record["bootId"]) is not None)


def attest_cloud_init(identifier: str) -> int:
    identity = document(str(CLI), "candidate-status", "--json")
    if (identity.get("schema") != "machine-control-candidate-assertion/v0"
            or identity.get("identityPin") != "verified"
            or identity.get("role") != "candidate"
            or identity.get("powerState") != "running"):
        raise ValueError("running_exact_candidate_required")
    agent, _ = call(str(UTM_PROVIDER), "factory-agent-ready", timeout=15)
    if not agent:
        raise ValueError("guest_agent_unavailable")
    media = document(str(UTM_PROVIDER), "factory-media-status")
    shape = media.get("stage") if media.get("schema") == "linuxvm-factory-media-status/v0" else None
    status, boot_id, matching = cloud_observation()
    if not (status == "done" or status == "disabled" and shape == "detached") or not boot_id or not matching:
        raise ValueError("matching_cloud_init_completion_required")
    path = attestation_path(identifier)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent,
                                     prefix=".cloud-init-", delete=False) as file:
        temporary = Path(file.name)
        os.fchmod(file.fileno(), 0o600)
        json.dump({"schema": "linuxvm-cloud-init-attestation/v0",
                   "targetId": identifier.lower(), "bootId": boot_id,
                   "observedAt": time.time()}, file)
        file.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"schema": "linuxvm-cloud-init-attestation/v0",
                      "attested": True}))
    return 0


def utm_candidate(identifier: str) -> dict:
    stages = []
    identity = document(str(CLI), "candidate-status", "--json")
    valid = (identity.get("schema") == "machine-control-candidate-assertion/v0"
             and identity.get("identityPin") == "verified"
             and identity.get("role") == "candidate")
    stages.append(stage("identity", "complete" if valid else "blocked",
                        "exact_candidate_pin_verified" if valid else "exact_candidate_required"))
    if not valid:
        return {"schema": SCHEMA, "provider": "utm-macos", "stages": stages}
    power = identity.get("powerState")
    stages.append(stage("power", "complete" if power == "running" else
                        "action_required" if power == "off" else "blocked",
                        "candidate_running" if power == "running" else
                        "candidate_off" if power == "off" else "candidate_power_unknown",
                        *("bin/linuxvm", "up") if power == "off" else ()))
    media = document(str(UTM_PROVIDER), "factory-media-status")
    shape = media.get("stage") if media.get("schema") == "linuxvm-factory-media-status/v0" else None
    agent = power == "running" and call(str(UTM_PROVIDER),
                                         "factory-agent-ready", timeout=15)[0]
    stages.append(stage("guest-agent", "complete" if agent else "waiting",
                        "qga_responsive" if agent else "qga_not_yet_responsive"))
    status, boot_id, matching = cloud_observation() if agent else ("", "", False)
    historical = attested(identifier)
    cloud_done = bool(boot_id and matching and
                      (status == "done" or status == "disabled" and shape == "detached"))
    cloud_error = status == "error"
    stages.append(stage("cloud-init", "complete" if cloud_done or historical and power == "off" else
                        "blocked" if cloud_error else "waiting",
                        "completed_in_observed_boot" if status == "done" and cloud_done else
                        "prior_nocloud_completion_on_disk" if cloud_done else
                        "prior_exact_candidate_attestation" if historical and power == "off" else
                        "cloud_init_error" if cloud_error else "cloud_init_pending"))
    if boot_id:
        stages[-1]["bootId"] = boot_id
    stages.append(stage("cloud-attestation", "complete" if historical else
                        "action_required" if cloud_done else "blocked",
                        "exact_candidate_completion_recorded" if historical else
                        "completion_requires_record" if cloud_done else
                        "current_cloud_completion_required",
                        *("bin/linuxvm", "factory-stages", "attest-cloud-init")
                        if cloud_done and not historical else ()))
    resident = False
    resident_state = "blocked"
    resident_evidence = "cloud_init_required"
    resident_command: tuple[str, ...] = ()
    if cloud_done:
        installed, _ = utm_exec("/usr/bin/test", "-x", "/usr/local/bin/machine-control")
        if not installed:
            resident_state = "action_required"
            resident_evidence = "bootstrap_required"
            resident_command = ("bin/linuxvm", "bootstrap", "--profile", "development")
        else:
            doctor = document(str(CLI), "doctor", "--json", timeout=45,
                              allow_failure_json=True)
            if doctor.get("schema") != "machine-control-doctor/v0":
                resident_state = "unverified"
                resident_evidence = "doctor_unavailable"
                resident_command = ("bin/linuxvm", "doctor", "--json")
            elif doctor.get("ready") is True:
                resident = True
                resident_state = "complete"
                resident_evidence = "full_doctor_ready"
            elif doctor.get("states", {}).get("desktop") == "locked":
                resident_state = "action_required"
                resident_evidence = "desktop_locked"
                resident_command = ("../../bin/machine-control", "inventory", "credentials", "TARGET")
            else:
                resident_state = "action_required"
                resident_evidence = "resident_not_ready"
                resident_command = ("bin/linuxvm", "post-update", "audit", "--json")
    stages.append(stage("resident", resident_state, resident_evidence,
                        *resident_command))
    if shape == "detached":
        stages.append(stage("media", "complete", "seed_drive_absent"))
    elif shape == "seed_only" and historical and (resident or power == "off"):
        stages.append(stage("media", "action_required", "seed_drive_shape_observed",
                            "bin/linuxvm", "shutdown" if power == "running" else
                            "factory-detach-media"))
    elif shape == "seed_only":
        stages.append(stage("media", "blocked", "cloud_attestation_and_resident_required"))
    else:
        stages.append(stage("media", "blocked", "factory_media_unverified"))
    stages.append(stage("final-stop", "complete" if power == "off" and shape == "detached" and historical else
                        "action_required" if resident and shape == "detached" else "blocked",
                        "source_stopped" if power == "off" and shape == "detached" and historical else
                        "clean_shutdown_required" if resident and shape == "detached" else
                        "resident_attestation_and_detached_media_required",
                        *("bin/linuxvm", "shutdown") if resident and shape == "detached" and power == "running" else ()))
    stages.append(credential_stage(power))
    stages.append(promotion_stage(stages))
    return {"schema": SCHEMA, "provider": "utm-macos", "stages": stages}


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
    sub.add_parser("attest-cloud-init")
    args = parser.parse_args()
    provider = os.environ.get("LINUXVM_PROVIDER")
    if provider not in ("libvirt-linux", "utm-macos"):
        parser.error("factory stages require libvirt-linux or utm-macos")
    if args.command != "preflight" and provider == "utm-macos":
        identifier = os.environ.get("LINUXVM_EXPECTED_UUID", "")
        if not re.fullmatch(r"[0-9A-Fa-f-]{36}", identifier):
            parser.error("exact candidate identity is not pinned")
        claim = os.environ.get("MACHINE_CONTROL_CLAIM_ID", "")
        if not claim or not call(str(CLI), "claim-check", "--claim-id", claim,
                                 "--json", timeout=10)[0]:
            parser.error("exclusive exact-candidate claim required")
    if args.command == "attest-cloud-init":
        if provider != "utm-macos":
            parser.error("cloud-init attestation is only for UTM")
        try:
            return attest_cloud_init(identifier)
        except ValueError as error:
            parser.error(str(error))
    if args.command == "preflight":
        report = preflight(args, provider)
    elif provider == "utm-macos":
        report = utm_candidate(identifier)
    else:
        report = candidate()
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
