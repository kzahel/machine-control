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
    def test_linux_local_host_selects_native_adapter(self):
        target = machine_control.default_host_target("Linux")
        self.assertEqual(target["platform"], "linux")
        self.assertEqual(target["profile"], "linux-host-desktop")
        self.assertEqual(target["launcher"], "python")
        self.assertEqual(target["claimPolicy"], "required")
        self.assertTrue(Path(target["command"][0]).is_file())
    def test_windows_local_host_selects_native_adapter(self):
        target = machine_control.default_host_target("Windows")
        self.assertEqual(target["platform"], "windows")
        self.assertEqual(target["launcher"], "python")
        self.assertEqual(target["claimPolicy"], "required")
        self.assertTrue(Path(target["command"][0]).is_file())
        self.assertEqual(machine_control.default_host_target("Darwin")["profile"], "macos-host-resident")

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
        workspace_default_intent="persistent",
        claim_policy="test_default",
    ):
        target = {
            "platform": platform,
            "profile": "fixture",
            "controllerPlatforms": controller_platforms
            or [machine_control.controller_platform()],
            "launcher": launcher,
            "command": command or [sys.executable, str(MOCK)],
        }
        if workspace_default_intent is not None:
            target["workspaceDefaultIntent"] = workspace_default_intent
        if claim_policy == "test_default":
            target["claimPolicy"] = (
                "unsupported" if interface == "native" else "optional"
            )
        elif claim_policy is not None:
            target["claimPolicy"] = claim_policy
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
        # Keep this controller's real per-user configuration out of fixtures.
        environment["XDG_CONFIG_HOME"] = str(self.directory / "config")
        environment["APPDATA"] = str(self.directory / "config")
        environment.pop("MACHINE_CONTROL_HOST_ATTENDANCE", None)
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
        self.assertEqual(
            value["targets"][0]["workspaceDefaultIntent"], "persistent"
        )
        self.assertEqual(value["targets"][0]["claimPolicy"], "optional")

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

    def test_vm_registry_defaults_claim_policy_to_required(self):
        self.write_registry("linux", claim_policy=None)
        result, value = self.run_cli("targets")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["targets"][0]["claimPolicy"], "required")

    def test_native_registry_rejects_required_claim_policy(self):
        self.write_registry(
            "ios", interface="native", claim_policy="required"
        )
        result, value = self.run_cli("targets")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "invalid_registry")

    def test_claim_capabilities_and_status_are_discoverable(self):
        result, value = self.run_cli(
            "--target", "fixture", "claim", "capabilities"
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["mode"], "exclusive")
        self.assertEqual(value["useClasses"], {
            "supported": ["ordinary", "disruptive"],
            "default": "ordinary",
        })
        self.assertEqual(value["durations"]["defaultSeconds"], 1800)
        self.assertEqual(value["target"]["logicalTarget"], "fixture")

        result, value = self.run_cli(
            "--target", "fixture", "claim", "status",
            extra_env={"MACHINE_CONTROL_MOCK_CLAIM_HELD": "1"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["state"], "held")
        self.assertEqual(
            value["data"]["claim"]["claimant"]["assurance"],
            "self_asserted",
        )

    def test_claim_and_workspace_help_explain_cleanup(self):
        result, value = self.run_cli(
            "--target", "fixture", "claim", "--help"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(value)
        self.assertIn("--claimant-authority", result.stdout)
        self.assertIn("--disruptive", result.stdout)
        self.assertIn("release from cleanup", result.stdout)

        result, value = self.run_cli(
            "--target", "fixture", "workspace", "--help"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(value)
        self.assertIn("already-acquired", result.stdout)
        self.assertIn("workspace release", result.stdout)

    def test_claim_acquire_translates_duration_and_bounded_metadata(self):
        log = self.directory / "arguments.json"
        result, value = self.run_cli(
            "--target", "fixture", "claim", "acquire",
            "--duration", "30m",
            "--reason", "exercise fixture",
            "--claimant-authority", "test-runner",
            "--claimant-id", "case-1",
            "--session-id", "session-1",
            "--label", "client test",
            "--metadata", "suite=client",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["claim"]["mode"], "exclusive")
        self.assertEqual(value["data"]["claim"]["useClass"], "ordinary")
        arguments = json.loads(log.read_text(encoding="utf-8"))
        self.assertEqual(
            arguments[arguments.index("--duration-seconds") + 1], "1800"
        )
        metadata = json.loads(
            arguments[arguments.index("--metadata-json") + 1]
        )
        self.assertEqual(metadata, {"suite": "client"})

    def test_claim_acquire_forwards_explicit_disruptive_use(self):
        log = self.directory / "arguments.json"
        result, value = self.run_cli(
            "--target", "fixture", "claim", "acquire",
            "--disruptive",
            "--reason", "recover the fixture",
            "--claimant-authority", "test-runner",
            "--claimant-id", "case-1",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["claim"]["useClass"], "disruptive")
        self.assertIn(
            "--disruptive", json.loads(log.read_text(encoding="utf-8"))
        )

    def test_claim_renew_and_release_validate_opaque_id(self):
        claim_id = "c-0123456789abcdef01234567"
        result, value = self.run_cli(
            "--target", "fixture", "claim", "renew", claim_id,
            "--duration", "1h",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["claim"]["claimId"], claim_id)
        result, value = self.run_cli(
            "--target", "fixture", "claim", "release", claim_id
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["disposition"], "released")

        result, value = self.run_cli(
            "--target", "fixture", "claim", "release", "not-a-claim"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "invalid_claim_id")

    def test_required_target_refuses_use_without_claim_before_dispatch(self):
        log = self.directory / "arguments.json"
        self.write_registry("linux", claim_policy="required")
        result, value = self.run_cli(
            "--target", "fixture", "desktop", "status",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "claim_required")
        self.assertEqual(
            value["data"]["remediation"]["operation"], "claim.acquire"
        )
        self.assertFalse(log.exists())

    def test_required_target_checks_and_forwards_selected_claim(self):
        claim_id = "c-0123456789abcdef01234567"
        self.write_registry("linux", claim_policy="required")
        result, value = self.run_cli(
            "--target", "fixture", "--claim", claim_id,
            "desktop", "status",
            extra_env={"MACHINE_CONTROL_MOCK_EXPECT_CLAIM": claim_id},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["operation"], "status")

    def test_expired_claim_refuses_before_target_operation(self):
        claim_id = "c-0123456789abcdef01234567"
        log = self.directory / "arguments.json"
        self.write_registry("linux", claim_policy="required")
        result, value = self.run_cli(
            "--target", "fixture", "--claim", claim_id,
            "desktop", "status",
            extra_env={
                "MACHINE_CONTROL_MOCK_CLAIM_EXPIRED": "1",
                "MACHINE_CONTROL_MOCK_LOG": str(log),
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["errorCode"], "claim_expired")
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8"))[0], "claim-check"
        )

    def test_outer_vm_command_requires_a_disruptive_claim(self):
        claim_id = "c-0123456789abcdef01234567"
        log = self.directory / "arguments.json"
        self.write_registry("linux", claim_policy="required")
        result, value = self.run_cli(
            "--target", "fixture", "--claim", claim_id,
            "testbed", "--", "screenshot",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["errorCode"], "disruptive_claim_required")
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8")),
            [
                "claim-check", "--claim-id", claim_id,
                "--required-use-class", "disruptive", "--json",
            ],
        )

    def test_outer_vm_command_dispatches_with_a_disruptive_claim(self):
        claim_id = "c-0123456789abcdef01234567"
        log = self.directory / "arguments.json"
        self.write_registry("linux", claim_policy="required")
        result, value = self.run_cli(
            "--target", "fixture", "--claim", claim_id,
            "testbed", "--", "screenshot",
            extra_env={
                "MACHINE_CONTROL_MOCK_CLAIM_USE_CLASS": "disruptive",
                "MACHINE_CONTROL_MOCK_LOG": str(log),
            },
        )
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(value)
        self.assertEqual(result.stdout.strip(), "provider-dispatched")
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8")), ["screenshot"]
        )

    def test_required_target_keeps_doctor_claim_free(self):
        self.write_registry("linux", claim_policy="required")
        result, value = self.run_cli(
            "--target", "fixture", "target", "doctor"
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["ready"])

    def test_required_workspace_acquire_returns_atomic_claim(self):
        self.write_registry("linux", claim_policy="required")
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "acquire",
            "--intent", "isolated",
            "--claim-duration", "30m",
            "--reason", "isolated fixture work",
            "--claimant-authority", "test-runner",
            "--claimant-id", "case-1",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["claim"]["mode"], "exclusive")
        self.assertEqual(value["data"]["claim"]["useClass"], "ordinary")

    def test_required_workspace_acquire_requires_attribution(self):
        log = self.directory / "arguments.json"
        self.write_registry("linux", claim_policy="required")
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "acquire",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "claim_metadata_required")
        self.assertFalse(log.exists())

    def test_required_workspace_release_forwards_claim_to_adapter(self):
        claim_id = "c-0123456789abcdef01234567"
        self.write_registry("linux", claim_policy="required")
        result, value = self.run_cli(
            "--target", "fixture", "--claim", claim_id,
            "workspace", "release", "w-fixture-isolated",
            extra_env={"MACHINE_CONTROL_MOCK_EXPECT_CLAIM": claim_id},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["disposition"], "discarded")

        result, value = self.run_cli(
            "--target", "fixture", "workspace", "release",
            "w-fixture-isolated",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "claim_required")

    def test_native_target_uses_explicit_testbed_escape(self):
        self.write_registry("steamdeck", interface="native")
        result, _ = self.run_cli(
            "--target", "fixture", "target", "status"
        )
        self.assertEqual(result.returncode, 2)
        result, _ = self.run_cli(
            "--target", "fixture", "testbed", "--", "probe"
        )
        self.assertEqual(result.returncode, 0)

    def test_chromeos_native_target_exposes_common_readiness(self):
        log = self.directory / "arguments.json"
        self.write_registry("chromeos", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "target", "status",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["ready"])
        self.assertEqual(value["data"]["states"]["boot"], "ready")
        self.assertEqual(value["target"]["interface"], "native")
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8")), ["common-doctor"]
        )

    def test_native_device_exposes_common_outer_status(self):
        self.write_registry("ios", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "target", "status"
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["ready"])
        self.assertEqual(value["data"]["states"]["connection"], "ready")
        self.assertEqual(value["target"]["interface"], "native")

    def test_linux_reboot_uses_declared_lifecycle(self):
        result, value = self.run_cli("--target", "fixture", "target", "reboot")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["operation"], "target.reboot")
        self.assertEqual(value["data"]["powerState"], "running")

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

    def test_native_device_refuses_desktop_readiness_mutation(self):
        self.write_registry("ios", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "target", "ensure-ready"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "unsupported_target_operation")

    def test_ios_common_capabilities_use_typed_adapter_stdin(self):
        log = self.directory / "arguments.json"
        self.write_registry("ios", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "ios", "capabilities",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["operation"], "capabilities")
        self.assertEqual(value["client"]["logicalTarget"], "fixture")
        self.assertEqual(json.loads(log.read_text(encoding="utf-8")), ["control"])
        self.assertEqual(
            value["data"]["request"], {"operation": "capabilities"}
        )

    def test_ios_common_fill_is_not_placed_in_adapter_arguments(self):
        log = self.directory / "arguments.json"
        self.write_registry("ios", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "ios", "fill", "label=Query",
            "fixture text", "--settle",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(log.read_text(encoding="utf-8")), ["control"])
        self.assertEqual(
            value["data"]["request"],
            {
                "operation": "semantic.fill",
                "target": "label=Query",
                "text": "fixture text",
                "settle": True,
            },
        )

    def test_ios_common_open_url_uses_typed_adapter_stdin(self):
        log = self.directory / "arguments.json"
        self.write_registry("ios", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "ios", "application", "open-url",
            "com.example.fixture", "https://example.test/path", "--relaunch",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(log.read_text(encoding="utf-8")), ["control"])
        self.assertEqual(
            value["data"]["request"],
            {
                "operation": "application.open_url",
                "application": "com.example.fixture",
                "url": "https://example.test/path",
                "relaunch": True,
            },
        )

    def test_ios_common_copy_from_keeps_paths_in_typed_request(self):
        self.write_registry("ios", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "ios", "application", "copy-from",
            "com.example.fixture", "/Documents/export.db", "/tmp/export.db",
            "--max-bytes", "4096",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            value["data"]["request"],
            {
                "operation": "application.copy_from",
                "application": "com.example.fixture",
                "source": "/Documents/export.db",
                "destination": "/tmp/export.db",
                "maxBytes": 4096,
            },
        )

    def test_ios_common_logs_expose_explicit_start_and_collect(self):
        self.write_registry("ios", interface="native")
        started, start_value = self.run_cli(
            "--target", "fixture", "ios", "logs", "start"
        )
        collected, collect_value = self.run_cli(
            "--target", "fixture", "ios", "logs", "collect",
            "/tmp/fixture.log", "--max-bytes", "2048",
        )
        self.assertEqual(started.returncode, 0)
        self.assertEqual(collected.returncode, 0)
        self.assertEqual(
            start_value["data"]["request"],
            {"operation": "diagnostics.logs.start"},
        )
        self.assertEqual(
            collect_value["data"]["request"],
            {
                "operation": "diagnostics.logs.collect",
                "output": "/tmp/fixture.log",
                "maxBytes": 2048,
            },
        )

    def test_ios_common_uninstall_uses_exact_application(self):
        self.write_registry("ios", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "ios", "application", "uninstall",
            "com.example.fixture",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            value["data"]["request"],
            {
                "operation": "application.uninstall",
                "application": "com.example.fixture",
            },
        )

    def test_ios_common_system_logs_expose_start_and_bounded_collect(self):
        self.write_registry("ios", interface="native")
        started, start_value = self.run_cli(
            "--target", "fixture", "ios", "system-logs", "start"
        )
        collected, collect_value = self.run_cli(
            "--target", "fixture", "ios", "system-logs", "collect",
            "/tmp/system.log", "--max-bytes", "4096",
        )
        self.assertEqual(started.returncode, 0)
        self.assertEqual(collected.returncode, 0)
        self.assertEqual(
            start_value["data"]["request"],
            {"operation": "diagnostics.system_logs.start"},
        )
        self.assertEqual(
            collect_value["data"]["request"],
            {
                "operation": "diagnostics.system_logs.collect",
                "output": "/tmp/system.log",
                "maxBytes": 4096,
            },
        )

    def test_ios_common_crash_inventory_and_collect_are_typed(self):
        self.write_registry("ios", interface="native")
        listed, list_value = self.run_cli(
            "--target", "fixture", "ios", "crashes", "list",
            "--match", "Fixture",
        )
        collected, collect_value = self.run_cli(
            "--target", "fixture", "ios", "crashes", "collect",
            "DiagnosticLogs/Fixture.ips", "/tmp/Fixture.ips",
            "--max-bytes", "8192",
        )
        self.assertEqual(listed.returncode, 0)
        self.assertEqual(collected.returncode, 0)
        self.assertEqual(
            list_value["data"]["request"],
            {
                "operation": "diagnostics.crashes.list",
                "match": "Fixture",
            },
        )
        self.assertEqual(
            collect_value["data"]["request"],
            {
                "operation": "diagnostics.crashes.collect",
                "source": "DiagnosticLogs/Fixture.ips",
                "output": "/tmp/Fixture.ips",
                "maxBytes": 8192,
            },
        )

    def test_ios_common_family_refuses_non_ios_target_without_dispatch(self):
        log = self.directory / "arguments.json"
        self.write_registry("android", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "ios", "capabilities",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "unsupported_ios_target")
        self.assertFalse(log.exists())

    def test_ios_result_requires_common_host_interference(self):
        self.write_registry("ios", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "ios", "capabilities",
            extra_env={"MACHINE_CONTROL_MOCK_OMIT_HOST_INTERFERENCE": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["errorCode"], "invalid_resident_result")

    def test_windows_reboot_remains_platform_escape(self):
        self.write_registry("windows")
        result, value = self.run_cli(
            "--target", "fixture", "target", "reboot"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "unsupported_target_operation")

    def test_desktop_capabilities_report_unavailable_suspend(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "capabilities",
            extra_env={"MACHINE_CONTROL_MOCK_SUSPEND_UNAVAILABLE": "1"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("suspend", value["data"]["lifecycleOperations"])
        self.assertEqual(
            value["data"]["lifecycle"],
            {
                "suspend": {
                    "availability": "unavailable",
                    "source": "configured",
                    "reasons": ["configured-disabled"],
                },
                "defaultDownAction": "guest-shutdown",
            },
        )

    def test_desktop_suspend_refuses_before_adapter_dispatch(self):
        log = self.directory / "arguments.json"
        result, value = self.run_cli(
            "--target", "fixture", "target", "suspend",
            extra_env={
                "MACHINE_CONTROL_MOCK_LOG": str(log),
                "MACHINE_CONTROL_MOCK_SUSPEND_UNAVAILABLE": "1",
            },
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "unsupported_target_operation")
        self.assertIn("configured-disabled", value["message"])
        self.assertEqual(
            value["data"]["lifecycle"]["suspend"]["reasons"],
            ["configured-disabled"],
        )
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8")), ["doctor", "--json"]
        )

    def test_invalid_lifecycle_capabilities_fail_typed(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "capabilities",
            extra_env={"MACHINE_CONTROL_MOCK_BAD_LIFECYCLE": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["errorCode"], "invalid_doctor_result")

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

    def test_ensure_ready_is_noop_when_already_ready(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "ensure-ready"
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["ready"])
        self.assertEqual(value["data"]["actions"], [])
        self.assertEqual(value["data"]["completion"], "ready")

    def test_ensure_ready_starts_an_off_target(self):
        state = self.directory / "power-state"
        state.write_text("off", encoding="utf-8")
        result, value = self.run_cli(
            "--target", "fixture", "target", "ensure-ready",
            extra_env={"MACHINE_CONTROL_MOCK_STATE_FILE": str(state)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["ready"])
        self.assertEqual(value["data"]["initial"]["states"]["power"], "off")
        self.assertEqual(value["data"]["actions"][0]["id"], "start")
        self.assertEqual(state.read_text(encoding="utf-8"), "running")

    def test_ensure_ready_does_not_guess_a_running_repair(self):
        state = self.directory / "power-state"
        state.write_text("running", encoding="utf-8")
        result, value = self.run_cli(
            "--target", "fixture", "target", "ensure-ready",
            extra_env={
                "MACHINE_CONTROL_MOCK_NOT_READY": "1",
                "MACHINE_CONTROL_MOCK_STATE_FILE": str(state),
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(value["data"]["ready"])
        self.assertEqual(value["data"]["actions"], [])
        self.assertEqual(
            value["data"]["errorCode"], "readiness_repair_required"
        )
        self.assertEqual(
            value["data"]["recommendedActions"],
            [{
                "operation": "maintenance.audit",
                "profile": "development",
                "mutatesTarget": False,
            }],
        )

    def test_maintenance_capabilities_do_not_dispatch(self):
        log = self.directory / "arguments.json"
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "capabilities",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            value["schema"], "machine-control-maintenance-capabilities/v0"
        )
        self.assertFalse(value["operations"]["audit"]["mutatesTarget"])
        self.assertTrue(
            value["operations"]["certify"]["requiresCleanCommittedSource"]
        )
        self.assertFalse(log.exists())

    def test_chromeos_maintenance_capabilities_are_partial_and_noninvoking(self):
        log = self.directory / "arguments.json"
        self.write_registry("chromeos", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "capabilities",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["profiles"], ["runtime"])
        self.assertEqual(
            value["operations"]["audit"]["availability"], "available"
        )
        self.assertEqual(
            value["operations"]["repair"]["requiresExactCandidate"], False
        )
        self.assertEqual(
            value["operations"]["certify"]["availability"], "unavailable"
        )
        self.assertFalse(log.exists())

    def test_chromeos_unavailable_certification_refuses_before_dispatch(self):
        log = self.directory / "arguments.json"
        self.write_registry("chromeos", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "certify",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            value["errorCode"], "maintenance_operation_unavailable"
        )
        self.assertFalse(log.exists())

    def test_chromeos_audit_uses_runtime_profile_and_allows_locked_doctor(self):
        log = self.directory / "arguments.json"
        self.write_registry("chromeos", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "audit",
            extra_env={
                "MACHINE_CONTROL_MOCK_LOG": str(log),
                "MACHINE_CONTROL_MOCK_MAINTENANCE_DOCTOR_NOT_READY": "1",
            },
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["healthy"])
        self.assertEqual(value["data"]["profile"], "runtime")
        self.assertFalse(value["data"]["readiness"]["ready"])
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8")),
            ["maintenance", "audit", "--profile", "runtime", "--json"],
        )

    def test_chromeos_repair_dispatches_explicit_proof_reboot(self):
        log = self.directory / "arguments.json"
        self.write_registry("chromeos", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "repair", "--reboot",
            "--profile", "runtime",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["reboot"]["requested"])
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8")),
            [
                "maintenance", "repair", "--profile", "runtime",
                "--reboot", "--json",
            ],
        )

    def test_maintenance_audit_dispatches_and_minimizes_platform_result(self):
        log = self.directory / "arguments.json"
        for platform_name in ("windows", "macos", "linux"):
            with self.subTest(platform=platform_name):
                self.write_registry(platform_name)
                result, value = self.run_cli(
                    "--target", "fixture", "maintenance", "audit",
                    "--profile", "runtime",
                    extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    value["schema"], "machine-control-maintenance/v0"
                )
                self.assertTrue(value["data"]["healthy"])
                self.assertEqual(value["data"]["profile"], "runtime")
                self.assertEqual(
                    json.loads(log.read_text(encoding="utf-8")),
                    [
                        "post-update", "audit", "--profile", "runtime",
                        "--json",
                    ],
                )
                self.assertNotIn("private-observation", result.stdout)
                self.assertNotIn("privateDetail", result.stdout)

    def test_maintenance_repair_preserves_explicit_reboot(self):
        log = self.directory / "arguments.json"
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "repair", "--reboot",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["reboot"]["requested"])
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8")),
            [
                "post-update", "repair", "--profile", "development",
                "--reboot", "--json",
            ],
        )

    def test_maintenance_certify_projects_exact_source_without_private_state(self):
        log = self.directory / "arguments.json"
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "certify",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["reboot"]["observed"])
        self.assertEqual(value["data"]["finalPower"], "off")
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8")),
            ["appliance-certify", "--profile", "development", "--json"],
        )
        self.assertNotIn("privateBootEpoch", result.stdout)
        self.assertNotIn("privateStage", result.stdout)

    def test_maintenance_preserves_valid_unhealthy_result_and_exit(self):
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "audit",
            extra_env={"MACHINE_CONTROL_MOCK_UNHEALTHY_MAINTENANCE": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(value["data"]["healthy"])
        self.assertEqual(value["data"]["failure"], "fixture_unhealthy")

    def test_maintenance_rejects_invalid_platform_result(self):
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "audit",
            extra_env={"MACHINE_CONTROL_MOCK_BAD_MAINTENANCE": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["errorCode"], "invalid_maintenance_result")

    def test_maintenance_refuses_mismatched_interface_before_dispatch(self):
        log = self.directory / "arguments.json"
        self.write_registry("linux", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "audit",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            value["errorCode"], "unsupported_maintenance_interface"
        )
        self.assertFalse(log.exists())

    def test_maintenance_reboot_is_repair_only(self):
        result, value = self.run_cli(
            "--target", "fixture", "maintenance", "audit", "--reboot"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "invalid_maintenance_reboot")

    def test_ensure_ready_observes_after_reported_start_failure(self):
        state = self.directory / "power-state"
        state.write_text("off", encoding="utf-8")
        result, value = self.run_cli(
            "--target", "fixture", "target", "ensure-ready",
            extra_env={
                "MACHINE_CONTROL_MOCK_STATE_FILE": str(state),
                "MACHINE_CONTROL_MOCK_UP_FAIL": "1",
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(value["data"]["ready"])
        self.assertEqual(value["data"]["completion"], "action_failed")
        self.assertEqual(
            value["data"]["actions"][0]["status"], "reportedFailed"
        )
        self.assertNotIn("private-adapter-failure", result.stdout)

    def test_candidate_validation_requires_running_ready_candidate(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "validate-candidate"
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["identityPin"], "verified")
        self.assertFalse(value["data"]["eligibleForPrivatePromotion"])
        self.assertEqual(value["data"]["finalPowerState"], "running")

    def test_prepare_promotion_observes_ready_then_stopped_identity(self):
        state = self.directory / "power-state"
        state.write_text("running", encoding="utf-8")
        result, value = self.run_cli(
            "--target", "fixture", "target", "prepare-promotion",
            extra_env={"MACHINE_CONTROL_MOCK_STATE_FILE": str(state)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["eligibleForPrivatePromotion"])
        self.assertEqual(value["data"]["finalPowerState"], "off")
        self.assertEqual(value["data"]["actions"][0]["id"], "clean-shutdown")
        self.assertEqual(state.read_text(encoding="utf-8"), "off")

    def test_lifecycle_suppresses_adapter_network_output(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "up"
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["powerState"], "running")
        self.assertNotIn("private-adapter-detail", result.stdout)

    def test_linux_promotion_refuses_missing_handoff_before_shutdown(self):
        state = self.directory / "power-state"
        state.write_text("running", encoding="utf-8")
        result, value = self.run_cli(
            "--target", "fixture", "target", "prepare-promotion",
            extra_env={"MACHINE_CONTROL_MOCK_STATE_FILE": str(state),
                       "MACHINE_CONTROL_MOCK_CREDENTIAL_FAIL": "verify"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("credential_handoff_required", result.stdout)
        self.assertNotIn("eligibleForPrivatePromotion", result.stdout)
        self.assertEqual(state.read_text(), "running")

    def test_linux_promotion_rechecks_credential_receipt_after_shutdown(self):
        state = self.directory / "power-state"
        state.write_text("running", encoding="utf-8")
        result, value = self.run_cli(
            "--target", "fixture", "target", "prepare-promotion",
            extra_env={"MACHINE_CONTROL_MOCK_STATE_FILE": str(state),
                       "MACHINE_CONTROL_MOCK_CREDENTIAL_FAIL": "status"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("credential_handoff_required", result.stdout)
        self.assertNotIn("eligibleForPrivatePromotion", result.stdout)
        self.assertEqual(state.read_text(), "off")

    def test_candidate_validation_does_not_require_completed_credentials(self):
        result, value = self.run_cli(
            "--target", "fixture", "target", "validate-candidate",
            extra_env={"MACHINE_CONTROL_MOCK_CREDENTIAL_FAIL": "verify"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(value["data"]["eligibleForPrivatePromotion"])

    def test_workspace_capabilities_are_validated_and_projected(self):
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "capabilities"
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            value["schema"], "machine-control-workspace-capabilities/v0"
        )
        self.assertEqual(value["defaultIntent"], "persistent")
        self.assertEqual(value["target"]["logicalTarget"], "fixture")
        self.assertEqual(
            value["intents"]["isolated"]["mechanisms"][0]["kind"],
            "provider_disposable_overlay",
        )

    def test_workspace_acquire_uses_configured_default(self):
        log = self.directory / "arguments.json"
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "acquire",
            extra_env={"MACHINE_CONTROL_MOCK_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["requestedIntent"], "persistent")
        self.assertEqual(
            json.loads(log.read_text(encoding="utf-8")),
            ["workspace-acquire", "--intent", "persistent", "--json"],
        )

    def test_workspace_acquire_accepts_explicit_isolated_intent(self):
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "acquire",
            "--intent", "isolated",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            value["data"]["actualMechanism"],
            "provider_disposable_overlay",
        )
        self.assertEqual(value["data"]["retention"], "discardOnRelease")

    def test_workspace_acquire_requires_intent_without_default(self):
        self.write_registry("linux", workspace_default_intent=None)
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "acquire"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "workspace_intent_required")

    def test_native_target_refuses_workspace_interface(self):
        self.write_registry("ios", interface="native")
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "capabilities"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "unsupported_workspace_interface")

    def test_workspace_refusal_is_preserved(self):
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "acquire",
            "--intent", "candidate",
            extra_env={"MACHINE_CONTROL_MOCK_WORKSPACE_REFUSAL": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(value["accepted"])
        self.assertEqual(value["errorCode"], "intent_unavailable")

    def test_workspace_result_rejects_private_provider_fields(self):
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "acquire",
            extra_env={"MACHINE_CONTROL_MOCK_PRIVATE_WORKSPACE_FIELD": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["errorCode"], "invalid_workspace_result")
        self.assertNotIn("private-vm-fixture", result.stdout)

    def test_workspace_capability_omission_is_typed(self):
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "capabilities",
            extra_env={"MACHINE_CONTROL_MOCK_BAD_WORKSPACE_CAPABILITIES": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["errorCode"], "invalid_workspace_capabilities")

    def test_workspace_inventory_and_gc_dry_run(self):
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "inventory"
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["counts"]["temporary"], 1)
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "gc", "--dry-run"
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(value["data"]["dryRun"])

    def test_workspace_release_validates_opaque_handle(self):
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "release", "not-a-handle"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "invalid_workspace_handle")
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "release",
            "w-fixture-isolated",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["data"]["disposition"], "discarded")

    def test_workspace_gc_is_dry_run_only(self):
        result, value = self.run_cli(
            "--target", "fixture", "workspace", "gc"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            value["errorCode"], "workspace_gc_requires_dry_run"
        )

    def test_workspace_handle_selects_later_adapter_calls(self):
        handle = "w-fixture-isolated"
        result, value = self.run_cli(
            "--target", "fixture", "--workspace", handle,
            "desktop", "status",
            extra_env={"MACHINE_CONTROL_MOCK_EXPECT_WORKSPACE": handle},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["client"]["logicalTarget"], "fixture")

        result, value = self.run_cli(
            "--target", "fixture", "--workspace", handle,
            "target", "status",
            extra_env={"MACHINE_CONTROL_MOCK_EXPECT_WORKSPACE": handle},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(value["target"]["workspaceHandle"], handle)

    def test_invalid_workspace_selector_fails_before_adapter(self):
        result, value = self.run_cli(
            "--target", "fixture", "--workspace", "../private",
            "target", "status",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "invalid_workspace_handle")

    def test_workspace_management_refuses_selected_workspace(self):
        result, value = self.run_cli(
            "--target", "fixture", "--workspace", "w-fixture-isolated",
            "workspace", "inventory",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "workspace_selection_conflict")

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

    def test_default_host_matches_the_controller_platform(self):
        host = machine_control.DEFAULT_TARGETS["host"]
        platform = machine_control.controller_platform()
        expected = {"windows": ("windows", "windows-host-desktop", "platforms/windows/host/winhost.py"),
                    "linux": ("linux", "linux-host-desktop", "platforms/linux/host/linuxhost.py"),
                    "darwin": ("macos", "macos-host-resident", "platforms/macos/bin/machost")}[platform]
        self.assertEqual(host["platform"], expected[0])
        self.assertEqual(host["profile"], expected[1])
        self.assertEqual(host["claimPolicy"], "required")
        suffix = expected[2]
        self.assertTrue(Path(host["command"][0]).as_posix().endswith(suffix))

    def test_update_requests_are_metadata_only_and_use_existing_transport(self):
        for platform in ("macos", "windows", "linux"):
            self.write_registry(platform)
            for command in ("check", "status"):
                result, value = self.run_cli("--target", "fixture", "update", command)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(value["data"]["request"], {"operation": f"update.{command}"})
        for arguments in ([], ["install"], ["check", "--endpoint", "https://example.com"], ["status", "extra"]):
            with self.assertRaises(machine_control.ClientError):
                machine_control.update_request(arguments)
        self.assertTrue(machine_control.operation_requires_claim("update", ["check"]))

    def test_grant_request_builds_bounded_resident_request(self):
        self.write_registry("macos")
        result, value = self.run_cli(
            "--target", "fixture", "grant", "request", "--scope", "control",
            "--scope", "observe", "--scope", "control", "--duration", "15m",
            "--timeout", "90", "--reason", " Fix the build ",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["request"], {
            "operation": "grant.request", "scopes": ["control", "observe"],
            "durationSeconds": 900, "timeoutSeconds": 90,
            "reason": "Fix the build",
        })
        result, value = self.run_cli("--target", "fixture", "grant", "revoke")
        self.assertEqual(value["data"]["request"], {"operation": "grant.revoke"})

    def test_grant_request_requires_scope_and_reason(self):
        self.write_registry("macos")
        for arguments in (["--scope", "observe"], ["--reason", "x"],
                          ["--scope", "root", "--reason", "x"],
                          ["--scope", "observe", "--reason", "x", "--duration", "soon"]):
            result, value = self.run_cli(
                "--target", "fixture", "grant", "request", *arguments)
            self.assertEqual(result.returncode, 2, arguments)
            self.assertEqual(value["errorCode"], "usage")

    def test_browser_requests_are_typed(self):
        self.write_registry("macos")
        result, value = self.run_cli(
            "--target", "fixture", "browser", "navigate", "--url",
            "https://example.com/", "--new-tab",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["request"], {
            "operation": "browser.navigate", "url": "https://example.com/",
            "newTab": True,
        })
        result, value = self.run_cli(
            "--target", "fixture", "browser", "snapshot", "--tab", "4",
            "--max", "50", "--interactive",
        )
        self.assertEqual(value["data"]["request"], {
            "operation": "browser.snapshot", "tabId": 4, "maxElements": 50,
            "interactiveOnly": True,
        })
        result, value = self.run_cli("--target", "fixture", "browser", "click")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(value["errorCode"], "usage")

    def test_browser_upload_requires_reference_and_absolute_files(self):
        self.write_registry("macos")
        result, value = self.run_cli(
            "--target", "fixture", "browser", "upload", "--reference", "1:2:3",
            "--file", "/tmp/a.png", "--file", "/tmp/b.png",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["request"], {
            "operation": "browser.upload", "reference": "1:2:3",
            "files": ["/tmp/a.png", "/tmp/b.png"],
        })
        for arguments in (["--reference", "1:2:3"], ["--file", "/tmp/a.png"],
                          ["--reference", "1:2:3", "--file", "a.png"]):
            result, value = self.run_cli(
                "--target", "fixture", "browser", "upload", *arguments)
            self.assertEqual(value["errorCode"], "usage", arguments)

    def test_browser_upload_uses_the_targets_path_syntax(self):
        self.write_registry("windows")
        result, value = self.run_cli("--target", "fixture", "browser", "upload",
                                     "--reference", "fixture", "--file", "C:/Temp/upload.png")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["request"]["files"], ["C:/Temp/upload.png"])
        for path in ("/tmp/upload.png", "C:upload.png", "upload.png"):
            result, value = self.run_cli("--target", "fixture", "browser", "upload",
                                         "--reference", "fixture", "--file", path)
            self.assertEqual(value["errorCode"], "usage")

    def test_browser_help_and_wait(self):
        self.write_registry("macos")
        result, value = self.run_cli("--target", "fixture", "browser", "key", "--help")
        self.assertEqual(value["errorCode"], "usage")
        self.assertIn("Enter", value["message"])
        result, value = self.run_cli(
            "--target", "fixture", "browser", "wait", "--tab", "5", "--timeout", "10")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["request"],
                         {"operation": "browser.wait", "tabId": 5, "timeoutMs": 10000})

    def test_browser_cdp_and_eval_requests(self):
        self.write_registry("macos")
        result, value = self.run_cli(
            "--target", "fixture", "browser", "cdp", "--tab", "3", "--method",
            "Page.reload", "--params", '{"ignoreCache":true}',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(value["data"]["request"], {
            "operation": "browser.cdp", "tabId": 3, "method": "Page.reload",
            "params": {"ignoreCache": True},
        })
        result, value = self.run_cli(
            "--target", "fixture", "browser", "eval", "--expression", "document.title")
        self.assertEqual(value["data"]["request"], {
            "operation": "browser.eval", "expression": "document.title"})
        for arguments in (["cdp"], ["cdp", "--method", "X.y", "--params", "[1]"], ["eval"]):
            result, value = self.run_cli("--target", "fixture", "browser", *arguments)
            self.assertEqual(value["errorCode"], "usage", arguments)
        result, value = self.run_cli(
            "--target", "fixture", "grant", "request", "--scope", "devtools",
            "--reason", "debug")
        self.assertEqual(value["data"]["request"]["scopes"], ["devtools"])

    def test_desktop_input_key_help_and_target(self):
        self.write_registry("macos")
        result, value = self.run_cli(
            "--target", "fixture", "desktop", "input", "key", "--help")
        self.assertEqual(value["errorCode"], "usage")
        self.assertIn("cmd+shift+g", value["message"])
        result, value = self.run_cli(
            "--target", "fixture", "desktop", "input", "text", "hello",
            "--target", "com.apple.TextEdit",
        )
        self.assertEqual(value["data"]["request"], {
            "operation": "input.text", "text": "hello",
            "target": "com.apple.TextEdit",
        })

    def test_approval_required_adds_grant_remediation(self):
        self.write_registry("macos")
        result, value = self.run_cli(
            "--target", "fixture", "desktop", "status",
            extra_env={"MACHINE_CONTROL_MOCK_RESIDENT_REFUSAL": "approval_required"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["client"]["remediation"]["command"][:4],
                         ["grant", "request", "--scope", "control"])

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


class RegistryResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.config_home = self.directory / "config"
        self.config_directory = self.config_home / "machine-control"
        self.config_directory.mkdir(parents=True)
        self.checkout = self.directory / "workspace" / "machine-control"
        self.checkout.mkdir(parents=True)
        environment = {
            key: value
            for key, value in os.environ.items()
            if key
            not in {
                "MACHINE_CONTROL_TARGETS_FILE",
                "MACHINE_CONTROL_INVENTORY_PROVIDER",
                "MACHINE_CONTROL_HOST_ATTENDANCE",
            }
        }
        environment.update(
            {
                "XDG_CONFIG_HOME": str(self.config_home),
                "APPDATA": str(self.config_home),
            }
        )
        self.environment = environment
        patches = [
            mock.patch.dict(os.environ, environment, clear=True),
            mock.patch("machine_control.ROOT", self.checkout),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.temporary.cleanup()

    def write_targets(self, path, alias):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema": "machine-control-targets/v0",
            "targets": {
                alias: {
                    "platform": "linux",
                    "profile": "fixture",
                    "controllerPlatforms": [machine_control.controller_platform()],
                    "command": [sys.executable],
                }
            }
        }), encoding="utf-8")

    def write_config(self, **fields):
        (self.config_directory / "config.json").write_text(
            json.dumps({"schema": "machine-control-controller/v0", **fields}),
            encoding="utf-8",
        )

    def write_sibling_provider(self):
        provider = self.checkout.parent / "dotfiles" / "testbeds" / "testbeds.py"
        provider.parent.mkdir(parents=True)
        provider.write_text("", encoding="utf-8")
        return provider

    def test_controller_config_targets_precede_checkout_registry(self):
        self.write_targets(self.checkout / "targets.local.json", "checkout-target")
        self.write_targets(self.config_directory / "targets.json", "config-target")
        self.write_config(targets="targets.json")
        targets, source = machine_control.load_registry(None)
        self.assertEqual(list(targets), ["config-target"])
        self.assertEqual(source, "controller-config")

    def test_environment_registry_precedes_controller_config(self):
        self.write_targets(self.config_directory / "targets.json", "config-target")
        self.write_config(targets="targets.json")
        environment_registry = self.directory / "environment-targets.json"
        self.write_targets(environment_registry, "environment-target")
        with mock.patch.dict(
            os.environ,
            {"MACHINE_CONTROL_TARGETS_FILE": str(environment_registry)},
        ):
            targets, source = machine_control.load_registry(None)
        self.assertEqual(list(targets), ["environment-target"])
        self.assertEqual(source, "environment")

    def test_controller_config_without_targets_uses_checkout_registry(self):
        self.write_targets(self.checkout / "targets.local.json", "checkout-target")
        self.write_config(inventoryProvider=None)
        targets, source = machine_control.load_registry(None)
        self.assertEqual(list(targets), ["checkout-target"])
        self.assertEqual(source, "checkout")

    def test_sibling_provider_is_discovered_without_controller_config(self):
        provider = self.write_sibling_provider()
        self.assertEqual(machine_control.provider_path(), provider)

    def test_controller_config_disables_sibling_provider_discovery(self):
        self.write_sibling_provider()
        self.write_config(inventoryProvider=None)
        self.assertIsNone(machine_control.provider_path())
        targets, source = machine_control.load_registry(None)
        self.assertEqual(source, "defaults")
        self.assertIn("linux", targets)

    def test_controller_config_selects_relative_inventory_provider(self):
        self.write_sibling_provider()
        self.write_config(inventoryProvider="providers/inventory.py")
        self.assertEqual(
            machine_control.provider_path(),
            (self.config_directory / "providers" / "inventory.py").resolve(),
        )

    def test_explicit_provider_precedes_controller_config(self):
        self.write_config(inventoryProvider=None)
        explicit = self.directory / "explicit.py"
        self.assertEqual(
            machine_control.provider_path(str(explicit)), explicit.resolve()
        )

    def test_invalid_controller_config_fails_closed(self):
        self.write_sibling_provider()
        for document in (
            "{",
            json.dumps({"schema": "unexpected"}),
            json.dumps({
                "schema": "machine-control-controller/v0",
                "targets": "",
            }),
            json.dumps({
                "schema": "machine-control-controller/v0",
                "inventory": None,
            }),
        ):
            with self.subTest(document=document):
                (self.config_directory / "config.json").write_text(
                    document, encoding="utf-8"
                )
                with self.assertRaises(machine_control.ClientError) as caught:
                    machine_control.provider_path()
                self.assertEqual(caught.exception.code, "invalid_controller_config")

    def test_cli_reports_source_kind_without_private_path(self):
        self.write_targets(self.config_directory / "targets.json", "config-target")
        self.write_config(targets="targets.json")
        result = subprocess.run(
            [sys.executable, str(CLI), "targets"],
            text=True,
            capture_output=True,
            check=False,
            env=self.environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["registrySource"], "controller-config")
        self.assertEqual(value["targets"][0]["logicalTarget"], "config-target")
        self.assertNotIn(str(self.directory), result.stdout)

    def test_controller_config_validates_host_attendance(self):
        for attendance in ("attended", "unattended"):
            with self.subTest(attendance=attendance):
                self.write_config(hostAttendance=attendance)
                self.assertEqual(
                    machine_control.controller_host_attendance(), attendance
                )
        self.write_config(hostAttendance="sometimes")
        with self.assertRaises(machine_control.ClientError) as caught:
            machine_control.controller_host_attendance()
        self.assertEqual(caught.exception.code, "invalid_controller_config")
        (self.config_directory / "config.json").unlink()
        self.assertIsNone(machine_control.controller_host_attendance())

    def test_cli_passes_host_attendance_to_adapter(self):
        adapter = self.directory / "adapter.py"
        adapter.write_text(
            "import os\n"
            "print(os.environ.get('MACHINE_CONTROL_HOST_ATTENDANCE', 'absent'))\n",
            encoding="utf-8",
        )
        registry = self.config_directory / "targets.json"
        registry.write_text(json.dumps({
            "schema": "machine-control-targets/v0",
            "targets": {
                "fixture": {
                    "platform": "linux",
                    "profile": "fixture",
                    "controllerPlatforms": [machine_control.controller_platform()],
                    "claimPolicy": "optional",
                    "command": [sys.executable, str(adapter)],
                }
            }
        }), encoding="utf-8")
        for fields, expected in (
            ({"hostAttendance": "unattended"}, "unattended"),
            ({}, "absent"),
        ):
            with self.subTest(fields=fields):
                self.write_config(targets="targets.json", **fields)
                result = subprocess.run(
                    [sys.executable, str(CLI), "--target", "fixture",
                     "testbed", "--", "status"],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=self.environment,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.strip(), expected)

    def test_cli_inventory_refuses_when_controller_config_disables_provider(self):
        self.write_config(inventoryProvider=None)
        result = subprocess.run(
            [sys.executable, str(CLI), "inventory", "status"],
            text=True,
            capture_output=True,
            check=False,
            env=self.environment,
        )
        value = json.loads(result.stdout)
        self.assertEqual(value["errorCode"], "inventory_provider_unavailable")


if __name__ == "__main__":
    unittest.main()
