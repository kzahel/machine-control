#!/usr/bin/env python3
"""Build the Chrome Web Store upload zip.

The store assigns and signs its own extension ID, so the development
manifest `key` is removed. Only files the extension loads are included.
"""
import argparse
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
FILES = ["service_worker.js", "browser_cdp.js", "indicators.js",
         "panel.html", "panel.css", "panel.js",
         "icons/16.png", "icons/32.png", "icons/48.png", "icons/128.png"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=pathlib.Path, help="zip file to write")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "manifest.json").read_text())
    manifest.pop("key", None)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
        for name in FILES:
            archive.write(ROOT / name, name)
    print(f"{args.output} (version {manifest['version']})")


if __name__ == "__main__":
    main()
