#!/usr/bin/env python3
"""Typed native-x86_64 libvirt appliance factory operations."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from libvirt_provider import (
    Configuration,
    Libvirt,
    ProviderError,
    host_doctor,
    inspect_domain,
    require_uuid,
    run,
)


NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def require_name(configuration: Configuration, name: str) -> str:
    if not NAME_PATTERN.fullmatch(name):
        raise ProviderError("factory_name_invalid", "The factory name is invalid")
    if configuration.domain_name and name != configuration.domain_name:
        raise ProviderError(
            "factory_identity_mismatch",
            "The factory name does not match private inventory",
        )
    return name


def require_media(path_value: str) -> str:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file() or not os.access(path, os.R_OK):
        raise ProviderError(
            "factory_media_unavailable", "Required factory media is unavailable"
        )
    return str(path)


def require_factory_host(configuration: Configuration) -> None:
    _value, exit_code = host_doctor(configuration)
    if exit_code != 0:
        raise ProviderError("host_not_ready", "The KVM controller host is not ready")


def absent_domain(provider: Libvirt, name: str) -> None:
    result = provider.command("domuuid", name, check=False)
    if result.returncode == 0:
        raise ProviderError(
            "factory_destination_exists", "The factory destination already exists"
        )


def absent_volume(provider: Libvirt, pool: str, volume: str) -> None:
    result = provider.command("vol-info", "--pool", pool, volume, check=False)
    if result.returncode == 0:
        raise ProviderError(
            "factory_destination_exists", "The factory storage already exists"
        )


def create_volume(
    provider: Libvirt,
    pool: str,
    volume: str,
    capacity: str,
) -> None:
    provider.command(
        "vol-create-as",
        "--pool",
        pool,
        "--name",
        volume,
        "--capacity",
        capacity,
        "--format",
        "qcow2",
    )


def delete_volume(provider: Libvirt, pool: str, volume: str) -> None:
    provider.command("vol-delete", "--pool", pool, volume, check=False)


def define_domain(
    configuration: Configuration,
    provider: Libvirt,
    arguments: list[str],
    *,
    name: str,
) -> str:
    completed = run(
        [
            "virt-install",
            "--connect",
            configuration.uri,
            "--name",
            name,
            *arguments,
            "--noautoconsole",
            "--print-xml",
        ],
        timeout=120,
    )
    provider.command("define", "/dev/stdin", input_text=completed.stdout)
    actual_uuid = require_uuid(provider.text("domuuid", name))
    exact = replace(
        configuration,
        domain_name=name,
        expected_uuid=actual_uuid,
    )
    inspect_domain(exact, provider)
    return actual_uuid


def common_domain_arguments(
    configuration: Configuration,
    volume: str,
    *,
    memory_mib: int,
    vcpus: int,
    osinfo: str,
) -> list[str]:
    return [
        "--memory",
        str(memory_mib),
        "--vcpus",
        str(vcpus),
        "--cpu",
        "host-passthrough",
        "--machine",
        "q35",
        "--features",
        "smm.state=on",
        "--disk",
        f"vol={configuration.pool}/{volume},bus=virtio,format=qcow2",
        "--network",
        f"network={configuration.network},model=virtio",
        "--graphics",
        "spice,listen=none",
        "--video",
        "virtio",
        "--channel",
        "unix,target.type=virtio,target.name=org.qemu.guest_agent.0",
        "--controller",
        "usb,model=qemu-xhci",
        "--input",
        "tablet,bus=usb",
        "--osinfo",
        osinfo,
    ]


def cleanup_failed_creation(
    provider: Libvirt, name: str, pool: str, volumes: list[str]
) -> None:
    provider.command("undefine", name, "--nvram", "--tpm", check=False)
    for volume in volumes:
        delete_volume(provider, pool, volume)


def stage_pool_file(
    configuration: Configuration,
    provider: Libvirt,
    volume: str,
    source: str,
) -> str:
    pool_path = require_local_pool_path(provider, configuration.pool)
    destination = pool_path / volume
    if destination.exists() or destination.is_symlink():
        raise ProviderError(
            "factory_destination_exists", "The factory storage already exists"
        )
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{volume}.", suffix=".stage", dir=pool_path
    )
    os.close(descriptor)
    temporary = Path(temporary_path)
    temporary.unlink()
    linked_destination = False
    try:
        run(
            ["cp", "--reflink=auto", "--sparse=always", source, str(temporary)],
            timeout=600,
        )
        os.chmod(temporary, 0o600)
        os.link(temporary, destination)
        linked_destination = True
        temporary.unlink()
        provider.command("pool-refresh", configuration.pool)
        registered = Path(
            provider.text(
                "vol-path", "--pool", configuration.pool, volume
            )
        ).resolve(strict=True)
        if registered != destination.resolve(strict=True):
            raise ProviderError(
                "factory_volume_identity_mismatch",
                "The staged media does not match the exact pool path",
            )
        return str(registered)
    except Exception:
        if linked_destination:
            destination.unlink(missing_ok=True)
            provider.command("pool-refresh", configuration.pool, check=False)
        raise
    finally:
        temporary.unlink(missing_ok=True)


def create_windows(
    configuration: Configuration,
    provider: Libvirt,
    name_value: str,
    windows_iso_value: str,
    seed_iso_value: str,
) -> None:
    name = require_name(configuration, name_value)
    windows_iso = require_media(windows_iso_value)
    seed_iso = require_media(seed_iso_value)
    require_factory_host(configuration)
    absent_domain(provider, name)
    volume = f"{name}.qcow2"
    installer_volume = f"{name}.installer.iso"
    seed_volume = f"{name}.seed.iso"
    absent_volume(provider, configuration.pool, volume)
    absent_volume(provider, configuration.pool, installer_volume)
    absent_volume(provider, configuration.pool, seed_volume)
    create_volume(provider, configuration.pool, volume, "128G")
    owned_volumes = [volume]
    try:
        staged_installer = stage_pool_file(
            configuration, provider, installer_volume, windows_iso
        )
        owned_volumes.append(installer_volume)
        staged_seed = stage_pool_file(
            configuration, provider, seed_volume, seed_iso
        )
        owned_volumes.append(seed_volume)
        arguments = common_domain_arguments(
            configuration,
            volume,
            memory_mib=8192,
            vcpus=6,
            osinfo="win11",
        )
        arguments.extend(
            [
                "--boot",
                "uefi,firmware.feature0.name=secure-boot,"
                "firmware.feature0.enabled=yes,"
                "firmware.feature1.name=enrolled-keys,"
                "firmware.feature1.enabled=yes",
                "--tpm",
                "backend.type=emulator,backend.version=2.0,model=tpm-crb",
                "--disk",
                f"path={staged_installer},device=cdrom,bus=sata,readonly=on",
                "--disk",
                f"path={staged_seed},device=cdrom,bus=sata,readonly=on",
            ]
        )
        define_domain(configuration, provider, arguments, name=name)
    except Exception:
        cleanup_failed_creation(
            provider, name, configuration.pool, owned_volumes
        )
        raise
    print("factory target created")


def validate_cloud_image(configuration: Configuration, image: str) -> None:
    qemu_img = shutil.which("qemu-img")
    if qemu_img is None:
        raise ProviderError(
            "provider_unavailable", "The QCOW2 image tool is unavailable"
        )
    completed = run(
        [qemu_img, "info", "--output", "json", image]
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ProviderError(
            "factory_media_invalid", "The cloud image metadata is invalid"
        ) from error
    if value.get("format") != "qcow2" or not isinstance(
        value.get("virtual-size"), int
    ):
        raise ProviderError(
            "factory_media_invalid", "The cloud image must be QCOW2"
        )


def require_local_pool_path(provider: Libvirt, pool: str) -> Path:
    configured = os.environ.get("MC_LIBVIRT_POOL_PATH", "")
    if not configured or not Path(configured).is_absolute():
        raise ProviderError(
            "factory_pool_path_unconfigured",
            "The local factory pool path is not configured",
        )
    try:
        root = ET.fromstring(provider.text("pool-dumpxml", pool))
    except ET.ParseError as error:
        raise ProviderError(
            "factory_pool_shape_invalid", "The factory pool XML is invalid"
        ) from error
    declared = root.findtext("./target/path") or ""
    try:
        configured_path = Path(configured).resolve(strict=True)
        declared_path = Path(declared).resolve(strict=True)
    except OSError as error:
        raise ProviderError(
            "factory_pool_unavailable", "The local factory pool is unavailable"
        ) from error
    if configured_path != declared_path:
        raise ProviderError(
            "factory_pool_identity_mismatch",
            "The configured path does not match the exact libvirt pool",
        )
    if not configured_path.is_dir() or not os.access(
        configured_path, os.W_OK | os.X_OK
    ):
        raise ProviderError(
            "factory_pool_unwritable",
            "The dedicated local factory pool is not controller-writable",
        )
    return configured_path


def import_cloud_volume(
    configuration: Configuration,
    provider: Libvirt,
    volume: str,
    cloud_image: str,
) -> None:
    pool_path = require_local_pool_path(provider, configuration.pool)
    destination = pool_path / volume
    if destination.exists() or destination.is_symlink():
        raise ProviderError(
            "factory_destination_exists", "The factory storage already exists"
        )
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{volume}.", suffix=".import", dir=pool_path
    )
    os.close(descriptor)
    temporary = Path(temporary_path)
    temporary.unlink()
    linked_destination = False
    try:
        run(
            [
                "qemu-img",
                "convert",
                "-O",
                "qcow2",
                "-S",
                "4096",
                cloud_image,
                str(temporary),
            ],
            timeout=600,
        )
        run(["qemu-img", "resize", str(temporary), "128G"])
        os.chmod(temporary, 0o600)
        os.link(temporary, destination)
        linked_destination = True
        temporary.unlink()
        provider.command("pool-refresh", configuration.pool)
        registered = Path(
            provider.text(
                "vol-path", "--pool", configuration.pool, volume
            )
        ).resolve(strict=True)
        if registered != destination.resolve(strict=True):
            raise ProviderError(
                "factory_volume_identity_mismatch",
                "The imported volume does not match the exact pool path",
            )
        try:
            metadata = json.loads(
                run(
                    ["qemu-img", "info", "--output", "json", str(registered)]
                ).stdout
            )
        except json.JSONDecodeError as error:
            raise ProviderError(
                "factory_volume_invalid",
                "The imported cloud volume metadata is invalid",
            ) from error
        if metadata.get("format") != "qcow2" or metadata.get(
            "virtual-size"
        ) != 128 * 1024**3:
            raise ProviderError(
                "factory_volume_invalid",
                "The imported cloud volume failed exact validation",
            )
    except Exception:
        if linked_destination:
            destination.unlink(missing_ok=True)
            provider.command("pool-refresh", configuration.pool, check=False)
        raise
    finally:
        temporary.unlink(missing_ok=True)


def create_linux(
    configuration: Configuration,
    provider: Libvirt,
    name_value: str,
    cloud_image_value: str,
    seed_iso_value: str,
) -> None:
    name = require_name(configuration, name_value)
    cloud_image = require_media(cloud_image_value)
    seed_iso = require_media(seed_iso_value)
    validate_cloud_image(configuration, cloud_image)
    require_factory_host(configuration)
    absent_domain(provider, name)
    volume = f"{name}.qcow2"
    seed_volume = f"{name}.seed.iso"
    absent_volume(provider, configuration.pool, volume)
    absent_volume(provider, configuration.pool, seed_volume)
    owned_volumes: list[str] = []
    try:
        import_cloud_volume(
            configuration, provider, volume, cloud_image
        )
        owned_volumes.append(volume)
        staged_seed = stage_pool_file(
            configuration, provider, seed_volume, seed_iso
        )
        owned_volumes.append(seed_volume)
        arguments = common_domain_arguments(
            configuration,
            volume,
            memory_mib=6144,
            vcpus=4,
            osinfo="ubuntu24.04",
        )
        arguments.extend(
            [
                "--boot",
                "uefi",
                "--import",
                "--disk",
                f"path={staged_seed},device=cdrom,bus=sata,readonly=on",
            ]
        )
        define_domain(configuration, provider, arguments, name=name)
    except Exception:
        cleanup_failed_creation(
            provider, name, configuration.pool, owned_volumes
        )
        raise
    print("factory target created")


def cdrom_media(xml_text: str) -> list[tuple[str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise ProviderError(
            "domain_xml_invalid", "The provider returned invalid domain XML"
        ) from error
    media: list[tuple[str, str]] = []
    for disk in root.findall("./devices/disk[@device='cdrom']"):
        source = disk.find("source")
        target = disk.find("target")
        if source is None or not source.get("file") or target is None:
            raise ProviderError(
                "factory_media_shape_invalid",
                "The factory removable-media shape is invalid",
            )
        device = target.get("dev") or ""
        if not re.fullmatch(r"sd[a-z]", device):
            raise ProviderError(
                "factory_media_shape_invalid",
                "The factory removable-media target is invalid",
            )
        media.append((device, source.get("file") or ""))
    return sorted(media)


def cdrom_targets(xml_text: str) -> list[str]:
    return [target for target, _source in cdrom_media(xml_text)]


def detach_media(
    configuration: Configuration,
    provider: Libvirt,
    *,
    installer_only: bool,
) -> None:
    inspect_domain(configuration, provider)
    state = provider.text("domstate", configuration.expected_uuid).lower()
    if state != "shut off":
        raise ProviderError(
            "lifecycle_state_invalid", "Factory media detachment requires a stopped target"
        )
    before = cdrom_media(
        provider.text("dumpxml", "--inactive", configuration.expected_uuid)
    )
    expected = 2 if installer_only else 1
    if len(before) != expected:
        raise ProviderError(
            "factory_media_shape_invalid",
            "The factory removable-media shape is invalid",
        )
    seed_volume = f"{configuration.domain_name}.seed.iso"
    installer_volume = f"{configuration.domain_name}.installer.iso"
    expected_volumes = (
        {installer_volume, seed_volume} if installer_only else {seed_volume}
    )
    actual_volumes = {Path(source).name for _target, source in before}
    if actual_volumes != expected_volumes:
        raise ProviderError(
            "factory_media_shape_invalid",
            "The factory removable-media names are invalid",
        )
    selected = (
        [item for item in before if Path(item[1]).name == installer_volume]
        if installer_only
        else before
    )
    pool_path = require_local_pool_path(provider, configuration.pool)
    for _target, source in selected:
        expected_path = pool_path / Path(source).name
        if Path(source).resolve(strict=True) != expected_path.resolve(strict=True):
            raise ProviderError(
                "factory_media_shape_invalid",
                "Factory media is outside the exact dedicated pool",
            )
    for target, _source in selected:
        provider.command(
            "detach-disk", configuration.expected_uuid, target, "--config"
        )
    after = cdrom_media(
        provider.text("dumpxml", "--inactive", configuration.expected_uuid)
    )
    remaining = [item for item in before if item not in selected]
    if after != remaining:
        raise ProviderError(
            "factory_media_detach_unverified",
            "Factory media detachment could not be verified",
        )
    for _target, source in selected:
        volume = Path(source).name
        delete_volume(provider, configuration.pool, volume)
        if Path(source).exists() or provider.command(
            "vol-info", "--pool", configuration.pool, volume, check=False
        ).returncode == 0:
            raise ProviderError(
                "factory_media_cleanup_unverified",
                "Detached factory media cleanup could not be verified",
            )
    if installer_only:
        print("factory installer detached: seed_media_remaining=1")
    else:
        print("factory media detached: remaining=0")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    windows = subparsers.add_parser("create-windows")
    windows.add_argument("name")
    windows.add_argument("windows_iso")
    windows.add_argument("seed_iso")
    linux = subparsers.add_parser("create-linux")
    linux.add_argument("name")
    linux.add_argument("cloud_image")
    linux.add_argument("seed_iso")
    subparsers.add_parser("detach-installer")
    subparsers.add_parser("detach-media")
    return parser.parse_args()


def main() -> int:
    try:
        arguments = parse_arguments()
        configuration = Configuration.from_environment()
        provider = Libvirt(configuration)
        if arguments.command == "create-windows":
            create_windows(
                configuration,
                provider,
                arguments.name,
                arguments.windows_iso,
                arguments.seed_iso,
            )
        elif arguments.command == "create-linux":
            create_linux(
                configuration,
                provider,
                arguments.name,
                arguments.cloud_image,
                arguments.seed_iso,
            )
        elif arguments.command == "detach-installer":
            detach_media(configuration, provider, installer_only=True)
        elif arguments.command == "detach-media":
            detach_media(configuration, provider, installer_only=False)
        return 0
    except ProviderError as error:
        print(f"{error.code}: {error.message}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError):
        print("factory_failed: The provider factory failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
