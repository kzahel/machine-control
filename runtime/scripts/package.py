"""Build private policy-host qualification payloads; no system installation.

Node ships its pinned runtime and original LICENSE, without npm, headers or a
system-runtime dependency. Bun compilation is an evaluated alternative. Neither
output is signed or an installed desktop candidate. Refuse existing outputs.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PINS = json.loads((ROOT / "toolchains.json").read_text())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def binary_target(path):
    with path.open("rb") as stream:
        header = stream.read(64)
        if header[:4] == b"\xcf\xfa\xed\xfe":
            cpu = struct.unpack_from("<I", header, 4)[0]
            return "darwin-" + {0x0100000c: "arm64", 0x01000007: "x64"}[cpu]
        if header[:4] == b"\x7fELF" and header[4:6] == b"\x02\x01":
            cpu = struct.unpack_from("<H", header, 18)[0]
            return "linux-" + {183: "arm64", 62: "x64"}[cpu]
        if header[:2] == b"MZ":
            stream.seek(struct.unpack_from("<I", header, 60)[0])
            pe = stream.read(6)
            if pe[:4] != b"PE\0\0":
                raise ValueError("Invalid PE header")
            return "win-" + {0xaa64: "arm64", 0x8664: "x64"}[struct.unpack_from("<H", pe, 4)[0]]
    raise ValueError("Unrecognized executable")


def node_payload(target, output, cache):
    pin = PINS["node"]
    suffix, sha = pin["archives"][target]
    name = f"node-v{pin['version']}-{target}"
    archive = cache / f"{name}.{suffix}"
    if not archive.exists():
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as download:
            temporary = Path(download.name)
            try:
                with urllib.request.urlopen(f"https://nodejs.org/download/release/v{pin['version']}/{archive.name}", timeout=120) as response:
                    shutil.copyfileobj(response, download)
                download.close()
                if digest(temporary) != sha:
                    raise ValueError("Node archive digest mismatch")
                temporary.replace(archive)
            finally:
                temporary.unlink(missing_ok=True)
    if digest(archive) != sha:
        raise ValueError("Cached Node archive digest mismatch")
    executable = "node.exe" if target.startswith("win-") else "node"
    members = {f"{name}/LICENSE": output / "LICENSE.node", f"{name}/{'node.exe' if target.startswith('win-') else 'bin/node'}": output / executable}
    if suffix == "zip":
        with zipfile.ZipFile(archive) as source:
            for member, destination in members.items():
                destination.write_bytes(source.read(member))
    else:
        with tarfile.open(archive) as source:
            for member, destination in members.items():
                with source.extractfile(member) as stream:
                    destination.write_bytes(stream.read())
    (output / executable).chmod(0o755)
    for directory in ("src", "node"):
        shutil.copytree(ROOT / directory, output / "policy" / directory)
    shutil.copytree(ROOT / "node_modules/ws", output / "policy/node_modules/ws")
    (output / "policy/package.json").write_text('{"type":"module"}\n')
    return executable, ["policy/node/main.ts"]


def build(engine, target, output, cache, bun):
    output.mkdir(parents=True, exist_ok=False)
    try:
        if engine == "node":
            executable, arguments = node_payload(target, output, cache)
        else:
            if subprocess.check_output([bun, "--version"], text=True).strip() != PINS["bun"]["version"]:
                raise ValueError("Bun compiler version mismatch")
            executable = "policy-host.exe" if target.startswith("win-") else "policy-host"
            bun_target = "windows-" + target[4:] if target.startswith("win-") else target
            if target.endswith("-x64"):
                bun_target += "-baseline"
            subprocess.run([bun, "build", "--compile", f"--target=bun-{bun_target}", str(ROOT / "node/main.ts"), "--outfile", str(output / executable)], check=True)
            arguments = []
        if binary_target(output / executable) != target:
            raise ValueError("Executable target mismatch")
        sources = {str(path.relative_to(ROOT)): digest(path) for directory in ("src", "node") for path in sorted((ROOT / directory).glob("*.ts"))}
        manifest = {
            "schema": "machine-control-policy-payload/v1", "qualificationOnly": True,
            "engine": engine, "engineVersion": PINS[engine]["version"], "target": target,
            "executable": executable, "arguments": arguments, "sourceSha256": sources,
            "files": {str(path.relative_to(output)): {"sha256": digest(path), "bytes": path.stat().st_size}
                      for path in sorted(output.rglob("*")) if path.is_file()},
        }
        (output / "payload.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return {"engine": engine, "target": target, "bytes": sum(item["bytes"] for item in manifest["files"].values()), "binaryTargetVerified": True}
    except BaseException:
        shutil.rmtree(output)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("node", "bun"), required=True)
    parser.add_argument("--target", choices=(*PINS["node"]["archives"], "all", "native"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=ROOT.parent / ".artifacts/runtime-cache")
    parser.add_argument("--bun", default="bun")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    if args.target == "native":
        host_os = {"darwin": "darwin", "linux": "linux", "win32": "win"}[sys.platform]
        host_arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}[platform.machine().lower()]
        args.target = host_os + "-" + host_arch
    targets = PINS["node"]["archives"] if args.target == "all" else [args.target]
    for target in targets:
        print(json.dumps(build(args.engine, target, args.output / target, args.cache, args.bun)), flush=True)
