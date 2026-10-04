import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("virtualbox_adapter", Path(__file__).parents[1] / "adapter.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.config = dict(schema="machine-control-virtualbox-target/v0", platform="linux",
                           profile="ubuntu-gnome-wayland", role="candidate",
                           uuid="11111111-1111-4111-8111-111111111111",
                           diskUuid="22222222-2222-4222-8222-222222222222", username="appliance", sshPort=2222)
        for key in ("library", "vmFile", "disk", "stateDirectory", "sshKey", "knownHosts"):
            self.config[key] = str(root / key)
        self.instance = adapter.Adapter(self.config)
        self.info = {"UUID": self.config["uuid"], "CfgFile": self.config["vmFile"],
                     "SATA-0-0": self.config["disk"], "SATA-ImageUUID-0-0": self.config["diskUuid"],
                     "VMState": "poweroff"}

    def text(self, **changes):
        return "\n".join(json.dumps(k) + "=" + json.dumps(v) for k, v in (self.info | changes).items())

    def test_management_composite_does_not_truncate_identity(self):
        value = adapter.parse_info('VideoMode="1280,800,32"@0,0 1\nUUID="valid"trailing')
        self.assertEqual(value["VideoMode"], '"1280,800,32"@0,0 1')
        self.assertNotEqual(value["UUID"], "valid")
        with self.assertRaises(ValueError):
            adapter.parse_info('UUID="one"\nUUID="two"')
        raw = r'"file,C:\Users\example\boot.log"'
        self.assertEqual(adapter.parse_info('uartmode1=' + raw)["uartmode1"], raw)

    def test_recovery_requires_disruptive_claim(self):
        def require(disruptive=False):
            if disruptive:
                raise ValueError("Ordinary claim")
        for command, args in (("force-stop", []), ("acpi-shutdown", []),
                              ("screenshot", [str(Path(self.directory.name) / "screen.png")]),
                              ("candidate-hardware", ["--cpus", "1"])):
            with self.subTest(command=command), \
                    patch.object(self.instance, "require_claim", side_effect=require), \
                    patch.object(self.instance, "inspect", return_value=self.info | {"VMState": "running"}), \
                    patch.object(self.instance, "vbox") as vbox:
                with self.assertRaises(ValueError):
                    self.instance.dispatch(command, args)
                vbox.assert_not_called()

    def test_media_removal_requires_exact_seed_and_verified_password(self):
        self.config["bootstrapMedia"] = str(Path(self.directory.name) / "seed.iso")
        for medium, verified in (("foreign.iso", True), (self.config["bootstrapMedia"], False)):
            with self.subTest(medium=medium, verified=verified), \
                    patch.object(self.instance, "require_claim"), \
                    patch.object(self.instance, "inspect", return_value=self.info | {"SATA-1-0": medium}), \
                    patch.object(self.instance, "credential", return_value={"ready": verified}), \
                    patch.object(self.instance, "vbox") as vbox:
                with self.assertRaises(ValueError):
                    self.instance.dispatch("detach-bootstrap-media", [])
                vbox.assert_not_called()

    def test_artifact_traversal_cannot_reach_guest(self):
        with patch.object(self.instance, "require_claim"), \
                patch.object(self.instance, "inspect", return_value=self.info), \
                patch.object(self.instance, "ssh") as ssh:
            with self.assertRaises(ValueError):
                self.instance.dispatch("artifact", ["../../private", "output.png"])
            ssh.assert_not_called()

    def test_replaced_vm_registration_and_disk_refuse(self):
        cases = {"UUID": "33333333-3333-4333-8333-333333333333",
                 "CfgFile": str(Path(self.directory.name) / "foreign.vbox"),
                 "SATA-0-0": str(Path(self.directory.name) / "foreign.vdi"),
                 "SATA-ImageUUID-0-0": "44444444-4444-4444-8444-444444444444"}
        for key, value in cases.items():
            with self.subTest(key=key), patch.object(self.instance, "vbox", return_value=self.text(**{key: value})):
                with self.assertRaises(ValueError):
                    self.instance.inspect()

    def test_unclaimed_and_expired_calls_cannot_reach_vm(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(self.instance, "vbox") as vbox:
            with self.assertRaises(ValueError):
                self.instance.dispatch("force-stop", [])
            vbox.assert_not_called()
        expired = subprocess.CompletedProcess([], 1, '{"accepted":false}', "")
        with patch.dict(os.environ, MACHINE_CONTROL_CLAIM_ID="c-" + "a" * 24), \
                patch.object(self.instance, "claim", return_value=expired), \
                patch.object(self.instance, "vbox") as vbox:
            with self.assertRaises(ValueError):
                self.instance.dispatch("up", [])
            vbox.assert_not_called()

    def test_claim_resource_override_refuses_before_dispatch(self):
        for option in ("--provider=foreign", "--resource-id=foreign", "--state-dir=foreign"):
            with self.subTest(option=option), patch.object(self.instance, "claim") as claim:
                with self.assertRaises(ValueError):
                    self.instance.dispatch("claim-acquire", ["--json", option])
                claim.assert_not_called()

    def test_offline_doctor_does_not_probe_or_claim_guest(self):
        with patch.object(self.instance, "vbox", return_value=self.text()), \
                patch.object(self.instance, "ssh") as ssh, patch.object(self.instance, "claim") as claim:
            result = self.instance.doctor()
            self.assertFalse(result["ready"])
            self.assertEqual(result["states"]["power"], "off")
            self.assertEqual(result["checks"][0]["status"], "pass")
            self.assertNotIn("suspend", result["lifecycleOperations"])
            ssh.assert_not_called(); claim.assert_not_called()

    def test_identity_is_rechecked_after_claim_before_start(self):
        with patch.object(self.instance, "require_claim"), \
                patch.object(self.instance, "vbox", return_value=self.text(UUID="foreign")) as vbox:
            with self.assertRaises(ValueError):
                self.instance.dispatch("up", [])
            self.assertEqual(vbox.call_count, 1)
            self.assertEqual(vbox.call_args.args[0], "showvminfo")

    def test_private_configuration_rejects_unsafe_role(self):
        path = Path(self.directory.name) / "target.json"
        path.write_text(json.dumps(self.config | {"role": "base"}))
        with self.assertRaises(ValueError):
            adapter.load_config(path)


if __name__ == "__main__":
    unittest.main()
