from __future__ import annotations

import subprocess
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


if __name__ == "__main__":
    unittest.main()
