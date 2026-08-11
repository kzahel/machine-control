#!/usr/bin/env python3
"""Minimized Ubuntu post-update audit and bounded systemd repair."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Sequence


SCHEMA = "machine-control-linux-post-update/v0"
RUNTIME_PACKAGES = (
    "qemu-guest-agent",
    "spice-vdagent",
    "python3-gi",
    "gir1.2-atspi-2.0",
    "gnome-screenshot",
    "python3-evdev",
    "python3-pyqt5",
    "wl-clipboard",
    "jq",
)
DEVELOPMENT_PACKAGES = ("git", "build-essential", "python3-venv")
OPTIONAL_CHECKS = frozenset(("spice_session",))


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""


class Runner:
    def run(self, command: Sequence[str]) -> CommandResult:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return CommandResult(completed.returncode, completed.stdout.strip())


def command_ok(runner: Runner, *command: str) -> bool:
    return runner.run(command).returncode == 0


def systemctl_state(runner: Runner, verb: str, unit: str) -> str:
    result = runner.run(("systemctl", verb, unit))
    return result.stdout.splitlines()[-1].strip() if result.stdout else "unknown"


def active_desktop(runner: Runner) -> tuple[str, str] | None:
    sessions = runner.run(("loginctl", "list-sessions", "--no-legend", "--no-pager"))
    if sessions.returncode != 0:
        return None
    for line in sessions.stdout.splitlines():
        fields = line.split()
        if not fields:
            continue
        session_id = fields[0]
        values: dict[str, str] = {}
        for prop in ("Active", "Type", "Name"):
            result = runner.run(
                ("loginctl", "show-session", session_id, f"--property={prop}", "--value")
            )
            if result.returncode != 0:
                values = {}
                break
            values[prop] = result.stdout.strip()
        user = values.get("Name", "")
        if (
            values.get("Active") == "yes"
            and values.get("Type") == "wayland"
            and user
            and user != "root"
        ):
            uid = runner.run(("id", "-u", user))
            if uid.returncode == 0 and uid.stdout.isdigit():
                return user, uid.stdout
    return None


def user_command(
    runner: Runner,
    desktop: tuple[str, str],
    command: Sequence[str],
) -> CommandResult:
    user, uid = desktop
    return runner.run(
        (
            "runuser",
            "-u",
            user,
            "--",
            "env",
            f"XDG_RUNTIME_DIR=/run/user/{uid}",
            f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus",
            *command,
        )
    )


def package_profile_ready(runner: Runner, profile: str) -> bool:
    packages = RUNTIME_PACKAGES + (
        DEVELOPMENT_PACKAGES if profile == "development" else ()
    )
    for package in packages:
        result = runner.run(
            ("dpkg-query", "-W", "-f=${db:Status-Abbrev}", package)
        )
        if result.returncode != 0 or not result.stdout.startswith("ii"):
            return False
    return True


def resident_status(
    runner: Runner,
    desktop: tuple[str, str] | None,
) -> tuple[bool, bool]:
    if desktop is None:
        return False, False
    enabled = user_command(
        runner, desktop, ("systemctl", "--user", "is-enabled", "linuxvm-control.service")
    ).stdout == "enabled"
    active = user_command(
        runner, desktop, ("systemctl", "--user", "is-active", "linuxvm-control.service")
    ).stdout == "active"
    socket_ready = Path(f"/run/user/{desktop[1]}/linuxvm-testbed/control.sock").is_socket()
    service_ready = enabled and active and socket_ready
    if not service_ready:
        return False, False
    result = user_command(
        runner,
        desktop,
        ("/usr/local/bin/machine-control", '{"operation":"status"}'),
    )
    if result.returncode != 0:
        return True, False
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return True, False
    data = payload.get("data", {})
    target_ready = (
        payload.get("schema") == "machine-control/v0"
        and payload.get("accepted") is True
        and data.get("semanticState") == "ready"
        and data.get("captureState") == "ready"
        and data.get("inputState") == "ready"
    )
    return True, target_ready


def collect_state(runner: Runner, profile: str) -> dict[str, bool]:
    desktop = active_desktop(runner)
    guest_agent = systemctl_state(
        runner, "is-active", "qemu-guest-agent.service"
    ) == "active"
    spice_system = systemctl_state(
        runner, "is-active", "spice-vdagentd.service"
    ) == "active"
    desktop_ready = desktop is not None and command_ok(
        runner, "pgrep", "-u", desktop[1], "-x", "gnome-shell"
    )
    spice_session = desktop is not None and command_ok(
        runner, "pgrep", "-u", desktop[1], "-x", "spice-vdagent"
    )
    input_enabled = systemctl_state(
        runner, "is-enabled", "linuxvm-input.service"
    ) == "enabled"
    input_active = systemctl_state(
        runner, "is-active", "linuxvm-input.service"
    ) == "active"
    input_ready = (
        input_enabled
        and input_active
        and Path("/run/linuxvm-testbed/input.sock").is_socket()
    )
    resident_ready, target_ready = resident_status(runner, desktop)
    dpkg_audit = runner.run(("dpkg", "--audit"))
    return {
        "package_manager": dpkg_audit.returncode == 0 and not dpkg_audit.stdout,
        "pending_reboot": not Path("/var/run/reboot-required").exists(),
        "profile_packages": package_profile_ready(runner, profile),
        "guest_agent": guest_agent,
        "spice_system": spice_system,
        "desktop_session": desktop_ready,
        "spice_session": spice_session,
        "input_broker": input_ready,
        "resident_service": resident_ready,
        "target_native": target_ready,
    }


def installed_unit(runner: Runner, unit: str) -> bool:
    result = runner.run(("systemctl", "show", unit, "--property=LoadState", "--value"))
    return result.returncode == 0 and result.stdout not in ("", "not-found")


def repair_state(runner: Runner, profile: str) -> dict[str, str]:
    before = collect_state(runner, profile)
    repairs = {key: "not_needed" if value else "not_repairable" for key, value in before.items()}

    if not before["guest_agent"] and installed_unit(runner, "qemu-guest-agent.service"):
        repairs["guest_agent"] = (
            "started"
            if command_ok(runner, "systemctl", "start", "qemu-guest-agent.service")
            else "failed"
        )
    if not before["spice_system"] and installed_unit(runner, "spice-vdagentd.service"):
        repairs["spice_system"] = (
            "started"
            if command_ok(runner, "systemctl", "start", "spice-vdagentd.service")
            else "failed"
        )
    if not before["input_broker"] and installed_unit(runner, "linuxvm-input.service"):
        command_ok(runner, "systemctl", "daemon-reload")
        enabled = command_ok(runner, "systemctl", "enable", "linuxvm-input.service")
        started = command_ok(runner, "systemctl", "restart", "linuxvm-input.service")
        repairs["input_broker"] = "enabled_and_restarted" if enabled and started else "failed"

    desktop = active_desktop(runner)
    if not before["resident_service"] or not before["target_native"]:
        if desktop is not None and Path(
            "/usr/local/libexec/linuxvm-testbed/linuxcontrol.py"
        ).is_file():
            user_command(runner, desktop, ("systemctl", "--user", "daemon-reload"))
            enabled = user_command(
                runner,
                desktop,
                ("systemctl", "--user", "enable", "linuxvm-control.service"),
            ).returncode == 0
            restarted = user_command(
                runner,
                desktop,
                ("systemctl", "--user", "restart", "linuxvm-control.service"),
            ).returncode == 0
            disposition = "enabled_and_restarted" if enabled and restarted else "failed"
            repairs["resident_service"] = disposition
            repairs["target_native"] = disposition
    return repairs


def check_payload(
    state: dict[str, bool],
    repairs: dict[str, str] | None,
) -> list[dict[str, object]]:
    observations = {
        "package_manager": ("consistent", "inconsistent"),
        "pending_reboot": ("clear", "required"),
        "profile_packages": ("present", "missing"),
        "guest_agent": ("active", "inactive"),
        "spice_system": ("active", "inactive"),
        "desktop_session": ("gnome_wayland_active", "unavailable"),
        "spice_session": ("active", "inactive"),
        "input_broker": ("ready", "unavailable"),
        "resident_service": ("ready", "unavailable"),
        "target_native": ("ready", "unavailable"),
    }
    checks: list[dict[str, object]] = []
    for check_id, ready in state.items():
        required = check_id not in OPTIONAL_CHECKS
        checks.append(
            {
                "id": check_id,
                "required": required,
                "status": "pass" if ready else ("fail" if required else "warn"),
                "observed": observations[check_id][0 if ready else 1],
                "repair": repairs.get(check_id, "not_requested")
                if repairs is not None
                else "not_requested",
            }
        )
    return checks


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("audit", "repair"), default="audit")
    parser.add_argument(
        "--profile", choices=("development", "runtime"), default="development"
    )
    parser.add_argument("--nonce", required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9]{24}", args.nonce):
        parser.error("nonce must contain exactly 24 lowercase letters or digits")
    return args


def main(argv: Sequence[str] | None = None, runner: Runner | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if os.geteuid() != 0:
        print("Run this script as root", file=sys.stderr)
        return 1
    active_runner = runner or Runner()
    repairs = repair_state(active_runner, args.profile) if args.mode == "repair" else None
    state = collect_state(active_runner, args.profile)
    if args.mode == "repair":
        deadline = time.monotonic() + 15
        repairable = (
            "guest_agent",
            "spice_system",
            "input_broker",
            "resident_service",
            "target_native",
        )
        while not all(state[key] for key in repairable) and time.monotonic() < deadline:
            time.sleep(0.25)
            state = collect_state(active_runner, args.profile)
    healthy = all(
        ready for check_id, ready in state.items() if check_id not in OPTIONAL_CHECKS
    )
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "mode": args.mode,
                "profile": args.profile,
                "nonce": args.nonce,
                "healthy": healthy,
                "checks": check_payload(state, repairs),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
