#!/usr/bin/env python3

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "bin" / "machine-control"
MOCK = ROOT / "tests" / "client" / "fixtures" / "mock-testbed.py"


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.registry = self.directory / "targets.json"
        self.write_registry("linux")

    def tearDown(self):
        self.temporary.cleanup()

    def write_registry(self, platform):
        self.registry.write_text(json.dumps({
            "schema": "machine-control-targets/v0",
            "targets": {
                "fixture": {
                    "platform": platform,
                    "profile": "fixture",
                    "command": [sys.executable, str(MOCK)]
                }
            }
        }), encoding="utf-8")

    def run_cli(self, *arguments, extra_env=None):
        environment = os.environ.copy()
        document = json.loads(self.registry.read_text(encoding="utf-8"))
        environment["MACHINE_CONTROL_MOCK_PLATFORM"] = (
            document["targets"]["fixture"]["platform"]
        )
        environment.update(extra_env or {})
        result = subprocess.run(
            [str(CLI), "--registry", str(self.registry), *arguments],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        value = (
            json.loads(result.stdout)
            if result.stdout.strip().startswith("{")
            else None
        )
        return result, value

    def test_lists_targets_without_adapter_command(self):
        result, value = self.run_cli("targets")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["targets"][0]["logicalTarget"], "fixture")
        self.assertNotIn("command", value["targets"][0])
        self.assertNotIn(str(self.directory), result.stdout)

    def test_doctor_adds_logical_target(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "doctor"
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["ready"])
        self.assertEqual(value["target"]["logicalTarget"], "fixture")

    def test_not_ready_doctor_is_valid_and_nonzero(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "doctor",
            extra_env={"MACHINE_CONTROL_MOCK_NOT_READY": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(value["ready"])
        self.assertEqual(value["states"]["power"], "off")

    def test_malformed_doctor_fails_typed(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "doctor",
            extra_env={"MACHINE_CONTROL_MOCK_BAD_DOCTOR": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["errorCode"], "invalid_doctor_result")

    def test_lifecycle_suppresses_adapter_network_output(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "up"
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["powerState"], "running")
        self.assertNotIn("private-adapter-detail", result.stdout)

    def test_windows_translates_common_request(self):
        self.write_registry("windows")
        result, value = self.run_cli(
            "--target", "fixture", "desktop", "call",
            '{"operation":"action","action":"press",'
            '"reference":"r1"}',
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["operation"], "invoke")
        self.assertEqual(value["client"]["requestedOperation"], "action")
        self.assertEqual(value["data"]["request"]["reference"], "r1")

    def test_sealed_windows_compatibility_is_explicit(self):
        self.write_registry("windows")
        result, value = self.run_cli(
            "--target", "fixture", "desktop", "status",
            extra_env={
                "MACHINE_CONTROL_MOCK_OMIT_HOST_INTERFERENCE": "1"
            },
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["hostInterference"], "none")
        self.assertEqual(
            value["client"]["compatibilityProjection"],
            ["hostInterference"],
        )

    def test_linux_translates_set_value(self):
        result, value = self.run_cli(
            "--target", "fixture", "desktop", "action",
            "--reference", "r1", "--action", "set_value",
            "--text", "Hello, 世界",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["operation"], "set_value")
        self.assertEqual(value["data"]["request"]["value"], "Hello, 世界")

    def test_local_placement_is_reported(self):
        result, value = self.run_cli(
            "--target", "fixture", "desktop", "call-local",
            '{"operation":"status"}',
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            value["client"]["placement"], "guest_local_cli"
        )

    def test_artifact_uses_bounded_adapter_entry(self):
        result, value = self.run_cli(
            "--target", "fixture", "desktop", "artifact", "opaque-id"
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["handle"], "opaque-id")
        self.assertEqual(value["schema"], "machine-control-artifact/v0")

    def test_os_escape_preserves_arguments(self):
        log = self.directory / "arguments.json"
        result, _ = self.run_cli(
            "--target", "fixture", "os", "--", "printf", "a b",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8")),
            ["exec", "--", "printf", "a b"],
        )

    def test_unknown_target_fails_typed(self):
        result, value = self.run_cli(
            "--target", "absent", "target", "status"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "target_not_found")


if __name__ == "__main__":
    unittest.main()
