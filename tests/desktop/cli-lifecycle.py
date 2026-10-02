#!/usr/bin/env python3
"""Installed Mac CLI claim fencing and recovery with a harness-owned resident.

Run only inside an authorized dedicated Mac appliance with standing policy.
The caller owns the appliance claim, exact signed app staging and power cleanup.
This harness never stops the appliance's original resident or changes policy.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--client", type=Path, required=True)
args = parser.parse_args()
if sys.platform != "darwin":
    parser.error("Dedicated Mac appliance only")
client = args.client.resolve(strict=True)
resident = client.parents[3] / "MacOS/macui"
assert resident.is_file(), "Select the CLI inside the exact staged Mac app"

with tempfile.TemporaryDirectory(prefix="mc-cli-lifecycle-") as temporary:
    root = Path(temporary)
    root.chmod(0o700)
    endpoint = root / "resident.sock"
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("MACHINE_CONTROL_", "PYTHON"))}
    environment.update({"MACHINE_CONTROL_HOST_SOCKET": str(endpoint),
                        "MACHINE_CONTROL_HOST_STATE_DIR": str(root / "claims"),
                        "XDG_CONFIG_HOME": str(root), "APPDATA": str(root)})
    registry = root / "targets.json"
    registry.write_text(json.dumps({"schema": "machine-control-targets/v0",
                                    "includeDefaults": True, "targets": {}}))
    base = [str(client), "--registry", str(registry), "--target", "host"]
    process = None
    claim = None

    def invoke(*arguments):
        response = subprocess.run([*base, *arguments], cwd=root, env=environment,
                                  capture_output=True, text=True, timeout=30)
        return response, json.loads(response.stdout)

    def accepted(*arguments):
        response, value = invoke(*arguments)
        assert response.returncode == 0 and value.get("accepted", True), value
        return value

    def refused(code, *arguments):
        response, value = invoke(*arguments)
        assert response.returncode != 0 and value.get("accepted") is False, value
        assert value["errorCode"] == code, value
        return value

    def acquire(duration="2m", claimant="installed-lifecycle"):
        return accepted("claim", "acquire", "--duration", duration,
                        "--claimant-authority", "mc-conformance",
                        "--claimant-id", claimant,
                        "--reason", "Bounded installed CLI lifecycle acceptance")["data"]["claim"]["claimId"]

    def status():
        return accepted("--claim", claim, "desktop", "raw",
                        '{"operation":"status"}')

    def stop_owned():
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        if endpoint.exists():
            info = endpoint.lstat()
            assert stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid()
            endpoint.unlink()

    def start_owned(log):
        child = subprocess.Popen([str(resident), "serve", str(endpoint)],
                                 cwd=root, env=environment, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 15
            while not endpoint.exists():
                assert child.poll() is None, "Owned resident exited before readiness"
                assert time.monotonic() < deadline, "Owned resident startup timed out"
                time.sleep(0.1)
            return child
        except BaseException:
            child.terminate()
            child.wait(timeout=10)
            raise

    log_path = root / "resident.log"
    log_path.touch(mode=0o600)
    with log_path.open("ab", buffering=0) as log:
        try:
            identity = accepted("agent", "identity")
            assert identity["distribution"] == "desktop" and identity["clientProtocol"] == 1
            process = start_owned(log)
            doctor = accepted("target", "doctor")
            assert doctor["ready"], doctor
            refused("claim_required", "desktop", "windows")
            claim = acquire("1m")
            grant = accepted("--claim", claim, "grant", "status")
            assert grant["data"]["policy"]["grantMode"] == "standing", "Standing appliance policy required"
            refused("target_claimed", "claim", "acquire", "--duration", "2m",
                    "--claimant-authority", "mc-conformance",
                    "--claimant-id", "other-lifecycle-caller", "--reason", "Check exclusive use")
            with ThreadPoolExecutor(max_workers=3) as pool:
                observations = list(pool.map(lambda _: status(), range(3)))
            generation = observations[0]["generation"]
            assert all(value["generation"] == generation for value in observations)
            print("PASS exclusive claims and concurrent claimed observations", flush=True)

            deadline = time.monotonic() + 90
            while accepted("claim", "status")["data"]["state"] != "available":
                assert time.monotonic() < deadline, "Claim did not expire within its bound"
                time.sleep(1)
            old_claim = claim
            refused("claim_expired", "--claim", old_claim, "desktop", "windows")
            accepted("claim", "release", old_claim)
            claim = None
            claim = acquire()
            refused("claim_mismatch", "--claim", old_claim, "desktop", "windows")
            assert status()["generation"] == generation
            print("PASS expired and superseded claim fencing without restarting the resident", flush=True)

            stop_owned()
            process = None
            response, doctor = invoke("target", "doctor")
            assert response.returncode != 0 and doctor["states"]["resident"] == "unavailable"
            refused("adapter_failed", "--claim", claim, "desktop", "windows")
            assert not endpoint.exists(), "CLI started an unowned replacement"
            assert accepted("agent", "identity") == identity
            process = start_owned(log)
            replacement = status()
            assert replacement["generation"] != generation
            assert replacement["data"]["processId"] == process.pid
            assert accepted("claim", "status")["data"]["claim"]["claimId"] == claim
            assert accepted("target", "doctor")["ready"]
            print("PASS unavailable-resident refusal and explicit recovery with a fresh resident generation", flush=True)
        finally:
            try:
                if claim:
                    accepted("claim", "release", claim)
            finally:
                stop_owned()
    assert accepted("claim", "status")["data"]["state"] == "available"
print("PASS owned resident reaped, isolated claims released and temporary state removed")
