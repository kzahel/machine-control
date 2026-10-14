#!/usr/bin/env python3
"""Run paired route-comparison trials in disposable macOS experiment clones.

Each trial acquires an isolated workspace of the experiment base, opens one
SSH connection (controller AAR into the guest, guest YA out to the
controller), runs the task's setup, asks a guest Codex session to do the task
through one route, runs the oracle, collects private evidence and releases the
clone. See docs/comparison-experiments.md. Results never belong in Git.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
MC_REPL = Path(__file__).resolve().parent / "mc-repl" / "mc-repl.mjs"
# Registered only in mc-repl trial clones; the base image stays unchanged.
MC_REPL_CONFIG = """
[mcp_servers.mc]
command = "/opt/homebrew/bin/node"
args = ["/Users/admin/experiment/mc-repl.mjs"]
startup_timeout_sec = 30
"""
TASKS = Path(__file__).resolve().parent / "tasks"
CLI = [sys.executable, str(ROOT / "bin/machine-control")]

ROUTES = {
    "machine-control": (
        "Use Machine Control for all UI work: run its CLI from ~/code/machine-control "
        "(bin/machine-control --target host ...) as described in "
        "platforms/macos/skills/drive-macos-host/SKILL.md. Do not use Codex Computer Use, "
        "AppleScript, osascript or System Events, and do not use shell commands to change "
        "the files or settings the task is about."),
    "mc-repl": (
        "Use the mc tool (a persistent JavaScript session over this Mac's Machine Control "
        "resident; its description lists the API) for all UI work. Do not use the "
        "machine-control CLI, Codex Computer Use, AppleScript, osascript or System Events, and "
        "do not use shell commands to change the files or settings the task is about."),
    "computer-use": (
        "Use Codex Computer Use (the cua object in your JavaScript tool) for all UI work. "
        "Do not use Machine Control, AppleScript, osascript or System Events, and do not use "
        "shell commands to change the files or settings the task is about."),
}
COMMON = ("Nobody is at the computer and nobody will answer questions. If you get stuck, "
          "stop and report exactly what blocked you. Finish with one line starting with "
          "RESULT: done or RESULT: blocked.")


def now():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def mc(*arguments, check=True):
    completed = subprocess.run([*CLI, *arguments], capture_output=True, text=True, check=False)
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        value = {"accepted": False, "errorCode": "unparsable", "stdout": completed.stdout[-500:]}
    if check and value.get("accepted") is not True:
        raise RuntimeError(f"machine-control {' '.join(arguments[:4])} failed: "
                           f"{value.get('errorCode')} {value.get('message', '')}")
    return value


def tart_names():
    out = subprocess.run(["tart", "list", "--quiet"], capture_output=True, text=True, check=True).stdout
    return set(out.split())


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Guest:
    def __init__(self, args, vm):
        self.args, self.vm = args, vm
        self.ip = subprocess.run(["tart", "ip", vm], capture_output=True, text=True,
                                 check=True).stdout.strip()
        self.options = ["-i", str(args.ssh_key), "-o", "IdentitiesOnly=yes",
                        "-o", f"HostKeyAlias={args.host_key_alias}",
                        "-o", f"UserKnownHostsFile={args.known_hosts}",
                        "-o", "StrictHostKeyChecking=yes", "-o", "BatchMode=yes"]
        self.tunnel = None
        self.port = None

    def run(self, command, stdin=None, timeout=300):
        return subprocess.run(["ssh", *self.options, f"{self.args.guest_user}@{self.ip}", command],
                              input=stdin, capture_output=True, text=True, timeout=timeout)

    def open_tunnel(self):
        self.port = free_port()
        self.tunnel = subprocess.Popen(
            ["ssh", *self.options, "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=15",
             "-N", "-R", "127.0.0.1:8417:127.0.0.1:8417",
             "-L", f"127.0.0.1:{self.port}:127.0.0.1:3400", f"{self.args.guest_user}@{self.ip}"])
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                self.ya("GET", "/api/auth/status")
                return
            except OSError:
                time.sleep(2)
        raise RuntimeError("guest YA did not answer through the tunnel")

    def close(self):
        if self.tunnel and self.tunnel.poll() is None:
            self.tunnel.terminate()
            self.tunnel.wait(10)

    def ya(self, method, path, body=None):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "X-Yep-Anywhere": "true"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"{}")


def project_id(path):
    return base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")


def run_trial(args, task, route, index, run_dir):
    trial_dir = run_dir / task["id"] / f"{route}-{index}"
    trial_dir.mkdir(parents=True, mode=0o700)
    record = {"task": task["id"], "route": route, "repetition": index, "startedAt": now()}
    before = tart_names()
    acquired = mc("--target", args.target, "workspace", "acquire", "--intent", "isolated",
                  "--claim-duration", "2h", "--reason",
                  f"Route comparison trial {task['id']} {route} {index}")
    handle = acquired["data"]["handle"]
    claim = acquired["data"]["claim"]["claimId"]
    guest = None
    started = time.monotonic()
    try:
        created = sorted(tart_names() - before)
        if len(created) != 1:
            raise RuntimeError(f"expected one new clone, found {created}")
        selector = ["--target", args.target, "--workspace", handle, "--claim", claim]
        deadline = time.monotonic() + 600
        while True:
            ready = mc(*selector, "target", "ensure-ready", check=False)
            if ready.get("data", {}).get("ready"):
                break
            if time.monotonic() > deadline:
                raise RuntimeError("clone did not become ready")
            time.sleep(15)
        guest = Guest(args, created[0])
        guest.open_tunnel()
        # Trials use the current CLI and skills; the resident is the base's.
        pulled = guest.run("git -C ~/code/machine-control pull -q --ff-only && "
                           "git -C ~/code/machine-control rev-parse --short HEAD", timeout=120)
        record["guestRevision"] = pulled.stdout.strip() or f"pull failed: {pulled.stderr[-200:]}"
        common = (TASKS / "common-chrome.sh").read_text()
        guest.run("mkdir -p ~/experiment && cat > ~/experiment/common-chrome.sh", stdin=common)
        if route == "mc-repl":
            guest.run("cat > ~/experiment/mc-repl.mjs", stdin=MC_REPL.read_text())
            guest.run("cat >> ~/.codex/config.toml", stdin=MC_REPL_CONFIG)
        setup = guest.run("bash -s", stdin=(TASKS / task["id"] / "setup.sh").read_text())
        record["setup"] = {"exit": setup.returncode, "stderr": setup.stderr[-500:]}
        if setup.returncode:
            raise RuntimeError("task setup failed")

        prompt = "\n\n".join([(TASKS / task["id"] / "prompt.md").read_text().strip(),
                              ROUTES[route], COMMON])
        project = project_id(args.project)
        session = guest.ya("POST", f"/api/projects/{project}/sessions",
                           {"provider": "codex", "mode": "bypassPermissions", "message": prompt})
        session_id = session["sessionId"]
        record["sessionId"] = session_id
        agent_started = time.monotonic()
        deadline = agent_started + task.get("timeoutSeconds", 600)
        time.sleep(15)
        while time.monotonic() < deadline:
            state = (guest.ya("GET", f"/api/sessions/{session_id}/process").get("process") or {}).get("state")
            if state in (None, "idle", "terminated"):
                break
            time.sleep(10)
        else:
            record["timedOut"] = True
        record["agentSeconds"] = round(time.monotonic() - agent_started)
        detail = guest.ya("GET", f"/api/projects/{project}/sessions/{session_id}")
        record["finalText"] = (detail.get("session") or {}).get("lastAgentText", "")[-1500:]

        oracle = guest.run("bash -s", stdin=(TASKS / task["id"] / "oracle.sh").read_text())
        try:
            record["oracle"] = json.loads(oracle.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            record["oracle"] = {"passed": False, "detail": "oracle output unreadable"}

        transcript = guest.run(
            f"f=$(find ~/.codex/sessions -name '*{session_id}.jsonl' | head -1); [ -n \"$f\" ] && cat \"$f\"",
            timeout=120)
        (trial_dir / "transcript.jsonl").write_text(transcript.stdout)
        record.update(transcript_metrics(transcript.stdout))
        notes = guest.run(
            f"cd ~/code/machine-control && /opt/homebrew/bin/python3 bin/machine-control usage show "
            f"--session-ref {session_id} --commands")
        (trial_dir / "usage-notes.json").write_text(notes.stdout)
        audit = guest.run(
            f"cd ~/code/machine-control && /opt/homebrew/bin/python3 bin/machine-control audit history "
            f"--session-ref {session_id} --limit 500")
        (trial_dir / "audit.json").write_text(audit.stdout)
        record.update(audit_metrics(audit.stdout))
        capture = mc(*selector, "desktop", "capture", "--scope", "display", check=False)
        path = (capture.get("data") or {}).get("artifactPath")
        if path:
            mc(*selector, "desktop", "artifact", path, str(trial_dir / "final.png"), check=False)
    except Exception as error:  # Record and continue with the next trial.
        record["error"] = str(error)
    finally:
        record["wallSeconds"] = round(time.monotonic() - started)
        if guest:
            guest.close()
        released = mc("--target", args.target, "--claim", claim, "workspace", "release", handle,
                      check=False)
        record["released"] = (released.get("data") or {}).get("disposition")
        (trial_dir / "trial.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def transcript_metrics(text):
    calls = cua = mc_calls = mc_repl = 0
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = item.get("payload") or {}
        if item.get("type") == "response_item" and payload.get("type") in ("function_call", "custom_tool_call"):
            calls += 1
            body = json.dumps(payload.get("arguments") or payload.get("input") or "")
            cua += "cua." in body or "getApp(" in body
            mc_repl += payload.get("name") == "mc" or '"server": "mc"' in body
            mc_calls += body.count("machine-control")
    return {"toolCalls": calls, "computerUseCalls": cua, "machineControlInvocations": mc_calls,
            "mcReplCalls": mc_repl}


def audit_metrics(text):
    try:
        events = json.loads(text).get("events", [])
    except json.JSONDecodeError:
        return {}
    results = [e for e in events if e.get("event") == "command.result"]
    refused = [e for e in results if e.get("accepted") is False or e.get("errorCode")]
    codes = {}
    for event in refused:
        codes[event.get("errorCode") or f"exit {event.get('exitCode')}"] = codes.get(
            event.get("errorCode") or f"exit {event.get('exitCode')}", 0) + 1
    return {"machineControlCommands": len(results), "machineControlRefusals": codes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="macos-exp")
    parser.add_argument("--task", action="append", help="Task id; repeat; default all")
    parser.add_argument("--route", action="append", choices=sorted(ROUTES),
                        help="Default: machine-control and computer-use")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--results", type=Path, default=Path(os.environ.get(
        "XDG_STATE_HOME", Path.home() / ".local/state")) / "machine-control/experiments")
    parser.add_argument("--ssh-key", type=Path, default=Path.home() / ".ssh/mc-experiments_ed25519")
    parser.add_argument("--known-hosts", type=Path, default=Path.home() / ".ssh/mc-experiments_known_hosts")
    parser.add_argument("--host-key-alias", default="mc-experiment-base")
    parser.add_argument("--guest-user", default="admin")
    parser.add_argument("--project", default="/Users/admin/code/machine-control")
    args = parser.parse_args()

    tasks = [json.loads((TASKS / name / "task.json").read_text())
             for name in (args.task or sorted(p.name for p in TASKS.iterdir() if p.is_dir()))]
    plan = [(task, route, n) for task in tasks for route in (args.route or ["computer-use", "machine-control"])
            for n in range(1, args.repetitions + 1)]
    random.shuffle(plan)
    run_dir = args.results / f"run-{now()}"
    run_dir.mkdir(parents=True, mode=0o700)
    print(f"Run {run_dir} with {len(plan)} trials", flush=True)
    summary = []
    for task, route, n in plan:
        record = run_trial(args, task, route, n, run_dir)
        summary.append(record)
        print(json.dumps({k: record.get(k) for k in (
            "task", "route", "repetition", "oracle", "agentSeconds", "toolCalls",
            "machineControlRefusals", "error", "released")}), flush=True)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
