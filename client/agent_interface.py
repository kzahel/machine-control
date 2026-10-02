"""Installed-client discovery and instructions; neither command contacts a target."""

import json
from pathlib import Path
import platform


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "machine-control-client-identity/v1"


def identity():
    receipt = ROOT / "client-runtime.json"
    if receipt.is_file():
        value = json.loads(receipt.read_text(encoding="utf-8"))
        if value.get("schema") != SCHEMA or value.get("clientProtocol") != 1:
            raise ValueError("Incompatible installed CLI identity")
        return value
    return {
        "schema": SCHEMA, "clientProtocol": 1, "residentProtocol": "machine-control/v0",
        "version": "0.3.0", "distribution": "source", "platform": platform.system().lower(),
        "features": ["agent.instructions", "host.desktop", "host.browser", "host.claims"],
    }


def instructions():
    return """Machine Control: target-native desktop and browser control

Use the installed command path provided by your launcher if PATH differs.
`host` means the computer executing this CLI, not the operator's browser host.
Capabilities and access are enforced by Machine Control and the OS. Installing
the app, receiving these instructions, and acquiring a claim grant no access.
If the resident is unavailable, ask the operator to open Machine Control;
do not install a second resident or switch to outer VM/window control.

Begin with:
  machine-control --target host target doctor
  machine-control --target host claim capabilities
  machine-control --target host claim acquire --duration 30m \\
    --reason 'describe the task' --claimant-authority YOUR_ENVIRONMENT \\
    --claimant-id YOUR_TASK_ID

Require accepted=true and retain data.claim.claimId. Carry --claim CLAIM_ID on
every subsequent target operation. Renew during long work and release promptly
in finally/trap cleanup: machine-control --target host claim release CLAIM_ID.
Caller/session ids are attribution, not credentials. Never invent identity.
Alternatively `machine-control --target host run --help` describes a scoped
runner that owns doctor, claim renewal and release for a local task program.

Inspect status/capabilities; request only the scopes needed for this task:
  machine-control --target host --claim CLAIM_ID desktop status
  machine-control --target host --claim CLAIM_ID desktop capabilities
  machine-control --target host --claim CLAIM_ID grant request \\
    --scope observe --scope control --reason 'describe the task' --duration 10m
  machine-control --target host --claim CLAIM_ID grant status

A person at the target approves access in MC's native UI. Cancellation,
timeout, refusal and revocation are terminal for the attempt; report them
without automatically retrying or weakening policy. Discovery can work without
an access grant. Missing OS permissions are separate from MC approval.

Desktop workflow:
  machine-control --target host --claim CLAIM_ID desktop applications
  machine-control --target host --claim CLAIM_ID desktop windows
  machine-control --target host --claim CLAIM_ID desktop snapshot --target APP
  machine-control --target host --claim CLAIM_ID desktop capture \\
    --scope window --target active_window

Use desktop --help for action/input options. Observe before acting. References
are scoped to runtime/session/desktop/provider generations; rediscover after
navigation or restart. Never retarget or replay an uncertain mutation. Request
acceptance, delivery, observed effect and uncertainty are different facts;
verify the intended application effect independently.

Browser workflow (requires the installed extension and a browser scope):
  machine-control --target host --claim CLAIM_ID grant request \\
    --scope browser --reason 'describe the browser task' --duration 10m
  machine-control --target host --claim CLAIM_ID browser tabs
  machine-control --target host --claim CLAIM_ID browser snapshot --tab TAB_ID
  machine-control --target host --claim CLAIM_ID browser click \\
    --tab TAB_ID --reference REFERENCE
  machine-control --target host --claim CLAIM_ID browser capture --tab TAB_ID

Use browser COMMAND --help for options. Raw CDP/evaluation/endpoints require
the separate devtools scope; do not request it for ordinary browser semantics.
Capture results contain bounded artifact handles. Retrieve them with
`desktop artifact HANDLE OUTPUT_PATH`, carrying target and claim, then use
your harness's image viewer. A JSON pathname alone is not an image observation.
Release browser debugger sessions when finished with `browser release`.

MC access/arming never implies administrator authority. Native sudo is a
separately advertised helper with OS authentication. Never request or pass a
login password through chat, JSON, command arguments, environment or logs.
Other targets require explicitly configured adapters; the packaged local CLI
does not imply remote/device provider availability. See COMMAND --help.
"""
