#!/usr/bin/env python3
"""Local Linux app adapter. Claims coordinate; native grants authorize."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import shutil
import tempfile
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def endpoint():
    path = Path(os.environ.get("MACHINE_CONTROL_DESKTOP_SOCKET",
                               str(Path(os.environ["XDG_RUNTIME_DIR"]) / "machine-control-desktop/desktop.sock")))
    value = path.lstat()
    if not stat.S_ISSOCK(value.st_mode) or value.st_uid != os.getuid() or stat.S_IMODE(value.st_mode) != 0o600:
        raise ValueError("Private desktop socket required")
    return path


def call(request):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        timeout = min(615, float(request.get("timeoutSeconds", 120)) + 15) if request.get("operation") == "grant.request" else 35
        client.settimeout(timeout)
        client.connect(str(endpoint()))
        client.sendall(json.dumps(request, separators=(",", ":")).encode() + b"\n")
        with client.makefile("rb") as stream:
            frame = stream.readline(24 * 1024 * 1024 + 1)
            if len(frame) > 24 * 1024 * 1024 or not frame.endswith(b"\n"):
                raise ValueError("Invalid resident frame")
            result = json.loads(frame)
    if not isinstance(result, dict) or result.get("schema") != "machine-control/v0":
        raise ValueError("Invalid resident result")
    return result


def resource_id():
    value = Path("/etc/machine-id").read_text().strip()
    if not re.fullmatch("[a-f0-9]{32}", value):
        raise ValueError("Exact local identity unavailable")
    return hashlib.sha256(value.encode()).hexdigest()


def claim(arguments, capture=False):
    state = Path(os.environ.get("MACHINE_CONTROL_HOST_STATE_DIR",
                                str(Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "machine-control/controller")))
    return subprocess.run([sys.executable, str(ROOT / "providers/claims/claims.py"),
                           "--state-dir", str(state / "claims"), *arguments],
                          text=True, capture_output=capture)


def doctor():
    states = dict(power="running", administration="unavailable", resident="unavailable",
                  desktop="unknown", semantic="unavailable", capture="unavailable",
                  input="unavailable", outer="prohibited")
    checks = []
    extensions = {"transport": "local_unix_socket", "inputPrivilege": "ordinary_user"}
    try:
        resource_id()
        status = call({"operation": "status"})
        data = status["data"]
        if status.get("accepted") is not True or data.get("desktopProduct") is not True:
            raise ValueError("Desktop resident unavailable")
        states["resident"] = "ready"
        states["desktop"] = "unlocked" if data["ready"] else "no_session"
        for name in ["semantic", "capture", "input"]:
            states[name] = data[name + "State"]
        extensions["deployment"] = {k: data[k] for k in ["policy", "grant", "pendingRequest"]}
        extensions["runtimeGeneration"] = status["generation"]
        checks.append(dict(id="resident", status="pass", summary="Desktop resident is reachable"))
        checks.append(dict(id="grant", status="pass" if data["grant"] else "warn",
                           summary="Access requires a native operator grant"))
    except (OSError, ValueError, KeyError):
        checks.append(dict(id="resident", status="fail", summary="Desktop resident or identity is unavailable"))
    ready = states["resident"] == "ready" and states["desktop"] == "unlocked"
    print(json.dumps(dict(schema="machine-control-doctor/v0", ready=ready,
                          target=dict(platform="linux", profile="linux-host-desktop", kind="desktop"),
                          states=states, checks=checks, lifecycleOperations=[], extensions=extensions)))
    return 0 if ready else 1


def artifact_fetch(arguments):
    if not 1 <= len(arguments) <= 2 or not re.fullmatch("[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}", arguments[0]):
        raise ValueError("Resident artifact ID required")
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "machine-control/desktop/artifacts"
    source = root / (arguments[0] + ".png")
    value = source.lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_uid != os.getuid() or value.st_size > 16 * 1024 * 1024:
        raise ValueError("Invalid resident artifact")
    output = Path(arguments[1]) if len(arguments) == 2 else Path(tempfile.mkdtemp(prefix="linuxhost-artifact.")) / source.name
    with source.open("rb") as incoming:
        if incoming.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid resident PNG")
        incoming.seek(0)
        with output.open("xb") as stream:
            shutil.copyfileobj(incoming, stream)
    print(output)
    return 0


def main(arguments):
    if not arguments:
        return 2
    command, rest = arguments[0], arguments[1:]
    try:
        if command == "doctor":
            return doctor()
        if command.startswith("claim-"):
            operation = command.removeprefix("claim-")
            if "--json" not in rest or operation not in {"capabilities", "status", "acquire", "check", "renew", "release"}:
                return 2
            forwarded = [v for v in rest if v != "--json"]
            if any(v.split("=", 1)[0] in {"--provider", "--resource-id", "--state-dir"} for v in forwarded):
                return 2
            if operation == "capabilities":
                return claim([operation]).returncode if not forwarded else 2
            return claim([operation, "--provider", "linux-host", "--resource-id", resource_id(), *forwarded]).returncode
        identifier = os.environ.get("MACHINE_CONTROL_CLAIM_ID", "")
        if not re.fullmatch("c-[a-f0-9]{24}", identifier) or claim([
            "check", "--provider", "linux-host", "--resource-id", resource_id(),
            "--claim-id", identifier], capture=True).returncode:
            raise ValueError("Exclusive target use requires a live claim")
        if command in {"control", "control-local"} and len(rest) == 1:
            request = json.loads(rest[0])
            if not isinstance(request, dict):
                raise ValueError("Object required")
            request.setdefault("claimId", identifier)
            result = call(request)
            print(json.dumps(result))
            return 0 if result.get("accepted") is True else 1
        if command in {"artifact", "artifact-fetch"}:
            return artifact_fetch(rest)
        return 2
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Linux desktop adapter unavailable: {type(error).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
