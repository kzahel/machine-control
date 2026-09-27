import argparse
import importlib.util
from pathlib import Path
import sys
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
    def test_preflight_never_recommends_creation_with_mismatched_seed(self):
        args = argparse.Namespace(cloud_image="/private/cloud.qcow2",
                                  public_key="/private/key.pub", user="appliance",
                                  name="candidate")
        preflight = {"schema": "machine-control-libvirt-factory-preflight/v0",
                     "kind": "linux", "ready": True}
        with mock.patch.object(MODULE, "call", return_value=(True, "")), \
             mock.patch.object(MODULE, "document", return_value=preflight), \
             mock.patch.object(MODULE, "private_seed", return_value=False), \
             mock.patch.object(Path, "read_text", return_value="ssh-ed25519 AAAA test"):
            report = MODULE.preflight(args)
        current = stages(report)
        self.assertEqual(current["seed-media"]["state"], "action_required")
        self.assertEqual(current["create"]["state"], "blocked")
        self.assertNotIn("/private/", str(report))

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
