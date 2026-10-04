import importlib.util
import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location("vbox_images", Path(__file__).parents[1] / "images.py")
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)


class ImageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        config = dict(role="candidate", platform="windows", uuid="vm", diskUuid="disk",
                      disk=str(self.root / "system.vdi"), vmFile=str(self.root / "guest.vbox"),
                      credentialFile=str(self.root / "credential"))
        for path in (*[config[k] for k in ("disk", "vmFile", "credentialFile")],
                     str(self.root / "guest.nvram")):
            Path(path).write_bytes(b"test-only")
        self.info = dict(VMState="poweroff", UUID="vm", cpus="3", memory="6144")
        self.adapter = types.SimpleNamespace(config=config, state=self.root / "state", resource="resource",
                                             require_claim=Mock(), inspect=Mock(return_value=self.info))
        self.store = images.Images(self.adapter)

    def records(self, count=3):
        return [dict(resource="resource", hardware=images.hardware(self.info),
                     observedAt=time.time(), stoppedAt=time.time(), shutdownSeconds=20,
                     facts=dict(boot=str(i)), diskStamp=images.file_stamp(self.adapter.config["disk"]),
                     credentialStamp=images.file_stamp(self.adapter.config["credentialFile"]))
                for i in range(count)]

    def history(self, records):
        images.write_atomic(self.store.history, records)

    def test_missing_duplicate_and_mismatched_boots_cannot_promote(self):
        records = self.records()
        for history in ([], records[:2], [records[0]] * 3,
                        [*records[:2], records[2] | {"hardware": "changed"}]):
            self.history(history)
            with self.assertRaises(ValueError):
                self.store.promote(self.info)
            self.assertFalse(self.store.protected())

    def test_unqualified_restart_cannot_reuse_previous_acceptance(self):
        self.history(self.records())
        self.store.starting()
        with self.assertRaises(ValueError):
            self.store.promote(self.info)

    def test_disk_or_credential_change_refuses_promotion(self):
        for key in ("disk", "credentialFile"):
            self.history(self.records())
            Path(self.adapter.config[key]).write_bytes(b"changed value")
            with self.assertRaises(ValueError):
                self.store.promote(self.info)

    def test_promotion_retains_firmware_and_protects_without_deleting(self):
        self.history(self.records())
        self.assertTrue(self.store.promote(self.info)["promoted"])
        self.assertTrue(self.store.protected())
        self.assertTrue(self.store.verify(self.info)["verified"])
        self.assertTrue((self.root / "guest.nvram").exists())
        with self.assertRaises(ValueError):
            self.store.promote(self.info)
        Path(self.adapter.config["disk"]).write_bytes(b"corrupted")
        with self.assertRaises(ValueError):
            self.store.verify(self.info)

    def test_recovery_invalidates_previous_lifecycle_evidence(self):
        self.history(self.records())
        self.store.invalidate(history=True)
        with self.assertRaises(ValueError):
            self.store.promote(self.info)

    def test_scheduler_policy_change_cannot_reuse_qualification(self):
        self.history(self.records())
        self.adapter.config["shutdownRescheduleAfterSeconds"] = 30
        with self.assertRaises(ValueError):
            self.store.promote(self.info)

    def test_nic_or_transport_policy_change_cannot_reuse_qualification(self):
        self.history(self.records())
        with self.assertRaises(ValueError):
            self.store.promote(self.info | {"nictype1": "different"})
        self.adapter.config["sshConnectTimeoutSeconds"] = 15
        with self.assertRaises(ValueError):
            self.store.promote(self.info)

    def test_running_or_changed_source_cannot_be_recorded_clean(self):
        self.store.starting()
        images.write_atomic(self.store.qualification, self.records(1)[0])
        self.store.stopped(self.info | {"VMState": "running"}, 10)
        self.assertFalse(self.store.history.exists())
        self.assertTrue(self.store.pending.exists())


if __name__ == "__main__":
    unittest.main()
