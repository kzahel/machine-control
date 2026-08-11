from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import quest


def completed(
    argv: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout, stderr)


class SelectionClient(quest.AdbClient):
    def __init__(
        self, devices: list[quest.AdbDevice], requested: str | None = None
    ) -> None:
        self.adb = "adb"
        self.requested_serial = requested
        self._devices = devices

    def devices(self) -> list[quest.AdbDevice]:
        return self._devices

    def quest_like(self, device: quest.AdbDevice) -> bool:
        return device.attributes.get("model") == "Quest_3"


class FakeClient:
    def __init__(self) -> None:
        self.adb = "adb"
        self.settings: dict[tuple[str, str], str] = {
            ("global", "stay_on_while_plugged_in"): "0",
            ("secure", "skip_launch_check_requires_controllers_enabled"): "0",
        }
        self.proximity = "0"
        self.remote_files: dict[str, str] = {}
        self.commands: list[tuple[str, ...]] = []
        self.battery_level = 80
        self.powered = True

    def shell_text(
        self, serial: str, argv: list[str], *, check: bool = True
    ) -> str:
        del serial, check
        if argv[:2] == ["settings", "get"]:
            return self.settings.get((argv[2], argv[3]), "null")
        if argv[:2] == ["getprop", "sys.boot_completed"]:
            return "1"
        if argv[:2] == ["getprop", "debug.oculus.disableProximity"]:
            return self.proximity
        if argv[:2] == ["getprop", "ro.product.manufacturer"]:
            return "Meta"
        if argv[:2] == ["getprop", "ro.product.model"]:
            return "Quest 3"
        if argv[:2] == ["getprop", "ro.product.name"]:
            return "eureka"
        if argv[:2] == ["getprop", "ro.build.version.sdk"]:
            return "32"
        if argv[:2] == ["getprop", "ro.product.cpu.abi"]:
            return "arm64-v8a"
        if argv == ["dumpsys", "power"]:
            return "mWakefulness=Asleep"
        if argv == ["dumpsys", "battery"]:
            powered = "true" if self.powered else "false"
            return f"USB powered: {powered}\nlevel: {self.battery_level}\nstatus: 3\n"
        if argv == ["dumpsys", "activity", "activities"]:
            return ""
        return ""

    def shell(
        self,
        serial: str,
        argv: list[str],
        *,
        check: bool = True,
        capture: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        del serial, capture
        self.commands.append(tuple(argv))
        returncode = 0
        stdout = ""
        if argv[:2] == ["settings", "get"]:
            stdout = self.settings.get((argv[2], argv[3]), "null") + "\n"
        elif argv[:2] == ["settings", "put"]:
            self.settings[(argv[2], argv[3])] = argv[4]
        elif argv[:2] == ["settings", "delete"]:
            self.settings.pop((argv[2], argv[3]), None)
        elif argv[:2] == ["setprop", "debug.oculus.disableProximity"]:
            self.proximity = argv[2]
        elif argv[0] == "cat":
            if argv[1] in self.remote_files:
                stdout = self.remote_files[argv[1]]
            else:
                returncode = 1
        elif argv[0] == "mv":
            self.remote_files[argv[2]] = self.remote_files.pop(argv[1])
        elif argv[:2] == ["rm", "-f"]:
            self.remote_files.pop(argv[2], None)
        result = completed(argv, returncode, stdout)
        if check and returncode:
            raise subprocess.CalledProcessError(returncode, argv)
        return result

    def run(
        self,
        argv: list[str],
        *,
        serial: str | None = None,
        check: bool = True,
        capture: bool = True,
        text: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        del serial, capture, text
        self.commands.append(tuple(argv))
        if argv[0] == "push":
            self.remote_files[argv[2]] = Path(argv[1]).read_text(encoding="utf-8")
        result = completed(argv)
        if check and result.returncode:
            raise subprocess.CalledProcessError(result.returncode, argv)
        return result


class DeviceSelectionTests(unittest.TestCase):
    def test_selects_one_quest_and_ignores_emulator(self) -> None:
        client = SelectionClient(
            [
                quest.AdbDevice("emulator-5554", "device", {"model": "sdk"}),
                quest.AdbDevice("QUEST123", "device", {"model": "Quest_3"}),
            ]
        )
        self.assertEqual(client.select_quest(), "QUEST123")

    def test_requires_serial_for_multiple_quests(self) -> None:
        client = SelectionClient(
            [
                quest.AdbDevice("ONE", "device", {"model": "Quest_3"}),
                quest.AdbDevice("TWO", "device", {"model": "Quest_3"}),
            ]
        )
        with self.assertRaisesRegex(quest.TestbedError, "multiple Quest"):
            client.select_quest()

    def test_reports_unauthorized_device(self) -> None:
        client = SelectionClient([quest.AdbDevice("QUEST123", "unauthorized", {})])
        with self.assertRaisesRegex(quest.TestbedError, "RSA prompt"):
            client.select_quest()

    def test_rejects_explicit_non_quest(self) -> None:
        client = SelectionClient(
            [quest.AdbDevice("PHONE", "device", {"model": "Pixel_9"})], "PHONE"
        )
        with self.assertRaisesRegex(quest.TestbedError, "not recognized as a Quest"):
            client.select_quest()


class StatusParsingTests(unittest.TestCase):
    def test_parses_battery_and_power_source(self) -> None:
        result = quest.parse_battery(
            "AC powered: false\nUSB powered: true\nlevel: 42\nstatus: 2\n"
        )
        self.assertEqual(result["level"], 42)
        self.assertTrue(result["powered"])

    def test_parses_android_wakefulness(self) -> None:
        self.assertEqual(quest.parse_wake_state("mWakefulness=Awake"), "awake")
        self.assertEqual(quest.parse_wake_state("Wakefulness: Asleep"), "asleep")

    def test_reverse_requires_explicit_mapping(self) -> None:
        self.assertEqual(
            quest.normalize_reverse("tcp:9757=tcp:9757"),
            ("tcp:9757", "tcp:9757"),
        )
        with self.assertRaises(quest.TestbedError):
            quest.normalize_reverse("tcp:9757")

    def test_common_doctor_is_device_shaped_and_minimized(self) -> None:
        client = FakeClient()
        payload, ok = quest.doctor_payload(client, "PRIVATE-SERIAL")  # type: ignore[arg-type]
        document = quest.common_doctor_document(payload, ok)
        self.assertEqual(document["target"]["kind"], "device")
        self.assertEqual(document["target"]["platformFamily"], "android")
        self.assertEqual(document["states"]["connection"], "ready")
        self.assertNotIn("PRIVATE-SERIAL", json.dumps(document))


class LifecycleTests(unittest.TestCase):
    @mock.patch("quest.controller_name", return_value="test-controller")
    def test_lease_restores_settings_proximity_reverse_and_sleep(
        self, _controller: mock.Mock
    ) -> None:
        client = FakeClient()
        journal = quest.begin_lease(
            client,  # type: ignore[arg-type]
            "QUEST123",
            mode="external",
            owner_pid=os.getpid(),
            stop_packages=["com.example.game"],
            reverses=[("tcp:9757", "tcp:9757")],
            min_battery=15,
            sleep_on_end=True,
            wake=True,
            disable_proximity=True,
            should_dismiss_dialogs=False,
        )
        self.assertEqual(client.proximity, "1")
        self.assertEqual(
            client.settings[("global", "stay_on_while_plugged_in")], "3"
        )
        self.assertIn(quest.REMOTE_JOURNAL, client.remote_files)

        self.assertTrue(
            quest.restore_journal(  # type: ignore[arg-type]
                client, "QUEST123", journal
            )
        )
        self.assertEqual(client.proximity, "0")
        self.assertEqual(
            client.settings[("global", "stay_on_while_plugged_in")], "0"
        )
        self.assertNotIn(
            ("global", "require_controllers_for_vr_apps"), client.settings
        )
        self.assertNotIn(quest.REMOTE_JOURNAL, client.remote_files)
        self.assertIn(("am", "force-stop", "com.example.game"), client.commands)
        self.assertIn(("reverse", "--remove", "tcp:9757"), client.commands)
        self.assertIn(("input", "keyevent", "KEYCODE_SLEEP"), client.commands)

    @mock.patch("quest.controller_name", return_value="test-controller")
    def test_low_unpowered_battery_refuses_lease(self, _controller: mock.Mock) -> None:
        client = FakeClient()
        client.battery_level = 10
        client.powered = False
        with self.assertRaisesRegex(quest.TestbedError, "10%"):
            quest.begin_lease(
                client,  # type: ignore[arg-type]
                "QUEST123",
                mode="external",
                owner_pid=os.getpid(),
                stop_packages=[],
                reverses=[],
                min_battery=15,
                sleep_on_end=True,
                wake=True,
                disable_proximity=True,
                should_dismiss_dialogs=False,
            )
        self.assertNotIn(quest.REMOTE_JOURNAL, client.remote_files)

    @mock.patch("quest.controller_name", return_value="new-controller")
    def test_foreign_journal_is_not_silently_recovered(
        self, _controller: mock.Mock
    ) -> None:
        client = FakeClient()
        client.remote_files[quest.REMOTE_JOURNAL] = json.dumps(
            {
                "schema": quest.JOURNAL_SCHEMA,
                "token": "foreign",
                "controller": "other-controller",
                "owner_pid": 1,
                "mode": "external",
            }
        )
        with self.assertRaisesRegex(quest.TestbedError, "recover --force"):
            quest.begin_lease(
                client,  # type: ignore[arg-type]
                "QUEST123",
                mode="external",
                owner_pid=os.getpid(),
                stop_packages=[],
                reverses=[],
                min_battery=15,
                sleep_on_end=True,
                wake=True,
                disable_proximity=True,
                should_dismiss_dialogs=False,
            )

    @mock.patch("quest.controller_name", return_value="test-controller")
    @mock.patch("quest.pid_is_alive", return_value=False)
    def test_same_controller_stale_journal_is_recovered_before_new_lease(
        self, _alive: mock.Mock, _controller: mock.Mock
    ) -> None:
        client = FakeClient()
        old = quest.new_journal(
            client,  # type: ignore[arg-type]
            "QUEST123",
            mode="external",
            owner_pid=99999,
            stop_packages=[],
            reverses=[],
            sleep_on_end=True,
        )
        client.remote_files[quest.REMOTE_JOURNAL] = json.dumps(old)
        new = quest.begin_lease(
            client,  # type: ignore[arg-type]
            "QUEST123",
            mode="external",
            owner_pid=os.getpid(),
            stop_packages=[],
            reverses=[],
            min_battery=15,
            sleep_on_end=True,
            wake=True,
            disable_proximity=True,
            should_dismiss_dialogs=False,
        )
        self.assertNotEqual(old["token"], new["token"])
        persisted = json.loads(client.remote_files[quest.REMOTE_JOURNAL])
        self.assertEqual(persisted["token"], new["token"])


class LockTests(unittest.TestCase):
    @mock.patch("quest.controller_name", return_value="test-controller")
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_stale_local_lock_is_replaced(self, _controller: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.dict(
                os.environ, {"QUEST_TESTBED_STATE_DIR": temporary}, clear=False
            ):
                path = Path(temporary) / "locks" / "QUEST123.lock"
                path.mkdir(parents=True)
                (path / "owner.json").write_text(
                    json.dumps(
                        {"controller": "test-controller", "pid": 999999, "token": "old"}
                    ),
                    encoding="utf-8",
                )
                lock = quest.LocalLock("QUEST123", "new")
                lock.acquire()
                owner = json.loads((path / "owner.json").read_text(encoding="utf-8"))
                self.assertEqual(owner["token"], "new")
                lock.release()
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
