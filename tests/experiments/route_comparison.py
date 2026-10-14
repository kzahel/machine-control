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
import hashlib
import shlex
import stat
import os
from pathlib import Path
import random
import re
import socket
import subprocess
import sys
import time
import urllib.request

from measurements import transcript_metrics, claude_transcript_metrics
from agent_profiles import DEFAULT_MODELS, launch_request, qualify

ROOT = Path(__file__).resolve().parents[2]
MC_REPL = Path(__file__).resolve().parent / "mc-repl" / "mc-repl.mjs"
# Registered only in mc-repl trial clones; the base image stays unchanged.
MC_REPL_CONFIG = """
[mcp_servers.mc]
command = "/opt/homebrew/bin/node"
args = ["/Users/admin/experiment/mc-repl.mjs"]
startup_timeout_sec = 30
"""
MC_PYTHON_CONFIG = """
[mcp_servers.mc]
command = "/opt/homebrew/bin/python3"
args = ["/Users/admin/code/machine-control/bin/machine-control", "--target", "host", "mcp", "--session-id-file", "~/experiment/mc-session.id"]
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
    "mc-python": (
        "Use the mc tool (a persistent Python session over Machine Control; its description "
        "lists the blocking Python API) for all UI work. Do not write await. Do not use the "
        "machine-control CLI, Codex Computer Use, AppleScript, osascript or System Events, and "
        "do not use shell commands to change the files or settings the task is about."),
    "computer-use": (
        "Use Codex Computer Use (the cua object in your JavaScript tool) for all UI work. "
        "Do not use Machine Control, AppleScript, osascript or System Events, and do not use "
        "shell commands to change the files or settings the task is about."),
}
COMMON = ("Nobody is at the computer and nobody will answer questions. If you get stuck, "
          "stop and report exactly what blocked you. Do not delegate or spawn other agents. "
          "Finish with one line starting with "
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

    def run(self, command, stdin=None, timeout=300, binary=False):
        return subprocess.run(["ssh", *self.options, f"{self.args.guest_user}@{self.ip}", command],
                              input=stdin, capture_output=True, text=not binary, timeout=timeout)

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


def publish_session_identity(guest, provider, identifier):
    """Publish only an exact YA process ID backed by its native transcript.

    YA may initially report a provisional launch ID. Do not publish that ID or
    search for the newest transcript; require this process's exact native file.
    """
    if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', identifier):
        return False
    result = guest.run('/opt/homebrew/bin/python3 -', stdin=f'provider={provider!r}\nidentifier={identifier!r}\n'+'''
import os
from pathlib import Path
root=Path.home()/('.codex/sessions' if provider=='codex' else '.claude/projects')
matches=list(root.rglob('*'+identifier+'.jsonl'))
if len(matches)!=1 or not matches[0].stat().st_size:
    raise SystemExit(3)
path=Path.home()/'experiment/mc-session.id'
temporary=path.with_suffix('.tmp')
fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as stream:stream.write(identifier+'\\n')
temporary.replace(path)
''')
    if result.returncode not in (0, 3):
        raise RuntimeError('Agent session identity publication failed')
    return result.returncode == 0


def wait_for_agent(guest, session_id, timeout, poll_seconds, *, clock=time.monotonic, sleep=time.sleep,
                   publish_identity=None):
    started = clock()
    deadline = started + timeout
    process = None
    timed_out = True
    published_identity = None
    while clock() < deadline:
        process = guest.ya("GET", f"/api/sessions/{session_id}/process").get("process")
        actual = (process or {}).get('sessionId')
        if publish_identity and actual:
            if published_identity and actual != published_identity:
                raise RuntimeError('Provider session changed after identity publication')
            if not published_identity and publish_identity(actual):
                published_identity = actual
        if (process or {}).get("state") in ("idle", "terminated"):
            timed_out = False
            break
        sleep(poll_seconds)
    elapsed = clock() - started
    if timed_out:
        if not process or not process.get("id"):
            raise RuntimeError("timeout without a known process; skip racing oracle")
        guest.ya("POST", f"/api/processes/{process['id']}/abort", {"blockResume": True})
        stopped = guest.ya("GET", f"/api/sessions/{session_id}/process").get("process")
        if stopped and stopped.get("state") != "terminated":
            raise RuntimeError("timeout cancellation not verified; skip racing oracle")
    return {"timedOut": timed_out, "controllerWaitSeconds": elapsed,
            "sessionIdentityPublished": bool(published_identity) if publish_identity else None,
            "completionPollSeconds": poll_seconds,
            "providerSessionId": (process or {}).get('sessionId', session_id),
            "effectiveProcess": {k:process[k] for k in ('model','requestedModel','effort','thinking','serviceTier')
                                 if process and k in process}}


def run_trial(args, task, route, index, run_dir):
    journal = subprocess.run([*CLI, "provision", "begin", "--platform", "macos",
                              "--profile", "development"], capture_output=True, text=True, check=True)
    run = json.loads(journal.stdout)["runId"]
    previous = os.environ.get("MACHINE_CONTROL_PROVISION_RUN")
    os.environ["MACHINE_CONTROL_PROVISION_RUN"] = run
    record = {"error": "trial did not finish"}
    try:
        record = _run_trial(args, task, route, index, run_dir)
        return record
    finally:
        if previous is None:
            os.environ.pop("MACHINE_CONTROL_PROVISION_RUN", None)
        else:
            os.environ["MACHINE_CONTROL_PROVISION_RUN"] = previous
        summary = ("Direct SSH setup, YA work, oracle and transcript collection are outside automatic "
                   "command coverage. Private results: " + str(run_dir) + ". " +
                   json.dumps({k: record.get(k) for k in ("error", "passed", "released", "timedOut")}))
        subprocess.run([*CLI, "provision", "note", run, "--kind", "summary"],
                       input=summary, text=True, capture_output=True, check=True)
        subprocess.run([*CLI, "provision", "finish", run, "--outcome",
                        "failed" if record.get("error") or not record.get("released") else "ready"],
                       capture_output=True, text=True, check=True)


def _run_trial(args, task, route, index, run_dir):
    trial_dir = run_dir / task["id"] / f"{route}-{index}"
    trial_dir.mkdir(parents=True, mode=0o700)
    record = {"task": task["id"], "route": route, "repetition": index, "startedAt": now(),
              "provider":args.provider, "requestedModel":args.model, "requestedEffort":args.effort,
              "instructionProfile":args.instructions}
    # Read-only identity resolution precedes workspace acquisition.
    mc("--target", args.target, "target", "doctor", check=False)
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
        # Preserve the inherited base password in a workspace-specific secret store.
        secret_dir = Path.home() / ".local/share/machine-control/secrets/experiments" / handle
        secret_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        secret = secret_dir / "guest-login-password.secret"
        fd = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(args.credential_file.read_bytes())
        if secret.read_bytes() != args.credential_file.read_bytes():
            raise RuntimeError("cloned credential handoff verification failed")
        record["credentialFile"] = str(secret)
        record["credentialVerification"] = "inherited_base_bytes_equal_mode_0600"
        deadline = time.monotonic() + 600
        while True:
            ready = mc(*selector, "target", "ensure-ready", check=False)
            if ready.get("data", {}).get("ready"):
                break
            if time.monotonic() > deadline:
                raise RuntimeError("clone did not become ready")
            time.sleep(15)
        stages = mc(*selector, "testbed", "--", "bootstrap-stages", "--kind", "prepared", "--json", check=False)
        record["bootstrapStagesAvailable"] = stages.get("schema") is not None
        guest = Guest(args, created[0])
        guest.open_tunnel()
        if args.provider == 'claude':
            # Gateway credential travels only over stdin into an owner-only guest file.
            delivered = guest.run('umask 077; mkdir -p ~/.config/aar; cat > ~/.config/aar/claude-token',
                                  stdin=args.gateway_credential_file.read_bytes(), binary=True)
            if delivered.returncode:
                raise RuntimeError('Claude gateway credential delivery failed')
            configured = guest.run('/opt/homebrew/bin/python3 -', stdin='''
import json,os
from pathlib import Path
p=Path.home()/'.claude';p.mkdir(exist_ok=True)
f=p/'settings.json'
x=json.loads(f.read_text()) if f.exists() else {}
x.update(apiKeyHelper='cat ~/.config/aar/claude-token', fastMode=False, effortLevel='medium')
x.setdefault('env',{})['ANTHROPIC_BASE_URL']='http://127.0.0.1:8417/claude'
f.write_text(json.dumps(x));os.chmod(f,0o600)
''')
            if configured.returncode:
                raise RuntimeError('Claude profile setup failed')
        else:
            checked = guest.run('/opt/homebrew/bin/python3 -', stdin='''
import tomllib
from pathlib import Path
x=tomllib.loads((Path.home()/'.codex/config.toml').read_text())
assert x.get('service_tier') in (None,'default'), 'remove saved fast-tier override in the experiment base'
''')
            if checked.returncode:
                raise RuntimeError('Codex saved speed override refused')
        # Transfer the frozen controller commit, including unpushed commits.
        transferred = guest.run("cat > /tmp/mc-experiment.bundle", stdin=args.bundle.read_bytes(),
                                binary=True, timeout=120)
        if transferred.returncode:
            raise RuntimeError("pinned bundle transfer failed")
        pinned = guest.run(
            "git -C ~/code/machine-control fetch -q /tmp/mc-experiment.bundle HEAD && "
            f"git -C ~/code/machine-control checkout -q --detach {shlex.quote(args.revision)} && "
            "rm /tmp/mc-experiment.bundle && git -C ~/code/machine-control rev-parse HEAD", timeout=120)
        if pinned.returncode or pinned.stdout.strip() != args.revision:
            raise RuntimeError("guest did not reach pinned source revision")
        record["guestRevision"] = args.revision
        record["enforcementProfile"] = ("prototype_direct_socket_no_claim_or_controller_audit"
                                        if route == "mc-repl" else "retained_claim_owner_per_operation_audit"
                                        if route == "mc-python" else "normal_route")
        fingerprint = guest.run("cd ~/code/machine-control/tests/experiments/native-efficiency && python3 -", stdin="""
import json
from pathlib import Path
from provenance import collect
configs=list((Path.home()/'.codex/plugins/cache/openai-bundled/unified-computer-use').glob('*/.mcp.json'))
if len(configs)!=1:
    raise RuntimeError('ambiguous installed Computer Use configuration; resolve selection before trial')
print(json.dumps(collect(configs[0])))
""")
        if fingerprint.returncode:
            raise RuntimeError("runtime fingerprint unavailable")
        runtime = json.loads(fingerprint.stdout)
        (trial_dir / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
        identity = {"service": runtime["service"], "artifacts": runtime["artifacts"],
                    "configSha256": runtime["configSha256"], "commands": runtime["commands"]}
        baseline = run_dir / "runtime-reference.json"
        if baseline.exists():
            if json.loads(baseline.read_text()) != identity:
                raise RuntimeError("runtime drift within pinned batch")
        else:
            baseline.write_text(json.dumps(identity, indent=2) + "\n")
        common = (TASKS / "common-chrome.sh").read_text()
        guest.run("mkdir -p ~/experiment && cat > ~/experiment/common-chrome.sh", stdin=common)
        if route in ("mc-repl", "mc-python"):
            if route == "mc-repl":
                guest.run("cat > ~/experiment/mc-repl.mjs", stdin=MC_REPL.read_text())
            if args.provider == 'codex':
                guest.run("cat >> ~/.codex/config.toml", stdin=MC_REPL_CONFIG if route == 'mc-repl' else MC_PYTHON_CONFIG)
            else:
                descriptor = ({'command':'/opt/homebrew/bin/node','args':['/Users/admin/experiment/mc-repl.mjs']}
                              if route == 'mc-repl' else {'command':'/opt/homebrew/bin/python3',
                                'args':['/Users/admin/code/machine-control/bin/machine-control','--target','host','mcp',
                                        '--session-id-file','~/experiment/mc-session.id']})
                guest.run('/opt/homebrew/bin/python3 -', stdin=f'config={descriptor!r}\n'+'''
from pathlib import Path
import json,os
f=Path.home()/'.claude.json';x=json.loads(f.read_text()) if f.exists() else {}
x.setdefault('mcpServers',{})['mc']=config
f.write_text(json.dumps(x));os.chmod(f,0o600)
''')
        fixture_seed = hashlib.sha256(f"{args.seed}:{task['id']}:{index}".encode()).hexdigest()
        record['fixtureSeed'] = fixture_seed
        setup = guest.run(f"MC_EXPERIMENT_SEED={fixture_seed} bash -s", stdin=(TASKS / task["id"] / "setup.sh").read_text())
        record["setup"] = {"exit": setup.returncode, "stderr": setup.stderr[-500:]}
        if setup.returncode:
            raise RuntimeError("task setup failed")

        route_prompt = ROUTES[route]
        if route == 'machine-control' and args.instructions != 'current':
            route_prompt = (Path(__file__).parent/'instructions'/f'mc-{args.instructions}.md').read_text()
        prompt = "\n\n".join([(TASKS / task["id"] / "prompt.md").read_text().strip(), route_prompt, COMMON])
        record['promptSha256'] = hashlib.sha256(prompt.encode()).hexdigest()
        project = project_id(args.project)
        request = launch_request(args.provider, args.model, args.effort, prompt)
        record['launchSettings'] = {k:v for k,v in request.items() if k!='message'}
        session = guest.ya("POST", f"/api/projects/{project}/sessions",
                           request)
        session_id = session["sessionId"]
        record["launchSessionId"] = session_id
        record.update(wait_for_agent(guest, session_id, task.get("timeoutSeconds", 600), args.poll_seconds,
            publish_identity=(lambda identifier: publish_session_identity(guest,args.provider,identifier))
                             if route == 'mc-python' else None))
        session_id = record['providerSessionId']
        record['sessionId'] = session_id
        detail = guest.ya("GET", f"/api/projects/{project}/sessions/{session_id}")
        record["finalText"] = (detail.get("session") or {}).get("lastAgentText", "")[-1500:]

        oracle = guest.run("bash -s", stdin=(TASKS / task["id"] / "oracle.sh").read_text())
        record["oracleExit"] = oracle.returncode
        try:
            record["oracle"] = json.loads(oracle.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            record["oracle"] = {"passed": False, "detail": "oracle output unreadable"}
            record["error"] = "oracle output unreadable"
        if oracle.returncode:
            record["error"] = "oracle infrastructure failed"
        diagnostics = TASKS / task["id"] / "diagnostics.sh"
        if diagnostics.is_file():
            diagnostic = guest.run("bash -s", stdin=diagnostics.read_text())
            (trial_dir / "fixture-diagnostics.txt").write_text(diagnostic.stdout + diagnostic.stderr)

        transcript_root = '~/.codex/sessions' if args.provider=='codex' else '~/.claude/projects'
        transcript = guest.run(
            f"f=$(find {transcript_root} -name '*{session_id}.jsonl' | head -1); [ -n \"$f\" ] && cat \"$f\"",
            timeout=120)
        (trial_dir / "transcript.jsonl").write_text(transcript.stdout)
        parser = transcript_metrics if args.provider=='codex' else claude_transcript_metrics
        record.update(parser(transcript.stdout))
        record['profileQualification'] = qualify(args.provider,args.model,args.effort,record,record['effectiveProcess'])
        record["validTrial"] = (not record.get("timedOut", False) and
                                not record.get('terminalProviderError') and
                                record["transcriptComplete"] and
                                record["malformedTranscriptLines"] == 0 and oracle.returncode == 0 and
                                record['profileQualification']['qualified'])
        record["passed"] = record["validTrial"] and record["oracle"].get("passed") is True
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
    except Exception as error:  # Preserve evidence and clean up before stopping the batch.
        record["error"] = str(error)
    finally:
        record["wallSeconds"] = round(time.monotonic() - started)
        try:
            if guest:
                guest.close()
        except Exception as error:
            record["tunnelCleanupError"] = str(error)
        try:
            released = mc("--target", args.target, "--claim", claim, "workspace", "release", handle,
                          check=False)
            record["released"] = (released.get("data") or {}).get("disposition")
            if released.get("accepted") is not True or record["released"] != "discarded":
                record["releaseError"] = released.get("errorCode", "disposal_not_confirmed")
        except Exception as error:
            record["releaseError"] = str(error)
        finally:
            (trial_dir / "trial.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


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
    parser.add_argument("--credential-file", type=Path, required=True,
                        help="Canonical base login secret file; contents never enter argv or logs")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument('--provider',choices=sorted(DEFAULT_MODELS),default='codex')
    parser.add_argument('--model',help='Exact model ID; defaults to the requested baseline for this provider')
    parser.add_argument('--effort',choices=['low','medium','high'],default='medium')
    parser.add_argument('--instructions',choices=['discovery','current','quickstart'],default='current')
    parser.add_argument('--gateway-credential-file',type=Path,help='Mode-0600 scoped Claude gateway client token')
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--revision", default="HEAD", help="Freeze this local commit for the batch")
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
    args.model = args.model or DEFAULT_MODELS[args.provider]
    if args.provider=='claude' and (not args.route or 'computer-use' in args.route):
        parser.error('Claude requires explicit MC routes; Computer Use is not qualified on Claude')
    if args.provider=='claude':
        if not args.gateway_credential_file or not args.gateway_credential_file.is_file():
            parser.error('Claude requires gateway-credential-file')
        if stat.S_IMODE(args.gateway_credential_file.lstat().st_mode)!=0o600 or args.gateway_credential_file.is_symlink():
            parser.error('gateway-credential-file must be a regular mode-0600 file')

    os.umask(0o077)
    secret_stat = args.credential_file.lstat()
    if not stat.S_ISREG(secret_stat.st_mode) or stat.S_IMODE(secret_stat.st_mode) != 0o600:
        parser.error("credential-file must be a regular mode-0600 file")
    if not args.credential_file.read_bytes():
        parser.error("credential-file must not be empty")
    if args.repetitions < 1 or args.poll_seconds <= 0:
        parser.error("repetitions and poll-seconds must be positive")
    args.revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", args.revision + "^{commit}"], cwd=ROOT, text=True).strip()
    # Fixtures and runner must come from the same commit as the client.
    if subprocess.check_output(["git", "status", "--porcelain", "--", "tests/experiments"],
                               cwd=ROOT, text=True).strip():
        parser.error("commit experiment changes before running a batch")
    if args.revision != subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip():
        parser.error("run from the selected revision's checkout to freeze fixtures too")
    tasks = [json.loads((TASKS / name / "task.json").read_text())
             for name in (args.task or sorted(p.name for p in TASKS.iterdir() if p.is_dir()))]
    plan = [(task, route, n) for task in tasks for route in (args.route or ["computer-use", "machine-control"])
            for n in range(1, args.repetitions + 1)]
    random.Random(args.seed).shuffle(plan)
    run_dir = args.results / f"run-{now()}"
    run_dir.mkdir(parents=True, mode=0o700)
    args.bundle = run_dir / "source.bundle"
    subprocess.run(["git", "bundle", "create", str(args.bundle), "HEAD"], cwd=ROOT, check=True)
    manifest = {"schema": "route-comparison-batch/v1", "revision": args.revision,
                "provider":args.provider,"model":args.model,"effort":args.effort,
                "speed":"standard","instructionProfile":args.instructions,
                "seed": args.seed, "pollSeconds": args.poll_seconds,
                "plan": [{"task": t["id"], "route": r, "repetition": n} for t, r, n in plan],
                "fixtureHashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in TASKS.rglob("*") if p.is_file()}}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Run {run_dir} with {len(plan)} trials", flush=True)
    summary = []
    for task, route, n in plan:
        record = run_trial(args, task, route, n, run_dir)
        summary.append(record)
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        if record.get("error"):
            raise RuntimeError("trial infrastructure failed; inspect private receipt before continuing")
        if record.get("releaseError"):
            raise RuntimeError("workspace release unresolved; stop batch and inspect private receipt")
        if not record.get('profileQualification',{}).get('qualified'):
            raise RuntimeError('effective model profile unqualified; stop before further trials')
        print(json.dumps({k: record.get(k) for k in (
            "task", "route", "repetition", "oracle", "agentSeconds", "toolCalls",
            "machineControlRefusals", "error", "released")}), flush=True)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
