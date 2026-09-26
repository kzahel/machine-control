import importlib.util
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
                password_valid=False, doctor=None):
        def json_command(path, operation, *arguments, **_kwargs):
            if operation == "assert-target":
                return IDENTITY
            if operation == "factory-media-status":
                return {"schema": MEDIA, "stage": media}
            if operation == "factory-status":
                return {"schema": FACTORY, "state": first_logon}
            if operation == "status":
                return CREDENTIAL
            if operation == "doctor":
                return doctor
            raise AssertionError((path, operation, arguments))

        def command(path, operation, *arguments, **_kwargs):
            if operation == "status":
                return True, power
            if operation == "ssh-exec":
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
                     "credential", "resident"):
            self.assertEqual(stages[name]["state"], "complete", name)
        doctor["states"]["desktop"] = "locked"
        stages = self.inspect("started", "detached", "complete", attested=True,
                              ssh=True, password_valid=True, doctor=doctor)
        self.assertEqual(stages["resident"]["nextCommand"],
                         ["bin/winvm", "login"])

    def test_missing_doctor_never_recommends_bootstrap(self):
        stages = self.inspect("started", "detached", "complete", attested=True,
                              ssh=True, password_valid=True)
        self.assertEqual(stages["resident"]["state"], "blocked")
        self.assertEqual(stages["resident"]["nextCommand"],
                         ["bin/winvm", "doctor", "--json"])


if __name__ == "__main__":
    unittest.main()
