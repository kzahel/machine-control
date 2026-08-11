#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import plistlib
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

LEASE_SCHEMA = 1
PINNED_AGENT_DEVICE_VERSION = "0.20.5"
SIGNING_PROFILES = {"unspecified", "developer_program", "personal_team"}
PERSONAL_TEAM_REFRESH_SECONDS = 2 * 24 * 60 * 60
REPO_ROOT = Path(os.environ.get("IOS_DEVICE_TESTBED_ROOT", Path(__file__).parent))
IDENTIFIER_PATTERNS = (
    re.compile(r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f-]{15,}\b"),
    re.compile(r"\b[0-9A-Fa-f]{24,}\b"),
)
DEVICE_IDENTIFIER = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f-]{8,}$")


class TestbedError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    device_selector: str
    team_id: str
    runner_bundle_id: str
    state_dir: Path
    agent_device: Path
    signing_identity: str
    signing_profile: str = "unspecified"

    @property
    def agent_state_dir(self) -> Path:
        return self.state_dir / "agent-device"

    @property
    def lease_path(self) -> Path:
        return self.state_dir / "lease.json"


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    fix: str | None = None


@dataclass(frozen=True)
class Lease:
    token: str
    owner_pid: int
    controller: str
    mode: str
    session_name: str
    created_at: str


def load_config(env: dict[str, str] | None = None) -> Config:
    values = os.environ if env is None else env
    state_dir = Path(
        values.get(
            "IOS_DEVICE_TESTBED_STATE_DIR",
            str(Path.home() / ".ios-device-testbed"),
        )
    ).expanduser()
    configured_agent = values.get("IOS_DEVICE_TESTBED_AGENT_DEVICE", "").strip()
    agent_device = (
        Path(configured_agent).expanduser()
        if configured_agent
        else REPO_ROOT / "node_modules" / ".bin" / "agent-device"
    )
    signing_profile = values.get(
        "IOS_DEVICE_TESTBED_SIGNING_PROFILE", "unspecified"
    ).strip()
    if signing_profile not in SIGNING_PROFILES:
        raise TestbedError(
            "IOS_DEVICE_TESTBED_SIGNING_PROFILE must be unspecified, "
            "developer_program, or personal_team"
        )
    return Config(
        device_selector=values.get("IOS_DEVICE_TESTBED_DEVICE", "").strip(),
        team_id=values.get("IOS_DEVICE_TESTBED_TEAM_ID", "").strip(),
        runner_bundle_id=values.get(
            "IOS_DEVICE_TESTBED_RUNNER_BUNDLE_ID", ""
        ).strip(),
        state_dir=state_dir,
        agent_device=agent_device,
        signing_identity=values.get(
            "IOS_DEVICE_TESTBED_SIGNING_IDENTITY", "Apple Development"
        ).strip(),
        signing_profile=signing_profile,
    )


def redact(text: str) -> str:
    for pattern in IDENTIFIER_PATTERNS:
        text = pattern.sub("<identifier>", text)
    return text


def redact_config(text: str, config: Config) -> str:
    value = redact(text)
    private_values = {
        config.device_selector,
        config.team_id,
        config.runner_bundle_id,
        str(config.state_dir),
        str(config.agent_device),
        str(Path.home()),
    }
    for private in sorted(private_values, key=len, reverse=True):
        if private:
            value = value.replace(private, "<private>")
    return value


def run_capture(
    argv: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(argv),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise TestbedError(
            redact(detail or f"command exited with status {result.returncode}")
        )
    return result


def devicectl_json(args: Sequence[str]) -> dict[str, object]:
    if shutil.which("xcrun") is None:
        raise TestbedError("xcrun was not found; install full Xcode")
    descriptor, path_string = tempfile.mkstemp(
        prefix="ios-device-testbed-", suffix=".json"
    )
    os.close(descriptor)
    output_path = Path(path_string)
    try:
        run_capture(
            ["xcrun", "devicectl", *args, "--json-output", str(output_path)]
        )
        with output_path.open(encoding="utf-8") as handle:
            parsed = json.load(handle)
        if not isinstance(parsed, dict):
            raise TestbedError("devicectl returned an invalid JSON document")
        return parsed
    finally:
        output_path.unlink(missing_ok=True)


def listed_devices(document: dict[str, object]) -> list[dict[str, object]]:
    result = document.get("result")
    if not isinstance(result, dict):
        raise TestbedError("devicectl JSON did not contain a result object")
    devices = result.get("devices")
    if not isinstance(devices, list):
        raise TestbedError("devicectl JSON did not contain a device list")
    return [device for device in devices if isinstance(device, dict)]


def developer_mode_device_identifiers() -> list[str]:
    """Return physical-device identifiers visible to Apple's bootstrap tool."""
    result = run_capture(["xcrun", "devmodectl", "list"], check=False)
    if result.returncode:
        return []
    identifiers: list[str] = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields and DEVICE_IDENTIFIER.fullmatch(fields[0]):
            identifiers.append(fields[0])
    return identifiers


def device_details(reference: str) -> dict[str, object] | None:
    try:
        document = devicectl_json(
            ["device", "info", "details", "--device", reference]
        )
    except TestbedError:
        return None
    result = document.get("result")
    return result if isinstance(result, dict) else None


def device_identifier(device: dict[str, object]) -> str:
    return nested_string(device, "hardwareProperties", "udid") or nested_string(
        device, "identifier"
    )


def device_references(device: dict[str, object]) -> set[str]:
    return {
        value
        for value in (
            nested_string(device, "identifier"),
            nested_string(device, "hardwareProperties", "udid"),
        )
        if value
    }


def discoverable_devices() -> list[dict[str, object]]:
    """Merge normal CoreDevice inventory with pre-convergence developer devices."""
    devices = listed_devices(devicectl_json(["list", "devices"]))
    seen = {
        reference
        for device in devices
        for reference in device_references(device)
    }
    for reference in developer_mode_device_identifiers():
        if reference in seen:
            for index, existing in enumerate(devices):
                if reference not in device_references(existing):
                    continue
                if bool(device_summary(existing)["available"]):
                    break
                details = device_details(reference)
                if details is not None:
                    devices[index] = details
                    seen.update(device_references(details))
                break
            continue
        details = device_details(reference)
        if details is None:
            continue
        references = device_references(details)
        if references & seen:
            seen.update(references)
            continue
        devices.append(details)
        seen.update(references)
    return devices


def nested_string(value: object, *path: str) -> str:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current.strip() if isinstance(current, str) else ""


def physical_ios_devices(devices: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for device in devices:
        reality = nested_string(device, "hardwareProperties", "reality")
        target_platform = nested_string(device, "hardwareProperties", "platform")
        if reality.casefold() != "physical":
            continue
        if target_platform.casefold() not in {"ios", "iphoneos"}:
            continue
        selected.append(device)
    return selected


def select_device(
    devices: Iterable[dict[str, object]], selector: str = ""
) -> dict[str, object]:
    candidates = physical_ios_devices(devices)
    if selector:
        matches = []
        for device in candidates:
            values = {
                nested_string(device, "deviceProperties", "name"),
                nested_string(device, "identifier"),
                nested_string(device, "hardwareProperties", "udid"),
            }
            if selector in values:
                matches.append(device)
        if not matches:
            raise TestbedError(
                f"configured iOS device {selector!r} is not connected"
            )
        if len(matches) > 1:
            raise TestbedError(
                f"configured iOS device name {selector!r} is ambiguous; rename one "
                "device or use a private local identifier"
            )
        return matches[0]
    if not candidates:
        raise TestbedError("no physical iOS device is connected")
    if len(candidates) > 1:
        names = sorted(
            nested_string(device, "deviceProperties", "name") or "unnamed"
            for device in candidates
        )
        raise TestbedError(
            "multiple physical iOS devices are connected; set "
            f"IOS_DEVICE_TESTBED_DEVICE in config.local ({', '.join(names)})"
        )
    return candidates[0]


def discover_selected_device(config: Config) -> dict[str, object]:
    return select_device(discoverable_devices(), config.device_selector)


def discover_listed_device(config: Config) -> dict[str, object]:
    """Select only from the converged CoreDevice inventory."""
    return select_device(
        listed_devices(devicectl_json(["list", "devices"])),
        config.device_selector,
    )


def device_summary(device: dict[str, object]) -> dict[str, object]:
    pairing = nested_string(device, "connectionProperties", "pairingState")
    tunnel = nested_string(device, "connectionProperties", "tunnelState")
    transport = nested_string(device, "connectionProperties", "transportType")
    connected = pairing.casefold() == "paired" and (
        tunnel.casefold() == "connected" or transport.casefold() == "wired"
    )
    state = "connected" if connected else "disconnected"
    return {
        "name": nested_string(device, "deviceProperties", "name") or "iPhone",
        "model": nested_string(device, "hardwareProperties", "marketingName"),
        "osVersion": nested_string(device, "deviceProperties", "osVersionNumber"),
        "developerMode": nested_string(
            device, "deviceProperties", "developerModeStatus"
        ),
        "pairing": pairing,
        "transport": transport,
        "tunnel": tunnel,
        "state": state,
        "available": connected,
        "ready": connected,
    }


def selected_device_name(config: Config) -> str:
    device = discover_selected_device(config)
    name = nested_string(device, "deviceProperties", "name")
    if not name:
        raise TestbedError("selected iOS device has no usable name")
    return name


def probe(config: Config, *, json_output: bool = False) -> int:
    try:
        summary = device_summary(discover_selected_device(config))
    except TestbedError as error:
        if json_output:
            print(
                json.dumps(
                    {
                        "id": "ios",
                        "state": "disconnected",
                        "available": False,
                        "ready": False,
                        "error": redact(str(error)),
                    },
                    indent=2,
                )
            )
        else:
            print("disconnected")
        return 1
    if json_output:
        print(json.dumps({"id": "ios", **summary}, indent=2))
    else:
        print(summary["state"])
    return 0 if summary["available"] else 1


def runner_cache_root() -> Path:
    # Agent Device 0.20.5 isolates daemon/session state with AGENT_DEVICE_STATE_DIR
    # but intentionally retains Apple build products in its user-wide cache.
    return Path.home() / ".agent-device" / "apple-runner" / "derived" / "ios-device"


def matching_runner_cache_directories(config: Config) -> list[Path]:
    derived = runner_cache_root()
    if not derived.is_dir() or not config.team_id or not config.runner_bundle_id:
        return []
    expected_settings = {
        f"AGENT_DEVICE_IOS_RUNNER_APP_BUNDLE_ID={config.runner_bundle_id}",
        f"AGENT_DEVICE_IOS_RUNNER_TEST_BUNDLE_ID={config.runner_bundle_id}.uitests",
        "CODE_SIGN_STYLE=Automatic",
        f"DEVELOPMENT_TEAM={config.team_id}",
    }
    matches: list[Path] = []
    for manifest_path in derived.glob("*/.agent-device-runner-cache.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            settings = {
                *manifest.get("runnerBundleBuildSettings", []),
                *manifest.get("runnerSigningBuildSettings", []),
            }
        except (OSError, TypeError, json.JSONDecodeError):
            continue
        if (
            manifest.get("packageVersion") == PINNED_AGENT_DEVICE_VERSION
            and expected_settings <= settings
            and any(manifest_path.parent.rglob("*.xctestrun"))
        ):
            matches.append(manifest_path.parent)
    return matches


def provisioning_profile_dates(path: Path) -> tuple[datetime, datetime] | None:
    try:
        result = run_capture(
            ["security", "cms", "-D", "-i", str(path)], check=False
        )
    except OSError:
        return None
    if result.returncode:
        return None
    try:
        document = plistlib.loads(result.stdout.encode("utf-8"))
    except (ValueError, plistlib.InvalidFileException):
        return None
    created = document.get("CreationDate")
    expires = document.get("ExpirationDate")
    if not isinstance(created, datetime) or not isinstance(expires, datetime):
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return created.astimezone(timezone.utc), expires.astimezone(timezone.utc)


def runner_cache_observation(
    config: Config, *, now: datetime | None = None
) -> dict[str, object]:
    current = now or datetime.now(timezone.utc)
    matches = matching_runner_cache_directories(config)
    cache_dates: list[tuple[datetime, datetime]] = []
    for directory in matches:
        dates = [
            observed
            for profile in directory.rglob("embedded.mobileprovision")
            if (observed := provisioning_profile_dates(profile)) is not None
        ]
        if dates:
            cache_dates.append(min(dates, key=lambda item: item[1]))
    selected = max(cache_dates, key=lambda item: item[1]) if cache_dates else None
    remaining = (
        int((selected[1] - current).total_seconds()) if selected else None
    )
    lifetime = (
        int((selected[1] - selected[0]).total_seconds()) if selected else None
    )
    lifetime_class = "unknown"
    if lifetime is not None:
        lifetime_class = "short_lived" if lifetime <= 10 * 86400 else "long_lived"
    all_profiles_observed = bool(matches) and len(cache_dates) == len(matches)
    expired = (
        all_profiles_observed
        and bool(cache_dates)
        and all(expires <= current for _, expires in cache_dates)
    )
    refresh_recommended = expired or (
        config.signing_profile == "personal_team"
        and all_profiles_observed
        and remaining is not None
        and remaining <= PERSONAL_TEAM_REFRESH_SECONDS
    )
    profile_mismatch = (
        config.signing_profile == "personal_team" and lifetime_class == "long_lived"
    ) or (
        config.signing_profile == "developer_program"
        and lifetime_class == "short_lived"
    )
    return {
        "available": bool(matches) and not expired,
        "profileObserved": selected is not None,
        "profileExpiration": selected[1].isoformat() if selected else None,
        "secondsRemaining": remaining,
        "profileLifetimeSeconds": lifetime,
        "observedLifetime": lifetime_class,
        "expired": expired,
        "refreshRecommended": refresh_recommended,
        "declarationMismatch": profile_mismatch,
    }


def runner_cache_available(config: Config) -> bool:
    return bool(runner_cache_observation(config)["available"])


def refresh_matching_runner_cache(config: Config) -> int:
    root = runner_cache_root().resolve()
    removed = 0
    for directory in matching_runner_cache_directories(config):
        resolved = directory.resolve()
        if resolved.parent != root or not resolved.name.startswith("cache-"):
            raise TestbedError("refusing to refresh an unexpected runner cache path")
        shutil.rmtree(resolved)
        removed += 1
    return removed


def lock_state(device_name: str) -> dict[str, object]:
    document = devicectl_json(
        ["device", "info", "lockState", "--device", device_name]
    )
    result = document.get("result")
    if not isinstance(result, dict):
        return {}
    return {
        "passcodeRequired": bool(result.get("passcodeRequired", False)),
        "unlockedSinceBoot": bool(result.get("unlockedSinceBoot", False)),
    }


def interaction_observation(
    *, connected: bool, locked: dict[str, object]
) -> tuple[str, bool, str]:
    if not connected:
        return "unknown", False, "unavailable"
    if not {
        "passcodeRequired",
        "unlockedSinceBoot",
    } <= locked.keys():
        return "unknown", False, "unverified"
    passcode_required = bool(locked["passcodeRequired"])
    unlocked_since_boot = bool(locked["unlockedSinceBoot"])
    if passcode_required or not unlocked_since_boot:
        return "protected", False, "manual_first_unlock_required"
    return "unlocked", True, "none_observed"


def status(config: Config, *, json_output: bool = False) -> int:
    device = discover_selected_device(config)
    summary = device_summary(device)
    data = {
        "id": "ios",
        **summary,
        "runnerCacheAvailable": runner_cache_available(config),
        "leaseActive": config.lease_path.exists(),
        "agentStateDir": str(config.agent_state_dir),
    }
    if json_output:
        print(json.dumps(data, indent=2))
    else:
        print(f"state: {data['state']}")
        print(f"device: {data['name']} ({data['model']}, iOS {data['osVersion']})")
        print(f"developer mode: {data['developerMode'] or 'unknown'}")
        print(f"transport: {data['transport'] or 'unknown'}")
        print(
            "runner cache available: "
            f"{'yes' if data['runnerCacheAvailable'] else 'no'}"
        )
        print(f"lease active: {'yes' if data['leaseActive'] else 'no'}")
    return 0 if summary["available"] else 1


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def doctor_checks(config: Config) -> list[Check]:
    checks: list[Check] = []
    checks.append(
        Check(
            "host",
            "ok" if sys.platform == "darwin" else "error",
            platform.platform(),
            None if sys.platform == "darwin" else "Use a Mac with full Xcode.",
        )
    )
    for command, fix in (
        ("xcrun", "Install full Xcode and select it with xcode-select."),
        ("xcodebuild", "Install full Xcode."),
        ("security", "Use the macOS system security tool."),
        ("node", "Install Node.js 24 or newer."),
    ):
        checks.append(
            Check(
                command,
                "ok" if command_exists(command) else "error",
                shutil.which(command) or "not found",
                None if command_exists(command) else fix,
            )
        )

    if config.agent_device.is_file():
        version = run_capture(
            [str(config.agent_device), "--version"], check=False
        ).stdout.strip()
        version_ok = version == PINNED_AGENT_DEVICE_VERSION
        checks.append(
            Check(
                "agent-device",
                "ok" if version_ok else "error",
                version or str(config.agent_device),
                None
                if version_ok
                else f"Run pnpm install to restore {PINNED_AGENT_DEVICE_VERSION}.",
            )
        )
    else:
        checks.append(
            Check(
                "agent-device",
                "error",
                f"not installed at {config.agent_device}",
                "Run pnpm install in the testbed checkout.",
            )
        )

    checks.append(
        Check(
            "signing team",
            "ok" if config.team_id else "error",
            "configured" if config.team_id else "missing",
            None if config.team_id else "Set IOS_DEVICE_TESTBED_TEAM_ID in config.local.",
        )
    )
    profile_labels = {
        "unspecified": "not declared",
        "developer_program": "Apple Developer Program",
        "personal_team": "free Personal Team",
    }
    checks.append(
        Check(
            "signing profile",
            "warn" if config.signing_profile == "unspecified" else "ok",
            profile_labels[config.signing_profile],
            (
                "Set IOS_DEVICE_TESTBED_SIGNING_PROFILE to developer_program "
                "or personal_team."
                if config.signing_profile == "unspecified"
                else None
            ),
        )
    )
    checks.append(
        Check(
            "runner bundle",
            "ok" if config.runner_bundle_id else "error",
            config.runner_bundle_id or "missing",
            None
            if config.runner_bundle_id
            else "Set IOS_DEVICE_TESTBED_RUNNER_BUNDLE_ID in config.local.",
        )
    )

    try:
        device = discover_selected_device(config)
        summary = device_summary(device)
        device_name = str(summary["name"])
        checks.append(
            Check(
                "device",
                "ok" if summary["available"] else "error",
                f"{device_name} ({summary['model']}, iOS {summary['osVersion']}, {summary['transport']})",
                None if summary["available"] else "Connect, pair, and unlock the selected iPhone.",
            )
        )
        developer_mode = str(summary["developerMode"]).casefold()
        checks.append(
            Check(
                "Developer Mode",
                "ok" if developer_mode == "enabled" else "error",
                str(summary["developerMode"] or "unknown"),
                None
                if developer_mode == "enabled"
                else "Enable Developer Mode in Privacy & Security on the iPhone.",
            )
        )
        try:
            locked = lock_state(device_name)
            passcode_required = bool(locked.get("passcodeRequired", False))
            unlocked_since_boot = bool(locked.get("unlockedSinceBoot", False))
            interaction_ready = not passcode_required and unlocked_since_boot
            checks.append(
                Check(
                    "device unlock",
                    "ok" if interaction_ready else "error",
                    "unlocked"
                    if interaction_ready
                    else "manual first unlock required",
                    None if interaction_ready else "Unlock the iPhone locally.",
                )
            )
        except TestbedError as error:
            checks.append(Check("device unlock", "warn", redact(str(error))))
    except TestbedError as error:
        checks.append(
            Check(
                "device",
                "error",
                redact(str(error)),
                "Connect the configured iPhone.",
            )
        )

    if command_exists("security"):
        identities = run_capture(
            ["security", "find-identity", "-v", "-p", "codesigning"],
            check=False,
        )
        valid = (
            identities.returncode == 0
            and bool(config.signing_identity)
            and config.signing_identity.casefold() in identities.stdout.casefold()
            and not re.search(r"\b0 valid identities found\b", identities.stdout)
        )
        checks.append(
            Check(
                "code signing identity",
                "ok" if valid else "error",
                "valid identity available" if valid else "no valid identity found",
                None
                if valid
                else "Create or import an Apple Development identity in Xcode.",
            )
        )

    devtools = Path("/usr/sbin/DevToolsSecurity")
    if devtools.is_file():
        result = run_capture([str(devtools), "-status"], check=False)
        enabled = "enabled" in (result.stdout + result.stderr).casefold()
        checks.append(
            Check(
                "Developer Tools security",
                "ok" if enabled else "error",
                "enabled" if enabled else "disabled",
                None if enabled else "Run sudo DevToolsSecurity -enable once.",
            )
        )

    cache = runner_cache_observation(config)
    cache_available = bool(cache["available"])
    checks.append(
        Check(
            "XCTest build cache",
            "ok" if cache_available else "error",
            "available" if cache_available else "not available",
            None if cache_available else "Run bin/ios-device prepare.",
        )
    )
    if bool(cache["profileObserved"]):
        if bool(cache["expired"]):
            profile_status = "error"
            profile_detail = "expired"
            profile_fix = "Run bin/ios-device prepare --refresh."
        elif bool(cache["declarationMismatch"]):
            profile_status = "warn"
            profile_detail = "lifetime differs from the declared signing profile"
            profile_fix = "Check IOS_DEVICE_TESTBED_SIGNING_PROFILE."
        elif bool(cache["refreshRecommended"]):
            profile_status = "warn"
            profile_detail = "expires soon"
            profile_fix = "Run bin/ios-device prepare before unattended work."
        else:
            profile_status = "ok"
            profile_detail = f"valid ({cache['observedLifetime']})"
            profile_fix = None
        checks.append(
            Check(
                "runner provisioning",
                profile_status,
                profile_detail,
                profile_fix,
            )
        )
    elif cache_available:
        checks.append(
            Check(
                "runner provisioning",
                "warn",
                "embedded profile lifetime unavailable",
                "Run prepare --refresh if the runner stops launching.",
            )
        )
    return checks


def common_check_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")


def common_doctor_document(
    config: Config,
    checks: list[Check],
) -> dict[str, object]:
    device_check_names = {"device", "Developer Mode", "device unlock"}
    host_checks = [check for check in checks if check.name not in device_check_names]
    ok = not any(check.status == "error" for check in host_checks)
    common_checks = [
        {
            "id": common_check_id(check.name),
            "status": {"ok": "pass", "warn": "warn", "error": "fail"}[
                check.status
            ],
            "summary": f"iOS {check.name} check is "
            + ({"ok": "pass", "warn": "warn", "error": "fail"}[check.status]),
        }
        for check in host_checks
    ]
    locked: dict[str, object] = {}
    try:
        device = discover_selected_device(config)
        summary = device_summary(device)
        name = nested_string(device, "deviceProperties", "name")
        connected = bool(summary["available"])
    except TestbedError:
        summary = {"developerMode": "", "transport": ""}
        connected = False
        name = ""
    if connected and name:
        try:
            locked = lock_state(name)
        except TestbedError:
            pass
    passcode_required = bool(locked.get("passcodeRequired", False))
    unlocked_since_boot = bool(locked.get("unlockedSinceBoot", False))
    lock_observed = {
        "passcodeRequired",
        "unlockedSinceBoot",
    } <= locked.keys()
    developer_mode = (
        str(summary.get("developerMode", "")).casefold() == "enabled"
    )
    interaction, interaction_ready, interaction_gate = interaction_observation(
        connected=connected,
        locked=locked,
    )
    cache = runner_cache_observation(config)
    cache_available = bool(cache["available"])
    runner_available = (
        connected and developer_mode and cache_available and interaction_ready
    )
    if connected:
        common_checks.extend(
            [
                {
                    "id": "device",
                    "status": "pass",
                    "summary": "the configured physical iOS device is connected",
                },
                {
                    "id": "developer_mode",
                    "status": "pass" if developer_mode else "fail",
                    "summary": "iOS Developer Mode is enabled"
                    if developer_mode
                    else "iOS Developer Mode is unavailable",
                },
                {
                    "id": "device_unlock",
                    "status": "pass" if interaction_ready else "warn",
                    "summary": "the iOS interaction surface is unlocked"
                    if interaction_ready
                    else (
                        "the iOS interaction surface requires a local first unlock"
                        if interaction_gate == "manual_first_unlock_required"
                        else "the iOS interaction state is unverified"
                    ),
                },
            ]
        )
    else:
        common_checks.append(
            {
                "id": "device",
                "status": "fail",
                "summary": "the configured physical iOS device is unavailable",
            }
        )
    return {
        "schema": "machine-control-doctor/v0",
        "ready": ok and connected and developer_mode and interaction_ready,
        "target": {
            "platform": "ios",
            "platformFamily": "ios",
            "kind": "device",
            "deviceClass": "phone",
            "profile": "ios-coredevice-xctest",
        },
        "states": {
            "power": "running" if connected else "unknown",
            "connection": "ready" if connected else "unavailable",
            "boot": "ready" if connected else "unavailable",
            "administration": "ready" if connected else "unavailable",
            "interaction": interaction,
            "runner": "degraded" if runner_available else "unavailable",
            "semantic": "degraded" if runner_available else "unavailable",
            "capture": "degraded" if runner_available else "unavailable",
            "input": "degraded" if runner_available else "unavailable",
            "outer": "ready" if connected else "unavailable",
        },
        "checks": common_checks,
        "lifecycleOperations": ["status", "doctor", "capabilities", "reboot"],
        "extensions": {
            "routeClass": "host.device",
            "providers": ["ios.coredevice", "ios.xctest"],
            "developerMode": developer_mode,
            "transport": str(summary.get("transport", "")).casefold() or "unknown",
            "lockState": {
                "observed": lock_observed,
                "passcodeRequired": passcode_required,
                "unlockedSinceBoot": unlocked_since_boot,
            },
            "interactionGate": interaction_gate,
            "runnerCacheAvailable": cache_available,
            "runnerAuthentication": "unverified_until_launch",
            "runnerProvisioning": {
                "declaredSigningProfile": config.signing_profile,
                "profileObserved": cache["profileObserved"],
                "profileExpiration": cache["profileExpiration"],
                "secondsRemaining": cache["secondsRemaining"],
                "observedLifetime": cache["observedLifetime"],
                "refreshRecommended": cache["refreshRecommended"],
                "declarationMismatch": cache["declarationMismatch"],
            },
            "iosOperations": [
                "capabilities",
                "runner.prepare",
                "application.install",
                "application.launch",
                "application.terminate",
                "semantic.snapshot",
                "semantic.press",
                "semantic.fill",
                "navigation.home",
            ],
        },
    }


def doctor(config: Config, *, json_output: bool = False) -> int:
    checks = doctor_checks(config)
    ok = not any(check.status == "error" for check in checks)
    if json_output:
        document = common_doctor_document(config, checks)
        print(json.dumps(document, indent=2))
        return 0 if document["ready"] else 1
    else:
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}")
            if check.fix:
                print(f"  fix: {check.fix}")
        print("doctor: ready" if ok else "doctor: attention required")
    return 0 if ok else 1


def require_mutation_config(config: Config) -> None:
    if not config.team_id:
        raise TestbedError("IOS_DEVICE_TESTBED_TEAM_ID is missing from config.local")
    if not config.runner_bundle_id:
        raise TestbedError(
            "IOS_DEVICE_TESTBED_RUNNER_BUNDLE_ID is missing from config.local"
        )
    if not config.agent_device.is_file():
        raise TestbedError(
            f"pinned agent-device is not installed at {config.agent_device}; run pnpm install"
        )


def agent_environment(config: Config) -> dict[str, str]:
    require_mutation_config(config)
    config.agent_state_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["AGENT_DEVICE_STATE_DIR"] = str(config.agent_state_dir)
    env["AGENT_DEVICE_IOS_TEAM_ID"] = config.team_id
    env["AGENT_DEVICE_IOS_BUNDLE_ID"] = config.runner_bundle_id
    env["AGENT_DEVICE_IOS_SIGNING_IDENTITY"] = config.signing_identity
    env.setdefault("AGENT_DEVICE_IOS_RUNNER_IDLE_STOP_MS", "60000")
    return env


def daemon_environment(config: Config) -> dict[str, str]:
    """Return the minimum environment needed to recover this checkout's daemon."""
    config.agent_state_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["AGENT_DEVICE_STATE_DIR"] = str(config.agent_state_dir)
    return env


def contains_option(args: Sequence[str], option: str) -> bool:
    return option in args or any(arg.startswith(f"{option}=") for arg in args)


def agent_argv(
    config: Config,
    args: Sequence[str],
    *,
    add_target: bool = True,
    device_name: str | None = None,
) -> list[str]:
    argv = [str(config.agent_device), *args]
    if add_target:
        name = device_name or selected_device_name(config)
        if not contains_option(args, "--platform"):
            argv.extend(["--platform", "ios"])
        if not contains_option(args, "--device"):
            argv.extend(["--device", name])
    return argv


def run_agent(
    config: Config,
    args: Sequence[str],
    *,
    add_target: bool = True,
    capture: bool = False,
) -> int:
    env = agent_environment(config)
    argv = agent_argv(config, args, add_target=add_target)
    if capture:
        result = run_capture(argv, env=env, check=False)
        if result.stdout:
            print(redact(result.stdout), end="")
        if result.stderr:
            print(redact(result.stderr), end="", file=sys.stderr)
        return result.returncode
    return subprocess.run(argv, env=env, check=False).returncode


def stop_daemon(config: Config) -> None:
    if not config.agent_device.is_file():
        return
    env = daemon_environment(config)
    run_capture(
        [
            str(config.agent_device),
            "daemon",
            "stop",
            "--state-dir",
            str(config.agent_state_dir),
            "--clean",
        ],
        env=env,
        check=False,
    )


def controller_name() -> str:
    return socket.gethostname()


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


def read_lease(path: Path) -> Lease | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != LEASE_SCHEMA:
            raise TestbedError("unknown lease schema")
        return Lease(
            token=str(data["token"]),
            owner_pid=int(data["owner_pid"]),
            controller=str(data["controller"]),
            mode=str(data["mode"]),
            session_name=str(data["session_name"]),
            created_at=str(data["created_at"]),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise TestbedError(f"invalid lease journal at {path}: {error}") from error


def active_nested_lease(config: Config) -> Lease | None:
    token = os.environ.get("IOS_DEVICE_TESTBED_LEASE_TOKEN", "")
    if not token:
        return None
    lease = read_lease(config.lease_path)
    if lease and secrets.compare_digest(lease.token, token):
        return lease
    raise TestbedError("session lease token does not match the active testbed lease")


def acquire_lease(
    config: Config,
    *,
    mode: str,
    stale_cleanup: Callable[[], None] | None = None,
    alive: Callable[[int], bool] = pid_is_alive,
) -> Lease:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    existing = read_lease(config.lease_path)
    if existing:
        if existing.controller == controller_name() and not alive(existing.owner_pid):
            if stale_cleanup:
                stale_cleanup()
            config.lease_path.unlink(missing_ok=True)
        else:
            raise TestbedError(
                "iOS device is leased by "
                f"{existing.controller} pid {existing.owner_pid}; use recover only after "
                "confirming that owner is gone"
            )
    token = secrets.token_hex(16)
    lease = Lease(
        token=token,
        owner_pid=os.getpid(),
        controller=controller_name(),
        mode=mode,
        session_name=f"ios-device-testbed-{token[:10]}",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    payload = {"schema": LEASE_SCHEMA, **asdict(lease)}
    try:
        descriptor = os.open(
            config.lease_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as error:
        raise TestbedError("another process acquired the iOS device lease") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return lease


def release_lease(config: Config, lease: Lease) -> None:
    current = read_lease(config.lease_path)
    if current and secrets.compare_digest(current.token, lease.token):
        config.lease_path.unlink(missing_ok=True)


def with_command_lease(config: Config, action: Callable[[], int]) -> int:
    if active_nested_lease(config):
        return action()
    lease = acquire_lease(config, mode="command", stale_cleanup=lambda: stop_daemon(config))
    try:
        return action()
    finally:
        release_lease(config, lease)


def prepare(config: Config, *, refresh: bool = False) -> int:
    require_mutation_config(config)

    def action() -> int:
        try:
            cache = runner_cache_observation(config)
            if refresh or bool(cache["refreshRecommended"]):
                refresh_matching_runner_cache(config)
            return run_agent(
                config,
                ["prepare", "ios-runner", "--timeout", "240000"],
            )
        finally:
            stop_daemon(config)

    return with_command_lease(config, action)


def wait_for_pairing(
    reference: str,
    timeout: int,
    *,
    clock: Callable[[], float] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, object]:
    now = clock or time.monotonic
    sleep = sleeper or time.sleep
    deadline = now() + timeout
    while now() < deadline:
        device = device_details(reference)
        if device is not None and bool(device_summary(device)["available"]):
            return device
        sleep(0.5)
    raise TestbedError(
        "the iOS pairing request was not confirmed; approve Trust on the phone "
        "and enter its passcode locally when one is configured"
    )


def pair_device(config: Config, timeout: int) -> int:
    if timeout <= 0:
        raise TestbedError("pair timeout must be positive")
    if not config.device_selector:
        raise TestbedError(
            "pair requires IOS_DEVICE_TESTBED_DEVICE to select one exact phone"
        )

    def action() -> int:
        device = select_device(discoverable_devices(), config.device_selector)
        reference = device_identifier(device)
        if not reference:
            raise TestbedError("the selected iOS device has no stable identifier")
        if bool(device_summary(device)["available"]):
            print("paired")
            return 0
        print(
            "Confirm Trust on the selected iPhone and enter its passcode locally "
            "if one is configured."
        )
        devicectl_json(
            [
                "manage",
                "pair",
                "--device",
                reference,
                "--timeout",
                str(timeout),
            ]
        )
        wait_for_pairing(reference, timeout)
        print("paired")
        return 0

    return with_command_lease(config, action)


def same_physical_device(device: dict[str, object], expected: str) -> bool:
    return bool(expected) and device_identifier(device) == expected


def wait_for_reboot_effect(
    config: Config,
    expected_identifier: str,
    timeout: int,
    *,
    clock: Callable[[], float] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    now = clock or time.monotonic
    sleep = sleeper or time.sleep
    deadline = now() + timeout
    disconnect_observed = False
    stable_connected = 0
    last_lock: dict[str, object] = {}

    while now() < deadline:
        if not disconnect_observed:
            try:
                listed = discover_listed_device(config)
                listed_available = bool(device_summary(listed)["available"])
            except TestbedError:
                listed_available = False
            if not listed_available:
                disconnect_observed = True
            sleep(0.5)
            continue

        try:
            device = discover_selected_device(config)
            summary = device_summary(device)
            if not same_physical_device(device, expected_identifier):
                raise TestbedError(
                    "a different iOS device appeared while waiting for reboot"
                )
            if not bool(summary["available"]):
                stable_connected = 0
                sleep(0.5)
                continue
            stable_connected += 1
            name = nested_string(device, "deviceProperties", "name")
            try:
                last_lock = lock_state(name) if name else {}
            except TestbedError:
                last_lock = {}
            if last_lock or stable_connected >= 3:
                return device, last_lock
        except TestbedError:
            stable_connected = 0
        sleep(0.5)

    if not disconnect_observed:
        raise TestbedError(
            "the iOS reboot request was accepted but no disconnect was observed"
        )
    raise TestbedError("the selected iOS device did not reconnect after reboot")


def reboot_device(config: Config, timeout: int) -> int:
    if timeout <= 0:
        raise TestbedError("reboot timeout must be positive")

    def action() -> int:
        stop_daemon(config)
        device = discover_selected_device(config)
        device_name = nested_string(device, "deviceProperties", "name")
        expected_identifier = device_identifier(device)
        if not device_name or not expected_identifier:
            raise TestbedError("the selected iOS device has incomplete identity")
        devicectl_json(
            [
                "device",
                "reboot",
                "--device",
                device_name,
                "--style",
                "full",
                "--timeout",
                str(timeout),
            ]
        )
        _, locked = wait_for_reboot_effect(config, expected_identifier, timeout)
        _, interaction_ready, interaction_gate = interaction_observation(
            connected=True,
            locked=locked,
        )
        if interaction_ready:
            print("running: interaction ready")
        elif interaction_gate == "manual_first_unlock_required":
            print("running: manual first unlock required before XCTest")
        else:
            print("running: interaction state unverified")
        return 0

    return with_command_lease(config, action)


def strip_separator(args: Sequence[str]) -> list[str]:
    values = list(args)
    if values and values[0] == "--":
        values.pop(0)
    return values


def cleanup_session(config: Config, lease: Lease) -> None:
    try:
        try:
            device_name = selected_device_name(config)
        except TestbedError:
            device_name = config.device_selector
        if device_name:
            run_capture(
                [
                    str(config.agent_device),
                    "close",
                    "--session",
                    lease.session_name,
                    "--platform",
                    "ios",
                    "--device",
                    device_name,
                ],
                env=agent_environment(config),
                check=False,
            )
    finally:
        stop_daemon(config)


def session(config: Config, command: Sequence[str]) -> int:
    require_mutation_config(config)
    argv = strip_separator(command)
    if not argv:
        raise TestbedError("session requires a command after --")
    lease = acquire_lease(
        config,
        mode="transactional",
        stale_cleanup=lambda: stop_daemon(config),
    )
    env = agent_environment(config)
    env["IOS_DEVICE_TESTBED_SESSION_ACTIVE"] = "1"
    env["IOS_DEVICE_TESTBED_LEASE_TOKEN"] = lease.token
    env["AGENT_DEVICE_SESSION"] = lease.session_name
    try:
        return subprocess.run(argv, env=env, check=False).returncode
    finally:
        try:
            cleanup_session(config, lease)
        finally:
            release_lease(config, lease)


def recover(config: Config, *, force: bool = False) -> int:
    lease = read_lease(config.lease_path)
    if lease and pid_is_alive(lease.owner_pid) and not force:
        raise TestbedError(
            f"lease owner pid {lease.owner_pid} is still alive; pass --force only after "
            "confirming it is safe to interrupt"
        )
    if lease and lease.controller != controller_name() and not force:
        raise TestbedError("foreign-controller lease requires recover --force")
    stop_daemon(config)
    if lease:
        config.lease_path.unlink(missing_ok=True)
    print("Recovered iOS testbed runner and lease state.")
    return 0


def install_app(config: Config, app_path: str) -> int:
    path = Path(app_path).expanduser().resolve()
    if not path.is_dir() or path.suffix != ".app":
        raise TestbedError(f"install requires an existing .app directory: {path}")
    name = selected_device_name(config)

    def action() -> int:
        run_capture(
            [
                "xcrun",
                "devicectl",
                "device",
                "install",
                "app",
                "--device",
                name,
                str(path),
            ]
        )
        print(f"Installed {path.name} on {name}.")
        return 0

    return with_command_lease(config, action)


def normal_launch(config: Config, bundle_id: str) -> int:
    name = selected_device_name(config)

    def action() -> int:
        run_capture(
            [
                "xcrun",
                "devicectl",
                "device",
                "process",
                "launch",
                "--device",
                name,
                bundle_id,
            ]
        )
        print(f"Launched {bundle_id} on {name} outside XCTest automation.")
        return 0

    return with_command_lease(config, action)


FORWARDED_COMMANDS = {
    "snapshot": "snapshot",
    "find": "find",
    "get": "get",
    "wait": "wait",
    "assert": "is",
    "press": "press",
    "tap": "press",
    "fill": "fill",
    "type": "type",
    "scroll": "scroll",
    "swipe": "swipe",
    "longpress": "longpress",
    "home": "home",
    "app-switcher": "app-switcher",
    "screenshot": "screenshot",
    "record": "record",
    "logs": "logs",
    "launch": "open",
    "terminate": "close",
}

IOS_CONTROL_OPERATIONS = {
    "capabilities",
    "runner.prepare",
    "application.install",
    "application.launch",
    "application.terminate",
    "semantic.snapshot",
    "semantic.press",
    "semantic.fill",
    "navigation.home",
}

SENSITIVE_PROVIDER_KEYS = {
    "deviceid",
    "udid",
    "serial",
    "serialnumber",
    "ecid",
    "teamid",
    "logpath",
    "requestlogpath",
    "runnerlogpath",
    "ownerstatedir",
    "xctestrunpath",
    "jsonpath",
}


def sanitize_provider_value(value: object) -> object:
    if isinstance(value, list):
        return [sanitize_provider_value(item) for item in value]
    if not isinstance(value, dict):
        return redact(value) if isinstance(value, str) else value
    device_descriptor = (
        str(value.get("platform", "")).casefold() == "ios"
        and str(value.get("kind", "")).casefold() in {"device", "physical"}
    )
    sanitized: dict[str, object] = {}
    for key, item in value.items():
        folded = key.casefold()
        if folded in SENSITIVE_PROVIDER_KEYS:
            continue
        if device_descriptor and folded in {"id", "name"}:
            continue
        sanitized[key] = sanitize_provider_value(item)
    return sanitized


def require_control_string(
    request: dict[str, object], key: str, *, optional: bool = False
) -> str | None:
    value = request.get(key)
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value:
        raise TestbedError(f"iOS control operation requires nonempty {key}")
    return value


def control_capabilities(upstream: object) -> dict[str, object]:
    available = []
    if isinstance(upstream, dict):
        commands = upstream.get("availableCommands")
        if isinstance(commands, list):
            available = sorted(
                command for command in commands if isinstance(command, str)
            )
    return {
        "operations": [
            {
                "operation": "capabilities",
                "route": "ios.xctest",
                "mutating": False,
            },
            {
                "operation": "runner.prepare",
                "route": "ios.xctest",
                "mutating": True,
                "effect": "runner health check",
            },
            {
                "operation": "application.install",
                "route": "ios.coredevice",
                "mutating": True,
                "effect": "installed-app inventory",
            },
            {
                "operation": "application.launch",
                "route": "ios.xctest",
                "mutating": True,
            },
            {
                "operation": "application.terminate",
                "route": "ios.xctest",
                "mutating": True,
            },
            {
                "operation": "semantic.snapshot",
                "route": "ios.xctest",
                "mutating": False,
                "references": "provider_snapshot_scoped",
            },
            {
                "operation": "semantic.press",
                "route": "ios.xctest",
                "mutating": True,
                "references": "provider_snapshot_scoped",
            },
            {
                "operation": "semantic.fill",
                "route": "ios.xctest",
                "mutating": True,
                "secretTransport": "unsupported",
            },
            {
                "operation": "navigation.home",
                "route": "ios.xctest",
                "mutating": True,
            },
        ],
        "upstreamAvailableCommands": available,
        "protectedAuthentication": "human_only",
    }


def provider_settle_effect(data: object) -> str:
    if not isinstance(data, dict):
        return "unverifiable"
    settle = data.get("settle")
    if not isinstance(settle, dict) or settle.get("settled") is not True:
        return "unverifiable"
    diff = settle.get("diff")
    summary = diff.get("summary") if isinstance(diff, dict) else None
    if not isinstance(summary, dict):
        return "unverifiable"
    values = (summary.get("additions"), summary.get("removals"))
    changed = sum(value for value in values if isinstance(value, int))
    return "confirmed" if changed > 0 else "unverifiable"


def ios_result(
    operation: str,
    *,
    accepted: bool,
    route: str,
    elapsed_ms: int,
    delivery: str,
    effect: str,
    uncertainty: str,
    data: object | None = None,
    error_code: str | None = None,
    message: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema": "machine-control/v0",
        "requestId": secrets.token_hex(12),
        "operation": operation,
        "accepted": accepted,
        "actualRoute": f"host.device/{route}",
        "generation": "unavailable",
        "delivery": delivery,
        "effect": effect,
        "hostInterference": "none",
        "uncertainty": uncertainty,
        "retrySafety": (
            "observation_safe"
            if effect == "not_applicable"
            else "not_needed"
            if effect == "confirmed"
            else "observe_before_retry"
        ),
        "fallbackUsed": False,
        "retryCount": 0,
        "providerAttempts": [
            {
                "provider": route,
                "operation": operation,
                "outcome": "accepted" if accepted else "failed",
                "delivery": delivery,
                "effect": effect,
                "elapsedMs": elapsed_ms,
            }
        ],
        "elapsedMs": elapsed_ms,
        "data": sanitize_provider_value(data or {}),
    }
    if error_code:
        result["errorCode"] = error_code
    if message:
        result["message"] = redact(message)
    return result


def run_agent_json(
    config: Config, arguments: Sequence[str]
) -> tuple[dict[str, object] | None, int, str]:
    started = time.monotonic()
    result = run_capture(
        agent_argv(config, [*arguments, "--json"]),
        env=agent_environment(config),
        check=False,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        parsed = None
    return (
        parsed if isinstance(parsed, dict) else None,
        elapsed_ms,
        result.stderr.strip(),
    )


def provider_control_result(
    config: Config,
    operation: str,
    arguments: Sequence[str],
    *,
    observation: bool = False,
    confirmed_effect: bool = False,
) -> dict[str, object]:
    document, elapsed_ms, stderr = run_agent_json(config, arguments)
    if document is None:
        return ios_result(
            operation,
            accepted=False,
            route="ios.xctest",
            elapsed_ms=elapsed_ms,
            delivery="unknown",
            effect="unknown",
            uncertainty="the provider returned no valid structured response",
            error_code="invalid_provider_response",
            message=redact_config(
                stderr or "Agent Device returned invalid JSON", config
            ),
        )
    success = document.get("success") is True or document.get("ok") is True
    if not success:
        error = document.get("error")
        error_data = error if isinstance(error, dict) else {}
        provider_code = str(error_data.get("code", "PROVIDER_FAILED"))
        refused = provider_code in {
            "INVALID_ARGS",
            "UNSUPPORTED_OPERATION",
            "UNSUPPORTED_PLATFORM",
            "APP_NOT_INSTALLED",
            "SESSION_NOT_FOUND",
        }
        return ios_result(
            operation,
            accepted=False,
            route="ios.xctest",
            elapsed_ms=elapsed_ms,
            delivery="refused" if refused else "unknown",
            effect="refused" if refused else "unknown",
            uncertainty=(
                "none" if refused else "provider failure left delivery uncertain"
            ),
            error_code=f"agent_device_{provider_code.casefold()}",
            message=redact_config(
                str(error_data.get("message", stderr or "Agent Device failed")),
                config,
            ),
            data={
                "hint": error_data.get("hint")
                if isinstance(error_data.get("hint"), str)
                else None
            },
        )
    provider_data = document.get("data")
    data = (
        control_capabilities(provider_data)
        if operation == "capabilities"
        else provider_data
    )
    effect = (
        "not_applicable"
        if observation
        else "confirmed"
        if confirmed_effect
        else provider_settle_effect(provider_data)
        if operation in {"semantic.press", "semantic.fill"}
        else "unverifiable"
    )
    return ios_result(
        operation,
        accepted=True,
        route="ios.xctest",
        elapsed_ms=elapsed_ms,
        delivery="not_applicable" if observation else "confirmed",
        effect=effect,
        uncertainty=(
            "none"
            if observation or effect == "confirmed"
            else "provider delivery succeeded without an independent effect oracle"
        ),
        data=data,
    )


def installed_app_present(device_name: str, bundle_id: str) -> bool:
    document = devicectl_json(
        [
            "device",
            "info",
            "apps",
            "--device",
            device_name,
            "--bundle-id",
            bundle_id,
        ]
    )
    result = document.get("result")
    apps = result.get("apps") if isinstance(result, dict) else None
    return isinstance(apps, list) and bool(apps)


def install_control_result(config: Config, path_text: str) -> dict[str, object]:
    started = time.monotonic()
    path = Path(path_text).expanduser().resolve()
    if not path.is_dir() or path.suffix != ".app":
        raise TestbedError("application.install requires an existing .app directory")
    info_path = path / "Info.plist"
    try:
        with info_path.open("rb") as handle:
            info = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as error:
        raise TestbedError(
            "application.install could not read the app Info.plist"
        ) from error
    bundle_id = info.get("CFBundleIdentifier")
    if not isinstance(bundle_id, str) or not bundle_id:
        raise TestbedError("application.install app has no bundle identifier")
    device_name = selected_device_name(config)
    try:
        devicectl_json(
            ["device", "install", "app", "--device", device_name, str(path)]
        )
    except TestbedError as error:
        return ios_result(
            "application.install",
            accepted=False,
            route="ios.coredevice",
            elapsed_ms=int((time.monotonic() - started) * 1000),
            delivery="unknown",
            effect="unknown",
            uncertainty="CoreDevice failure left installation delivery uncertain",
            error_code="coredevice_install_failed",
            message=redact_config(str(error), config),
        )
    try:
        observed = installed_app_present(device_name, bundle_id)
    except TestbedError:
        observed = False
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return ios_result(
        "application.install",
        accepted=True,
        route="ios.coredevice",
        elapsed_ms=elapsed_ms,
        delivery="confirmed",
        effect="confirmed" if observed else "unknown",
        uncertainty=(
            "none"
            if observed
            else "installation succeeded but inventory readback failed"
        ),
        data={"applicationId": bundle_id, "installed": observed},
    )


def execute_control_request(
    config: Config, request: dict[str, object]
) -> dict[str, object]:
    operation = request.get("operation")
    if not isinstance(operation, str) or operation not in IOS_CONTROL_OPERATIONS:
        raise TestbedError("unsupported typed iOS control operation")
    if operation == "capabilities":
        return provider_control_result(
            config, operation, ["capabilities"], observation=True
        )
    if operation == "runner.prepare":
        refresh = request.get("refresh", False)
        if not isinstance(refresh, bool):
            raise TestbedError("runner.prepare refresh must be boolean")
        cache = runner_cache_observation(config)
        if refresh or bool(cache["refreshRecommended"]):
            refresh_matching_runner_cache(config)
        try:
            return provider_control_result(
                config,
                operation,
                ["prepare", "ios-runner", "--timeout", "240000"],
                confirmed_effect=True,
            )
        finally:
            stop_daemon(config)
    if operation == "application.install":
        path = require_control_string(request, "path")
        assert path is not None
        return install_control_result(config, path)
    if operation == "application.launch":
        application = require_control_string(request, "application")
        assert application is not None
        relaunch = request.get("relaunch", False)
        if not isinstance(relaunch, bool):
            raise TestbedError("application.launch relaunch must be boolean")
        return provider_control_result(
            config,
            operation,
            ["open", application, *(["--relaunch"] if relaunch else [])],
        )
    if operation == "application.terminate":
        application = require_control_string(request, "application", optional=True)
        return provider_control_result(
            config,
            operation,
            ["close", *([application] if application else [])],
        )
    if operation == "semantic.snapshot":
        interactive = request.get("interactive", False)
        depth = request.get("depth")
        scope = request.get("scope")
        if not isinstance(interactive, bool):
            raise TestbedError("semantic.snapshot interactive must be boolean")
        if depth is not None and (
            not isinstance(depth, int) or isinstance(depth, bool) or depth <= 0
        ):
            raise TestbedError("semantic.snapshot depth must be a positive integer")
        if scope is not None and (not isinstance(scope, str) or not scope):
            raise TestbedError("semantic.snapshot scope must be a nonempty string")
        arguments = ["snapshot"]
        if interactive:
            arguments.append("-i")
        if depth is not None:
            arguments.extend(["--depth", str(depth)])
        if scope is not None:
            arguments.extend(["--scope", scope])
        return provider_control_result(
            config, operation, arguments, observation=True
        )
    if operation in {"semantic.press", "semantic.fill"}:
        target = require_control_string(request, "target")
        assert target is not None
        settle = request.get("settle", False)
        if not isinstance(settle, bool):
            raise TestbedError(f"{operation} settle must be boolean")
        arguments = ["press", target]
        if operation == "semantic.fill":
            text = require_control_string(request, "text")
            assert text is not None
            arguments = ["fill", target, text]
        if settle:
            arguments.append("--settle")
        return provider_control_result(config, operation, arguments)
    return provider_control_result(config, operation, ["home"])


def control(config: Config) -> int:
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError:
        result = ios_result(
            "ios.control",
            accepted=False,
            route="ios.adapter",
            elapsed_ms=0,
            delivery="refused",
            effect="refused",
            uncertainty="none",
            error_code="invalid_ios_request",
            message="typed iOS control requires one JSON object on stdin",
        )
        print(json.dumps(result, indent=2))
        return 1
    if not isinstance(request, dict):
        result = ios_result(
            "ios.control",
            accepted=False,
            route="ios.adapter",
            elapsed_ms=0,
            delivery="refused",
            effect="refused",
            uncertainty="none",
            error_code="invalid_ios_request",
            message="typed iOS control requires one JSON object on stdin",
        )
        print(json.dumps(result, indent=2))
        return 1

    result: dict[str, object]
    try:
        require_mutation_config(config)
        result = with_command_lease(
            config, lambda: execute_control_request(config, request)
        )
    except TestbedError as error:
        operation = str(request.get("operation", "ios.control"))
        result = ios_result(
            operation,
            accepted=False,
            route="ios.adapter",
            elapsed_ms=0,
            delivery="refused",
            effect="refused",
            uncertainty="none",
            error_code="invalid_ios_request",
            message=redact_config(str(error), config),
        )
    print(json.dumps(result, indent=2))
    return 0 if bool(result["accepted"]) else 1


def forward(config: Config, command: str, args: Sequence[str]) -> int:
    underlying = FORWARDED_COMMANDS[command]
    values = strip_separator(args)
    return with_command_lease(
        config, lambda: run_agent(config, [underlying, *values])
    )


def raw_agent(config: Config, args: Sequence[str]) -> int:
    values = strip_separator(args)
    if not values:
        raise TestbedError("agent requires an Agent Device command")
    return with_command_lease(config, lambda: run_agent(config, values))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ios-device",
        description="Safely operate the configured physical iPhone testbed.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("probe", "status", "doctor"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--json", action="store_true")
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--refresh", action="store_true")
    pair_parser = subparsers.add_parser("pair")
    pair_parser.add_argument("--timeout", type=int, default=60)
    reboot_parser = subparsers.add_parser("reboot")
    reboot_parser.add_argument("--timeout", type=int, default=180)
    session_parser = subparsers.add_parser("session")
    session_parser.add_argument("child", nargs=argparse.REMAINDER)
    recover_parser = subparsers.add_parser("recover")
    recover_parser.add_argument("--force", action="store_true")
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("app_path")
    normal_parser = subparsers.add_parser("normal-launch")
    normal_parser.add_argument("bundle_id")
    subparsers.add_parser("control")
    agent_parser = subparsers.add_parser("agent")
    agent_parser.add_argument("agent_args", nargs=argparse.REMAINDER)
    for name in FORWARDED_COMMANDS:
        forwarded = subparsers.add_parser(name)
        forwarded.add_argument("forwarded_args", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if not raw_argv:
        build_parser().parse_args(raw_argv)
    command = raw_argv[0]
    config = load_config()
    try:
        # Forwarded commands intentionally accept the pinned upstream CLI's
        # evolving flags verbatim. argparse.REMAINDER still rejects options
        # such as `snapshot -i` unless callers insert `--`, which defeats the
        # wrapper's transparent command aliases.
        if command in FORWARDED_COMMANDS:
            return forward(config, command, raw_argv[1:])
        if command == "agent":
            return raw_agent(config, raw_argv[1:])
        if command == "session" and raw_argv[1:] not in (["-h"], ["--help"]):
            return session(config, raw_argv[1:])

        args = build_parser().parse_args(raw_argv)
        if args.command == "probe":
            return probe(config, json_output=args.json)
        if args.command == "status":
            return status(config, json_output=args.json)
        if args.command == "doctor":
            return doctor(config, json_output=args.json)
        if args.command == "prepare":
            return prepare(config, refresh=args.refresh)
        if args.command == "pair":
            return pair_device(config, args.timeout)
        if args.command == "reboot":
            return reboot_device(config, args.timeout)
        if args.command == "session":
            return session(config, args.child)
        if args.command == "recover":
            return recover(config, force=args.force)
        if args.command == "install":
            return install_app(config, args.app_path)
        if args.command == "normal-launch":
            return normal_launch(config, args.bundle_id)
        if args.command == "control":
            return control(config)
        raise TestbedError(f"unsupported command: {args.command}")
    except TestbedError as error:
        print(f"error: {redact(str(error))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
