#!/usr/bin/env python3
"""Installed Tauri acceptance through native accessibility, menu and socket APIs."""

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--app", type=Path, required=True)
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--consent-actor", type=Path, required=True)
parser.add_argument("--revision")
args = parser.parse_args()
sys.path.insert(0, str(args.runtime))
import linuxui
from gi.repository import Gio, GLib

checks = []
process = None
log = args.output.with_suffix(".log").open("w")
endpoint = Path(os.environ["XDG_RUNTIME_DIR"]) / "machine-control-desktop/desktop.sock"
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
startup = shortcut = False


def report(complete=False, failure=None):
    args.output.write_text(json.dumps({"complete": complete, "passed": complete and not failure,
                                      "failure": failure, "checks": checks}, indent=2))


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})
    report()
    if not value:
        raise AssertionError(name)


def poll(fn, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            value = fn()
            if value:
                return value
        except (OSError, linuxui.UIError):
            pass
        time.sleep(.15)
    raise AssertionError("Timed out waiting for native product effect")


def call(operation, **params):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(35)
        client.connect(str(endpoint))
        client.sendall(json.dumps({"operation": operation, **params}).encode() + b"\n")
        return json.loads(client.makefile("rb").readline(24 * 1024 * 1024))


def nodes(name="machine-control"):
    return list(linuxui.walk(linuxui.choose_application(linuxui.desktop(), name), 25, 2000))


def widget(label, role="push button", app="machine-control"):
    found = [(node, info) for node, info in nodes(app) if info["name"] == label and info["role"] == role]
    if len(found) != 1:
        return None
    return found[0][0]


def press(label, role="push button", app="machine-control"):
    node = poll(lambda: widget(label, role, app))
    check("native UI " + label, node.do_action(0))
    time.sleep(.2)


def dbus(destination, path, interface, method, params=None):
    return bus.call_sync(destination, path, interface, method, params, None,
                         Gio.DBusCallFlags.NONE, 3000, None).unpack()


def tray():
    items = dbus("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.freedesktop.DBus.Properties",
                 "Get", GLib.Variant("(ss)", ("org.kde.StatusNotifierWatcher", "RegisteredStatusNotifierItems")))[0]
    for item in items:
        if "@" not in item:
            continue
        destination, path = item.split("@", 1)
        properties = dbus(destination, path, "org.freedesktop.DBus.Properties", "GetAll",
                          GLib.Variant("(s)", ("org.kde.StatusNotifierItem",)))[0]
        if properties.get("Id") == "tray-icon tray app control":
            return destination, properties["Menu"]
    return None


def menu_entries():
    destination, path = poll(tray)
    layout = dbus(destination, path, "com.canonical.dbusmenu", "GetLayout",
                  GLib.Variant("(iias)", (0, -1, [])))[1]
    entries = {}
    def walk(node):
        identifier, props, children = node
        if "label" in props:
            label = props["label"].replace("_", "").replace(" Machine Control", "").rstrip("…")
            entries[label] = identifier
        for child in children:
            walk(child)
    walk(layout)
    return destination, path, entries


def menu(label):
    destination, path, entries = menu_entries()
    if label not in entries:
        raise AssertionError("Missing native tray item " + label)
    dbus(destination, path, "com.canonical.dbusmenu", "Event",
         GLib.Variant("(isvu)", (entries[label], "clicked", GLib.Variant("i", 0), 0)))
    time.sleep(.3)


try:
    check("no predecessor resident", not endpoint.exists())
    if args.app.suffix == ".AppImage":
        args.app.chmod(args.app.stat().st_mode | 0o100)
    process = subprocess.Popen([str(args.app)], stdout=log, stderr=log, start_new_session=True)
    poll(lambda: endpoint.exists())
    state = call("status")
    check("installed resident ready", state["accepted"] and state["data"]["ready"])
    if args.revision:
        check("exact source revision", state["data"]["sourceRevision"] == args.revision)
    check("starts Off", state["data"]["grant"] is None)
    check("Off refuses", call("snapshot", target="machine-control")["errorCode"] == "approval_required")
    poll(lambda: widget("Enable access"))
    check("compact settings presented", widget("Settings") is not None)
    second = subprocess.Popen([str(args.app)], stdout=log, stderr=log)
    second.wait(15)
    check("single instance", second.returncode == 0 and call("status")["generation"] == state["generation"])
    labels = menu_entries()[2]
    check("all tray controls", {"Open", "Settings", "Check for Updates", "Stop access", "Quit"} <= set(labels))
    press("Enable access")
    poll(lambda: call("status")["data"]["grant"])
    check("native UI arms access", True)
    check("operator protects itself", call("snapshot", target="machine-control")["errorCode"] == "operator_protected")
    generation = call("status")["generation"]
    menu("Stop access")
    check("tray Stop", call("status")["data"]["grant"] is None)
    check("tray Stop rotates authority", call("status")["generation"] != generation)
    menu("Settings")
    poll(lambda: widget("Start at login", "check box"))
    check("startup initially off", "checked" not in linuxui.state_names(widget("Start at login", "check box")))
    press("Start at login", "check box")
    startup = True
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    registrations = poll(lambda: [p for p in (config / "autostart").glob("*.desktop")
                                if str(args.app) in p.read_text() and "--background" in p.read_text()])
    check("login registration owns stable app path", any(str(args.app) in p.read_text() for p in registrations))
    press("Start at login", "check box")
    startup = False
    check("login registration removed", all(not p.exists() for p in registrations))
    press("Stop shortcut", "check box")
    shortcut = True
    poll(lambda: "checked" in linuxui.state_names(widget("Stop shortcut", "check box")))
    menu("Open")
    press("Enable access")
    poll(lambda: call("status")["data"]["grant"])
    independent = subprocess.run(["/usr/local/bin/machine-control",
        json.dumps({"operation": "input.key", "key": "ctrl+alt+shift+dot"})],
        capture_output=True, text=True, check=True)
    check("independent native shortcut delivery", json.loads(independent.stdout)["accepted"])
    poll(lambda: call("status")["data"]["grant"] is None)
    check("real shortcut Stop effect", True)
    menu("Settings")
    press("Stop shortcut", "check box")
    shortcut = False
    menu("Open")
    with concurrent.futures.ThreadPoolExecutor() as pool:
        denial = pool.submit(call, "grant.request", scopes=["observe"], durationSeconds=20,
                             reason="Installed native denial")
        press("Deny", app="machine-control-approval")
        check("installed native denial", denial.result()["errorCode"] == "approval_denied")
        approval = pool.submit(call, "grant.request", scopes=["observe", "control"], durationSeconds=2,
                               reason="Installed native approval")
        poll(lambda: call("status")["data"]["pendingRequest"])
        check("installed prompt pauses control", call("input.key", key="enter")["errorCode"] == "approval_prompt_visible")
        press("Allow", app="machine-control-approval")
        check("installed native approval", approval.result()["accepted"])
    time.sleep(2.2)
    check("installed grant expiry", call("snapshot", target="machine-control")["errorCode"] == "approval_required")
    menu("Open")
    press("Permissions")
    press("Share…")
    consent = subprocess.run(["/usr/bin/python3", str(args.consent_actor), "--runtime", str(args.runtime)],
                             stdout=log, stderr=log, timeout=35)
    check("installed portal consent", consent.returncode == 0)
    poll(lambda: call("status")["data"]["captureState"] == "ready")
    menu("Open")
    press("Enable access")
    poll(lambda: call("status")["data"]["grant"])
    capture = call("capture")
    check("installed portal capture", capture["accepted"])
    import hashlib
    artifact = capture["data"]["artifact"]
    check("installed capture hash", hashlib.sha256(Path(artifact["guestPath"]).read_bytes()).hexdigest() == artifact["sha256"])
    refusal = call("input.key", key="enter")
    print("Own foreground refusal", json.dumps(refusal), file=log, flush=True)
    check("own foreground input protected", not refusal["accepted"] and refusal["errorCode"] in {
        "operator_protected", "foreground_unavailable"})
    old = call("status")["generation"]
    menu("Settings")
    press("Restart")
    poll(lambda: call("status")["generation"] != old, 35)
    check("Restart revokes access", call("status")["data"]["grant"] is None)
    check("Restart closes sharing", call("status")["data"]["captureState"] == "unavailable")
    poll(lambda: widget("Settings"), 35)
    menu("Check for Updates")
    poll(lambda: widget("Check for updates"))
    check("tray opens update settings", True)
    menu("Open")
    poll(lambda: widget("Enable access"))
    window = next(n for n, i in nodes() if i["role"] == "frame")
    check("owned window is foreground before close", "active" in linuxui.state_names(window))
    subprocess.run(["/usr/local/bin/machine-control", json.dumps({"operation":"input.key", "key":"alt+f4"})],
                   capture_output=True, check=True)
    poll(lambda: not any("showing" in i["states"] for _, i in nodes() if i["role"] == "frame"))
    check("close preserves tray and resident", endpoint.exists() and tray() is not None)
    menu("Open")
    poll(lambda: widget("Enable access"))
    check("tray reopens settings", True)
    menu("Quit")
    poll(lambda: not endpoint.exists())
    check("Quit removes owned endpoint", True)
    report(complete=True)
except BaseException as error:
    report(complete=True, failure=str(error))
    raise
finally:
    if endpoint.exists():
        try:
            menu("Stop access")
            menu("Settings")
            if startup:
                press("Start at login", "check box")
            if shortcut:
                press("Stop shortcut", "check box")
            menu("Quit")
        except Exception:
            pass
    if process and process.poll() is None:
        try:
            process.wait(5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(5)
