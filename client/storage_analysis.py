"""Private, read-only disk-image discovery. Review is never deletion authority."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import sys

SCHEMA = "machine-control-storage-analysis/v0"
EXTENSIONS = {".qcow", ".qcow2", ".raw", ".img", ".iso", ".vhd", ".vhdx",
              ".vmdk", ".vdi", ".hdd", ".dmg", ".ipsw", ".sparseimage"}


def default_roots() -> list[Path]:
    home = Path.home()
    source = Path(__file__).resolve().parents[1]
    roots = [home / ".tart", home / ".local/share/machine-control",
             home / "Library/Containers/com.utmapp.UTM/Data",
             home / "Library/Containers/com.docker.docker/Data/vms",
             home / "Library/Application Support/Claude/vm_bundles",
             home / ".android/avd", home / "Android/Sdk/system-images"]
    for platform, legacy in (("windows", "winvm-testbed"),
                             ("linux", "linuxvm-testbed"),
                             ("macos", "macvm-testbed")):
        roots += [source / "platforms" / platform / ".factory.local",
                  source.parent / legacy / ".factory.local"]
    if sys.platform == "win32":
        roots += [home / "VirtualBox VMs", home / "Documents/Virtual Machines"]
    return roots


def category(path: Path) -> str:
    parts = set(path.parts)
    if ".factory.local" in parts:
        return "factory_artifact_review"
    if ".tart" in parts or any(p.endswith(".utm") and p != "com.utmapp.UTM"
                                for p in parts):
        return "provider_disk"
    if "com.docker.docker" in parts or "vm_bundles" in parts:
        return "application_managed_disk"
    if "avd" in parts or "system-images" in parts or "CoreSimulator" in parts:
        return "development_image"
    return "image_review"


def analyze(roots: list[Path], *, minimum_bytes: int = 1048576,
            max_files: int = 5000000, max_results: int = 5000) -> dict:
    images, errors, volumes, skipped = [], [], [], 0
    inspected, total_logical, total_allocated = 0, 0, 0
    seen_files, seen_directories, seen_devices = set(), set(), set()
    complete = True

    def error(path: Path, reason: str) -> None:
        nonlocal complete
        complete = False
        if len(errors) < 100:
            errors.append({"path": str(path), "reason": reason})

    for supplied in roots:
        # Do not resolve links into another library or a network filesystem.
        root = Path(os.path.abspath(supplied.expanduser()))
        if root.is_symlink():
            error(root, "symlink_root_not_followed")
            continue
        if not root.exists():
            continue
        try:
            info = root.stat()
            if info.st_dev not in seen_devices:
                usage = shutil.disk_usage(root)
                volumes.append({"root": str(root), "totalBytes": usage.total,
                                "freeBytes": usage.free})
                seen_devices.add(info.st_dev)
        except OSError:
            error(root, "unreadable_root")
            continue
        stack = [root]
        while stack:
            directory = stack.pop()
            try:
                info = directory.stat(follow_symlinks=False)
                identity = (info.st_dev, info.st_ino)
                if identity in seen_directories:
                    continue
                seen_directories.add(identity)
                with os.scandir(directory) as entries:
                    for entry in entries:
                        path = Path(entry.path)
                        if entry.is_symlink():
                            skipped += 1
                            continue
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                # Secret custody has no disk-prune surface.
                                if entry.name != "secrets":
                                    stack.append(path)
                                continue
                            inspected += 1
                            if inspected > max_files:
                                error(directory, "file_scan_limit")
                                stack.clear()
                                break
                            if path.suffix.lower() not in EXTENSIONS:
                                continue
                            info = entry.stat(follow_symlinks=False)
                            if not stat.S_ISREG(info.st_mode) or info.st_size < minimum_bytes:
                                continue
                            identity = (info.st_dev, info.st_ino)
                            if identity in seen_files:
                                continue
                            seen_files.add(identity)
                            allocated = (info.st_blocks * 512
                                         if hasattr(info, "st_blocks") else None)
                            total_logical += info.st_size
                            if allocated is not None:
                                total_allocated += allocated
                            else:
                                complete = False
                            if len(images) < max_results:
                                images.append({"path": str(path), "category": category(path),
                                               "logicalBytes": info.st_size,
                                               "allocatedBytes": allocated,
                                               "modifiedAtEpoch": info.st_mtime,
                                               "automaticDeletionAllowed": False})
                            else:
                                error(directory, "result_limit")
                        except OSError:
                            error(path, "entry_unreadable")
            except OSError:
                error(directory, "directory_unreadable")
        if inspected > max_files:
            break
    images.sort(key=lambda value: value["allocatedBytes"] or 0, reverse=True)
    return {"schema": SCHEMA, "readOnly": True, "roots": [str(p) for p in roots],
            "images": images, "volumes": volumes,
            "summary": {"filesInspected": inspected, "imagesFound": len(seen_files),
                        "logicalBytes": total_logical,
                        "allocatedBytes": total_allocated,
                        "exclusiveBytes": None, "reclaimableBytes": None},
            "coverage": {"complete": complete, "symlinksSkipped": skipped,
                         "errors": errors, "minimumBytes": minimum_bytes,
                         "limitations": ["No provider registration or live-use proof",
                                         "Allocated bytes may include shared APFS extents",
                                         "No deletion or credential/VM cleanup authorization",
                                         "Concurrent writes may change measurements"]}}


def handle(arguments: list[str]) -> dict:
    parser = argparse.ArgumentParser(prog="machine-control storage analyze")
    parser.add_argument("operation", choices=["analyze"])
    parser.add_argument("--root", action="append", type=Path)
    parser.add_argument("--minimum-bytes", type=int, default=1048576)
    parser.add_argument("--max-files", type=int, default=5000000)
    parser.add_argument("--max-results", type=int, default=5000)
    options = parser.parse_args(arguments)
    if options.minimum_bytes < 0 or options.max_files < 1 or not 1 <= options.max_results <= 50000:
        parser.error("positive scan/result limits and nonnegative size required")
    return analyze(options.root or default_roots(), minimum_bytes=options.minimum_bytes,
                   max_files=options.max_files, max_results=options.max_results)
