import importlib.util
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "scripts/factory-stages.py"
SPEC = importlib.util.spec_from_file_location("factory_stages", SOURCE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

IDENTITY = {"identity_pin": "verified", "role": "candidate"}
CREDENTIAL = {"schema": "winvm-credential-status/v0",
              "loginPassword": "stored", "rotationPending": False}
MEDIA = "winvm-factory-media-status/v0"
FACTORY = "winvm-image-factory-status/v0"


def by_name(report):
    return {item["name"]: item for item in report["stages"]}


class FactoryStagesTests(unittest.TestCase):
    def test_attestation_is_exact_and_private(self):
        identifier = "00000000-0000-0000-0000-000000000000"
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.dict(os.environ, {"WINVM_FACTORY_STAGE_STATE_DIR": directory}):
            receipt = MODULE.attestation_path(identifier)
            receipt.parent.mkdir()
            receipt.write_text(json.dumps({
                "schema": "winvm-factory-first-logon-attestation/v0",
                "targetId": identifier,
                "completed": True,
                "observedAt": time.time(),
            }))
            receipt.chmod(0o600)
            self.assertTrue(MODULE.attested(identifier))
            self.assertFalse(MODULE.attested("11111111-1111-1111-1111-111111111111"))
            receipt.chmod(0o644)
            self.assertFalse(MODULE.attested(identifier))
            receipt.chmod(0o600)
            stale = json.loads(receipt.read_text())
            stale["observedAt"] = time.time() - MODULE.ATTESTATION_MAX_AGE_SECONDS - 1
            receipt.write_text(json.dumps(stale))
            self.assertFalse(MODULE.attested(identifier))

    def test_locked_doctor_json_is_preserved_despite_nonzero_exit(self):
        document = {"schema": "machine-control-doctor/v0",
                    "states": {"desktop": "locked"}}
        with mock.patch.object(MODULE, "command", return_value=(False, json.dumps(document))):
            self.assertIsNone(MODULE.json_command("doctor"))
            self.assertEqual(MODULE.json_command("doctor", allow_failure_json=True),
                             document)

    def inspect(self, power, media, first_logon, *, attested=False, ssh=False,
                password_valid=False, doctor=None, support=None, audit=None):
        def json_command(path, operation, *arguments, **_kwargs):
            if operation == "assert-target":
                return IDENTITY
            if operation == "factory-media-status":
                return {"schema": MEDIA, "stage": media}
            if operation == "factory-status":
                if first_logon is None:
                    return None
                return {"schema": FACTORY, "state": first_logon}
            if operation == "status":
                return CREDENTIAL
            if operation == "doctor":
                return doctor
            if operation == "post-update":
                return audit or {"schema":
                    "machine-control-windows-post-update-orchestration/v0",
                    "healthy": True}
            raise AssertionError((path, operation, arguments))

        def command(path, operation, *arguments, **_kwargs):
            if operation == "status":
                return True, power
            if operation == "factory-agent-ready":
                return first_logon is not None, ""
            if operation == "ssh-exec":
                if arguments and arguments[0].startswith("if (Test-Path"):
                    return support is not None, support or ""
                return ssh, ""
            if operation == "credential":
                return password_valid, ""
            raise AssertionError((path, operation, arguments))

        with mock.patch.object(MODULE, "json_command", side_effect=json_command), \
             mock.patch.object(MODULE, "command", side_effect=command), \
             mock.patch.object(MODULE, "attested", return_value=attested):
            return by_name(MODULE.inspect(Path("/fixture"), Path("/provider"),
                                          "00000000-0000-0000-0000-000000000000"))

    def test_pending_install_blocks_media_detachment(self):
        stages = self.inspect("started", "installer_and_seed", "pending")
        self.assertEqual(stages["first-logon"]["state"], "waiting")
        self.assertEqual(stages["media"]["state"], "blocked")
        self.assertIsNone(stages["media"]["nextCommand"])

    def test_running_guest_without_agent_is_waiting(self):
        stages = self.inspect("started", "installer_and_seed", None)
        self.assertEqual(stages["first-logon"]["state"], "waiting")
        self.assertEqual(stages["media"]["state"], "blocked")

    def test_attested_stopped_candidate_advises_exact_detach_order(self):
        stages = self.inspect("stopped", "installer_and_seed", "complete",
                              attested=True)
        self.assertEqual(stages["media"]["nextCommand"],
                         ["bin/winvm", "factory-detach-installer"])
        self.assertEqual(stages["credential"]["state"], "unverified")
        stages = self.inspect("stopped", "seed_only", "complete", attested=True)
        self.assertEqual(stages["media"]["nextCommand"],
                         ["bin/winvm", "factory-detach-media"])

    def test_live_ready_candidate_uses_guest_evidence(self):
        doctor = {"schema": "machine-control-doctor/v0",
                  "states": {name: "ready" for name in
                             ("administration", "resident", "semantic",
                              "capture", "input")}}
        doctor["states"]["desktop"] = "unlocked"
        stages = self.inspect("started", "detached", "complete", attested=True,
                              ssh=True, password_valid=True, doctor=doctor)
        for name in ("identity", "first-logon", "transport", "media",
                     "credential", "resident", "maintenance"):
            self.assertEqual(stages[name]["state"], "complete", name)
        doctor["states"]["desktop"] = "locked"
        stages = self.inspect("started", "detached", "complete", attested=True,
                              ssh=True, password_valid=True, doctor=doctor)
        self.assertEqual(stages["resident"]["nextCommand"],
                         ["bin/winvm", "login"])

    def test_pending_reboot_has_explicit_next_action(self):
        doctor = {"schema": "machine-control-doctor/v0",
                  "states": {name: "ready" for name in
                             ("administration", "resident", "semantic",
                              "capture", "input")}}
        doctor["states"]["desktop"] = "unlocked"
        audit = {"schema": "machine-control-windows-post-update-orchestration/v0",
                 "healthy": False, "post_update": {"checks": [
                     {"id": "pending_reboot", "healthy": False}]}}
        stages = self.inspect("started", "detached", "complete", attested=True,
                              ssh=True, password_valid=True, doctor=doctor,
                              audit=audit)
        self.assertEqual(stages["maintenance"]["evidence"], "pending_reboot")
        self.assertEqual(stages["maintenance"]["nextCommand"],
                         ["bin/winvm", "post-update", "repair", "--reboot", "--json"])

    def test_missing_doctor_never_recommends_bootstrap(self):
        stages = self.inspect("started", "detached", "complete", attested=True,
                              ssh=True, password_valid=True)
        self.assertEqual(stages["resident"]["state"], "blocked")
        self.assertEqual(stages["resident"]["nextCommand"],
                         ["bin/winvm", "doctor", "--json"])

    def test_bootstrap_repair_requires_observed_support_state(self):
        doctor = {"schema": "machine-control-doctor/v0",
                  "states": {"administration": "ready", "resident": "unavailable"}}
        stages = self.inspect("started", "detached", "complete", ssh=True,
                              password_valid=True, doctor=doctor, support="absent\n")
        self.assertEqual(stages["bootstrap"]["nextCommand"],
                         ["bin/winvm", "bootstrap", "--profile", "development"])
        stages = self.inspect("started", "detached", "complete", ssh=True,
                              password_valid=True, doctor=doctor, support="present\n")
        self.assertEqual(stages["bootstrap"]["nextCommand"],
                         ["bin/winvm", "post-update", "repair", "--json"])
        stages = self.inspect("started", "detached", "complete", ssh=True,
                              password_valid=True, doctor=doctor)
        self.assertEqual(stages["bootstrap"]["state"], "blocked")
        stages = self.inspect("started", "installer_and_seed", "complete",
                              attested=True, ssh=True, password_valid=True,
                              doctor=doctor, support="absent\n")
        self.assertEqual(stages["bootstrap"]["evidence"],
                         "factory_media_detachment_required")

    def test_preflight_does_not_publish_private_paths(self):
        options = argparse.Namespace(source_iso="/private/source.iso",
            guest_tools_iso="/private/tools.iso", secret_file="/private/setup.secret",
            public_key="/private/controller.pub", user="Appliance", image_index="6",
            name="candidate")
        def readable(path, **_kwargs):
            return path.startswith("/private/")
        def private(path):
            return path == "/private/setup.secret"
        def json_command(path, *_arguments, **_kwargs):
            if path.endswith("image-catalog.py"):
                return {"schema": "winvm-image-catalog/v0", "images": [
                    {"index": 6, "name": "Windows 11 Pro", "flags": "Professional"}]}
            if path.endswith("verify-prepared-media.py"):
                return {"schema": "winvm-prepared-media-verification/v0",
                        "ready": True}
            return {"schema": "machine-control-libvirt-factory-preflight/v0",
                    "ready": True}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "windows-install-noprompt.iso").touch()
            (root / "winvm-seed.iso").touch()
            with mock.patch.dict(os.environ, {"WINVM_FACTORY_LOCAL_ROOT": directory}), \
                 mock.patch.object(MODULE, "readable_file", side_effect=readable), \
                 mock.patch.object(MODULE, "private_file", side_effect=private), \
                 mock.patch.object(MODULE, "seed_media_ready", return_value=True), \
                 mock.patch.object(MODULE, "command", return_value=(True, "")), \
                 mock.patch.object(MODULE, "json_command", side_effect=json_command):
                report = MODULE.preflight(Path("/fixture"), Path("/provider"), options)
        stages = by_name(report)
        self.assertEqual(stages["create"]["state"], "action_required")
        self.assertEqual(stages["image-index"]["imageIndex"], 6)
        self.assertNotIn("/private/", json.dumps(report))

    def test_preflight_destination_refusal_is_typed(self):
        options = argparse.Namespace(source_iso=None, guest_tools_iso=None,
            secret_file=None, public_key=None, user=None, name="candidate")
        with mock.patch.object(MODULE, "json_command", return_value={
            "schema": "machine-control-libvirt-factory-preflight/v0",
            "ready": False, "reason": "factory_destination_exists",
        }):
            stages = by_name(MODULE.preflight(Path("/fixture"), Path("/provider"),
                                              options))
        self.assertEqual(stages["destination"]["state"], "blocked")
        self.assertEqual(stages["destination"]["evidence"],
                         "factory_destination_exists")

    def test_preflight_never_recommends_creation_without_inputs(self):
        options = argparse.Namespace(source_iso=None, guest_tools_iso=None,
            secret_file=None, public_key=None, user=None, image_index=None,
            name=None)
        with mock.patch.object(MODULE, "json_command") as provider:
            stages = by_name(MODULE.preflight(Path("/fixture"), Path("/provider"),
                                              options))
        self.assertEqual(stages["create"]["state"], "blocked")
        self.assertIsNone(stages["create"]["nextCommand"])
        provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
