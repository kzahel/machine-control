#!/usr/bin/env python3
"""Persistent active-session facade for LinuxVM target-native control."""

from __future__ import annotations

import argparse
import asyncio
import gettext
import hashlib
import json
import os
import re
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
import uuid
from collections import OrderedDict
from functools import cached_property
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib

import linuxui


SCHEMA = "machine-control/v0"
ROUTE = "guest.user/linux.atspi"
CAPTURE_ROUTE = "guest.user/gnome-screenshot"
SHELL_CAPTURE_ROUTE = "guest.user/gnome-shell-screenshot-shortcut"
SHELL_CAPTURE_KEYS = {
    "display": ("screenshot", "<Shift>Print", "shift+sysrq"),
    "active_window": ("screenshot-window", "<Alt>Print", "alt+sysrq"),
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_END = b"\x00\x00\x00\x00IEND\xaeB`\x82"
MAX_CAPTURE_BYTES = 64 * 1024 * 1024
ARTIFACT_DIRECTORY = Path.home() / ".cache/linuxvm-testbed/artifacts"
INPUT_SOCKET = Path("/run/linuxvm-testbed/input.sock")
INPUT_ROUTE = "guest.system/linux.uinput"
APPLICATION_ROUTE = "guest.user/linux.systemd-atspi"
CLIPBOARD_TYPE = "text/plain;charset=utf-8"
CLIPBOARD_OWNERSHIP_TIMEOUT_SECONDS = 3.0
CLIPBOARD_FOCUS_SETTLE_SECONDS = 0.3


def clipboard_serves(expected: bytes) -> bool:
    """Wait until the clipboard serves exactly the expected text."""
    deadline = time.monotonic() + CLIPBOARD_OWNERSHIP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            current = subprocess.run(
                ["/usr/bin/wl-paste", "--no-newline", "--type", CLIPBOARD_TYPE],
                capture_output=True,
                timeout=1,
                check=False,
            )
        except subprocess.TimeoutExpired:
            current = None
        if current is not None and current.returncode == 0 and current.stdout == expected:
            return True
        time.sleep(0.05)
    return False


def role_name(native: str) -> str:
    aliases = {
        "application": "application",
        "frame": "window",
        "dialog": "dialog",
        "push button": "button",
        "toggle button": "button",
        "check box": "checkbox",
        "radio button": "radio",
        "text": "text",
        "entry": "text_field",
        "password text": "secure_text_field",
        "menu": "menu",
        "menu item": "menu_item",
        "page tab": "tab",
        "link": "link",
    }
    return aliases.get(native, native.replace(" ", "_"))


class ControlFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class UnverifiedCapture(ControlFailure):
    """The appliance broker delivered the shortcut, with no usable artifact observed."""


# Common request names (contracts/request-v0.schema.json) and the appliance's
# historical names. Drag starts at the common x/y.
COMMON_FIELDS = {"deltaX": "dx", "deltaY": "dy", "applicationId": "desktopId"}
DRAG_FIELDS = {"x": "x1", "y": "y1"}


def normalize_request(request: dict[str, Any]) -> dict[str, Any]:
    """Map common field names to internal ones; refuse conflicting duplicates."""
    aliases = dict(COMMON_FIELDS)
    if request.get("operation") == "input.drag":
        aliases.update(DRAG_FIELDS)
    result = dict(request)
    for common, internal in aliases.items():
        if common not in request:
            continue
        if internal in request and request[internal] != request[common]:
            raise ControlFailure(
                "invalid_request", f"Conflicting {common} and {internal} values"
            )
        result[internal] = result.pop(common)
    return result


class Resident:
    def __init__(self) -> None:
        self.generation = str(uuid.uuid4())
        self.started = time.monotonic()
        self.snapshot_sequence = 0
        self.snapshots: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def envelope(self, request: dict[str, Any], operation: str) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "requestId": str(request.get("requestId") or uuid.uuid4()),
            "operation": operation,
            "generation": self.generation,
            "desktop": "GNOME Wayland",
            "accepted": True,
            "actualRoute": ROUTE,
            "fidelity": "semantic_native",
            "delivery": "not_applicable",
            "effect": "not_applicable",
            "uncertainty": "none",
            "fallbackUsed": False,
            "agentRoundTrips": 1,
            "hostInterference": "none",
        }

    def call_input(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(8)
                client.connect(str(INPUT_SOCKET))
                client.sendall(
                    json.dumps(request, separators=(",", ":")).encode() + b"\n"
                )
                response = bytearray()
                while True:
                    chunk = client.recv(65536)
                    if not chunk:
                        break
                    response.extend(chunk)
        except OSError as error:
            raise ControlFailure("input_unavailable", str(error)) from error
        value = json.loads(response)
        if not value.get("accepted"):
            raise ControlFailure(
                "input_refused", str(value.get("error") or "Input broker refused")
            )
        return value

    def display_geometry(self) -> dict[str, int]:
        display = Gdk.Display.get_default()
        if display is None or display.get_n_monitors() < 1:
            raise ControlFailure("display_unavailable", "No GDK display is available")
        rectangles = [
            display.get_monitor(index).get_geometry()
            for index in range(display.get_n_monitors())
        ]
        left = min(value.x for value in rectangles)
        top = min(value.y for value in rectangles)
        right = max(value.x + value.width for value in rectangles)
        bottom = max(value.y + value.height for value in rectangles)
        return {
            "x": left,
            "y": top,
            "width": right - left,
            "height": bottom - top,
        }

    def input_ready(self) -> bool:
        try:
            return self.call_input({"operation": "status"}).get("state") == "ready"
        except (ControlFailure, json.JSONDecodeError):
            return False

    def fail(
        self,
        request: dict[str, Any],
        operation: str,
        code: str,
        message: str,
    ) -> dict[str, Any]:
        result = self.envelope(request, operation)
        result.update(
            {
                "accepted": False,
                "delivery": "refused",
                "effect": "refused",
                "errorCode": code,
                "message": message,
            }
        )
        return result

    def element(self, info: dict[str, Any], reference: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "reference": reference,
            "role": role_name(info["role"]),
            "nativeRole": info["role"],
            "label": info["name"],
            "enabled": "enabled" in info["states"],
            "actions": [value["name"] for value in info["actions"]],
            "depth": info["depth"],
        }
        if info.get("description"):
            result["description"] = info["description"]
        if "bounds" in info:
            result["bounds"] = info["bounds"]
        return result

    def desktop_state(self) -> str:
        """Common desktopState from the session's GNOME screen shield."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            value = bus.call_sync(
                "org.gnome.ScreenSaver",
                "/org/gnome/ScreenSaver",
                "org.gnome.ScreenSaver",
                "GetActive",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            ).unpack()[0]
        except Exception:
            return "unknown"
        if type(value) is not bool:
            return "unknown"
        return "locked" if value else "unlocked"

    def status(self, request: dict[str, Any]) -> dict[str, Any]:
        root = linuxui.desktop()
        applications = linuxui.application_roots(root)
        desktop_state = self.desktop_state()
        input_ready = self.input_ready()
        result = self.envelope(request, "status")
        result["data"] = {
            "semanticState": "ready",
            "captureState": self.capture_state(desktop_state, input_ready),
            "inputState": "ready" if input_ready else "unavailable",
            "sessionType": os.environ.get("XDG_SESSION_TYPE", "wayland"),
            "desktopName": os.environ.get("XDG_CURRENT_DESKTOP", "GNOME"),
            "applicationCount": len(applications),
            "displayGeometry": self.display_geometry(),
            "residentPid": os.getpid(),
            "uptimeMs": int((time.monotonic() - self.started) * 1000),
            "desktopState": desktop_state,
            # The dedicated appliance admits its claimed same-user callers
            # without per-surface consent: a standing appliance policy.
            "deployment": {
                "policy": {
                    "preset": "appliance",
                    "grantMode": "standing",
                    "protectedAdministration": False,
                },
                "availability": {"paused": False, "blockingReasons": []},
                "browserOnlyWhileLocked": False,
            },
        }
        return result

    def capabilities(self, request: dict[str, Any]) -> dict[str, Any]:
        result = self.envelope(request, "capabilities")
        input_ready = self.input_ready()
        shell_shortcut = self.capture_route == SHELL_CAPTURE_ROUTE
        result["data"] = {
            "provider": "linux-native",
            "operations": [
                "status",
                "capabilities",
                "applications",
                "windows",
                "snapshot",
                "action",
                "focus",
                "set_value",
                "capture",
                "application.launch",
                "application.activate",
                "application.terminate",
                "input.move",
                "input.click",
                "input.drag",
                "input.scroll",
                "input.key",
                "input.text",
            ],
            "semantic": {
                "route": ROUTE,
                "fidelity": "semantic_native",
                "sessionRequirement": "active_user_atspi",
            },
            "capture": {
                "state": self.capture_state(self.desktop_state(), input_ready),
                "route": self.capture_route,
                "targets": ["display", "active_window"],
                "artifactLifetime": "until_cleanup",
                "sessionRequirement": "unlocked_active_user_gnome_wayland",
                "clipboardImageSideEffect": shell_shortcut,
                "savesScreenshotInPictures": shell_shortcut,
            },
            "input": {
                "state": "ready" if input_ready else "unavailable",
                "route": INPUT_ROUTE,
                "fidelity": "virtual_hid",
                "privilege": "root_test_appliance",
                "authorization": "active_user_owned_socket",
                "sessionRequirement": "logged_in_unlocked_graphical_session",
                "clipboardTextSideEffect": True,
            },
            "applicationLifecycle": {
                "state": "ready",
                "route": APPLICATION_ROUTE,
                "launch": "systemd_user_transient_unit",
                "activation": "atspi_component_focus",
                "termination": ["owned_transient_unit", "atspi_process"],
            },
            "outerRecoveryRequired": False,
        }
        return result

    def find_application(self, query: str) -> Any | None:
        folded = query.casefold()
        for application in linuxui.application_roots(linuxui.desktop()):
            name = linuxui.safe(application.get_name, "") or ""
            if folded == name.casefold() or folded in name.casefold():
                return application
        return None

    def before_effect(self) -> None:
        """Resident adapters may fence native dispatch after blocking preflight."""

    def application_launch(self, request: dict[str, Any]) -> dict[str, Any]:
        command = request.get("command")
        if (
            not isinstance(command, list)
            or not command
            or len(command) > 64
            or not all(isinstance(value, str) and value for value in command)
        ):
            raise ControlFailure(
                "invalid_request", "Application command must be a nonempty string array"
            )
        unit = f"linuxvm-app-{uuid.uuid4().hex}.service"
        self.before_effect()
        completed = subprocess.run(
            [
                "/usr/bin/systemd-run",
                "--user",
                "--quiet",
                "--collect",
                "--property=ExitType=cgroup",
                "--unit",
                unit,
                "--",
                *command,
            ],
            capture_output=True,
            check=False,
            timeout=15,
        )
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise ControlFailure("launch_failed", detail or "systemd-run failed")

        expected = str(request.get("expectTarget") or "")
        application = None
        if expected:
            deadline = time.monotonic() + min(
                max(float(request.get("timeoutSeconds", 8)), 0), 30
            )
            while time.monotonic() < deadline:
                application = self.find_application(expected)
                if application is not None:
                    break
                time.sleep(0.1)
        result = self.envelope(request, "application.launch")
        result.update(
            {
                "actualRoute": APPLICATION_ROUTE,
                "fidelity": "target_user_session",
                "delivery": "confirmed",
                "effect": "application_observed" if application else "unverifiable",
                "uncertainty": "none" if application else "no_expected_target",
            }
        )
        result["data"] = {
            "unit": unit,
            "application": (
                {
                    "name": linuxui.safe(application.get_name, "") or "",
                    "processId": linuxui.safe(application.get_process_id, 0) or 0,
                }
                if application is not None
                else None
            ),
        }
        return result

    def application_activate(self, request: dict[str, Any]) -> dict[str, Any]:
        query = str(request.get("target") or "")
        desktop_id = str(request.get("desktopId") or "")
        if not query and not desktop_id:
            raise ControlFailure(
                "invalid_request", "Application target or applicationId is required"
            )
        if desktop_id:
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", desktop_id):
                raise ControlFailure("invalid_request", "Application ID is invalid")
            self.before_effect()
            completed = subprocess.run(
                ["/usr/bin/gtk-launch", desktop_id],
                capture_output=True,
                check=False,
                timeout=15,
            )
            if completed.returncode != 0:
                detail = completed.stderr.decode("utf-8", errors="replace").strip()
                raise ControlFailure("activation_failed", detail or "gtk-launch failed")
            if not query:
                result = self.envelope(request, "application.activate")
                result.update(
                    {
                        "actualRoute": APPLICATION_ROUTE,
                        "fidelity": "desktop_application_activation",
                        "delivery": "confirmed",
                        "effect": "unverifiable",
                        "uncertainty": "no_expected_target",
                    }
                )
                result["data"] = {"desktopId": desktop_id}
                return result
        application = self.find_application(query)
        if desktop_id and application is None:
            deadline = time.monotonic() + min(
                max(float(request.get("timeoutSeconds", 8)), 0), 30
            )
            while time.monotonic() < deadline:
                application = self.find_application(query)
                if application is not None:
                    break
                time.sleep(0.1)
        if application is None:
            raise ControlFailure("not_found", "Application is not present in AT-SPI")
        candidates = [child for _, child in linuxui.children(application)]
        if not candidates:
            raise ControlFailure("not_found", "Application exposes no window")
        window = candidates[0]
        interfaces = linuxui.interfaces(window)
        if desktop_id:
            time.sleep(0.2)
        else:
            try:
                self.before_effect()
                focused = "Component" in interfaces and window.grab_focus()
            except Exception as error:
                raise ControlFailure(
                    "activation_unsupported",
                    "GNOME Wayland rejected AT-SPI top-level activation; use applicationId",
                ) from error
            if not focused:
                raise ControlFailure(
                    "activation_unsupported",
                    "GNOME Wayland rejected AT-SPI top-level activation; use applicationId",
                )
        effect = "active" in linuxui.state_names(window) or "focused" in linuxui.state_names(
            window
        )
        result = self.envelope(request, "application.activate")
        result.update(
            {
                "actualRoute": APPLICATION_ROUTE,
                "fidelity": (
                    "desktop_application_activation"
                    if desktop_id
                    else "semantic_native"
                ),
                "delivery": "confirmed",
                "effect": "window_active" if effect else "unverifiable",
                "uncertainty": "none" if effect else "no_independent_active_state",
            }
        )
        result["data"] = {
            "application": linuxui.safe(application.get_name, "") or "",
            "window": linuxui.safe(window.get_name, "") or "",
            "desktopId": desktop_id or None,
        }
        return result

    def application_terminate(self, request: dict[str, Any]) -> dict[str, Any]:
        unit = str(request.get("unit") or "")
        query = str(request.get("target") or "")
        process_id = 0
        if unit:
            if not re.fullmatch(r"linuxvm-app-[0-9a-f]{32}\.service", unit):
                raise ControlFailure("invalid_request", "Unit is not resident-owned")
            self.before_effect()
            completed = subprocess.run(
                ["/usr/bin/systemctl", "--user", "stop", unit],
                capture_output=True,
                check=False,
                timeout=15,
            )
            if completed.returncode != 0:
                detail = completed.stderr.decode("utf-8", errors="replace").strip()
                raise ControlFailure("termination_failed", detail or "Unit stop failed")
        elif query:
            application = self.find_application(query)
            if application is None:
                raise ControlFailure("not_found", "Application is not present in AT-SPI")
            process_id = int(linuxui.safe(application.get_process_id, 0) or 0)
            if process_id <= 1:
                raise ControlFailure("termination_failed", "Application PID is invalid")
            self.before_effect()
            os.kill(process_id, signal.SIGTERM)
        else:
            raise ControlFailure("invalid_request", "Unit or target is required")

        terminated = True
        if query:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if self.find_application(query) is None:
                    break
                time.sleep(0.1)
            else:
                terminated = False

        result = self.envelope(request, "application.terminate")
        result.update(
            {
                "actualRoute": APPLICATION_ROUTE,
                "fidelity": "target_user_session",
                "delivery": "confirmed",
                "effect": (
                    "application_terminated" if terminated else "unverifiable"
                ),
                "uncertainty": "none" if terminated else "application_still_observed",
            }
        )
        result["data"] = {"unit": unit or None, "processId": process_id or None}
        return result

    def input(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation") or "")
        action = operation.removeprefix("input.")
        broker_request: dict[str, Any] = {"operation": action}
        geometry = self.display_geometry()
        for name in (
            "x",
            "y",
            "x1",
            "y1",
            "x2",
            "y2",
            "dx",
            "dy",
            "button",
            "count",
            "steps",
            "durationMs",
            "key",
        ):
            if name in request:
                broker_request[name] = request[name]
        if action in ("move", "drag") or (
            action in ("click", "scroll") and "x" in request
        ):
            broker_request["width"] = geometry["width"]
            broker_request["height"] = geometry["height"]
            for name in ("x", "x1", "x2"):
                if name in broker_request:
                    broker_request[name] = int(broker_request[name]) - geometry["x"]
            for name in ("y", "y1", "y2"):
                if name in broker_request:
                    broker_request[name] = int(broker_request[name]) - geometry["y"]
        if action in ("click", "scroll") and "x" in broker_request:
            self.call_input(
                {
                    "operation": "move",
                    "x": broker_request.pop("x"),
                    "y": broker_request.pop("y"),
                    "width": broker_request.pop("width"),
                    "height": broker_request.pop("height"),
                }
            )

        clipboard_side_effect = False
        if action == "text":
            text = str(request.get("text") or "")
            # GNOME offers no data-control protocol, so wl-copy and wl-paste
            # each take keyboard focus briefly. In its default mode wl-copy
            # returns only once it owns the selection and leaves a child to
            # serve it; pasting earlier inserts the previous contents, and
            # pasting before focus returns loses the keystroke.
            # The serving child inherits these descriptors, so use a file
            # rather than a pipe that would stay open until it exits.
            with tempfile.TemporaryFile() as errors:
                try:
                    copied = subprocess.run(
                        ["/usr/bin/wl-copy", "--type", CLIPBOARD_TYPE],
                        input=text.encode("utf-8"),
                        stdout=subprocess.DEVNULL,
                        stderr=errors,
                        timeout=CLIPBOARD_OWNERSHIP_TIMEOUT_SECONDS,
                        check=False,
                    )
                except subprocess.TimeoutExpired as error:
                    raise ControlFailure(
                        "text_delivery_failed",
                        "Clipboard ownership was not established",
                    ) from error
                if copied.returncode != 0:
                    errors.seek(0)
                    raise ControlFailure(
                        "text_delivery_failed",
                        errors.read().decode("utf-8", errors="replace").strip()
                        or "Clipboard ownership was not established",
                    )
            if not clipboard_serves(text.encode("utf-8")):
                raise ControlFailure(
                    "text_delivery_failed", "Clipboard did not serve the requested text"
                )
            time.sleep(CLIPBOARD_FOCUS_SETTLE_SECONDS)
            self.call_input({"operation": "key", "key": "ctrl+v"})
            clipboard_side_effect = True
        else:
            self.call_input(broker_request)

        result = self.envelope(request, operation)
        result.update(
            {
                "actualRoute": INPUT_ROUTE,
                "fidelity": "virtual_hid",
                "delivery": "confirmed",
                "effect": "unverifiable",
                "uncertainty": "no_independent_state_change",
            }
        )
        result["data"] = {
            "displayGeometry": geometry,
            "clipboardTextSideEffect": clipboard_side_effect,
            "privilege": "root_test_appliance",
        }
        return result

    @cached_property
    def capture_route(self) -> str:
        try:
            version = subprocess.check_output(
                ["/usr/bin/gnome-shell", "--version"], text=True, timeout=3,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            return CAPTURE_ROUTE
        match = re.search(r"\bGNOME Shell (\d+)\b", version)
        if match and int(match[1]) >= 50:
            return SHELL_CAPTURE_ROUTE
        return CAPTURE_ROUTE

    def capture_state(self, desktop_state: str, input_ready: bool) -> str:
        if desktop_state != "unlocked":
            return "unavailable"
        if self.capture_route == SHELL_CAPTURE_ROUTE and not input_ready:
            return "unavailable"
        return "ready"

    def legacy_capture(self, target: str, artifact_path: Path) -> bytes:
        command = ["/usr/bin/gnome-screenshot"]
        if target == "active_window":
            command.append("--window")
        command.extend(("--file", str(artifact_path)))
        self.before_effect()
        try:
            completed = subprocess.run(
                command, capture_output=True, check=False, timeout=15,
            )
        except subprocess.TimeoutExpired as error:
            raise ControlFailure("capture_failed", "GNOME screenshot timed out") from error
        if completed.returncode != 0 or not artifact_path.is_file():
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise ControlFailure(
                "capture_failed",
                detail or "GNOME screenshot provider did not produce an artifact",
            )
        return artifact_path.read_bytes()

    def shell_capture(self, target: str) -> bytes:
        binding, accelerator, key = SHELL_CAPTURE_KEYS[target]
        settings = Gio.Settings.new("org.gnome.shell.keybindings")
        lockdown = Gio.Settings.new("org.gnome.desktop.lockdown")
        if (accelerator not in settings.get_strv(binding)
                or lockdown.get_boolean("disable-save-to-disk")):
            raise ControlFailure(
                "capture_unavailable", "GNOME Shell screenshot shortcut or saving is disabled",
            )

        pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
        directory = Path(pictures or Path.home()) / gettext.dgettext("gnome-shell", "Screenshots")
        previous = set(directory.glob("*.png"))
        self.before_effect()
        self.call_input({"operation": "key", "key": key})
        try:
            return self.read_shell_capture(directory, previous)
        except OSError as error:
            raise UnverifiedCapture("capture_failed", "Cannot read the new GNOME screenshot") from error

    def read_shell_capture(self, directory: Path, previous: set[Path]) -> bytes:
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            candidates = set(directory.glob("*.png")) - previous
            if len(candidates) > 1:
                raise UnverifiedCapture("capture_failed", "GNOME Shell produced ambiguous screenshot files")
            if candidates:
                # GNOME writes to the final name. Wait for its complete PNG
                # and refuse symlinks or non-regular files.
                path = next(iter(candidates))
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                with os.fdopen(os.open(path, flags), "rb") as source:
                    info = os.fstat(source.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                        raise UnverifiedCapture("capture_failed", "Invalid GNOME Shell screenshot file")
                    content = source.read(MAX_CAPTURE_BYTES + 1)
                if len(content) > MAX_CAPTURE_BYTES:
                    raise UnverifiedCapture("capture_failed", "GNOME Shell screenshot exceeds the artifact limit")
                if content.endswith(PNG_END):
                    return content
            time.sleep(0.05)
        raise UnverifiedCapture("capture_failed", "GNOME Shell did not produce a complete screenshot")

    def capture(self, request: dict[str, Any]) -> dict[str, Any]:
        target = str(request.get("target") or "display")
        if target not in SHELL_CAPTURE_KEYS:
            raise ControlFailure(
                "unsupported_target", "Capture target must be display or active_window",
            )
        if self.desktop_state() != "unlocked":
            raise ControlFailure("capture_unavailable", "The GNOME session must be unlocked")

        ARTIFACT_DIRECTORY.mkdir(parents=True, exist_ok=True, mode=0o700)
        artifact_id = str(uuid.uuid4())
        artifact_path = ARTIFACT_DIRECTORY / f"{artifact_id}.png"
        shell_shortcut = self.capture_route == SHELL_CAPTURE_ROUTE
        capture_failure = UnverifiedCapture if shell_shortcut else ControlFailure
        try:
            if shell_shortcut:
                content = self.shell_capture(target)
            else:
                content = self.legacy_capture(target, artifact_path)
            if (len(content) < 24 or not content.startswith(PNG_SIGNATURE)
                    or content[12:16] != b"IHDR" or not content.endswith(PNG_END)):
                raise capture_failure("capture_failed", "Capture artifact is not a complete PNG")
            width, height = struct.unpack(">II", content[16:24])
            if not width or not height:
                raise capture_failure("capture_failed", "Capture artifact has invalid dimensions")
            if self.desktop_state() != "unlocked":
                raise capture_failure("capture_unavailable", "The GNOME session locked during capture")
            if shell_shortcut:
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                with os.fdopen(os.open(artifact_path, flags, 0o600), "wb") as artifact:
                    artifact.write(content)
        except (OSError, ControlFailure):
            artifact_path.unlink(missing_ok=True)
            raise
        result = self.envelope(request, "capture")
        result.update(
            {
                "actualRoute": self.capture_route,
                "fidelity": (
                    "pixel_exact_active_window"
                    if target == "active_window"
                    else "pixel_full_display"
                ),
                "delivery": "confirmed",
                "effect": "artifact_observed",
            }
        )
        result["data"] = {
            "artifact": {
                "id": artifact_id,
                "guestPath": str(artifact_path),
                "mediaType": "image/png",
                "byteLength": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "width": width,
                "height": height,
            },
            "target": target,
            "selection": "current_active_window" if target == "active_window" else None,
            "clipboardImageSideEffect": shell_shortcut,
            "savesScreenshotInPictures": shell_shortcut,
        }
        return result

    def applications(self, request: dict[str, Any]) -> dict[str, Any]:
        root = linuxui.desktop()
        values = []
        for app in linuxui.application_roots(root):
            values.append(
                {
                    "name": linuxui.safe(app.get_name, "") or "",
                    "processId": linuxui.safe(app.get_process_id, 0) or 0,
                    "toolkit": linuxui.safe(app.get_toolkit_name, "") or "",
                    "toolkitVersion": linuxui.safe(app.get_toolkit_version, "")
                    or "",
                    "running": True,
                }
            )
        result = self.envelope(request, "applications")
        result["data"] = {"applications": values}
        return result

    def windows(self, request: dict[str, Any]) -> dict[str, Any]:
        root = linuxui.desktop()
        query = request.get("target")
        target = linuxui.choose_application(root, str(query) if query else None)
        values = []
        for index, child in linuxui.children(target):
            info = linuxui.node_info(child, f"0/{index}", 1)
            values.append(
                {
                    "role": role_name(info["role"]),
                    "nativeRole": info["role"],
                    "label": info["name"],
                    "bounds": info.get("bounds"),
                }
            )
        result = self.envelope(request, "windows")
        result["data"] = {"windows": values}
        return result

    def snapshot(self, request: dict[str, Any]) -> dict[str, Any]:
        root = linuxui.desktop()
        target_query = request.get("target")
        target = linuxui.choose_application(
            root, str(target_query) if target_query else None
        )
        maximum_depth = max(0, min(int(request.get("maxDepth", 8)), 32))
        maximum_elements = max(1, min(int(request.get("maxElements", 240)), 2000))
        query = str(request.get("query") or "").casefold()
        projection = str(request.get("projection") or "compact")
        if projection not in ("compact", "full"):
            raise ControlFailure("invalid_request", "Unknown snapshot projection")

        self.snapshot_sequence += 1
        snapshot_id = f"s{self.snapshot_sequence}"
        references: dict[str, Any] = {}
        elements = []
        truncated = False
        visited = 0
        for node, info in linuxui.walk(target, maximum_depth, 10000):
            visited += 1
            haystack = " ".join(
                (info["name"], info["role"], info["description"])
            ).casefold()
            if query and query not in haystack:
                continue
            reference = f"{self.generation}:{snapshot_id}:{info['path']}"
            references[reference] = node
            value = self.element(info, reference)
            if projection == "full":
                value["states"] = info["states"]
                value["interfaces"] = info["interfaces"]
                value["nativePath"] = info["path"]
            elements.append(value)
            if len(elements) >= maximum_elements:
                truncated = visited < 10000
                break

        self.snapshots[snapshot_id] = references
        while len(self.snapshots) > 20:
            self.snapshots.popitem(last=False)

        result = self.envelope(request, "snapshot")
        result["data"] = {
            "snapshotId": snapshot_id,
            "projection": projection,
            "elements": elements,
            "truncated": truncated,
        }
        return result

    def action(self, request: dict[str, Any]) -> dict[str, Any]:
        node = self.resolve_reference(request)
        requested = str(request.get("action") or "press").casefold()
        available = linuxui.actions(node)
        if not available:
            raise ControlFailure("unsupported_action", "Element exposes no action")

        selected = None
        aliases = {
            "press": ("click", "press", "activate"),
            "activate": ("activate", "click", "press"),
        }
        for candidate in aliases.get(requested, (requested,)):
            selected = next(
                (
                    value
                    for value in available
                    if candidate in value["name"].casefold()
                ),
                None,
            )
            if selected is not None:
                break
        if selected is None and requested in ("press", "activate"):
            selected = next(
                (value for value in available if not value["name"]),
                None,
            )
        if selected is None:
            raise ControlFailure("unsupported_action", "Requested action is unavailable")
        self.before_effect()
        if not node.do_action(selected["index"]):
            raise ControlFailure("delivery_failed", "AT-SPI rejected the action")

        result = self.envelope(request, "action")
        result.update(
            {
                "delivery": "confirmed",
                "effect": "unverifiable",
                "uncertainty": "no_independent_state_change",
            }
        )
        result["data"] = {"invoked": selected["name"] or f"index:{selected['index']}"}
        return result

    def resolve_reference(self, request: dict[str, Any]) -> Any:
        reference = str(request.get("reference") or "")
        parts = reference.split(":", 2)
        if len(parts) != 3 or parts[0] != self.generation:
            raise ControlFailure(
                "stale_reference", "Reference belongs to another resident generation"
            )
        snapshot = self.snapshots.get(parts[1])
        if snapshot is None or reference not in snapshot:
            raise ControlFailure("stale_reference", "Snapshot reference has expired")
        return snapshot[reference]

    def focus(self, request: dict[str, Any]) -> dict[str, Any]:
        node = self.resolve_reference(request)
        if "Component" not in linuxui.interfaces(node):
            raise ControlFailure("unsupported_action", "Element cannot receive focus")
        try:
            self.before_effect()
            delivered = node.grab_focus()
        except Exception as error:
            raise ControlFailure("delivery_failed", str(error)) from error
        if not delivered:
            raise ControlFailure("delivery_failed", "AT-SPI rejected focus")
        effect = "focused" in linuxui.state_names(node)
        result = self.envelope(request, "focus")
        result.update(
            {
                "delivery": "confirmed",
                "effect": "element_focused" if effect else "unverifiable",
                "uncertainty": "none" if effect else "focus_state_not_observed",
            }
        )
        result["data"] = {"focused": effect}
        return result

    def set_value(self, request: dict[str, Any]) -> dict[str, Any]:
        node = self.resolve_reference(request)
        interfaces = linuxui.interfaces(node)
        value = request.get("value")
        if "EditableText" in interfaces:
            self.before_effect()
            if not node.set_text_contents(str(value or "")):
                raise ControlFailure("delivery_failed", "AT-SPI rejected text value")
            kind = "text"
        elif "Value" in interfaces:
            self.before_effect()
            node.set_current_value(float(value))
            kind = "number"
        else:
            raise ControlFailure(
                "unsupported_action", "Element exposes no writable value interface"
            )
        result = self.envelope(request, "set_value")
        result.update(
            {
                "delivery": "confirmed",
                "effect": "unverifiable",
                "uncertainty": "no_independent_state_change",
            }
        )
        result["data"] = {"kind": kind, "value": value}
        return result

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation") or "")
        started = time.monotonic()
        try:
            dispatch = {
                "status": self.status,
                "capabilities": self.capabilities,
                "applications": self.applications,
                "windows": self.windows,
                "snapshot": self.snapshot,
                "action": self.action,
                "focus": self.focus,
                "set_value": self.set_value,
                "capture": self.capture,
                "application.launch": self.application_launch,
                "application.activate": self.application_activate,
                "application.terminate": self.application_terminate,
            }
            request = normalize_request(request)
            if operation.startswith("input."):
                result = self.input(request)
                result["elapsedMs"] = int((time.monotonic() - started) * 1000)
                return result
            if operation not in dispatch:
                raise ControlFailure(
                    "unsupported_operation", f"Unsupported operation: {operation}"
                )
            result = dispatch[operation](request)
        except UnverifiedCapture as error:
            result = self.fail(request, operation, error.code, str(error))
            result.update(actualRoute=SHELL_CAPTURE_ROUTE, delivery="confirmed",
                          effect="unverifiable", uncertainty="no_artifact_observed")
        except ControlFailure as error:
            result = self.fail(request, operation, error.code, str(error))
        except linuxui.UIError as error:
            result = self.fail(request, operation, "operation_failed", str(error))
        except Exception as error:
            result = self.fail(request, operation, "provider_error", str(error))
        result["elapsedMs"] = int((time.monotonic() - started) * 1000)
        return result


async def serve_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    resident: Resident,
) -> None:
    try:
        line = await reader.readline()
        request = json.loads(line.decode("utf-8"))
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        result = resident.handle(request)
    except Exception as error:
        result = resident.fail({}, "", "invalid_request", str(error))
    writer.write(json.dumps(result, separators=(",", ":"), ensure_ascii=False).encode())
    writer.write(b"\n")
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def run_server(socket_path: Path) -> None:
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()
    resident = Resident()
    server = await asyncio.start_unix_server(
        lambda reader, writer: serve_client(reader, writer, resident),
        path=str(socket_path),
    )
    os.chmod(socket_path, 0o600)
    async with server:
        await server.serve_forever()


def send_request(socket_path: Path, request: str) -> int:
    parsed = json.loads(request)
    if not isinstance(parsed, dict):
        raise ValueError("request must be a JSON object")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(socket_path))
        client.sendall(json.dumps(parsed, separators=(",", ":")).encode() + b"\n")
        response = bytearray()
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            response.extend(chunk)
    sys.stdout.buffer.write(response)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="linuxcontrol")
    commands = result.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--socket", required=True, type=Path)
    call = commands.add_parser("call")
    call.add_argument("--socket", required=True, type=Path)
    call.add_argument("request", nargs="?")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "serve":
        asyncio.run(run_server(args.socket))
        return 0
    request = args.request if args.request is not None else sys.stdin.read()
    return send_request(args.socket, request)


if __name__ == "__main__":
    raise SystemExit(main())
