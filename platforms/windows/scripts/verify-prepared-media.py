#!/usr/bin/env python3
"""Verify a private no-prompt ISO against its source Windows ISO."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def boot_extent(path: Path) -> tuple[int, int]:
    with path.open("rb") as source:
        catalog_lba = None
        for sector in range(16, 64):
            source.seek(sector * 2048)
            descriptor = source.read(2048)
            if (descriptor[:1] == b"\x00" and descriptor[1:6] == b"CD001"
                    and descriptor[7:30] == b"EL TORITO SPECIFICATION"):
                catalog_lba = int.from_bytes(descriptor[71:75], "little")
                break
        if not catalog_lba:
            raise ValueError("boot_catalog_unavailable")
        source.seek(catalog_lba * 2048)
        catalog = source.read(2048)
        if catalog[30:32] != b"\x55\xaa":
            raise ValueError("boot_catalog_invalid")
        entry = None
        if catalog[1] == 0xEF and catalog[32] == 0x88:
            entry = catalog[32:64]
        offset = 64
        while entry is None and offset + 32 <= len(catalog):
            header = catalog[offset:offset + 32]
            if header[0] == 0:
                break
            if header[0] not in (0x90, 0x91):
                offset += 32
                continue
            count = int.from_bytes(header[2:4], "little")
            for index in range(1, count + 1):
                candidate = catalog[offset + index * 32:offset + (index + 1) * 32]
                if header[1] == 0xEF and len(candidate) == 32 and candidate[0] == 0x88:
                    entry = candidate
                    break
            offset += (count + 1) * 32
        if entry is None:
            raise ValueError("efi_boot_entry_unavailable")
        lba = int.from_bytes(entry[8:12], "little")
        source.seek(lba * 2048)
        sector = source.read(512)
        size = int.from_bytes(sector[11:13], "little") * (
            int.from_bytes(sector[19:21], "little") or
            int.from_bytes(sector[32:36], "little")
        )
        if sector[11:13] != b"\x00\x02" or not 65536 <= size <= 67108864:
            raise ValueError("efi_boot_image_invalid")
        return lba * 2048, size


def equal_span(source, prepared, length: int) -> bool:
    while length:
        size = min(length, 4 * 1024 * 1024)
        if source.read(size) != prepared.read(size):
            return False
        length -= size
    return True


def verify(source_path: Path, prepared_path: Path) -> dict:
    if not source_path.is_file() or not prepared_path.is_file():
        raise ValueError("media_unavailable")
    if os.path.samefile(source_path, prepared_path):
        raise ValueError("prepared_media_is_source")
    size = source_path.stat().st_size
    if size < 1024 * 1024 * 1024 or prepared_path.stat().st_size != size:
        raise ValueError("media_size_mismatch")
    offset, length = boot_extent(source_path)
    if offset + length > size:
        raise ValueError("efi_boot_extent_invalid")
    if boot_extent(prepared_path) != (offset, length):
        raise ValueError("boot_extent_mismatch")
    with source_path.open("rb") as source, prepared_path.open("rb") as prepared:
        if not equal_span(source, prepared, offset):
            raise ValueError("prepared_media_outside_boot_changed")
        source.seek(offset + length)
        prepared.seek(offset + length)
        if not equal_span(source, prepared, size - offset - length):
            raise ValueError("prepared_media_outside_boot_changed")
        prepared.seek(offset)
        image = prepared.read(length)
    loader = subprocess.run(
        ["7z", "x", "-so", str(source_path),
         "efi/microsoft/boot/cdboot_noprompt.efi"],
        capture_output=True, timeout=30, check=False,
    )
    if loader.returncode != 0 or not loader.stdout:
        raise ValueError("source_no_prompt_loader_unavailable")
    with tempfile.TemporaryDirectory(prefix="winvm-verify-") as directory:
        root = Path(directory)
        boot_image = root / "efi.img"
        boot_image.write_bytes(image)
        extracted = root / "loader.efi"
        for name in ("BOOTX64.EFI", "BOOTAA64.EFI"):
            result = subprocess.run(
                ["mcopy", "-i", str(boot_image), f"::/EFI/BOOT/{name}",
                 str(extracted)],
                capture_output=True, timeout=30, check=False,
            )
            if result.returncode == 0:
                break
        else:
            raise ValueError("prepared_boot_loader_unavailable")
        if extracted.read_bytes() != loader.stdout:
            raise ValueError("prepared_no_prompt_loader_mismatch")
    return {"schema": "winvm-prepared-media-verification/v0", "ready": True,
            "evidence": "source_identical_outside_efi_and_no_prompt_loader_exact"}


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: verify-prepared-media.py SOURCE_ISO PREPARED_ISO",
              file=sys.stderr)
        return 2
    try:
        result = verify(Path(sys.argv[1]), Path(sys.argv[2]))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        reason = str(error) if isinstance(error, ValueError) else "verification_failed"
        result = {"schema": "winvm-prepared-media-verification/v0",
                  "ready": False, "reason": reason}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
