#!/usr/bin/env python3
"""Real GLib/socket/AT-SPI faults; native fixture files are the effect oracle."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--fixture", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
checks = []
child = None
log = args.output.with_suffix(".log").open("w")
gate = args.output.with_suffix(".gate")
state_file = args.output.with_suffix(".fixture.json")
fixture_file = args.output.with_suffix(".fixture.py")
unit = "mc-runtime-fault-fixture.service"


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})
    if not value:
        raise AssertionError(name)


def poll(fn, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(.05)
    raise AssertionError("Timed out")


def operator(method, **parameters):
    child.stdin.write(json.dumps({"method": method, **parameters}) + "\n")
    child.stdin.flush()
    if not select.select([child.stdout], [], [], 5)[0]:
        raise AssertionError("Operator blocked")
    reply = json.loads(child.stdout.readline())
    if method in {"arm", "resume", "pause"} and reply.get("ok"):
        poll(lambda: operator("state")["state"]["safetyNoticeReady"])
    return reply


def call(operation, **parameters):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(25)
        client.connect(str(endpoint))
        client.sendall(json.dumps({"operation": operation, **parameters}).encode() + b"\n")
        return json.loads(client.makefile("rb").readline(24 * 1024 * 1024))


def recovery(method="stop"):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(str(endpoint.with_name("operator.sock")))
        client.sendall(json.dumps({"method": method}).encode() + b"\n")
        return json.loads(client.makefile("rb").readline(4097))


def reset_gate():
    for suffix in [".gate", ".started", ".effect", ".after"]:
        args.output.with_suffix(suffix).unlink(missing_ok=True)


def effect_count():
    return json.loads(state_file.read_text())["semanticPresses"]


failure = None
try:
    reset_gate()
    fixture_file.write_text(args.fixture.read_text().replace(
        'Path.home() / ".cache/linuxvm-testbed/fixture/state.json"', 'Path(' + repr(str(state_file)) + ')'))
    subprocess.run(["systemd-run", "--user", "--quiet", "--collect", "--unit", unit,
                    "/usr/bin/python3", str(fixture_file)], check=True)
    poll(lambda: state_file.exists())
    child = subprocess.Popen(["/usr/bin/python3", str(Path(__file__).with_name("linux-fault-host.py")),
                              "--runtime", str(args.runtime), "--gate", str(gate)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
    check("handshake", operator("hello", processId=os.getpid(), executable="/usr/bin/true",
                                instance="fault-fixture")["ok"])
    state = poll(lambda: (s if s["safetyAvailable"] and s["permissions"]["accessibility"] else None)
                 if (s := operator("state")["state"]) else None)
    endpoint = Path(state["socket"])
    check("arm", operator("arm", scopes=["observe", "control"], duration=120)["ok"])
    snapshot = call("snapshot", target="machine-control-fixture", maxDepth=16)
    reference = next(n["reference"] for n in snapshot["data"]["elements"] if n["label"] == "Semantic Increment")
    with ThreadPoolExecutor(max_workers=8) as pool:
        held = pool.submit(call, "snapshot", target="machine-control-fixture", query="stall")
        poll(lambda: gate.with_suffix(".started").exists())
        started = time.monotonic()
        statuses = list(pool.map(lambda _: call("status"), range(30)))
        latency = time.monotonic() - started
        check("discovery progresses while provider stalls", all(v["accepted"] for v in statuses) and latency < 3)
        check("physical provider slot retained", call("snapshot", target="machine-control-fixture")["errorCode"] == "provider_busy")
        started = time.monotonic()
        check("independent Stop", recovery()["ok"])
        check("Stop latency below one second", time.monotonic() - started < 1)
        check("replacement grant", operator("arm", scopes=["observe", "control"], duration=120)["ok"])
        gate.touch()
        check("late completion refused", held.result()["errorCode"] == "operation_cancelled")
        poll(lambda: not operator("state")["state"]["providerWork"]["busy"])
        check("stale references", call("action", reference=reference)["errorCode"] == "stale_reference")

        reset_gate()
        current = call("snapshot", target="machine-control-fixture", maxDepth=16)
        reference = next(n["reference"] for n in current["data"]["elements"] if n["label"] == "Semantic Increment")
        before = effect_count()
        gate.with_suffix(".effect").touch()
        held = pool.submit(call, "action", reference=reference)
        poll(lambda: gate.with_suffix(".started").exists())
        check("Pause", operator("pause")["ok"])
        check("paused access refused", call("snapshot")["errorCode"] == "access_paused")
        check("Resume", operator("resume")["ok"])
        gate.touch()
        result = held.result()
        check("preflight cancellation has no dispatch", result["errorCode"] == "operation_cancelled" and result["delivery"] == "refused")
        check("independent no late native effect", effect_count() == before)

        reset_gate()
        current = call("snapshot", target="machine-control-fixture", maxDepth=16)
        reference = next(n["reference"] for n in current["data"]["elements"] if n["label"] == "Semantic Increment")
        gate.with_suffix(".after").touch()
        held = pool.submit(call, "action", reference=reference)
        poll(lambda: gate.with_suffix(".started").exists())
        poll(lambda: effect_count() == before + 1)
        check("Stop after dispatch", recovery()["ok"])
        gate.touch()
        result = held.result()
        check("already dispatched effect stays uncertain", result["delivery"] == "unknown" and result["retrySafety"] == "unsafe_delivery_unknown")
        check("independent effect occurred once", effect_count() == before + 1)

        reset_gate()
        check("grant for deadline", operator("arm", scopes=["observe"], duration=120)["ok"])
        held = pool.submit(call, "snapshot", target="machine-control-fixture", query="stall")
        poll(lambda: gate.with_suffix(".started").exists())
        check("deadline is bounded", held.result(timeout=23)["errorCode"] == "operation_cancelled")
        check("timeout retains physical capacity", call("snapshot")["errorCode"] == "provider_busy")
        gate.touch()
        poll(lambda: not operator("state")["state"]["providerWork"]["busy"])
    reset_gate()
    disconnected = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    disconnected.connect(str(endpoint))
    disconnected.sendall(json.dumps({"operation": "snapshot", "target": "machine-control-fixture", "query": "stall"}).encode() + b"\n")
    poll(lambda: gate.with_suffix(".started").exists())
    disconnected.close()
    time.sleep(.2)
    check("disconnected caller retains worker capacity", call("snapshot")["errorCode"] == "provider_busy")
    gate.touch()
    poll(lambda: not operator("state")["state"]["providerWork"]["busy"])
    check("Stop before lifecycle", recovery()["ok"])
    check("update exclusion", operator("prepare_update")["ok"])
    check("update blocks arming", not operator("arm", scopes=["observe"], duration=30)["ok"])
    check("release update exclusion", operator("cancel_update")["ok"])
    check("grant before safety fault", operator("arm", scopes=["observe"], duration=30)["ok"])
    safety = None
    for path in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            if args.runtime.joinpath("notice.py").as_posix().encode() in path.read_bytes():
                safety = path
                break
        except OSError:
            pass
    check("native safety identity found", safety is not None)
    os.kill(int(safety.parent.name), 15)
    poll(lambda: not operator("state")["state"]["safetyAvailable"])
    check("safety loss revokes access", call("status")["data"]["grant"] is None)
    check("safety loss prevents arming", not operator("arm", scopes=["observe"], duration=30)["ok"])
    child.stdin.close()
    child.wait(5)
    check("owner EOF removes endpoints", not endpoint.exists() and not endpoint.with_name("operator.sock").exists())
except BaseException as error:
    failure = str(error)
    raise
finally:
    gate.touch()
    if child and child.poll() is None:
        child.terminate()
        try:
            child.wait(5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    subprocess.run(["systemctl", "--user", "stop", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reset_gate()
    fixture_file.unlink(missing_ok=True)
    state_file.unlink(missing_ok=True)
    args.output.write_text(json.dumps({"complete": True, "passed": failure is None,
                                      "failure": failure, "checks": checks}, indent=2))
