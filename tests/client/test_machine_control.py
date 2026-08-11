#!/usr/bin/env python3

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "bin" / "machine-control"
MOCK = ROOT / "tests" / "client" / "fixtures" / "mock-testbed.py"
sys.path.insert(0, str(ROOT / "client"))
import machine_control  # noqa: E402


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.registry = self.directory / "targets.json"
        self.write_registry("linux")

    def tearDown(self):
        self.temporary.cleanup()

    def write_registry(
        self,
        platform,
        *,
        interface=None,
        environment=None,
        controller_platforms=None,
        launcher="auto",
        command=None,
    ):
        target = {
            "platform": platform,
            "profile": "fixture",
            "controllerPlatforms": controller_platforms
            or [machine_control.controller_platform()],
            "launcher": launcher,
            "command": command or [sys.executable, str(MOCK)],
        }
        if interface is not None:
            target["interface"] = interface
        if environment is not None:
            target["environment"] = environment
        self.registry.write_text(json.dumps({
            "schema": "machine-control-targets/v0",
            "targets": {
                "fixture": target
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
            [sys.executable, str(CLI), "--registry", str(self.registry), *arguments],
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
        self.assertEqual(
            value["targets"][0]["controllerPlatform"],
            machine_control.controller_platform(),
        )
        self.assertTrue(value["targets"][0]["controllerSupported"])
        self.assertTrue(value["targets"][0]["adapterAvailable"])
        self.assertNotIn("command", value["targets"][0])
        self.assertNotIn(str(self.directory), result.stdout)

    def test_lists_native_target_without_private_environment(self):
        self.write_registry(
            "chromeos",
            interface="native",
            environment={"CHROMEBOOK_HOST": "private-fixture-host"},
        )
        result, value = self.run_cli("targets")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["targets"][0]["interface"], "native")
        self.assertNotIn("private-fixture-host", result.stdout)

    def test_native_target_uses_explicit_testbed_escape(self):
        self.write_registry("chromeos", interface="native")
        result, _ = self.run_cli(
            "--target", "fixture", "target", "status"
        )
        self.assertEqual(result.returncode, 2)
        result, _ = self.run_cli(
            "--target", "fixture", "testbed", "--", "probe"
        )
        self.assertEqual(result.returncode, 0)

    def test_native_device_exposes_common_outer_status(self):
        self.write_registry("ios", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "target", "status"
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["ready"])
        self.assertEqual(value["data"]["states"]["connection"], "ready")
        self.assertEqual(value["target"]["interface"], "native")

    def test_native_device_reboot_uses_declared_lifecycle(self):
        log = self.directory / "arguments.json"
        self.write_registry("android", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "target", "reboot",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["operation"], "target.reboot")
        self.assertEqual(json.loads(log.read_text(encoding="utf-8")), ["doctor", "--json"])

    def test_native_device_refuses_undeclared_lifecycle(self):
        self.write_registry("quest", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "target", "shutdown"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "unsupported_target_operation")

    def test_desktop_reboot_remains_platform_escape(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "reboot"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "unsupported_target_operation")

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

    def test_desktop_target_does_not_replace_machine_target(self):
        result, value = self.run_cli(
            "--target", "fixture", "desktop", "snapshot",
            "--target", "fixture-application",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            value["client"]["logicalTarget"], "fixture"
        )
        self.assertEqual(
            value["data"]["request"]["target"],
            "fixture-application",
        )

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

    def test_unsupported_controller_refuses_before_adapter_lookup(self):
        current = machine_control.controller_platform()
        unsupported = next(
            value
            for value in ("darwin", "linux", "windows")
            if value != current
        )
        missing = self.directory / "must-not-be-executed"
        self.write_registry(
            "linux",
            controller_platforms=[unsupported],
            command=[str(missing)],
        )
        listed, listing = self.run_cli("targets")
        self.assertEqual(listed.returncode, 0)
        self.assertFalse(listing["targets"][0]["controllerSupported"])
        self.assertFalse(listing["targets"][0]["adapterAvailable"])
        result, value = self.run_cli(
            "--target", "fixture", "target", "status"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            value["errorCode"], "controller_platform_unsupported"
        )

    def test_python_launcher_uses_active_interpreter(self):
        command = machine_control.launcher_command([str(MOCK)], "python")
        self.assertEqual(command, [sys.executable, str(MOCK)])

    def test_powershell_launcher_is_explicit(self):
        with mock.patch(
            "machine_control.shutil.which",
            side_effect=lambda name: "/fixture/pwsh" if name == "pwsh" else None,
        ):
            command = machine_control.launcher_command(
                ["fixture.ps1", "argument"], "powershell"
            )
        self.assertEqual(
            command,
            [
                "/fixture/pwsh",
                "-NoLogo",
                "-NoProfile",
                "-File",
                "fixture.ps1",
                "argument",
            ],
        )

    def test_bash_launcher_is_explicit(self):
        with mock.patch(
            "machine_control.shutil.which",
            return_value="/fixture/bash",
        ):
            command = machine_control.launcher_command(
                ["fixture.sh", "argument"], "bash"
            )
        self.assertEqual(
            command, ["/fixture/bash", "fixture.sh", "argument"]
        )

    def test_direct_launcher_preserves_command(self):
        with mock.patch(
            "machine_control.path_command_available", return_value=True
        ):
            command = machine_control.launcher_command(
                ["fixture-command", "argument"], "direct"
            )
        self.assertEqual(command, ["fixture-command", "argument"])


if __name__ == "__main__":
    unittest.main()
