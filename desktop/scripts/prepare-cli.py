#!/usr/bin/env python3
"""Package the Python client and a digest-pinned, relocatable CPython runtime."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SOURCES = [
    "bin/machine-control", "client/machine_control.py", "client/scoped_run.py",
    "client/scoped_process.py", "client/agent_interface.py", "client/control_session.py",
    "providers/claims/claims.py", "providers/claims/common.sh", "providers/claims/channel.py",
    "providers/claims/admission.py", "providers/claims/admission_channel.py", "client/claim_session.py", "client/outer_session.py",
    "platforms/macos/bin/machost", "platforms/macos/host/machost.py",
    "platforms/windows/host/winhost.py", "platforms/linux/host/linuxhost.py",
]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch(pin, cache):
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / (pin["sha256"] + ".tar.gz")
    if archive.is_file() and digest(archive) == pin["sha256"]:
        return archive
    descriptor, name = tempfile.mkstemp(dir=cache, prefix="python-download-")
    try:
        with os.fdopen(descriptor, "wb") as output:
            with urllib.request.urlopen(pin["url"], timeout=60) as response:
                shutil.copyfileobj(response, output)
        if digest(Path(name)) != pin["sha256"]:
            raise ValueError("Standalone Python archive digest mismatch")
        os.replace(name, archive)
    finally:
        Path(name).unlink(missing_ok=True)
    return archive


def extract(archive, destination):
    # Requires Python 3.12+ for the build, not a Python installation at runtime.
    with tarfile.open(archive) as source:
        members = source.getmembers()
        if any(not item.name.startswith("python/") for item in members):
            raise ValueError("Unexpected standalone Python archive root")
        # The CLI does not use curses. Linux terminfo aliases can differ only
        # by case, forming self-referential links on macOS build filesystems.
        # Omit this unused data before extraction, not after following links.
        members = [item for item in members
                   if item.name.rstrip("/") != "python/share/terminfo"
                   and not item.name.startswith("python/share/terminfo/")]
        source.extractall(destination, members=members, filter="data")
    runtime = destination / "python"
    # Flatten only internal links. Tauri resources and signed inventories must
    # contain regular files, so installed trust checks cover their exact bytes.
    for path in sorted(runtime.rglob("*")):
        if path.is_symlink():
            target = path.resolve(strict=True)
            if not target.is_relative_to(runtime.resolve()) or not target.is_file():
                raise ValueError("Unexpected standalone Python link")
            content = target.read_bytes()
            mode = target.stat().st_mode
            path.unlink()
            path.write_bytes(content)
            path.chmod(mode)
    # Editable scripts stay outside bytecode caches; do not ship pip or test data.
    for path in list(runtime.rglob("__pycache__")):
        shutil.rmtree(path)
    for path in list(runtime.rglob("site-packages")):
        shutil.rmtree(path)
    binaries = runtime / "bin"
    if binaries.exists():
        for path in binaries.iterdir():
            if path.name != "python3":
                path.unlink()


def stage(destination, target, version, revision, cache):
    pins = json.loads((ROOT / "desktop/python-runtime.lock.json").read_text())
    if (target not in pins["targets"] or not re.fullmatch(r"[0-9a-f]{40}", revision)
            or not re.fullmatch(r"\d+\.\d+\.\d+", version)):
        raise ValueError("Exact supported target, source and version required")
    archive = fetch(pins["targets"][target], cache)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix="cli-stage-") as tmp:
        output = Path(tmp) / "mc-cli"
        output.mkdir()
        extract(archive, output)
        shutil.copytree(ROOT / "desktop/python-licenses", output / "licenses")
        for name in SOURCES:
            file = output / name
            file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, file)
        bootstrap = output / "launch.py"
        bootstrap.write_text('''import os
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parent
if sys.platform == "win32":
    os.environ["MACHINE_CONTROL_DESKTOP_INSTALL_DIR"] = str(root.parent)
os.environ.pop("PYTHONHOME", None)
os.environ.pop("PYTHONPATH", None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, str(root / "client"))
sys.argv[0] = str(root / "bin/machine-control")
runpy.run_path(sys.argv[0], run_name="__main__")
''')
        commands = output / "commands"
        commands.mkdir()
        windows = "windows" in target
        if windows:
            shutil.copy2(ROOT / "desktop/native/windows-launch.py", output / "windows-launch.py")
            shutil.copy2(ROOT / "desktop/native/windows-path.py", output / "windows-path.py")
        command = commands / ("machine-control.cmd" if windows else "machine-control")
        if windows:
            command.write_text('@echo off\r\n"%~dp0..\\python\\python.exe" -I -B "%~dp0..\\launch.py" %*\r\n')
        else:
            command.write_text('''#!/bin/sh
set -eu
directory=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$directory/python/bin/python3" -I -B "$directory/launch.py" "$@"
''')
            command.chmod(0o755)
        platform = "windows" if windows else "macos" if "apple" in target else "linux"
        identity = {
            "schema": "machine-control-client-identity/v1", "clientProtocol": 1,
            "residentProtocol": "machine-control/v0", "distribution": "desktop",
            "version": version, "sourceRevision": revision, "target": target,
            "platform": platform, "pythonVersion": pins["pythonVersion"],
            "pythonArchiveSha256": pins["targets"][target]["sha256"],
            "command": "commands/" + command.name,
            "features": ["agent.instructions", "host.desktop", "host.browser", "host.claims"],
        }
        (output / "client-runtime.json").write_text(json.dumps(identity, indent=2) + "\n")
        # The platform signs/authenticates the receipt as part of the product.
        inventory(output)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(output), destination)


def inventory(root):
    files = [{"path": str(p.relative_to(root)).replace(os.sep, "/"),
              "sha256": digest(p), "byteLength": p.stat().st_size}
             for p in sorted(root.rglob("*")) if p.is_file()
             and p.relative_to(root).as_posix() not in {"files.json", "package.cat", "files.json.sig"}]
    (root / "files.json").write_text(json.dumps({"schema": "machine-control-client-files/v1",
                                               "files": files}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--destination", type=Path, default=ROOT / "desktop/src-tauri/native/mc-cli")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/python-runtime")
    args = parser.parse_args()
    stage(args.destination, args.target, args.version, args.revision, args.cache)
