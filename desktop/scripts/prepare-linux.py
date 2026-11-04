#!/usr/bin/env python3
"""Stage the ordinary-user adapter and unchanged shared AT-SPI provider."""

import argparse
import hashlib
import json
import importlib.util
import platform
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]


def stage(destination, revision, arch=None):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Exact source revision required")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    sources = list((ROOT / "desktop/native/linux").glob("*.py")) + [
        ROOT / "platforms/linux/guests/ubuntu/ui" / name for name in ["linuxcontrol.py", "linuxui.py"]]
    files = []
    for source in sorted(sources):
        shutil.copyfile(source, destination / source.name)
        files.append({"path": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                      "byteLength": source.stat().st_size})
    extension = destination / "extension"
    extension.mkdir()
    # Runtime files only: Web Store tooling, sources and docs stay behind.
    root = ROOT / "providers/chrome-extension"
    for source in sorted(root.rglob("*")):
        relative = source.relative_to(root)
        if source.suffix not in {".js", ".json", ".html", ".css", ".png"} or relative.parts[0] == "store":
            continue
        (extension / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, extension / relative)
        files.append({"path": "extension/" + relative.as_posix(),
                      "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                      "byteLength": source.stat().st_size})
    arch = arch or {"aarch64":"arm64", "arm64":"arm64", "x86_64":"x64"}[platform.machine().lower()]
    if arch not in {"arm64", "x64"}:
        raise ValueError("Linux runtime architecture required")
    spec = importlib.util.spec_from_file_location("policy_package", ROOT / "runtime/scripts/package.py")
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    cache = ROOT / ".artifacts/runtime-cache"
    cache.mkdir(parents=True, exist_ok=True)
    policy = destination / "shared-policy"
    package.build("node", "linux-" + arch, policy, cache, None)
    manifest = json.loads((policy / "payload.json").read_text())
    manifest.update(qualificationOnly=False, consumer="linux-desktop")
    (policy / "payload.json").write_text(json.dumps(manifest, indent=2) + "\n")
    policy_files=[]
    for path in sorted(policy.rglob("*")):
        if path.is_file():
            policy_files.append({"path":path.relative_to(policy).as_posix(),
                          "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                          "byteLength":path.stat().st_size})
    identity = {"schema": "machine-control-linux-desktop-runtime/v0", "sourceRevision": revision,
                "profile": "gnome_wayland", "privilege": "ordinary_user", "files": files,
                "policyFiles":policy_files, "policyInstallation":"usr_share",
                "policyPayloadProtocol":2, "admissionSchema":"machine-control-admission/v2", "architecture":arch}
    (destination / "desktop-runtime.json").write_text(json.dumps(identity, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", required=True)
    parser.add_argument("--destination", type=Path, default=ROOT / "desktop/src-tauri/native/linux-runtime")
    parser.add_argument("--arch", choices=["arm64", "x64"])
    args = parser.parse_args()
    stage(args.destination, args.revision, args.arch)
