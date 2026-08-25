#!/usr/bin/env python3
"""Guarded local libvirt/QEMU/KVM primitives for platform adapters."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
from typing import Any, Sequence
import uuid
import xml.etree.ElementTree as ET


HOST_SCHEMA = "machine-control-libvirt-host-doctor/v0"
INSPECT_SCHEMA = "machine-control-libvirt-domain-inspect/v0"
ALLOWED_URI = "qemu:///system"


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Configuration:
    uri: str
    domain_name: str
    expected_uuid: str
    network: str
    pool: str
    virsh: str
    qemu: str
    boot_timeout: int
    shutdown_timeout: int
    exec_timeout: int
    minimum_free_bytes: int
    require_secure_boot: bool
    require_tpm2: bool

    @classmethod
    def from_environment(cls) -> "Configuration":
        return cls(
            uri=os.environ.get("MC_LIBVIRT_URI", ALLOWED_URI),
            domain_name=os.environ.get("MC_LIBVIRT_DOMAIN_NAME", ""),
            expected_uuid=os.environ.get("MC_LIBVIRT_EXPECTED_UUID", ""),
            network=os.environ.get("MC_LIBVIRT_NETWORK", "default"),
            pool=os.environ.get("MC_LIBVIRT_POOL", "default"),
            virsh=os.environ.get("MC_LIBVIRT_VIRSH", "virsh"),
            qemu=os.environ.get("MC_LIBVIRT_QEMU", "qemu-system-x86_64"),
            boot_timeout=positive_integer("MC_LIBVIRT_BOOT_TIMEOUT", 600),
            shutdown_timeout=positive_integer(
                "MC_LIBVIRT_SHUTDOWN_TIMEOUT", 180
            ),
            exec_timeout=positive_integer("MC_LIBVIRT_EXEC_TIMEOUT", 300),
            minimum_free_bytes=nonnegative_integer(
                "MC_LIBVIRT_MIN_FREE_BYTES", 0
            ),
            require_secure_boot=boolean_environment(
                "MC_LIBVIRT_REQUIRE_SECURE_BOOT", False
            ),
            require_tpm2=boolean_environment(
                "MC_LIBVIRT_REQUIRE_TPM2", False
            ),
        )


def positive_integer(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    if not raw.isdigit() or int(raw) < 1:
        raise ProviderError("configuration_invalid", f"{name} must be positive")
    return int(raw)


def nonnegative_integer(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    if not raw.isdigit():
        raise ProviderError(
            "configuration_invalid", f"{name} must be nonnegative"
        )
    return int(raw)


def boolean_environment(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise ProviderError(
        "configuration_invalid", f"{name} must be true or false"
    )


def run(
    arguments: Sequence[str],
    *,
    input_text: str | None = None,
    timeout: int = 30,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            list(arguments),
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProviderError(
            "provider_unavailable", "The local virtualization provider failed"
        ) from error
    if check and completed.returncode != 0:
        raise ProviderError(
            "provider_refused", "The local virtualization provider refused the operation"
        )
    return completed


class Libvirt:
    def __init__(self, configuration: Configuration):
        self.configuration = configuration

    def command(
        self,
        *arguments: str,
        input_text: str | None = None,
        timeout: int = 30,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return run(
            [
                self.configuration.virsh,
                "--connect",
                self.configuration.uri,
                *arguments,
            ],
            input_text=input_text,
            timeout=timeout,
            check=check,
        )

    def text(self, *arguments: str, timeout: int = 30) -> str:
        return self.command(*arguments, timeout=timeout).stdout.strip()


def validate_local_host_basics(configuration: Configuration) -> list[str]:
    failures: list[str] = []
    if platform.system() != "Linux":
        failures.append("controller-platform-not-linux")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        failures.append("controller-architecture-not-x86_64")
    if configuration.uri != ALLOWED_URI:
        failures.append("libvirt-uri-not-local-system")
    virsh = shutil.which(configuration.virsh)
    if virsh is None or not os.access(virsh, os.X_OK):
        failures.append("virsh-unavailable")
    qemu = shutil.which(configuration.qemu)
    if qemu is None or not os.access(qemu, os.X_OK):
        failures.append("x86_64-qemu-unavailable")
    kvm = Path("/dev/kvm")
    try:
        mode = kvm.stat().st_mode
        if not stat.S_ISCHR(mode) or not os.access(kvm, os.R_OK | os.W_OK):
            failures.append("kvm-device-inaccessible")
    except OSError:
        failures.append("kvm-device-inaccessible")
    return failures


def enum_values(root: ET.Element, name: str) -> set[str]:
    return {
        value.text or ""
        for enum in root.findall(f".//enum[@name='{name}']")
        for value in enum.findall("value")
    }


def host_doctor(configuration: Configuration) -> tuple[dict[str, Any], int]:
    failures = validate_local_host_basics(configuration)
    acceleration = False
    uefi = False
    secure_boot = False
    tpm2 = False
    network_active = False
    pool_active = False
    free_bytes: int | None = None

    if not failures:
        provider = Libvirt(configuration)
        try:
            if provider.text("uri") != ALLOWED_URI:
                failures.append("libvirt-uri-mismatch")
            capabilities = ET.fromstring(
                provider.text(
                    "domcapabilities",
                    "--virttype",
                    "kvm",
                    "--arch",
                    "x86_64",
                    "--machine",
                    "q35",
                )
            )
            acceleration = (
                capabilities.findtext("domain") == "kvm"
                and capabilities.findtext("arch") == "x86_64"
                and (capabilities.findtext("machine") or "").startswith(
                    "pc-q35"
                )
            )
            uefi = "efi" in enum_values(capabilities, "firmware")
            secure_boot = "yes" in enum_values(capabilities, "secure")
            tpm2 = "2.0" in enum_values(capabilities, "backendVersion")
            if not acceleration:
                failures.append("kvm-domain-unavailable")
            if not uefi:
                failures.append("q35-uefi-unavailable")
            if configuration.require_secure_boot and not secure_boot:
                failures.append("secure-boot-unavailable")
            if configuration.require_tpm2 and not tpm2:
                failures.append("tpm2-unavailable")

            accel_help = run(
                [configuration.qemu, "-accel", "help"], check=True
            ).stdout.splitlines()
            if "kvm" not in {line.strip() for line in accel_help}:
                acceleration = False
                failures.append("qemu-kvm-accelerator-unavailable")

            network_info = provider.text("net-info", configuration.network)
            network_active = bool(
                re.search(r"^Active:\s+yes$", network_info, re.MULTILINE)
            )
            if not network_active:
                failures.append("libvirt-network-inactive")

            pool_info = provider.text("pool-info", configuration.pool)
            pool_active = bool(
                re.search(r"^State:\s+running$", pool_info, re.MULTILINE)
            )
            if not pool_active:
                failures.append("libvirt-pool-inactive")
            pool_xml = ET.fromstring(
                provider.text("pool-dumpxml", configuration.pool)
            )
            pool_path = pool_xml.findtext("./target/path")
            if not pool_path:
                failures.append("libvirt-pool-path-unavailable")
            else:
                stats = os.statvfs(pool_path)
                free_bytes = stats.f_bavail * stats.f_frsize
                if free_bytes < configuration.minimum_free_bytes:
                    failures.append("libvirt-pool-capacity-below-reserve")
        except (ET.ParseError, OSError, ProviderError):
            failures.append("libvirt-capability-probe-failed")

    failures = sorted(set(failures))
    checks = [
        {
            "id": "hardware_acceleration",
            "status": "pass" if acceleration else "fail",
            "summary": "Native x86_64 KVM acceleration is available"
            if acceleration
            else "Native x86_64 KVM acceleration is unavailable",
        },
        {
            "id": "firmware",
            "status": "pass"
            if uefi and (secure_boot or not configuration.require_secure_boot)
            else "fail",
            "summary": "Required Q35 UEFI firmware is available"
            if uefi
            else "Required Q35 UEFI firmware is unavailable",
        },
        {
            "id": "tpm",
            "status": "pass"
            if tpm2 or not configuration.require_tpm2
            else "fail",
            "summary": "Required emulated TPM 2.0 capability is available"
            if tpm2
            else "Emulated TPM 2.0 capability is unavailable",
        },
        {
            "id": "network",
            "status": "pass" if network_active else "fail",
            "summary": "Configured libvirt network is active"
            if network_active
            else "Configured libvirt network is unavailable",
        },
        {
            "id": "storage",
            "status": "pass" if pool_active and free_bytes is not None else "fail",
            "summary": "Configured libvirt storage is ready"
            if pool_active and free_bytes is not None
            else "Configured libvirt storage is unavailable",
        },
    ]
    value = {
        "schema": HOST_SCHEMA,
        "ready": not failures,
        "architecture": "x86_64",
        "acceleration": {"required": "kvm", "available": acceleration},
        "firmware": {"uefi": uefi, "secureBoot": secure_boot},
        "tpm2": tpm2,
        "network": {"active": network_active},
        "storage": {
            "active": pool_active,
            "measurement": "exact" if free_bytes is not None else "unavailable",
            "freeBytes": free_bytes,
        },
        "checks": checks,
        "failures": failures,
    }
    return value, 0 if not failures else 1


def require_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as error:
        raise ProviderError(
            "identity_unpinned", "The provider identity is unpinned or invalid"
        ) from error


def required_element(root: ET.Element, path: str, reason: str) -> ET.Element:
    element = root.find(path)
    if element is None:
        raise ProviderError("domain_incompatible", reason)
    return element


def validate_domain_xml(
    xml_text: str,
    *,
    expected_uuid: str,
    expected_name: str,
    require_secure_boot: bool,
    require_tpm2: bool,
) -> dict[str, Any]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise ProviderError(
            "domain_xml_invalid", "The provider returned invalid domain XML"
        ) from error
    if root.tag != "domain" or root.get("type") != "kvm":
        raise ProviderError(
            "hardware_acceleration_required", "The domain type must be KVM"
        )
    actual_uuid = require_uuid(root.findtext("uuid") or "")
    if actual_uuid != require_uuid(expected_uuid):
        raise ProviderError(
            "identity_mismatch", "The domain UUID does not match private inventory"
        )
    actual_name = root.findtext("name") or ""
    if not expected_name or actual_name != expected_name:
        raise ProviderError(
            "identity_mismatch", "The domain name does not match private inventory"
        )
    os_type = required_element(
        root, "./os/type", "The domain operating-system type is unavailable"
    )
    architecture = os_type.get("arch") or ""
    machine = os_type.get("machine") or ""
    if architecture != "x86_64":
        raise ProviderError(
            "native_architecture_required", "The domain architecture must be x86_64"
        )
    if not machine.startswith("pc-q35"):
        raise ProviderError(
            "domain_incompatible", "The domain machine type must be Q35"
        )
    emulator = root.findtext("./devices/emulator") or ""
    if Path(emulator).name != "qemu-system-x86_64":
        raise ProviderError(
            "native_architecture_required", "The domain emulator must be x86_64 QEMU"
        )
    loader = root.find("./os/loader")
    secure_boot = loader is not None and loader.get("secure") == "yes"
    if require_secure_boot and not secure_boot:
        raise ProviderError(
            "secure_boot_required", "The domain must use Secure Boot firmware"
        )
    tpm = root.find("./devices/tpm/backend[@version='2.0']")
    tpm2 = tpm is not None
    if require_tpm2 and not tpm2:
        raise ProviderError("tpm2_required", "The domain must expose TPM 2.0")
    guest_agent = any(
        target.get("name") == "org.qemu.guest_agent.0"
        for target in root.findall("./devices/channel/target")
    )
    if not guest_agent:
        raise ProviderError(
            "guest_agent_channel_required",
            "The domain must expose the QEMU guest-agent channel",
        )
    disks = root.findall("./devices/disk[@device='disk']")
    if len(disks) != 1:
        raise ProviderError(
            "domain_incompatible", "The domain must have one primary system disk"
        )
    disk = disks[0]
    driver = required_element(
        disk, "driver", "The primary disk driver is unavailable"
    )
    target = required_element(
        disk, "target", "The primary disk target is unavailable"
    )
    source = required_element(
        disk, "source", "The primary disk source is unavailable"
    )
    if driver.get("type") != "qcow2" or target.get("bus") != "virtio":
        raise ProviderError(
            "domain_incompatible", "The primary disk must be QCOW2 over VirtIO"
        )
    disk_path = source.get("file") or ""
    if not disk_path.startswith("/"):
        raise ProviderError(
            "domain_incompatible", "The primary disk must have an absolute path"
        )
    interface_models = {
        model.get("type") for model in root.findall("./devices/interface/model")
    }
    if "virtio" not in interface_models:
        raise ProviderError(
            "domain_incompatible", "The domain network must use VirtIO"
        )
    return {
        "schema": INSPECT_SCHEMA,
        "identityVerified": True,
        "architecture": architecture,
        "domainType": "kvm",
        "machine": "q35",
        "acceleration": "kvm",
        "secureBoot": secure_boot,
        "tpm2": tpm2,
        "guestAgentChannel": guest_agent,
        "primaryDisk": {"format": "qcow2", "bus": "virtio", "path": disk_path},
    }


def inspect_domain(
    configuration: Configuration, provider: Libvirt
) -> dict[str, Any]:
    expected_uuid = require_uuid(configuration.expected_uuid)
    try:
        actual_uuid = require_uuid(provider.text("domuuid", expected_uuid))
        actual_name = provider.text("domname", expected_uuid)
    except ProviderError as error:
        raise ProviderError(
            "identity_unavailable", "The exact provider domain is unavailable"
        ) from error
    if actual_uuid != expected_uuid or actual_name != configuration.domain_name:
        raise ProviderError(
            "identity_mismatch", "The exact provider identity does not match"
        )
    xml_text = provider.text("dumpxml", "--inactive", expected_uuid)
    return validate_domain_xml(
        xml_text,
        expected_uuid=expected_uuid,
        expected_name=configuration.domain_name,
        require_secure_boot=configuration.require_secure_boot,
        require_tpm2=configuration.require_tpm2,
    )


def domain_state(configuration: Configuration, provider: Libvirt) -> str:
    inspect_domain(configuration, provider)
    raw = provider.text("domstate", configuration.expected_uuid).lower()
    if raw == "running":
        return "started"
    if raw in {"shut off", "shutdown", "crashed", "pmsuspended"}:
        return "stopped"
    if raw in {"paused", "blocked"}:
        return "suspended"
    return "unknown"


def query_kvm(configuration: Configuration, provider: Libvirt) -> bool:
    result = provider.text(
        "qemu-monitor-command",
        configuration.expected_uuid,
        '{"execute":"query-kvm"}',
    )
    try:
        value = json.loads(result)["return"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ProviderError(
            "acceleration_unverified", "The live KVM state could not be verified"
        ) from error
    return value.get("enabled") is True and value.get("present") is True


def wait_for_state(
    configuration: Configuration,
    provider: Libvirt,
    expected: str,
    timeout: int,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if domain_state(configuration, provider) == expected:
            return
        time.sleep(1)
    raise ProviderError(
        "lifecycle_timeout", "The domain did not reach the requested state"
    )


def start_domain(configuration: Configuration, provider: Libvirt) -> None:
    host, host_exit = host_doctor(configuration)
    if host_exit != 0:
        raise ProviderError(
            "host_not_ready", "The KVM controller host is not ready"
        )
    state = domain_state(configuration, provider)
    if state == "started":
        if not query_kvm(configuration, provider):
            raise ProviderError(
                "hardware_acceleration_required",
                "The running domain is not using KVM acceleration",
            )
        return
    if state != "stopped":
        raise ProviderError(
            "lifecycle_state_invalid", "The domain is not in a startable state"
        )
    provider.command("start", configuration.expected_uuid)
    try:
        wait_for_state(
            configuration, provider, "started", configuration.boot_timeout
        )
        if not query_kvm(configuration, provider):
            raise ProviderError(
                "hardware_acceleration_required",
                "The started domain did not enable KVM acceleration",
            )
    except ProviderError:
        provider.command("destroy", configuration.expected_uuid, check=False)
        raise


def shutdown_domain(configuration: Configuration, provider: Libvirt) -> None:
    state = domain_state(configuration, provider)
    if state == "stopped":
        return
    if state != "started":
        raise ProviderError(
            "lifecycle_state_invalid", "The domain is not in a stoppable state"
        )
    result = provider.command(
        "shutdown",
        configuration.expected_uuid,
        "--mode",
        "agent",
        check=False,
    )
    if result.returncode != 0:
        provider.command(
            "shutdown", configuration.expected_uuid, "--mode", "acpi"
        )
    wait_for_state(
        configuration, provider, "stopped", configuration.shutdown_timeout
    )


def agent_command(
    configuration: Configuration,
    provider: Libvirt,
    payload: dict[str, Any],
    *,
    timeout: int | None = None,
) -> Any:
    result = provider.text(
        "qemu-agent-command",
        configuration.expected_uuid,
        "--timeout",
        str(timeout or configuration.exec_timeout),
        json.dumps(payload, separators=(",", ":")),
        timeout=(timeout or configuration.exec_timeout) + 5,
    )
    try:
        value = json.loads(result)
    except json.JSONDecodeError as error:
        raise ProviderError(
            "guest_agent_invalid", "The guest agent returned invalid JSON"
        ) from error
    if "error" in value:
        raise ProviderError(
            "guest_agent_refused", "The guest agent refused the operation"
        )
    if "return" not in value:
        raise ProviderError(
            "guest_agent_invalid", "The guest agent response was incomplete"
        )
    return value["return"]


def wait_for_agent(configuration: Configuration, provider: Libvirt) -> None:
    deadline = time.monotonic() + configuration.boot_timeout
    while time.monotonic() < deadline:
        try:
            agent_command(
                configuration,
                provider,
                {"execute": "guest-ping"},
                timeout=5,
            )
            return
        except ProviderError:
            time.sleep(1)
    raise ProviderError(
        "guest_agent_unavailable", "The QEMU guest agent is unavailable"
    )


def guest_exec(
    configuration: Configuration,
    provider: Libvirt,
    arguments: Sequence[str],
) -> int:
    if not arguments:
        raise ProviderError("arguments_invalid", "A guest executable is required")
    start_domain(configuration, provider)
    wait_for_agent(configuration, provider)
    started = agent_command(
        configuration,
        provider,
        {
            "execute": "guest-exec",
            "arguments": {
                "path": arguments[0],
                "arg": list(arguments[1:]),
                "capture-output": True,
            },
        },
    )
    pid = started.get("pid") if isinstance(started, dict) else None
    if not isinstance(pid, int):
        raise ProviderError(
            "guest_agent_invalid", "The guest command did not return a process ID"
        )
    deadline = time.monotonic() + configuration.exec_timeout
    while time.monotonic() < deadline:
        status = agent_command(
            configuration,
            provider,
            {
                "execute": "guest-exec-status",
                "arguments": {"pid": pid},
            },
        )
        if isinstance(status, dict) and status.get("exited") is True:
            stdout = base64.b64decode(status.get("out-data", ""), validate=True)
            stderr = base64.b64decode(status.get("err-data", ""), validate=True)
            sys.stdout.buffer.write(stdout)
            sys.stderr.buffer.write(stderr)
            if "exitcode" in status:
                return max(0, min(255, int(status["exitcode"])))
            return 128 + max(0, min(127, int(status.get("signal", 1))))
        time.sleep(0.25)
    raise ProviderError(
        "guest_exec_timeout", "The guest command did not complete in time"
    )


def guest_file_open(
    configuration: Configuration,
    provider: Libvirt,
    path: str,
    mode: str,
) -> int:
    handle = agent_command(
        configuration,
        provider,
        {
            "execute": "guest-file-open",
            "arguments": {"path": path, "mode": mode},
        },
    )
    if not isinstance(handle, int):
        raise ProviderError(
            "guest_agent_invalid", "The guest file operation returned no handle"
        )
    return handle


def guest_file_close(
    configuration: Configuration, provider: Libvirt, handle: int
) -> None:
    agent_command(
        configuration,
        provider,
        {"execute": "guest-file-close", "arguments": {"handle": handle}},
    )


def guest_push(
    configuration: Configuration,
    provider: Libvirt,
    local_path: str,
    remote_path: str,
) -> None:
    source = Path(local_path)
    if not source.is_file():
        raise ProviderError("source_unreadable", "The local source is unreadable")
    start_domain(configuration, provider)
    wait_for_agent(configuration, provider)
    handle = guest_file_open(configuration, provider, remote_path, "wb")
    try:
        with source.open("rb") as stream:
            while chunk := stream.read(48 * 1024):
                result = agent_command(
                    configuration,
                    provider,
                    {
                        "execute": "guest-file-write",
                        "arguments": {
                            "handle": handle,
                            "buf-b64": base64.b64encode(chunk).decode("ascii"),
                        },
                    },
                )
                if not isinstance(result, dict) or result.get("count") != len(chunk):
                    raise ProviderError(
                        "guest_file_incomplete", "The guest file write was incomplete"
                    )
    finally:
        guest_file_close(configuration, provider, handle)


def guest_pull(
    configuration: Configuration,
    provider: Libvirt,
    remote_path: str,
    local_path: str | None,
) -> None:
    wait_for_agent(configuration, provider)
    handle = guest_file_open(configuration, provider, remote_path, "rb")
    output = Path(local_path).open("wb") if local_path else sys.stdout.buffer
    try:
        while True:
            result = agent_command(
                configuration,
                provider,
                {
                    "execute": "guest-file-read",
                    "arguments": {"handle": handle, "count": 48 * 1024},
                },
            )
            if not isinstance(result, dict):
                raise ProviderError(
                    "guest_agent_invalid", "The guest file read was invalid"
                )
            data = base64.b64decode(result.get("buf-b64", ""), validate=True)
            output.write(data)
            if result.get("eof") is True:
                break
    finally:
        if local_path:
            output.close()
        guest_file_close(configuration, provider, handle)


def guest_ipv4(configuration: Configuration, provider: Libvirt) -> str:
    start_domain(configuration, provider)
    wait_for_agent(configuration, provider)
    deadline = time.monotonic() + configuration.boot_timeout
    address_pattern = re.compile(r"\b([0-9]+(?:\.[0-9]+){3})/\d+\b")
    while time.monotonic() < deadline:
        result = provider.command(
            "domifaddr",
            configuration.expected_uuid,
            "--source",
            "agent",
            check=False,
        )
        if result.returncode == 0:
            for match in address_pattern.finditer(result.stdout):
                address = ipaddress.ip_address(match.group(1))
                if not address.is_loopback and not address.is_link_local:
                    return str(address)
        time.sleep(1)
    raise ProviderError(
        "guest_address_unavailable", "The guest IPv4 address is unavailable"
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("host-doctor")
    subparsers.add_parser("inspect")
    subparsers.add_parser("status")
    subparsers.add_parser("start")
    subparsers.add_parser("shutdown")
    subparsers.add_parser("force-stop")
    subparsers.add_parser("ip")
    execute = subparsers.add_parser("exec")
    execute.add_argument("arguments", nargs=argparse.REMAINDER)
    push = subparsers.add_parser("push")
    push.add_argument("local")
    push.add_argument("remote")
    pull = subparsers.add_parser("pull")
    pull.add_argument("remote")
    pull.add_argument("local", nargs="?")
    return parser.parse_args()


def main() -> int:
    try:
        arguments = parse_arguments()
        configuration = Configuration.from_environment()
        if arguments.command == "host-doctor":
            value, exit_code = host_doctor(configuration)
            print(json.dumps(value, separators=(",", ":"), sort_keys=True))
            return exit_code
        provider = Libvirt(configuration)
        if arguments.command == "inspect":
            print(
                json.dumps(
                    inspect_domain(configuration, provider),
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
            return 0
        if arguments.command == "status":
            print(domain_state(configuration, provider))
            return 0
        if arguments.command == "start":
            start_domain(configuration, provider)
            return 0
        if arguments.command == "shutdown":
            shutdown_domain(configuration, provider)
            print("stopped")
            return 0
        if arguments.command == "force-stop":
            inspect_domain(configuration, provider)
            provider.command("destroy", configuration.expected_uuid)
            wait_for_state(
                configuration,
                provider,
                "stopped",
                configuration.shutdown_timeout,
            )
            print("stopped")
            return 0
        if arguments.command == "ip":
            print(guest_ipv4(configuration, provider))
            return 0
        if arguments.command == "exec":
            command = arguments.arguments
            if command and command[0] == "--":
                command = command[1:]
            return guest_exec(configuration, provider, command)
        if arguments.command == "push":
            guest_push(configuration, provider, arguments.local, arguments.remote)
            return 0
        if arguments.command == "pull":
            guest_pull(configuration, provider, arguments.remote, arguments.local)
            return 0
        raise ProviderError("arguments_invalid", "Unsupported provider command")
    except ProviderError as error:
        print(f"{error.code}: {error.message}", file=sys.stderr)
        return 1
    except (ValueError, base64.binascii.Error):
        print("provider_invalid: The provider returned invalid data", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
