#!/usr/bin/env python3
"""Build/package an inert native signing fixture; never install a resident."""

import argparse
import json
from pathlib import Path
import plistlib
import platform
import re
import shutil
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("windows-x64", "macos-arm64", "linux-x64")
APP_NAME = "Machine Control Signing Smoke.app"


def revision():
    value = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Expected an exact source revision")
    return value


def build(target, output):
    host = (platform.system(), platform.machine().lower())
    allowed = {
        "windows-x64": ("Windows", {"amd64", "x86_64"}),
        "macos-arm64": ("Darwin", {"arm64"}),
        "linux-x64": ("Linux", {"x86_64", "amd64"}),
    }
    system, architectures = allowed[target]
    if host[0] != system or host[1] not in architectures:
        raise ValueError("The smoke target must match its native build host")
    output.mkdir(parents=True, exist_ok=True)
    source_revision = revision()
    (output / "smoke_identity.h").write_text(
        f'#define MC_PLATFORM "{target}"\n'
        f'#define MC_REVISION "{source_revision}"\n', encoding="utf-8"
    )
    binary = output / ("machine-control-smoke.exe" if target == "windows-x64"
                       else "machine-control-smoke")
    source = ROOT / "release/smoke.c"
    if target == "windows-x64":
        command = ["cl", "/nologo", "/W4", "/WX", "/O2", "/MT",
                   f"/I{output}", str(source), f"/Fe{binary}"]
    else:
        command = ["cc", "-O2", "-Wall", "-Wextra", "-Werror",
                   "-I", str(output), str(source), "-o", str(binary)]
        if target == "macos-arm64":
            command.extend(["-arch", "arm64", "-mmacosx-version-min=13.0"])
    subprocess.run(command, cwd=output, check=True)
    observed = json.loads(subprocess.check_output([str(binary)], text=True))
    assert observed == {
        "schema": "machine-control-signing-smoke/v0",
        "platform": target,
        "sourceRevision": source_revision,
    }, "Native build identity did not match its source"
    if target == "macos-arm64":
        contents = output / APP_NAME / "Contents"
        for directory in ("MacOS", "Helpers", "Resources"):
            (contents / directory).mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, contents / "MacOS/machine-control-smoke")
        shutil.copy2(binary, contents / "Helpers/machine-control-smoke-helper")
        shutil.copy2(ROOT / "LICENSE", contents / "Resources/LICENSE")
        with (contents / "Info.plist").open("wb") as stream:
            plistlib.dump({
                "CFBundleIdentifier": "dev.machinecontrol.signing-smoke",
                "CFBundleName": "Machine Control Signing Smoke",
                "CFBundleExecutable": "machine-control-smoke",
                "CFBundlePackageType": "APPL",
                "CFBundleShortVersionString": "0.0.1",
                "CFBundleVersion": "1",
                "LSMinimumSystemVersion": "13.0",
                "LSUIElement": True,
            }, stream)
    print(json.dumps(observed))


def package(target, output):
    packages = output / "packages"
    packages.mkdir(exist_ok=True)
    prefix = f"machine-control-signing-smoke-{target}"
    if target == "macos-arm64":
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(output / APP_NAME), str(packages / f"{prefix}.zip")],
                       check=True)
    elif target == "windows-x64":
        with zipfile.ZipFile(packages / f"{prefix}.zip", "w",
                             zipfile.ZIP_DEFLATED) as archive:
            archive.write(output / "machine-control-smoke.exe",
                          "machine-control-smoke.exe")
            archive.write(ROOT / "LICENSE", "LICENSE")
    else:
        with tarfile.open(packages / f"{prefix}.tar.gz", "w:gz") as archive:
            archive.add(output / "machine-control-smoke",
                        arcname="machine-control-smoke")
            archive.add(ROOT / "LICENSE", arcname="LICENSE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "package"))
    parser.add_argument("target", choices=TARGETS)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    {"build": build, "package": package}[args.command](
        args.target, args.output.resolve())
