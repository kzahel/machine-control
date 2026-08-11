#!/usr/bin/env python3
"""Private receipt storage with a minimized public workspace projection."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sys
from typing import Any


SCHEMA = "machine-control-workspace-receipt/v0"
HANDLE_PATTERN = re.compile(r"w-[A-Za-z0-9][A-Za-z0-9._-]{7,127}")
INTENTS = {"persistent", "isolated", "candidate"}
MECHANISMS = {
    "existing_instance",
    "provider_disposable_overlay",
    "filesystem_cow_clone",
    "qcow_backing_overlay",
    "full_copy",
    "fresh_provision",
}
RETENTIONS = {"retained", "discardOnRelease"}
CLEANUPS = {"none", "release", "pending"}
STATES = {"off", "running", "unknown"}
FIELD_PATHS = {
    "provider": ("provider",),
    "intent": ("intent",),
    "mechanism": ("mechanism",),
    "retention": ("retention",),
    "cleanup": ("cleanup",),
    "state": ("state",),
    "target.name": ("target", "name"),
    "target.id": ("target", "id"),
    "source.name": ("source", "name"),
    "source.id": ("source", "id"),
}


class ReceiptError(Exception):
    pass


def valid_handle(value: str) -> bool:
    return HANDLE_PATTERN.fullmatch(value) is not None


def state_directory(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ReceiptError("receipt state directory must be absolute")
    if path.exists() and (not path.is_dir() or path.is_symlink()):
        raise ReceiptError("receipt state path is not a private directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        path.chmod(0o700)
    return path


def receipt_path(directory: Path, handle: str) -> Path:
    if not valid_handle(handle):
        raise ReceiptError("invalid workspace handle")
    return directory / f"{handle}.json"


def _write_exclusive(path: Path, value: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, separators=(",", ":"), sort_keys=True)
            output.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    if os.name != "nt":
        path.chmod(0o600)


def _write_replace(path: Path, value: dict[str, Any]) -> None:
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}"
    _write_exclusive(temporary, value)
    os.replace(temporary, path)
    if os.name != "nt":
        path.chmod(0o600)


def _private_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or "\0" in value:
        raise ReceiptError(f"receipt {name} is invalid")
    return value


def validate_receipt(value: Any, expected_handle: str | None = None) -> dict[str, Any]:
    required = {
        "schema", "handle", "createdAt", "provider", "intent", "mechanism",
        "retention", "cleanup", "state", "target",
    }
    if not isinstance(value, dict):
        raise ReceiptError("receipt shape is invalid")
    keys = set(value)
    if keys != required and keys != required | {"source"}:
        raise ReceiptError("receipt shape is invalid")
    handle = value.get("handle")
    if (
        not isinstance(handle, str)
        or not valid_handle(handle)
        or (expected_handle is not None and handle != expected_handle)
        or value.get("schema") != SCHEMA
        or value.get("intent") not in INTENTS
        or value.get("mechanism") not in MECHANISMS
        or value.get("retention") not in RETENTIONS
        or value.get("cleanup") not in CLEANUPS
        or value.get("state") not in STATES
    ):
        raise ReceiptError("receipt value is invalid")
    _private_text(value.get("createdAt"), "createdAt")
    _private_text(value.get("provider"), "provider")
    target = value.get("target")
    if not isinstance(target, dict) or set(target) != {"name", "id"}:
        raise ReceiptError("receipt target is invalid")
    _private_text(target.get("name"), "target name")
    _private_text(target.get("id"), "target id")
    source = value.get("source")
    if source is not None:
        if not isinstance(source, dict) or set(source) != {"name", "id"}:
            raise ReceiptError("receipt source is invalid")
        _private_text(source.get("name"), "source name")
        _private_text(source.get("id"), "source id")
    return value


def load_receipt(directory: Path, handle: str) -> dict[str, Any]:
    path = receipt_path(directory, handle)
    if not path.is_file() or path.is_symlink():
        raise ReceiptError("workspace receipt not found")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReceiptError("workspace receipt is unreadable") from error
    return validate_receipt(value, handle)


def load_all(directory: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for path in sorted(directory.glob("w-*.json")):
        if path.is_symlink() or not path.is_file():
            raise ReceiptError("workspace receipt entry is unsafe")
        handle = path.name.removesuffix(".json")
        receipts.append(load_receipt(directory, handle))
    return receipts


def public_item(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "handle": receipt["handle"],
        "intent": receipt["intent"],
        "actualMechanism": receipt["mechanism"],
        "retention": receipt["retention"],
        "state": receipt["state"],
        "cleanup": receipt["cleanup"],
    }


def command_create(args: argparse.Namespace) -> int:
    directory = state_directory(args.state_dir)
    handle = f"w-{secrets.token_hex(12)}"
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "handle": handle,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "provider": args.provider,
        "intent": args.intent,
        "mechanism": args.mechanism,
        "retention": args.retention,
        "cleanup": args.cleanup,
        "state": args.state,
        "target": {"name": args.target_name, "id": args.target_id},
    }
    if args.source_name is not None or args.source_id is not None:
        if not args.source_name or not args.source_id:
            raise ReceiptError("source name and id must be supplied together")
        receipt["source"] = {"name": args.source_name, "id": args.source_id}
    validate_receipt(receipt)
    _write_exclusive(receipt_path(directory, handle), receipt)
    print(handle)
    return 0


def command_find(args: argparse.Namespace) -> int:
    directory = state_directory(args.state_dir)
    for receipt in load_all(directory):
        if (
            receipt["provider"] == args.provider
            and receipt["target"]["id"] == args.target_id
            and receipt["intent"] == args.intent
        ):
            print(receipt["handle"])
            break
    return 0


def command_field(args: argparse.Namespace) -> int:
    directory = state_directory(args.state_dir)
    value: Any = load_receipt(directory, args.handle)
    for part in FIELD_PATHS[args.field]:
        if not isinstance(value, dict) or part not in value:
            raise ReceiptError("receipt field is unavailable")
        value = value[part]
    if not isinstance(value, str):
        raise ReceiptError("receipt field is invalid")
    print(value)
    return 0


def command_update(args: argparse.Namespace) -> int:
    directory = state_directory(args.state_dir)
    receipt = load_receipt(directory, args.handle)
    if args.state is not None:
        receipt["state"] = args.state
    if args.cleanup is not None:
        receipt["cleanup"] = args.cleanup
    validate_receipt(receipt, args.handle)
    _write_replace(receipt_path(directory, args.handle), receipt)
    return 0


def command_inventory(args: argparse.Namespace) -> int:
    directory = state_directory(args.state_dir)
    receipts = load_all(directory)
    workspaces = [public_item(receipt) for receipt in receipts]
    print(json.dumps({
        "workspaces": workspaces,
        "counts": {
            "temporary": sum(
                item["retention"] == "discardOnRelease" for item in workspaces
            ),
            "retained": sum(
                item["retention"] == "retained" for item in workspaces
            ),
        },
    }, separators=(",", ":"), sort_keys=True))
    return 0


def command_gc(args: argparse.Namespace) -> int:
    directory = state_directory(args.state_dir)
    candidates = [
        public_item(receipt)
        for receipt in load_all(directory)
        if receipt["retention"] == "discardOnRelease"
        and receipt["cleanup"] in {"release", "pending"}
    ]
    print(json.dumps({
        "dryRun": True,
        "candidates": candidates,
        "count": len(candidates),
    }, separators=(",", ":"), sort_keys=True))
    return 0


def command_forget(args: argparse.Namespace) -> int:
    directory = state_directory(args.state_dir)
    load_receipt(directory, args.handle)
    receipt_path(directory, args.handle).unlink()
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--state-dir", required=True)
    commands = result.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create")
    create.add_argument("--provider", required=True)
    create.add_argument("--intent", required=True, choices=sorted(INTENTS))
    create.add_argument("--mechanism", required=True, choices=sorted(MECHANISMS))
    create.add_argument("--retention", required=True, choices=sorted(RETENTIONS))
    create.add_argument("--cleanup", required=True, choices=sorted(CLEANUPS))
    create.add_argument("--state", required=True, choices=sorted(STATES))
    create.add_argument("--target-name", required=True)
    create.add_argument("--target-id", required=True)
    create.add_argument("--source-name")
    create.add_argument("--source-id")
    create.set_defaults(function=command_create)

    find = commands.add_parser("find")
    find.add_argument("--provider", required=True)
    find.add_argument("--target-id", required=True)
    find.add_argument("--intent", required=True, choices=sorted(INTENTS))
    find.set_defaults(function=command_find)

    field = commands.add_parser("field")
    field.add_argument("--handle", required=True)
    field.add_argument("--field", required=True, choices=sorted(FIELD_PATHS))
    field.set_defaults(function=command_field)

    update = commands.add_parser("update")
    update.add_argument("--handle", required=True)
    update.add_argument("--state", choices=sorted(STATES))
    update.add_argument("--cleanup", choices=sorted(CLEANUPS))
    update.set_defaults(function=command_update)

    inventory = commands.add_parser("inventory")
    inventory.set_defaults(function=command_inventory)

    gc = commands.add_parser("gc")
    gc.set_defaults(function=command_gc)

    forget = commands.add_parser("forget")
    forget.add_argument("--handle", required=True)
    forget.set_defaults(function=command_forget)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.function(args)
    except ReceiptError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
