#!/usr/bin/env python3
"""Stateful, short-lease fixture; records effects separately from CLI output."""

import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time


root = Path(os.environ["SCOPE_FIXTURE_DIR"])
args = sys.argv[1:]
operation = args[0]
mode = os.environ.get("SCOPE_FIXTURE_MODE", "")
claim_id = "c-0123456789abcdef01234567"
handle = "w-scoped-fixture"
lease = root / "held.json"
with (root / "events.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "operation": operation, "args": args,
        "claim": os.environ.get("MACHINE_CONTROL_CLAIM_ID"),
        "workspace": os.environ.get("MACHINE_CONTROL_WORKSPACE_HANDLE"),
    }) + "\n")


def refusal(kind, action):
    print(json.dumps({"schema": f"machine-control-{kind}/v0",
                      "operation": action, "accepted": False,
                      "uncertainty": "none", "data": {},
                      "errorCode": "fixture_refused", "message": "private-detail"}))
    raise SystemExit(1)


if mode == "identity" and operation == "claim-status":
    refusal("claim", "status")
if mode == "acquire_refused" and operation.endswith("-acquire"):
    refusal(operation.split("-")[0], "acquire")
if operation == "claim-renew" and mode == "renew_refused":
    refusal("claim", "renew")
if operation.endswith("-release") and mode == "release_refused":
    refusal(operation.split("-")[0], "release")
if operation in {"claim-check", "claim-renew", "claim-release", "workspace-release"}:
    if not lease.exists():
        refusal(operation.split("-")[0], operation.split("-")[1])
    held = json.loads(lease.read_text())
    if held["expires"] < time.time():
        refusal(operation.split("-")[0], operation.split("-")[1])
    if operation == "workspace-release":
        assert os.environ.get("MACHINE_CONTROL_CLAIM_ID") == claim_id
        assert os.environ.get("MACHINE_CONTROL_WORKSPACE_HANDLE") is None
        assert args[args.index("--handle") + 1] == handle
    else:
        assert args[args.index("--claim-id") + 1] == claim_id
    if held.get("workspace") and operation == "claim-renew":
        assert os.environ.get("MACHINE_CONTROL_WORKSPACE_HANDLE") == handle
if operation == "claim-renew" and mode == "renew_slow":
    time.sleep(10)
if operation == "claim-acquire" and mode == "acquire_slow":
    (root / "acquiring").touch()
    time.sleep(0.5)
if operation == "claim-acquire" and mode == "unknown_receipt":
    lease.write_text('{}')
    print('{"invalid":true}')
    raise SystemExit(0)

result = subprocess.run([sys.executable, str(Path(__file__).with_name("mock-testbed.py")),
                         *args], capture_output=True, text=True)
if not result.stdout.strip().startswith("{"):
    sys.stdout.write(result.stdout)
    raise SystemExit(result.returncode)
value = json.loads(result.stdout)
if operation in {"claim-acquire", "workspace-acquire", "claim-renew"}:
    claim = value["data"]["claim"]
    seconds = int(os.environ.get("SCOPE_FIXTURE_TTL", "30"))
    now = datetime.datetime.now(datetime.timezone.utc)
    def stamp(moment):
        return moment.isoformat(timespec="seconds").replace("+00:00", "Z")
    claim.update(acquiredAt=stamp(now), renewedAt=stamp(now),
                 expiresAt=stamp(now + datetime.timedelta(seconds=seconds)),
                 maxExpiresAt=stamp(now + datetime.timedelta(hours=4)),
                 remainingSeconds=seconds)
    if operation == "workspace-acquire":
        value["data"]["handle"] = handle
    if operation == "claim-renew":
        claim["useClass"] = held["use_class"]
    workspace = operation == "workspace-acquire" or (
        operation == "claim-renew" and held.get("workspace"))
    lease.write_text(json.dumps({"expires": time.time() + seconds,
                                "workspace": workspace,
                                "use_class": claim["useClass"]}))
    if mode == "bad_receipt":
        claim["unexpected"] = True
    if operation == "claim-renew" and mode == "renew_mismatch":
        claim["claimId"] = "c-ffffffffffffffffffffffff"
if operation == "workspace-release":
    value["data"]["handle"] = handle
if operation.endswith("-release"):
    lease.unlink()
if operation == "claim-status" and lease.exists():
    # A status query is only used before acquisition in these fixtures.
    raise SystemExit(9)
print(json.dumps(value))
raise SystemExit(result.returncode)
