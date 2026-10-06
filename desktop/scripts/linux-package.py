#!/usr/bin/env python3
"""Inventory final Linux containers and authenticate updater bytes and version."""

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {"x86_64-unknown-linux-gnu": ("amd64", "x86_64"),
           "aarch64-unknown-linux-gnu": ("arm64", "aarch64")}
VERSION = r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(target, version, revision, run):
    if (target not in TARGETS or not re.fullmatch(VERSION, version)
            or not re.fullmatch(r"[0-9a-f]{40}", revision)
            or not re.fullmatch(r"[1-9]\d*\.[1-9]\d*", run)):
        raise ValueError("Exact Linux target, version, source and workflow required")


def packages(directory):
    values = []
    for suffix in (".AppImage", ".deb"):
        matches = list(directory.glob("*" + suffix))
        if len(matches) != 1 or matches[0].is_symlink():
            raise ValueError("Exactly one final Debian and AppImage package required")
        values.append(matches[0])
    return values


def inventory(directory, target, version, revision, purpose="candidate"):
    """Run on the native build architecture; read containers independently."""
    records = []
    for package in packages(directory):
        with tempfile.TemporaryDirectory(prefix="mc-linux-payload-") as tmp:
            root = Path(tmp)
            if package.suffix == ".deb":
                subprocess.run(["dpkg-deb", "-x", str(package.resolve()), str(root)], check=True)
                architecture = subprocess.check_output(["dpkg-deb", "-f", str(package), "Architecture"], text=True).strip()
                package_version = subprocess.check_output(["dpkg-deb", "-f", str(package), "Version"], text=True).strip()
                if architecture != TARGETS[target][0] or package_version != version:
                    raise ValueError("Debian package identity mismatch")
            else:
                package.chmod(package.stat().st_mode | 0o100)
                subprocess.run([str(package.resolve()), "--appimage-extract"], cwd=root, check=True,
                               stdout=subprocess.DEVNULL)
                root = root / "squashfs-root"
            runtimes = list(root.rglob("linux-runtime/desktop-runtime.json"))
            if len(runtimes) != 1:
                raise ValueError("Exactly one packaged ordinary-user runtime required")
            runtime = runtimes[0].parent
            metadata = json.loads(runtimes[0].read_text())
            if (metadata.get("schema") != "machine-control-linux-desktop-runtime/v0"
                    or metadata.get("sourceRevision") != revision
                    or metadata.get("profile") != "gnome_wayland"
                    or metadata.get("privilege") != "ordinary_user"
                    or metadata.get("purpose", "candidate") != purpose):
                raise ValueError("Packaged runtime identity mismatch")
            binary = root / "usr/bin/machine-control"
            compiled = json.loads(subprocess.check_output([str(binary), "--identity"], text=True))
            if (compiled.get("schema") != "machine-control-desktop-identity/v0"
                    or compiled.get("sourceRevision") != revision
                    or compiled.get("version") != version or compiled.get("platform") != "linux"
                    or compiled.get("arch") != TARGETS[target][1]
                    or compiled.get("purpose", "candidate") != purpose):
                raise ValueError("Compiled Linux identity mismatch")
            files = [{"name": "machine-control", "size": binary.stat().st_size, "sha256": digest(binary)}]
            entries = metadata.get("files", [])
            expected = {entry["path"] for entry in entries} | {"desktop-runtime.json"}
            actual = {str(file.relative_to(runtime)) for file in runtime.rglob("*") if file.is_file()}
            if expected != actual:
                raise ValueError("Uninventoried runtime payload")
            for name in sorted(expected):
                if not safe_name(name):
                    raise ValueError("Unsafe runtime inventory path")
                file = runtime / name
                if file.is_symlink():
                    raise ValueError("Runtime symlink is not a payload")
                entry = next((entry for entry in entries if entry["path"] == name), None)
                if entry and (entry["byteLength"] != file.stat().st_size or entry["sha256"] != digest(file)):
                    raise ValueError("Runtime source receipt mismatch")
                files.append({"name": "linux-runtime/" + name, "size": file.stat().st_size, "sha256": digest(file)})
            # linuxdeploy rewrites every ELF under usr/lib, even resource
            # interpreters. Keep the pinned CLI in usr/share in both formats.
            cli = root / "usr/share/machine-control/mc-cli"
            if tuple(map(int, version.split("."))) >= (0, 5, 3) and not cli.is_dir():
                raise ValueError("Required packaged Python CLI is missing")
            if cli.exists():
                spec = importlib.util.spec_from_file_location("cli_payload", ROOT / "desktop/scripts/cli-payload.py")
                helper = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(helper)
                identity = helper.verify(cli)
                if identity.get("sourceRevision") != revision or identity.get("version") != version or identity.get("target") != target:
                    raise ValueError("Packaged CLI identity mismatch")
                subprocess.run([sys.executable, str(ROOT / "tests/desktop/cli-installed.py"),
                                "--client", str(cli / "commands/machine-control")], check=True)
                for file in sorted(cli.rglob("*")):
                    if file.is_file():
                        files.append({"name": "mc-cli/" + file.relative_to(cli).as_posix(),
                                      "size": file.stat().st_size, "sha256": digest(file)})
            records.append({"package": package.name, "files": files})
    # Tauri patches the executable's bundle-type marker separately for Debian
    # and AppImage. Native identity is verified in each; resources must match.
    if records[0]["files"][1:] != records[1]["files"][1:]:
        raise ValueError("Debian and AppImage product payloads differ")
    value = {"schema": "machine-control-desktop-payload/v0", "platform": "linux",
             "target": target, "version": version, "sourceRevision": revision, "purpose": purpose, "packages": records}
    (directory / "payload.json").write_text(json.dumps(value, indent=2) + "\n")


def safe_name(name):
    return isinstance(name, str) and name and "\\" not in name and ":" not in name and not name.startswith("/") and all(
        part not in {"", ".", ".."} for part in name.split("/"))


def public_name(name, arch):
    if name == "payload.json":
        return "payload-linux-" + arch + ".json"
    # Tauri's ARM AppImage uses aarch64; Debian and public routes use arm64.
    # Receipts retain the original name and authenticated bytes.
    if arch == "arm64":
        name = name.replace("_aarch64.AppImage", "_arm64.AppImage", 1)
    return name.replace("Machine Control_", "MachineControl_", 1)


def evidence(directory, target, version, revision, run, purpose="candidate"):
    identity(target, version, revision, run)
    inventory(directory, target, version, revision, purpose)
    files = [file for package in packages(directory) for file in (package, Path(str(package) + ".sig"))]
    files.append(directory / "payload.json")
    value = {"schema": "machine-control-desktop-build/v0", "platform": "linux", "target": target,
             "arch": TARGETS[target][0], "version": version, "sourceRevision": revision,
             "bundleIdentifier": "org.machine-control.app", "sourceState": "ci_checkout",
             "workflowRun": run.split(".")[0], "workflowAttempt": run.split(".")[1],
             "purpose": purpose, "artifacts": [{"name": file.name, "size": file.stat().st_size, "sha256": digest(file)} for file in files]}
    (directory / "build.json").write_text(json.dumps(value, indent=2) + "\n")


def verify(directory, target, version, revision, run, tamper=False, published=False, purpose="candidate"):
    identity(target, version, revision, run)
    arch = TARGETS[target][0]
    receipt = "build-linux-" + arch + ".json" if published else "build.json"
    value = json.loads((directory / receipt).read_text())
    expected = {"schema": "machine-control-desktop-build/v0", "platform": "linux", "target": target,
                "arch": arch, "version": version, "sourceRevision": revision,
                "bundleIdentifier": "org.machine-control.app", "sourceState": "ci_checkout",
                "workflowRun": run.split(".")[0], "workflowAttempt": run.split(".")[1]}
    if published and purpose != "candidate":
        raise ValueError("Update sender fixtures cannot be published")
    if value.get("purpose", "candidate") != purpose or any(value.get(key) != item for key, item in expected.items()):
        raise ValueError("Linux candidate identity mismatch")
    def path(name):
        return directory / (public_name(name, arch) if published else name)
    names = set()
    for item in value.get("artifacts", []):
        name = item.get("name", "")
        if not safe_name(name) or "/" in name or name in names:
            raise ValueError("Unsafe or duplicate package name")
        names.add(name)
        file = path(name)
        if file.is_symlink() or file.stat().st_size != item["size"] or digest(file) != item["sha256"]:
            raise ValueError("Final Linux artifact bytes changed")
    images = [name for name in names if name.endswith(".AppImage")]
    debs = [name for name in names if name.endswith(".deb")]
    if (len(images) != 1 or len(debs) != 1 or
            names != {images[0], images[0] + ".sig", debs[0], debs[0] + ".sig", "payload.json"}):
        raise ValueError("Incomplete Linux package set")
    payload = json.loads(path("payload.json").read_text())
    if any(payload.get(key) != item for key, item in {
        "schema": "machine-control-desktop-payload/v0", "platform": "linux",
        "target": target, "version": version, "sourceRevision": revision}.items()):
        raise ValueError("Linux payload identity mismatch")
    if payload.get("purpose", "candidate") != purpose:
        raise ValueError("Linux payload purpose mismatch")
    records = payload.get("packages", [])
    if len(records) != 2 or {r.get("package") for r in records} != {images[0], debs[0]}:
        raise ValueError("Both final containers need payload inventories")
    if records[0].get("files", [])[1:] != records[1].get("files", [])[1:]:
        raise ValueError("Linux container payloads differ")
    required = {"machine-control", "linux-runtime/desktop-runtime.json", "linux-runtime/desktop.py",
                "linux-runtime/grants.py", "linux-runtime/portal.py", "linux-runtime/provider.py",
                "linux-runtime/approval.py", "linux-runtime/browser.py", "linux-runtime/browser_host.py",
                "linux-runtime/artifacts.py", "linux-runtime/shortcut.py", "linux-runtime/startup.py", "linux-runtime/linuxcontrol.py",
                "linux-runtime/linuxui.py", "linux-runtime/extension/manifest.json",
                "linux-runtime/extension/service_worker.js", "linux-runtime/extension/indicators.js"}
    if tuple(map(int, version.split("."))) >= (0, 5, 3):
        required.add("linux-runtime/updates.py")
    if tuple(map(int, version.split("."))) >= (0, 5, 4):
        required.add("linux-runtime/journal.py")
    if tuple(map(int, version.split("."))) >= (0, 5, 7):
        required.add("linux-runtime/extension/browser_cdp.js")
    for record in records:
        found = set()
        for item in record.get("files", []):
            name = item.get("name", "")
            if (not safe_name(name) or name in found or type(item.get("size")) is not int or item["size"] < 0
                    or (item["size"] == 0 and not name.startswith("mc-cli/"))
                    or not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", ""))):
                raise ValueError("Invalid Linux payload inventory")
            found.add(name)
        cli_names = {name for name in found if name.startswith("mc-cli/")}
        if (cli_names or tuple(map(int, version.split("."))) >= (0, 5, 3)) and not {
                "mc-cli/client-runtime.json", "mc-cli/files.json", "mc-cli/launch.py",
                              "mc-cli/commands/machine-control", "mc-cli/python/bin/python3"}.issubset(cli_names):
            raise ValueError("Incomplete packaged CLI")
        if found - cli_names != required or record["files"][0]["name"] != "machine-control":
            raise ValueError("Incomplete or unexpected ordinary-user Linux payload: "
                             f"missing={sorted(required - (found - cli_names))}, "
                             f"unexpected={sorted((found - cli_names) - required)}")
    with tempfile.TemporaryDirectory(prefix="mc-linux-auth-") as tmp:
        root = Path(tmp)
        config = json.loads((ROOT / "desktop/src-tauri/tauri.conf.json").read_text())
        public = root / "updater.pub"
        public.write_bytes(base64.b64decode(config["plugins"]["updater"]["pubkey"], validate=True))
        for name in (images[0], debs[0]):
            signature = root / "package.sig"
            signature.write_bytes(base64.b64decode(path(name + ".sig").read_text().strip(), validate=True))
            def authentic(file):
                return subprocess.run(["minisign", "-V", "-p", str(public), "-m", str(file), "-x", str(signature)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0
            if not authentic(path(name)):
                raise ValueError("Linux package signature failed")
            comments = [line for line in signature.read_text().splitlines() if line.startswith("trusted comment: ")]
            versions = [field.removeprefix("version:") for line in comments for field in line.split("\t") if field.startswith("version:")]
            if len(comments) != 1 or versions != [version]:
                raise ValueError("Authenticated Linux version mismatch")
            if tamper:
                modified = root / "tampered"
                with path(name).open("rb") as source, modified.open("wb") as dest:
                    import shutil
                    shutil.copyfileobj(source, dest)
                    dest.write(b"tampered")
                if authentic(modified):
                    raise ValueError("Modified Linux package accepted")
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["evidence", "verify"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--target", choices=TARGETS, required=True)
    for name in ("version", "revision", "run"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--test-tampering", action="store_true")
    parser.add_argument("--published", action="store_true")
    parser.add_argument("--purpose", choices=["candidate", "update_sender_fixture"], default="candidate")
    args = parser.parse_args()
    if args.command == "evidence":
        evidence(args.directory, args.target, args.version, args.revision, args.run, args.purpose)
    else:
        verify(args.directory, args.target, args.version, args.revision, args.run,
               args.test_tampering, args.published, args.purpose)
        print("Linux package signatures, signed versions, provenance and tamper rejection verified")
