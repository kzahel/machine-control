#!/usr/bin/env python3
"""Exact libvirt domain and QCOW2-overlay workspace mutations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import Any
import uuid
import xml.etree.ElementTree as ET


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from libvirt_provider import (  # noqa: E402
    Configuration,
    Libvirt,
    MACOS_PROFILE,
    ProviderError,
    QEMU_NAMESPACE,
    domain_state,
    inspect_domain,
    require_uuid,
    validate_domain_xml,
)


VOLUME_PREFIX = "machine-control-"
VOLUME_SUFFIX = ".qcow2"
NVRAM_SUFFIX = "_VARS.fd"
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}")
ET.register_namespace("qemu", QEMU_NAMESPACE)


def volume_name(target_uuid: str, role: str = "primaryDisk") -> str:
    suffix = "-opencore" if role == "bootDisk" else ""
    return f"{VOLUME_PREFIX}{require_uuid(target_uuid)}{suffix}{VOLUME_SUFFIX}"


def nvram_name(target_uuid: str) -> str:
    return f"{VOLUME_PREFIX}{require_uuid(target_uuid)}{NVRAM_SUFFIX}"


def direct_children(parent: ET.Element, tag: str) -> list[ET.Element]:
    return [child for child in list(parent) if child.tag == tag]


def remove_children(parent: ET.Element, tag: str) -> None:
    for child in direct_children(parent, tag):
        parent.remove(child)


def derive_domain_xml(
    source_xml: str,
    *,
    source_uuid: str,
    source_name: str,
    target_uuid: str,
    target_name: str,
    target_disk: str,
    target_nvram: str,
    nvram_template: str,
    require_secure_boot: bool,
    require_tpm2: bool,
    profile: str = "standard",
    target_boot_disk: str = "",
) -> str:
    source_layout = validate_domain_xml(
        source_xml,
        expected_uuid=source_uuid,
        expected_name=source_name,
        require_secure_boot=require_secure_boot,
        require_tpm2=require_tpm2,
        profile=profile,
    )
    macos = profile == MACOS_PROFILE
    target_uuid = require_uuid(target_uuid)
    if not SAFE_NAME.fullmatch(target_name):
        raise ProviderError(
            "workspace_name_invalid", "The generated workspace name is invalid"
        )
    workspace_paths = (target_disk, target_nvram, nvram_template)
    if macos:
        workspace_paths += (target_boot_disk,)
        source_paths = {
            os.path.realpath(source_layout["primaryDisk"]["path"]),
            os.path.realpath(source_layout["bootDisk"]["path"]),
            os.path.realpath(source_layout["nvramPath"]),
        }
        destination_paths = {os.path.realpath(path) for path in
                             (target_disk, target_boot_disk, target_nvram)}
        if len(destination_paths) != 3 or source_paths & destination_paths:
            raise ProviderError("workspace_path_invalid", "macOS workspace paths must be independent")
        nvram_template = source_layout["nvramPath"]
    if not all(PurePosixPath(path).is_absolute() for path in workspace_paths):
        raise ProviderError(
            "workspace_path_invalid", "Workspace paths must be absolute"
        )
    try:
        root = ET.fromstring(source_xml)
    except ET.ParseError as error:
        raise ProviderError(
            "domain_xml_invalid", "The provider returned invalid domain XML"
        ) from error
    name = root.find("name")
    identity = root.find("uuid")
    if name is None or identity is None:
        raise ProviderError(
            "domain_xml_invalid", "The source domain identity is incomplete"
        )
    name.text = target_name
    identity.text = target_uuid

    metadata = root.find("metadata")
    if metadata is not None:
        root.remove(metadata)
    for element in root.findall("./devices/disk[@device='cdrom']"):
        devices = root.find("devices")
        assert devices is not None
        devices.remove(element)
    for interface in root.findall("./devices/interface"):
        remove_children(interface, "mac")
        remove_children(interface, "target")
        remove_children(interface, "alias")
        if not macos:
            remove_children(interface, "address")
    for channel in root.findall("./devices/channel"):
        remove_children(channel, "source")
        remove_children(channel, "alias")
        remove_children(channel, "address")
    for device in root.findall("./devices/*"):
        remove_children(device, "alias")
        if not macos:
            remove_children(device, "address")
    for disk in root.findall("./devices/disk[@device='disk']"):
        source = disk.find("source")
        if source is None:
            raise ProviderError(
                "domain_xml_invalid", "The source system disk is incomplete"
            )
        source.attrib.clear()
        source.set("file", target_boot_disk if macos and disk.find("boot") is not None else target_disk)
        if macos:
            remove_children(disk, "backingStore")

    os_element = root.find("os")
    if os_element is None:
        raise ProviderError(
            "domain_xml_invalid", "The source firmware configuration is absent"
        )
    nvram = os_element.find("nvram")
    if nvram is None:
        nvram = ET.SubElement(os_element, "nvram")
    nvram.attrib.clear()
    nvram.set("template", nvram_template)
    nvram.text = target_nvram

    for launch_security in root.findall("launchSecurity"):
        root.remove(launch_security)
    return ET.tostring(root, encoding="unicode")


def volume_info(
    configuration: Configuration, provider: Libvirt, path: str
) -> dict[str, Any]:
    try:
        root = ET.fromstring(
            provider.text(
                "vol-dumpxml", path, "--pool", configuration.pool
            )
        )
        capacity = int(root.findtext("capacity") or "0")
    except (ET.ParseError, ValueError) as error:
        raise ProviderError(
            "workspace_storage_invalid", "QCOW2 metadata is unavailable"
        ) from error
    target_format = root.find("./target/format")
    if target_format is None or target_format.get("type") != "qcow2":
        raise ProviderError(
            "workspace_storage_invalid", "The workspace disk must be QCOW2"
        )
    return {
        "capacity": capacity,
        "backing": root.findtext("./backingStore/path"),
    }


def write_temporary_xml(value: str) -> Path:
    descriptor, raw_path = tempfile.mkstemp(
        prefix="machine-control-libvirt-", suffix=".xml"
    )
    path = Path(raw_path)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(value)
            output.write("\n")
        path.chmod(0o600)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def create_volume(
    configuration: Configuration,
    provider: Libvirt,
    *,
    name: str,
    capacity: int,
    backing_path: str,
) -> str:
    volume_xml = ET.Element("volume")
    ET.SubElement(volume_xml, "name").text = name
    capacity_element = ET.SubElement(volume_xml, "capacity", unit="bytes")
    capacity_element.text = str(capacity)
    target = ET.SubElement(volume_xml, "target")
    ET.SubElement(target, "format", type="qcow2")
    backing = ET.SubElement(volume_xml, "backingStore")
    ET.SubElement(backing, "path").text = backing_path
    ET.SubElement(backing, "format", type="qcow2")
    temporary = write_temporary_xml(
        ET.tostring(volume_xml, encoding="unicode")
    )
    try:
        provider.command("vol-create", configuration.pool, str(temporary))
    finally:
        temporary.unlink(missing_ok=True)
    path = provider.text("vol-path", "--pool", configuration.pool, name)
    if not Path(path).is_absolute():
        raise ProviderError(
            "workspace_storage_invalid", "The provider volume path is invalid"
        )
    return path


def command_derive(arguments: argparse.Namespace) -> int:
    configuration = Configuration.from_environment()
    provider = Libvirt(configuration)
    source = inspect_domain(configuration, provider)
    if domain_state(configuration, provider) != "stopped":
        raise ProviderError(
            "source_not_stopped", "Workspace derivation requires a stopped source"
        )
    source_uuid = require_uuid(configuration.expected_uuid)
    if provider.command("domuuid", arguments.name, check=False).returncode == 0:
        raise ProviderError(
            "destination_exists", "The generated workspace domain already exists"
        )
    target_uuid = str(uuid.uuid4())
    macos = configuration.profile == MACOS_PROFILE
    roles = ["primaryDisk", "bootDisk"] if macos else ["primaryDisk"]
    volumes = {}
    rollback_names = []
    defined = False
    try:
        for role in roles:
            source_disk = source[role]["path"]
            capacity = volume_info(configuration, provider, source_disk).get("capacity")
            if not isinstance(capacity, int) or capacity < 1:
                raise ProviderError(
                    "workspace_storage_invalid", "The source virtual capacity is invalid"
                )
            name = volume_name(target_uuid, role)
            rollback_names.append(name)
            volumes[role] = create_volume(
                configuration, provider, name=name, capacity=capacity, backing_path=source_disk,
            )
        source_xml = provider.text("dumpxml", "--inactive", source_uuid)
        target_nvram = str(Path(arguments.nvram_directory) / nvram_name(target_uuid))
        target_xml = derive_domain_xml(
            source_xml,
            source_uuid=source_uuid,
            source_name=configuration.domain_name,
            target_uuid=target_uuid,
            target_name=arguments.name,
            target_disk=volumes["primaryDisk"],
            target_nvram=target_nvram,
            nvram_template=arguments.nvram_template,
            require_secure_boot=configuration.require_secure_boot,
            require_tpm2=configuration.require_tpm2,
            profile=configuration.profile,
            target_boot_disk=volumes.get("bootDisk", ""),
        )
        temporary = write_temporary_xml(target_xml)
        try:
            provider.command("define", "--validate", str(temporary))
            defined = True
        finally:
            temporary.unlink(missing_ok=True)

        derived_configuration = Configuration(
            **{
                **configuration.__dict__,
                "domain_name": arguments.name,
                "expected_uuid": target_uuid,
            }
        )
        derived = inspect_domain(derived_configuration, provider)
        if any(derived[role]["path"] != volumes[role] for role in roles) or (
            macos and derived["nvramPath"] != target_nvram
        ):
            raise ProviderError(
                "workspace_identity_mismatch",
                "The derived domain disk identity does not match",
            )
        print(
            json.dumps(
                {"name": arguments.name, "uuid": target_uuid},
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 0
    except BaseException:
        if defined:
            undefine = ["undefine", target_uuid, "--nvram"]
            if not macos:
                undefine.append("--tpm")
            if provider.command(*undefine, check=False).returncode != 0:
                raise
        for name in rollback_names:
            provider.command(
                "vol-delete", name, "--pool", configuration.pool, check=False
            )
        raise


def command_release(arguments: argparse.Namespace) -> int:
    configuration = Configuration.from_environment()
    provider = Libvirt(configuration)
    target_uuid = require_uuid(configuration.expected_uuid)
    source_uuid = require_uuid(arguments.source_uuid)
    if target_uuid == source_uuid:
        raise ProviderError("workspace_identity_mismatch", "The workspace source is protected")
    target = inspect_domain(configuration, provider)
    if domain_state(configuration, provider) != "stopped":
        raise ProviderError(
            "workspace_running", "Workspace cleanup requires a stopped domain"
        )
    source_configuration = Configuration(
        **{
            **configuration.__dict__,
            "domain_name": arguments.source_name,
            "expected_uuid": source_uuid,
        }
    )
    source = inspect_domain(source_configuration, provider)
    macos = configuration.profile == MACOS_PROFILE
    roles = ["primaryDisk", "bootDisk"] if macos else ["primaryDisk"]
    names = []
    for role in roles:
        name = volume_name(target_uuid, role)
        expected_disk = provider.text("vol-path", "--pool", configuration.pool, name)
        if target[role]["path"] != expected_disk:
            raise ProviderError(
                "workspace_identity_mismatch",
                "The receipt-owned workspace disk does not match the domain",
            )
        backing = volume_info(configuration, provider, expected_disk).get("backing")
        if not isinstance(backing, str) or Path(backing).resolve() != Path(source[role]["path"]).resolve():
            raise ProviderError(
                "workspace_backing_mismatch",
                "The workspace backing image does not match its exact source",
            )
        names.append(name)
    if macos:
        nvram_root = Path(arguments.nvram_directory)
        expected_nvram = nvram_root / nvram_name(target_uuid)
        if not nvram_root.is_absolute() or Path(target["nvramPath"]) != expected_nvram or (
            expected_nvram.resolve() == Path(source["nvramPath"]).resolve()
        ):
            raise ProviderError("workspace_identity_mismatch", "The workspace NVRAM is not receipt-owned")
    xml_text = provider.text("dumpxml", "--inactive", target_uuid)
    root = ET.fromstring(xml_text)
    arguments_undefine = ["undefine", target_uuid]
    if root.find("./os/nvram") is not None:
        arguments_undefine.append("--nvram")
    if root.find("./devices/tpm") is not None:
        arguments_undefine.append("--tpm")
    provider.command(*arguments_undefine)
    for name in names:
        provider.command("vol-delete", name, "--pool", configuration.pool)
    if provider.command("domname", target_uuid, check=False).returncode == 0:
        raise ProviderError(
            "workspace_cleanup_incomplete", "The derived domain still exists"
        )
    if any(provider.command(
        "vol-info", name, "--pool", configuration.pool, check=False
    ).returncode == 0 for name in names):
        raise ProviderError(
            "workspace_cleanup_incomplete", "The derived volume still exists"
        )
    return 0


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    derive = commands.add_parser("derive")
    derive.add_argument("--name", required=True)
    derive.add_argument("--nvram-directory", required=True)
    derive.add_argument("--nvram-template", required=True)
    derive.set_defaults(function=command_derive)
    release = commands.add_parser("release")
    release.add_argument("--source-uuid", required=True)
    release.add_argument("--source-name", required=True)
    release.add_argument("--nvram-directory", default="")
    release.set_defaults(function=command_release)
    return parser.parse_args()


def main() -> int:
    try:
        arguments = parse_arguments()
        return arguments.function(arguments)
    except ProviderError as error:
        print(f"{error.code}: {error.message}", file=sys.stderr)
        return 1
    except (OSError, ET.ParseError, ValueError):
        print("workspace_provider_failed: The workspace operation failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
