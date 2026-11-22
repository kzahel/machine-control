#!/usr/bin/env python3
"""Exercise native GDM reauthentication and relock on a claimed Linux appliance."""

import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
import machine_control as mc


# The systemd user service is outside the SSH login session. GDM therefore
# selects the current graphical session of the worker's UID.
GUEST_WORKER = r"""
import ctypes
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid

if ctypes.CDLL(None).prctl(4, 0, 0, 0, 0):  # PR_SET_DUMPABLE
    sys.exit("guest_process_protection_unavailable")
signal.signal(signal.SIGALRM, lambda *_: sys.exit("guest_probe_timeout"))
signal.alarm(45)

provider = GnomeUnlock()
initial = provider.observe()
console = initial.console

def read_secret():
    print("password_prompt_ready", flush=True)
    return sys.stdin.buffer.read(MAX_PASSWORD_BYTES + 2).removesuffix(b"\n").decode("utf-8")

def call_resident(operation, **fields):
    return json.loads(subprocess.check_output(
        ["/usr/local/bin/machine-control", json.dumps(dict(operation=operation, **fields))],
        timeout=9,
    ))

def move_local_device():
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(3)
        connection.connect("/run/linuxvm-testbed/input.sock")
        connection.sendall(b'{"operation":"move_relative","dx":32,"dy":-12}\n')
        with connection.makefile("rb") as reply:
            if not json.loads(reply.readline(2049)).get("accepted"):
                sys.exit("fixture_input_refused")

def wait_for_count(file, field, expected):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            if json.loads(file.read_text())[field] == expected:
                return
        except FileNotFoundError:
            pass
        time.sleep(0.1)
    sys.exit("fixture_effect_unverified")

def press_fixture():
    snapshot = call_resident("snapshot", target="machine-control-fixture",
                             query="Semantic Increment")
    elements = [element for element in snapshot["data"]["elements"]
                if element["label"] == "Semantic Increment"]
    if len(elements) != 1:
        sys.exit("fixture_button_unavailable")
    if not call_resident("action", reference=elements[0]["reference"], action="press")["accepted"]:
        sys.exit("fixture_action_refused")

def exercise(fixture_state=None):
    provider.lock(console)
    print("native_lock_observed", flush=True)
    cover = GnomeCover(provider, console, Takeover(console, "/run/machine-control-cover-test/activity.sock")) if covered_end else None
    try:
        if cover:
            cover.open()
            print("compositor_cover_painted", flush=True)
            if not cover.opaque_frame():
                sys.exit("locked_cover_pixels_unverified")
            print("locked_cover_pixels_observed", flush=True)
        allowed = cover.covered if cover else lambda: True
        provider.authenticate(console, read_secret, allowed)
        print("gdm_authenticated_and_original_console_unlocked", flush=True)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            state = provider.observe()
            if state.console != console or not state.unlocked or not allowed():
                sys.exit("original_console_did_not_stay_unlocked")
            time.sleep(0.15)
        print("original_console_stayed_unlocked", flush=True)
        if fixture_state is not None:
            press_fixture()
            wait_for_count(fixture_state, "semanticPresses", 1)
            print("native_application_effect_observed_after_unlock", flush=True)
        if cover:
            if not cover.opaque_frame():
                sys.exit("unlocked_cover_pixels_unverified")
            print("unlocked_cover_pixels_observed", flush=True)
            with tempfile.TemporaryDirectory(prefix="mc-covered-frame-") as directory:
                frame = Path(directory) / "fixture.png"
                frame.write_bytes(cover.capture())
                point = json.loads(subprocess.check_output(
                    ["/usr/bin/python3", "/usr/local/libexec/linuxvm-testbed/control_fixture.py",
                     "--locate-canvas", str(frame)], timeout=5,
                ))
            if not cover.opaque_frame():
                sys.exit("cover_changed_during_capture")
            print("covered_capture_observed_fixture", flush=True)
            cover.click(point["x"], point["y"])
            wait_for_count(fixture_state, "visualClicks", 1)
            if not cover.opaque_frame():
                sys.exit("cover_changed_during_pointer_input")
            print("covered_pointer_effect_observed", flush=True)
            if covered_end == "owner_crashed":
                print("covered_owner_crash_armed", flush=True)
                os.kill(os.getpid(), signal.SIGKILL)
            elif covered_end == "local_input":
                move_local_device()
            elif covered_end == "lease_expired":
                cover.stop_renewing.set()
            else:
                cover.close(end=covered_end == "owner_ended")
            provider.wait_for(console, "locked", lambda: True)
            if cover.status()[1] != covered_end:
                sys.exit("compositor_relock_reason_unverified")
            print("compositor_relocked_after_" + covered_end, flush=True)
    finally:
        if cover:
            cover.close()
            provider.wait_for(console, "locked", lambda: True)
        else:
            provider.lock(console)
        print("original_console_relocked", flush=True)

if desktop_effect:
    if not initial.unlocked:
        sys.exit("start_with_the_appliance_unlocked")
    with tempfile.TemporaryDirectory(prefix="mc-unlock-fixture-") as home:
        state_file = Path(home) / ".cache/linuxvm-testbed/fixture/state.json"
        fixture = subprocess.Popen(
            ["/usr/bin/python3", "/usr/local/libexec/linuxvm-testbed/control_fixture.py"],
            env={**os.environ, "HOME": home}, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        )
        try:
            wait_for_count(state_file, "semanticPresses", 0)
            exercise(state_file)
        finally:
            if fixture.poll() is None:
                fixture.terminate()
                fixture.wait(timeout=5)
else:
    exercise()

try:
    provider.authenticate(console, lambda: uuid.uuid4().hex, lambda: True)
except UnlockRefused as error:
    if str(error) != "gnome_authentication_failed":
        raise
    provider.require_locked(console)
    print("incorrect_password_refused_and_console_still_locked", flush=True)
else:
    provider.lock(console)
    sys.exit("incorrect_password_unexpectedly_accepted")
"""


def checked_target():
    scope = json.loads(Path(os.environ["MACHINE_CONTROL_SCOPE_FILE"]).read_text())
    target = mc.load_registry(scope["registry"])[0][scope["target"]]
    if (target.get("platform") != "linux" or target.get("claimPolicy") != "required"
            or mc.resolved_adapter_command(target) == mc.resolved_adapter_command(mc.DEFAULT_TARGETS["host"])
            or scope.get("workspace") is not None):
        raise SystemExit("Use a scoped, privately configured Linux appliance")
    target["_claimId"] = scope["claim"]
    target["environment"] = {**target["environment"], "MACHINE_CONTROL_CLAIM_ID": scope["claim"]}
    mc.require_selected_claim(target)
    return target


def guest_program(desktop_effect, covered_end):
    provider = (ROOT / "platforms/linux/guests/ubuntu/ui/gnome_unlock.py").read_text()
    worker = f"""
import sys, types
provider = sys.modules['gnome_unlock'] = types.ModuleType('gnome_unlock')
exec(compile({provider!r}, 'gnome_unlock.py', 'exec'), provider.__dict__)
from gnome_unlock import GnomeUnlock, MAX_PASSWORD_BYTES, UnlockRefused
desktop_effect = {desktop_effect!r}
covered_end = {covered_end!r}
"""
    if covered_end:
        activity = (ROOT / "desktop/native/linux/activity.py").read_text()
        cover = (ROOT / "platforms/linux/guests/ubuntu/ui/gnome_cover.py").read_text()
        worker += "activity = sys.modules['activity'] = types.ModuleType('activity')\n"
        worker += f"exec(compile({activity!r}, 'activity.py', 'exec'), activity.__dict__)\n"
        worker += f"exec(compile({cover!r}, 'gnome_cover.py', 'exec'))\n"
    worker += GUEST_WORKER
    return f"""
import os, pwd, sys
entry = pwd.getpwnam(sys.argv[1])
os.initgroups(entry.pw_name, entry.pw_gid)
os.setgid(entry.pw_gid)
os.setuid(entry.pw_uid)
runtime = f"/run/user/{{entry.pw_uid}}"
os.execve("/usr/bin/systemd-run", ["/usr/bin/systemd-run", "--user",
    "--wait", "--pipe", "--quiet", "--collect", "--", "/usr/bin/python3",
    "-I", "-c", {worker!r}], {{"XDG_RUNTIME_DIR": runtime,
    "DBUS_SESSION_BUS_ADDRESS": f"unix:path={{runtime}}/bus"}})
"""


def exchange(remote, fd, target, desktop_effect, covered_end, original_session):
    observed = []
    before_password = ["native_lock_observed"]
    if covered_end:
        before_password.extend(["compositor_cover_painted", "locked_cover_pixels_observed"])
    before_password.append("password_prompt_ready")
    with selectors.DefaultSelector() as selector:
        selector.register(remote.stdout, selectors.EVENT_READ)
        while selector.select(timeout=40):
            line = remote.stdout.readline()
            if not line:
                failed = remote.wait(timeout=5) != 0
                if failed != (covered_end == "owner_crashed"):
                    raise SystemExit("The guest probe failed")
                break
            line = line.strip().decode("utf-8")
            observed.append(line)
            if observed == before_password:
                mc.require_selected_claim(target)
                remote.stdin.write(os.read(fd, 4098))
                remote.stdin.close()
            print(line, flush=True)
        else:
            raise SystemExit("The guest probe timed out")
    expected = before_password + ["gdm_authenticated_and_original_console_unlocked",
                                  "original_console_stayed_unlocked"]
    if desktop_effect:
        expected.append("native_application_effect_observed_after_unlock")
    if covered_end:
        expected.extend(["unlocked_cover_pixels_observed", "covered_capture_observed_fixture",
                         "covered_pointer_effect_observed"])
    if covered_end == "owner_crashed":
        if observed != expected + ["covered_owner_crash_armed"]:
            raise SystemExit("The covered owner did not reach the crash point")
        verify_crash_relock(original_session)
        return
    if covered_end:
        expected.append("compositor_relocked_after_" + covered_end)
    expected += ["original_console_relocked", "incorrect_password_refused_and_console_still_locked"]
    if observed != expected:
        raise SystemExit("The complete native lock, authentication and relock were not observed")


def active_seat_session():
    return subprocess.check_output([str(ROOT / "bin/machine-control"), "testbed", "--", "exec", "--",
        "/usr/bin/loginctl", "show-seat", "seat0", "--property=ActiveSession", "--value"],
        text=True, timeout=8).strip()


def verify_crash_relock(original_session):
    command = [str(ROOT / "bin/machine-control"), "testbed", "--"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not original_session or active_seat_session() != original_session:
            raise SystemExit("The active console changed after the covered owner crashed")
        status = json.loads(subprocess.check_output(
            command + ["control", '{"operation":"status"}'], timeout=8,
        ))
        locked = subprocess.check_output(command + ["exec", "--", "/usr/bin/loginctl",
            "show-session", original_session, "--property=LockedHint", "--value"], text=True, timeout=8).strip()
        if status.get("data", {}).get("desktopState") == "locked" and locked == "yes":
            print("crashed_owner_native_relock_observed", flush=True)
            return
        time.sleep(0.1)
    raise SystemExit("The console did not relock after the covered owner crashed")


def run():
    target = checked_target()
    arguments = sys.argv[1:]
    endings = {
        "--covered-effect": "local_input",
        "--covered-stop": "owner_ended",
        "--covered-expiry": "lease_expired",
        "--covered-owner-loss": "owner_disconnected",
        "--covered-crash": "owner_crashed",
    }
    variants = ([], ["--desktop-effect"], *([flag] for flag in endings))
    if arguments in variants:
        result = subprocess.call(
            ["bash", "-ec", 'source "$1"; interpreter="$2"; probe="$3"; shift 3; '
             'exec "$interpreter" "$probe" --configured "$@"', "probe",
             str(ROOT / "platforms/linux/scripts/common.sh"), sys.executable, __file__, *arguments],
            env={**os.environ, **target["environment"]},
        )
        return result
    if arguments[:1] != ["--configured"] or arguments[1:] not in variants:
        raise SystemExit("Run this probe with machine-control run")
    covered_end = endings.get(arguments[-1])
    desktop_effect = bool(covered_end) or "--desktop-effect" in arguments
    original_session = active_seat_session() if covered_end == "owner_crashed" else None

    sys.path.insert(0, str(ROOT / "platforms/linux/scripts"))
    import credential

    config = credential.configuration()
    if config["profile"] != "password":
        raise SystemExit("This appliance has no password credential profile")
    fd, _ = credential.open_secret(config["secretFile"])
    try:
        command = credential.verification_route(config, guest_program(desktop_effect, covered_end))
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0) as remote:
            try:
                exchange(remote, fd, target, desktop_effect, covered_end, original_session)
            finally:
                if remote.poll() is None:
                    remote.terminate()
                    try:
                        remote.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        remote.kill()
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
