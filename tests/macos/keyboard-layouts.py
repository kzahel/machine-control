#!/usr/bin/env python3
"""Live keyboard acceptance on an already claimed, running Tart appliance.

Builds a deterministic fixture, switches guest-only settings, exercises the real
resident, restores settings in finally, and optionally installs the Dvorak profile.
"""
import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

FIXTURE = "org.machine-control.keyboard-fixture"
LAYOUTS = ["com.apple.keylayout.US", "com.apple.keylayout.Dvorak", "com.apple.keylayout.DVORAK-QWERTYCMD"]
MODIFIERS = (1 << 16) | (1 << 17) | (1 << 18) | (1 << 19) | (1 << 20)


def command(args, **kwargs):
    result = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, **kwargs)
    if result.returncode:
        raise RuntimeError("Command failed: " + str(args[0]) + ": " + result.stderr.decode(errors="replace")[-1500:])
    return result.stdout


def normalized_hid_mapping(value):
    # `hidutil --get` prints OpenStep plist numbers as bare strings. Passing
    # those strings back in JSON can crash WindowServer's HID keyboard filter.
    # Require exact fields and restore only numeric 64-bit HID usage values.
    if not isinstance(value, list):
        raise ValueError("Invalid HID mapping list")
    keys = {"HIDKeyboardModifierMappingSrc", "HIDKeyboardModifierMappingDst"}
    result = []
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != keys:
            raise ValueError("Invalid HID mapping entry")
        pair = {}
        for key, raw in entry.items():
            if isinstance(raw, bool) or not isinstance(raw, (str, int)):
                raise ValueError("Invalid HID usage type")
            number = int(raw, 0) if isinstance(raw, str) and raw.lower().startswith("0x") else int(raw)
            if not 0 <= number < 1 << 64:
                raise ValueError("Invalid HID usage range")
            pair[key] = number
        result.append(pair)
    return result


def host_observation(before, after, require_unchanged=False):
    unchanged = before == after
    # A person may use the controller during the guest-only suite. Two passive
    # samples cannot attribute a change to the tested provider. Keep a strict
    # gate available for a deliberately quiet controller, and otherwise report
    # the limit honestly instead of failing keyboard effects for user activity.
    if require_unchanged and not unchanged:
        raise AssertionError("Host state changed during the controlled observation")
    return {"hostUnchanged": unchanged,
            "hostObservation": "unchanged" if unchanged else "changed_unattributed",
            "hostInputPolicy": "forbidden"}


def guest(root, browser_smoke=False):
    root = Path(root)
    environment = root / "environment"
    binary = Path.home() / "Applications/Machine Control.app/Contents/MacOS/macui"
    socket = Path.home() / "Library/Application Support/MachineControl/control.sock"
    env = lambda *args: json.loads(command([environment, *args]))
    initial = env("status")
    # The guest helper normalizes OpenStep properties to typed JSON. Validate
    # the complete map again before retaining it for restoration.
    old_mapping = normalized_hid_mapping(initial["modifierMapping"])
    revision = 0
    generation = None
    checks = 0
    state_path = root / "state.json"
    log_path = root / "events.jsonl"

    def state():
        try:
            return json.loads(state_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def wait(predicate, label):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            value = state()
            if predicate(value):
                return value
            time.sleep(0.05)
        raise AssertionError("Fixture effect missing: " + label)

    def configure(mode="text", text=""):
        nonlocal revision
        revision += 1
        path = root / "command.json"
        temporary = path.with_suffix(".new")
        temporary.write_text(json.dumps({"revision": revision, "mode": mode, "text": text}))
        temporary.replace(path)
        return wait(lambda s: s.get("revision") == revision, "fixture configuration")

    def control(operation, **kwargs):
        nonlocal generation, checks
        request = dict(operation=operation, provider="macos-native", **kwargs)
        result = json.loads(command([binary, "request", socket, json.dumps(request)]))
        assert result.get("accepted"), "Resident refused " + operation + ": " + result.get("errorCode", "unknown")
        assert result.get("hostInterference") == "none"
        if generation is None:
            generation = result["generation"]
        assert result["generation"] == generation, "Resident restarted during the layout matrix"
        checks += 1
        return result

    def key(chord, targeted=True):
        return control("input.key", key=chord, **({"target": FIXTURE} if targeted else {}))

    def text(value, native=True):
        if native:
            return control("input.text", target=FIXTURE, text=value)
        nonlocal checks
        result = json.loads(command([binary, "request", socket, json.dumps(dict(operation="input.text", target=FIXTURE, text=value))]))
        assert result.get("accepted"), "Default text route refused"
        checks += 1
        return result

    def events_since(offset):
        return [json.loads(line) for line in log_path.read_text()[offset:].splitlines() if line]

    def clean_flags():
        flags = env("status")
        assert flags["hidFlags"] & MODIFIERS == 0, "HID modifiers left set"
        assert flags["sessionFlags"] & MODIFIERS == 0, "Session modifiers left set"

    pid = None
    try:
        command(["/usr/bin/open", "-n", root / "KeyboardFixture.app", "--args", "--log", log_path,
                 "--commands", root / "command.json", "--state", state_path])
        pid = wait(lambda s: bool(s.get("pid")), "fixture launch")["pid"]
        for layout in LAYOUTS:
            for mapping in ["default", "swapped"]:
                selected = env("select", layout)
                assert selected["inputSourceId"] == layout
                mapped = env("remap", mapping)
                assert mapped["modifierProfile"] == ("alternate" if mapping == "swapped" else "standard")
                configure()
                for chord in ["cmd+l", "cmd+t", "cmd+w", "cmd+,", "cmd+shift+w", "cmd+shift+l", "cmd+.", "cmd+]", "cmd+option+l", "cmd+ctrl+l"]:
                    result = key(chord)
                    assert result["data"]["activeLayoutId"] == layout
                    wait(lambda s: s.get("menu") == chord, chord)
                    clean_flags()
                # No target activation path: use the same resident's HID route.
                configure()
                key("cmd+l", targeted=False)
                wait(lambda s: s.get("menu") == "cmd+l", "untargeted shortcut")
                configure()
                sample = "aAzZ09 !@#$%^&*()[]{}+-_=;:'\",.<>/?\\|`~ é日本語 👩‍💻"
                text(sample)
                wait(lambda s: s.get("text") == sample, "native Unicode text")
                key("cmd+a"); key("cmd+c"); key("right"); key("cmd+v")
                wait(lambda s: s.get("text") == sample + sample, "copy and paste")
                key("cmd+z")
                wait(lambda s: s.get("text") == sample, "undo")
                configure()
                text("default text é日本語 👩‍💻", native=False)
                wait(lambda s: s.get("text") == "default text é日本語 👩‍💻", "default text provider")
                configure()
                for chord in ["a", "shift+b", "1", "?", "-", "shift++"]:
                    key(chord)
                wait(lambda s: s.get("text") == "aB1?-+", "character keys and shifted punctuation")
                # Control-A follows AppKit's native start-of-line behavior.
                key("ctrl+a"); text("X")
                wait(lambda s: s.get("text") == "XaB1?-+", "logical Control shortcut")
                # Option-Left performs native word navigation; insertion proves it.
                configure(text="one two")
                key("option+left"); text("X")
                wait(lambda s: s.get("text") == "one Xtwo", "logical Option navigation")
                # Shared production credential planner/emitter, both delivery routes.
                # No real authorization sheet or credential transport is opened.
                for route in ["session", "pid"]:
                    configure("secure")
                    command([root / "credential-probe", route])
                    wait(lambda s: s.get("secureMatches") is True, "dummy credential " + route)
                    clean_flags()
                configure("web")
                offset = len(log_path.read_text())
                key("shift+a"); key("ctrl+b"); key("option+left")
                web_events = [e for e in events_since(offset) if e.get("layer") == "web" and e.get("type") == "keydown"]
                assert any(e.get("key") == "A" and e.get("shift") for e in web_events), "Web shifted key mismatch"
                assert any(e.get("ctrl") and not e.get("meta") for e in web_events), "Web Control modifier mismatch"
                assert any(e.get("opt") and not e.get("meta") for e in web_events), "Web Option modifier mismatch"
                configure()
                key("cmd+shift+l")
                offset = len(log_path.read_text())
                # Fixture content is at a known point in its own window, measured
                # from its AX bounds via the real resident, not a host screenshot.
                snap = control("snapshot", target=FIXTURE, projection="compact", maxDepth=8, maxElements=100)
                areas = [e for e in snap["data"]["elements"] if e.get("role") == "AXTextArea" and e.get("bounds", {}).get("width", 0) > 0]
                assert len(areas) == 1
                bounds = areas[0]["bounds"]
                x, y = int(bounds["x"] + 30), int(bounds["y"] + 30)
                control("input.click", target=FIXTURE, x=x, y=y)
                pointer = [e for e in events_since(offset) if e.get("layer") == "pointer"]
                assert pointer and pointer[-1]["flags"] & MODIFIERS == 0, "Pointer inherited modifiers"
                text("after chord")
                wait(lambda s: s.get("text") == "after chord", "plain input after pointer")
                clean_flags()
                print(json.dumps({"layout": layout, "mapping": mapping, "passed": True, "checks": checks}), flush=True)
        if browser_smoke:
            env("select", "com.apple.keylayout.Dvorak")
            env("remap", "swapped")
            output = command(["/usr/bin/python3", root / "keyboard-browser-guest.py", root / "browser-smoke"])
            print(output.decode(), end="", flush=True)
        return {"passed": True, "cells": 6, "residentChecks": checks, "browserSmoke": browser_smoke}
    finally:
        env("select", initial["inputSourceId"])
        payload = json.dumps({"UserKeyMapping": old_mapping})
        command(["/usr/bin/hidutil", "property", "--set", payload])
        if pid:
            # Kill only the process launched from our unique scratch fixture.
            actual = command(["/bin/ps", "-p", str(pid), "-o", "command="]).decode()
            if str(root / "KeyboardFixture.app") in actual:
                command(["/bin/kill", "-TERM", str(pid)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guest", metavar="SCRATCH", help=argparse.SUPPRESS)
    parser.add_argument("--target", default="macos")
    parser.add_argument("--claim", default=os.environ.get("MACHINE_CONTROL_CLAIM_ID"))
    parser.add_argument("--require-host-unchanged", action="store_true", help="Require identical passive host samples; use only with a deliberately quiet controller")
    parser.add_argument("--browser-smoke", action="store_true", help="Also verify real Chrome for Testing effects under Dvorak/remapped modifiers")
    parser.add_argument("--install-profile", action="store_true", help="Persist Dvorak, swapped Command/Option, and Caps→Control in the existing guest")
    args = parser.parse_args()
    if args.guest:
        print(json.dumps(guest(args.guest, args.browser_smoke)), flush=True)
        return
    if not args.claim:
        parser.error("--claim or MACHINE_CONTROL_CLAIM_ID is required")
    repo = Path(__file__).resolve().parents[2]
    base = [repo / "bin/machine-control", "--target", args.target, "--claim", args.claim]
    runtime_env = dict(os.environ, MACVM_FORBID_OUTER_UI="true")
    def mc(*argv, **kwargs):
        return command([*base, *argv], env=runtime_env, **kwargs)
    doctor = json.loads(mc("target", "doctor"))
    assert doctor.get("ready") and doctor["target"]["profile"] == "macos-aqua-tart", "Healthy Tart target required"
    remote = "/tmp/machine-control-keyboard-" + uuid.uuid4().hex
    source = repo / "platforms/macos/guests/macos/keyboard-fixture"
    with tempfile.TemporaryDirectory(prefix="mc-keyboard-") as scratch:
        stage = Path(scratch)
        app = stage / "KeyboardFixture.app/Contents"
        (app / "MacOS").mkdir(parents=True)
        command(["/usr/bin/xcrun", "swiftc", source / "KeyboardFixture.swift", "-o", app / "MacOS/KeyboardFixture"])
        (app / "Info.plist").write_bytes((source / "Info.plist").read_bytes())
        command(["/usr/bin/codesign", "--force", "--sign", "-", app.parent])
        command(["/usr/bin/xcrun", "swiftc", source / "environment.swift", "-o", stage / "environment"])
        command(["/usr/bin/xcrun", "swiftc", "-parse-as-library", source / "credential-probe.swift",
                 repo / "platforms/macos/resident/Sources/macui/KeyboardInput.swift", "-o", stage / "credential-probe"])
        (stage / "keyboard-layouts.py").write_bytes(Path(__file__).read_bytes())
        (stage / "keyboard-browser-guest.py").write_bytes(Path(__file__).with_name("keyboard-browser-guest.py").read_bytes())
        archive = stage / "payload.tar"
        with tarfile.open(archive, "w") as tar:
            for name in ["KeyboardFixture.app", "environment", "credential-probe", "keyboard-layouts.py", "keyboard-browser-guest.py"]:
                tar.add(stage / name, arcname=name)
        before = json.loads(mc("testbed", "--", "host-state"))
        try:
            mc("testbed", "--", "exec", "/bin/mkdir", "-p", remote)
            mc("testbed", "--", "exec", "-i", "/usr/bin/tar", "-xf", "-", "-C", remote, input=archive.read_bytes())
            # Stream bounded progress while the single guest-native suite runs.
            proc = subprocess.Popen([str(a) for a in [*base, "testbed", "--", "exec", "/usr/bin/python3", remote + "/keyboard-layouts.py", "--guest", remote, *(["--browser-smoke"] if args.browser_smoke else [])]], env=runtime_env)
            try:
                if proc.wait(timeout=900):
                    raise AssertionError("Guest keyboard matrix failed")
            finally:
                if proc.poll() is None:
                    proc.terminate(); proc.wait(timeout=10)
            if args.install_profile:
                installed = json.loads(mc("testbed", "--", "exec", remote + "/environment", "install-profile"))
                assert installed["inputSourceId"] == "com.apple.keylayout.Dvorak"
                assert installed["modifierProfile"] == "alternate"
                assert set(LAYOUTS).issubset(installed["enabledLayouts"])
                print(json.dumps(installed), flush=True)
            after = json.loads(mc("testbed", "--", "host-state"))
            observation = host_observation(before, after, args.require_host_unchanged)
            print(json.dumps({"passed": True, **observation, "persistentProfile": args.install_profile}))
        finally:
            mc("testbed", "--", "exec", "/bin/rm", "-rf", remote)


if __name__ == "__main__":
    main()
