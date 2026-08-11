import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "providers" / "workspaces" / "receipts.py"


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "private" / "workspaces"

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, *arguments, check=True):
        result = subprocess.run(
            [sys.executable, str(CLI), "--state-dir", str(self.state), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(result.stderr)
        return result

    def create(self, *, intent="isolated", cleanup="release"):
        result = self.run_cli(
            "create",
            "--provider", "fixture",
            "--intent", intent,
            "--mechanism", (
                "provider_disposable_overlay"
                if intent == "isolated" else "existing_instance"
            ),
            "--retention", (
                "discardOnRelease" if intent == "isolated" else "retained"
            ),
            "--cleanup", cleanup,
            "--state", "running",
            "--target-name", "private target name",
            "--target-id", "private-target-id",
            "--source-name", "private source name",
            "--source-id", "private-source-id",
        )
        return result.stdout.strip()

    def test_private_receipt_and_public_inventory(self):
        handle = self.create()
        self.assertRegex(handle, r"^w-[0-9a-f]{24}$")
        receipt_path = self.state / f"{handle}.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["target"]["name"], "private target name")
        if os.name != "nt":
            self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
            self.assertEqual(receipt_path.stat().st_mode & 0o777, 0o600)

        inventory = self.run_cli("inventory").stdout
        value = json.loads(inventory)
        self.assertEqual(value["counts"], {"temporary": 1, "retained": 0})
        self.assertEqual(value["workspaces"][0]["handle"], handle)
        self.assertNotIn("private target name", inventory)
        self.assertNotIn("private-target-id", inventory)
        self.assertNotIn("source", inventory)

    def test_find_and_allowlisted_field(self):
        handle = self.create(intent="persistent", cleanup="none")
        found = self.run_cli(
            "find", "--provider", "fixture",
            "--target-id", "private-target-id",
            "--intent", "persistent",
        )
        self.assertEqual(found.stdout.strip(), handle)
        field = self.run_cli(
            "field", "--handle", handle, "--field", "target.id"
        )
        self.assertEqual(field.stdout.strip(), "private-target-id")

    def test_update_gc_and_forget(self):
        handle = self.create()
        gc_value = json.loads(self.run_cli("gc").stdout)
        self.assertEqual(gc_value["count"], 1)
        self.run_cli(
            "update", "--handle", handle,
            "--state", "off", "--cleanup", "pending",
        )
        inventory = json.loads(self.run_cli("inventory").stdout)
        self.assertEqual(inventory["workspaces"][0]["state"], "off")
        self.assertEqual(inventory["workspaces"][0]["cleanup"], "pending")
        self.run_cli("forget", "--handle", handle)
        self.assertEqual(json.loads(self.run_cli("inventory").stdout)["workspaces"], [])

    def test_invalid_handle_never_selects_a_path(self):
        result = self.run_cli(
            "field", "--handle", "../private", "--field", "target.id",
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid workspace handle", result.stderr)


if __name__ == "__main__":
    unittest.main()
