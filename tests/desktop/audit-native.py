#!/usr/bin/env python3
"""Run in a claimed dedicated Linux GUI session; never replace an installed app."""
import argparse
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
child = None
checks = []
owned = tempfile.TemporaryDirectory(prefix="mc-audit-live-")
state_home = Path(owned.name)
environment = {**os.environ, "XDG_STATE_HOME": str(state_home), "PYTHONDONTWRITEBYTECODE": "1"}
log = (state_home / "companion.log").open("w")


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})
    if not condition:
        raise AssertionError(name)


def operator(method, **fields):
    child.stdin.write(json.dumps({"method": method, **fields}) + "\n")
    child.stdin.flush()
    check("operator responds", bool(select.select([child.stdout], [], [], 10)[0]))
    reply = json.loads(child.stdout.readline())
    check("operator accepted " + method, reply.get("ok"))
    return reply


def start():
    global child, endpoint
    child = subprocess.Popen(["/usr/bin/python3", str(args.runtime / "desktop.py")], env=environment,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
    operator("hello", processId=os.getpid(), executable="/usr/bin/true")
    state = operator("state")["state"]
    endpoint = state["socket"]
    check("logging ready", state["logging"]["available"])


def stop():
    global child
    operator("quit")
    check("companion exits", child.wait(timeout=10) == 0)
    child = None


def call(operation, **fields):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(10)
        client.connect(endpoint)
        client.sendall((json.dumps({"operation": operation, **fields}) + "\n").encode())
        with client.makefile("rb") as file:
            return json.loads(file.readline())


try:
    start()
    sentinel = "SENTINEL-audit-payload"
    began = time.monotonic()
    reply = call("input.text", text=sentinel, requestId=sentinel)
    latency = int((time.monotonic() - began) * 1000)
    check("off refuses input", reply["errorCode"] == "approval_required")
    history = operator("logs.query")["history"]["entries"]
    check("intent and result stored", {e["phase"] for e in history if e["operation"] == "input.text"} == {"intent", "result"})
    check("kernel caller metadata", any(e.get("callerPid") == os.getpid() for e in history))
    event_ids = {e["eventId"] for e in history}
    operator("logs.debug", enabled=True)
    check("debug bounded", 0 < operator("state")["state"]["logging"]["debugRemainingSeconds"] <= 900)
    preview = operator("logs.preview")["preview"]
    check("payload excluded", sentinel not in json.dumps(preview))
    exported = Path(operator("logs.export")["path"])
    check("export private", exported.stat().st_mode & 0o777 == 0o600)
    check("export payload excluded", sentinel not in exported.read_text())
    stop()
    start()
    history = operator("logs.query")["history"]["entries"]
    check("restart retains history", event_ids <= {e["eventId"] for e in history})
    check("restart does not retain access", operator("state")["state"]["deployment"]["grant"] is None)
    directory = state_home / "machine-control/logs/audit"
    backup = directory.with_name("audit-backup")
    directory.rename(backup)
    directory.write_text("fixture blocks the audit directory")
    check("failed intent blocks provider", call("input.click", x=1, y=1)["errorCode"] == "audit_storage_unavailable")
    operator("stop")
    check("stop works without audit storage", operator("state")["state"]["deployment"]["grant"] is None)
    directory.unlink(); backup.rename(directory)
    call("snapshot")
    check("storage recovers", operator("state")["state"]["logging"]["available"])
    stop()
    args.output.write_text(json.dumps({"passed": True, "checks": checks, "refusedInputElapsedMs": latency}, indent=2))
finally:
    if child:
        child.stdin.close()
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired: child.kill(); child.wait()
    log.close()
    owned.cleanup()
