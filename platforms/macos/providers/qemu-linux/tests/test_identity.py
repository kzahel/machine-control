import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity import QemuIdentity  # noqa: E402
from vnc import Keyboard  # noqa: E402


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux QEMU process identity")
class QemuIdentityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.boot = self.root / "boot.qcow2"
        self.system = self.root / "system.qcow2"
        for path in (self.boot, self.system):
            path.touch()
        wiring = {"MACVM_QEMU_DIRECTORY": str(self.root)}
        for role, path in (("OPENCORE", self.boot), ("SYSTEM", self.system)):
            info = path.stat()
            wiring[f"MACVM_QEMU_{role}_DISK"] = str(path)
            wiring[f"MACVM_QEMU_{role}_DISK_ID"] = f"{info.st_dev}:{info.st_ino}"
        environment = patch.dict(os.environ, wiring)
        environment.start()
        self.addCleanup(environment.stop)

    def test_replaced_system_disk_refuses_before_qmp(self):
        self.system.rename(self.root / "original.qcow2")
        self.system.touch()
        with self.assertRaisesRegex(ValueError, "private identity pin"):
            QemuIdentity()

    def test_inactive_exact_target_retains_claim_identity(self):
        identity = QemuIdentity()
        self.assertEqual(identity.resource, os.environ["MACVM_QEMU_SYSTEM_DISK_ID"])
        self.assertEqual(identity.state(), "off")

    def test_untrusted_endpoint_cannot_be_treated_as_powered_off(self):
        identity = QemuIdentity()
        identity.endpoint.touch()
        with self.assertRaisesRegex(ValueError, "owner-controlled Unix socket"):
            identity.state()

    def test_missing_file_during_live_identity_check_is_not_power_off(self):
        identity = QemuIdentity()
        with patch.object(QemuIdentity, "__enter__", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                identity.state()

    def test_qmp_roles_bind_the_disks_even_if_both_are_open(self):
        identity = QemuIdentity()
        blocks = [
            {"device": "BootLoader", "inserted": {"file": self.boot.name, "drv": "qcow2"}},
            {"device": "SystemDisk", "inserted": {"file": self.system.name, "drv": "qcow2"}},
        ]
        with patch.object(identity, "request", return_value=blocks):
            identity.verify_block_devices(self.root)
            blocks[0]["inserted"]["file"] = self.system.name
            blocks[1]["inserted"]["file"] = self.boot.name
            with self.assertRaisesRegex(ValueError, "block roles"):
                identity.verify_block_devices(self.root)

    def test_changed_console_frame_does_not_open_the_secret(self):
        identity = QemuIdentity()
        with (
            patch("recovery.Keyboard") as constructor,
            patch("recovery.observed_frame", return_value=b"observed"),
            patch("recovery.time.sleep"),
            patch.object(identity, "screenshot", side_effect=lambda path: path.write_bytes(b"changed")),
        ):
            keyboard = constructor.return_value.__enter__.return_value
            with self.assertRaisesRegex(ValueError, "password field frame changed"):
                identity.recovery_keyboard("type-secret", self.root / "console.png")
            keyboard.type_password.assert_not_called()

    def test_blinking_console_field_waits_for_an_exact_fresh_frame(self):
        identity = QemuIdentity()
        frames = iter([b"changed"] * 5 + [b"observed"])
        with (
            patch.dict(os.environ, {"MACVM_QEMU_LOGIN_SECRET_FILE": "test-secret"}),
            patch("recovery.Keyboard") as constructor,
            patch("recovery.observed_frame", return_value=b"observed") as observe,
            patch("recovery.time.sleep"),
            patch.object(identity, "screenshot", side_effect=lambda path: path.write_bytes(next(frames))),
        ):
            keyboard = constructor.return_value.__enter__.return_value
            identity.recovery_keyboard("type-secret", self.root / "console.png")
            self.assertEqual(observe.call_count, 2)
            keyboard.verify_exclusive_client.assert_called_once_with(identity)
            keyboard.type_password.assert_called_once_with("test-secret")

    def test_console_accepts_either_exact_observed_frame(self):
        identity = QemuIdentity()
        first = self.root / "caret-on.png"
        second = self.root / "caret-off.png"
        with (
            patch.dict(os.environ, {"MACVM_QEMU_LOGIN_SECRET_FILE": "test-secret"}),
            patch("recovery.Keyboard") as constructor,
            patch("recovery.observed_frame", side_effect=[b"caret-on", b"caret-off", b"caret-off"]) as observe,
            patch.object(identity, "screenshot", side_effect=lambda path: path.write_bytes(b"caret-off")),
        ):
            keyboard = constructor.return_value.__enter__.return_value
            identity.recovery_keyboard("type-secret", first, second)
            self.assertEqual([call.args[0] for call in observe.call_args_list], [first, second, second])
            keyboard.type_password.assert_called_once_with("test-secret")

    def test_concurrent_vnc_viewer_refuses_before_connecting(self):
        qmp = Mock()
        qmp.request.return_value = {
            "enabled": True, "host": "127.0.0.1", "auth": "none",
            "service": "5900", "clients": [{}],
        }
        with self.assertRaisesRegex(ValueError, "exclusive loopback"):
            Keyboard(qmp)


if __name__ == "__main__":
    unittest.main()
