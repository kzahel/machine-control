#!/usr/bin/env python3
"""Run a prepared Desktop task against the installed app on a claimed VM."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import uuid


def poll(check, label, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if result := check():
            return result
        time.sleep(.1)
    raise AssertionError(label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--ending", choices=("disconnect", "expiry", "preparing", "takeover", "stop", "resident"), required=True)
    parser.add_argument("--skip-pointer", action="store_true")
    parser.add_argument("--extended-input", action="store_true")
    parser.add_argument("--renew", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(args.runtime))
    from gnome_unlock import GnomeUnlock

    root = Path(os.environ["XDG_RUNTIME_DIR"]) / "machine-control-desktop"
    native = GnomeUnlock()
    original = native.observe()
    console = original.console

    def message(peer, operation, **fields):
        request = {"operation": operation, "requestId": uuid.uuid4().hex, **fields}
        peer.sendall(json.dumps(request).encode() + b"\n")
        with peer.makefile("rb", buffering=0) as stream:
            return json.loads(stream.readline(16 * 1024 * 1024))

    def connect(path):
        peer = socket.socket(socket.AF_UNIX)
        peer.settimeout(30)
        peer.connect(str(path))
        return peer

    def status():
        with connect(root / "desktop.sock") as peer:
            return message(peer, "status")["data"]

    preflight = status()
    assert preflight["lockedUse"]["phase"] == "ready", preflight["lockedUse"]
    assert preflight["admission"]["surfaces"]["desktop"]["mode"] == "automatic"
    with tempfile.TemporaryDirectory(prefix="mc-covered-installed-") as temporary:
        state = Path(temporary) / ".cache/linuxvm-testbed/fixture/state.json"
        fixture = subprocess.Popen(["/usr/bin/python3", str(args.fixture)], env={**os.environ, "HOME": temporary})
        try:
            poll(state.exists, "Fixture did not start")
            if original.unlocked:
                native.lock(console)
            poll(lambda: status()["desktopState"] == "locked", "App did not observe lock")
            with connect(root / "desktop.sock") as peer:
                common = dict(schema="machine-control-admission/v2", waitSeconds=30,
                              durationSeconds=8 if args.ending == "expiry" else 40, reason="Verify packaged covered task")
                plain = message(peer, "control.open", surfaces=["desktop"], **common)
                assert plain["errorCode"] == "prepared_console_required", plain
            with connect(root / "desktop.sock") as peer:
                opened = message(peer, "control.open", surfaces=["desktop"], preparedConsole=True, **common)
                assert opened["accepted"], opened
                sequence = 0
                def send(operation, **fields):
                    nonlocal sequence
                    sequence += 1
                    reply = message(peer, operation, requestSequence=sequence, **fields)
                    assert reply["accepted"], reply
                    return reply["data"]
                def offered():
                    view = send("control.heartbeat")
                    return view if view["state"] == "offered" else None
                offer = poll(offered, "No offer for a covered Desktop task", 25)
                active = send("control.accept", offerGeneration=offer["offerGeneration"])
                assert active["consoleUnlock"]["state"] in ("unlocking", "unlocked"), active
                fence = {key: active[key] for key in ("sessionId", "resourceGenerations")}
                if args.ending == "preparing":
                    assert active["consoleUnlock"]["state"] == "unlocking", active
                    cancelled = send("control.cancel")
                    assert cancelled["state"] == "ended", cancelled
                    for _ in range(45):
                        observed = native.observe()
                        assert observed.console == console and observed.locked
                        time.sleep(.1)
                    print("console_stayed_locked_when_prepared_owner_cancelled", flush=True)
                    return
                def unlocked():
                    view = send("control.heartbeat")
                    native_status = view["consoleUnlock"]
                    assert view["state"] == "active" and native_status["state"] != "failed", view
                    return native_status["state"] == "unlocked"
                poll(unlocked, "The covered owner did not unlock the console", 20)

                def action(operation, **fields):
                    value = send("control.dispatch", request={"operation": operation, **fields}, **fence)
                    assert value["accepted"], value
                    return value["data"]

                capability = action("capabilities")
                assert capability["protectedDesktop"] and native.observe().unlocked
                print("admitted_and_covered_unlocked", flush=True)
                if args.renew:
                    assert args.ending == "expiry"
                    renewed = send("control.renew", durationSeconds=15, **fence)
                    assert renewed["activeRemainingSeconds"] > 8 and renewed["sessionId"] == fence["sessionId"], renewed
                    print("same_prepared_owner_renewed", flush=True)
                if args.ending != "expiry":
                    capture = action("capture")["artifact"]
                    artifact = Path(capture["guestPath"])
                    try:
                        point = json.loads(subprocess.check_output(
                            ["/usr/bin/python3", str(args.fixture), "--locate-canvas", str(artifact)], text=True))
                    finally:
                        artifact.unlink(missing_ok=True)
                    snapshot = action("snapshot", target="machine-control-fixture", query="Semantic Increment")
                    button, = (node for node in snapshot["elements"] if node["label"] == "Semantic Increment")
                    action("action", reference=button["reference"], action="press")
                    poll(lambda: json.loads(state.read_text())["semanticPresses"] == 1,
                         "Independent fixture did not observe covered semantic action")
                    print("offscreen_capture_and_semantic_effect_confirmed", flush=True)
                    if not args.skip_pointer:
                        try:
                            action("input.click", x=point["x"], y=point["y"])
                        except AssertionError:
                            result = json.loads(state.read_text())
                            print("pointer_events_observed", result["visualClicks"], result["dragReleases"], flush=True)
                            raise
                        poll(lambda: (result := json.loads(state.read_text()))["visualClicks"] == 1
                             and result["dragReleases"] == 1,
                             "Independent fixture did not observe covered pointer action")
                        print("covered_pointer_effect_confirmed", flush=True)
                    if args.extended_input:
                        send("control.heartbeat")
                        action("input.key", key="tab")
                        poll(lambda: json.loads(state.read_text())["lastKey"] == "Tab",
                             "Independent fixture did not observe covered keyboard input")
                        snapshot = action("snapshot", target="machine-control-fixture", query="Fixture Text")
                        entry, = (node for node in snapshot["elements"] if node["label"] == "Fixture Text")
                        action("focus", reference=entry["reference"])
                        action("input.text", text="covered ✓ text")
                        poll(lambda: json.loads(state.read_text())["text"] == "covered ✓ text",
                             "Independent fixture did not observe covered text")
                        send("control.heartbeat")
                        action("input.drag", x=point["x"], y=point["y"], x2=point["x"] + 70, y2=point["y"])
                        poll(lambda: json.loads(state.read_text())["dragReleases"] == 2,
                             "Independent fixture did not observe covered drag release")
                        action("input.scroll", x=point["x"], y=point["y"], dy=3)
                        poll(lambda: json.loads(state.read_text())["scrollY"] > 0,
                             "Independent fixture did not observe covered scrolling")
                        print("covered_key_text_drag_scroll_effects_confirmed", flush=True)
                if args.ending == "takeover":
                    with connect("/run/linuxvm-testbed/input.sock") as device:
                        reply = message(device, "move_relative", dx=32, dy=-12)
                        assert reply["accepted"], reply
                    def interrupted():
                        view = send("control.heartbeat")
                        return view["state"] == "ended" and native.observe().locked
                    poll(interrupted, "Input takeover did not relock the live owner", 4)
                elif args.ending == "stop":
                    with connect(root / "operator.sock") as operator:
                        operator.sendall(b'{"method":"stop"}\n')
                        assert json.loads(operator.makefile("rb").readline())["ok"]
                elif args.ending == "resident":
                    import signal
                    import struct
                    resident, uid, _ = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    assert uid == os.getuid()
                    assert str(args.runtime / "desktop.py").encode() in Path(f"/proc/{resident}/cmdline").read_bytes().split(b"\0")
                    os.kill(resident, signal.SIGKILL)
                if args.ending == "expiry":
                    ended = poll(lambda: view if (view := send("control.heartbeat"))["state"] == "ended" else None,
                                 "Task did not expire")
                    assert ended["terminalReason"] == "duration_expired", ended
                if args.ending != "disconnect":
                    poll(lambda: native.observe().locked, "Console did not relock with owner connected")
            poll(lambda: (result := native.observe()).console == console and result.locked, "Original console did not relock")
            if args.ending == "takeover":
                poll(lambda: status()["lockedUse"]["pausedUntilManualUnlock"], "Takeover did not pause covered access")
            print("original_console_relocked_after_" + args.ending, flush=True)
        finally:
            fixture.terminate()
            fixture.wait(timeout=5)
            native.lock(console)


if __name__ == "__main__":
    main()
