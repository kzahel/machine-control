#!/usr/bin/env python3
"""Read-only, source-independent CLI smoke for an exact installed client."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--client", type=Path, required=True)
args = parser.parse_args()
client = args.client.resolve(strict=True)
with tempfile.TemporaryDirectory(prefix="mc-cli-installed-") as tmp:
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("MACHINE_CONTROL_") and not key.startswith("PYTHON")}
    environment.update({"PATH": str(client.parent) + os.pathsep + ("/usr/bin:/bin" if os.name != "nt" else environment.get("SystemRoot", r"C:\Windows") + r"\System32"),
                        "XDG_CONFIG_HOME": tmp, "APPDATA": tmp,
                        "PYTHONPATH": str(Path(tmp) / "unavailable-python"),
                        "PYTHONHOME": str(Path(tmp) / "unavailable-python")})

    def run(*values):
        command = [str(client), *values]
        if os.name == "nt":
            command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
        result = subprocess.run(command, cwd=tmp, env=environment, capture_output=True,
                                text=True, timeout=30)
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
print("PASS relocated installed CLI, isolated Python, offline discovery and bundled claim dependency")
