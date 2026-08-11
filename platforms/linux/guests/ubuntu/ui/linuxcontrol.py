#!/usr/bin/env python3
"""Persistent active-session facade for LinuxVM target-native control."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import signal
import socket
import struct
import subprocess
import sys
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk

import linuxui


SCHEMA = "machine-control/v0"
ROUTE = "guest.user/linux.atspi"
CAPTURE_ROUTE = "guest.user/gnome-screenshot"
ARTIFACT_DIRECTORY = Path.home() / ".cache/linuxvm-testbed/artifacts"
INPUT_SOCKET = Path("/run/linuxvm-testbed/input.sock")
INPUT_ROUTE = "guest.system/linux.uinput"
APPLICATION_ROUTE = "guest.user/linux.systemd-atspi"


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

    def status(self, request: dict[str, Any]) -> dict[str, Any]:
        root = linuxui.desktop()
        applications = linuxui.application_roots(root)
        result = self.envelope(request, "status")
        result["data"] = {
            "semanticState": "ready",
            "captureState": "ready",
            "inputState": "ready" if self.input_ready() else "unavailable",
            "sessionType": os.environ.get("XDG_SESSION_TYPE", "wayland"),
            "desktopName": os.environ.get("XDG_CURRENT_DESKTOP", "GNOME"),
            "applicationCount": len(applications),
            "displayGeometry": self.display_geometry(),
            "residentPid": os.getpid(),
            "uptimeMs": int((time.monotonic() - self.started) * 1000),
        }
        return result

    def capabilities(self, request: dict[str, Any]) -> dict[str, Any]:
        result = self.envelope(request, "capabilities")
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
                "state": "ready",
                "route": CAPTURE_ROUTE,
                "targets": ["display", "active_window"],
                "artifactLifetime": "until_cleanup",
                "sessionRequirement": "active_user_gnome_wayland",
            },
            "input": {
                "state": "ready" if self.input_ready() else "unavailable",
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
                "invalid_request", "Application target or desktopId is required"
            )
        if desktop_id:
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", desktop_id):
                raise ControlFailure("invalid_request", "Desktop ID is invalid")
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
                focused = "Component" in interfaces and window.grab_focus()
            except Exception as error:
                raise ControlFailure(
                    "activation_unsupported",
                    "GNOME Wayland rejected AT-SPI top-level activation; use desktopId",
                ) from error
            if not focused:
                raise ControlFailure(
                    "activation_unsupported",
                    "GNOME Wayland rejected AT-SPI top-level activation; use desktopId",
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
            provider = subprocess.Popen(
                [
                    "/usr/bin/wl-copy",
                    "--foreground",
                    "--paste-once",
                    "--type",
                    "text/plain;charset=utf-8",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            assert provider.stdin is not None
            provider.stdin.write(text.encode("utf-8"))
            provider.stdin.close()
            time.sleep(0.1)
            self.call_input({"operation": "key", "key": "ctrl+v"})
            try:
                provider.wait(timeout=3)
            except subprocess.TimeoutExpired as error:
                provider.terminate()
                provider.wait(timeout=2)
                raise ControlFailure(
                    "text_delivery_failed", "Clipboard paste was not consumed"
                ) from error
            if provider.returncode != 0:
                detail = (provider.stderr.read() if provider.stderr else b"").decode(
                    "utf-8", errors="replace"
                )
                raise ControlFailure("text_delivery_failed", detail.strip())
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

    def capture(self, request: dict[str, Any]) -> dict[str, Any]:
        target = str(request.get("target") or "display")
        if target not in ("display", "active_window"):
            raise ControlFailure(
                "unsupported_target",
                "Capture target must be display or active_window",
            )

        ARTIFACT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        artifact_id = str(uuid.uuid4())
        artifact_path = ARTIFACT_DIRECTORY / f"{artifact_id}.png"
        command = ["/usr/bin/gnome-screenshot"]
        if target == "active_window":
            command.append("--window")
        command.extend(("--file", str(artifact_path)))
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
        if completed.returncode != 0 or not artifact_path.is_file():
            artifact_path.unlink(missing_ok=True)
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise ControlFailure(
                "capture_failed",
                detail or "GNOME screenshot provider did not produce an artifact",
            )

        content = artifact_path.read_bytes()
        if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n":
            artifact_path.unlink(missing_ok=True)
            raise ControlFailure("capture_failed", "Capture artifact is not a PNG")
        width, height = struct.unpack(">II", content[16:24])
        result = self.envelope(request, "capture")
        result.update(
            {
                "actualRoute": CAPTURE_ROUTE,
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
            if not node.set_text_contents(str(value or "")):
                raise ControlFailure("delivery_failed", "AT-SPI rejected text value")
            kind = "text"
        elif "Value" in interfaces:
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
            if operation.startswith("input."):
                result = self.input(request)
                result["elapsedMs"] = int((time.monotonic() - started) * 1000)
                return result
            if operation not in dispatch:
                raise ControlFailure(
                    "unsupported_operation", f"Unsupported operation: {operation}"
                )
            result = dispatch[operation](request)
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
