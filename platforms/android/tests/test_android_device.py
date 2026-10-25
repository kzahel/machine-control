from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import android_device


class SelectionClient(android_device.AndroidClient):
    def __init__(
        self,
        devices: list[android_device.AdbDevice],
        requested: str | None = None,
    ) -> None:
        self.adb = "adb"
        self.requested_serial = requested
        self._devices = devices

    def devices(self) -> list[android_device.AdbDevice]:
        return self._devices

    def handheld_like(self, device: android_device.AdbDevice) -> bool:
        return device.attributes.get("class") == "handheld"


class FakeUnlockClient:
    def select_handheld(self) -> str:
        return "PRIVATE-SERIAL"

    def shell(self, *_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["adb"], 0, "", "")


def config(root: Path) -> android_device.Config:
    return android_device.Config(
        serial="PRIVATE-SERIAL",
        adb_path="adb",
        state_dir=root / "state",
        sdk_root=root / "sdk",
    )


def locked_status(*, wipe: int | None = 0, credential: str = "pin") -> dict:
    return {
        "currentUserId": 0,
        "bootCompleted": True,
        "bootGeneration": "android-generation",
        "wakeState": "awake",
        "userState": "RUNNING_UNLOCKED",
        "userUnlocked": True,
        "apiLevel": "35",
        "battery": {},
        "interaction": "protected",
        "keyguard": {
            "showing": True,
            "deviceLocked": True,
            "secure": credential != "none",
            "credentialKind": credential,
        },
        "maximumFailedPasswordsForWipe": wipe,
    }


def unlocked_status() -> dict:
    value = locked_status()
    value["interaction"] = "unlocked"
    value["keyguard"] = {
        "showing": False,
        "deviceLocked": False,
        "secure": True,
        "credentialKind": "pin",
    }
    return value


class SelectionTests(unittest.TestCase):
    def test_selects_one_authorized_physical_handheld(self) -> None:
        client = SelectionClient(
            [
                android_device.AdbDevice(
                    "PHONE", "device", {"class": "handheld"}
                ),
                android_device.AdbDevice(
                    "QUEST", "device", {"class": "headset"}
                ),
            ]
        )
        self.assertEqual(client.select_handheld(), "PHONE")

    def test_refuses_ambiguous_handheld_selection(self) -> None:
        client = SelectionClient(
            [
                android_device.AdbDevice("ONE", "device", {"class": "handheld"}),
                android_device.AdbDevice("TWO", "device", {"class": "handheld"}),
            ]
        )
        with self.assertRaisesRegex(android_device.TestbedError, "multiple"):
            client.select_handheld()

    def test_explicit_quest_is_not_treated_as_handheld(self) -> None:
        client = SelectionClient(
            [android_device.AdbDevice("QUEST", "device", {"class": "headset"})],
            requested="QUEST",
        )
        with self.assertRaisesRegex(android_device.TestbedError, "not an eligible"):
            client.select_handheld()


class StateParsingTests(unittest.TestCase):
    def test_parses_current_user_lock_and_credential(self) -> None:
        self.assertEqual(
            android_device.parse_user_state(
                "Started users state: [0=RUNNING_UNLOCKED]", 0
            ),
            "RUNNING_UNLOCKED",
        )
        self.assertTrue(
            android_device.parse_device_locked(
                'User "example" (id=0, flags=0x1): deviceLocked=1', 0
            )
        )
        self.assertEqual(
            android_device.parse_credential_kind(
                "User 0\n    CredentialType: PIN\nUser 10\n    CredentialType: Password",
                0,
            ),
            "pin",
        )

    def test_pin_surface_requires_known_secure_field(self) -> None:
        field = (
            '<node package="com.android.systemui" '
            'resource-id="com.android.systemui:id/pinEntry" '
            'password="true" enabled="true" text=""/>'
        )
        for xml, expected in [
            (f"<hierarchy>{field}</hierarchy>", True),
            (f"<hierarchy>{field}{field}</hierarchy>", False),
            (field.replace('package="com.android.systemui"', 'package="example.app"'), False),
            (field.replace('password="true"', 'password="false"'), False),
            (field.replace('enabled="true"', 'enabled="false"'), False),
            (field.replace('text=""', 'text="•"'), False),
            ("not an XML hierarchy", False),
        ]:
            with self.subTest(xml=xml):
                client = mock.Mock()
                client.shell.side_effect = [
                    subprocess.CompletedProcess([], 0, "", ""),
                    subprocess.CompletedProcess([], 0, "", ""),
                    subprocess.CompletedProcess([], 0, "dumped to file", ""),
                    subprocess.CompletedProcess([], 0, xml, ""),
                    subprocess.CompletedProcess([], 0, "", ""),
                ]
                self.assertEqual(android_device.pin_surface_visible(client, "PHONE"), expected)
                dump = client.shell.call_args_list[2].args[1]
                self.assertNotEqual(dump[2], "/dev/tty")
                self.assertEqual(client.shell.call_args_list[-1].args[1], ["rm", "-f", dump[2]])

    def test_failed_hierarchy_dump_is_cleaned_up(self) -> None:
        client = mock.Mock()
        client.shell.side_effect = [
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.TimeoutExpired([], 15),
            subprocess.CompletedProcess([], 0, "", ""),
        ]
        self.assertFalse(android_device.pin_surface_visible(client, "PHONE"))
        self.assertEqual(client.shell.call_args_list[-1].args[1][:2], ["rm", "-f"])

    def test_any_positive_wipe_policy_fails_safe(self) -> None:
        self.assertEqual(
            android_device.parse_maximum_failed_passwords(
                "maximumFailedPasswordsForWipe=0\n"
                "maximumFailedPasswordsForWipe=10"
            ),
            10,
        )


class CredentialFileTests(unittest.TestCase):
    def test_reads_one_pin_and_rejects_trailing_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            path = root / "unlock.secret"
            for value, expected in [
                (b"1234", True), (b"1234\n", True), (b"1234\r\n", True),
                (b"1234\n5678", False), (b"1234\n" + b"\n" * 100, False),
                (b" 1234", False), (b"", False),
            ]:
                with self.subTest(valid=expected):
                    path.write_bytes(value)
                    path.chmod(0o600)
                    if expected:
                        result = android_device.read_pin_file(path)
                        self.assertEqual(result, bytearray(b"1234"))
                        result[:] = b"\0" * len(result)
                    else:
                        with self.assertRaises(android_device.TestbedError) as caught:
                            android_device.read_pin_file(path)
                        self.assertNotIn("1234", str(caught.exception))

    @unittest.skipIf(os.name == "nt", "POSIX permission checks")
    def test_refuses_unsafe_permissions_and_symlink_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            path = root / "unlock.secret"
            path.write_bytes(b"1234")
            path.chmod(0o644)
            with mock.patch("android_device.os.fdopen", side_effect=AssertionError("must not read")):
                with self.assertRaises(android_device.TestbedError):
                    android_device.read_pin_file(path)
                path.chmod(0o600)
                root.chmod(0o755)
                with self.assertRaises(android_device.TestbedError):
                    android_device.read_pin_file(path)
                root.chmod(0o700)
                link = root / "alias.secret"
                link.symlink_to(path)
                with self.assertRaises(android_device.TestbedError):
                    android_device.read_pin_file(link)

    def test_configured_file_requires_an_explicit_device(self) -> None:
        with self.assertRaises(android_device.TestbedError):
            android_device.load_config({"ANDROID_TESTBED_PIN_FILE": "/private/example.secret"})


class UnlockTests(unittest.TestCase):
    @mock.patch("android_device.time.sleep")
    @mock.patch("android_device.stage_secret_helper")
    @mock.patch("android_device.pin_surface_visible", return_value=True)
    @mock.patch("android_device.AndroidClient", return_value=FakeUnlockClient())
    def test_first_unlock_does_not_require_user_storage_already_unlocked(
        self, _client, _surface, _stage, _sleep
    ) -> None:
        before = locked_status()
        before.update(userState="RUNNING_LOCKED", userUnlocked=False)
        delivery = mock.Mock(return_value=subprocess.CompletedProcess([], 0, b"", b""))
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "android_device.device_status", side_effect=[before, before, unlocked_status()]
        ):
            result = android_device.unlock_pin(
                config(Path(directory)), secret_reader=lambda: bytearray(b"1234"),
                helper_builder=lambda _cfg: Path("helper.jar"), deliverer=delivery,
            )
        delivery.assert_called_once()
        self.assertEqual(result["effect"], "confirmed")
        self.assertEqual(result["evidence"]["userStorage"], "unlocked")

    @mock.patch("android_device.read_pin_file", side_effect=AssertionError("must not open"))
    @mock.patch("android_device.AndroidClient", return_value=FakeUnlockClient())
    def test_configured_file_is_not_opened_when_unlocked_or_preflight_refuses(self, _client, reader) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cfg = replace(config(Path(directory)), pin_file=Path(directory) / "missing.secret")
            for before in (unlocked_status(), locked_status(credential="password"), locked_status(wipe=5)):
                with mock.patch("android_device.device_status", return_value=before):
                    result = android_device.unlock_pin(cfg)
                self.assertEqual(result["data"]["attempts"], 0)
        reader.assert_not_called()

    @mock.patch("android_device.time.sleep")
    @mock.patch("android_device.stage_secret_helper")
    @mock.patch("android_device.pin_surface_visible", return_value=True)
    @mock.patch("android_device.AndroidClient", return_value=FakeUnlockClient())
    def test_configured_file_is_read_after_preflight_delivered_once_and_cleared(
        self, _client, _surface, _stage, _sleep
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            path = root / "unlock.secret"
            path.write_bytes(b"1234\n")
            path.chmod(0o600)
            cfg = replace(config(root), pin_file=path)
            delivered = []

            def deliver(_client, _serial, pin):
                self.assertEqual(pin, bytearray(b"1234"))
                delivered.append(pin)
                return subprocess.CompletedProcess([], 0, b"", b"")

            with mock.patch("android_device.device_status", side_effect=[locked_status(), locked_status(), unlocked_status()]), mock.patch(
                "android_device.read_pin", side_effect=AssertionError("stdin must not be read")
            ):
                result = android_device.unlock_pin(cfg, helper_builder=lambda _cfg: Path("helper.jar"), deliverer=deliver)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0], bytearray(b"\0\0\0\0"))
        self.assertEqual(result["effect"], "confirmed")
        self.assertNotIn("1234", json.dumps(result))

    @mock.patch("android_device.time.sleep")
    @mock.patch("android_device.stage_secret_helper")
    @mock.patch("android_device.pin_surface_visible", return_value=True)
    @mock.patch("android_device.AndroidClient", return_value=FakeUnlockClient())
    def test_changed_generation_refuses_before_opening_configured_file(
        self, _client, _surface, _stage, _sleep
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cfg = replace(config(Path(directory)), pin_file=Path(directory) / "missing.secret")
            changed = locked_status()
            changed["bootGeneration"] = "new-generation"
            with mock.patch("android_device.device_status", side_effect=[locked_status(), changed]), mock.patch(
                "android_device.read_pin_file", side_effect=AssertionError("must not open")
            ) as reader:
                result = android_device.unlock_pin(cfg, helper_builder=lambda _cfg: Path("helper.jar"))
        reader.assert_not_called()
        self.assertEqual(result["errorCode"], "target_generation_changed")
        self.assertEqual(result["data"]["attempts"], 0)

    @mock.patch("android_device.unlock_pin")
    @mock.patch("android_device.config_from_args")
    def test_cli_stdin_flag_explicitly_overrides_configured_file(self, configure, unlock) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cfg = replace(config(Path(directory)), pin_file=Path(directory) / "missing.secret")
            configure.return_value = cfg
            unlock.return_value = {"effect": "confirmed"}
            with mock.patch("builtins.print"):
                self.assertEqual(android_device.main(["unlock", "--stdin", "--json"]), 0)
            unlock.assert_called_once_with(cfg, secret_reader=android_device.read_pin)

    @mock.patch("android_device.observe_wipe_policy", return_value=None)
    @mock.patch("android_device.AndroidClient", return_value=FakeUnlockClient())
    def test_unknown_native_policy_refuses_before_secret(self, _client, observer) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "android_device.device_status", return_value=locked_status(wipe=None)
        ):
            reader = mock.Mock(side_effect=AssertionError("secret must not be read"))
            result = android_device.unlock_pin(config(Path(directory)), secret_reader=reader)
        reader.assert_not_called()
        observer.assert_called_once()
        self.assertEqual(result["errorCode"], "wipe_policy_not_safe")

    @mock.patch("android_device.observe_wipe_policy", return_value=0)
    @mock.patch("android_device.pin_surface_visible", return_value=False)
    @mock.patch("android_device.time.sleep")
    @mock.patch("android_device.AndroidClient", return_value=FakeUnlockClient())
    def test_native_zero_policy_still_requires_pin_surface(self, _client, _sleep, _surface, observer) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "android_device.device_status", return_value=locked_status(wipe=None)
        ):
            reader = mock.Mock(side_effect=AssertionError("secret must not be read"))
            result = android_device.unlock_pin(config(Path(directory)), secret_reader=reader)
        reader.assert_not_called()
        observer.assert_called_once()
        self.assertEqual(result["errorCode"], "credential_field_unavailable")

    @mock.patch("android_device.AndroidClient", return_value=FakeUnlockClient())
    def test_refuses_non_pin_before_reading_secret(
        self, _client: mock.Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "android_device.device_status",
            return_value=locked_status(credential="password"),
        ):
            reader = mock.Mock(side_effect=AssertionError("secret must not be read"))
            result = android_device.unlock_pin(
                config(Path(directory)), secret_reader=reader
            )
        reader.assert_not_called()
        self.assertFalse(result["accepted"])
        self.assertEqual(result["errorCode"], "unsupported_credential_surface")

    @mock.patch("android_device.AndroidClient", return_value=FakeUnlockClient())
    def test_refuses_unknown_or_nonzero_wipe_policy_before_secret(
        self, _client: mock.Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "android_device.device_status", return_value=locked_status(wipe=5)
        ):
            reader = mock.Mock(side_effect=AssertionError("secret must not be read"))
            result = android_device.unlock_pin(
                config(Path(directory)), secret_reader=reader
            )
        reader.assert_not_called()
        self.assertEqual(result["errorCode"], "wipe_policy_not_safe")

    @mock.patch("android_device.time.sleep")
    @mock.patch("android_device.stage_secret_helper")
    @mock.patch("android_device.pin_surface_visible", return_value=True)
    @mock.patch("android_device.AndroidClient", return_value=FakeUnlockClient())
    def test_delivers_once_zeros_secret_and_observes_effect(
        self,
        _client: mock.Mock,
        _surface: mock.Mock,
        _stage: mock.Mock,
        _sleep: mock.Mock,
    ) -> None:
        secret = bytearray(b"1234")
        reader = mock.Mock(return_value=secret)
        delivery = mock.Mock(
            return_value=subprocess.CompletedProcess(["adb"], 0, b"", b"")
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "android_device.device_status",
            side_effect=[locked_status(), locked_status(), unlocked_status()],
        ):
            result = android_device.unlock_pin(
                config(Path(directory)),
                secret_reader=reader,
                helper_builder=lambda _config: Path("helper.jar"),
                deliverer=delivery,
            )
        reader.assert_called_once_with()
        delivery.assert_called_once()
        self.assertEqual(secret, bytearray(b"\0\0\0\0"))
        self.assertEqual(result["delivery"], "confirmed")
        self.assertEqual(result["effect"], "confirmed")
        self.assertEqual(result["retryCount"], 0)
        self.assertNotIn("1234", json.dumps(result))

    @mock.patch("android_device.time.sleep")
    @mock.patch("android_device.stage_secret_helper")
    @mock.patch("android_device.pin_surface_visible", return_value=True)
    @mock.patch("android_device.AndroidClient", return_value=FakeUnlockClient())
    def test_delivery_timeout_is_observed_and_never_retried(
        self,
        _client: mock.Mock,
        _surface: mock.Mock,
        _stage: mock.Mock,
        _sleep: mock.Mock,
    ) -> None:
        delivery = mock.Mock(side_effect=subprocess.TimeoutExpired(["adb"], 20))
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "android_device.device_status",
            side_effect=[locked_status(), locked_status(), locked_status()],
        ):
            result = android_device.unlock_pin(
                config(Path(directory)),
                secret_reader=lambda: bytearray(b"1234"),
                helper_builder=lambda _config: Path("helper.jar"),
                deliverer=delivery,
            )
        delivery.assert_called_once()
        self.assertEqual(result["delivery"], "unknown")
        self.assertEqual(result["effect"], "no_effect")
        self.assertEqual(result["retryCount"], 0)


class PolicyObservationTests(unittest.TestCase):
    @mock.patch("android_device.build_helper", return_value=Path("policy.jar"))
    def test_effective_policy_requires_success_and_exact_current_user(self, _build) -> None:
        for code, output, expected in [
            (0, "userId=0 maximumFailedPasswordsForWipe=0\n", 0),
            (0, "userId=0 maximumFailedPasswordsForWipe=5\n", 5),
            (0, "userId=10 maximumFailedPasswordsForWipe=0\n", None),
            (2, "userId=0 maximumFailedPasswordsForWipe=0\n", None),
            (0, "", None),
            (0, "userId=0 maximumFailedPasswordsForWipe=0\nextra", None),
        ]:
            with self.subTest(code=code, output=output), tempfile.TemporaryDirectory() as directory:
                client = mock.Mock()
                client.shell.side_effect = [
                    subprocess.CompletedProcess([], 0, "", ""),
                    subprocess.CompletedProcess([], code, output, ""),
                    subprocess.CompletedProcess([], 0, "", ""),
                ]
                self.assertEqual(
                    android_device.observe_wipe_policy(config(Path(directory)), client, "PHONE", 0),
                    expected,
                )
                remote = client.run.call_args.args[0][-1]
                self.assertEqual(client.shell.call_args_list[-1].args[1], ["rm", "-f", remote])


if __name__ == "__main__":
    unittest.main()
