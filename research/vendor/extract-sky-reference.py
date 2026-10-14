#!/usr/bin/env python3
"""Extract a local, Git-ignored reference copy of Codex Computer Use's
JavaScript layer, type declarations and bundled documentation.

The source is the installed ChatGPT desktop app and the Codex plugin cache on
this machine. The extracted files are proprietary: they stay in the ignored
output directory for study and must never be committed or published. Native
executables are recorded by version and hash only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

TEXT_SUFFIXES = {".js", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".json", ".md", ".txt", ".map"}
PLUGINS = ("computer-use", "unified-computer-use", "browser", "chrome")
HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bundle_info(app: Path) -> dict[str, object]:
    info: dict[str, object] = {"path": str(app), "present": app.is_dir()}
    plist = app / "Contents/Info.plist"
    if plist.is_file():
        with plist.open("rb") as stream:
            values = plistlib.load(stream)
        info.update(bundleId=values.get("CFBundleIdentifier"),
                    version=values.get("CFBundleShortVersionString"),
                    build=values.get("CFBundleVersion"))
    signing = subprocess.run(["codesign", "-dv", str(app)], capture_output=True, text=True)
    for line in signing.stderr.splitlines():
        if line.startswith(("TeamIdentifier=", "Identifier=")):
            key, _, value = line.partition("=")
            info["signing" + key] = value
    return info


def copy_text_tree(source: Path, destination: Path, files: list[dict[str, object]], label: str) -> None:
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.suffix not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(source)
        if "node_modules" in relative.parts:
            continue  # Third-party dependencies are not the reference.
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        files.append({"source": label, "path": str(target.relative_to(destination.parents[0])),
                      "bytes": path.stat().st_size, "sha256": digest(path)})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=Path("/Applications/ChatGPT.app"))
    parser.add_argument("--codex-home", type=Path,
                        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--output", type=Path, default=HERE / "sky")
    parser.add_argument("--format", action="store_true",
                        help="Pretty-print extracted JavaScript with `npx prettier` (downloads it)")
    args = parser.parse_args()

    modules = args.app / "Contents/Resources/cua_node/lib/node_modules/@oai"
    if not modules.is_dir():
        print(f"No Computer Use JavaScript layer under {args.app}", file=sys.stderr)
        return 1
    app = bundle_info(args.app)
    root = args.output / str(app.get("version") or "unknown")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    files: list[dict[str, object]] = []
    packages = {}
    for package in sorted(modules.iterdir()):
        if package.is_dir():
            copy_text_tree(package, root / "oai" / package.name, files, "chatgpt-app")
            manifest = package / "package.json"
            if manifest.is_file():
                packages[f"@oai/{package.name}"] = json.loads(manifest.read_text()).get("version")
    plugins = {}
    cache = args.codex_home / "plugins/cache/openai-bundled"
    for name in PLUGINS:
        versions = sorted(p for p in (cache / name).glob("*") if p.is_dir() and not p.is_symlink())
        if versions:
            copy_text_tree(versions[-1], root / "plugins" / name, files, "codex-plugin-cache")
            plugins[name] = versions[-1].name
    service = args.codex_home / "computer-use/Codex Computer Use.app"
    native = bundle_info(service)
    executable = service / "Contents/MacOS/SkyComputerUseService"
    if executable.is_file():
        native["executableSha256"] = digest(executable)
        native["executableBytes"] = executable.stat().st_size

    if args.format:
        scripts = [str(p) for p in root.rglob("*") if p.suffix in {".js", ".mjs", ".cjs"}]
        if scripts:
            subprocess.run(["npx", "--yes", "prettier", "--log-level", "warn", "--write", *scripts],
                           check=False)

    (root / "manifest.json").write_text(json.dumps({
        "schema": "machine-control-sky-reference/v0",
        "extractedAt": datetime.now(timezone.utc).isoformat(),
        "notice": "Proprietary reference for local study only. Do not commit or publish.",
        "chatgptApp": app, "packages": packages, "plugins": plugins, "nativeService": native,
        "formatted": args.format, "files": files,
    }, indent=2) + "\n")
    print(f"Extracted {len(files)} files to {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
