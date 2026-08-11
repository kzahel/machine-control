"""Dependency-free ADB discovery and transport shared by Android-family targets."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Sequence


class AdbError(RuntimeError):
    """ADB is unavailable or cannot satisfy a transport operation."""


@dataclass(frozen=True)
class AdbDevice:
    serial: str
    state: str
    attributes: dict[str, str]


def find_adb(
    explicit: str | None = None,
    *,
    environment_variable: str | None = None,
) -> str:
    candidates: list[Path] = []
    configured = explicit
    if not configured and environment_variable:
        configured = os.environ.get(environment_variable)
    if configured:
        candidates.append(Path(configured).expanduser())
    path_adb = shutil.which("adb")
    if path_adb:
        candidates.append(Path(path_adb))
    for variable in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value).expanduser() / "platform-tools" / "adb")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
        )
    candidates.extend(
        [
            Path.home() / "Android" / "Sdk" / "platform-tools" / "adb",
            Path.home() / "Library" / "Android" / "sdk" / "platform-tools" / "adb",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    setting = f" or set {environment_variable}" if environment_variable else ""
    raise AdbError(
        f"adb was not found; install Android SDK Platform Tools{setting}"
    )


class AdbClient:
    def __init__(
        self,
        adb_path: str | None = None,
        *,
        serial: str | None = None,
        adb_environment_variable: str | None = None,
    ) -> None:
        self.adb = find_adb(
            adb_path, environment_variable=adb_environment_variable
        )
        self.requested_serial = serial

    def run(
        self,
        argv: Sequence[str],
        *,
        serial: str | None = None,
        check: bool = True,
        capture: bool = True,
        text: bool = True,
        input_data: str | bytes | None = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[Any]:
        command = [self.adb]
        if serial:
            command.extend(["-s", serial])
        command.extend(argv)
        return subprocess.run(
            command,
            check=check,
            capture_output=capture,
            text=text,
            input=input_data,
            timeout=timeout,
        )

    def shell(
        self,
        serial: str,
        argv: Sequence[str],
        *,
        check: bool = True,
        capture: bool = True,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return self.run(
            ["shell", *argv],
            serial=serial,
            check=check,
            capture=capture,
            text=True,
            timeout=timeout,
        )

    def shell_text(
        self,
        serial: str,
        argv: Sequence[str],
        *,
        check: bool = True,
        timeout: float | None = None,
    ) -> str:
        return self.shell(
            serial, argv, check=check, timeout=timeout
        ).stdout.replace("\r", "").strip()

    def devices(self) -> list[AdbDevice]:
        result = self.run(["devices", "-l"])
        devices: list[AdbDevice] = []
        for raw_line in result.stdout.replace("\r", "").splitlines()[1:]:
            line = raw_line.strip()
            if not line or line.startswith("*"):
                continue
            fields = line.split()
            if len(fields) < 2:
                continue
            attributes: dict[str, str] = {}
            for field in fields[2:]:
                if ":" in field:
                    key, value = field.split(":", 1)
                    attributes[key] = value
            devices.append(AdbDevice(fields[0], fields[1], attributes))
        return devices


def parse_battery(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "level": None,
        "status": None,
        "ac_powered": False,
        "usb_powered": False,
        "wireless_powered": False,
        "dock_powered": False,
    }
    keys = {
        "AC powered": "ac_powered",
        "USB powered": "usb_powered",
        "Wireless powered": "wireless_powered",
        "Dock powered": "dock_powered",
    }
    for raw_line in text.replace("\r", "").splitlines():
        line = raw_line.strip()
        if line.startswith("level:"):
            value = line.split(":", 1)[1].strip()
            result["level"] = int(value) if value.isdecimal() else None
        elif line.startswith("status:"):
            value = line.split(":", 1)[1].strip()
            result["status"] = int(value) if value.isdecimal() else None
        else:
            for label, key in keys.items():
                if line.startswith(label + ":"):
                    result[key] = line.split(":", 1)[1].strip().lower() == "true"
    result["powered"] = any(
        result[key]
        for key in ("ac_powered", "usb_powered", "wireless_powered", "dock_powered")
    )
    return result


def parse_wake_state(text: str) -> str:
    patterns = (
        r"mWakefulness=([A-Za-z]+)",
        r"Wakefulness:\s*([A-Za-z]+)",
        r"Display Power:\s*state=([A-Za-z]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = match.group(1).lower()
        if value in {"awake", "on"}:
            return "awake"
        if value in {"asleep", "off"}:
            return "asleep"
        if value in {"dozing", "doze"}:
            return "dozing"
        return value
    return "unknown"
