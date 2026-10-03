#!/usr/bin/env python3
"""Local adapter for the Machine Control resident on this Mac.

The resident owns authorization. This adapter only selects the local socket,
attributes requests with the caller's claim ID, and projects doctor state.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import select
import socket
import sys
import tempfile
import selectors
from typing import Any

DOCTOR_SCHEMA = "machine-control-doctor/v0"
PROFILE = "macos-host-resident"
SUPPORT = Path.home() / "Library" / "Application Support" / "MachineControl"
ARTIFACT_ROOT = Path.home() / "Library" / "Caches" / "machine-control" / "artifacts"


def socket_path() -> str:
    return os.environ.get("MACHINE_CONTROL_HOST_SOCKET", str(SUPPORT / "control.sock"))


def call(request: dict[str, Any]) -> dict[str, Any]:
    timeout = 300.0
    if request.get("operation") == "grant.request":
        timeout = float(request.get("timeoutSeconds", 120)) + 15
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(socket_path())
        client.sendall(json.dumps(request, separators=(",", ":")).encode() + b"\n")
        session = request.get("operation") == "session.control"
        if not session:
            client.shutdown(socket.SHUT_WR)
        chunks = []
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            if chunk.endswith(b"\n"):
                break
        if session:
            initial = json.loads(b"".join(chunks))
            if initial.get("accepted") is not True:
                return initial
            parent = os.getppid()
            while os.getppid() == parent:
                readable, _, _ = select.select([client], [], [], 1)
                if readable:
                    final = bytearray()
                    while b"\n" not in final:
                        chunk = client.recv(65536)
                        if not chunk:
                            raise OSError("Control-session connection ended")
                        final.extend(chunk)
                        if len(final) > 1048576:
                            raise ValueError("Control-session response is too large")
                    return json.loads(final)
                client.sendall(b'{"operation":"heartbeat"}\n')
            raise OSError("Control-session owner exited")
    value = json.loads(b"".join(chunks))
    if not isinstance(value, dict):
        raise ValueError("resident returned a non-object result")
    return value


def control(argument: str) -> int:
    request = json.loads(argument)
    if not isinstance(request, dict):
        print("Request must be a JSON object", file=sys.stderr)
        return 2
    claim = os.environ.get("MACHINE_CONTROL_CLAIM_ID")
    if claim and "claimId" not in request:
        request["claimId"] = claim
    try:
        value = call(request)
    except (OSError, ValueError) as error:
        print(f"Machine Control resident is unavailable: {error}", file=sys.stderr)
        return 1
    print(json.dumps(value, separators=(",", ":"), sort_keys=True))
    return 0 if value.get("accepted") is True else 1


def readiness(value: Any) -> str:
    return "ready" if value == "ready" else "unavailable"


def doctor() -> int:
    checks: list[dict[str, str]] = []
    states = {
        "power": "running",
        "administration": "unavailable",
        "resident": "unavailable",
        "desktop": "unknown",
        "semantic": "unknown",
        "capture": "unknown",
        "input": "unknown",
        "outer": "unavailable",
    }
    extensions: dict[str, Any] = {"transport": "local_socket"}
    try:
        status = call({"operation": "status"})
        data = status.get("data") if isinstance(status.get("data"), dict) else {}
        states["resident"] = "ready" if status.get("accepted") is True else "degraded"
        desktop = data.get("desktopState", "unknown")
        states["desktop"] = desktop if desktop in {"unlocked", "locked", "no_session"} else "unknown"
        states["semantic"] = readiness(data.get("semanticState"))
        states["capture"] = readiness(data.get("captureState"))
        states["input"] = readiness(data.get("inputState"))
        deployment = data.get("deployment") if isinstance(data.get("deployment"), dict) else {}
        extensions["deployment"] = deployment
        if isinstance(data.get("lockScreen"), dict):
            extensions["lockScreen"] = data["lockScreen"]
        checks.append({"id": "resident", "status": "pass",
                       "summary": "Machine Control resident is reachable"})
        policy = deployment.get("policy", {}) if isinstance(deployment, dict) else {}
        mode = policy.get("grantMode", "unknown")
        grant = deployment.get("grant") if isinstance(deployment, dict) else None
        if mode == "approval":
            checks.append({"id": "grant", "status": "pass" if grant else "warn",
                           "summary": "An approved grant is active" if grant else
                           "No grant is active; request one with grant request"})
        else:
            checks.append({"id": "grant", "status": "pass",
                           "summary": f"The {policy.get('preset', 'unknown')} policy grants standing access"})
    except (OSError, ValueError) as error:
        checks.append({"id": "resident", "status": "fail",
                       "summary": f"Machine Control resident is unavailable: {error.__class__.__name__}"})
    for name in ("desktop", "semantic", "capture", "input"):
        good = states[name] in {"ready", "unlocked"}
        checks.append({"id": name, "status": "pass" if good else "fail",
                       "summary": f"{name.capitalize()} state: {states[name]}"})
    checks.append({"id": "outer", "status": "skip",
                   "summary": "A physical host has no outer recovery route"})
    ready = states["resident"] == "ready" and states["desktop"] == "unlocked" and all(
        states[name] == "ready" for name in ("semantic", "capture", "input"))
    print(json.dumps({
        "schema": DOCTOR_SCHEMA,
        "ready": ready,
        "target": {"platform": "macos", "profile": PROFILE, "kind": "desktop"},
        "states": states,
        "checks": checks,
        "lifecycleOperations": [],
        "extensions": extensions,
    }, separators=(",", ":"), sort_keys=True))
    return 0 if ready else 1


def artifact_fetch(arguments: list[str]) -> int:
    if not 1 <= len(arguments) <= 2:
        print("Usage: machost artifact-fetch ARTIFACT [OUTPUT]", file=sys.stderr)
        return 2
    source = Path(arguments[0])
    root = ARTIFACT_ROOT.resolve()
    try:
        resolved = source.resolve(strict=True)
    except OSError:
        print("Artifact does not exist", file=sys.stderr)
        return 1
    if not source.is_absolute() or ".." in source.parts or resolved.parent != root \
            or not resolved.is_file():
        print("Refusing artifact path outside the resident artifact root", file=sys.stderr)
        return 2
    if len(arguments) == 2:
        output = Path(arguments[1])
        output.parent.mkdir(parents=True, exist_ok=True)
    else:
        output = Path(tempfile.mkdtemp(prefix="machost-artifact.")) / resolved.name
    shutil.copyfile(resolved, output)
    print(output)
    return 0


def channel() -> int:
    """Relay a live SDK channel; EOF or parent loss ends ownership."""
    delegated = os.environ.get("MACHINE_CONTROL_DESKTOP_PROXY")
    if delegated is not None:
        if not delegated.startswith("/tmp/ya-mc-") or len(delegated.encode()) > 103:
            raise ValueError("Invalid native desktop proxy locator")
        # Only the bundled native client can authenticate the YA kernel peer.
        # Never fall back to ambient access when delegation is configured.
        native = Path(__file__).resolve().parents[5] / "MacOS" / "machine-control"
        if not native.is_file():
            raise OSError("Installed native desktop proxy client unavailable")
        os.execv(str(native), [str(native), "delegated-channel", delegated])
    parent = os.getppid()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(socket_path())
        with selectors.DefaultSelector() as selector:
            selector.register(sys.stdin.buffer, selectors.EVENT_READ, "input")
            selector.register(client, selectors.EVENT_READ, "resident")
            while os.getppid() == parent:
                for key, _ in selector.select(1):
                    chunk = os.read(key.fd, 16384)
                    if not chunk:
                        return 0
                    if key.data == "input":
                        client.sendall(chunk)
                    else:
                        sys.stdout.buffer.write(chunk)
                        sys.stdout.buffer.flush()
    return 0


def main(arguments: list[str]) -> int:
    if not arguments:
        return 2
    command, rest = arguments[0], arguments[1:]
    if command == "channel" and not rest:
        return channel()
    if command in {"control", "control-local"} and len(rest) == 1:
        return control(rest[0])
    if command == "doctor":
        return doctor()
    if command == "artifact-fetch":
        return artifact_fetch(rest)
    print(f"Unknown machost command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
