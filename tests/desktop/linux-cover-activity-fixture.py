#!/usr/bin/python3
"""Run the real observer against the guarded appliance's test HID device."""

import asyncio
from pathlib import Path
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import activityd
from activity_events import bitmap, relevant


def fixture_candidates():
    nodes = native_candidates()
    matches = []
    for endpoint in Path("/sys/class/input").glob("event*"):
        resolved = endpoint.resolve(strict=True)
        if not resolved.is_relative_to("/sys/devices/virtual/input"):
            continue
        try:
            name = (endpoint / "device/name").read_text().strip()
        except OSError:
            continue
        if name == "LinuxVM Target-Native Control":
            matches.append((endpoint, resolved))
    if len(matches) != 1:
        raise ValueError("input_coverage_unavailable")
    endpoint, resolved = matches[0]
    keys, relative, absolute = (bitmap((endpoint / "device/capabilities" / key).read_text())
                                for key in ("key", "rel", "abs"))
    node = Path("/dev/input") / endpoint.name
    info = node.lstat()
    if not stat.S_ISCHR(info.st_mode) or not relevant(keys, relative, absolute):
        raise ValueError("input_coverage_unavailable")
    nodes[str(node)] = (info.st_rdev, info.st_ino, str(resolved), keys, relative, absolute)
    return nodes


if __name__ == "__main__":
    native_candidates = activityd.Tracker.candidates
    activityd.Tracker.candidates = staticmethod(fixture_candidates)
    activityd.SOCKET = Path("/run/machine-control-cover-test/activity.sock")
    asyncio.run(activityd.main())
