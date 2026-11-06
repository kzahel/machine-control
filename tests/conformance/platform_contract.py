#!/usr/bin/env python3
"""Cross-platform contract conformance for desktop residents (Tactical 159).

Sends the same status request and admission-channel frames to any claimed
desktop target through the ordinary common CLI (`desktop status` and the
diagnostic `control frames` route) and checks the replies against
`contracts/`. It performs no input, never accepts an offer, and cancels the
one valid owner it opens. Results print as JSON lines without target identity.

  tests/conformance/platform_contract.py --target ALIAS --claim CLAIM_ID
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
CLI = ROOT / "bin" / "machine-control"


class SchemaError(ValueError):
    pass


def load(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def validate(value, schema: dict, root: dict | None = None, path: str = "$") -> None:
    """Dependency-free validator for the JSON Schema subset used in contracts/."""
    root = root or schema
    if "$ref" in schema:
        reference = schema["$ref"]
        if reference.startswith("#/"):
            target = root
            for part in reference[2:].split("/"):
                target = target[part]
            return validate(value, target, root, path)
        document = load(reference)
        return validate(value, document, document, path)
    if "oneOf" in schema:
        matches = 0
        for option in schema["oneOf"]:
            try:
                validate(value, option, root, path); matches += 1
            except SchemaError:
                pass
        if matches != 1:
            raise SchemaError(f"{path}: matches {matches} oneOf branches")
        return
    if "const" in schema and value != schema["const"]:
        raise SchemaError(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path}: {value!r} not in enum")
    kinds = schema.get("type")
    if kinds is not None:
        kinds = [kinds] if isinstance(kinds, str) else kinds
        checks = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
                  "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
                  "integer": lambda v: type(v) is int, "number": lambda v: type(v) in (int, float),
                  "null": lambda v: v is None}
        if not any(checks[kind](value) for kind in kinds):
            raise SchemaError(f"{path}: expected {'/'.join(kinds)}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")):
            raise SchemaError(f"{path}: string length out of range")
    if type(value) in (int, float) and not isinstance(value, bool):
        if value < schema.get("minimum", float("-inf")) or value > schema.get("maximum", float("inf")):
            raise SchemaError(f"{path}: number out of range")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise SchemaError(f"{path}: array length out of range")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            raise SchemaError(f"{path}: duplicate items")
        for index, item in enumerate(value):
            if "items" in schema:
                validate(item, schema["items"], root, f"{path}[{index}]")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise SchemaError(f"{path}: missing {key}")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key], root, f"{path}.{key}")
            elif extra is False:
                raise SchemaError(f"{path}: unexpected {key}")
            elif isinstance(extra, dict):
                validate(item, extra, root, f"{path}.{key}")


def open_frame(**overrides) -> dict:
    frame = {"schema": "machine-control-admission/v2", "operation": "control.open",
             "requestId": uuid.uuid4().hex, "reason": "Contract conformance probe",
             "surfaces": ["desktop"], "waitSeconds": 5, "durationSeconds": 60}
    frame.update(overrides)
    return {key: value for key, value in frame.items() if value is not None}


# (name, frames, expected refusal code of the first reply)
REFUSALS = [
    ("wrong_schema", [open_frame(schema="machine-control-admission/v9")], "unsupported_admission_schema"),
    ("bad_surfaces", [open_frame(surfaces=["desktop", "printer"])], "invalid_admission_surfaces"),
    ("browser_without_profiles", [open_frame(surfaces=["browser"])], "exact_browser_profile_required"),
    ("desktop_with_profiles", [open_frame(profileIds=["Work"])], "invalid_browser_profiles"),
    ("cross_surface_operations", [open_frame(operations=["browser.tabs"])], "invalid_admission_operations"),
]


def evaluate_refusal(name: str, replies: list, expected: str) -> dict:
    channel = load("admission-channel-v2.schema.json")
    first = replies[0] if replies else {"event": "none"}
    problems = []
    try:
        validate(first, channel["$defs"]["reply"], channel)
    except SchemaError as error:
        problems.append(f"reply framing: {error}")
    if first.get("accepted") is not False or first.get("errorCode") != expected:
        problems.append(f"expected refusal {expected}, got {first.get('errorCode')!r}")
    if replies[-1:] != [{"event": "closed"}]:
        problems.append("failed open did not close the channel")
    return {"check": name, "pass": not problems, "problems": problems}


def evaluate_sequence(replies: list) -> dict:
    """A valid open may queue, be offered, or (Windows, locked, no flag)
    refuse prepared_console_required; any of those is conformant. A
    sequence gap afterwards must close the channel."""
    channel = load("admission-channel-v2.schema.json")
    problems = []
    first = replies[0] if replies else {}
    try:
        validate(first, channel["$defs"]["reply"], channel)
    except SchemaError as error:
        problems.append(f"open reply framing: {error}")
    if first.get("accepted") is True:
        try:
            validate(first.get("data"), channel["$defs"]["view"], channel, "$.data")
        except SchemaError as error:
            problems.append(f"view: {error}")
        if replies[-1:] != [{"event": "closed"}]:
            problems.append("sequence gap did not close the channel")
    elif first.get("errorCode") != "prepared_console_required":
        problems.append(f"valid open refused: {first.get('errorCode')!r}")
    return {"check": "sequence_gap_closes", "pass": not problems, "problems": problems,
            "openState": (first.get("data") or {}).get("state")}


def evaluate_status(status: dict) -> dict:
    problems = []
    try:
        validate(status.get("data"), load("desktop-status-common-v1.schema.json"))
    except SchemaError as error:
        problems.append(str(error))
    return {"check": "status_common_fields", "pass": not problems, "problems": problems,
            "desktopState": (status.get("data") or {}).get("desktopState")}


def cli(target: str, claim: str, *arguments: str, stdin: str | None = None) -> str:
    completed = subprocess.run([str(CLI), "--target", target, "--claim", claim, *arguments],
        input=stdin, capture_output=True, text=True, timeout=180)
    return completed.stdout


def frames(target: str, claim: str, sequence: list) -> list:
    output = cli(target, claim, "control", "frames", stdin="".join(json.dumps(f) + "\n" for f in sequence))
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True)
    parser.add_argument("--claim", required=True)
    options = parser.parse_args()
    results = [evaluate_status(json.loads(cli(options.target, options.claim, "desktop", "status") or "{}"))]
    for name, sequence, expected in REFUSALS:
        results.append(evaluate_refusal(name, frames(options.target, options.claim, sequence), expected))
    gap = [open_frame(),
           {"operation": "control.status", "requestId": uuid.uuid4().hex, "requestSequence": 1},
           {"operation": "control.status", "requestId": uuid.uuid4().hex, "requestSequence": 3},
           {"operation": "control.cancel", "requestId": uuid.uuid4().hex, "requestSequence": 2}]
    results.append(evaluate_sequence(frames(options.target, options.claim, gap)))
    for result in results:
        print(json.dumps(result, separators=(",", ":")))
    return 0 if all(result["pass"] for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
