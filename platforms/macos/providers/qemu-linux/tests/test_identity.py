import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity import QemuIdentity  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
