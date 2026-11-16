#!/usr/bin/env python3
"""Read-only, source-independent CLI smoke for an exact installed client."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--client", type=Path, required=True)
parser.add_argument("--unavailable-resident", action="store_true",
                    help="Mac-only: exercise absent-resident refusal with an isolated claim store")
args = parser.parse_args()
if args.unavailable_resident and sys.platform != "darwin":
    parser.error("--unavailable-resident requires the Mac host adapter")
client = args.client.resolve(strict=True)


def snapshot(root):
    return {file.relative_to(root).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
            for file in root.rglob("*") if file.is_file()}


original_root = client.parent.parent
original = snapshot(original_root)
with tempfile.TemporaryDirectory(prefix="mc-cli-installed-") as tmp:
    # Move the entire payload away from its original product/source location.
    relocated = Path(tmp) / "relocated client/mc-cli"
    shutil.copytree(client.parent.parent, relocated)
    client = relocated / "commands" / client.name
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("MACHINE_CONTROL_") and not key.startswith("PYTHON")}
    environment.update({"PATH": str(client.parent) + os.pathsep + ("/usr/bin:/bin" if os.name != "nt" else environment.get("SystemRoot", r"C:\Windows") + r"\System32"),
                        "XDG_CONFIG_HOME": tmp, "APPDATA": tmp,
                        "PYTHONPATH": str(Path(tmp) / "unavailable-python"),
                        "PYTHONHOME": str(Path(tmp) / "unavailable-python")})
    before = snapshot(relocated)
    python = relocated / ("python/python.exe" if os.name == "nt" else "python/bin/python3")
    protected = False
    # Copying a payload does not preserve installed ownership/ACLs. Exercise
    # the real guard on this owned copy before deliberately bypassing -B.
    if sys.platform == "darwin" and (relocated / "protect-cli.py").is_file():
        subprocess.run([str(python), "-I", "-B", str(relocated / "protect-cli.py")],
                       check=True, timeout=30)
        protected = True
    elif os.name == "nt" and (relocated / "windows-payload.ps1").is_file():
        shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-File", str(relocated / "windows-payload.ps1"), "-Action", "protect",
                        "-Directory", str(relocated.parent)], check=True, timeout=60)
        protected = True
    if protected:
        subprocess.run([str(python), "-I", str(relocated / "bin/machine-control"), "--help"],
                       check=True, capture_output=True, timeout=30)
        subprocess.run([str(python), "-I", "-c",
                        "import sys;sys.path.insert(0,sys.argv[1]);"
                        "import agent_interface,control_session,json,ctypes,sqlite3",
                        str(relocated / "client")], check=True, capture_output=True, timeout=30)
        assert snapshot(relocated) == before, "Direct Python execution changed the protected payload"

    def invoke(*values):
        command = [str(client), *values]
        if os.name == "nt":
            command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
        return subprocess.run(command, cwd=tmp, env=environment, capture_output=True,
                              text=True, timeout=30)

    def run(*values):
        result = invoke(*values)
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return result.stdout

    identity = json.loads(run("agent", "identity"))
    assert identity["schema"] == "machine-control-client-identity/v1"
    assert identity["distribution"] == "desktop" and identity["clientProtocol"] == 1
    assert "claim release" in run("agent", "instructions")
    targets = json.loads(run("targets"))["targets"]
    assert len(targets) == 1 and targets[0]["logicalTarget"] == "host" and targets[0]["adapterAvailable"]
    claims = json.loads(run("--target", "host", "claim", "capabilities"))
    assert claims["schema"] == "machine-control-claim-capabilities/v0"
    if args.unavailable_resident:
        endpoint = Path(tmp) / "missing.sock"
        environment.update({"MACHINE_CONTROL_HOST_SOCKET": str(endpoint),
                            "MACHINE_CONTROL_HOST_STATE_DIR": str(Path(tmp) / "state")})
        result = invoke("--target", "host", "target", "doctor")
        doctor = json.loads(result.stdout)
        assert result.returncode != 0 and doctor["ready"] is False
        assert doctor["states"]["resident"] == "unavailable"
        acquired = json.loads(run("--target", "host", "claim", "acquire",
                                  "--duration", "2m",
                                  "--claimant-authority", "mc-conformance",
                                  "--claimant-id", "installed-unavailable",
                                  "--reason", "Verify absent-resident refusal"))
        assert acquired["accepted"]
        claim = acquired["data"]["claim"]["claimId"]
        try:
            for operation in (("desktop", "windows"), ("grant", "status")):
                result = invoke("--target", "host", "--claim", claim, *operation)
                refused = json.loads(result.stdout)
                assert result.returncode != 0 and refused["accepted"] is False
                assert refused["schema"] == "machine-control-client-error/v0"
                assert refused["errorCode"] == "adapter_failed"
                assert "resident is unavailable" in result.stderr
            assert not endpoint.exists(), "The CLI must not create a resident socket"
        finally:
            released = json.loads(run("--target", "host", "claim", "release", claim))
            assert released["accepted"]
        assert json.loads(run("--target", "host", "claim", "status"))["data"]["state"] == "available"
        print("PASS unavailable resident doctor/refusal and isolated claim release")
    assert snapshot(relocated) == before, "Installed CLI execution changed its payload"
assert snapshot(original_root) == original, "Acceptance changed the original installation"
print("PASS relocated installed CLI, isolated Python, offline discovery and bundled claim dependency")
