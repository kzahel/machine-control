#!/usr/bin/env python3
"""Native lock and claimed cold-boot startup acceptance in two phases.

Run lock before a controller-owned reboot and startup after its read-only doctor
reports a ready session. Use persistent staging; the guest may clear /tmp.
"""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--app", type=Path, required=True)
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--consent-actor", type=Path, required=True)
parser.add_argument("--revision", required=True)
parser.add_argument("--phase", choices=["lock", "startup"], required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.runtime))
import linuxui
from gi.repository import Gio, GLib

checks = []
process = None
log = args.output.with_suffix(".log").open("w")
endpoint = Path(os.environ["XDG_RUNTIME_DIR"]) / "machine-control-desktop/desktop.sock"
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


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
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)
    root = linuxui.choose_application(linuxui.desktop(), name)
    root.clear_cache()
    return list(linuxui.walk(root, 25, 2000))


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
    if args.phase == "lock":
        check("session fixture initially Off", not endpoint.exists())
        process = subprocess.Popen([str(args.app)], stdout=log, stderr=log, start_new_session=True)
        poll(lambda: endpoint.exists())
        check("lock exact candidate source", call("status")["data"]["sourceRevision"] == args.revision)
        poll(lambda: widget("Settings"))
        menu("Settings")
        press("Start at login", "check box")
        menu("Open")
        press("Permissions")
        press("Share…")
        subprocess.run(["/usr/bin/python3", str(args.consent_actor), "--runtime", str(args.runtime)], check=True, stdout=log, stderr=log, timeout=35)
        poll(lambda: call("status")["data"]["captureState"]=="ready")
        menu("Open")
        press("Enable access")
        poll(lambda: call("status")["data"]["grant"])
        old=call("status")["generation"]
        dbus("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", "Lock")
        poll(lambda: not call("status")["data"]["ready"] and call("status")["data"]["grant"] is None)
        check("native lock revokes access", True)
        check("lock closes sharing", call("status")["data"]["captureState"]=="unavailable")
        check("lock rotates generation", call("status")["generation"]!=old)
        check("lock refuses operations", call("snapshot", target="machine-control")["errorCode"]=="desktop_unavailable")
        report(complete=True)
        # Keep the owned unit alive until the claimed controller reboot.
        while True:
            time.sleep(1)
    else:
        poll(lambda: endpoint.exists(), 45)
        state=call("status")
        check("login startup is ready and Off", state["data"]["ready"] and state["data"]["grant"] is None)
        check("login startup has no sharing session", state["data"]["captureState"] == "unavailable")
        check("startup exact candidate source", state["data"]["sourceRevision"] == args.revision)
        check("startup hides settings window", not any("showing" in i["states"] for _,i in nodes() if i["role"]=="frame"))
        menu("Settings")
        poll(lambda: widget("Start at login", "check box"))
        check("startup preference retained", "checked" in linuxui.state_names(widget("Start at login", "check box")))
        press("Start at login", "check box")
        check("startup preference removed", "checked" not in linuxui.state_names(widget("Start at login", "check box")))
        menu("Quit")
        poll(lambda: not endpoint.exists())
        check("session fixture Quit cleanup", True)
        report(complete=True)
except BaseException as error:
    report(complete=True, failure=str(error))
    raise
finally:
    log.close()
