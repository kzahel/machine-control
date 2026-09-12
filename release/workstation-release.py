#!/usr/bin/env python3
"""Create and verify the consumer release contract over signed Windows archives."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess

spec = importlib.util.spec_from_file_location("preview", Path(__file__).with_name("workstation-manifest.py"))
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)
SCHEMA = "machine-control-workstation-release/v1"


def create(directory, revision, run, version, publisher):
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("Expected a stable semantic version")
    if not publisher or publisher != publisher.strip() or len(publisher) > 256:
        raise ValueError("Expected the configured Windows publisher")
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or not re.fullmatch(r"[0-9]+\.[0-9]+", run):
        raise ValueError("Expected exact source and workflow identity")
    value = {
        "schema": SCHEMA, "version": version,
        "tag": "workstation-v" + version, "protocol": "machine-control/v0",
        "consumerProtocol": 1, "sourceRevision": revision, "workflowRun": run,
        "publisher": publisher,
        "artifacts": [preview.artifact(directory / name, target)
                      for target, name in sorted(preview.PACKAGES.items())],
    }
    (directory / "release.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def verify(directory, revision, run, version, publisher, public_key=preview.PUBLIC_KEY):
    manifest = directory / "release.json"
    subprocess.run(["minisign", "-V", "-q", "-p", str(public_key), "-m", str(manifest)], check=True)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if (value.get("schema") != SCHEMA or value.get("version") != version
            or value.get("tag") != "workstation-v" + version
            or value.get("protocol") != "machine-control/v0" or value.get("consumerProtocol") != 1
            or value.get("publisher") != publisher or value.get("sourceRevision") != revision
            or value.get("workflowRun") != run):
        raise ValueError("Release identity mismatch")
    expected = [preview.artifact(directory / name, target) for target, name in sorted(preview.PACKAGES.items())]
    if value.get("artifacts") != expected:
        raise ValueError("Incomplete or modified artifact set")
    print("Verified release identity and both Windows archives")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("create", "verify"))
    parser.add_argument("directory", type=Path)
    for field in ("revision", "run", "version", "publisher"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    {"create": create, "verify": verify}[args.command](
        args.directory, args.revision, args.run, args.version, args.publisher)
