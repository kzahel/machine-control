#!/usr/bin/env python3
"""Persistent active-session facade for LinuxVM target-native control."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import socket
import struct
import subprocess
import sys
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

import linuxui


SCHEMA = "machine-control/v0"
ROUTE = "guest.user/linux.atspi"
CAPTURE_ROUTE = "guest.user/gnome-screenshot"
ARTIFACT_DIRECTORY = Path.home() / ".cache/linuxvm-testbed/artifacts"


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
            "inputState": "semantic_only",
            "sessionType": os.environ.get("XDG_SESSION_TYPE", "wayland"),
            "desktopName": os.environ.get("XDG_CURRENT_DESKTOP", "GNOME"),
            "applicationCount": len(applications),
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
                "capture",
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
            "input": {"state": "semantic_only"},
            "outerRecoveryRequired": False,
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
        reference = str(request.get("reference") or "")
        parts = reference.split(":", 2)
        if len(parts) != 3 or parts[0] != self.generation:
            raise ControlFailure(
                "stale_reference", "Reference belongs to another resident generation"
            )
        snapshot = self.snapshots.get(parts[1])
        if snapshot is None or reference not in snapshot:
            raise ControlFailure("stale_reference", "Snapshot reference has expired")
        node = snapshot[reference]
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
        result["data"] = {"invoked": selected["name"]}
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
                "capture": self.capture,
            }
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
