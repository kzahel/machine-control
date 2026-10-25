from __future__ import annotations

import subprocess
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

from providers.adb import AdbClient, AdbDevice, parse_battery, parse_wake_state


class ParsingTests(unittest.TestCase):
    def test_parses_devices_and_attributes(self) -> None:
        output = (
            "List of devices attached\n"
            "SERIAL device product:sample model:Example device:sample transport_id:1\n"
            "LOCKED unauthorized usb:1-1\n"
        )
        client = object.__new__(AdbClient)
        client.adb = "adb"
        client.requested_serial = None
        with mock.patch.object(
            client,
            "run",
            return_value=subprocess.CompletedProcess(["adb"], 0, output, ""),
        ):
            devices = client.devices()
        self.assertEqual(
            devices,
            [
                AdbDevice(
                    "SERIAL",
                    "device",
                    {
                        "product": "sample",
                        "model": "Example",
                        "device": "sample",
                        "transport_id": "1",
                    },
                ),
                AdbDevice("LOCKED", "unauthorized", {"usb": "1-1"}),
            ],
        )

    def test_parses_shared_power_and_battery_state(self) -> None:
        battery = parse_battery(
            "AC powered: false\nUSB powered: true\nlevel: 42\nstatus: 2\n"
        )
        self.assertEqual(battery["level"], 42)
        self.assertTrue(battery["powered"])
        self.assertEqual(parse_wake_state("mWakefulness=Awake"), "awake")
        self.assertEqual(parse_wake_state("Wakefulness: Asleep"), "asleep")


class InputIsolationTests(unittest.TestCase):
    def test_preflight_cannot_consume_parent_secret_stdin(self) -> None:
        program = """
import json, sys
from providers.adb import AdbClient
client = object.__new__(AdbClient)
client.adb = sys.executable
child = ['-c', 'import sys; print(len(sys.stdin.buffer.read()))']
preflight = client.run(child)
secret = sys.stdin.buffer.read()
delivery = client.run(child, text=False, input_data=secret)
print(json.dumps([int(preflight.stdout), len(secret), int(delivery.stdout)]))
"""
        result = subprocess.run(
            [sys.executable, "-c", program],
            cwd=Path(__file__).resolve().parents[3],
            input=b"1234\n", capture_output=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout), [0, 5, 5])


if __name__ == "__main__":
    unittest.main()
