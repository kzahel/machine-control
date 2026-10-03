#!/usr/bin/env python3
"""Claimed, opt-in acceptance for a configured Mac locked-use resident.

Caller owns installation, native consent, ordinary approval, and subsequent
manual unlock. This runner never reads credentials or installs on the host.
Normal cells start unlocked; repeated-task cells explicitly start locked with
retained approval. Captures remain in a private directory.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="macos")
    parser.add_argument("--registry", help="Private common-CLI target registry")
    parser.add_argument("--local", action="store_true", help="Explicit physical-host acceptance; use --target host")
    parser.add_argument("--session-probe", help="Local native read-only probe for independent OS lock verification")
    parser.add_argument("--manual-lock", action="store_true", help="Wait for the person to lock normally instead of sending a synthetic shortcut")
    parser.add_argument("--session-lock", help="Explicit local native session-lock runner; avoids a synthetic lock shortcut")
    parser.add_argument("--start-locked", action="store_true", help="Start an unattended task on an already locked console")
    parser.add_argument("--expect-retained-access", action="store_true", help="Require unchanged ordinary approval after clean completion or lease expiry")
    parser.add_argument("--claim", required=True)
    parser.add_argument("--executable", help="Guest candidate executable; also supply --socket")
    parser.add_argument("--socket", help="Guest candidate socket")
    parser.add_argument("--case", choices=["completed", "duration_expired", "owner_disconnected",
                        "resident_stall", "resident_crash", "guardian_crash", "physical_presence"], default="completed")
    args = parser.parse_args()
    if bool(args.executable) != bool(args.socket):
        parser.error("--executable and --socket must be supplied together")
    if args.local and (args.target != "host" or args.executable or args.case in {"resident_stall", "resident_crash", "guardian_crash"}):
        parser.error("Local acceptance requires the host adapter; process-failure cells remain dedicated-testbed only")
    if args.local and not args.session_probe:
        parser.error("Local acceptance requires --session-probe for independent OS lock verification")
    if args.session_lock and (not args.local or args.manual_lock):
        parser.error("--session-lock requires --local and cannot be combined with --manual-lock")
    if args.start_locked and (args.manual_lock or args.session_lock):
        parser.error("--start-locked cannot be combined with a starting lock action")
    if args.expect_retained_access and args.case not in {"completed", "duration_expired"}:
        parser.error("Retained access is only expected after clean completion or lease expiry")
    mc = [str(ROOT / "bin/machine-control")]
    if args.registry:
        mc += ["--registry", args.registry]
    mc += ["--target", args.target, "--claim", args.claim]

    def execute(*command):
        return subprocess.run([*mc, *command], capture_output=True, check=True, timeout=60).stdout

    def command(request):
        encoded = json.dumps(request, separators=(",", ":"))
        return [*mc, "os", "--", args.executable, "request", args.socket, encoded] if args.executable else [*mc, "desktop", "raw", encoded]

    def request(value):
        response = json.loads(subprocess.run(command(value), capture_output=True, timeout=60).stdout)
        assert response.get("accepted"), (response.get("errorCode", "request refused"), response.get("message"))
        return response.get("data", {})

    def state():
        return request({"operation":"status"})

    fixture_pid = None
    def fixture_state():
        if args.local:
            value = json.loads((Path.home() / "Library/Caches/machine-control-fixture/state.json").read_text())
        else:
            value = json.loads(execute("testbed", "--", "fixture-state"))
        if fixture_pid is not None:
            assert value["pid"] == fixture_pid, "Fixture oracle changed process"
        return value

    def wait(predicate, timeout=45):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.2)
        raise AssertionError("Expected state not observed")

    initial = state()
    assert initial["desktopState"] == ("locked" if args.start_locked else "unlocked"), "Unexpected starting console state"
    assert initial["lockedUse"]["enabled"] and initial["lockedUse"]["helperHealthy"]
    assert not initial["lockedUse"]["pausedUntilManualUnlock"]
    grant = request({"operation":"grant.status"})["grant"]
    assert grant, "Approve ordinary access first"
    applications = request({"operation":"applications", "provider":"macos-native"})["applications"]
    fixtures = [app for app in applications if app.get("bundleId") == "org.machine-control.fixture"]
    assert len(fixtures) == 1, "Launch exactly one native fixture before acceptance"
    fixture_pid = fixtures[0]["processId"]
    fixture_state()  # Bind the independent oracle before control begins.
    fixture = str(fixture_pid)
    owner = subprocess.Popen(command({"operation":"session.control", "durationSeconds":90 if args.case == "duration_expired" else 300}),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    suspended = None
    session_id = None
    try:
        def started():
            current = state()["lockedUse"]
            ready = current["controlSessionId"] is not None if args.start_locked else current["phase"] == "waiting_for_lock"
            if not ready and owner.poll() is not None:
                output, error = owner.communicate()
                raise AssertionError("Control session ended before startup", current["lastEndedReason"],
                                     output.decode(), error.decode())
            return ready
        wait(started)
        session_id = state()["lockedUse"]["controlSessionId"]
        if args.start_locked:
            pass
        elif args.manual_lock:
            print("Ready for manual lock: lock the Mac normally, then leave hardware untouched", flush=True)
        elif args.session_lock:
            observed = json.loads(subprocess.run([args.session_lock, "--lock"], capture_output=True, check=True, timeout=10).stdout)
            assert observed["lockedObserved"], "Native lock runner did not observe OS lock"
        else:
            request({"operation":"input.key", "key":"ctrl-cmd-q", "target":fixture, "provider":"macos-native"})
        def active():
            current = state()["lockedUse"]
            assert current["controlSessionId"] == session_id, (
                "Control session ended before covered activation", current["lastEndedReason"])
            return current["phase"] == "active"
        wait(active, timeout=180 if args.manual_lock else 45)
        current = state()
        assert current["desktopState"] == "unlocked" and current["lockedUse"]["coveredDisplays"] > 0
        print("Covered session active; keep hardware still until the requested takeover", flush=True)
        before = fixture_state()
        tree = request({"operation":"snapshot", "target":fixture, "provider":"macos-native"})
        assert tree["application"]["processId"] == fixture_pid
        buttons = [e for e in tree["elements"] if e.get("role") == "AXButton" and e.get("label") == "Increment"]
        assert len(buttons) == 1
        request({"operation":"action", "reference":buttons[0]["reference"], "action":"press", "provider":"macos-native"})
        after = fixture_state()
        assert after["count"] == before["count"] + 1, "No independently observed fixture effect"
        bounds = buttons[0]["bounds"]
        request({"operation":"input.click", "target":fixture, "provider":"macos-native",
                 "coordinateSpace":"global_display_points",
                 "x":int(bounds["x"] + bounds["width"] / 2),
                 "y":int(bounds["y"] + bounds["height"] / 2)})
        pointer = fixture_state()
        assert pointer["count"] == after["count"] + 1, "No independent pointer effect beneath covers"
        request({"operation":"input.key", "target":fixture, "provider":"macos-native", "key":"a"})
        keyboard = fixture_state()
        assert keyboard["keyEventCount"] > pointer["keyEventCount"] and keyboard["lastKey"] == "a", "No independent keyboard effect beneath covers"
        capture = request({"operation":"capture", "scope":"display", "provider":"macos-native"})
        assert capture["coversExcluded"]
        with tempfile.TemporaryDirectory(prefix="mc-locked-use-evidence-") as directory:
            image = Path(directory) / "agent.png"
            if args.local:
                execute("desktop", "artifact", capture["artifactPath"], str(image))
            else:
                image.write_bytes(execute("os", "--", "/bin/cat", capture["artifactPath"]))
            assert image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        print("Covered native capture and independent AX/pointer/keyboard effects: PASS", flush=True)
        if args.case == "completed":
            request({"operation":"session.control.end", "controlSessionId":session_id})
        elif args.case == "owner_disconnected":
            # Terminate the exact guest connection owner, not merely its outer
            # CLI wrapper (a remote transport can survive that wrapper).
            if args.local:
                owner.terminate()  # The local adapter observes its parent loss and closes the socket.
            else:
                processes = execute("os", "--", "/bin/ps", "-axo", "pid=,command=").decode().splitlines()
                peers = [line.split(None, 1)[0] for line in processes if " request " in line and '"operation":"session.control"' in line and (not args.executable or args.executable in line)]
                assert len(peers) == 1, "Connection owner is ambiguous"
                execute("os", "--", "/bin/kill", "-TERM", peers[0])
        elif args.case in {"resident_stall", "resident_crash"}:
            suspended = str(current["processId"]) if args.case == "resident_stall" else None
            execute("os", "--", "/bin/kill", "-STOP" if suspended else "-KILL", str(current["processId"]))
        elif args.case == "guardian_crash":
            processes = execute("os", "--", "/bin/ps", "-axo", "pid=,command=").decode().splitlines()
            peers = [line.split(None, 1)[0] for line in processes if " locked-use-guardian" in line]
            assert len(peers) == 1, "Guardian is ambiguous"
            execute("os", "--", "/bin/kill", "-KILL", peers[0])
        if args.case in {"resident_crash", "resident_stall"}:
            # Doctor observes OS lock independently even if the candidate
            # cannot answer. It is a read-only, claim-free path.
            def locked():
                result = subprocess.run([str(ROOT / "bin/machine-control"), "--target", args.target, "target", "doctor"], capture_output=True, timeout=60)
                return json.loads(result.stdout)["states"]["desktop"] == "locked"
            wait(locked)
        else:
            if args.case == "physical_presence":
                print("Ready for takeover: press a hardware key or move the physical pointer", flush=True)
            wait(lambda: state()["desktopState"] == "locked", timeout=240 if args.case == "physical_presence" else 120)
            wait(lambda: state()["lockedUse"]["controlSessionId"] is None)
            final = state()
            assert final["lockedUse"]["coveredDisplays"] == 0
            if args.case in {"completed", "duration_expired"}:
                assert not final["lockedUse"]["pausedUntilManualUnlock"]
                assert final["lockedUse"]["lastEndedReason"] == args.case, "Unexpected clean termination reason"
            else:
                assert final["lockedUse"]["pausedUntilManualUnlock"]
            if args.case == "physical_presence":
                assert final["lockedUse"]["lastEndedReason"] == "physical_presence"
            if args.local:
                observed = json.loads(subprocess.run([args.session_probe], capture_output=True, check=True, timeout=5).stdout)
                assert observed["desktopState"] == "locked", "Independent native OS probe did not observe relock"
            if args.expect_retained_access:
                retained = request({"operation":"grant.status"})["grant"]
                assert retained and retained["grantId"] == grant["grantId"], "Clean relock ended or replaced ordinary approval"
        print(f"{args.case}: independent OS relock PASS", flush=True)
    finally:
        if suspended:
            execute("os", "--", "/bin/kill", "-CONT", suspended)
        if args.case != "resident_crash":
            current = state()["lockedUse"]
            if current["controlSessionId"] == session_id and session_id:
                request({"operation":"session.control.end", "controlSessionId":session_id})
        try:
            owner.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            owner.terminate()
            owner.communicate(timeout=15)


if __name__ == "__main__":
    main()
