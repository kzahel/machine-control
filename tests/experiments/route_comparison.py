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
import importlib.util
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
import sky_skill_acceptance as sky_skill

ROOT = Path(__file__).resolve().parents[2]
_runtime_spec = importlib.util.spec_from_file_location('mc_runtime_selection',
    Path(__file__).parent / 'native-efficiency/runtime_selection.py')
runtime_selection = importlib.util.module_from_spec(_runtime_spec)
_runtime_spec.loader.exec_module(runtime_selection)
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
    "sky-external": (
        "Use the sky_experiment MCP server's js tool and genuine cua API for all UI work. "
        "If MCP tools are still starting, use WaitForMcpServers when available, or tool "
        "discovery, before declaring the server unavailable. "
        "This is persistent JavaScript, not Python. Start with exactly one API call: "
        "var app = await cua.getApp(\"com.apple.TextEdit\"). Read the returned documentation "
        "before continuing. Use documented key names, including case (for example Return). "
        "Follow the runtime's API and use fresh observations; retain "
        "native refusals. Only TextEdit is preauthorized for this experiment. "
        "Obtain a screenshot at least once and inspect its returned image. "
        "After final verification call sky_close to release the runtime. "
        "Do not use Machine Control, AppleScript, osascript, System Events, other agents, "
        "or shell commands to change the task files/settings."),
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
                   publish_identity=None, observe_process=None):
    started = clock()
    deadline = started + timeout
    process = None
    timed_out = True
    published_identity = None
    while clock() < deadline:
        process = guest.ya("GET", f"/api/sessions/{session_id}/process").get("process")
        if observe_process and process:
            observe_process(process)
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


def pinned_input(path, revision, *, directory=False):
    """Require exact tracked bytes from the selected checkout, including overrides."""
    path = Path(path).resolve(strict=True)
    if not path.is_relative_to(ROOT) or path == ROOT or path.is_dir() != directory:
        raise ValueError('experiment input must be a tracked file/directory within the pinned checkout')
    relative = path.relative_to(ROOT).as_posix()
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '-z', revision, '--', relative], cwd=ROOT)
    entries = {}
    for entry in tree.split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        mode, kind, blob = metadata.decode().split()
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('experiment inputs must be regular tracked files')
        tracked = ROOT / name.decode()
        if tracked.is_symlink() or not tracked.is_file():
            raise ValueError('experiment input missing or linked')
        frozen = subprocess.check_output(['git', 'cat-file', 'blob', blob], cwd=ROOT)
        if tracked.read_bytes() != frozen:
            raise ValueError('experiment input differs from pinned revision')
        entries[name.decode()] = hashlib.sha256(frozen).hexdigest()
    actual = {p.relative_to(ROOT).as_posix() for p in path.rglob('*') if p.is_file() or p.is_symlink()} if directory else {relative}
    if not entries or actual != set(entries):
        raise ValueError('experiment input contains untracked or missing files')
    return {'path': relative, 'hashes': entries}


def trial_inputs(args, task, route):
    task_root = Path(getattr(args, 'task_root', None) or TASKS).resolve()
    instruction_file = getattr(args, 'instruction_file', None)
    sky_skill.validate_profile(args.provider, args.model, [route], [task['id']], args.instructions)
    if args.instructions == 'skill' and (task_root != TASKS or instruction_file):
        raise ValueError('skill uses the frozen TextEdit fixtures and public guide only')
    if instruction_file and route != 'machine-control':
        raise ValueError('instruction-file applies only to machine-control')
    if task_root != TASKS:
        pinned_input(task_root, args.revision, directory=True)
    if instruction_file:
        pinned_input(instruction_file, args.revision)
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', task['id']):
        raise ValueError('invalid task ID')
    return task_root


def runtime_input(args):
    path = getattr(args, 'runtime_config_file', None)
    if path is None:
        return None, None
    raw, metadata = runtime_selection.private_input(path, ROOT)
    expected = getattr(args, 'runtime_config_expected_sha256', None)
    if expected and metadata['sha256'] != expected:
        raise ValueError('runtime-config-file changed after batch selection')
    return raw, metadata


def _run_trial(args, task, route, index, run_dir):
    total_started = time.monotonic()
    task_root = trial_inputs(args, task, route)
    runtime_bytes, runtime_metadata = runtime_input(args)
    trial_dir = run_dir / task["id"] / f"{route}-{index}"
    trial_dir.mkdir(parents=True, mode=0o700)
    record = {"task": task["id"], "route": route, "repetition": index, "startedAt": now(),
              "provider":args.provider, "requestedModel":args.model, "requestedEffort":args.effort,
              "instructionProfile":args.instructions}
    if runtime_metadata:
        record['runtimeConfigInput'] = runtime_metadata
    if task_root != TASKS or getattr(args, 'instruction_file', None):
        record['inputPins'] = {}
        if task_root != TASKS:
            record['inputPins']['taskRoot'] = pinned_input(task_root, args.revision, directory=True)
        if getattr(args, 'instruction_file', None):
            record['inputPins']['instructionFile'] = pinned_input(args.instruction_file, args.revision)
    timings = record['lifecycleTimings'] = {name: None for name in (
        'preflightSeconds', 'doctorSeconds', 'acquisitionSeconds', 'readinessSeconds',
        'setupSeconds', 'taskLaunchSeconds', 'taskWaitSeconds', 'taskEvidenceSeconds',
        'ownedSessionCleanupSeconds', 'tunnelCleanupSeconds', 'workspaceCleanupSeconds', 'totalSeconds')}
    phase, phase_started = 'preflightSeconds', total_started

    def advance_phase(next_phase=None):
        nonlocal phase, phase_started
        stamp = time.monotonic()
        if phase is not None:
            timings[phase] = stamp - phase_started
        phase, phase_started = next_phase, stamp
        return stamp

    advance_phase('doctorSeconds')
    # Read-only identity resolution precedes workspace acquisition.
    lifecycle = record['lifecycleEvidence'] = {
        'initialDoctor': mc('--target', args.target, 'target', 'doctor', check=False)}
    advance_phase('acquisitionSeconds')
    before = tart_names()
    acquired = mc("--target", args.target, "workspace", "acquire", "--intent", "isolated",
                  "--claim-duration", "2h", "--reason",
                  f"Route comparison trial {task['id']} {route} {index}")
    lifecycle['workspaceAcquisition'] = acquired
    handle = acquired["data"]["handle"]
    claim = acquired["data"]["claim"]["claimId"]
    guest = None
    owned_sessions = []
    started = time.monotonic()
    advance_phase('readinessSeconds')
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
        secret_stat = secret.lstat()
        inherited_equal = secret.read_bytes() == args.credential_file.read_bytes()
        lifecycle['credentialHandoff'] = {
            'path': str(secret), 'regularFile': stat.S_ISREG(secret_stat.st_mode),
            'mode': oct(stat.S_IMODE(secret_stat.st_mode)), 'inheritedBytesEqual': inherited_equal,
            'verified': inherited_equal and stat.S_ISREG(secret_stat.st_mode) and
                        stat.S_IMODE(secret_stat.st_mode) == 0o600}
        if not lifecycle['credentialHandoff']['verified']:
            raise RuntimeError("cloned credential handoff verification failed")
        record["credentialFile"] = str(secret)
        record["credentialVerification"] = "inherited_base_bytes_equal_mode_0600"
        deadline = time.monotonic() + 600
        lifecycle['readinessChecks'] = []
        while True:
            ready = mc(*selector, "target", "ensure-ready", check=False)
            lifecycle['readinessChecks'].append(ready)
            if ready.get('accepted') is True and ready.get("data", {}).get("ready") is True:
                break
            if time.monotonic() > deadline:
                raise RuntimeError("clone did not become ready")
            time.sleep(15)
        lifecycle['readyDoctor'] = mc(*selector, 'target', 'doctor', check=False)
        if lifecycle['readyDoctor'].get('ready') is not True:
            raise RuntimeError('claimed clone doctor did not confirm ready=true')
        stages = mc(*selector, "testbed", "--", "bootstrap-stages", "--kind", "prepared", "--json", check=False)
        lifecycle["bootstrapStages"] = stages
        record["bootstrapStagesAvailable"] = stages.get("schema") is not None
        advance_phase('setupSeconds')
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
        selection_tool = str(Path(args.project) / 'tests/experiments/native-efficiency/runtime_selection.py')
        selected_runtime = None
        selection_args = []
        if runtime_metadata:
            # Only the manifest bytes travel over stdin. No env/config body in argv,
            # shell source, YA prompts, subprocess output or controller receipts.
            delivered_runtime = guest.run(shlex.join(['/opt/homebrew/bin/python3', selection_tool, 'receive',
                '--checkout', args.project, '--expected-sha256', runtime_metadata['sha256']]),
                stdin=runtime_bytes, binary=True)
            transfer_diagnostic = {'exit': delivered_runtime.returncode,
                'stdout': delivered_runtime.stdout.decode() if isinstance(delivered_runtime.stdout, bytes) else delivered_runtime.stdout,
                'stderr': delivered_runtime.stderr.decode() if isinstance(delivered_runtime.stderr, bytes) else delivered_runtime.stderr}
            (trial_dir / 'runtime-config-transfer-diagnostic.json').write_text(json.dumps(transfer_diagnostic, indent=2) + '\n')
            if delivered_runtime.returncode:
                raise RuntimeError('private runtime manifest transfer/target validation failed')
            transferred_runtime = json.loads(delivered_runtime.stdout)
            if transferred_runtime.get('configSha256') != runtime_metadata['sha256']:
                raise RuntimeError('private runtime manifest transfer fingerprint mismatch')
            selected_runtime = transferred_runtime['configPath']
            record['runtimeConfigTransfer'] = transferred_runtime
            selection_args = ['--config', selected_runtime, '--expected-sha256', runtime_metadata['sha256'], '--private']
        fingerprint = guest.run(shlex.join(['/opt/homebrew/bin/python3', selection_tool, 'fingerprint',
                                          '--checkout', args.project, *selection_args]))
        (trial_dir / 'runtime-fingerprint-diagnostic.json').write_text(json.dumps({
            'exit': fingerprint.returncode, 'stdout': fingerprint.stdout,
            'stderr': fingerprint.stderr}, indent=2) + '\n')
        if fingerprint.returncode:
            raise RuntimeError("runtime fingerprint unavailable")
        runtime = json.loads(fingerprint.stdout)
        selected_runtime = runtime['configPath']
        if runtime_metadata and runtime.get('configSha256') != runtime_metadata['sha256']:
            raise RuntimeError('runtime fingerprint differs from selected private manifest')
        record['runtimeConfigSelection'] = {'path': selected_runtime, 'sha256': runtime['configSha256'],
                                            'source': runtime.get('configSelection')}
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
        if route == 'sky-external' and args.instructions != 'skill':
            configured = guest.run('/opt/homebrew/bin/python3 -', stdin=f'selected_runtime={selected_runtime!r}\nexpected_sha256={runtime["configSha256"]!r}\n'+'''
from pathlib import Path
import hashlib,json,os,subprocess
assert hashlib.sha256(Path(selected_runtime).read_bytes()).hexdigest()==expected_sha256, 'selected runtime config changed'
base=Path.home()/'code/machine-control/tests/experiments/sky-external/bridge.py'
config={'command':'/opt/homebrew/bin/python3','args':[str(base), '--config', selected_runtime,
    '--allow-app','com.apple.TextEdit','--evidence',str(Path.home()/'experiment/sky-evidence')]}
f=Path.home()/'.claude.json';x=json.loads(f.read_text()) if f.exists() else {}
x.setdefault('mcpServers',{})['sky_experiment']=config
f.write_text(json.dumps(x));os.chmod(f,0o600)
preflight=[config['command'],*config['args']]
preflight[-1]=str(Path.home()/'experiment/sky-preflight')
messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},
 {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}},
 {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'sky_close','arguments':{}}}]
r=subprocess.run(preflight,input=''.join(json.dumps(m)+'\\n' for m in messages),capture_output=True,text=True,timeout=90)
(Path.home()/'experiment/sky-preflight-result.json').write_text(json.dumps({'stdout':r.stdout,'stderr':r.stderr,'exit':r.returncode}))
rows=[json.loads(line) for line in r.stdout.splitlines()]
assert r.returncode==0 and len(rows)==3 and not any('error' in row for row in rows), 'Sky MCP preflight failed'
assert {t['name'] for t in rows[1]['result']['tools']}=={'js','js_reset','sky_close'}
print(json.dumps({'passed':True,'tools':['js','js_reset','sky_close']}))
''')
            if configured.returncode:
                raise RuntimeError('External Sky experiment setup failed')
            record['skyPreflight'] = json.loads(configured.stdout)
            record['enforcementProfile'] = 'genuine_sky_wrapper_fixture_scoped_host_approval'
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
        setup = guest.run(f"MC_EXPERIMENT_SEED={fixture_seed} bash -s", stdin=(task_root / task["id"] / "setup.sh").read_text())
        record["setup"] = {"exit": setup.returncode, "stderr": setup.stderr[-500:]}
        if setup.returncode:
            raise RuntimeError("task setup failed")

        actual_task = (task_root / task['id'] / 'prompt.md').read_text()
        if args.instructions == 'skill':
            record['enforcementProfile'] = 'genuine_sky_wrapper_fixture_scoped_host_approval'
            record['skillSetup'] = sky_skill.run_setup(guest, args, actual_task, trial_dir / 'skill-setup',
                owned_sessions, wait_for_agent, runtime['configSha256'], runtime_artifacts=runtime['artifacts'], runtime_config=selected_runtime)
            record['stageAccounting'] = sky_skill.stage_accounting(record['skillSetup'])
            if not record['skillSetup']['passed']:
                record.update(error='skill setup gate failed; task session not launched', validTrial=False, passed=False)
                return record
            prompt = sky_skill.task_prompt(record['skillSetup']['inputs'], actual_task, COMMON)
        else:
            route_prompt = ROUTES[route]
            if getattr(args, 'instruction_file', None):
                route_prompt = Path(args.instruction_file).read_text()
            elif route == 'machine-control' and args.instructions != 'current':
                route_prompt = (Path(__file__).parent/'instructions'/f'mc-{args.instructions}.md').read_text()
            prompt = "\n\n".join([actual_task.strip(), route_prompt, COMMON])
        record['promptSha256'] = hashlib.sha256(prompt.encode()).hexdigest()
        project = project_id(args.project)
        request = launch_request(args.provider, args.model, args.effort, prompt)
        if args.instructions == 'skill':
            record['taskStartedAt'] = now()
            task_started = time.monotonic()
        record['launchSettings'] = {k:v for k,v in request.items() if k!='message'}
        advance_phase('taskLaunchSeconds')
        session = guest.ya("POST", f"/api/projects/{project}/sessions",
                           request)
        task_session = sky_skill.register_owned_session(session)
        owned_sessions.append(task_session)
        if not task_session.get('launchSessionId') or task_session.get('queueId'):
            raise RuntimeError('task launch queued or missing session identity')
        session_id = task_session['launchSessionId']
        if args.instructions == 'skill' and session_id in {record['skillSetup'].get(k) for k in
                                                         ('launchSessionId', 'providerSessionId', 'sessionId')}:
            raise RuntimeError('task session reused setup identity')
        record["launchSessionId"] = session_id
        advance_phase('taskWaitSeconds')
        record.update(wait_for_agent(guest, session_id, task.get("timeoutSeconds", 600), args.poll_seconds,
            publish_identity=(lambda identifier: publish_session_identity(guest,args.provider,identifier))
                             if route == 'mc-python' else None,
            observe_process=lambda process: sky_skill.observe_owned_process(task_session, process)))
        advance_phase('taskEvidenceSeconds')
        session_id = record['providerSessionId']
        task_session['providerSessionId'] = session_id
        if args.instructions == 'skill' and session_id == record['skillSetup'].get('sessionId'):
            raise RuntimeError('task session resolved to setup identity')
        record['sessionId'] = session_id
        detail = guest.ya("GET", f"/api/projects/{project}/sessions/{session_id}")
        record["finalText"] = (detail.get("session") or {}).get("lastAgentText", "")[-1500:]

        oracle = guest.run("bash -s", stdin=(task_root / task["id"] / "oracle.sh").read_text())
        record["oracleExit"] = oracle.returncode
        try:
            record["oracle"] = json.loads(oracle.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            record["oracle"] = {"passed": False, "detail": "oracle output unreadable"}
            record["error"] = "oracle output unreadable"
        if oracle.returncode:
            record["error"] = "oracle infrastructure failed"
        diagnostics = task_root / task["id"] / "diagnostics.sh"
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
        if route == 'sky-external':
            evidence_path = (record['skillSetup']['verification']['evidenceDir']
                             if args.instructions == 'skill' else None)
            evidence = guest.run('/opt/homebrew/bin/python3 -', stdin=f'evidence_path={evidence_path!r}\n'+'''
from pathlib import Path
import json
p=Path(evidence_path) if evidence_path else Path.home()/'experiment/sky-evidence'
print(json.dumps({f.name:f.read_text() for f in p.glob('*') if f.is_file()}))
''')
            (trial_dir/'sky-evidence.json').write_text(evidence.stdout)
            data = json.loads(evidence.stdout)
            closed = json.loads(data.get('closed.json', '{}'))
            record['skyRuntimeClosed'] = closed.get('closed', False)
            if args.instructions == 'skill':
                record['skyEvidenceDir'] = evidence_path
                record['skyRuntimeClosure'] = sky_skill.runtime_closure_evidence(data,
                    verification=record['skillSetup']['verification'], transcript=transcript.stdout)
                record['skyRuntimeClosed'] = record['skyRuntimeClosure']['passed']
                record['validTrial'] = record['validTrial'] and record['skyRuntimeClosed']
                record['passed'] = record['passed'] and record['validTrial']
        capture = mc(*selector, "desktop", "capture", "--scope", "display", check=False)
        path = (capture.get("data") or {}).get("artifactPath")
        if path:
            mc(*selector, "desktop", "artifact", path, str(trial_dir / "final.png"), check=False)
    except Exception as error:  # Preserve evidence and clean up before stopping the batch.
        record["error"] = str(error)
    finally:
        record["wallSeconds"] = round(time.monotonic() - started)
        advance_phase('ownedSessionCleanupSeconds')
        sessions_stopped = True
        if guest:
            record['ownedSessionCleanup'] = []
            for owned in owned_sessions:
                try:
                    if not owned.get('terminationVerified'):
                        record['ownedSessionCleanup'].append(sky_skill.stop_owned_session(guest, owned))
                    else:
                        record['ownedSessionCleanup'].append(dict(owned))
                except Exception as error:
                    sessions_stopped = False
                    record['ownedSessionCleanup'].append({'session': dict(owned), 'error': str(error)})
        if args.instructions == 'skill':
            task_stage = dict(record, controllerWallSeconds=time.monotonic() - task_started if record.get('taskStartedAt') else None,
                              status='failed' if record.get('error') else 'passed' if record.get('passed') else 'blocked')
            record['stageAccounting'] = sky_skill.stage_accounting(record.get('skillSetup', {}),
                task_stage if record.get('launchSessionId') else None)
        advance_phase('tunnelCleanupSeconds')
        try:
            if guest:
                guest.close()
        except Exception as error:
            record["tunnelCleanupError"] = str(error)
        advance_phase('workspaceCleanupSeconds')
        try:
            if not sessions_stopped:
                raise RuntimeError('owned session termination unverified; workspace retained for recovery')
            released = mc("--target", args.target, "--claim", claim, "workspace", "release", handle,
                          check=False)
            lifecycle["workspaceRelease"] = released
            record["released"] = (released.get("data") or {}).get("disposition")
            if released.get("accepted") is not True or record["released"] != "discarded":
                record["releaseError"] = released.get("errorCode", "disposal_not_confirmed")
        except Exception as error:
            record["releaseError"] = str(error)
            lifecycle["releaseError"] = str(error)
        finally:
            timings['totalSeconds'] = advance_phase() - total_started
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
    parser.add_argument('--instructions',choices=['discovery','current','quickstart','skill'],default='current')
    parser.add_argument('--runtime-config-file', type=Path,
                        help='Private mode-0600 exact installed target runtime manifest, outside checkout; copied over stdin')
    parser.add_argument('--gateway-credential-file',type=Path,help='Mode-0600 scoped Claude gateway client token')
    parser.add_argument('--skill-setup-timeout-seconds', type=float, default=600,
                        help='Separate bounded setup wait for the Claude sky-external skill profile')
    parser.add_argument('--task-root', type=Path, default=TASKS,
                        help='Tracked task tree within the pinned checkout; default frozen tasks')
    parser.add_argument('--instruction-file', type=Path,
                        help='Tracked pinned route instructions; machine-control only')
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
    try:
        _, runtime_metadata = runtime_input(args)
        if runtime_metadata:
            args.runtime_config_expected_sha256 = runtime_metadata['sha256']
    except (ValueError, OSError) as error:
        parser.error(str(error))
    try:
        sky_skill.validate_profile(args.provider, args.model, args.route, args.task, args.instructions)
        if args.instructions == 'skill' and (args.task_root.resolve() != TASKS or args.instruction_file):
            raise ValueError('skill uses the frozen TextEdit fixtures and public guide only')
        if args.instruction_file and set(args.route or ['computer-use', 'machine-control']) != {'machine-control'}:
            raise ValueError('instruction-file requires only the machine-control route')
    except ValueError as error:
        parser.error(str(error))
    if args.provider=='claude' and (not args.route or 'computer-use' in args.route):
        parser.error('Claude requires explicit routes; use sky-external for bounded Sky qualification')
    if 'sky-external' in (args.route or []):
        if args.provider != 'claude' or not args.task or not set(args.task) <= {'textedit-save','textedit-menu'}:
            parser.error('sky-external qualification requires Claude and explicit TextEdit save/menu tasks')
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
    if args.repetitions < 1 or args.poll_seconds <= 0 or args.skill_setup_timeout_seconds <= 0:
        parser.error("repetitions, poll-seconds and skill-setup-timeout-seconds must be positive")
    args.revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", args.revision + "^{commit}"], cwd=ROOT, text=True).strip()
    # Fixtures and runner must come from the same commit as the client.
    if subprocess.check_output(["git", "status", "--porcelain", "--", "tests/experiments"],
                               cwd=ROOT, text=True).strip():
        parser.error("commit experiment changes before running a batch")
    if args.revision != subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip():
        parser.error("run from the selected revision's checkout to freeze fixtures too")
    args.task_root = args.task_root.resolve()
    input_pins = {}
    try:
        if args.task_root != TASKS:
            input_pins['taskRoot'] = pinned_input(args.task_root, args.revision, directory=True)
        if args.instruction_file:
            args.instruction_file = args.instruction_file.resolve()
            input_pins['instructionFile'] = pinned_input(args.instruction_file, args.revision)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    task_names = args.task or sorted(p.name for p in args.task_root.iterdir() if p.is_dir())
    if any(not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) for name in task_names):
        parser.error('invalid task ID')
    tasks = [json.loads((args.task_root / name / 'task.json').read_text()) for name in task_names]
    if any(task['id'] != name for task, name in zip(tasks, task_names)):
        parser.error('task manifest ID must match directory')
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
                                  for p in args.task_root.rglob("*") if p.is_file()}}
    if input_pins:
        manifest["inputPins"] = input_pins
    if runtime_metadata:
        manifest['runtimeConfigInput'] = runtime_metadata
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
