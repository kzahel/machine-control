#!/usr/bin/env python3
"""Independent native safety UI, private inherited pipes, parent-bound lifetime."""
import ctypes
import json
import os
import signal
import sys
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

parent = os.getppid()
if ctypes.CDLL(None).prctl(1, signal.SIGTERM, 0, 0, 0) != 0 or os.getppid() != parent:
    raise SystemExit("Safety owner unavailable")
GLib.set_prgname("machine-control-safety")
Gtk.init([])
window = Gtk.Window(title="Machine Control — Access active")
window.set_default_size(360, 120)
window.set_border_width(12)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
window.add(box)
label = Gtk.Label(label="Access active", xalign=0)
box.pack_start(label, True, True, 0)
buttons = Gtk.Box(spacing=8)
box.pack_start(buttons, False, False, 0)
paused = False


def intent(method):
    print(json.dumps({"method": method}), flush=True)


pause = Gtk.Button(label="Pause")
pause.connect("clicked", lambda *_: intent("resume" if paused else "pause"))
buttons.pack_start(pause, True, True, 0)
stop = Gtk.Button(label="Stop access")
stop.connect("clicked", lambda *_: intent("stop"))
buttons.pack_start(stop, True, True, 0)
settings = Gtk.Button(label="Settings…")
settings.connect("clicked", lambda *_: intent("settings"))
buttons.pack_start(settings, True, True, 0)
# Closing active safety UI means Stop; it cannot silently hide ongoing access.
window.connect("delete-event", lambda *_: (intent("stop"), True)[1])


def update(value):
    global paused
    paused = value.get("paused", False)
    grant = value.get("grant")
    if grant:
        label.set_text(("Access paused: " if paused else "Access active: ") + ", ".join(grant["scopes"]))
        pause.set_label("Resume" if paused else "Pause")
        window.show_all()
        print(json.dumps({"method": "presented", "generation": value["generation"]}), flush=True)
    else:
        window.hide()
    return False


def reader():
    try:
        for line in sys.stdin.buffer:
            if len(line) > 65536:
                break
            GLib.idle_add(update, json.loads(line))
    finally:
        GLib.idle_add(Gtk.main_quit)


threading.Thread(target=reader, daemon=True).start()
intent("ready")
Gtk.main()
