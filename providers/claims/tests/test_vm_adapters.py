from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


@unittest.skipIf(shutil.which("bash") is None, "requires POSIX Bash")
class VmClaimAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def adapters(self):
        return (
            (
                ROOT / "platforms" / "windows" / "bin" / "winvm",
                {
                    "WINVM_CONFIG_FILE": "/dev/null",
                    "WINVM_EXPECTED_UTM_ID": "fixture-windows-id",
                    "WINVM_CLAIM_STATE_DIR": str(self.directory / "windows"),
                },
                ["ssh-config", "fixture-user"],
            ),
            (
                ROOT / "platforms" / "linux" / "bin" / "linuxvm",
                {
                    "LINUXVM_CONFIG_FILE": "/dev/null",
                    "LINUXVM_EXPECTED_UUID": "fixture-linux-id",
                    "LINUXVM_CLAIM_STATE_DIR": str(self.directory / "linux"),
                },
                ["bootstrap-command"],
            ),
            (
                ROOT / "platforms" / "macos" / "bin" / "macvm",
                {
                    "MACVM_CONFIG_FILE": "/dev/null",
                    "MACVM_EXPECTED_NAME": "fixture-macos-id",
                    "MACVM_CLAIM_STATE_DIR": str(self.directory / "macos"),
                },
                ["up"],
            ),
        )

    def run_adapter(self, executable, environment, *arguments):
        return subprocess.run(
            [str(executable), *arguments],
            text=True,
            capture_output=True,
            check=False,
            env={
                **os.environ,
                **environment,
                "MACHINE_CONTROL_CLAIM_POLICY": "required",
            },
        )

    def test_vm_adapters_expose_claims_and_gate_effectful_use(self) -> None:
        for executable, environment, effectful in self.adapters():
            with self.subTest(adapter=executable.parent.parent.name):
                result = self.run_adapter(
                    executable, environment, "claim-capabilities", "--json"
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                capabilities = json.loads(result.stdout)
                self.assertEqual(capabilities["mode"], "exclusive")

                result = self.run_adapter(executable, environment, *effectful)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("requires a live claim", result.stderr)

                result = self.run_adapter(
                    executable,
                    environment,
                    "claim-acquire",
                    "--duration-seconds",
                    "60",
                    "--reason",
                    "exercise the adapter boundary",
                    "--claimant-authority",
                    "claim-adapter-tests",
                    "--claimant-id",
                    self.id(),
                    "--metadata-json",
                    '{}',
                    "--json",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                acquired = json.loads(result.stdout)
                claim_id = acquired["data"]["claim"]["claimId"]

                result = self.run_adapter(
                    executable,
                    environment,
                    "claim-check",
                    "--claim-id",
                    claim_id,
                    "--json",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)["accepted"])

                result = self.run_adapter(
                    executable,
                    environment,
                    "claim-release",
                    "--claim-id",
                    claim_id,
                    "--json",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    json.loads(result.stdout)["data"]["disposition"],
                    "released",
                )

    def test_missing_private_identity_points_to_inventory_repair(self) -> None:
        executable = ROOT / "platforms" / "windows" / "bin" / "winvm"
        environment = {
            "WINVM_CONFIG_FILE": "/dev/null",
            "WINVM_CLAIM_STATE_DIR": str(self.directory / "unresolved"),
        }
        result = self.run_adapter(
            executable, environment, "claim-status", "--json"
        )
        self.assertEqual(result.returncode, 1)
        value = json.loads(result.stdout)
        self.assertEqual(value["errorCode"], "claim_identity_unavailable")
        self.assertIn("repair private inventory", value["message"])

        result = self.run_adapter(
            executable, environment, "ssh-config", "fixture-user"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("repair private inventory", result.stderr)


if __name__ == "__main__":
    unittest.main()
