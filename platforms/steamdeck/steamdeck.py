#!/usr/bin/env python3
"""Project-neutral SteamOS Devkit transport for a physical Steam Deck."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parent
SCREEN_CONTROL = ROOT / "scripts" / "screen-control.sh"
SCREEN_WAKE = ROOT / "scripts" / "screen-wake.py"
MANIFEST_SCHEMA = "steamdeck-testbed.game.v1"
GAME_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class TestbedError(RuntimeError):
    """An expected configuration, validation, or device-operation failure."""


@dataclass(frozen=True)
class GameManifest:
    path: Path
    game_id: str
    payload: Path
    argv: list[str]
    env: dict[str, str]
    runtime: str | None
    force_appid: str

    def registration(self, remote_directory: str) -> dict[str, Any]:
        settings: dict[str, str] = {"steam_play": "0"}
        if self.runtime:
            settings["compat_tool"] = self.runtime
        return {
            "gameid": self.game_id,
            "directory": remote_directory,
            "argv": self.argv,
            "env": self.env,
            "settings": settings,
            "force_appid": self.force_appid,
        }


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TestbedError(f"{label} must be a JSON object")
    return value


def load_manifest(path_value: str) -> GameManifest:
    path = Path(path_value).expanduser().resolve()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TestbedError(f"cannot read manifest {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise TestbedError(f"invalid JSON in {path}: {error}") from error
    data = _object(raw, "manifest")
    allowed = {
        "schema",
        "game_id",
        "payload",
        "argv",
        "env",
        "runtime",
        "force_appid",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise TestbedError(f"unknown manifest field(s): {', '.join(unknown)}")
    if data.get("schema") != MANIFEST_SCHEMA:
        raise TestbedError(f"manifest schema must be {MANIFEST_SCHEMA!r}")
    game_id = data.get("game_id")
    if not isinstance(game_id, str) or not GAME_ID_PATTERN.fullmatch(game_id):
        raise TestbedError(
            "game_id must contain only lowercase letters, digits, and underscores"
        )
    payload_value = data.get("payload")
    if not isinstance(payload_value, str) or not payload_value:
        raise TestbedError("payload must be a non-empty path string")
    payload = Path(payload_value).expanduser()
    if not payload.is_absolute():
        payload = path.parent / payload
    payload = payload.resolve()
    argv = data.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(value, str) and value for value in argv)
    ):
        raise TestbedError("argv must be a non-empty array of non-empty strings")
    if not argv[0].startswith("./") or ".." in PurePosixPath(argv[0]).parts:
        raise TestbedError("argv[0] must be a safe payload-relative path beginning ./")
    environment = data.get("env", {})
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in environment.items()
    ):
        raise TestbedError("env must be an object of string keys and values")
    runtime = data.get("runtime")
    if runtime is not None and (not isinstance(runtime, str) or not runtime):
        raise TestbedError("runtime must be null or a non-empty string")
    force_appid = data.get("force_appid", "")
    if not isinstance(force_appid, str) or (
        force_appid and not force_appid.isdecimal()
    ):
        raise TestbedError("force_appid must be empty or contain only digits")
    return GameManifest(
        path=path,
        game_id=game_id,
        payload=payload,
        argv=list(argv),
        env=dict(environment),
        runtime=runtime,
        force_appid=force_appid,
    )


def validate_upload_directory(
    response: dict[str, Any], game_id: str, expected_user: str
) -> str:
    remote_user = response.get("user")
    remote_directory = response.get("directory")
    if remote_user != expected_user:
        raise TestbedError(
            f"unexpected upload user: {remote_user or 'missing'} "
            f"(expected {expected_user})"
        )
    if not isinstance(remote_directory, str) or not remote_directory:
        raise TestbedError("Devkit response omitted the upload directory")
    path = PurePosixPath(remote_directory)
    home = PurePosixPath("/home") / expected_user
    try:
        path.relative_to(home)
    except ValueError as error:
        raise TestbedError(f"refusing upload directory outside {home}: {path}") from error
    if path.name != game_id or ".." in path.parts:
        raise TestbedError(f"refusing unexpected upload directory: {path}")
    return str(path)


class SteamDeck:
    def __init__(self) -> None:
        self.host = os.environ.get("STEAMDECK_HOST", "steamdeck")
        self.user = os.environ.get("STEAMDECK_USER", "")
        self.remote_user = os.environ.get(
            "STEAMDECK_REMOTE_USER", self.user or "deck"
        )
        self.key = os.environ.get("STEAMDECK_KEY", "")
        self.connect_timeout = os.environ.get("STEAMDECK_CONNECT_TIMEOUT", "10")
        if not self.connect_timeout.isdecimal() or int(self.connect_timeout) <= 0:
            raise TestbedError("STEAMDECK_CONNECT_TIMEOUT must be a positive integer")
        if "@" in self.host and self.user:
            raise TestbedError("set the SSH user in either STEAMDECK_HOST or STEAMDECK_USER")
        self.target = f"{self.user}@{self.host}" if self.user else self.host
        self.ssh_options = [
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={self.connect_timeout}",
            "-o",
            "StrictHostKeyChecking=yes",
        ]
        if self.key:
            key_path = Path(self.key).expanduser()
            if not key_path.is_file():
                raise TestbedError(f"SSH key not found: {key_path}")
            self.ssh_options.extend(["-i", str(key_path)])
        extra = os.environ.get("STEAMDECK_SSH_OPTIONS", "")
        if extra:
            self.ssh_options.extend(shlex.split(extra))

    @property
    def ssh_argv(self) -> list[str]:
        return ["ssh", *self.ssh_options]

    def remote(
        self,
        argv: Sequence[str] | str,
        *,
        check: bool = True,
        capture: bool = False,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = argv if isinstance(argv, str) else shlex.join(argv)
        return subprocess.run(
            [*self.ssh_argv, self.target, command],
            check=check,
            text=True,
            input=input_text,
            capture_output=capture,
        )

    def status(self) -> dict[str, Any]:
        result = self.remote(
            [
                "python3",
                f"/home/{self.remote_user}/devkit-utils/steamos-get-status",
                "--json",
            ],
            capture=True,
        )
        try:
            return _object(json.loads(result.stdout), "SteamOS status")
        except json.JSONDecodeError as error:
            raise TestbedError(f"SteamOS returned invalid status JSON: {error}") from error

    def prepare_upload(self, game_id: str) -> str:
        validate_game_id(game_id)
        result = self.remote(
            [
                "python3",
                f"/home/{self.remote_user}/devkit-utils/steamos-prepare-upload",
                "--gameid",
                game_id,
            ],
            capture=True,
        )
        try:
            response = _object(json.loads(result.stdout), "prepare-upload response")
        except json.JSONDecodeError as error:
            raise TestbedError(f"Devkit returned invalid upload JSON: {error}") from error
        return validate_upload_directory(response, game_id, self.remote_user)

    def register(self, manifest: GameManifest, remote_directory: str) -> None:
        parameters = json.dumps(
            manifest.registration(remote_directory), separators=(",", ":")
        )
        result = self.remote(
            [
                "python3",
                f"/home/{self.remote_user}/devkit-utils/steam-client-create-shortcut",
                "--parms",
                parameters,
            ],
            capture=True,
        )
        try:
            response = _object(json.loads(result.stdout), "registration response")
        except json.JSONDecodeError as error:
            raise TestbedError(f"Devkit returned invalid registration JSON: {error}") from error
        if response.get("error"):
            raise TestbedError(f"shortcut registration failed: {response['error']}")
        if "success" not in response:
            raise TestbedError("shortcut registration returned no success field")

    def install(self, manifest: GameManifest) -> str:
        if not manifest.payload.is_dir():
            raise TestbedError(f"payload directory not found: {manifest.payload}")
        remote_directory = self.prepare_upload(manifest.game_id)
        print(
            f"Uploading {manifest.payload} to {self.target}:{remote_directory}",
            file=sys.stderr,
        )
        subprocess.run(
            [
                "rsync",
                "-av",
                "--delete",
                "--chmod=Du=rwx,Dgo=rx,Fu=rwx,Fgo=rx",
                "-e",
                shlex.join(self.ssh_argv),
                f"{manifest.payload}/",
                f"{self.target}:{remote_directory}/",
            ],
            check=True,
        )
        self.register(manifest, remote_directory)
        return remote_directory

    def deploy_screen_helpers(self) -> str:
        for path in (SCREEN_CONTROL, SCREEN_WAKE):
            if not path.is_file():
                raise TestbedError(f"screen helper not found: {path}")
        remote_directory = ".local/state/steamdeck-testbed/screen-control"
        self.remote(["install", "-d", "-m", "700", remote_directory])
        subprocess.run(
            [
                "rsync",
                "-a",
                "--chmod=Fu=rwx,Fgo=",
                "-e",
                shlex.join(self.ssh_argv),
                str(SCREEN_CONTROL),
                str(SCREEN_WAKE),
                f"{self.target}:{remote_directory}/",
            ],
            check=True,
        )
        return f"$HOME/{remote_directory}"

    def set_screen(self, mode: str) -> None:
        remote_directory = self.deploy_screen_helpers()
        self.remote(f'{remote_directory}/screen-control.sh {shlex.quote(mode)}')


def validate_game_id(game_id: str) -> None:
    if not GAME_ID_PATTERN.fullmatch(game_id):
        raise TestbedError(
            "game ID must contain only lowercase letters, digits, and underscores"
        )


POWER_STATUS_SCRIPT = r"""
set -euo pipefail
ac_online=unknown
for supply in /sys/class/power_supply/*; do
    [[ -e $supply ]] || continue
    [[ $(cat "$supply/type" 2>/dev/null || true) == Mains ]] || continue
    ac_online=$(cat "$supply/online" 2>/dev/null || echo unknown)
    break
done
config="$HOME/.local/share/Steam/config/config.vdf"
ac_suspend=$(sed -n 's/.*"IdleSuspendACSeconds"[[:space:]]*"\([0-9]*\)".*/\1/p' "$config" 2>/dev/null | tail -1)
battery_suspend=$(sed -n 's/.*"IdleSuspendBatterySeconds"[[:space:]]*"\([0-9]*\)".*/\1/p' "$config" 2>/dev/null | tail -1)
connector=unavailable
connector_state=unknown
for path in /sys/class/drm/card*-eDP-*; do
    [[ -e $path ]] || continue
    connector=${path##*/}
    connector_state=$(cat "$path/enabled" 2>/dev/null || echo unknown)
    break
done
if pgrep -f '(^|/)gamescope( |$)' >/dev/null 2>&1; then
    gamescope_state=running
else
    gamescope_state=stopped
fi
printf 'AC online: %s\n' "$ac_online"
printf 'AC idle suspend: %s seconds%s\n' "${ac_suspend:-unknown}" "$([[ ${ac_suspend:-} == 0 ]] && printf ' (disabled)' || true)"
printf 'Battery idle suspend: %s seconds%s\n' "${battery_suspend:-unknown}" "$([[ ${battery_suspend:-} == 0 ]] && printf ' (disabled)' || true)"
printf 'Gamescope: %s\n' "$gamescope_state"
printf 'Internal connector: %s (%s)\n' "$connector" "$connector_state"
printf 'SSH: reachable\n'
"""


def require_local_tools(names: Sequence[str]) -> list[str]:
    return [name for name in names if shutil.which(name) is None]


def doctor(deck: SteamDeck, as_json: bool) -> int:
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    missing = require_local_tools(["ssh", "rsync", "python3"])
    record(
        "local-tools",
        not missing,
        "available" if not missing else f"missing: {', '.join(missing)}",
    )
    status: dict[str, Any] | None = None
    if not missing:
        try:
            status = deck.status()
            record("ssh", True, f"reachable as {deck.target}")
            record(
                "steamos-status",
                status.get("os_name") == "SteamOS",
                f"{status.get('os_name', 'unknown')} {status.get('os_version', 'unknown')}",
            )
            session = str(status.get("session_status", "unknown"))
            record(
                "session",
                session in {"gamescope", "plasma-x11", "plasma-wayland"},
                session,
            )
        except (TestbedError, subprocess.CalledProcessError) as error:
            record("ssh", False, str(error))
    if status is not None:
        try:
            result = deck.remote(
                "test -x \"$HOME/devkit-utils/steamos-prepare-upload\" "
                "&& test -x \"$HOME/devkit-utils/steam-client-create-shortcut\" "
                "&& test -x \"$HOME/devkit-utils/steam-devkit-rpc\"",
                check=False,
                capture=True,
            )
            record(
                "devkit-utilities",
                result.returncode == 0,
                "installed" if result.returncode == 0 else "missing or incomplete",
            )
            panel = deck.remote(
                "for path in /sys/class/drm/card*-eDP-*/enabled; do "
                "test -e \"$path\" || continue; cat \"$path\"; exit; done; "
                "echo unavailable",
                capture=True,
            ).stdout.strip()
            record("internal-panel", panel in {"enabled", "disabled"}, panel)
        except subprocess.CalledProcessError as error:
            record("device-details", False, str(error))
    passed = all(check["ok"] for check in checks)
    if as_json:
        print(json.dumps({"ok": passed, "target": deck.target, "checks": checks}, indent=2))
    else:
        for check in checks:
            marker = "ok" if check["ok"] else "FAIL"
            print(f"[{marker:4}] {check['name']}: {check['detail']}")
        print(f"Steam Deck doctor: {'ready' if passed else 'not ready'}")
    return 0 if passed else 1


def install_screen_shortcut(deck: SteamDeck, game_id: str) -> str:
    validate_game_id(game_id)
    with tempfile.TemporaryDirectory(prefix="steamdeck-screen-shortcut-") as temporary:
        payload = Path(temporary)
        shutil.copy2(SCREEN_CONTROL, payload / SCREEN_CONTROL.name)
        shutil.copy2(SCREEN_WAKE, payload / SCREEN_WAKE.name)
        os.chmod(payload / SCREEN_CONTROL.name, 0o755)
        os.chmod(payload / SCREEN_WAKE.name, 0o755)
        manifest = GameManifest(
            path=payload / "generated.json",
            game_id=game_id,
            payload=payload,
            argv=["./screen-control.sh", "off"],
            env={},
            runtime=None,
            force_appid="",
        )
        return deck.install(manifest)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="steamdeck",
        description="Diagnose and deploy games to a physical Steam Deck.",
    )
    subcommands = result.add_subparsers(dest="command", required=True)
    subcommands.add_parser("probe", help="print one inventory session state")
    status = subcommands.add_parser("status", help="query SteamOS status")
    status.add_argument("--json", action="store_true", dest="as_json")
    diagnose = subcommands.add_parser("doctor", help="run full read-only diagnostics")
    diagnose.add_argument("--json", action="store_true", dest="as_json")
    subcommands.add_parser("power-status", help="report power and panel state")
    subcommands.add_parser("screen-off", help="sleep only the internal panel")
    subcommands.add_parser("screen-on", help="wake the internal panel")
    screen_shortcut = subcommands.add_parser(
        "screen-shortcut", help="manage the Gaming Mode screen shortcut"
    )
    screen_shortcut.add_argument("action", choices=["install"])
    screen_shortcut.add_argument("--game-id", default="screenoff")
    prepare = subcommands.add_parser(
        "prepare-upload", help="print a validated Devkit upload directory"
    )
    prepare.add_argument("game_id")
    install = subcommands.add_parser("install", help="upload and register a game")
    install.add_argument("manifest")
    register = subcommands.add_parser(
        "register", help="register an existing uploaded game"
    )
    register.add_argument("manifest")
    launch = subcommands.add_parser("launch", help="launch a Devkit Game")
    launch.add_argument("game_id")
    execute = subcommands.add_parser("exec", help="run an explicit remote command")
    execute.add_argument("argv", nargs=argparse.REMAINDER)
    push = subcommands.add_parser("push", help="copy a path to the Deck")
    push.add_argument("local")
    push.add_argument("remote")
    pull = subcommands.add_parser("pull", help="copy a path from the Deck")
    pull.add_argument("remote")
    pull.add_argument("local", nargs="?")
    subcommands.add_parser("shell", help="open an interactive SSH session")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    deck = SteamDeck()
    if args.command == "probe":
        print(deck.status().get("session_status", "unknown"))
        return 0
    if args.command == "status":
        status = deck.status()
        if args.as_json:
            print(json.dumps(status, indent=2, sort_keys=True))
        else:
            print(f"Host: {status.get('hostname', 'unknown')}")
            print(f"SteamOS: {status.get('os_version', 'unknown')}")
            print(f"Session: {status.get('session_status', 'unknown')}")
            print(f"Steam: {status.get('steam_status_description', 'unknown')}")
        return 0
    if args.command == "doctor":
        return doctor(deck, args.as_json)
    if args.command == "power-status":
        deck.remote(["bash", "-s"], input_text=POWER_STATUS_SCRIPT)
        return 0
    if args.command == "screen-off":
        deck.set_screen("off")
        return 0
    if args.command == "screen-on":
        deck.set_screen("on")
        return 0
    if args.command == "screen-shortcut":
        print(install_screen_shortcut(deck, args.game_id))
        return 0
    if args.command == "prepare-upload":
        print(deck.prepare_upload(args.game_id))
        return 0
    if args.command in {"install", "register"}:
        manifest = load_manifest(args.manifest)
        if args.command == "install":
            print(deck.install(manifest))
        else:
            remote_directory = deck.prepare_upload(manifest.game_id)
            deck.register(manifest, remote_directory)
            print(remote_directory)
        return 0
    if args.command == "launch":
        validate_game_id(args.game_id)
        deck.remote(
            [
                "python3",
                f"/home/{deck.remote_user}/devkit-utils/steam-devkit-rpc",
                "run-game",
                f"gameid={args.game_id}",
            ]
        )
        return 0
    if args.command == "exec":
        remote_argv = list(args.argv)
        if remote_argv and remote_argv[0] == "--":
            remote_argv.pop(0)
        if not remote_argv:
            raise TestbedError("exec requires a command after --")
        return deck.remote(remote_argv, check=False).returncode
    if args.command == "push":
        local = Path(args.local).expanduser()
        if not local.exists():
            raise TestbedError(f"local path not found: {local}")
        subprocess.run(
            [
                "rsync",
                "-av",
                "-e",
                shlex.join(deck.ssh_argv),
                str(local),
                f"{deck.target}:{args.remote}",
            ],
            check=True,
        )
        return 0
    if args.command == "pull":
        local = args.local or Path(PurePosixPath(args.remote).name).as_posix()
        subprocess.run(
            [
                "rsync",
                "-av",
                "-e",
                shlex.join(deck.ssh_argv),
                f"{deck.target}:{args.remote}",
                local,
            ],
            check=True,
        )
        return 0
    if args.command == "shell":
        os.execvp("ssh", [*deck.ssh_argv, deck.target])
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestbedError as error:
        print(f"steamdeck: {error}", file=sys.stderr)
        raise SystemExit(1)
    except subprocess.CalledProcessError as error:
        print(f"steamdeck: command failed with exit status {error.returncode}", file=sys.stderr)
        raise SystemExit(error.returncode or 1)
