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
        arguments = json.loads(log.read_text(encoding="utf-8"))
        self.assertEqual(
            arguments[arguments.index("--duration-seconds") + 1], "1800"
        )
        metadata = json.loads(
            arguments[arguments.index("--metadata-json") + 1]
        )
        self.assertEqual(metadata, {"suite": "client"})

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

    def test_desktop_reboot_remains_platform_escape(self):
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
