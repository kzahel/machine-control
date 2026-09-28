#!/usr/bin/env python3
"""Read-only scoped-claim acceptance; never starts or focuses the target."""

import argparse
import json
from pathlib import Path
import signal
import subprocess
import sys


CLI = Path(__file__).resolve().parents[2] / "bin" / "machine-control"


def report(arguments):
    result = subprocess.run([sys.executable, str(CLI), *arguments],
                            text=True, capture_output=True, timeout=180)
    return result.returncode, json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    options = parser.parse_args()
    selection = ["--target", options.target]
    _, before = report([*selection, "target", "doctor"])
    rc, status = report([*selection, "claim", "status"])
    if rc or status.get("data", {}).get("state") != "available":
        raise SystemExit("Live acceptance requires an available target")
    # The explicit testbed escape requires the inherited claim even though the
    # dispatched status operation is read-only. Do not echo platform details.
    task = (
        "import subprocess,sys,time; "
        f"command=[sys.executable,{str(CLI)!r},'testbed','--','status']; "
        "first=subprocess.run(command,capture_output=True,timeout=30); "
        "time.sleep(23); second=subprocess.run(command,capture_output=True,timeout=30); "
        "sys.exit(first.returncode or second.returncode)"
    )
    process = subprocess.Popen([
        sys.executable, str(CLI), *selection, "run", "--duration", "60s",
        "--reason", "verify read-only scoped claim renewal and cleanup",
        "--claimant-authority", "machine-control-tests",
        "--claimant-id", "live-scoped-run", "--", sys.executable, "-c", task,
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    saved = {}
    def forward(signum, _frame):
        if process.poll() is None:
            process.send_signal(signum)
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            saved[signum] = signal.signal(signum, forward)
        _, stderr = process.communicate()
    finally:
        for signum, handler in saved.items():
            signal.signal(signum, handler)
    audits = [json.loads(line) for line in stderr.splitlines()
              if line.startswith('{"schema":"machine-control-run/v0"')]
    final = audits[-1] if audits else {}
    _, after = report([*selection, "target", "doctor"])
    rc, status = report([*selection, "claim", "status"])
    checks = {
        "taskSucceeded": process.returncode == 0,
        "claimRenewed": final.get("renewals", 0) >= 1,
        "releaseReported": final.get("cleanup", {}).get("claim") == "released",
        "claimIndependentlyAvailable": rc == 0 and status.get("data", {}).get("state") == "available",
        "powerUnchanged": before["states"]["power"] == after["states"]["power"],
    }
    print(json.dumps({"schema": "machine-control-scoped-run-acceptance/v0",
                      "passed": all(checks.values()), "checks": checks,
                      "finalPower": after["states"]["power"]}, separators=(",", ":")))
    if not all(checks.values()):
        # Only the minimized runner audit belongs in failure output.
        print(json.dumps(final), file=sys.stderr)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
