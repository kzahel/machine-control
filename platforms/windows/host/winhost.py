#!/usr/bin/env python3
"""Local Windows desktop adapter. Claims coordinate; native grants authorize."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
PROFILE = "windows-host-desktop"


def installation() -> Path:
    # An explicit controller-local locator also supports acceptance installs.
    path = Path(os.environ.get("MACHINE_CONTROL_DESKTOP_INSTALL_DIR",
                               str(Path(os.environ["LOCALAPPDATA"]) / "Machine Control")))
    metadata = json.loads((path / "runtime/desktop-runtime.json").read_text(encoding="utf-8-sig"))
    if metadata.get("schema") != "machine-control-desktop-runtime/v0" or \
            metadata.get("profile") != "ordinary_user_desktop" or metadata.get("instance") != "desktop":
        raise ValueError("The selected installation is not the desktop product")
    return path


def session_id() -> int:
    value = ctypes.c_ulong()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(value)) or value.value == 0:
        raise OSError("An interactive Windows user session is required")
    return value.value


def call(request: dict) -> dict:
    timeout = min(615, float(request.get("timeoutSeconds", 120)) + 15) \
        if request.get("operation") == "grant.request" else 30
    arguments = [str(installation() / "runtime/machine-control-windows.exe"), "call",
                 "--profile", "user", "--instance", "desktop", "--session-id", str(session_id())]
    result = subprocess.run(arguments, input=json.dumps(request), capture_output=True,
                            text=True, timeout=timeout)
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or value.get("schema") != "machine-control/v0":
        raise ValueError("Invalid resident result")
    return value


def resource_id() -> str:
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                        0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        identity = winreg.QueryValueEx(key, "MachineGuid")[0]
    if not isinstance(identity, str) or not identity:
        raise ValueError("Exact local machine identity is unavailable")
    return hashlib.sha256(identity.encode()).hexdigest()


def claim(arguments: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    state = Path(os.environ.get("MACHINE_CONTROL_HOST_STATE_DIR",
                                str(Path(os.environ["LOCALAPPDATA"]) / "MachineControl/controller")))
    command = [sys.executable, str(ROOT / "providers/claims/claims.py"),
               "--state-dir", str(state / "claims"), *arguments]
    return subprocess.run(command, capture_output=capture, text=True)


def require_claim() -> None:
    identifier = os.environ.get("MACHINE_CONTROL_CLAIM_ID", "")
    if not re.fullmatch(r"c-[a-f0-9]{24}", identifier):
        raise ValueError("Exclusive target use requires a live claim")
    checked = claim(["check", "--provider", "windows-host", "--resource-id", resource_id(),
                     "--claim-id", identifier], capture=True)
    if checked.returncode:
        raise ValueError("The target-use claim is unavailable or belongs to another target")


def doctor() -> int:
    states = dict(power="running", administration="unavailable", resident="unavailable",
                  desktop="unknown", semantic="unavailable", capture="unavailable",
                  input="unavailable", outer="unavailable")
    checks = []
    extensions = {"transport": "local_named_pipe", "protectedAuthority": "unavailable_in_desktop_profile"}
    try:
        resource_id()
        checks.append(dict(id="identity", status="pass", summary="Exact local identity is available"))
        status = call({"operation": "status"})
        data = status.get("data", {})
        if status.get("accepted") is not True or data.get("desktopProduct") is not True:
            raise ValueError("The desktop resident is unavailable")
        states["resident"] = "ready"
        states["desktop"] = "locked" if status.get("sessionLocked") else \
            "unlocked" if data.get("ready") else "no_session"
        for name in ("semantic", "capture", "input"):
            states[name] = "ready" if data.get("ready") else "unavailable"
        grant = call({"operation": "grant.status"})
        deployment = grant.get("data", {})
        extensions["deployment"] = deployment
        extensions["runtimeGeneration"] = status.get("generation")
        checks.append(dict(id="resident", status="pass", summary="Desktop resident is reachable"))
        checks.append(dict(id="grant", status="pass" if deployment.get("grant") else "warn",
                           summary="Access requires a native operator grant"))
    except (OSError, ValueError, subprocess.SubprocessError):
        checks.append(dict(id="resident", status="fail", summary="Desktop resident or local identity is unavailable"))
    ready = states["resident"] == "ready" and states["desktop"] == "unlocked"
    print(json.dumps(dict(schema="machine-control-doctor/v0", ready=ready,
                          target=dict(platform="windows", profile=PROFILE, kind="desktop"),
                          states=states, checks=checks, lifecycleOperations=[], extensions=extensions)))
    return 0 if ready else 1


def artifact_fetch(arguments: list[str]) -> int:
    if not 1 <= len(arguments) <= 2 or not re.fullmatch(r"[a-f0-9]{32}", arguments[0]):
        raise ValueError("Artifact selection requires a resident artifact ID")
    root = Path(os.environ["LOCALAPPDATA"]) / f"MachineControl/workstation/desktop/session-{session_id()}/artifacts"
    source = (root / f"{arguments[0]}.png").resolve(strict=True)
    if source.parent != root.resolve() or not source.is_file():
        raise ValueError("Artifact is outside the resident artifact root")
    with source.open("rb") as stream:
        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Resident artifact is not a PNG")
    output = Path(arguments[1]) if len(arguments) == 2 else \
        Path(tempfile.mkdtemp(prefix="winhost-artifact.")) / source.name
    # Match the remote adapter: do not overwrite an existing output.
    with output.open("xb") as stream, source.open("rb") as incoming:
        shutil.copyfileobj(incoming, stream)
    print(output)
    return 0


def main(arguments: list[str]) -> int:
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
            forwarded = [value for value in rest if value != "--json"]
            if operation == "capabilities":
                return claim([operation]).returncode if not forwarded else 2
            # Callers must not override the adapter's exact resource binding.
            if any(value.split("=", 1)[0] in {"--provider", "--resource-id", "--state-dir"} for value in forwarded):
                return 2
            return claim([operation, "--provider", "windows-host", "--resource-id", resource_id(), *forwarded]).returncode
        require_claim()
        if command in {"control", "control-local"} and len(rest) == 1:
            request = json.loads(rest[0])
            if not isinstance(request, dict):
                raise ValueError("Request must be an object")
            request.setdefault("claimId", os.environ["MACHINE_CONTROL_CLAIM_ID"])
            value = call(request)
            print(json.dumps(value))
            return 0 if value.get("accepted") is True else 1
        if command in {"artifact", "artifact-fetch"}:
            return artifact_fetch(rest)
        return 2
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Windows desktop adapter unavailable: {type(error).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
