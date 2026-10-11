#!/usr/bin/env python3
"""Test-only native companion with file-controlled stalls, no production switches."""
import argparse
from pathlib import Path
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--gate", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.runtime))
import desktop
from provider import Provider


class FaultProvider(Provider):
    def stall(self, stage):
        args.gate.with_suffix(".started").write_text(stage)
        end = time.monotonic() + 35
        while not args.gate.exists() and time.monotonic() < end:
            time.sleep(.02)

    def snapshot(self, request):
        if request.get("query") == "stall":
            self.stall("observation")
        return super().snapshot(request)

    def before_effect(self):
        if args.gate.with_suffix(".effect").exists():
            self.stall("preflight")
        super().before_effect()

    def action(self, request):
        result = super().action(request)
        if args.gate.with_suffix(".after").exists():
            self.stall("dispatched")
        return result


desktop.Provider = FaultProvider
# Let production main parse only its own arguments.
sys.argv = [sys.argv[0]]
desktop.main()
