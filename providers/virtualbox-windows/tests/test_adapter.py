import importlib.util
import contextlib
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
                              ("recovery-key", ["enter"]),
                              ("screenshot", [str(Path(self.directory.name) / "screen.png")]),
                              ("candidate-hardware", ["--cpus", "1"])):
            with self.subTest(command=command), \
                    patch.object(self.instance, "require_claim", side_effect=require), \
                    patch.object(self.instance, "inspect", return_value=self.info | {"VMState": "running"}), \
                    patch.object(self.instance, "vbox") as vbox:
                with self.assertRaises(ValueError):
                    self.instance.dispatch(command, args)
                vbox.assert_not_called()

    def test_recovery_key_refuses_unknown_input_before_management(self):
        with patch.object(self.instance, "require_claim"), \
                patch.object(self.instance, "inspect", return_value=self.info | {"VMState": "running"}), \
                patch.object(self.instance, "vbox") as vbox:
            with self.assertRaises(ValueError):
                self.instance.dispatch("recovery-key", ["arbitrary text"])
            vbox.assert_not_called()

    def test_login_refuses_uncertain_identity_without_reading_secret(self):
        self.config["platform"] = "windows"
        identity = json.dumps(dict(user="appliance", display="Appliance User"))
        field = dict(controlType="Edit", automationId="PasswordField_2", name="Password",
                     enabled=True, offscreen=False)
        account = dict(controlType="Text", name="Appliance User", offscreen=False)
        for elements in ([field], [field, field, account],
                         [field | {"offscreen": True}, account]):
            with self.subTest(elements=elements), \
                    patch.object(self.instance, "powershell", return_value=identity), \
                    patch.object(self.instance, "control", side_effect=[
                        dict(accepted=True, data=dict(interactiveUserPresent=False)),
                        dict(accepted=True, desktop="Winlogon", data=dict(elements=elements))]), \
                    patch.object(Path, "read_bytes") as read, \
                    patch.object(self.instance, "ssh") as ssh:
                with self.assertRaises(ValueError):
                    self.instance.login()
                read.assert_not_called()
                ssh.assert_not_called()

    def test_login_refuses_existing_user_before_secret_discovery(self):
        with patch.object(self.instance, "powershell", return_value=json.dumps(
                    dict(user="appliance", display="Appliance User"))), \
                patch.object(self.instance, "control", return_value=dict(
                    accepted=True, data=dict(interactiveUserPresent=True))), \
                patch.object(Path, "read_bytes") as read:
            with self.assertRaises(ValueError):
                self.instance.login()
            read.assert_not_called()

    def test_login_binds_password_field_to_account_and_uses_stdin(self):
        self.config["credentialFile"] = str(Path(self.directory.name) / "credential")
        Path(self.config["credentialFile"]).write_bytes(b"test-password\r\n")
        elements = [dict(controlType="Group", name="Appliance User", depth=3, offscreen=False),
                    dict(controlType="Edit", name="Password", depth=4,
                         automationId="PasswordField_2", enabled=True, offscreen=False)]
        with patch.object(self.instance, "powershell", return_value=json.dumps(
                    dict(user="appliance", display="Appliance User"))), \
                patch.object(self.instance, "control", side_effect=[
                    dict(accepted=True, data=dict(interactiveUserPresent=False)),
                    dict(accepted=True, desktop="Winlogon", data=dict(elements=elements))]), \
                patch.object(self.instance, "require_claim"), \
                patch.object(self.instance, "inspect"), \
                patch.object(self.instance, "ssh", return_value='{"accepted":true}') as ssh:
            self.assertTrue(self.instance.login()["accepted"])
            self.assertEqual(ssh.call_args.args[1], b"test-password")
            self.assertNotIn("test-password", ssh.call_args.args[0])

    def test_windows_shutdown_can_finish_after_two_minutes_without_force(self):
        self.config["platform"] = "windows"
        running = self.info | {"VMState": "running"}
        with patch.object(self.instance, "require_claim") as claim, \
                patch.object(self.instance, "inspect", side_effect=[running, running, self.info]), \
                patch.object(self.instance, "powershell") as guest, \
                patch.object(self.instance, "vbox") as vbox, \
                patch.object(adapter.claims, "store_lock", return_value=contextlib.nullcontext()), \
                patch.object(adapter.time, "monotonic", side_effect=[0, 121, 278]), \
                patch.object(adapter.time, "sleep"):
            self.assertEqual(self.instance.dispatch("shutdown", []), 0)
            guest.assert_called_once_with("shutdown.exe /s /t 0")
            vbox.assert_not_called()
            self.assertEqual(claim.call_count, 4)

    def test_protected_base_refuses_mutation_even_with_candidate_config(self):
        self.instance.state.mkdir()
        (self.instance.state / "protected-base.json").write_text("malformed")
        for operation in ("up", "shutdown", "force-stop", "login", "qualify", "ps"):
            with self.subTest(operation=operation), \
                    patch.object(self.instance, "require_claim"), \
                    patch.object(self.instance, "inspect", return_value=self.info), \
                    patch.object(self.instance, "vbox") as vbox, \
                    patch.object(self.instance, "ssh") as ssh:
                with self.assertRaises(ValueError):
                    self.instance.dispatch(operation, [])
                vbox.assert_not_called()
                ssh.assert_not_called()

    def test_opt_in_shutdown_reschedules_once_without_power_cut(self):
        self.config.update(platform="windows", shutdownRescheduleAfterSeconds=30)
        running = self.info | {"VMState": "running"}
        with patch.object(self.instance, "require_claim"), \
                patch.object(self.instance, "inspect", side_effect=[
                    running, running, self.info | {"VMState": "paused"}, self.info]), \
                patch.object(self.instance, "powershell"), \
                patch.object(self.instance, "vbox") as vbox, \
                patch.object(adapter.claims, "store_lock", return_value=contextlib.nullcontext()), \
                patch.object(adapter.time, "monotonic", side_effect=[0, 31, 36]), \
                patch.object(adapter.time, "sleep"):
            self.assertEqual(self.instance.dispatch("shutdown", []), 0)
            self.assertEqual([c.args[-1] for c in vbox.call_args_list], ["pause", "resume"])

    def test_shutdown_assist_refuses_ordinary_claim_before_guest_action(self):
        self.config.update(platform="windows", shutdownRescheduleAfterSeconds=30)
        def require(disruptive=False):
            if disruptive:
                raise ValueError("Disruptive authority required")
        with patch.object(self.instance, "require_claim", side_effect=require), \
                patch.object(self.instance, "inspect", return_value=self.info | {"VMState": "running"}), \
                patch.object(self.instance, "powershell") as guest, \
                patch.object(self.instance, "vbox") as vbox:
            with self.assertRaises(ValueError):
                self.instance.dispatch("shutdown", [])
            guest.assert_not_called()
            vbox.assert_not_called()

    def test_pause_error_still_restores_a_paused_vm(self):
        self.config.update(platform="windows", shutdownRescheduleAfterSeconds=30)
        running = self.info | {"VMState": "running"}
        with patch.object(self.instance, "require_claim"), \
                patch.object(self.instance, "inspect", side_effect=[
                    running, running, self.info | {"VMState": "paused"}]), \
                patch.object(self.instance, "powershell"), \
                patch.object(self.instance, "vbox", side_effect=[ValueError("Uncertain pause"), ""]) as vbox, \
                patch.object(adapter.claims, "store_lock", return_value=contextlib.nullcontext()), \
                patch.object(adapter.time, "monotonic", side_effect=[0, 31]):
            with self.assertRaises(ValueError):
                self.instance.dispatch("shutdown", [])
            self.assertEqual([c.args[-1] for c in vbox.call_args_list], ["pause", "resume"])

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

    def test_native_ssh_is_not_reselected_when_openssl_changes_path(self):
        with patch.dict(os.environ, SystemRoot=self.directory.name,
                        PATH=str(Path(self.directory.name) / "foreign-tools")):
            arguments = self.instance.ssh_arguments("public carrier command")
        self.assertTrue(Path(arguments[0]).is_absolute())
        self.assertEqual(Path(arguments[0]).name, "ssh.exe")
        self.assertIn("StrictHostKeyChecking=yes", arguments)
        self.assertEqual(arguments[-1], "public carrier command")

    def test_unlock_missing_authority_cannot_start_carrier_or_read_secret(self):
        self.config["platform"] = "windows"
        self.config["unlockInstance"] = "test-instance"
        for key in ("unlockGrantFile", "unlockKeyFile", "credentialFile"):
            self.config[key] = str(Path(self.directory.name) / key)
        with patch.object(self.instance, "require_claim"), \
                patch.object(self.instance, "inspect", return_value=self.info), \
                patch.object(adapter.subprocess, "run") as run, \
                patch.object(Path, "read_bytes") as read:
            with self.assertRaises(ValueError):
                self.instance.dispatch("unlock", [])
            run.assert_not_called()
            read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
