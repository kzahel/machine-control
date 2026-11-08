#!/usr/bin/env python3
"""Drive the MC HID app on an attached Android handheld over ADB.

The handheld acts as a Bluetooth keyboard and mouse for a paired host. ADB
access is the authority: the app publishes a loopback port and token in its
private storage, which this tool reads with `run-as` and reaches with
`adb forward`. The token is never printed, logged or passed as an argument,
and it is sent only after the service proves it holds the token.
Text to type is read from standard input only, never from argv.

Examples:
  hidctl.py --serial SERIAL install
  hidctl.py --serial SERIAL pair-floss --ssh CHROMEOS_ROOT_ALIAS
  hidctl.py --serial SERIAL status --wait-host 10
  printf 'echo hello\\n' | hidctl.py --serial SERIAL --host HOST_ADDR type
  hidctl.py --serial SERIAL --host HOST_ADDR key ctrl+alt+t
  hidctl.py --serial SERIAL move 200 -50
  hidctl.py --serial SERIAL click --button right
  hidctl.py --serial SERIAL scroll -- -3
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
from typing import Any, Callable

PACKAGE = "dev.machinecontrol.android.hid"
ARM_ACTIVITY = PACKAGE + "/.ArmActivity"
SCHEMA = "mc-android-hid/v1"
GRANT = "files/bridge.json"
PREFS = "shared_prefs/hid.xml"
APK = Path(__file__).resolve().parent / "app/build/outputs/apk/debug/app-debug.apk"
PERMISSIONS = ("BLUETOOTH_CONNECT", "BLUETOOTH_ADVERTISE", "BLUETOOTH_SCAN", "POST_NOTIFICATIONS")
MAX_TEXT = 16 * 1024
ADDRESS = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$")
INPUT_OPS = {"type", "key", "move", "scroll", "click", "button", "release"}
JSON = dict[str, Any]


class HidError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def address(value: str) -> str:
    value = value.strip().upper()
    if not ADDRESS.match(value):
        raise HidError("bad_address", "Use a Bluetooth address such as AA:BB:CC:DD:EE:FF")
    return value


class Adb:
    def __init__(self, serial: str, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> None:
        if not serial:
            raise HidError("serial_required", "Select the handheld explicitly with --serial or ANDROID_SERIAL")
        self.serial = serial
        self.runner = runner

    def run(self, *args: str, check: bool = True, timeout: float = 30) -> subprocess.CompletedProcess:
        result = self.runner(["adb", "-s", self.serial, *args], capture_output=True, timeout=timeout)
        if check and result.returncode != 0:
            # Report the command shape only; outputs may contain private device details.
            raise HidError("adb_failed", f"adb {args[0]} failed with exit status {result.returncode}")
        return result

    def private(self, path: str) -> bytes | None:
        result = self.run("exec-out", "run-as", PACKAGE, "cat", path, check=False)
        return result.stdout if result.returncode == 0 and result.stdout else None

    def grant(self) -> JSON | None:
        data = self.private(GRANT)
        if data is None:
            return None
        try:
            value = json.loads(data)
        except ValueError:
            return None
        if (value.get("schema") != SCHEMA or not isinstance(value.get("port"), int)
                or not isinstance(value.get("token"), str) or not value["token"]
                or not isinstance(value.get("generation"), str)):
            raise HidError("invalid_grant", "Unknown HID grant schema")
        return value

    def stopped_by_operator(self) -> bool:
        data = self.private(PREFS) or b""
        return b'name="operatorStopped" value="true"' in data

    def dump_ui(self) -> bytes:
        return self.run("exec-out", "uiautomator", "dump", "/dev/tty", check=False).stdout

    def tap_bounds(self, match: re.Match) -> None:
        x1, y1, x2, y2 = map(int, match.groups())
        self.run("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))


def arm(adb: Adb, timeout: float = 15, override: bool = False) -> JSON:
    """Starts or re-arms the service through the shell-only ArmActivity."""
    if adb.stopped_by_operator() and not override:
        raise HidError("stopped_by_operator", "A person pressed Stop; relaunch the app on the handheld or arm --override")
    adb.run("exec-out", "run-as", PACKAGE, "rm", "-f", GRANT, check=False)
    command = ["shell", "am", "start", "-W", "-a", PACKAGE + ".ARM", "-n", ARM_ACTIVITY]
    if override:
        command += ["--ez", "override", "true"]
    adb.run(*command)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        grant = adb.grant()
        if grant is not None:
            return grant
        time.sleep(0.3)
    raise HidError("arm_failed", "No grant appeared; unlock the handheld, check permissions and Bluetooth")


def proof(token: str, nonce: str) -> str:
    return hmac.new(token.encode(), b"mc-hid-ping:" + nonce.encode(), hashlib.sha256).hexdigest()


class Bridge:
    """One forwarded loopback connection to the app's control socket."""

    def __init__(self, adb: Adb, grant: JSON, connect: Callable[..., socket.socket] = socket.create_connection) -> None:
        self.adb = adb
        self.token = grant["token"]
        self.generation = grant["generation"]
        self.closed = False
        forwarded = adb.run("forward", "tcp:0", f"tcp:{grant['port']}").stdout.decode().strip()
        if not forwarded.isdigit():
            raise HidError("forward_failed", "adb forward did not report a local port")
        self.local = int(forwarded)
        try:
            self.connection = connect(("127.0.0.1", self.local), timeout=10)
            self.stream = self.connection.makefile("rwb")
        except BaseException:
            adb.run("forward", "--remove", f"tcp:{self.local}", check=False)
            raise

    def exchange(self, body: JSON, timeout: float) -> JSON:
        frame = json.dumps(body).encode() + b"\n"
        if len(frame) > 64 * 1024:
            raise HidError("request_too_large", "Request exceeds 64 KiB")
        self.connection.settimeout(timeout)
        self.stream.write(frame)
        self.stream.flush()
        line = self.stream.readline(1024 * 1024)
        if not line.endswith(b"\n"):
            raise HidError("bridge_lost", "No complete reply; do not replay input blindly")
        return json.loads(line)

    def verify(self) -> str:
        """Challenges the listener before the token is sent: only the real service can answer."""
        nonce = secrets.token_hex(16)
        reply = self.exchange({"op": "ping", "nonce": nonce}, timeout=10)
        if reply.get("errorCode") == "approval_denied":
            return "expired"
        if not reply.get("accepted") or not hmac.compare_digest(str(reply.get("proof", "")), proof(self.token, nonce)):
            return "impostor"
        return "verified"

    def call(self, request: JSON, timeout: float = 30) -> JSON:
        reply = self.exchange({**request, "token": self.token}, timeout)
        if reply.get("accepted") and reply.get("generation") != self.generation:
            raise HidError("bridge_lost", "Service generation changed")
        return reply

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.stream.close()
            self.connection.close()
        finally:
            self.adb.run("forward", "--remove", f"tcp:{self.local}", check=False)


def open_bridge(adb: Adb, auto_arm: bool, notes: list[str] | None = None) -> Bridge:
    """Opens a bridge to a listener proven to hold the current token.

    A grant left by a killed process points at a dead port; adb still accepts
    the forwarded connection and closes it (a direct connection is refused),
    and another app could even bind that port. The challenge happens before
    the token or any request is sent, so neither is lost or leaked; the CLI
    then re-arms, and the caller's request is sent exactly once.
    """
    grant = adb.grant()
    for _ in range(2):
        if grant is None:
            if not auto_arm:
                raise HidError("not_armed", "No grant; run arm first")
            grant = arm(adb)
        bridge = None
        try:
            bridge = Bridge(adb, grant)
            outcome = bridge.verify()
            if outcome == "verified":
                return bridge
            if outcome == "impostor" and notes is not None:
                # A listener that cannot prove the token may be a hostile app on the
                # handheld that bound a stale port. Nothing secret was sent; say so.
                notes.append("listener_failed_challenge")
        except HidError as error:
            if error.code != "bridge_lost":
                if bridge is not None:
                    bridge.close()
                raise
        except (OSError, ValueError):
            pass  # Refused or reset: nothing trustworthy listens behind this grant.
        if bridge is not None:
            bridge.close()
        if not auto_arm:
            raise HidError("not_armed", "Grant is stale or expired; run arm")
        grant = None
    raise HidError("bridge_lost", "Service did not answer after arming")


def request(adb: Adb, body: JSON, timeout: float = 30, auto_arm: bool = True) -> JSON:
    notes: list[str] = []
    bridge = open_bridge(adb, auto_arm, notes)
    try:
        reply = bridge.call(body, timeout)
    except (OSError, ValueError, HidError):
        # The request may still be waiting or running on the handheld; ask it to stop
        # so a caller that gave up never has its keystrokes delivered later.
        if body.get("op") in ("type", "key"):
            try:
                request(adb, {"op": "cancel"}, 10, auto_arm=False)
            except (OSError, ValueError, HidError):
                pass
        raise
    finally:
        bridge.close()
    if notes:
        reply["warnings"] = notes
    return reply


def read_text(stream) -> str:
    data = stream.buffer.read(MAX_TEXT * 4 + 1)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise HidError("bad_text", "Standard input is not UTF-8") from None
    if len(text) > MAX_TEXT:
        raise HidError("text_too_large", f"Type at most {MAX_TEXT} characters per call")
    return text


def type_timeout(characters: int, hold: int, gap: int) -> float:
    # Worst case per character: modifier, key and key-up holds plus the gap,
    # doubled for radio stalls and release retries.
    return 15 + characters * (3 * hold + gap) / 1000 * 2


def install(adb: Adb, apk: Path) -> JSON:
    if not apk.is_file():
        raise HidError("apk_missing", "Build the debug APK first (see README)")
    adb.run("install", "-r", str(apk), timeout=120)
    # Reinstalling kills the service; its published grant would point at a dead port.
    adb.run("exec-out", "run-as", PACKAGE, "rm", "-f", GRANT, check=False)
    for name in PERMISSIONS:
        adb.run("shell", "pm", "grant", PACKAGE, "android.permission." + name, check=False)
    return {"accepted": True, "op": "install"}


ALLOW = re.compile(rb'<node [^>]*resource-id="android:id/button1"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
PAIR = re.compile(rb'<node [^>]*text="Pair"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')


def discoverable(adb: Adb, seconds: int, allow: bool) -> JSON:
    """Requests discoverability and, if asked, accepts this app's consent dialog only."""
    adb.run("shell", "am", "start", "-a", PACKAGE + ".DISCOVERABLE", "--ei", "seconds", str(seconds),
            "-n", ARM_ACTIVITY)
    if not allow:
        return {"accepted": True, "op": "discoverable", "consent": "pending_on_device"}
    for _ in range(10):
        time.sleep(0.7)
        dump = adb.dump_ui()
        match = ALLOW.search(dump)
        # The consent dialog names the requesting app; never accept someone else's dialog.
        if match and b"MC HID" in dump:
            adb.tap_bounds(match)
            return {"accepted": True, "op": "discoverable", "consent": "allowed", "seconds": seconds}
    return {"accepted": False, "errorCode": "consent_not_found", "message": "No MC HID discoverability dialog appeared"}


def handheld_address(adb: Adb, explicit: str | None) -> str:
    """The handheld's own Bluetooth address; apps cannot read it, but ADB can."""
    if explicit:
        return address(explicit)
    value = adb.run("shell", "settings", "get", "secure", "bluetooth_address", check=False).stdout.decode().strip()
    try:
        return address(value)
    except HidError:
        raise HidError("address_unavailable", "Pass --handheld-address; the secure setting is unavailable") from None


class Floss:
    """Root shell on a ChromeOS host running the Floss Bluetooth stack."""

    PREFIX = ("timeout 15 gdbus call --system --dest org.chromium.bluetooth "
              "--object-path /org/chromium/bluetooth/hci0/adapter --method org.chromium.bluetooth.Bluetooth.")

    def __init__(self, alias: str, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> None:
        if not re.match(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$", alias):
            raise HidError("bad_alias", "Use a plain SSH alias")
        self.alias = alias
        self.runner = runner

    def run(self, command: str, method: str) -> str:
        result = self.runner(["ssh", "--", self.alias, command], capture_output=True, timeout=30)
        if result.returncode != 0:
            raise HidError("floss_failed", f"{method} failed on the host")
        return result.stdout.decode()

    def call(self, method: str, device: str, *extra: str) -> str:
        device = address(device)
        argument = f"\"{{'address': <'{device}'>, 'name': <''>}}\""
        return self.run(self.PREFIX + method + " " + " ".join((argument, *extra)), method)

    def plain(self, method: str) -> str:
        return self.run(self.PREFIX + method, method)

    def string(self, method: str) -> str:
        found = re.match(r"^\('(.*)',\)$", self.plain(method).strip())
        return found.group(1) if found else ""

    def bonded(self, device: str) -> bool:
        return device in self.plain("GetBondedDevices")

    def discover(self, device: str, seconds: float = 12) -> bool:
        """Inquiry lets Floss learn the handheld's page parameters before bonding."""
        self.plain("StartDiscovery")
        try:
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                time.sleep(2)
                if self.call("GetRemoteName", device).strip() not in ("('',)", ""):
                    return True
            return False
        finally:
            self.plain("CancelDiscovery")


def pair_floss(adb: Adb, floss: Floss, timeout: float, explicit_address: str | None = None) -> JSON:
    """Host-initiated classic pairing, the only path ChromeOS offers a phone-class device.

    Sequence proven on the testbed: make the handheld discoverable, run inquiry
    on the host, CreateBond from the host, accept numeric comparison on both
    sides, then have the host open HID itself (Floss rejects a first HID
    connection that the device starts). The handheld prompt must name this
    host and the connected host must be this host's adapter. Accepting the
    comparison without a person reading both codes is only appropriate on a
    controlled testbed.
    """
    handheld = handheld_address(adb, explicit_address)
    host_address = address(floss.string("GetAddress"))
    host_name = floss.string("GetName")
    if not host_name or '"' in host_name or "<" in host_name:
        raise HidError("host_name_unavailable", "The host reported no usable adapter name")
    if floss.bonded(handheld):
        raise HidError("already_bonded", "The host already has a bond; reconnect instead of pairing")
    if adb.grant() is None:
        arm(adb)
    allowed = discoverable(adb, 120, True)
    if not allowed.get("accepted"):
        return allowed
    if not floss.discover(handheld):
        raise HidError("not_discovered", "The host did not find the handheld during inquiry")
    floss.call("CreateBond", handheld, "1")
    deadline = time.monotonic() + timeout
    code = None
    while time.monotonic() < deadline:
        dump = adb.dump_ui()
        match = PAIR.search(dump)
        # uiautomator XML-escapes text, so compare against the unescaped dump.
        if match and host_name in html.unescape(dump.decode("utf-8", "replace")):
            digits = re.search(rb'text="(\d{6})"', dump)
            code = digits.group(1).decode() if digits else None
            adb.tap_bounds(match)
            break
        time.sleep(0.7)
    else:
        raise HidError("pairing_prompt_missing", "The handheld showed no pairing prompt naming this host")
    floss.call("SetPairingConfirmation", handheld, "true")
    while time.monotonic() < deadline and not floss.bonded(handheld):
        time.sleep(1)
    if not floss.bonded(handheld):
        raise HidError("bond_failed", "The host did not record a bond")
    floss.call("ConnectAllEnabledProfiles", handheld)
    while time.monotonic() < deadline:
        reply = request(adb, {"op": "status"})
        connected = reply.get("host") or {}
        if connected.get("address", "").upper() == host_address:
            return {"accepted": True, "op": "pair-floss", "host": connected, "comparisonCode": code}
        if connected:
            raise HidError("wrong_host", "A different host connected during pairing; unplug it and investigate")
        time.sleep(1)
    raise HidError("hid_not_connected", "Bonded, but the host did not open HID")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    root.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL", ""))
    root.add_argument("--host", default=os.environ.get("MC_HID_HOST", ""), metavar="ADDRESS",
                      help="refuse input unless this host is the connected one (required for type and key)")
    root.add_argument("--any-host", action="store_true",
                      help="allow type and key without --host, to whichever host is connected")
    root.add_argument("--no-arm", action="store_true", help="fail instead of arming when no grant exists")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("install").add_argument("--apk", type=Path, default=APK)
    arm_command = commands.add_parser("arm")
    arm_command.add_argument("--override", action="store_true", help="re-arm even after an operator Stop")
    status = commands.add_parser("status")
    status.add_argument("--wait-host", type=float, default=0, metavar="SECONDS",
                        help="poll until a host is connected, for example right after arming")
    commands.add_parser("disarm")
    commands.add_parser("cancel", help="stop a type or key request in progress")
    found = commands.add_parser("discoverable")
    found.add_argument("--seconds", type=int, default=120)
    found.add_argument("--no-allow", action="store_true", help="leave the consent dialog to a person")
    connect = commands.add_parser("connect")
    connect.add_argument("address")
    connect.add_argument("--wait-ms", type=int, default=10000)
    unplug = commands.add_parser("unplug", help="disconnect the host; Android also removes the bond")
    unplug.add_argument("--confirm-unpair", action="store_true", required=True)
    pair = commands.add_parser("pair-floss", help="pair with a ChromeOS (Floss) host reached as root over SSH")
    pair.add_argument("--ssh", required=True, metavar="ALIAS", help="SSH alias with root on the ChromeOS host")
    pair.add_argument("--timeout", type=float, default=45)
    pair.add_argument("--handheld-address", help="the handheld's Bluetooth address if ADB cannot read it")
    typed = commands.add_parser("type", help="type UTF-8 text read from stdin")
    typed.add_argument("--layout", choices=("us", "dvorak"), default="us")
    typed.add_argument("--hold-ms", type=int, default=12)
    typed.add_argument("--gap-ms", type=int, default=12)
    key = commands.add_parser("key", help="press chords such as ctrl+alt+t, enter, search")
    key.add_argument("chords", nargs="+")
    key.add_argument("--layout", choices=("us", "dvorak"), default="us")
    move = commands.add_parser("move")
    move.add_argument("dx", type=int)
    move.add_argument("dy", type=int)
    click = commands.add_parser("click")
    click.add_argument("--button", choices=("left", "right", "middle"), default="left")
    click.add_argument("--count", type=int, default=1)
    scroll = commands.add_parser("scroll", help="positive scrolls up, negative down")
    scroll.add_argument("wheel", type=int)
    scroll.add_argument("--pan", type=int, default=0)
    button = commands.add_parser("button", help="hold or release a button for drags (auto-released after 15 s)")
    button.add_argument("button", choices=("left", "right", "middle"))
    button.add_argument("state", choices=("down", "up"))
    commands.add_parser("release", help="cancel typing and release every key and button")
    return root


def run(args: argparse.Namespace, adb: Adb, stdin=sys.stdin) -> JSON:
    auto = not args.no_arm
    command = args.command

    def send(body: JSON, timeout: float = 30) -> JSON:
        if body["op"] in INPUT_OPS and body["op"] != "release":
            if args.host:
                body = {**body, "expectHost": address(args.host)}
            elif body["op"] in ("type", "key") and not args.any_host:
                raise HidError("host_required", "Name the intended host with --host (or MC_HID_HOST), or pass --any-host")
        return request(adb, body, timeout, auto)

    if command == "install":
        return install(adb, args.apk)
    if command == "arm":
        grant = arm(adb, override=args.override)
        return {"accepted": True, "op": "arm", "generation": grant["generation"]}
    if command == "discoverable":
        if auto and adb.grant() is None:
            arm(adb)
        return discoverable(adb, args.seconds, not args.no_allow)
    if command == "pair-floss":
        return pair_floss(adb, Floss(args.ssh), args.timeout, args.handheld_address)
    if command == "type":
        text = read_text(stdin)
        body = {"op": "type", "text": text, "layout": args.layout, "holdMs": args.hold_ms, "gapMs": args.gap_ms}
        return send(body, type_timeout(len(text), args.hold_ms, args.gap_ms))
    if command == "status":
        deadline = time.monotonic() + args.wait_host
        while True:
            reply = send({"op": "status"})
            if reply.get("host") or not reply.get("accepted") or time.monotonic() >= deadline:
                return reply
            time.sleep(0.5)
    if command == "disarm":
        return request(adb, {"op": "disarm"}, auto_arm=False)
    if command == "cancel":
        return request(adb, {"op": "cancel"}, auto_arm=False)
    if command == "unplug":
        return send({"op": "unplug", "confirmUnpair": True})
    if command == "connect":
        return send({"op": "connect", "address": address(args.address), "waitMs": args.wait_ms},
                    timeout=args.wait_ms / 1000 + 10)
    bodies: dict[str, JSON] = {
        "release": {"op": "release"},
        "key": {"op": "key", "chords": getattr(args, "chords", None), "layout": getattr(args, "layout", "us")},
        "move": {"op": "move", "dx": getattr(args, "dx", 0), "dy": getattr(args, "dy", 0)},
        "click": {"op": "click", "button": getattr(args, "button", "left"), "count": getattr(args, "count", 1)},
        "scroll": {"op": "scroll", "wheel": getattr(args, "wheel", 0), "pan": getattr(args, "pan", 0)},
        "button": {"op": "button", "button": getattr(args, "button", "left"),
                   "down": getattr(args, "state", "") == "down"},
    }
    if command in bodies:
        return send(bodies[command])
    raise HidError("unsupported", "Unknown command")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        reply = run(args, Adb(args.serial))
    except HidError as error:
        reply = {"accepted": False, "errorCode": error.code, "message": str(error)}
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        reply = {"accepted": False, "errorCode": type(error).__name__, "message": "Transport failed; observe before retrying"}
    reply.pop("token", None)
    print(json.dumps(reply, indent=2))
    return 0 if reply.get("accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
