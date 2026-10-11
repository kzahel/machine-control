#!/usr/bin/env python3
"""Native local CLI effect; controller continues through the outside CLI."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--app", type=Path, required=True)
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--client", type=Path, required=True)
parser.add_argument("--fixture", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.runtime))
import linuxui

process = None
claim = None
checks = []
endpoint = Path(os.environ["XDG_RUNTIME_DIR"]) / "machine-control-desktop/desktop.sock"
state = args.output.with_suffix(".fixture.json")
fixture = args.output.with_suffix(".fixture.py")
unit = "mc-cli-parity-fixture.service"
log = args.output.with_suffix(".log").open("w")


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})
    if not value:
        raise AssertionError(name)


def poll(fn, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError("Timed out")


def cli(*arguments, use_claim=True):
    command = [str(args.client), "--target", "host"]
    if claim and use_claim:
        command += ["--claim", claim]
    result = subprocess.run([*command, *arguments], capture_output=True, text=True, timeout=35)
    return json.loads(result.stdout)


def call(operation, **parameters):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(35)
        client.connect(str(endpoint))
        client.sendall(json.dumps({"operation": operation, **parameters}).encode() + b"\n")
        return json.loads(client.makefile("rb").readline(24 * 1024 * 1024))


def allow():
    for app in linuxui.application_roots(linuxui.desktop()):
        if linuxui.safe(app.get_name, "") == "machine-control-approval":
            for node, info in linuxui.walk(app, 16, 1000):
                if info["name"] == "Allow" and info["role"] == "push button":
                    return node.do_action(0)


failure = None
try:
    process = subprocess.Popen([str(args.app), "--presentation", "minimal"], stdout=log, stderr=log)
    poll(lambda: endpoint.exists())
    poll(lambda: call("status")["data"]["ready"])
    check("local doctor resolves ordinary resident", cli("target", "doctor")["ready"])
    claim = cli("claim", "acquire", "--reason", "Native CLI parity qualification", "--duration", "600",
                "--claimant-authority", "native-fixture", "--claimant-id", "cli-parity", use_claim=False)["data"]["claim"]["claimId"]
    fixture.write_text(args.fixture.read_text().replace(
        'Path.home() / ".cache/linuxvm-testbed/fixture/state.json"', "Path(" + repr(str(state)) + ")"))
    subprocess.run(["systemd-run", "--user", "--quiet", "--collect", "--unit", unit,
                    "/usr/bin/python3", str(fixture)], check=True)
    poll(lambda: state.exists())
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(call, "grant.request", scopes=["observe", "control"],
                              reason="Native local and outside CLI effects", durationSeconds=120)
        poll(allow)
        check("native approval", request.result()["accepted"])
    generation = cli("desktop", "status")["generation"]
    snap = poll(lambda: (r if r["accepted"] else None)
                if (r := cli("desktop", "raw", json.dumps({"operation": "snapshot", "target": "machine-control-fixture", "maxDepth": 16}))) else None)
    button = next(n for n in snap["data"]["elements"] if n["label"] == "Semantic Increment")
    before = json.loads(state.read_text())["semanticPresses"]
    result = cli("desktop", "raw", json.dumps({"operation": "action", "reference": button["reference"]}))
    check("local CLI native delivery", result["accepted"])
    poll(lambda: json.loads(state.read_text())["semanticPresses"] == before + 1)
    check("local independent effect", True)
    args.output.write_text(json.dumps({"complete": False, "phase": "outside_ready", "generation": generation,
                                      "reference": button["reference"], "checks": checks}, indent=2))
    poll(lambda: args.output.with_suffix(".continue").exists(), 120)
    check("outside independent effect", json.loads(state.read_text())["semanticPresses"] == before + 2)
    check("local/outside retain same generation", cli("desktop", "status")["generation"] == generation)
finally:
    if claim:
        cli("grant", "revoke")
        cli("claim", "release", claim)
    if process and process.poll() is None:
        process.terminate()
        process.wait(8)
    subprocess.run(["systemctl", "--user", "stop", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fixture.unlink(missing_ok=True)
    state.unlink(missing_ok=True)
    args.output.with_suffix(".continue").unlink(missing_ok=True)
    args.output.write_text(json.dumps({"complete": True, "passed": len(checks) == 6 and all(c["passed"] for c in checks),
                                      "checks": checks}, indent=2))
