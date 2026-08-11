#!/usr/bin/env python3
"""Project-neutral ADB lifecycle and transport for Meta Quest testbeds."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from providers.adb import (  # noqa: E402
    AdbClient as SharedAdbClient,
    AdbDevice,
    AdbError,
    parse_battery,
    parse_wake_state,
)


REMOTE_JOURNAL = "/data/local/tmp/quest-testbed-session.json"
JOURNAL_SCHEMA = "quest-testbed.session.v1"
DEFAULT_MIN_BATTERY = 15
QUEST_FEATURES = {
    "oculus.hardware.standalone_vr",
    "oculus.software.xrsp",
}
MANAGED_SETTINGS = (
    ("global", "stay_on_while_plugged_in", "3"),
    ("secure", "skip_launch_check_requires_controllers_enabled", "1"),
    ("global", "require_controllers_for_vr_apps", "0"),
)
KNOWN_DIALOG_PATTERNS = (
    "com.oculus.panelapp.settings",
    "OculusLinkAvailableDialogActivity",
    "com.meta.link.ui.dialogs",
    "LaunchCheckControllerRequiredDialogActivity",
)


class TestbedError(RuntimeError):
    """An expected configuration, validation, or device-operation failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def controller_name() -> str:
    return socket.gethostname().lower().rstrip(".") or "unknown-controller"


def state_root() -> Path:
    override = os.environ.get("QUEST_TESTBED_STATE_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "quest-testbed"
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg).expanduser() / "quest-testbed"
    return Path.home() / ".local" / "state" / "quest-testbed"


def sanitize_serial(serial: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", serial)


def pid_is_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class AdbClient(SharedAdbClient):
    def __init__(self, adb_path: str | None = None, serial: str | None = None) -> None:
        requested = (
            serial
            or os.environ.get("QUEST_TESTBED_SERIAL")
            or os.environ.get("ANDROID_SERIAL")
        )
        try:
            super().__init__(
                adb_path,
                serial=requested,
                adb_environment_variable="QUEST_TESTBED_ADB",
            )
        except AdbError as error:
            raise TestbedError(str(error)) from error

    def quest_like(self, device: AdbDevice) -> bool:
        summary = " ".join(
            [
                device.attributes.get("product", ""),
                device.attributes.get("model", ""),
                device.attributes.get("device", ""),
            ]
        )
        if re.search(r"oculus|meta|quest", summary, re.IGNORECASE):
            return True
        manufacturer = self.shell_text(
            device.serial, ["getprop", "ro.product.manufacturer"], check=False
        )
        model = self.shell_text(
            device.serial, ["getprop", "ro.product.model"], check=False
        )
        if re.search(r"oculus|meta|quest", f"{manufacturer} {model}", re.IGNORECASE):
            return True
        features = self.shell_text(
            device.serial, ["pm", "list", "features"], check=False
        )
        return any(feature in features for feature in QUEST_FEATURES)

    def select_quest(self) -> str:
        devices = self.devices()
        by_serial = {device.serial: device for device in devices}
        if self.requested_serial:
            device = by_serial.get(self.requested_serial)
            if not device:
                raise TestbedError(
                    f"requested Quest {self.requested_serial!r} is not connected"
                )
            if device.state != "device":
                if device.state == "unauthorized":
                    raise TestbedError(
                        f"Quest {device.serial} is unauthorized; put on the headset, "
                        "accept this controller's USB debugging RSA prompt, and select "
                        "Always allow"
                    )
                raise TestbedError(
                    f"requested Quest {device.serial!r} is in ADB state {device.state!r}"
                )
            if not self.quest_like(device):
                raise TestbedError(
                    f"requested Android device {device.serial!r} is not recognized as a Quest"
                )
            return device.serial

        candidates = [
            device
            for device in devices
            if device.state == "device"
            and not device.serial.startswith("emulator-")
            and self.quest_like(device)
        ]
        if len(candidates) == 1:
            return candidates[0].serial
        if len(candidates) > 1:
            serials = ", ".join(device.serial for device in candidates)
            raise TestbedError(
                f"multiple Quest headsets are connected ({serials}); pass --serial"
            )
        unauthorized = [device.serial for device in devices if device.state == "unauthorized"]
        if unauthorized:
            raise TestbedError(
                "attached Android device(s) are unauthorized: "
                + ", ".join(unauthorized)
                + "; put on the headset, accept this controller's USB debugging "
                "RSA prompt, and select Always allow"
            )
        raise TestbedError("no attached, authorized Quest headset was found")


def read_setting(client: AdbClient, serial: str, namespace: str, name: str) -> dict[str, Any]:
    value = client.shell_text(
        serial, ["settings", "get", namespace, name], check=False
    )
    if not value or value == "null":
        return {"present": False, "value": None}
    return {"present": True, "value": value}


def restore_setting(
    client: AdbClient, serial: str, namespace: str, name: str, saved: dict[str, Any]
) -> bool:
    if saved.get("present"):
        argv = ["settings", "put", namespace, name, str(saved.get("value", ""))]
    else:
        argv = ["settings", "delete", namespace, name]
    return client.shell(serial, argv, check=False).returncode == 0


def read_remote_journal(client: AdbClient, serial: str) -> dict[str, Any] | None:
    result = client.shell(serial, ["cat", REMOTE_JOURNAL], check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise TestbedError(
            f"Quest recovery journal is invalid; inspect {REMOTE_JOURNAL}: {error}"
        ) from error
    if not isinstance(value, dict) or value.get("schema") != JOURNAL_SCHEMA:
        raise TestbedError(
            f"Quest recovery journal has an unsupported schema at {REMOTE_JOURNAL}"
        )
    return value


def write_remote_journal(client: AdbClient, serial: str, journal: dict[str, Any]) -> None:
    token = journal["token"]
    temporary_remote = f"{REMOTE_JOURNAL}.{token}.tmp"
    with tempfile.TemporaryDirectory(prefix="quest-testbed-") as temporary:
        path = Path(temporary) / "session.json"
        path.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        client.run(["push", str(path), temporary_remote], serial=serial)
    try:
        client.shell(serial, ["mv", temporary_remote, REMOTE_JOURNAL])
    except BaseException:
        client.shell(serial, ["rm", "-f", temporary_remote], check=False)
        raise


def delete_remote_journal(client: AdbClient, serial: str) -> bool:
    return (
        client.shell(serial, ["rm", "-f", REMOTE_JOURNAL], check=False).returncode
        == 0
    )


def journal_owner_active(journal: dict[str, Any]) -> bool:
    return (
        journal.get("controller") == controller_name()
        and journal.get("mode") in {"session", "external"}
        and pid_is_alive(journal.get("owner_pid"))
    )


class LocalLock:
    def __init__(self, serial: str, token: str) -> None:
        self.path = state_root() / "locks" / f"{sanitize_serial(serial)}.lock"
        self.owner_path = self.path / "owner.json"
        self.token = token
        self.acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.mkdir()
        except FileExistsError:
            owner: dict[str, Any] = {}
            try:
                owner = json.loads(self.owner_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
            if owner.get("controller") == controller_name() and pid_is_alive(
                owner.get("pid")
            ):
                raise TestbedError(
                    f"Quest is already leased by local pid {owner.get('pid')}"
                )
            try:
                self.owner_path.unlink(missing_ok=True)
                self.path.rmdir()
                self.path.mkdir()
            except OSError as error:
                raise TestbedError(
                    f"cannot recover stale local Quest lock {self.path}: {error}"
                ) from error
        self.owner_path.write_text(
            json.dumps(
                {
                    "schema": "quest-testbed.local-lock.v1",
                    "controller": controller_name(),
                    "pid": os.getpid(),
                    "token": self.token,
                    "created_at": utc_now(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.acquired = True

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            owner = json.loads(self.owner_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            owner = {}
        if owner.get("token") == self.token:
            self.owner_path.unlink(missing_ok=True)
            try:
                self.path.rmdir()
            except OSError:
                pass
        self.acquired = False


def device_status(client: AdbClient, serial: str) -> dict[str, Any]:
    getprop = lambda name: client.shell_text(serial, ["getprop", name], check=False)
    boot_completed = getprop("sys.boot_completed") == "1"
    power_text = client.shell_text(serial, ["dumpsys", "power"], check=False)
    wake_state = parse_wake_state(power_text)
    state = wake_state if boot_completed else "booting"
    battery = parse_battery(
        client.shell_text(serial, ["dumpsys", "battery"], check=False)
    )
    journal = read_remote_journal(client, serial)
    return {
        "serial": serial,
        "state": state,
        "boot_completed": boot_completed,
        "manufacturer": getprop("ro.product.manufacturer") or "unknown",
        "model": getprop("ro.product.model") or "unknown",
        "product": getprop("ro.product.name") or "unknown",
        "api": getprop("ro.build.version.sdk") or "unknown",
        "abi": getprop("ro.product.cpu.abi") or "unknown",
        "battery": battery,
        "proximity_override": getprop("debug.oculus.disableProximity") or "0",
        "settings": {
            f"{namespace}/{name}": read_setting(client, serial, namespace, name)
            for namespace, name, _value in MANAGED_SETTINGS
        },
        "journal": journal,
    }


def battery_guard(status: dict[str, Any], minimum: int) -> None:
    battery = status["battery"]
    level = battery.get("level")
    if isinstance(level, int) and level < minimum and not battery.get("powered"):
        raise TestbedError(
            f"Quest battery is {level}% and not charging; refusing to keep it awake "
            f"below the {minimum}% safety threshold"
        )


def dismiss_dialogs(client: AdbClient, serial: str) -> None:
    dump = client.shell_text(
        serial, ["dumpsys", "activity", "activities"], check=False
    )
    task_ids: set[str] = set()
    for line in dump.splitlines():
        if not any(pattern in line for pattern in KNOWN_DIALOG_PATTERNS):
            continue
        for pattern in (r"Task\{[^#]*#(\d+)", r"\st(\d+)\}"):
            match = re.search(pattern, line)
            if match:
                task_ids.add(match.group(1))
    for task_id in sorted(task_ids):
        client.shell(serial, ["am", "stack", "remove", task_id], check=False)
    client.shell(serial, ["input", "keyevent", "KEYCODE_BACK"], check=False)
    client.shell(serial, ["input", "keyevent", "KEYCODE_ESCAPE"], check=False)


def normalize_reverse(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise TestbedError(
            f"reverse mapping {value!r} must use LOCAL=REMOTE, for example "
            "tcp:9757=tcp:9757"
        )
    local, remote = value.split("=", 1)
    if not local or not remote:
        raise TestbedError(f"invalid reverse mapping: {value!r}")
    return local, remote


def new_journal(
    client: AdbClient,
    serial: str,
    *,
    mode: str,
    owner_pid: int,
    stop_packages: list[str],
    reverses: list[tuple[str, str]],
    sleep_on_end: bool,
) -> dict[str, Any]:
    return {
        "schema": JOURNAL_SCHEMA,
        "token": uuid.uuid4().hex,
        "controller": controller_name(),
        "owner_pid": owner_pid,
        "mode": mode,
        "started_at": utc_now(),
        "serial": serial,
        "sleep_on_end": sleep_on_end,
        "stop_packages": stop_packages,
        "reverses": [{"local": local, "remote": remote} for local, remote in reverses],
        "settings": {
            f"{namespace}/{name}": read_setting(client, serial, namespace, name)
            for namespace, name, _value in MANAGED_SETTINGS
        },
        "observed_proximity_override": client.shell_text(
            serial, ["getprop", "debug.oculus.disableProximity"], check=False
        )
        or "0",
    }


def restore_journal(
    client: AdbClient,
    serial: str,
    journal: dict[str, Any],
    *,
    keep_awake: bool = False,
) -> bool:
    warnings: list[str] = []
    for package in journal.get("stop_packages", []):
        result = client.shell(serial, ["am", "force-stop", str(package)], check=False)
        if result.returncode != 0:
            warnings.append(f"could not stop package {package}")
    for mapping in journal.get("reverses", []):
        local = mapping.get("local") if isinstance(mapping, dict) else None
        if local:
            result = client.run(
                ["reverse", "--remove", str(local)], serial=serial, check=False
            )
            if result.returncode != 0:
                warnings.append(f"could not remove adb reverse {local}")

    critical_ok = True
    saved_settings = journal.get("settings", {})
    for namespace, name, _value in MANAGED_SETTINGS:
        key = f"{namespace}/{name}"
        saved = saved_settings.get(key)
        if not isinstance(saved, dict):
            warnings.append(f"journal omitted saved setting {key}")
            critical_ok = False
            continue
        if not restore_setting(client, serial, namespace, name, saved):
            warnings.append(f"could not restore Android setting {key}")
            critical_ok = False

    # This is a debug override, not a user preference. Always normalize it to
    # the safe behavior so an old script or interrupted run cannot preserve a
    # forced-near state indefinitely.
    if (
        client.shell(
            serial,
            ["setprop", "debug.oculus.disableProximity", "0"],
            check=False,
        ).returncode
        != 0
    ):
        warnings.append("could not re-enable the Quest proximity sensor")
        critical_ok = False
    client.shell(
        serial,
        [
            "am",
            "broadcast",
            "-a",
            "com.oculus.vrpowermanager.prox_open",
            "--ei",
            "timeout",
            "0",
        ],
        check=False,
    )
    if journal.get("sleep_on_end", True) and not keep_awake:
        if (
            client.shell(
                serial, ["input", "keyevent", "KEYCODE_SLEEP"], check=False
            ).returncode
            != 0
        ):
            warnings.append("could not send KEYCODE_SLEEP")
            critical_ok = False
    client.shell(
        serial,
        ["setprop", "debug.oculus.disableProximity", "0"],
        check=False,
    )

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if critical_ok:
        if not delete_remote_journal(client, serial):
            print(
                f"warning: restored the Quest but could not clear {REMOTE_JOURNAL}",
                file=sys.stderr,
            )
            return False
        return True
    print(
        f"warning: Quest cleanup is incomplete; recovery journal retained at {REMOTE_JOURNAL}",
        file=sys.stderr,
    )
    return False


def begin_lease(
    client: AdbClient,
    serial: str,
    *,
    mode: str,
    owner_pid: int,
    stop_packages: list[str],
    reverses: list[tuple[str, str]],
    min_battery: int,
    sleep_on_end: bool,
    wake: bool,
    disable_proximity: bool,
    should_dismiss_dialogs: bool,
) -> dict[str, Any]:
    existing = read_remote_journal(client, serial)
    if existing:
        if existing.get("controller") == controller_name() and not journal_owner_active(
            existing
        ):
            print("Recovering an interrupted Quest lease from this controller.")
            if not restore_journal(client, serial, existing):
                raise TestbedError("interrupted Quest lease could not be recovered")
        else:
            owner = existing.get("controller", "unknown controller")
            pid = existing.get("owner_pid", "unknown")
            raise TestbedError(
                f"Quest already has a recovery journal owned by {owner} pid {pid}; "
                "end that session or use recover --force after confirming it is stale"
            )

    status = device_status(client, serial)
    if not status["boot_completed"]:
        raise TestbedError("Quest is connected but has not finished booting")
    battery_guard(status, min_battery)
    journal = new_journal(
        client,
        serial,
        mode=mode,
        owner_pid=owner_pid,
        stop_packages=stop_packages,
        reverses=reverses,
        sleep_on_end=sleep_on_end,
    )
    write_remote_journal(client, serial, journal)
    try:
        if disable_proximity:
            result = client.shell(
                serial,
                ["setprop", "debug.oculus.disableProximity", "1"],
                check=False,
            )
            if result.returncode != 0:
                print(
                    "warning: Horizon OS did not accept the Meta proximity override",
                    file=sys.stderr,
                )
        for namespace, name, value in MANAGED_SETTINGS:
            result = client.shell(
                serial,
                ["settings", "put", namespace, name, value],
                check=False,
            )
            if result.returncode != 0:
                print(
                    f"warning: Horizon OS did not accept Android setting {namespace}/{name}",
                    file=sys.stderr,
                )
        if wake:
            client.shell(serial, ["input", "keyevent", "KEYCODE_WAKEUP"])
            client.shell(
                serial,
                [
                    "am",
                    "broadcast",
                    "-a",
                    "com.oculus.vrpowermanager.prox_close",
                    "--ei",
                    "timeout",
                    "0",
                ],
                check=False,
            )
        if should_dismiss_dialogs:
            dismiss_dialogs(client, serial)
        for local, remote in reverses:
            client.run(["reverse", local, remote], serial=serial)
    except BaseException:
        restore_journal(client, serial, journal)
        raise
    return journal


def parse_min_battery(value: str | int | None) -> int:
    if value is None:
        value = os.environ.get("QUEST_TESTBED_MIN_BATTERY", str(DEFAULT_MIN_BATTERY))
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise TestbedError("minimum battery threshold must be an integer") from error
    if result < 0 or result > 100:
        raise TestbedError("minimum battery threshold must be between 0 and 100")
    return result


def status_text(status: dict[str, Any]) -> str:
    battery = status["battery"]
    level = battery.get("level")
    power = "charging" if battery.get("powered") else "battery"
    lines = [
        f"serial: {status['serial']}",
        f"device: {status['manufacturer']} {status['model']}",
        f"android: API {status['api']} {status['abi']}",
        f"state: {status['state']}",
        f"battery: {level if level is not None else 'unknown'}% ({power})",
        f"proximity override: {status['proximity_override']}",
        f"recovery journal: {'present' if status['journal'] else 'none'}",
    ]
    if status["journal"]:
        journal = status["journal"]
        lines.append(
            "lease: "
            f"{journal.get('controller', 'unknown')} pid {journal.get('owner_pid', 'unknown')} "
            f"since {journal.get('started_at', 'unknown')}"
        )
    return "\n".join(lines)


def doctor_payload(client: AdbClient, serial: str) -> tuple[dict[str, Any], bool]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str, *, warning: bool = False) -> None:
        checks.append(
            {
                "name": name,
                "status": "warn" if warning and not ok else ("ok" if ok else "fail"),
                "detail": detail,
            }
        )

    version = client.run(["version"], check=False)
    add("adb", version.returncode == 0, client.adb)
    status = device_status(client, serial)
    add("authorization", True, f"{serial} is authorized")
    add(
        "quest identity",
        status["manufacturer"] != "unknown" and status["model"] != "unknown",
        f"{status['manufacturer']} {status['model']}",
    )
    add("boot", status["boot_completed"], status["state"])
    battery = status["battery"]
    level = battery.get("level")
    battery_ok = not isinstance(level, int) or level >= DEFAULT_MIN_BATTERY or battery.get(
        "powered"
    )
    add(
        "battery",
        battery_ok,
        f"{level if level is not None else 'unknown'}%; "
        + ("powered" if battery.get("powered") else "not charging"),
        warning=True,
    )
    proximity_ok = status["proximity_override"] in {"", "0"} or bool(status["journal"])
    add(
        "proximity",
        proximity_ok,
        f"debug.oculus.disableProximity={status['proximity_override']}",
        warning=True,
    )
    journal = status["journal"]
    if journal:
        active = journal_owner_active(journal)
        add(
            "recovery journal",
            active,
            (
                f"active lease owned by {journal.get('controller')} pid "
                f"{journal.get('owner_pid')}"
                if active
                else "stale or foreign lease; run quest recover after confirming no test is active"
            ),
            warning=active,
        )
    else:
        add("recovery journal", True, "none")
    failed = any(check["status"] == "fail" for check in checks)
    return {"serial": serial, "status": status, "checks": checks}, not failed


def print_doctor(payload: dict[str, Any]) -> None:
    for check in payload["checks"]:
        print(f"[{check['status']}] {check['name']}: {check['detail']}")


def common_doctor_document(
    payload: dict[str, Any] | None,
    ok: bool,
) -> dict[str, Any]:
    if payload is None:
        return {
            "schema": "machine-control-doctor/v0",
            "ready": False,
            "target": {
                "platform": "quest",
                "platformFamily": "android",
                "kind": "device",
                "deviceClass": "xr_headset",
                "profile": "quest-adb-device",
            },
            "states": {
                "power": "unknown",
                "connection": "unavailable",
                "boot": "unavailable",
                "administration": "unavailable",
                "interaction": "unknown",
                "runner": "unavailable",
                "semantic": "unavailable",
                "capture": "unavailable",
                "input": "unavailable",
                "outer": "unavailable",
            },
            "checks": [
                {
                    "id": "adb_target",
                    "status": "fail",
                    "summary": "the configured Quest ADB target is unavailable",
                }
            ],
            "lifecycleOperations": ["status", "doctor", "capabilities"],
            "extensions": {
                "routeClass": "host.device",
                "provider": "quest.adb",
            },
        }
    status = payload["status"]
    boot_ready = bool(status["boot_completed"])
    wake_state = status["state"]
    checks = []
    for item in payload["checks"]:
        state = {"ok": "pass", "warn": "warn", "fail": "fail"}[item["status"]]
        identifier = re.sub(r"[^a-z0-9]+", "_", item["name"].casefold()).strip("_")
        checks.append(
            {
                "id": identifier,
                "status": state,
                "summary": f"Quest {item['name']} check is {state}",
            }
        )
    return {
        "schema": "machine-control-doctor/v0",
        "ready": ok and boot_ready,
        "target": {
            "platform": "quest",
            "platformFamily": "android",
            "kind": "device",
            "deviceClass": "xr_headset",
            "profile": "quest-adb-device",
        },
        "states": {
            "power": "running",
            "connection": "ready",
            "boot": "ready" if boot_ready else "degraded",
            "administration": "ready" if boot_ready else "degraded",
            "interaction": "unknown",
            "runner": "unavailable",
            "semantic": "unavailable",
            "capture": "ready" if boot_ready else "unavailable",
            "input": "ready" if boot_ready else "unavailable",
            "outer": "ready",
        },
        "checks": checks,
        "lifecycleOperations": ["status", "doctor", "capabilities"],
        "extensions": {
            "routeClass": "host.device",
            "provider": "quest.adb",
            "wakeState": wake_state,
            "leaseState": "active" if status["journal"] else "none",
            "battery": {
                "level": status["battery"].get("level"),
                "powered": status["battery"].get("powered"),
            },
            "proximityOverride": status["proximity_override"] not in {"", "0"},
        },
    }


def resolve_serial(client: AdbClient) -> str:
    serial = client.select_quest()
    client.requested_serial = serial
    return serial


def command_session(client: AdbClient, serial: str, args: argparse.Namespace) -> int:
    command = list(args.command_argv)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        raise TestbedError("session requires a command after --")
    reverses = [normalize_reverse(value) for value in args.reverse]
    token = uuid.uuid4().hex
    lock = LocalLock(serial, token)
    lock.acquire()
    journal: dict[str, Any] | None = None
    cleanup_ok = True
    child_returncode = 1
    previous_handlers: dict[int, Any] = {}

    def interrupt_session(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    for signal_name in ("SIGTERM", "SIGHUP"):
        signum = getattr(signal, signal_name, None)
        if signum is not None:
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, interrupt_session)
    try:
        journal = begin_lease(
            client,
            serial,
            mode="session",
            owner_pid=os.getpid(),
            stop_packages=args.stop_package,
            reverses=reverses,
            min_battery=parse_min_battery(args.min_battery),
            sleep_on_end=not args.keep_awake,
            wake=not args.no_wake,
            disable_proximity=not args.no_proximity_disable,
            should_dismiss_dialogs=not args.no_dismiss_dialogs,
        )
        environment = os.environ.copy()
        environment["QUEST_TESTBED_SESSION_ACTIVE"] = "1"
        environment["QUEST_TESTBED_SERIAL"] = serial
        environment["ANDROID_SERIAL"] = serial
        environment["QUEST_TESTBED_ADB"] = client.adb
        print(f"Quest session started on {serial}: {' '.join(command)}")
        process = subprocess.Popen(command, env=environment)
        try:
            child_returncode = process.wait()
        except KeyboardInterrupt:
            try:
                child_returncode = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                child_returncode = 130
    finally:
        if journal is not None:
            cleanup_ok = restore_journal(
                client, serial, journal, keep_awake=args.keep_awake
            )
            if cleanup_ok:
                print(f"Quest session restored on {serial}.")
        lock.release()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    if not cleanup_ok and child_returncode == 0:
        return 1
    return child_returncode


def launch_app(client: AdbClient, serial: str, args: argparse.Namespace) -> int:
    if not args.component and not args.action and not args.data:
        result = client.shell(
            serial,
            [
                "monkey",
                "-p",
                args.package,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ],
            check=False,
            capture=False,
        )
        return result.returncode
    command = ["am", "start"]
    if args.wait:
        command.append("-W")
    if args.component:
        command.extend(["-n", args.component])
    if args.action:
        command.extend(["-a", args.action])
    if args.data:
        command.extend(["-d", args.data])
    for category in args.category:
        command.extend(["-c", category])
    for value in args.string_extra:
        if "=" not in value:
            raise TestbedError(f"string extra {value!r} must use KEY=VALUE")
        key, extra = value.split("=", 1)
        command.extend(["--es", key, extra])
    if args.package and not args.component:
        command.append(args.package)
    result = client.shell(serial, command, check=False, capture=False)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose and safely drive a physical Meta Quest over ADB."
    )
    parser.add_argument("--adb", metavar="PATH", help="explicit adb executable")
    parser.add_argument("--serial", help="explicit Quest ADB serial")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("serial", help="print the selected Quest serial")
    subparsers.add_parser("probe", help="print one stable headset state")
    status_parser = subparsers.add_parser("status", help="show read-only headset status")
    status_parser.add_argument("--json", action="store_true")
    doctor_parser = subparsers.add_parser("doctor", help="run read-only setup diagnostics")
    doctor_parser.add_argument("--json", action="store_true")
    subparsers.add_parser("wake", help="send the standard Android wake key")
    subparsers.add_parser("sleep", help="normalize proximity and put the headset to sleep")
    subparsers.add_parser(
        "dismiss-dialogs", help="dismiss known Meta system panels before a test"
    )

    def lifecycle_options(target: argparse.ArgumentParser) -> None:
        target.add_argument("--owner-pid", type=int)
        target.add_argument("--stop-package", action="append", default=[])
        target.add_argument("--reverse", action="append", default=[], metavar="LOCAL=REMOTE")
        target.add_argument("--min-battery", type=int)
        target.add_argument("--keep-awake", action="store_true")
        target.add_argument("--no-wake", action="store_true")
        target.add_argument("--no-proximity-disable", action="store_true")
        target.add_argument("--no-dismiss-dialogs", action="store_true")

    begin_parser = subparsers.add_parser(
        "begin", help="begin a recoverable lease for an external project script"
    )
    lifecycle_options(begin_parser)
    end_parser = subparsers.add_parser("end", help="restore and end this controller's lease")
    end_parser.add_argument("--keep-awake", action="store_true")
    recover_parser = subparsers.add_parser(
        "recover", help="restore an interrupted Quest lease"
    )
    recover_parser.add_argument("--force", action="store_true")
    recover_parser.add_argument("--keep-awake", action="store_true")

    session_parser = subparsers.add_parser(
        "session", help="run a command inside a transactional Quest lease"
    )
    lifecycle_options(session_parser)
    session_parser.add_argument("command_argv", nargs=argparse.REMAINDER)

    install_parser = subparsers.add_parser("install", help="install an already-built APK")
    install_parser.add_argument("apk")
    install_parser.add_argument("--no-replace", action="store_true")
    stop_parser = subparsers.add_parser("stop", help="force-stop an explicit package")
    stop_parser.add_argument("package")
    launch_parser = subparsers.add_parser("launch", help="launch an installed package")
    launch_parser.add_argument("package")
    launch_parser.add_argument("--component")
    launch_parser.add_argument("--action")
    launch_parser.add_argument("--data")
    launch_parser.add_argument("--category", action="append", default=[])
    launch_parser.add_argument("--string-extra", action="append", default=[])
    launch_parser.add_argument("--wait", action="store_true")
    screenshot_parser = subparsers.add_parser("screenshot", help="capture a PNG display image")
    screenshot_parser.add_argument("output")
    logcat_parser = subparsers.add_parser("logcat", help="save a bounded logcat snapshot")
    logcat_parser.add_argument("output")
    logcat_parser.add_argument("--package")
    logcat_parser.add_argument("--lines", type=int, default=400)
    push_parser = subparsers.add_parser("push", help="push a file or directory")
    push_parser.add_argument("local")
    push_parser.add_argument("remote")
    pull_parser = subparsers.add_parser("pull", help="pull a file or directory")
    pull_parser.add_argument("remote")
    pull_parser.add_argument("local", nargs="?")
    reverse_parser = subparsers.add_parser("reverse", help="install an ADB reverse mapping")
    reverse_parser.add_argument("local")
    reverse_parser.add_argument("remote")
    reverse_remove_parser = subparsers.add_parser(
        "reverse-remove", help="remove an ADB reverse mapping"
    )
    reverse_remove_parser.add_argument("local")
    shell_parser = subparsers.add_parser("shell", help="run a Quest shell command")
    shell_parser.add_argument("shell_argv", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        client = AdbClient(args.adb, args.serial)
        if args.command == "doctor" and args.json:
            try:
                serial = resolve_serial(client)
                payload, ok = doctor_payload(client, serial)
                document = common_doctor_document(payload, ok)
            except (OSError, subprocess.SubprocessError, TestbedError):
                document = common_doctor_document(None, False)
            print(json.dumps(document, indent=2))
            return 0 if document["ready"] else 1
        serial = resolve_serial(client)
        if args.command == "serial":
            print(serial)
            return 0
        if args.command == "probe":
            print(device_status(client, serial)["state"])
            return 0
        if args.command == "status":
            status = device_status(client, serial)
            print(json.dumps(status, indent=2) if args.json else status_text(status))
            return 0
        if args.command == "doctor":
            payload, ok = doctor_payload(client, serial)
            print_doctor(payload)
            return 0 if ok else 1
        if args.command == "wake":
            client.shell(serial, ["input", "keyevent", "KEYCODE_WAKEUP"])
            return 0
        if args.command == "sleep":
            client.shell(
                serial,
                ["setprop", "debug.oculus.disableProximity", "0"],
                check=False,
            )
            client.shell(
                serial,
                ["am", "broadcast", "-a", "com.oculus.vrpowermanager.prox_open"],
                check=False,
            )
            client.shell(serial, ["input", "keyevent", "KEYCODE_SLEEP"])
            return 0
        if args.command == "dismiss-dialogs":
            dismiss_dialogs(client, serial)
            return 0
        if args.command == "begin":
            owner_pid = args.owner_pid or os.getpid()
            mode = "external" if args.owner_pid else "detached"
            reverses = [normalize_reverse(value) for value in args.reverse]
            journal = begin_lease(
                client,
                serial,
                mode=mode,
                owner_pid=owner_pid,
                stop_packages=args.stop_package,
                reverses=reverses,
                min_battery=parse_min_battery(args.min_battery),
                sleep_on_end=not args.keep_awake,
                wake=not args.no_wake,
                disable_proximity=not args.no_proximity_disable,
                should_dismiss_dialogs=not args.no_dismiss_dialogs,
            )
            print(f"Quest lease started on {serial} ({journal['token']}).")
            return 0
        if args.command in {"end", "recover"}:
            journal = read_remote_journal(client, serial)
            if not journal:
                if args.command == "end":
                    print(f"No Quest lease is active on {serial}.")
                    return 0
                raise TestbedError("no Quest recovery journal is present")
            same_controller = journal.get("controller") == controller_name()
            if args.command == "end" and not same_controller:
                raise TestbedError(
                    f"lease belongs to {journal.get('controller')}; use recover --force "
                    "after confirming its test is no longer active"
                )
            if args.command == "recover" and journal_owner_active(journal) and not args.force:
                raise TestbedError(
                    f"lease owner pid {journal.get('owner_pid')} is still active; "
                    "use --force only after confirming it is safe"
                )
            if args.command == "recover" and not same_controller and not args.force:
                raise TestbedError(
                    f"lease belongs to {journal.get('controller')}; pass --force after "
                    "confirming it is stale"
                )
            if not restore_journal(client, serial, journal, keep_awake=args.keep_awake):
                raise TestbedError("Quest lease cleanup was incomplete")
            print(f"Quest lease restored on {serial}.")
            return 0
        if args.command == "session":
            return command_session(client, serial, args)
        if args.command == "install":
            apk = Path(args.apk).expanduser().resolve()
            if not apk.is_file():
                raise TestbedError(f"APK not found: {apk}")
            command = ["install"]
            if not args.no_replace:
                command.append("-r")
            command.append(str(apk))
            return client.run(command, serial=serial, check=False, capture=False).returncode
        if args.command == "stop":
            return client.shell(
                serial,
                ["am", "force-stop", args.package],
                check=False,
                capture=False,
            ).returncode
        if args.command == "launch":
            return launch_app(client, serial, args)
        if args.command == "screenshot":
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            result = client.run(
                ["exec-out", "screencap", "-p"],
                serial=serial,
                text=False,
            )
            output.write_bytes(result.stdout)
            if output.stat().st_size == 0:
                raise TestbedError(f"Quest screenshot was empty: {output}")
            print(output)
            return 0
        if args.command == "logcat":
            if args.lines <= 0:
                raise TestbedError("--lines must be positive")
            command = ["logcat", "-d"]
            if args.package:
                pid = client.shell_text(
                    serial, ["pidof", args.package], check=False
                ).split()
                if pid:
                    command.append(f"--pid={pid[0]}")
            command.extend(["-t", str(args.lines)])
            result = client.run(command, serial=serial, check=False)
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(result.stdout, encoding="utf-8")
            print(output)
            return result.returncode
        if args.command == "push":
            return client.run(
                ["push", args.local, args.remote],
                serial=serial,
                check=False,
                capture=False,
            ).returncode
        if args.command == "pull":
            command = ["pull", args.remote]
            if args.local:
                command.append(args.local)
            return client.run(
                command, serial=serial, check=False, capture=False
            ).returncode
        if args.command == "reverse":
            return client.run(
                ["reverse", args.local, args.remote],
                serial=serial,
                check=False,
                capture=False,
            ).returncode
        if args.command == "reverse-remove":
            return client.run(
                ["reverse", "--remove", args.local],
                serial=serial,
                check=False,
                capture=False,
            ).returncode
        if args.command == "shell":
            command = list(args.shell_argv)
            if command and command[0] == "--":
                command.pop(0)
            if command:
                return client.shell(
                    serial, command, check=False, capture=False
                ).returncode
            return subprocess.run([client.adb, "-s", serial, "shell"], check=False).returncode
    except TestbedError as error:
        if args.command == "doctor" and args.json:
            print(json.dumps(common_doctor_document(None, False), indent=2))
            return 1
        print(f"error: {error}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        if args.command == "doctor" and args.json:
            print(json.dumps(common_doctor_document(None, False), indent=2))
            return 1
        detail = ""
        if error.stderr:
            detail = str(error.stderr).strip()
        print(
            f"error: adb command failed with exit {error.returncode}"
            + (f": {detail}" if detail else ""),
            file=sys.stderr,
        )
        return error.returncode or 1
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
