#!/usr/bin/env python3
"""Independent native actor for a dedicated test VM's visible portal chooser."""

import argparse
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--cancel", action="store_true")
parser.add_argument("--screen-only", action="store_true")
args = parser.parse_args()
sys.path.insert(0, str(args.runtime))
import linuxui
from gi.repository import GLib
linuxui.Atspi.init()

deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    try:
        context = GLib.MainContext.default()
        while context.pending():
            context.iteration(False)
        app = linuxui.choose_application(linuxui.desktop(), "xdg-desktop-portal-gnome")
        app.clear_cache()
        nodes = list(linuxui.walk(app, 25, 2000))
        windows = [node for node, info in nodes if info["role"] == "frame"
                   and "showing" in info["states"]]
        if len(windows) != 1:
            raise RuntimeError("Expected exactly one owned consent window")
        nodes = list(linuxui.walk(windows[0], 25, 2000))
        if args.cancel:
            selected = [(n, i) for n, i in nodes if i["name"] == "Cancel" and i["role"] == "push button"]
            assert len(selected) == 1 and selected[0][0].do_action(0)
            print("Consent cancelled")
            break
        check = [(n, i) for n, i in nodes if i["name"] == "Allow Remote Interaction" and i["role"] == "check box"]
        sources = [(n, i) for n, i in nodes if i["role"] == "toggle button"]
        share = [(n, i) for n, i in nodes if i["name"] == "Share" and i["role"] == "push button"]
        assert len(sources) == len(share) == 1
        assert len(check) == (0 if args.screen_only else 1)
        if check and "checked" not in linuxui.state_names(check[0][0]):
            assert check[0][0].do_action(0)
        # GNOME selects its sole monitor initially. GTK4 omits its checked
        # state from AT-SPI on this profile; toggling would deselect it. Require
        # the portal's returned stream and an actual frame as the oracle.
        assert share[0][0].do_action(0)
        print("Visible native consent submitted")
        break
    except (linuxui.UIError, RuntimeError, AssertionError):
        time.sleep(0.2)
else:
    print("Last portal nodes", [(i["role"], i["name"], i["states"]) for _, i in locals().get("nodes", [])], file=sys.stderr)
    raise SystemExit("No unambiguous portal chooser")
