from __future__ import annotations

import json
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
        self.assertTrue(
            any(
                __import__("re").search(
                    pattern,
                    '<node resource-id="com.android.systemui:id/pinEntry" '
                    'class="android.widget.EditText" password="true"/>',
                )
                for pattern in android_device.PIN_SURFACE_PATTERNS
            )
        )

    def test_any_positive_wipe_policy_fails_safe(self) -> None:
        self.assertEqual(
            android_device.parse_maximum_failed_passwords(
                "maximumFailedPasswordsForWipe=0\n"
                "maximumFailedPasswordsForWipe=10"
            ),
            10,
        )


class UnlockTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
