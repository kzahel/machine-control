#!/usr/bin/env python3
"""Guarded physical Android-handheld control over ADB."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Sequence
import uuid
import zipfile


PLATFORM_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PLATFORM_ROOT.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from providers.adb import (  # noqa: E402
    AdbClient as SharedAdbClient,
    AdbDevice,
    AdbError,
    parse_battery,
    parse_wake_state,
)


PROFILE = "android-handheld-adb"
REMOTE_HELPER = "/data/local/tmp/machine-control-secret-input.jar"
HELPER_CLASS = "dev.machinecontrol.android.SecretInput"
MAX_PIN_BYTES = 16
EXCLUDED_FEATURES = (
    "oculus.hardware.standalone_vr",
    "android.hardware.type.television",
    "android.hardware.type.watch",
    "android.hardware.type.automotive",
)
PIN_SURFACE_PATTERNS = (
    r"resource-id=\"[^\"]*(?:pinEntry|pin_entry|keyguard_pin_view)[^\"]*\"",
    r"class=\"android\.widget\.EditText\"[^>]*password=\"true\"",
)


class TestbedError(RuntimeError):
    """Expected configuration, validation, or bounded-operation failure."""


@dataclass(frozen=True)
class Config:
    serial: str
    adb_path: str
    state_dir: Path
    sdk_root: Path | None


def state_root(values: dict[str, str]) -> Path:
    configured = values.get("ANDROID_TESTBED_STATE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt" and values.get("LOCALAPPDATA"):
        return Path(values["LOCALAPPDATA"]) / "android-device-testbed"
    if values.get("XDG_STATE_HOME"):
        return Path(values["XDG_STATE_HOME"]).expanduser() / "android-device-testbed"
    return Path.home() / ".local" / "state" / "android-device-testbed"


def load_config(values: dict[str, str] | None = None) -> Config:
    env = dict(os.environ if values is None else values)
    sdk_value = env.get("ANDROID_SDK_ROOT") or env.get("ANDROID_HOME")
    try:
        probe = SharedAdbClient(
            env.get("ANDROID_TESTBED_ADB") or None,
            serial=None,
            adb_environment_variable="ANDROID_TESTBED_ADB",
        )
    except AdbError as error:
        raise TestbedError(str(error)) from error
    return Config(
        serial=(env.get("ANDROID_TESTBED_SERIAL") or env.get("ANDROID_SERIAL") or "").strip(),
        adb_path=probe.adb,
        state_dir=state_root(env),
        sdk_root=Path(sdk_value).expanduser() if sdk_value else None,
    )


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextmanager
def mutation_lease(config: Config):
    config.state_dir.mkdir(parents=True, exist_ok=True)
    path = config.state_dir / "mutation.lock"
    token = uuid.uuid4().hex
    for attempt in range(2):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            try:
                owner = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                owner = {}
            try:
                owner_pid = int(owner.get("pid", 0))
            except (TypeError, ValueError):
                owner_pid = 0
            if attempt == 0 and not pid_is_alive(owner_pid):
                path.unlink(missing_ok=True)
                continue
            raise TestbedError("the Android handheld has an active local mutation lease")
    else:
        raise TestbedError("the Android mutation lease could not be acquired")
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"schema": 1, "pid": os.getpid(), "token": token}, handle)
        handle.write("\n")
    try:
        yield
    finally:
        try:
            owner = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            owner = {}
        if owner.get("token") == token:
            path.unlink(missing_ok=True)


class AndroidClient(SharedAdbClient):
    def __init__(self, config: Config) -> None:
        super().__init__(config.adb_path, serial=config.serial or None)

    def handheld_like(self, device: AdbDevice) -> bool:
        if device.serial.startswith("emulator-"):
            return False
        characteristics = self.shell_text(
            device.serial, ["getprop", "ro.build.characteristics"], check=False
        ).casefold()
        if any(
            value in characteristics
            for value in ("emulator", "tv", "watch", "automotive")
        ):
            return False
        features = self.shell_text(
            device.serial, ["pm", "list", "features"], check=False
        ).casefold()
        return (
            "android.hardware.touchscreen" in features
            and not any(feature in features for feature in EXCLUDED_FEATURES)
        )

    def select_handheld(self) -> str:
        devices = self.devices()
        by_serial = {device.serial: device for device in devices}
        if self.requested_serial:
            device = by_serial.get(self.requested_serial)
            if device is None:
                raise TestbedError("the configured Android handheld is not connected")
            require_authorized(device)
            if not self.handheld_like(device):
                raise TestbedError(
                    "the configured ADB target is not an eligible physical Android handheld"
                )
            return device.serial

        candidates = [
            device
            for device in devices
            if device.state == "device" and self.handheld_like(device)
        ]
        if len(candidates) == 1:
            return candidates[0].serial
        if len(candidates) > 1:
            raise TestbedError(
                "multiple Android handhelds are connected; set ANDROID_TESTBED_SERIAL"
            )
        if any(device.state == "unauthorized" for device in devices):
            raise TestbedError(
                "an attached Android target is unauthorized; approve this controller's "
                "ADB RSA key locally before retrying"
            )
        raise TestbedError("no attached authorized physical Android handheld was found")


def require_authorized(device: AdbDevice) -> None:
    if device.state == "unauthorized":
        raise TestbedError(
            "the configured Android handheld is unauthorized; approve this "
            "controller's ADB RSA key locally"
        )
    if device.state != "device":
        raise TestbedError(
            f"the configured Android handheld is in ADB state {device.state!r}"
        )


def parse_bool(value: str) -> bool | None:
    lowered = value.strip().casefold()
    if lowered in {"1", "true"}:
        return True
    if lowered in {"0", "false"}:
        return False
    return None


def parse_user_state(text: str, user_id: int) -> str:
    patterns = (
        rf"Started users state:.*\b{user_id}=([A-Z_]+)",
        rf"User #{user_id}:\s*state=([A-Z_]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "UNKNOWN"


def parse_credential_kind(text: str, user_id: int) -> str:
    section = re.search(
        rf"(?:^|\n)\s*User\s+{user_id}\s*\n(?P<body>.*?)(?=\n\s*User\s+\d+\s*\n|\Z)",
        text,
        re.DOTALL,
    )
    body = section.group("body") if section else text
    match = re.search(r"CredentialType:\s*([A-Za-z]+)", body)
    if not match:
        return "unknown"
    value = match.group(1).casefold()
    aliases = {"none": "none", "pin": "pin", "password": "password", "pattern": "pattern"}
    return aliases.get(value, "unknown")


def parse_device_locked(text: str, user_id: int) -> bool | None:
    match = re.search(
        rf"\(id={user_id},[^\n]*\bdeviceLocked=(true|false|1|0)\b",
        text,
        re.IGNORECASE,
    )
    return parse_bool(match.group(1)) if match else None


def parse_keyguard_showing(text: str) -> bool | None:
    matches = re.findall(r"\bshowing=(true|false)\b", text, re.IGNORECASE)
    if matches:
        values = [parse_bool(value) for value in matches]
        return True if True in values else False
    match = re.search(r"\bisStatusBarKeyguard=(true|false)\b", text, re.IGNORECASE)
    return parse_bool(match.group(1)) if match else None


def parse_maximum_failed_passwords(text: str) -> int | None:
    values = [
        int(value)
        for value in re.findall(r"maximumFailedPasswordsForWipe=(\d+)", text)
    ]
    positive = [value for value in values if value > 0]
    if positive:
        return min(positive)
    return 0 if values else None


def interaction_state(status: dict[str, Any]) -> str:
    keyguard = status["keyguard"]
    if keyguard["showing"] is True or keyguard["deviceLocked"] is True:
        return "protected" if keyguard["secure"] is True else "locked"
    if keyguard["showing"] is False and keyguard["deviceLocked"] is False:
        return "unlocked"
    return "unknown"


def generation(serial: str, boot_id: str, user_id: int) -> str:
    digest = hashlib.sha256(
        f"{serial}\0{boot_id}\0{user_id}".encode("utf-8")
    ).hexdigest()[:20]
    return f"android-{digest}"


def device_status(client: AndroidClient, serial: str) -> dict[str, Any]:
    getprop = lambda name: client.shell_text(
        serial, ["getprop", name], check=False
    )
    boot_completed = getprop("sys.boot_completed") == "1"
    user_text = client.shell_text(serial, ["am", "get-current-user"], check=False)
    current_user = int(user_text) if user_text.isdecimal() else 0
    activity = client.shell_text(serial, ["dumpsys", "activity"], check=False)
    user_state = parse_user_state(activity, current_user)
    trust = client.shell_text(serial, ["dumpsys", "trust"], check=False)
    policy = client.shell_text(serial, ["dumpsys", "window", "policy"], check=False)
    lock_settings = client.shell_text(
        serial, ["dumpsys", "lock_settings"], check=False
    )
    credential_kind = parse_credential_kind(lock_settings, current_user)
    showing = parse_keyguard_showing(policy)
    locked = parse_device_locked(trust, current_user)
    secure = credential_kind not in {"none", "unknown"}
    boot_id = client.shell_text(
        serial, ["cat", "/proc/sys/kernel/random/boot_id"], check=False
    )
    status = {
        "bootCompleted": boot_completed,
        "bootGeneration": generation(serial, boot_id, current_user),
        "wakeState": parse_wake_state(
            client.shell_text(serial, ["dumpsys", "power"], check=False)
        ),
        "userState": user_state,
        "userUnlocked": user_state == "RUNNING_UNLOCKED",
        "apiLevel": getprop("ro.build.version.sdk") or "unknown",
        "battery": parse_battery(
            client.shell_text(serial, ["dumpsys", "battery"], check=False)
        ),
        "keyguard": {
            "showing": showing,
            "deviceLocked": locked,
            "secure": secure,
            "credentialKind": credential_kind,
        },
        "maximumFailedPasswordsForWipe": parse_maximum_failed_passwords(
            client.shell_text(serial, ["dumpsys", "device_policy"], check=False)
        ),
    }
    status["interaction"] = interaction_state(status)
    return status


def check(identifier: str, status: str, summary: str) -> dict[str, str]:
    return {"id": identifier, "status": status, "summary": summary}


def unavailable_doctor(_message: str) -> dict[str, Any]:
    return {
        "schema": "machine-control-doctor/v0",
        "ready": False,
        "target": {
            "platform": "android",
            "platformFamily": "android",
            "kind": "device",
            "deviceClass": "handheld",
            "profile": PROFILE,
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
            check(
                "adb_target",
                "fail",
                "the configured Android ADB target is unavailable",
            )
        ],
        "lifecycleOperations": ["status", "doctor", "capabilities"],
        "extensions": {
            "routeClass": "host.device",
            "provider": "android.adb",
            "generation": status["bootGeneration"],
        },
    }


def doctor_document(config: Config) -> dict[str, Any]:
    try:
        client = AndroidClient(config)
        serial = client.select_handheld()
        status = device_status(client, serial)
    except (AdbError, OSError, subprocess.SubprocessError, TestbedError) as error:
        return unavailable_doctor(str(error))
    boot_ready = status["bootCompleted"]
    interaction = status["interaction"]
    input_ready = boot_ready and status["wakeState"] != "unknown"
    ready = boot_ready and status["userUnlocked"] and interaction == "unlocked"
    return {
        "schema": "machine-control-doctor/v0",
        "ready": ready,
        "target": {
            "platform": "android",
            "platformFamily": "android",
            "kind": "device",
            "deviceClass": "handheld",
            "profile": PROFILE,
        },
        "states": {
            "power": "running",
            "connection": "ready",
            "boot": "ready" if boot_ready else "degraded",
            "administration": "ready" if boot_ready else "degraded",
            "interaction": interaction,
            "runner": "unavailable",
            "semantic": "degraded" if boot_ready else "unavailable",
            "capture": "ready" if boot_ready else "unavailable",
            "input": "ready" if input_ready else "degraded",
            "outer": "ready",
        },
        "checks": [
            check("adb_target", "pass", "one authorized physical Android handheld selected"),
            check("boot", "pass" if boot_ready else "warn", "Android boot completion observed"),
            check(
                "interaction",
                "pass" if interaction == "unlocked" else "warn",
                f"Android interaction state is {interaction}",
            ),
            check(
                "user_storage",
                "pass" if status["userUnlocked"] else "warn",
                "credential-encrypted user storage is unlocked"
                if status["userUnlocked"]
                else "credential-encrypted user storage is locked",
            ),
        ],
        "lifecycleOperations": ["status", "doctor", "capabilities", "reboot"],
        "extensions": {
            "routeClass": "host.device",
            "provider": "android.adb",
            "apiLevel": status["apiLevel"],
            "wakeState": status["wakeState"],
            "userStorage": "unlocked" if status["userUnlocked"] else "locked",
            "keyguard": status["keyguard"],
            "maximumFailedPasswordsForWipe": status[
                "maximumFailedPasswordsForWipe"
            ],
        },
    }


def print_doctor(config: Config, json_output: bool) -> int:
    document = doctor_document(config)
    if json_output:
        print(json.dumps(document, indent=2))
    else:
        for item in document["checks"]:
            print(f"[{item['status']}] {item['id']}: {item['summary']}")
        print("doctor: ready" if document["ready"] else "doctor: attention required")
    return 0 if document["ready"] else 1


def status_payload(config: Config) -> dict[str, Any]:
    client = AndroidClient(config)
    serial = client.select_handheld()
    status = device_status(client, serial)
    return {
        "id": "android",
        "state": "ready" if status["bootCompleted"] else "booting",
        "available": True,
        "ready": status["interaction"] == "unlocked" and status["userUnlocked"],
        "bootCompleted": status["bootCompleted"],
        "wakeState": status["wakeState"],
        "interaction": status["interaction"],
        "userStorage": "unlocked" if status["userUnlocked"] else "locked",
        "credentialKind": status["keyguard"]["credentialKind"],
        "apiLevel": status["apiLevel"],
    }


def pin_surface_visible(client: AndroidClient, serial: str) -> bool:
    result = client.shell(
        serial, ["uiautomator", "dump", "/dev/tty"], check=False, timeout=15
    )
    xml = result.stdout
    return result.returncode == 0 and any(
        re.search(pattern, xml, re.IGNORECASE) for pattern in PIN_SURFACE_PATTERNS
    )


def find_sdk_root(config: Config) -> Path:
    candidates = [
        config.sdk_root,
        Path.home() / "Android" / "Sdk",
        Path.home() / "Library" / "Android" / "sdk",
    ]
    for candidate in candidates:
        if candidate and (candidate / "platforms").is_dir():
            return candidate
    raise TestbedError(
        "Android SDK platforms were not found; set ANDROID_SDK_ROOT before unlock"
    )


def version_key(path: Path) -> tuple[int, ...]:
    values = re.findall(r"\d+", path.name)
    return tuple(int(value) for value in values) or (0,)


def helper_toolchain(config: Config) -> tuple[Path, Path, Path]:
    sdk = find_sdk_root(config)
    jars = sorted((sdk / "platforms").glob("android-*/android.jar"), key=lambda p: version_key(p.parent))
    d8s = sorted((sdk / "build-tools").glob("*/d8*"), key=lambda p: version_key(p.parent))
    javac = shutil.which("javac")
    if not jars or not d8s or not javac:
        raise TestbedError(
            "unlock requires javac plus Android SDK platform and d8 build tools"
        )
    return Path(javac), jars[-1], d8s[-1]


def build_secret_helper(config: Config) -> Path:
    source = (
        PLATFORM_ROOT
        / "helper"
        / "src"
        / "dev"
        / "machinecontrol"
        / "android"
        / "SecretInput.java"
    )
    source_bytes = source.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()[:16]
    destination = config.state_dir / "helper" / digest / "secret-input.jar"
    if destination.is_file():
        return destination
    javac, android_jar, d8 = helper_toolchain(config)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="android-secret-helper-") as temporary:
        root = Path(temporary)
        classes = root / "classes"
        dex = root / "dex"
        classes.mkdir()
        dex.mkdir()
        subprocess.run(
            [
                str(javac),
                "-source",
                "8",
                "-target",
                "8",
                "-classpath",
                str(android_jar),
                "-d",
                str(classes),
                str(source),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        class_file = classes / "dev" / "machinecontrol" / "android" / "SecretInput.class"
        subprocess.run(
            [
                str(d8),
                "--min-api",
                "26",
                "--lib",
                str(android_jar),
                "--output",
                str(dex),
                str(class_file),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        temporary_jar = root / "secret-input.jar"
        with zipfile.ZipFile(temporary_jar, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(dex / "classes.dex", "classes.dex")
        os.replace(temporary_jar, destination)
        if os.name != "nt":
            destination.chmod(0o600)
    return destination


def stage_secret_helper(client: AndroidClient, serial: str, helper: Path) -> None:
    client.run(["push", str(helper), REMOTE_HELPER], serial=serial)
    client.shell(serial, ["chmod", "600", REMOTE_HELPER])


def read_pin() -> bytearray:
    if sys.stdin.isatty():
        value = getpass.getpass("Android PIN: ").encode("utf-8")
    else:
        value = sys.stdin.buffer.read(MAX_PIN_BYTES + 2).rstrip(b"\r\n")
    pin = bytearray(value)
    if not 4 <= len(pin) <= MAX_PIN_BYTES or any(
        value < ord("0") or value > ord("9") for value in pin
    ):
        pin[:] = b"\0" * len(pin)
        raise TestbedError("PIN must contain 4 to 16 ASCII digits")
    return pin


def deliver_pin(
    client: AndroidClient, serial: str, pin: bytearray
) -> subprocess.CompletedProcess[Any]:
    return client.run(
        [
            "shell",
            f"CLASSPATH={REMOTE_HELPER}",
            "app_process",
            "/system/bin",
            HELPER_CLASS,
        ],
        serial=serial,
        check=False,
        text=False,
        input_data=bytes(pin),
        timeout=20,
    )


def result_document(
    *,
    accepted: bool,
    delivery: str,
    effect: str,
    generation_value: str,
    error_code: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "machine-control/v0",
        "requestId": str(uuid.uuid4()),
        "operation": "session.unlock",
        "accepted": accepted,
        "actualRoute": (
            "host.device/android.adb+app_process_secret_input"
            if delivery in {"confirmed", "unknown"}
            else "host.device/android.adb.keyguard_observation"
        ),
        "generation": generation_value or "android-unknown",
        "delivery": delivery,
        "effect": effect,
        "hostInterference": "none",
        "uncertainty": "none" if delivery != "unknown" else "delivery_may_be_partial",
        "retrySafety": "never_retry_credential_without_fresh_observation",
        "retryCount": 0,
        "data": {"credentialKind": "pin", "attempts": 1 if delivery != "refused" else 0},
        "elapsedMs": 0,
    }
    if error_code:
        result["errorCode"] = error_code
    if message:
        result["message"] = message
    return result


def unlock_pin(
    config: Config,
    *,
    secret_reader: Callable[[], bytearray] = read_pin,
    helper_builder: Callable[[Config], Path] = build_secret_helper,
    deliverer: Callable[[AndroidClient, str, bytearray], subprocess.CompletedProcess[Any]] = deliver_pin,
) -> dict[str, Any]:
    with mutation_lease(config):
        return _unlock_pin_impl(
            config,
            secret_reader=secret_reader,
            helper_builder=helper_builder,
            deliverer=deliverer,
        )


def _unlock_pin_impl(
    config: Config,
    *,
    secret_reader: Callable[[], bytearray],
    helper_builder: Callable[[Config], Path],
    deliverer: Callable[[AndroidClient, str, bytearray], subprocess.CompletedProcess[Any]],
) -> dict[str, Any]:
    started = time.monotonic()
    client = AndroidClient(config)
    serial = client.select_handheld()
    before = device_status(client, serial)
    generation_value = before["bootGeneration"]
    if not before["bootCompleted"]:
        return result_document(
            accepted=False,
            delivery="refused",
            effect="refused",
            generation_value=generation_value,
            error_code="boot_incomplete",
            message="Android has not completed boot",
        )
    if before["interaction"] == "unlocked" and before["userUnlocked"]:
        result = result_document(
            accepted=True,
            delivery="not_applicable",
            effect="confirmed",
            generation_value=generation_value,
            message="Android was already unlocked",
        )
        result["data"]["attempts"] = 0
        result["elapsedMs"] = int((time.monotonic() - started) * 1000)
        return result
    keyguard = before["keyguard"]
    if not keyguard["secure"] or keyguard["credentialKind"] != "pin":
        return result_document(
            accepted=False,
            delivery="refused",
            effect="refused",
            generation_value=generation_value,
            error_code="unsupported_credential_surface",
            message="The active Android keyguard is not a secure PIN surface",
        )
    wipe_limit = before["maximumFailedPasswordsForWipe"]
    if wipe_limit is None or wipe_limit != 0:
        return result_document(
            accepted=False,
            delivery="refused",
            effect="refused",
            generation_value=generation_value,
            error_code="wipe_policy_not_safe",
            message="A zero failed-password wipe threshold was not established",
        )
    client.shell(serial, ["input", "keyevent", "KEYCODE_WAKEUP"], check=False)
    client.shell(serial, ["cmd", "window", "dismiss-keyguard"], check=False)
    time.sleep(0.5)
    if not pin_surface_visible(client, serial):
        return result_document(
            accepted=False,
            delivery="refused",
            effect="refused",
            generation_value=generation_value,
            error_code="credential_field_unavailable",
            message="The Android PIN field was not discovered",
        )
    helper = helper_builder(config)
    stage_secret_helper(client, serial, helper)
    staged = device_status(client, serial)
    if staged["bootGeneration"] != generation_value or staged["interaction"] == "unlocked":
        client.shell(serial, ["rm", "-f", REMOTE_HELPER], check=False)
        return result_document(
            accepted=False,
            delivery="refused",
            effect="refused",
            generation_value=staged["bootGeneration"],
            error_code="target_generation_changed",
            message="Android state changed before the secret channel opened",
        )

    pin: bytearray | None = None
    completed: subprocess.CompletedProcess[Any] | None = None
    delivery_failed = False
    try:
        try:
            pin = secret_reader()
        except TestbedError:
            result = result_document(
                accepted=False,
                delivery="refused",
                effect="refused",
                generation_value=generation_value,
                error_code="invalid_credential_input",
                message="The dedicated PIN input was invalid",
            )
            result["elapsedMs"] = int((time.monotonic() - started) * 1000)
            return result
        try:
            completed = deliverer(client, serial, pin)
        except (OSError, subprocess.SubprocessError):
            delivery_failed = True
    finally:
        if pin is not None:
            pin[:] = b"\0" * len(pin)
        client.shell(serial, ["rm", "-f", REMOTE_HELPER], check=False)
    time.sleep(0.5)
    try:
        after = device_status(client, serial)
    except (OSError, subprocess.SubprocessError, TestbedError):
        result = result_document(
            accepted=True,
            delivery="unknown" if delivery_failed or completed is None else "confirmed",
            effect="unknown",
            generation_value=generation_value,
            error_code="postcondition_unavailable",
            message="Android state could not be observed after PIN delivery",
        )
        result["elapsedMs"] = int((time.monotonic() - started) * 1000)
        return result
    effect = (
        "confirmed"
        if after["interaction"] == "unlocked" and after["userUnlocked"]
        else "no_effect"
    )
    delivery = (
        "confirmed"
        if not delivery_failed and completed and completed.returncode == 0
        else "unknown"
    )
    result = result_document(
        accepted=True,
        delivery=delivery,
        effect=effect,
        generation_value=after["bootGeneration"],
        error_code=None if effect == "confirmed" else "unlock_not_observed",
        message=None if effect == "confirmed" else "PIN delivery did not produce an observed unlock",
    )
    result["evidence"] = {
        "kind": "android_keyguard_and_user_storage",
        "interaction": after["interaction"],
        "userStorage": "unlocked" if after["userUnlocked"] else "locked",
    }
    result["elapsedMs"] = int((time.monotonic() - started) * 1000)
    return result


def reboot_device(client: AndroidClient, serial: str, timeout: int) -> None:
    before = device_status(client, serial)["bootGeneration"]
    client.run(["reboot"], serial=serial)
    client.run(["wait-for-device"], serial=serial, timeout=timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.shell_text(
            serial, ["getprop", "sys.boot_completed"], check=False
        ) == "1":
            after = device_status(client, serial)["bootGeneration"]
            if after != before:
                return
        time.sleep(1)
    raise TestbedError("Android did not complete a new boot before timeout")


def screenshot(client: AndroidClient, serial: str, output: str) -> None:
    path = Path(output).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    result = client.run(
        ["exec-out", "screencap", "-p"], serial=serial, text=False
    )
    path.write_bytes(result.stdout)
    print(path)


def save_logcat(client: AndroidClient, serial: str, output: str) -> None:
    path = Path(output).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    result = client.run(
        ["logcat", "-d", "-t", "2000"], serial=serial, text=True
    )
    path.write_text(result.stdout, encoding="utf-8")
    print(path)


def launch_package(client: AndroidClient, serial: str, package: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.]+", package):
        raise TestbedError("launch requires an exact Android package name")
    resolved = client.shell_text(
        serial, ["cmd", "package", "resolve-activity", "--brief", package], check=False
    )
    component = next(
        (line.strip() for line in reversed(resolved.splitlines()) if "/" in line),
        "",
    )
    if not component:
        raise TestbedError("the requested package has no launchable activity")
    client.shell(serial, ["am", "start", "-n", component])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="android-device",
        description="Guarded control of an authorized physical Android handheld.",
    )
    parser.add_argument("--serial")
    parser.add_argument("--adb")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("probe", "status", "doctor"):
        target = subparsers.add_parser(name)
        target.add_argument("--json", action="store_true")
    subparsers.add_parser("serial")
    subparsers.add_parser("wake")
    subparsers.add_parser("dismiss-keyguard")
    unlock = subparsers.add_parser("unlock")
    unlock.add_argument("--json", action="store_true")
    reboot = subparsers.add_parser("reboot")
    reboot.add_argument("--timeout", type=int, default=180)
    install = subparsers.add_parser("install")
    install.add_argument("apk")
    launch = subparsers.add_parser("launch")
    launch.add_argument("package")
    stop = subparsers.add_parser("stop")
    stop.add_argument("package")
    capture = subparsers.add_parser("screenshot")
    capture.add_argument("output")
    logs = subparsers.add_parser("logcat")
    logs.add_argument("output")
    shell = subparsers.add_parser("shell")
    shell.add_argument("shell_args", nargs=argparse.REMAINDER)
    return parser


def config_from_args(args: argparse.Namespace) -> Config:
    values = dict(os.environ)
    if args.serial:
        values["ANDROID_TESTBED_SERIAL"] = args.serial
    if args.adb:
        values["ANDROID_TESTBED_ADB"] = args.adb
    return load_config(values)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = config_from_args(args)
        if args.command == "doctor":
            return print_doctor(config, args.json)
        if args.command == "unlock":
            result = unlock_pin(config)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(result.get("message") or f"unlock effect: {result['effect']}")
            return 0 if result["effect"] == "confirmed" else 1
        client = AndroidClient(config)
        serial = client.select_handheld()
        if args.command == "serial":
            print(serial)
        elif args.command == "probe":
            payload = status_payload(config)
            print(json.dumps(payload, indent=2) if args.json else payload["state"])
            return 0 if payload["available"] else 1
        elif args.command == "status":
            payload = status_payload(config)
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                for key, value in payload.items():
                    if key != "id":
                        print(f"{key}: {value}")
            return 0 if payload["available"] else 1
        elif args.command == "wake":
            client.shell(serial, ["input", "keyevent", "KEYCODE_WAKEUP"])
        elif args.command == "dismiss-keyguard":
            client.shell(serial, ["cmd", "window", "dismiss-keyguard"])
        elif args.command == "reboot":
            with mutation_lease(config):
                reboot_device(client, serial, args.timeout)
            print("running")
        elif args.command == "install":
            path = Path(args.apk).expanduser().resolve()
            if not path.is_file() or path.suffix.casefold() != ".apk":
                raise TestbedError("install requires an existing APK file")
            client.run(["install", "-r", str(path)], serial=serial)
        elif args.command == "launch":
            launch_package(client, serial, args.package)
        elif args.command == "stop":
            if not re.fullmatch(r"[A-Za-z0-9_.]+", args.package):
                raise TestbedError("stop requires an exact Android package name")
            client.shell(serial, ["am", "force-stop", args.package])
        elif args.command == "screenshot":
            screenshot(client, serial, args.output)
        elif args.command == "logcat":
            save_logcat(client, serial, args.output)
        elif args.command == "shell":
            values = list(args.shell_args)
            if values and values[0] == "--":
                values.pop(0)
            if not values:
                raise TestbedError("shell requires an explicit command")
            return client.shell(serial, values, capture=False).returncode
        return 0
    except (AdbError, OSError, subprocess.SubprocessError, TestbedError) as error:
        if args.command == "doctor" and args.json:
            print(json.dumps(unavailable_doctor(str(error)), indent=2))
            return 1
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
