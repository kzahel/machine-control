import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import os
import platform
import subprocess
import stat
import sys
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "scripts/factory-stages.py"
SPEC = importlib.util.spec_from_file_location("linux_factory_stages", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def stages(report):
    return {item["name"]: item for item in report["stages"]}


class FactoryStagesTests(unittest.TestCase):
    def test_stage_probe_timeout_returns_uncertainty(self):
        success, output = MODULE.call("/bin/sh", "-c", "sleep 3", timeout=1)
        self.assertFalse(success)
        self.assertEqual(output, "")

    def test_failed_doctor_json_remains_observable(self):
        with mock.patch.object(MODULE, "call", return_value=(False,
             '{"schema":"machine-control-doctor/v0","ready":false}')):
            self.assertEqual(MODULE.document("doctor"), {})
            self.assertFalse(MODULE.document("doctor", allow_failure_json=True)["ready"])

    def test_preflight_never_recommends_creation_with_mismatched_seed(self):
        args = argparse.Namespace(cloud_image="/private/cloud.qcow2",
                                  public_key="/private/key.pub", user="appliance",
                                  name="candidate")
        preflight = {"schema": "machine-control-libvirt-factory-preflight/v0",
                     "kind": "linux", "ready": True}
        with mock.patch.object(MODULE, "call", return_value=(True, "")), \
             mock.patch.object(MODULE, "document", return_value=preflight), \
             mock.patch.object(MODULE, "private_seed", return_value=False), \
             mock.patch.object(Path, "exists", return_value=True), \
             mock.patch.object(Path, "read_text", return_value="ssh-ed25519 AAAA test"):
            report = MODULE.preflight(args, "libvirt-linux")
        current = stages(report)
        self.assertEqual(current["seed-media"]["state"], "blocked")
        self.assertEqual(current["create"]["state"], "blocked")
        self.assertNotIn("/private/", str(report))

    def test_libvirt_ready_destination_keeps_existing_evidence(self):
        args = argparse.Namespace(cloud_image="/private/cloud.qcow2",
                                  public_key="/private/key.pub", user="appliance",
                                  name="candidate")
        destination = {"schema": "machine-control-libvirt-factory-preflight/v0",
                       "kind": "linux", "ready": True}
        with mock.patch.object(MODULE, "call", return_value=(True, "")), \
             mock.patch.object(MODULE, "document", return_value=destination), \
             mock.patch.object(MODULE, "private_seed", return_value=True), \
             mock.patch.object(Path, "exists", return_value=True), \
             mock.patch.object(Path, "read_text", return_value="ssh-ed25519 AAAA test"):
            report = MODULE.preflight(args, "libvirt-linux")
        current = stages(report)
        self.assertEqual(current["destination"]["evidence"],
                         "kvm_pool_and_destination_verified")
        self.assertEqual(current["create"]["state"], "action_required")

    def test_utm_preflight_refuses_registered_destination(self):
        args = argparse.Namespace(cloud_image="/private/cloud.qcow2",
                                  public_key="/private/key.pub", user="appliance",
                                  name="candidate")
        with mock.patch.object(MODULE, "call", return_value=(True, "")), \
             mock.patch.object(MODULE, "private_seed", return_value=True), \
             mock.patch.object(MODULE, "utm_destination",
                               return_value=(False, "candidate_already_registered")), \
             mock.patch.object(Path, "read_text", return_value="ssh-ed25519 AAAA test"):
            report = MODULE.preflight(args, "utm-macos")
        current = stages(report)
        self.assertEqual(report["provider"], "utm-macos")
        self.assertEqual(current["destination"]["evidence"],
                         "candidate_already_registered")
        self.assertEqual(current["create"]["state"], "blocked")
        self.assertNotIn("/private/", str(report))

    def test_utm_inventory_must_be_loaded_before_create(self):
        with mock.patch.object(MODULE.platform, "system", return_value="Darwin"), \
             mock.patch.object(MODULE.platform, "machine", return_value="arm64"), \
             mock.patch.object(MODULE.shutil, "which", return_value="/tool"), \
             mock.patch.object(MODULE.os, "access", return_value=True), \
             mock.patch.object(MODULE, "call", return_value=(True, "UUID Status Name\n")):
            ready, reason = MODULE.utm_destination("candidate", Path("/unused"))
        self.assertFalse(ready)
        self.assertEqual(reason, "utm_library_unverified")

    def test_utm_inventory_read_does_not_hide_unresponsive_scripting(self):
        with mock.patch.object(MODULE.platform, "system", return_value="Darwin"), \
             mock.patch.object(MODULE.platform, "machine", return_value="arm64"), \
             mock.patch.object(MODULE.shutil, "which", return_value="/tool"), \
             mock.patch.object(MODULE.os, "access", return_value=True), \
             mock.patch.object(MODULE, "call", side_effect=[
                 (True, "UUID Status Name\n00000000-0000-0000-0000-000000000000 stopped Existing\n"),
                 (False, ""),
             ]):
            ready, reason = MODULE.utm_destination("candidate", Path("/unused"))
        self.assertFalse(ready)
        self.assertEqual(reason, "utm_scripting_unavailable")

    @unittest.skipUnless(platform.system() == "Darwin", "macOS seed builder")
    def test_utm_seed_checks_actual_cidata_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "user-data").write_text("#cloud-config\n" + json.dumps({
                "users": [{"name": "appliance", "lock_passwd": True,
                           "ssh_authorized_keys": ["ssh-ed25519 AAAA test"]}],
                "ssh_pwauth": False,
            }))
            (source / "meta-data").write_text(json.dumps({
                "instance-id": "machine-control-linux-appliance",
            }))
            seed = root / "seed.iso"
            subprocess.run(["hdiutil", "makehybrid", "-iso", "-joliet",
                            "-default-volume-name", "CIDATA", "-o", str(seed),
                            str(source)], check=True, capture_output=True)
            os.chmod(seed, 0o600)
            self.assertTrue(MODULE.private_seed(seed, "appliance",
                                                "ssh-ed25519 AAAA test", "utm-macos"))
            self.assertFalse(MODULE.private_seed(seed, "other",
                                                 "ssh-ed25519 AAAA test", "utm-macos"))

    def test_utm_running_candidate_waits_without_guest_agent(self):
        identity = {"schema": "machine-control-candidate-assertion/v0",
                    "identityPin": "verified", "role": "candidate",
                    "powerState": "running"}

        def report(*args, **_kwargs):
            if "candidate-status" in args:
                return identity
            if "factory-media-status" in args:
                return {"schema": "linuxvm-factory-media-status/v0",
                        "stage": "seed_only"}
            return {}

        with mock.patch.object(MODULE, "document", side_effect=report), \
             mock.patch.object(MODULE, "call", return_value=(False, "")), \
             mock.patch.object(MODULE, "attested", return_value=False), \
             mock.patch.object(MODULE, "cloud_observation") as cloud:
            current = stages(MODULE.utm_candidate("00000000-0000-0000-0000-000000000000"))
        cloud.assert_not_called()
        self.assertEqual(current["guest-agent"]["state"], "waiting")
        self.assertEqual(current["cloud-init"]["state"], "waiting")
        self.assertEqual(current["media"]["state"], "blocked")

    def test_utm_cloud_completion_uses_recorded_runtime_when_cli_is_silent(self):
        phases = {name: {"finished": 3.0, "errors": []} for name in
                  ("init-local", "init", "modules-config", "modules-final")}

        def report(*args, **_kwargs):
            if "/run/cloud-init/status.json" in args:
                return {"v1": phases}
            if "/run/cloud-init/result.json" in args:
                return {"v1": {"datasource": "DataSourceNoCloud [seed=/dev/vdb]",
                               "errors": []}}
            return {}

        identifier = "00000000-0000-0000-0000-000000000000"
        with mock.patch.object(MODULE, "document", side_effect=report), \
             mock.patch.object(MODULE, "utm_exec", side_effect=[
                 (True, identifier), (True, "machine-control-linux-appliance"),
                 (True, "")]):
            status, boot_id, matching = MODULE.cloud_observation()
        self.assertEqual((status, boot_id, matching), ("done", identifier, True))

        phases["modules-final"].pop("finished")
        with mock.patch.object(MODULE, "document", side_effect=report), \
             mock.patch.object(MODULE, "utm_exec", side_effect=[
                 (True, identifier), (True, "machine-control-linux-appliance"),
                 (True, "")]):
            status, _, _ = MODULE.cloud_observation()
        self.assertEqual(status, "")

    def test_utm_seed_detach_needs_recorded_cloud_completion(self):
        identity = {"schema": "machine-control-candidate-assertion/v0",
                    "identityPin": "verified", "role": "candidate",
                    "powerState": "off"}

        def report(*args, **_kwargs):
            if "candidate-status" in args:
                return identity
            if "factory-media-status" in args:
                return {"schema": "linuxvm-factory-media-status/v0",
                        "stage": "seed_only"}
            return {}

        with mock.patch.object(MODULE, "document", side_effect=report), \
             mock.patch.object(MODULE, "attested", return_value=False):
            blocked = stages(MODULE.utm_candidate("00000000-0000-0000-0000-000000000000"))
        with mock.patch.object(MODULE, "document", side_effect=report), \
             mock.patch.object(MODULE, "attested", return_value=True):
            recorded = stages(MODULE.utm_candidate("00000000-0000-0000-0000-000000000000"))
        self.assertEqual(blocked["media"]["state"], "blocked")
        self.assertEqual(recorded["media"]["nextCommand"],
                         ["bin/linuxvm", "factory-detach-media"])

    def test_utm_attestation_refuses_unfinished_cloud_init(self):
        identity = {"schema": "machine-control-candidate-assertion/v0",
                    "identityPin": "verified", "role": "candidate",
                    "powerState": "running"}
        with mock.patch.object(MODULE, "document", side_effect=[
                 identity, {"schema": "linuxvm-factory-media-status/v0",
                            "stage": "seed_only"}]), \
             mock.patch.object(MODULE, "call", return_value=(True, "")), \
             mock.patch.object(MODULE, "cloud_observation",
                               return_value=("running", "00000000-0000-0000-0000-000000000000", True)):
            with self.assertRaisesRegex(ValueError, "completion_required"):
                MODULE.attest_cloud_init("00000000-0000-0000-0000-000000000000")

    def test_utm_completion_receipt_is_private_and_exact(self):
        identifier = "00000000-0000-0000-0000-000000000000"
        identity = {"schema": "machine-control-candidate-assertion/v0",
                    "identityPin": "verified", "role": "candidate",
                    "powerState": "running"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipts" / f"{identifier}.json"
            with mock.patch.object(MODULE, "document", side_effect=[
                     identity, {"schema": "linuxvm-factory-media-status/v0",
                                "stage": "seed_only"}]), \
                 mock.patch.object(MODULE, "call", return_value=(True, "")), \
                 mock.patch.object(MODULE, "cloud_observation",
                                   return_value=("done", identifier, True)), \
                 mock.patch.object(MODULE, "attestation_path", return_value=path), \
                 contextlib.redirect_stdout(io.StringIO()):
                MODULE.attest_cloud_init(identifier)
            with mock.patch.object(MODULE, "attestation_path", return_value=path):
                self.assertTrue(MODULE.attested(identifier))
                self.assertFalse(MODULE.attested("11111111-1111-1111-1111-111111111111"))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_utm_locked_desktop_does_not_suggest_bootstrap(self):
        identity = {"schema": "machine-control-candidate-assertion/v0",
                    "identityPin": "verified", "role": "candidate",
                    "powerState": "running"}

        def report(*args, **_kwargs):
            if "candidate-status" in args:
                return identity
            if "factory-media-status" in args:
                return {"schema": "linuxvm-factory-media-status/v0",
                        "stage": "seed_only"}
            if "doctor" in args:
                return {"schema": "machine-control-doctor/v0", "ready": False,
                        "states": {"desktop": "locked"}}
            return {}

        with mock.patch.object(MODULE, "document", side_effect=report), \
             mock.patch.object(MODULE, "call", return_value=(True, "")), \
             mock.patch.object(MODULE, "attested", return_value=False), \
             mock.patch.object(MODULE, "utm_exec", return_value=(True, "")), \
             mock.patch.object(MODULE, "cloud_observation", return_value=(
                 "done", "00000000-0000-0000-0000-000000000000", True)):
            current = stages(MODULE.utm_candidate("00000000-0000-0000-0000-000000000000"))
        self.assertEqual(current["resident"]["state"], "human_required")
        self.assertIsNone(current["resident"]["nextCommand"])

    def test_running_candidate_waits_for_agent_without_bootstrap(self):
        identity = {"schema": "machine-control-candidate-assertion/v0",
                    "identityPin": "verified", "role": "candidate",
                    "powerState": "running"}

        def report(*args, **_kwargs):
            if "candidate-status" in args:
                return identity
            if "factory-media-status" in args:
                return {"schema": "linuxvm-factory-media-status/v0",
                        "stage": "seed_only"}
            return {}

        with mock.patch.object(MODULE, "document", side_effect=report), \
             mock.patch.object(MODULE, "call", return_value=(False, "")):
            current = stages(MODULE.candidate())
        self.assertEqual(current["guest-agent"]["state"], "waiting")
        self.assertEqual(current["cloud-init"]["state"], "waiting")
        self.assertEqual(current["resident"]["state"], "blocked")
        self.assertIsNone(current["resident"]["nextCommand"])

    def test_detach_requires_stopped_exact_candidate(self):
        identity = {"schema": "machine-control-candidate-assertion/v0",
                    "identityPin": "verified", "role": "candidate",
                    "powerState": "off"}

        def report(*args, **_kwargs):
            if "candidate-status" in args:
                return identity
            if "factory-media-status" in args:
                return {"schema": "linuxvm-factory-media-status/v0",
                        "stage": "seed_only"}
            return {}

        with mock.patch.object(MODULE, "document", side_effect=report):
            current = stages(MODULE.candidate())
        self.assertEqual(current["media"]["state"], "action_required")
        self.assertEqual(current["media"]["nextCommand"],
                         ["bin/linuxvm", "factory-detach-media"])
        self.assertEqual(current["final-stop"]["state"], "blocked")

    def test_detached_seed_uses_guest_nocloud_receipt(self):
        identity = {"schema": "machine-control-candidate-assertion/v0",
                    "identityPin": "verified", "role": "candidate",
                    "powerState": "running"}

        def report(*args, **_kwargs):
            if "candidate-status" in args:
                return identity
            if "factory-media-status" in args:
                return {"schema": "linuxvm-factory-media-status/v0",
                        "stage": "detached"}
            if "cloud-init" in args:
                return {"status": "disabled"}
            if "doctor" in args:
                return {"ready": True}
            return {}

        def command(*args, **_kwargs):
            if "factory-agent-ready" in args:
                return True, ""
            if any("boot_id" in arg for arg in args):
                return True, "00000000-0000-0000-0000-000000000000\n"
            if any("instance-id" in arg for arg in args):
                return True, "machine-control-linux-appliance\n"
            return True, ""

        with mock.patch.object(MODULE, "document", side_effect=report), \
             mock.patch.object(MODULE, "call", side_effect=command):
            current = stages(MODULE.candidate())
        self.assertEqual(current["cloud-init"]["state"], "complete")
        self.assertEqual(current["cloud-init"]["evidence"],
                         "prior_nocloud_completion_on_disk")
        self.assertEqual(current["final-stop"]["state"], "action_required")


if __name__ == "__main__":
    unittest.main()
