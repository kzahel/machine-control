#!/usr/bin/env python3
"""Exercise native GDM reauthentication and relock on a claimed Linux appliance."""

import json
import os
from pathlib import Path
import selectors
import subprocess
import sys


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
import subprocess
import sys
import tempfile
import uuid

if ctypes.CDLL(None).prctl(4, 0, 0, 0, 0):  # PR_SET_DUMPABLE
    sys.exit("guest_process_protection_unavailable")
signal.signal(signal.SIGALRM, lambda *_: sys.exit("guest_probe_timeout"))
signal.alarm(35)

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

def wait_for_press_count(file, expected):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            if json.loads(file.read_text())["semanticPresses"] == expected:
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
    try:
        provider.authenticate(console, read_secret, lambda: True)
        print("gdm_authenticated_and_original_console_unlocked", flush=True)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            state = provider.observe()
            if state.console != console or not state.unlocked:
                sys.exit("original_console_did_not_stay_unlocked")
            time.sleep(0.15)
        print("original_console_stayed_unlocked", flush=True)
        if fixture_state is not None:
            press_fixture()
            wait_for_press_count(fixture_state, 1)
            print("native_application_effect_observed_after_unlock", flush=True)
    finally:
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
            wait_for_press_count(state_file, 0)
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


def guest_program(desktop_effect):
    provider = (ROOT / "platforms/linux/guests/ubuntu/ui/gnome_unlock.py").read_text()
    worker = provider + f"\ndesktop_effect = {desktop_effect!r}\n" + GUEST_WORKER
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


def exchange(remote, fd, target, desktop_effect):
    observed = []
    with selectors.DefaultSelector() as selector:
        selector.register(remote.stdout, selectors.EVENT_READ)
        while selector.select(timeout=40):
            line = remote.stdout.readline()
            if not line:
                if remote.wait(timeout=5):
                    raise SystemExit("The guest probe failed")
                break
            line = line.strip().decode("utf-8")
            observed.append(line)
            if observed == ["native_lock_observed", "password_prompt_ready"]:
                mc.require_selected_claim(target)
                remote.stdin.write(os.read(fd, 4098))
                remote.stdin.close()
            print(line, flush=True)
        else:
            raise SystemExit("The guest probe timed out")
    expected = ["native_lock_observed", "password_prompt_ready",
                "gdm_authenticated_and_original_console_unlocked", "original_console_stayed_unlocked"]
    if desktop_effect:
        expected.append("native_application_effect_observed_after_unlock")
    expected += ["original_console_relocked", "incorrect_password_refused_and_console_still_locked"]
    if observed != expected:
        raise SystemExit("The complete native lock, authentication and relock were not observed")


def run():
    target = checked_target()
    arguments = sys.argv[1:]
    if arguments in ([], ["--desktop-effect"]):
        result = subprocess.call(
            ["bash", "-ec", 'source "$1"; interpreter="$2"; probe="$3"; shift 3; '
             'exec "$interpreter" "$probe" --configured "$@"', "probe",
             str(ROOT / "platforms/linux/scripts/common.sh"), sys.executable, __file__, *arguments],
            env={**os.environ, **target["environment"]},
        )
        return result
    if arguments not in (["--configured"], ["--configured", "--desktop-effect"]):
        raise SystemExit("Run this probe with machine-control run")
    desktop_effect = "--desktop-effect" in arguments

    sys.path.insert(0, str(ROOT / "platforms/linux/scripts"))
    import credential

    config = credential.configuration()
    if config["profile"] != "password":
        raise SystemExit("This appliance has no password credential profile")
    fd, _ = credential.open_secret(config["secretFile"])
    try:
        command = credential.verification_route(config, guest_program(desktop_effect))
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0) as remote:
            try:
                exchange(remote, fd, target, desktop_effect)
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
