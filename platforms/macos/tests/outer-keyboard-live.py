#!/usr/bin/env python3
"""Disruptive Tart bootstrap-keyboard acceptance on a suspended prepared VM.

The guest agent only stages/reads a disposable AppKit oracle. All tested input
uses the outer CLI. This test acquires/releases its own disruptive claim and
suspends the VM in finally. It uses only public dummy text, never credentials.
"""
import argparse
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
PLATFORM = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="macos")
    args = parser.parse_args()
    claim = None
    scratch = None

    def mc(*arguments, check=True, env=None, registry=None):
        command = [str(ROOT / "bin/machine-control"), "--target", args.target]
        if registry:
            command += ["--registry", str(registry)]
        if claim and arguments[0] != "claim":
            command += ["--claim", claim]
        environment = dict(os.environ)
        environment.pop("MACVM_ALLOW_UNVERIFIED_MODIFIERS", None)
        environment["MACVM_CAPTURE_SYSTEM_KEYS"] = "false"
        if env:
            environment.update(env)
        result = subprocess.run(command + list(arguments), text=True,
                                capture_output=True, env=environment, timeout=180)
        if check and result.returncode:
            raise RuntimeError(f"{arguments[:2]} failed: {result.stdout} {result.stderr}")
        return result

    def guest(script):
        return mc("os", "--", "/bin/bash", "-lc", script).stdout.strip()

    def put(path, value):
        guest("printf %s " + shlex.quote(value) + " > " + shlex.quote(path))

    def state():
        return json.loads(guest("cat " + scratch + "/state.json"))

    def reset():
        guest("touch " + scratch + "/reset")
        for _ in range(10):
            snapshot = guest("if test ! -e " + scratch + "/reset && test -f "
                             + scratch + "/state.json; then cat "
                             + scratch + "/state.json; fi")
            if snapshot and json.loads(snapshot) == dict(
                    text="", commands=0, shiftedCommands=0, secureMatches=False,
                    active=True, focusedField="text"):
                return
            time.sleep(.1)
        raise AssertionError("Guest oracle did not reset")

    def key(value, **kwargs):
        return mc("testbed", "--", "key", value, **kwargs)

    def text(value, **kwargs):
        return mc("testbed", "--", "type", value, **kwargs)

    doctor = json.loads(mc("target", "doctor", check=False).stdout)
    if doctor["states"]["power"] != "suspended":
        raise RuntimeError("This acceptance runner requires a suspended prepared VM")
    try:
        acquired = json.loads(mc(
            "claim", "acquire", "--disruptive", "--duration", "30m",
            "--reason", "Verify outer bootstrap keyboard against guest file effects",
            "--claimant-authority", "machine-control-test",
            "--claimant-id", f"outer-keyboard-{os.getpid()}").stdout)
        claim = acquired["data"]["claim"]["claimId"]
        mc("target", "up")
        scratch = guest("mktemp -d /private/tmp/mc-outer-keyboard.XXXXXX")
        # Only accept the exact scratch shape before interpolating or removing it.
        if not re.fullmatch(r"/private/tmp/mc-outer-keyboard\.[A-Za-z0-9]+", scratch):
            scratch = None
            raise RuntimeError("Invalid guest scratch path")
        app = scratch + "/Oracle.app"
        binary = app + "/Contents/MacOS/Oracle"
        guest("mkdir -p " + app + "/Contents/MacOS")
        put(scratch + "/oracle.swift",
            (PLATFORM / "tests/fixtures/outer-keyboard.swift").read_text())
        put(app + "/Contents/Info.plist", """<?xml version="1.0"?>
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>Oracle</string>
<key>CFBundleIdentifier</key><string>org.machine-control.outer-keyboard-oracle.UNIQUE</string>
<key>CFBundleName</key><string>Outer Keyboard Oracle</string>
</dict></plist>""".replace("UNIQUE", scratch.rsplit(".", 1)[1]))
        guest("xcrun swiftc " + scratch + "/oracle.swift -o " + binary
              + " && open -n " + app + " --args " + scratch)
        reset()
        # Fresh observation; no coordinate actions or captures of populated fields.
        capture = mc("testbed", "--", "screenshot").stdout.strip()
        print("Initial capture:", capture, flush=True)
        samples = ["AbC!@Z", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
                   "0123456789 !@#$%^&*()_+{}|:\"<>?~ []\\;',./`-="]
        for sample in samples:
            mc("claim", "renew", claim, "--duration", "30m")
            reset()
            text(sample)
            key("cmd-k")
            key("cmd-shift-k")
            text("plain")
            observed = state()
            assert observed == dict(text=sample + "plain", commands=1,
                                    shiftedCommands=1, secureMatches=False,
                                    active=True, focusedField="text"), observed
            print("Text, Command, Shift–Command, release: PASS", flush=True)
        reset()
        key("shift-a")
        key("shift-cmd-k")
        text("z")
        observed = state()
        assert observed == dict(text="Az", commands=0, shiftedCommands=1,
                                secureMatches=False, active=True,
                                focusedField="text"), observed
        print("Shift key and reversed modifier order: PASS", flush=True)
        reset()
        assert text("prefix\N{SNOWMAN}", check=False).returncode != 0
        for chord in ("ctrl-k", "option-k", "fn-k"):
            assert key(chord, check=False).returncode != 0
        assert state() == dict(text="", commands=0, shiftedCommands=0,
                               secureMatches=False, active=True, focusedField="text")
        print("Unsupported input refused before any prefix: PASS", flush=True)
        # The public dummy goes through the production owner-only file/stdin path.
        # The secure-field oracle reports only a match, never its entered bytes.
        key("cmd-j")
        assert state() == dict(text="", commands=0, shiftedCommands=0,
                               secureMatches=False, active=True, focusedField="secure")
        with tempfile.TemporaryDirectory(prefix="mc-outer-dummy-") as directory:
            dummy = Path(directory) / "dummy.secret"
            dummy.write_text("AbC!@Z\n")
            dummy.chmod(0o600)
            # The common client's registry environment wins over process env.
            # Override in a private registry, never through an ineffective env
            # var that could leave the real inventory credential selected.
            sys.path.insert(0, str(ROOT / "client"))
            from machine_control import load_registry
            target = load_registry(None)[0][args.target]
            target["environment"] = {
                **target.get("environment", {}),
                "MACVM_ADMIN_SECRET_FILE": str(dummy),
            }
            registry = Path(directory) / "dummy-target.json"
            descriptor = os.open(registry, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                json.dump({"schema": "machine-control-targets/v0",
                           "targets": {args.target: target}}, stream)
            result = mc("testbed", "--", "type-secret", registry=registry)
            assert "AbC!@Z" not in result.stdout + result.stderr
        assert state() == dict(text="", commands=0, shiftedCommands=0,
                               secureMatches=True, active=True, focusedField="secure")
        print("Dummy secure field via type-secret: PASS", flush=True)
    finally:
        if claim:
            try:
                if scratch:
                    # Verify the recorded PID still belongs to our executable;
                    # do not depend on LaunchServices' /tmp path spelling.
                    guest("""set -e
if test -f {root}/pid; then
    pid=$(cat {root}/pid)
    case "$pid" in ''|*[!0-9]*) exit 1;; esac
    command=$(ps -p "$pid" -o command= || true)
    case "$command" in
        '{binary}'|'{binary} '*) kill "$pid";;
        '') ;;
        *) echo 'Refusing to kill an unexpected fixture process' >&2; exit 1;;
    esac
    for attempt in $(seq 1 30); do
        if ! kill -0 "$pid" 2>/dev/null; then break; fi
        sleep 0.1
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo 'Fixture process did not exit' >&2; exit 1
    fi
fi
rm -rf {root}
""".format(root=scratch, binary=scratch + "/Oracle.app/Contents/MacOS/Oracle"))
                    print("Guest fixture process and files removed", flush=True)
            finally:
                try:
                    mc("target", "suspend")
                    print("VM suspended", flush=True)
                finally:
                    mc("claim", "release", claim)
                    print("Claim released", flush=True)


if __name__ == "__main__":
    main()
