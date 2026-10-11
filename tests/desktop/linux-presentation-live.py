#!/usr/bin/env python3
"""Isolated packaged GUI profiles, native safety, recovery and restart."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--app", type=Path, required=True)
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--fixture", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.runtime))
import linuxui
from gi.repository import GLib

instance = "presentation-fixture"
endpoint = Path(os.environ["XDG_RUNTIME_DIR"]) / ("machine-control-" + instance) / "desktop.sock"
checks = []
process = None
owned_pids = set()
log = args.output.with_suffix(".log").open("w")
fixture_state = args.output.with_suffix(".fixture.json")
fixture_source = args.output.with_suffix(".fixture.py")
unit = "mc-presentation-live-fixture.service"


def report(failure=None, complete=False):
    args.output.write_text(json.dumps({"complete": complete, "passed": complete and failure is None,
                                      "failure": failure, "checks": checks}, indent=2))


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})
    report()
    if not value:
        raise AssertionError(name)


def poll(fn, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            value = fn()
            if value:
                return value
        except (OSError, linuxui.UIError):
            pass
        time.sleep(.1)
    raise AssertionError("Timed out waiting for native effect")


def call(operation, **parameters):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(35)
        client.connect(str(endpoint))
        client.sendall(json.dumps({"operation": operation, **parameters}).encode() + b"\n")
        return json.loads(client.makefile("rb").readline(24 * 1024 * 1024))


def cli(action="status", *extra):
    completed = subprocess.run([str(args.app), "presentation", action, *extra, "--instance", instance],
                               capture_output=True, text=True, timeout=6)
    return json.loads(completed.stdout)


def apps(name):
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)
    return [a for a in linuxui.application_roots(linuxui.desktop()) if linuxui.safe(a.get_name, "") == name]


def nodes(name):
    result = []
    for app in apps(name):
        app.clear_cache()
        result.extend(linuxui.walk(app, 30, 3000))
    return result


def widget(label, app="machine-control", role="push button"):
    found = [node for node, info in nodes(app) if info["name"] == label and info["role"] == role]
    return found[0] if len(found) == 1 else None


def press(label, app="machine-control"):
    check("native UI " + label, poll(lambda: widget(label, app)).do_action(0))


def settings_present():
    return any(info["role"] == "frame" and info["name"] == "Machine Control" and
               "showing" in info["states"] for _, info in nodes("machine-control"))


def gui_pids():
    values = []
    for path in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            argv = path.read_bytes().split(b"\0")
            if argv[0] == os.fsencode(args.app) and os.fsencode(instance) in argv:
                values.append(int(path.parent.name))
        except OSError:
            pass
    owned_pids.update(values)
    return values


def open_settings():
    result = subprocess.run([str(args.app), "--instance", instance, "--settings"],
                            stdout=log, stderr=log, timeout=8)
    check("same-runtime Settings launch", result.returncode == 0)
    poll(settings_present)


def close_settings():
    # Native target appliance actor; never host/hypervisor input.
    frames = [n for n, i in nodes("machine-control") if i["role"] == "frame" and i["name"] == "Machine Control"]
    check("unambiguous active Settings before close", len(frames) == 1 and "active" in linuxui.state_names(frames[0]))
    result = subprocess.run(["/usr/local/bin/machine-control", json.dumps({"operation": "input.key", "key": "alt+f4"})],
                            capture_output=True, text=True, check=True)
    check("target-native close delivered", json.loads(result.stdout)["accepted"])
    poll(lambda: not settings_present())
    check("Settings accessible frame destroyed", not any(i["role"] == "frame" and i["name"] == "Machine Control"
                                                          for _, i in nodes("machine-control")))


def cleanup_gui():
    for pid in gui_pids():
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    if process and process.poll() is None:
        try:
            process.wait(8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    poll(lambda: not endpoint.exists())


failure = None
try:
    check("candidate endpoint initially absent", not endpoint.exists())
    fixture_source.write_text(args.fixture.read_text().replace(
        'Path.home() / ".cache/linuxvm-testbed/fixture/state.json"', "Path(" + repr(str(fixture_state)) + ")"))
    subprocess.run(["systemd-run", "--user", "--quiet", "--collect", "--unit", unit,
                    "/usr/bin/python3", str(fixture_source)], check=True)
    poll(lambda: fixture_state.exists())
    check("offline reset", cli("reset")["ok"])
    for profile in ["personal", "minimal", "appliance"]:
        check("offline profile " + profile, cli("set", profile)["ok"])
        process = subprocess.Popen([str(args.app), "--instance", instance], stdout=log, stderr=log)
        poll(lambda: endpoint.exists())
        poll(lambda: call("status")["data"]["ready"])
        gui_pids()
        state = cli()
        runtime = state["runtimeId"]
        check(profile + " effective configuration", state["presentation"]["profile"] == profile)
        check(profile + " starts without authority", call("status")["data"]["grant"] is None)
        if profile == "personal":
            poll(settings_present)
            close_settings()
        else:
            time.sleep(.5)
            check(profile + " no Settings WebView", not settings_present())
        with ThreadPoolExecutor(max_workers=1) as pool:
            approval = pool.submit(call, "grant.request", scopes=["observe", "control"],
                                   reason="Native presentation qualification", durationSeconds=60)
            poll(lambda: widget("Allow", "machine-control-approval"))
            check("pending config refuses mutation", not cli("set", "personal")["ok"])
            press("Allow", "machine-control-approval")
            check(profile + " native approval", approval.result()["accepted"])
        poll(lambda: widget("Stop access", "machine-control-safety"))
        check(profile + " approval keeps Settings absent", not settings_present())
        snap = poll(lambda: (r if r["accepted"] else None)
                    if (r := call("snapshot", target="machine-control-fixture", maxDepth=16)) else None)
        button = next(n for n in snap["data"]["elements"] if n["label"] == "Semantic Increment")
        before = json.loads(fixture_state.read_text())["semanticPresses"]
        effect = call("action", reference=button["reference"])
        check(profile + " native delivery", effect["accepted"] and effect["delivery"] == "confirmed")
        poll(lambda: json.loads(fixture_state.read_text())["semanticPresses"] == before + 1)
        check(profile + " independent native effect", True)
        press("Pause", "machine-control-safety")
        poll(lambda: call("snapshot").get("errorCode") == "access_paused")
        press("Resume", "machine-control-safety")
        poll(lambda: widget("Pause", "machine-control-safety"))
        poll(lambda: call("action", reference=button["reference"]).get("errorCode") == "stale_reference")
        press("Stop access", "machine-control-safety")
        poll(lambda: call("status")["data"]["grant"] is None)
        check(profile + " independent native Stop", True)
        # Saturate public handshake slots without blocking local recovery.
        held = []
        try:
            for _ in range(16):
                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                client.connect(str(endpoint))
                client.sendall(b'{"operation":')
                held.append(client)
            started = time.monotonic()
            check("recovery independent of public saturation", cli("set", "minimal")["ok"])
            open_settings()
            check("bounded saturated recovery", time.monotonic() - started < 4)
            check("recovery keeps resident", cli()["runtimeId"] == runtime)
        finally:
            for client in held:
                client.close()
        close_settings()
        check("persistent profile applied", cli()["presentation"]["savedProfile"] == "minimal")
        cleanup_gui()

    check("saved profile before override", cli("set", "minimal")["ok"])
    process = subprocess.Popen([str(args.app), "--instance", instance, "--presentation", "appliance"],
                               stdout=log, stderr=log)
    poll(lambda: endpoint.exists())
    old = cli()["runtimeId"]
    check("temporary override", cli()["presentation"]["temporaryOverride"])
    check("temporary appliance", cli()["presentation"]["profile"] == "appliance")
    open_settings()
    press("Settings")
    press("Restart")
    poll(lambda: cli().get("runtimeId") not in {None, old}, 25)
    process.wait(5)
    poll(lambda: call("status")["data"]["ready"])
    state = cli()
    gui_pids()
    check("Restart expires override", not state["presentation"]["temporaryOverride"] and state["presentation"]["profile"] == "minimal")
    check("Restart revokes volatile authority", call("status")["data"]["grant"] is None)
    open_settings()
    check("Restart same-runtime recovery", state["runtimeId"] == cli()["runtimeId"])
    cleanup_gui()
    check("offline recovery resets Personal", cli("reset")["presentation"]["profile"] == "personal")
except BaseException as error:
    failure = str(error)
    raise
finally:
    if endpoint.exists() or gui_pids():
        cleanup_gui()
    subprocess.run(["systemctl", "--user", "stop", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fixture_source.unlink(missing_ok=True)
    fixture_state.unlink(missing_ok=True)
    report(failure, True)
