#!/usr/bin/env python3
"""Read Windows image indexes from an ISO without exposing local media paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def catalog(iso: Path, root: Path) -> dict:
    if not iso.is_file() or not os.access(iso, os.R_OK):
        raise ValueError("installation_media_unavailable")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    with tempfile.TemporaryDirectory(prefix=".catalog-", dir=root) as directory:
        image = Path(directory) / "install.wim"
        with image.open("wb") as output:
            result = subprocess.run(
                ["7z", "x", "-so", str(iso), "sources/install.wim"],
                stdout=output, stderr=subprocess.DEVNULL, timeout=180,
                check=False,
            )
        if result.returncode != 0 or image.stat().st_size < 1024 * 1024:
            raise ValueError("installation_catalog_unavailable")
        document = subprocess.run(
            ["wimlib-imagex", "info", str(image), "--xml"],
            capture_output=True, timeout=30, check=False,
        )
        if document.returncode != 0:
            raise ValueError("installation_catalog_invalid")
        try:
            xml = ET.fromstring(document.stdout)
        except ET.ParseError as error:
            raise ValueError("installation_catalog_invalid") from error
        images = []
        for item in xml.findall("IMAGE"):
            index = item.get("INDEX", "")
            if not index.isdecimal():
                raise ValueError("installation_catalog_invalid")
            images.append({
                "index": int(index),
                "name": item.findtext("NAME") or "",
                "flags": item.findtext("FLAGS") or "",
            })
        if not images:
            raise ValueError("installation_catalog_empty")
        return {"schema": "winvm-image-catalog/v0", "images": images}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: image-catalog.py WINDOWS_ISO", file=sys.stderr)
        return 2
    root = Path(os.environ.get(
        "WINVM_FACTORY_LOCAL_ROOT",
        str(Path(__file__).resolve().parents[1] / ".factory.local"),
    ))
    try:
        print(json.dumps(catalog(Path(sys.argv[1]), root), sort_keys=True))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        code = str(error) if isinstance(error, ValueError) else "catalog_probe_failed"
        print(code, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
