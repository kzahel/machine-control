#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

LEASE_SCHEMA = 1
PINNED_AGENT_DEVICE_VERSION = "0.20.5"
REPO_ROOT = Path(os.environ.get("IOS_DEVICE_TESTBED_ROOT", Path(__file__).parent))
IDENTIFIER_PATTERNS = (
    re.compile(r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f-]{15,}\b"),
    re.compile(r"\b[0-9A-Fa-f]{24,}\b"),
)


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
    )


def redact(text: str) -> str:
    for pattern in IDENTIFIER_PATTERNS:
        text = pattern.sub("<identifier>", text)
    return text


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


def runner_cache_available(config: Config) -> bool:
    # Agent Device 0.20.5 isolates daemon/session state with AGENT_DEVICE_STATE_DIR
    # but intentionally retains Apple build products in its user-wide cache.
    derived = Path.home() / ".agent-device" / "apple-runner" / "derived" / "ios-device"
    if not derived.is_dir() or not config.team_id or not config.runner_bundle_id:
        return False
    expected_settings = {
        f"AGENT_DEVICE_IOS_RUNNER_APP_BUNDLE_ID={config.runner_bundle_id}",
        f"AGENT_DEVICE_IOS_RUNNER_TEST_BUNDLE_ID={config.runner_bundle_id}.uitests",
        "CODE_SIGN_STYLE=Automatic",
        f"DEVELOPMENT_TEAM={config.team_id}",
    }
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
            return True
    return False


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
            checks.append(
                Check(
                    "device unlock",
                    "error" if passcode_required else "ok",
                    "locked" if passcode_required else "unlocked",
                    "Unlock the iPhone locally."
                    if passcode_required
                    else None,
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

    cache_available = runner_cache_available(config)
    checks.append(
        Check(
            "XCTest build cache",
            "ok" if cache_available else "error",
            "available" if cache_available else "not available",
            None if cache_available else "Run bin/ios-device prepare.",
        )
    )
    return checks


def doctor(config: Config, *, json_output: bool = False) -> int:
    checks = doctor_checks(config)
    ok = not any(check.status == "error" for check in checks)
    if json_output:
        print(
            json.dumps(
                {"ok": ok, "checks": [asdict(check) for check in checks]},
                indent=2,
            )
        )
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


def prepare(config: Config) -> int:
    require_mutation_config(config)

    def action() -> int:
        try:
            return run_agent(
                config,
                ["prepare", "ios-runner", "--timeout", "240000"],
            )
        finally:
            stop_daemon(config)

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
    subparsers.add_parser("prepare")
    session_parser = subparsers.add_parser("session")
    session_parser.add_argument("child", nargs=argparse.REMAINDER)
    recover_parser = subparsers.add_parser("recover")
    recover_parser.add_argument("--force", action="store_true")
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("app_path")
    normal_parser = subparsers.add_parser("normal-launch")
    normal_parser.add_argument("bundle_id")
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
            return prepare(config)
        if args.command == "session":
            return session(config, args.child)
        if args.command == "recover":
            return recover(config, force=args.force)
        if args.command == "install":
            return install_app(config, args.app_path)
        if args.command == "normal-launch":
            return normal_launch(config, args.bundle_id)
        raise TestbedError(f"unsupported command: {args.command}")
    except TestbedError as error:
        print(f"error: {redact(str(error))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
