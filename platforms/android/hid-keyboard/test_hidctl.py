#!/usr/bin/env python3
"""Host-side tests for hidctl: transport, grant handling and argument hygiene.

A local socket server stands in for the app's control socket and a fake ADB
runner stands in for the device, so no handheld is needed.
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hidctl  # noqa: E402

TOKEN = "secret-token-value"


class FakeApp:
    """Minimal line-JSON control socket with the app's authentication rule."""

    def __init__(self, token: str = TOKEN, generation: str = "gen-1") -> None:
        self.token = token
        self.generation = generation
        self.requests: list[dict] = []
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self.accept, daemon=True).start()

    def accept(self) -> None:
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            with connection, connection.makefile("rwb") as stream:
                for line in stream:
                    request = json.loads(line)
                    self.requests.append(request)
                    if "token" not in request:
                        # Challenge: prove possession of the token without revealing it.
                        reply = {"accepted": True, "op": "ping",
                                 "proof": hidctl.proof(self.token, request["nonce"])}
                    elif request.get("token") != self.token:
                        reply = {"accepted": False, "errorCode": "approval_denied"}
                    else:
                        reply = {"accepted": True, "op": request["op"], "host": {"address": "AA"},
                                 "generation": self.generation}
                    stream.write(json.dumps(reply).encode() + b"\n")
                    stream.flush()

    def close(self) -> None:
        self.server.close()


class FakeAdb:
    """Records ADB invocations; serves grants and identity port forwards."""

    def __init__(self, grants: list[dict | None], prefs: bytes | None = None) -> None:
        self.grants = grants
        self.prefs = prefs
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], capture_output: bool, timeout: float) -> subprocess.CompletedProcess:
        self.calls.append(argv)
        args = argv[3:]
        out = b""
        code = 0
        if args[:5] == ["exec-out", "run-as", hidctl.PACKAGE, "cat", hidctl.PREFS]:
            code, out = (0, self.prefs) if self.prefs else (1, b"")
        elif args[:4] == ["exec-out", "run-as", hidctl.PACKAGE, "cat"]:
            grant = self.grants[0] if self.grants else None
            if grant is None:
                code = 1
            else:
                out = json.dumps(grant).encode()
        elif args[:2] == ["forward", "tcp:0"]:
            out = args[2].split(":")[1].encode() + b"\n"
        elif args[:3] == ["shell", "am", "start"]:
            # Arming replaces the published grant with the next one.
            if len(self.grants) > 1:
                self.grants.pop(0)
        return subprocess.CompletedProcess(argv, code, out, b"")


def grant(app: FakeApp, port: int | None = None, token: str = TOKEN) -> dict:
    return {"schema": hidctl.SCHEMA, "port": port or app.port, "token": token, "generation": app.generation}


def dead_port() -> int:
    probe = socket.create_server(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class HidctlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FakeApp()
        self.addCleanup(self.app.close)

    def run_cli(self, argv: list[str], adb: FakeAdb, stdin: bytes = b"") -> tuple[dict, str]:
        args = hidctl.parser().parse_args(argv)
        output = io.StringIO()
        fake_stdin = io.TextIOWrapper(io.BytesIO(stdin), encoding="utf-8")
        with contextlib.redirect_stdout(output):
            reply = hidctl.run(args, hidctl.Adb("SERIAL", runner=adb), stdin=fake_stdin)
        return reply, output.getvalue()

    def test_type_reads_stdin_and_never_exposes_text_or_token_in_argv(self) -> None:
        adb = FakeAdb([grant(self.app)])
        reply, _ = self.run_cli(["--any-host", "type"], adb, stdin="pa$$ word\n".encode())
        self.assertTrue(reply["accepted"])
        typed = [r for r in self.app.requests if r["op"] == "type"]
        self.assertEqual(typed[0]["text"], "pa$$ word\n")
        flattened = " ".join(" ".join(call) for call in adb.calls)
        self.assertNotIn("pa$$", flattened)
        self.assertNotIn(TOKEN, flattened)
        self.assertNotIn(TOKEN, json.dumps(reply))

    def test_type_and_key_require_a_named_host(self) -> None:
        adb = FakeAdb([grant(self.app)])
        for argv in (["type"], ["key", "enter"]):
            with self.assertRaises(hidctl.HidError) as caught:
                self.run_cli(argv, adb, stdin=b"x")
            self.assertEqual(caught.exception.code, "host_required")
        self.assertEqual(self.app.requests, [])

    def test_bad_host_only_affects_input(self) -> None:
        adb = FakeAdb([grant(self.app)])
        reply, _ = self.run_cli(["--host", "garbage", "status"], adb)
        self.assertTrue(reply["accepted"])
        reply, _ = self.run_cli(["--host", "garbage", "release"], adb)
        self.assertNotIn("expectHost", self.app.requests[-1])

    def test_type_has_no_text_argument(self) -> None:
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            hidctl.parser().parse_args(["type", "hello"])

    def test_stale_grant_is_rearmed_before_the_request_is_sent(self) -> None:
        adb = FakeAdb([grant(self.app, port=dead_port()), grant(self.app)])
        reply, _ = self.run_cli(["--any-host", "key", "enter"], adb)
        self.assertTrue(reply["accepted"])
        self.assertEqual([r["op"] for r in self.app.requests], ["ping", "key"])
        self.assertTrue(any(call[3:6] == ["shell", "am", "start"] and hidctl.ARM_ACTIVITY in call
                            for call in adb.calls))

    def test_impostor_on_stale_port_never_receives_token_or_text(self) -> None:
        impostor = FakeApp(token="impostor-does-not-know-it")
        self.addCleanup(impostor.close)
        adb = FakeAdb([grant(impostor, token=TOKEN), grant(self.app)])
        reply, _ = self.run_cli(["--any-host", "type"], adb, stdin=b"secret text")
        self.assertTrue(reply["accepted"])
        self.assertEqual(reply["warnings"], ["listener_failed_challenge"])
        self.assertEqual([r["op"] for r in impostor.requests], ["ping"])
        self.assertNotIn(TOKEN, json.dumps(impostor.requests))
        self.assertEqual([r["op"] for r in self.app.requests], ["ping", "type"])

    def test_rotated_token_rearms_once(self) -> None:
        adb = FakeAdb([grant(self.app, token="old"), grant(self.app)])
        reply, _ = self.run_cli(["click"], adb)
        self.assertTrue(reply["accepted"])
        self.assertEqual([r["op"] for r in self.app.requests], ["ping", "ping", "click"])

    def test_operator_stop_blocks_auto_arm(self) -> None:
        prefs = b'<map><boolean name="operatorStopped" value="true" /></map>'
        adb = FakeAdb([None], prefs=prefs)
        with self.assertRaises(hidctl.HidError) as caught:
            self.run_cli(["status"], adb)
        self.assertEqual(caught.exception.code, "stopped_by_operator")
        self.assertFalse(any(call[3:6] == ["shell", "am", "start"] for call in adb.calls))

    def test_expected_host_is_sent_with_input_only(self) -> None:
        adb = FakeAdb([grant(self.app)])
        self.run_cli(["--host", "aa:bb:cc:dd:ee:ff", "move", "1", "1"], adb)
        self.assertEqual(self.app.requests[-1]["expectHost"], "AA:BB:CC:DD:EE:FF")
        self.run_cli(["--host", "AA:BB:CC:DD:EE:FF", "status"], adb)
        self.assertNotIn("expectHost", self.app.requests[-1])
        with self.assertRaises(hidctl.HidError):
            self.run_cli(["--host", "not-an-address", "click"], adb)

    def test_no_arm_refuses_instead_of_arming(self) -> None:
        adb = FakeAdb([None])
        with self.assertRaises(hidctl.HidError) as caught:
            self.run_cli(["--no-arm", "status"], adb)
        self.assertEqual(caught.exception.code, "not_armed")
        self.assertFalse(any(call[3:6] == ["shell", "am", "start"] for call in adb.calls))

    def test_forwards_are_removed(self) -> None:
        adb = FakeAdb([grant(self.app)])
        self.run_cli(["move", "5", "-5"], adb)
        removed = [call for call in adb.calls if call[3:5] == ["forward", "--remove"]]
        self.assertEqual(len(removed), 1)

    def test_unplug_requires_explicit_confirmation(self) -> None:
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            hidctl.parser().parse_args(["unplug"])
        adb = FakeAdb([grant(self.app)])
        self.run_cli(["unplug", "--confirm-unpair"], adb)
        self.assertEqual(self.app.requests[-1]["confirmUnpair"], True)

    def test_transport_switch_sends_only_a_known_mode(self) -> None:
        adb = FakeAdb([grant(self.app)])
        reply, _ = self.run_cli(["transport", "ble"], adb)
        self.assertTrue(reply["accepted"])
        self.assertEqual(self.app.requests[-1]["op"], "transport")
        self.assertEqual(self.app.requests[-1]["mode"], "ble")
        self.assertNotIn("unpin", self.app.requests[-1])
        self.run_cli(["transport", "ble", "--unpin"], adb)
        self.assertTrue(self.app.requests[-1]["unpin"])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            hidctl.parser().parse_args(["transport", "usb"])

    def test_serial_is_required(self) -> None:
        with self.assertRaises(hidctl.HidError):
            hidctl.Adb("")

    def test_grant_schema_is_checked(self) -> None:
        adb = FakeAdb([{"schema": "other", "port": 1, "token": "x"}])
        with self.assertRaises(hidctl.HidError):
            hidctl.Adb("SERIAL", runner=adb).grant()

    def test_floss_rejects_unsafe_alias_and_address(self) -> None:
        for alias in ("host; rm -rf /", "-oProxyCommand=x"):
            with self.assertRaises(hidctl.HidError):
                hidctl.Floss(alias)
        calls: list[list[str]] = []

        def runner(argv, capture_output, timeout):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, b"(true,)", b"")

        floss = hidctl.Floss("testbed", runner=runner)
        with self.assertRaises(hidctl.HidError):
            floss.call("CreateBond", "AA:BB:CC:DD:EE:FF'; reboot; '", "1")
        floss.call("CreateBond", "AA:BB:CC:DD:EE:FF", "1")
        self.assertEqual(calls[-1][:3], ["ssh", "--", "testbed"])
        self.assertIn("'address': <'AA:BB:CC:DD:EE:FF'>", calls[-1][3])

    def test_type_timeout_grows_with_text(self) -> None:
        self.assertGreater(hidctl.type_timeout(1000, 12, 12), hidctl.type_timeout(10, 12, 12))
        self.assertGreater(hidctl.type_timeout(1000, 12, 12), 1000 * 36 / 1000)

    def test_invalid_utf8_is_reported_as_bad_text(self) -> None:
        adb = FakeAdb([grant(self.app)])
        with self.assertRaises(hidctl.HidError) as caught:
            self.run_cli(["--any-host", "type"], adb, stdin=b"\xff\xfe")
        self.assertEqual(caught.exception.code, "bad_text")

    def test_grant_without_generation_is_rejected(self) -> None:
        adb = FakeAdb([{"schema": hidctl.SCHEMA, "port": 1, "token": "x"}])
        with self.assertRaises(hidctl.HidError):
            hidctl.Adb("SERIAL", runner=adb).grant()

    def test_main_reports_errors_as_json(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = hidctl.main(["--serial", "", "status"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["errorCode"], "serial_required")


if __name__ == "__main__":
    unittest.main()
