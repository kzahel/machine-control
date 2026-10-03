#!/usr/bin/env python3
"""Opt-in claimed Mac admission acceptance against an isolated fixture.

The caller prepares existing OS consent and operator authorization. This runner
does not change either. The fixture's independent state must be local to this
controller; target-native effects still travel through the common live channel.
For --pause, use the native operator UI after the readiness message. Raw state,
references and authority never enter the printed evidence.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
import machine_control as mc
from control_session import ControlSession


def run(args):
    _, target = mc.select_target(mc.load_registry(args.registry)[0], args.target)
    target = {**target, "_claimId": args.claim, "environment": {
        **target.get("environment", {}), "MACHINE_CONTROL_CLAIM_ID": args.claim}}

    def oracle():
        return json.loads(Path(args.fixture_state).read_text())

    def focused(value):
        return all(value.get(key) is True for key in
                   ("applicationActive", "keyWindow", "textFocused"))

    if not focused(oracle()):
        raise AssertionError("Fixture must have keyboard focus before submission")
    with ControlSession(target, reason="Validate polite native fixture control",
                        wait=args.timeout, duration=120) as first:
        with ControlSession(target, reason="Validate a second waiting owner",
                            wait=args.timeout, duration=120) as second:
            end = time.monotonic() + args.timeout
            announced = False
            while time.monotonic() < end:
                state = first.status()["state"]
                if state == "announcing":
                    announced = True
                    if not focused(oracle()):
                        raise AssertionError("Countdown changed independent focus")
                if state == "offered":
                    break
                time.sleep(.1)
            else:
                raise AssertionError("No activation offer before deadline")
            if not announced:
                raise AssertionError("Unlocked notice was not observed")
            first.wait()
            if second.status()["state"] != "waiting_for_resource":
                raise AssertionError("Second owner did not wait for the resource")
            before = oracle()["count"]
            response = first.call({"operation": "snapshot", "provider": "macos-native",
                                   "target": args.fixture, "depth": 6})
            if not response.get("accepted"):
                raise AssertionError("Native fixture snapshot refused")
            button = next(item for item in response["data"]["elements"]
                          if any(item.get(key) == "Increment" for key in
                                 ("title", "name", "label"))
                          or item.get("identifier") == "fixture.increment")
            response = first.call({"operation": "action", "provider": "macos-native",
                                   "action": "press", "reference": button["reference"]})
            if not response.get("accepted"):
                raise AssertionError("Native fixture effect refused")
            deadline = time.monotonic() + 5
            while oracle()["count"] == before and time.monotonic() < deadline:
                time.sleep(.1)
            if oracle()["count"] != before + 1:
                raise AssertionError("Independent effect count differs from one")
            print("PASS: countdown kept focus; second owner waited; native effect delta=1",
                  flush=True)
            if args.pause:
                print("Ready: choose Pause until Resume in the native operator UI",
                      flush=True)
                deadline = time.monotonic() + min(90, args.timeout)
                while time.monotonic() < deadline:
                    states = [owner.status() for owner in (first, second)]
                    if all(value["state"] == "paused" and
                           "manual" in value["blockingReasons"] for value in states):
                        break
                    time.sleep(.1)
                else:
                    raise AssertionError("Both owners did not enter manual pause")
                # Do not replay the earlier action: an interrupted provider may
                # already have delivered it. Reuse only a read-only observation.
                try:
                    refused = first.call({"operation": "windows", "provider": "macos-native"})
                except mc.ClientError as error:
                    if error.code != "control_interrupted":
                        raise
                    refused = {"accepted": False}
                if refused.get("accepted"):
                    raise AssertionError("Paused owner dispatched a governed observation")
                if oracle()["count"] != before + 1:
                    raise AssertionError("Effect changed while paused")
                print("PASS: manual pause fenced both owners; no further effect", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", help="Private common CLI registry")
    parser.add_argument("--target", default="host")
    parser.add_argument("--claim", required=True)
    parser.add_argument("--fixture", default="org.machine-control.fixture")
    parser.add_argument("--fixture-state", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--pause", action="store_true")
    args = parser.parse_args()
    if not 10 <= args.timeout <= 900:
        parser.error("timeout must be 10..900 seconds")
    run(args)


if __name__ == "__main__":
    main()
