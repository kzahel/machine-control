#!/usr/bin/env python3
"""Build the Chrome Web Store upload and its build record.

The store assigns and signs its own extension ID, so the development
manifest `key` is removed. Only files the extension loads are included,
with fixed timestamps so the same source produces the same bytes. The
build record lets the publisher refuse a dirty, mismatched or altered
candidate.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
STORE = json.loads((ROOT / "store/identity.json").read_text())
FILES = ["service_worker.js", "browser_cdp.js", "indicators.js", "requests.js",
         "panel.html", "panel.css", "panel.js",
         "icons/16.png", "icons/32.png", "icons/48.png", "icons/128.png"]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=pathlib.Path, help="directory to write")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "manifest.json").read_text())
    manifest.pop("key", None)
    version = manifest["version"]
    filename = f"machine-control-{version}.zip"
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / filename
    with zipfile.ZipFile(path, "w") as archive:
        entry(archive, "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())
        for name in FILES:
            entry(archive, name, (ROOT / name).read_bytes())
    build = {
        "version": version,
        "extensionId": STORE["id"],
        "revision": git("rev-parse", "HEAD"),
        "sourceDirty": git("status", "--porcelain") != "",
        "filename": filename,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    (args.output / "build.json").write_text(json.dumps(build, indent=2) + "\n")
    print(json.dumps(build))


if __name__ == "__main__":
    main()
