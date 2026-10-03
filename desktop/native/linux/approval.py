#!/usr/bin/env python3
"""One-shot native approval UI on an inherited pipe, never an agent endpoint."""

import json
import ctypes
import os
import signal
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

if ctypes.CDLL(None).prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
    raise SystemExit("Approval lifetime could not be bound")

GLib.set_prgname("machine-control-approval")
Gtk.init([])
line = sys.stdin.buffer.readline(65537)
if len(line) > 65536:
    raise SystemExit("Approval frame is too large")
pending = json.loads(line)
if pending["parentId"] != os.getppid():
    raise SystemExit("Approval owner exited")
dialog = Gtk.Dialog(title="Machine Control — Allow access?", modal=True)
dialog.set_default_size(360, 220)
dialog.set_border_width(12)
dialog.add_button("Deny", Gtk.ResponseType.CANCEL)
dialog.add_button("Allow", Gtk.ResponseType.OK)
dialog.set_default_response(Gtk.ResponseType.CANCEL)
box = dialog.get_content_area()
box.set_spacing(8)
for text in [pending["reason"], pending["caller"] + " (unverified)"]:
    label = Gtk.Label(label=text, xalign=0)
    label.set_line_wrap(True)
    box.pack_start(label, False, False, 0)
buttons = []
for scope in pending["scopes"]:
    button = Gtk.CheckButton(label=scope)
    button.set_active(True)
    box.pack_start(button, False, False, 0)
    buttons.append(button)
seconds = Gtk.SpinButton.new_with_range(1, pending["duration"], 1)
seconds.set_value(pending["duration"])
seconds.get_accessible().set_name("Duration in seconds")
box.pack_start(seconds, False, False, 0)
dialog.show_all()
dialog.present()
response = dialog.run()
result = {"id": pending["id"], "allow": response == Gtk.ResponseType.OK,
          "scopes": [b.get_label() for b in buttons if b.get_active()],
          "duration": seconds.get_value_as_int()}
dialog.destroy()
print(json.dumps(result), flush=True)
