"""Installed-client discovery and instructions; neither command contacts a target."""

import json
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "machine-control-client-identity/v1"


def identity(*, paths=False):
    receipt = ROOT / "client-runtime.json"
    if receipt.is_file():
        value = json.loads(receipt.read_text(encoding="utf-8"))
        if value.get("schema") != SCHEMA or value.get("clientProtocol") != 1:
            raise ValueError("Incompatible installed CLI identity")
        if paths:
            value["paths"] = resolved_paths(value)
        return value
    value = {
        "schema": SCHEMA, "clientProtocol": 1, "residentProtocol": "machine-control/v0",
        "version": "0.3.0", "distribution": "source", "platform": platform.system().lower(),
        "features": ["agent.instructions", "host.desktop", "host.browser", "host.claims"] +
            (["desktop.delegation.v1"] if platform.system() == "Darwin" else []),
    }
    if paths:
        value["paths"] = resolved_paths(value)
    return value


def resolved_paths(value):
    """Runtime diagnostics, deliberately absent from the signed static receipt."""
    installed = value["distribution"] == "desktop"
    command = ROOT / (value["command"] if installed else "bin/machine-control")
    result = {"cliRoot": str(ROOT), "cliEntry": str(command.resolve()),
              "interpreter": str(Path(sys.executable).resolve())}
    if installed and value["platform"] == "windows":
        result.update(installationRoot=str(ROOT.parent),
                      launcher=str((ROOT.parent / "machine-control.exe").resolve()),
                      bundledResident=str((ROOT.parent / "runtime/machine-control-windows.exe").resolve()))
    else:
        result["launcher"] = str(command.resolve())
    return result


def instructions():
    launch = ""
    if platform.system() == "Windows" and (ROOT / "windows-launch.py").is_file():
        launch = """Windows desktop entry: machine-control.exe
Run the bare executable (or --start) in an interactive user session to start
the installed app and print next steps. Use --gui to open the operator window.
Help and agent commands work offline; other commands do not start the app.
Use `agent identity --paths` to identify this client installation. A new PATH
registration may require restarting your terminal or agent host application.

"""
    return launch + """Machine Control: target-native desktop and browser control

Use the installed command path provided by your launcher if PATH differs.
`host` means the computer executing this CLI, not the operator's browser host.
Capabilities and access are enforced by Machine Control and the OS. Installing
the app, receiving these instructions, and acquiring a claim grant no access.
If the resident is unavailable, ask the operator to open Machine Control;
do not install a second resident or switch to outer VM/window control.

Begin with:
  machine-control --target host target doctor
  machine-control --target host claim capabilities

If your harness supplies a live claim for this task, carry that claim instead
of acquiring another. Do not borrow another caller's claim from a refusal.
Otherwise acquire your own claim:
  machine-control --target host claim acquire --duration 30m \\
    --reason 'describe the task' --claimant-authority YOUR_ENVIRONMENT \\
    --claimant-id YOUR_TASK_ID
Inside YepAnywhere, Claude Code or Codex, omit both claimant options: the
published session ID (AGENTCTL_SESSION_ID, CLAUDE_CODE_SESSION_ID or
CODEX_THREAD_ID) becomes the claimant, linking audit history to the transcript.

Require accepted=true and retain data.claim.claimId. Carry --claim CLAIM_ID on
every subsequent target operation. Renew during long work and release promptly
in finally/trap cleanup: machine-control --target host claim release CLAIM_ID.
Caller/session ids are attribution, not credentials. Never invent identity.

For past activity, use `machine-control --target TARGET audit history`.
Filter with --claim-id, --claimant-id, --session-ref or --since; inspect coverage and resourceKey.
Claims retain self-asserted holder attribution after release, not authenticated
agent identity. An alias can refer to a replacement VM. Missing history or one
old transcript cannot prove nobody used the target later. Raw command arguments,
payloads and secret transport are omitted from this operational journal.
Alternatively `machine-control --target host run --help` describes a scoped
runner that owns doctor, claim renewal and release for a local task program.

For a fresh Windows/Linux/macOS appliance bring-up, begin a private dated
journal before preflight: `machine-control provision begin --platform PLATFORM`.
Carry its runId with global --provision-run on common CLI calls through cleanup;
nested common CLI calls inherit the selection. Factory/bootstrap --json stage
inspections record safe phase states. Add non-secret notes on stdin using
`provision note RUN_ID --kind friction|workaround|fix|follow-up|summary`.
Record waits, manual steps, workarounds, fix commits, deferred ideas and evidence
references, including direct scripts outside automatic coverage. Recording
friction does not authorize fixing it. After acceptance and claim cleanup, use
`provision finish RUN_ID --outcome ready|blocked|failed|abandoned`, and inspect
`provision show RUN_ID --markdown`. Outcome is agent-reported; missing command
results remain unknown. Keep logs private and credentials in the secret store.

Record difficult control use privately. When a goal takes more than about
three attempts, needs CLI source to work out, has no observed effect, forces a
fallback (for example Computer Use), ends with a human takeover or stops on an
error, before reporting back (it works offline), pipe the
details (commands/references tried, what happened, what finally worked) to:
  machine-control --target host --claim CLAIM_ID usage note --kind friction \\
    --goal 'one line: what you were doing'
Kinds: friction|workaround|fallback|handoff|follow-up|summary. Notes carry your
session ID; review with `usage show --commands --markdown`. No secrets.

Inspect status/capabilities and the independent Desktop/Browser modes:
  machine-control --target host --claim CLAIM_ID desktop status
  machine-control --target host --claim CLAIM_ID desktop capabilities
  machine-control --target host --claim CLAIM_ID browser profiles

An operator chooses Off, Ask first or Automatic for each surface in Settings.
Off refuses quietly. Ask first requests approval for one task. Automatic warns
before disruptive use and then starts unless the operator defers. Browser
includes supported raw CDP, page JavaScript and streamed sessions; select exact
approved profile IDs. It has no separate scripts/DevTools permission tier.
OS permissions and protected-desktop preparation remain independent.

For a multi-step task, retain one owner instead of opening a new handoff for
each observation or click:
  machine-control --target host --claim CLAIM_ID control stream \\
    --surface desktop --reason 'describe the application task' \\
    --wait 5m --duration 5m
For Browser, use --surface browser --profile PROFILE_ID. Send one common
request JSON object per line and read each result before sending the next.
Supported owners renew automatically for the live task; --duration selects a
finite renewal interval, not a total task cutoff. No repeated handoff or new
approval is needed while the claim and original consent remain valid. Use
--no-renew only for an intentionally finite owner. Stop and disconnect still
end access. Keep the target claim renewed separately, or use a scoped run.
Close stdin in finally cleanup. Empty input acquires nothing. Inspect command
help for the target's typed operations; the transport preserves native routes.

The Python ControlSession SDK supports the same retained task, with
surfaces=['desktop'] or surfaces=['browser'], profile_ids=[PROFILE_ID]. Call
wait() once to acquire, call(request) for related observations/actions, and
close() in finally or a context manager. For Browser background-only work,
operations=['browser.tabs', 'browser.snapshot', 'browser.capture'] narrows the
owner; it cannot later execute CDP or input. Unrestricted Browser tasks use a
disruptive handoff. Use control call for a single independent operation.

Pause and human takeover retain valid consent and the live waiting task but
retire active ownership. Movement alone does not interrupt. Deliberate input
yields to a fixed minute of cooldown, then a fresh warning. Use SDK wait() for
a new owner and observe again before issuing new work. Never replay an uncertain
mutation. A stream ends on interrupted/uncertain work; inspect the outcome and
start a fresh task deliberately. Denial, Off and cancellation are terminal.
Waits and heartbeats never extend finite consent. Renewal requires explicitly
advertised provider support; a heartbeat alone is not renewal.

References are scoped to runtime/session/desktop/provider generations;
rediscover after ownership changes, navigation or restart. Request acceptance,
delivery, observed effect and uncertainty are different facts. Verify the
intended application effect independently. Capture results contain bounded
artifact handles; pass the full returned handle unchanged to
`desktop artifact HANDLE OUTPUT_PATH`, carrying target and claim, then use
your harness's image viewer. A JSON pathname alone is not an image observation.

For a native Open or Save panel an app has already shown (macOS), use
`desktop dialog choose --path /absolute/path --target APP` within its admitted
Desktop task. Browser permission does not authorize OS-dialog fallback.
Locked console: when `desktop status` reports desktopState "locked", open the
Desktop owner with `control stream|call --surface desktop --prepared-console`
(or `ControlSession(..., prepared_console=True)`); it is the same on macOS and
Windows. Once accepted, the console is unlocked behind covers and relocks when
the owner ends; no separate unlock request is needed. Keep the task owner
alive; closing, expiry or a safety failure triggers native cleanup/relock.
Prepared owners renew automatically on macOS and Windows, so a long locked
task needs no new owner. Linux has no locked use and refuses with locked_use_unsupported.
Report setup refusals such as locked_use_disabled, prepared_console_unavailable
or desktop_unavailable to the operator; do not work around them. macOS still
accepts a flagless owner on a locked console for older clients. On macOS,
`desktop session unlock` is a separate managed-appliance operation that leaves
the console unlocked; workstations refuse it (operation_not_permitted_by_policy).
Use it only where status reports protectedAdministration: true. Older
scope-based resident channels cannot silently satisfy the unified v2 contract;
update the resident instead.

A trusted native desktop integration can bind a local control channel to
its selected live agent process. The installed identity negotiates this
capability; a proxy pathname or session label alone grants nothing. Use
`control call` or the ControlSession SDK for delegated ordinary desktop work.
A delegated Mac channel uses the same --prepared-console request to compose
its trust with separately approved desktop consent and prepared locked-use
control; trust alone cannot unlock or arm locked control.
Pause preserves consent but ends current control; wait for a fresh session
before new work and never replay an uncertain mutation. Closing the agent
ends its delegated tasks, while separately approved MC access remains valid.

MC access/arming never implies administrator authority. Native sudo is a
separately advertised helper with OS authentication. Never request or pass a
login password through chat, JSON, command arguments, environment or logs.
Other targets require explicitly configured adapters; the packaged local CLI
does not imply remote/device provider availability. See COMMAND --help.
"""
