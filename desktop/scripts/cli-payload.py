"""Inventory after native signing, or verify the complete installed CLI payload."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def verify(root):
    value = json.loads((root / "files.json").read_text())
    if value.get("schema") != "machine-control-client-files/v1":
        raise ValueError("Invalid CLI inventory")
    names = set()
    for item in value["files"]:
        name = item["path"]
        if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                or name.startswith("/") or any(p in {"", ".", ".."} for p in name.split("/"))
                or name in names):
            raise ValueError("Invalid CLI inventory path")
        names.add(name)
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item["byteLength"]:
            raise ValueError("Incomplete CLI payload")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                raise ValueError("CLI payload digest mismatch")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual - {"files.json", "package.cat", "files.json.sig"} != names:
        raise ValueError("Unexpected CLI payload")
    return json.loads((root / "client-runtime.json").read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["inventory", "verify"])
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.command == "inventory":
        spec = importlib.util.spec_from_file_location("prepare_cli", Path(__file__).with_name("prepare-cli.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.inventory(args.root)
    else:
        verify(args.root)
        print("Complete CLI payload verified")
