import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
HARNESS = (
    ROOT / "providers" / "workspaces" / "tests" / "fixtures"
    / "utm-workspace-harness.sh"
)


@unittest.skipIf(os.name == "nt" or shutil.which("bash") is None, "requires POSIX Bash")
class UtmWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.state = self.directory / "utm.json"
        self.receipts = self.directory / "receipts"
        self.storage = self.directory / "storage"
        self.storage.mkdir()
        self.state.write_text(json.dumps({
            "nextId": 0,
            "vms": [
                {
                    "id": "dev-id",
                    "name": "fixture development",
                    "state": "stopped",
                    "disposable": False,
                },
                {
                    "id": "base-id",
                    "name": "fixture ready base",
                    "state": "stopped",
                    "disposable": False,
                },
            ],
        }), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, *arguments, full_copy=None):
        environment = {
            **os.environ,
            "MACHINE_CONTROL_UTM_FIXTURE_STATE": str(self.state),
            "MACHINE_CONTROL_UTM_FIXTURE_RECEIPTS": str(self.receipts),
            "MACHINE_CONTROL_UTM_FIXTURE_STORAGE": str(self.storage),
        }
        if full_copy is not None:
            environment["MACHINE_CONTROL_UTM_FIXTURE_FULL_COPY"] = full_copy
        result = subprocess.run(
            ["bash", str(HARNESS), *arguments],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        value = json.loads(result.stdout) if result.stdout.strip() else None
        return result, value

    def vm(self, identifier):
        for vm in json.loads(self.state.read_text(encoding="utf-8"))["vms"]:
            if identifier in {vm["id"], vm["name"]}:
                return vm
        return None

    def test_capabilities_disclose_mechanisms_not_private_targets(self):
        result, value = self.run_cli("workspace-capabilities", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            value["intents"]["isolated"]["mechanisms"][0]["kind"],
            "provider_disposable_overlay",
        )
        self.assertEqual(value["intents"]["candidate"]["availability"], "unavailable")
        self.assertNotIn("fixture development", result.stdout)
        self.assertNotIn("dev-id", result.stdout)

    def test_persistent_reuses_and_retains_development_vm(self):
        result, value = self.run_cli(
            "workspace-acquire", "--intent", "persistent", "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["actualMechanism"], "existing_instance")
        self.assertEqual(self.vm("dev-id")["state"], "started")
        handle = value["data"]["handle"]

        result, value = self.run_cli(
            "workspace-release", "--handle", handle, "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["disposition"], "retained")
        self.assertEqual(self.vm("dev-id")["state"], "started")

    def test_isolated_disposable_release_stops_without_deleting_base(self):
        result, value = self.run_cli(
            "workspace-acquire", "--intent", "isolated", "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.vm("base-id")["disposable"])
        handle = value["data"]["handle"]

        result, inventory = self.run_cli("workspace-inventory", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(inventory["data"]["counts"]["temporary"], 1)
        self.assertNotIn("fixture ready base", result.stdout)

        result, value = self.run_cli(
            "workspace-release", "--handle", handle, "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["disposition"], "discarded")
        self.assertEqual(self.vm("base-id")["state"], "stopped")
        self.assertIsNotNone(self.vm("base-id"))

    def test_full_copy_candidate_requires_policy_and_is_retained(self):
        result, value = self.run_cli(
            "workspace-acquire", "--intent", "candidate", "--json"
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["errorCode"], "intent_unavailable")

        result, value = self.run_cli(
            "workspace-acquire", "--intent", "candidate", "--json",
            full_copy="allowed",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["actualMechanism"], "full_copy")
        handle = value["data"]["handle"]
        self.assertEqual(self.vm("candidate-id-1")["state"], "started")

        result, value = self.run_cli(
            "workspace-release", "--handle", handle, "--json",
            full_copy="allowed",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["disposition"], "retained")
        self.assertIsNotNone(self.vm("candidate-id-1"))


if __name__ == "__main__":
    unittest.main()
