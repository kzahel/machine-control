#!/usr/bin/env python3
"""Headed native portal probe; consent is exercised by an independent controller."""

import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.runtime))
from portal import Portal
from gi.repository import GLib

loop = GLib.MainLoop()


def changed():
    args.output.write_text(json.dumps({"state": portal.state, "error": portal.error}))
    if portal.ready:
        GLib.timeout_add(500, frame)


def frame():
    try:
        data = portal.capture()
        args.output.with_suffix(".png").write_bytes(data)
        portal.move(10, 10)
        args.output.write_text(json.dumps({"state": portal.state, "captureBytes": len(data),
                                         "devices": portal.devices, "pointerDelivered": True,
                                         "streamProperties": portal.properties}))
    except Exception as error:
        args.output.write_text(json.dumps({"state": "failed", "error": str(error)}))
    return False


portal = Portal(changed)
portal.connect()
GLib.timeout_add_seconds(180, lambda: loop.quit() or False)
try:
    loop.run()
finally:
    portal.close()
