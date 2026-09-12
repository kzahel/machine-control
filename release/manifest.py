#!/usr/bin/env python3
"""Create and verify the complete, signed, non-release smoke artifact set."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

SCHEMA = "machine-control-signing-smoke-manifest/v0"
PACKAGES = {
    "windows-x64": "machine-control-signing-smoke-windows-x64.zip",
    "macos-arm64": "machine-control-signing-smoke-macos-arm64.zip",
    "linux-x64": "machine-control-signing-smoke-linux-x64.tar.gz",
}
PUBLIC_KEY = Path(__file__).with_name("machine-control.pub")


def artifact(path, target):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing regular artifact: {path.name}")
    size = path.stat().st_size
    if size == 0:
        raise ValueError(f"Empty artifact: {path.name}")
    return {"target": target, "file": path.name, "size": size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def create(directory, revision, run):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Expected a full source revision")
    if not re.fullmatch(r"[0-9]+\.[0-9]+", run):
        raise ValueError("Expected workflow run ID and attempt")
    value = {
        "schema": SCHEMA,
        "purpose": "signing-smoke-only",
        "sourceRevision": revision,
        "workflowRun": run,
        "artifacts": [artifact(directory / name, target)
                      for target, name in sorted(PACKAGES.items())],
    }
    (directory / "manifest.json").write_text(
        json.dumps(value, indent=2) + "\n", encoding="utf-8")


def verify(directory, revision, run, public_key=PUBLIC_KEY):
    manifest = directory / "manifest.json"
    # Authenticate the exact bytes before trusting names, hashes, or metadata.
    subprocess.run(["minisign", "-V", "-q", "-p", str(public_key),
                    "-m", str(manifest)], check=True)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if (value.get("schema") != SCHEMA
            or value.get("purpose") != "signing-smoke-only"
            or value.get("sourceRevision") != revision
            or value.get("workflowRun") != run):
        raise ValueError("Manifest identity does not match the requested build")
    expected = [artifact(directory / name, target)
                for target, name in sorted(PACKAGES.items())]
    if value.get("artifacts") != expected:
        raise ValueError("Incomplete or modified artifact set")
    print("Verified all three packages and their signed build identity")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("create", "verify"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    {"create": create, "verify": verify}[args.command](
        args.directory, args.revision, args.run)
