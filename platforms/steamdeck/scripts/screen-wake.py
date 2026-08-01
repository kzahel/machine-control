#!/usr/bin/env python3
"""Wake a forced-sleep Steam Deck display on the next Deck button press."""

from __future__ import annotations

import os
from pathlib import Path
import select
import subprocess
import sys
import time


REPORT_SIZE = 64
DECK_REPORT_TYPE = 0x09
DECK_HID_ID = "0003:000028DE:00001205"
CONNECTOR_WAIT_SECONDS = 10.0


def hid_uevent(path: str) -> dict[str, str]:
    hidraw_name = os.path.basename(path)
    try:
        lines = Path(f"/sys/class/hidraw/{hidraw_name}/device/uevent").read_text(
            encoding="utf-8"
        )
    except OSError:
        return {}
    return dict(line.split("=", 1) for line in lines.splitlines() if "=" in line)


def open_deck_hid_devices() -> list[tuple[int, str]]:
    devices: list[tuple[int, str]] = []
    for path in sorted(Path("/dev").glob("hidraw*")):
        uevent = hid_uevent(str(path))
        if (
            uevent.get("HID_ID") != DECK_HID_ID
            or not uevent.get("HID_PHYS", "").endswith("/input2")
        ):
            continue
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue
        devices.append((descriptor, str(path)))
    return devices


def read_reports(descriptor: int) -> list[bytes]:
    reports: list[bytes] = []
    while True:
        try:
            data = os.read(descriptor, REPORT_SIZE)
        except (BlockingIOError, OSError):
            return reports
        if not data:
            return reports
        reports.append(data)


def button_state(report: bytes) -> bool | None:
    if (
        len(report) != REPORT_SIZE
        or report[0] != 0x01
        or report[1] != 0x00
        or report[2] != DECK_REPORT_TYPE
    ):
        return None
    return bool(
        report[8]
        or report[9]
        or report[10] & 0x47
        or report[11] & 0x04
        or report[13] & 0x06
        or report[14] & 0x04
    )


def internal_connector_state() -> str | None:
    for path in sorted(Path("/sys/class/drm").glob("card*-eDP-*/enabled")):
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return None


def wait_until_screen_is_disabled(devices: list[tuple[int, str]]) -> None:
    deadline = time.monotonic() + CONNECTOR_WAIT_SECONDS
    while time.monotonic() < deadline:
        if internal_connector_state() == "disabled":
            return
        for descriptor, _path in devices:
            read_reports(descriptor)
        time.sleep(0.05)
    raise RuntimeError("internal connector did not become disabled")


def wait_until_buttons_released(devices: list[tuple[int, str]]) -> None:
    poller = select.poll()
    paths: dict[int, str] = {}
    latest_states: dict[int, bool] = {}
    for descriptor, path in devices:
        poller.register(descriptor, select.POLLIN)
        paths[descriptor] = path
    while True:
        for descriptor, flags in poller.poll():
            if not flags & select.POLLIN:
                continue
            for report in read_reports(descriptor):
                state = button_state(report)
                if state is not None:
                    latest_states[descriptor] = state
        if len(latest_states) == len(paths) and not any(latest_states.values()):
            return


def wake_screen() -> None:
    subprocess.run(
        ["gamescopectl", "drm_sleep_internal_screen", "false"],
        check=True,
        env=os.environ.copy(),
    )


def wait_for_button(devices: list[tuple[int, str]]) -> str:
    poller = select.poll()
    paths: dict[int, str] = {}
    for descriptor, path in devices:
        poller.register(descriptor, select.POLLIN)
        paths[descriptor] = path
    while True:
        for descriptor, flags in poller.poll():
            if not flags & select.POLLIN:
                continue
            for report in read_reports(descriptor):
                if button_state(report):
                    return paths[descriptor]


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} READY_PATH", file=sys.stderr)
        return 2
    devices = open_deck_hid_devices()
    if not devices:
        print("no readable Steam Deck controller HID devices", file=sys.stderr)
        return 1
    ready_path = Path(sys.argv[1])
    ready_path.parent.mkdir(parents=True, exist_ok=True)
    ready_path.write_text(
        "\n".join(path for _descriptor, path in devices) + "\n",
        encoding="utf-8",
    )
    try:
        wait_until_screen_is_disabled(devices)
        wait_until_buttons_released(devices)
        device_path = wait_for_button(devices)
        wake_screen()
        print(f"woke internal screen from button report on {device_path}", flush=True)
        return 0
    finally:
        ready_path.unlink(missing_ok=True)
        for descriptor, _path in devices:
            os.close(descriptor)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"screen wake watcher failed: {error}", file=sys.stderr)
        raise SystemExit(1)
