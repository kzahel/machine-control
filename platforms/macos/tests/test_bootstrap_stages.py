import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "scripts/bootstrap-stages.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_stages", SOURCE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def stages(report):
    return {item["name"]: item for item in report["stages"]}


IDENTITY = {"schema": "machine-control-candidate-assertion/v0",
            "identityPin": "verified", "role": "candidate"}
READY = {"schema": "machine-control-doctor/v0", "ready": True,
         "states": {"power": "running", "administration": "ready",
                    "resident": "ready", "desktop": "unlocked"}}


class BootstrapStagesTests(unittest.TestCase):
    def test_preflight_suggests_kind_specific_creation_only_for_unused_name(self):
        environment = {"MACVM_NAME": "new-candidate",
                       "MACVM_EXPECTED_NAME": "new-candidate",
                       "MACVM_TARGET_ROLE": "candidate",
                       "MACVM_REQUIRE_MUTATION_GUARD": "true"}
        with mock.patch.dict(os.environ, environment), \
             mock.patch.object(MODULE.platform, "system", return_value="Darwin"), \
             mock.patch.object(MODULE.platform, "machine", return_value="arm64"), \
             mock.patch.object(MODULE.os, "access", return_value=True), \
             mock.patch.object(MODULE, "host_permissions", return_value={
                 "screenCapture": False, "postEvent": False}), \
             mock.patch.object(MODULE, "document", return_value=[
                 {"Name": "existing", "State": "stopped"}]):
            prepared = stages(MODULE.preflight("prepared"))
            vanilla = stages(MODULE.preflight("vanilla"))
        self.assertEqual(prepared["vm"]["state"], "action_required")
        self.assertEqual(prepared["vm"]["nextCommand"][:2], ["tart", "clone"])
        self.assertEqual(vanilla["vm"]["nextCommand"][:2], ["tart", "create"])
        self.assertEqual(prepared["host-consent"]["state"], "human_required")
        self.assertNotIn("new-candidate", json.dumps(prepared))

    def test_preflight_refuses_unbound_target_configuration(self):
        environment = {"MACVM_NAME": "one", "MACVM_EXPECTED_NAME": "two",
                       "MACVM_TARGET_ROLE": "candidate",
                       "MACVM_REQUIRE_MUTATION_GUARD": "true"}
        with mock.patch.dict(os.environ, environment), \
             mock.patch.object(MODULE.platform, "system", return_value="Darwin"), \
             mock.patch.object(MODULE.platform, "machine", return_value="arm64"), \
             mock.patch.object(MODULE.os, "access", return_value=True), \
             mock.patch.object(MODULE, "host_permissions", return_value=None), \
             mock.patch.object(MODULE, "document") as observed:
            report = stages(MODULE.preflight("prepared"))
        self.assertEqual(report["target-config"]["state"], "blocked")
        self.assertIsNone(report["vm"]["nextCommand"])
        observed.assert_not_called()

    def test_candidate_reports_unknown_desktop_without_guessing_repair(self):
        doctor = {**READY, "ready": False,
                  "states": {**READY["states"], "desktop": "unknown"}}
        def observed(*args, **_kwargs):
            if "candidate-status" in args:
                return IDENTITY
            if "doctor" in args:
                return doctor
            if "health" in args:
                return {"accessibilityTrusted": True}
            if "session-state" in args:
                return None
            raise AssertionError(args)
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "secret"
            secret.write_text("fixture-only")
            secret.chmod(0o600)
            with mock.patch.dict(os.environ, {"MACVM_ADMIN_SECRET_FILE": str(secret)}), \
                 mock.patch.object(MODULE, "document", side_effect=observed), \
                 mock.patch.object(MODULE, "command", return_value=(True, "")), \
                 mock.patch.object(MODULE, "host_permissions", return_value={
                     "screenCapture": False, "postEvent": False}):
                report = stages(MODULE.inspect("prepared"))
        self.assertEqual(report["guest-agent"]["state"], "complete")
        self.assertEqual(report["accessibility"]["state"], "complete")
        self.assertEqual(report["desktop"]["state"], "unverified")
        self.assertEqual(report["desktop"]["nextActionId"], "inspect_guest_session")

    def test_direct_unlocked_probe_suggests_guarded_resident_restart(self):
        doctor = {**READY, "ready": False,
                  "states": {**READY["states"], "desktop": "unknown"}}
        def observed(*args, **_kwargs):
            if "candidate-status" in args:
                return IDENTITY
            if "doctor" in args:
                return doctor
            if "health" in args:
                return {"accessibilityTrusted": True}
            if "session-state" in args:
                return {"desktopState": "unlocked",
                        "observationSource": "iokit.console-session"}
            raise AssertionError(args)
        with mock.patch.object(MODULE, "document", side_effect=observed), \
             mock.patch.object(MODULE, "command", return_value=(True, "")), \
             mock.patch.object(MODULE, "host_permissions", return_value=None):
            report = stages(MODULE.inspect("prepared"))
        self.assertEqual(report["desktop"]["state"], "action_required")
        self.assertEqual(report["desktop"]["nextCommand"],
                         ["bin/macvm", "ui", "resident-restart"])

    def test_vanilla_guest_without_agent_requires_human_setup(self):
        doctor = {**READY, "ready": False,
                  "states": {"power": "running", "administration": "unavailable",
                             "resident": "unavailable", "desktop": "unknown"}}
        def observed(*args, **_kwargs):
            return IDENTITY if "candidate-status" in args else doctor
        with mock.patch.object(MODULE, "document", side_effect=observed), \
             mock.patch.object(MODULE, "stored_credential", return_value=False), \
             mock.patch.object(MODULE, "host_permissions", return_value={
                 "screenCapture": False, "postEvent": False}):
            report = stages(MODULE.inspect("vanilla"))
        self.assertEqual(report["guest-agent"]["state"], "human_required")
        self.assertEqual(report["administrator-authorization"]["state"],
                         "human_required")
        self.assertEqual(report["credential"]["state"], "human_required")
        self.assertEqual(report["outer-bootstrap"]["state"], "human_required")
        self.assertIsNone(report["resident"]["nextCommand"])

    def test_vanilla_stopped_waits_for_account_before_credential(self):
        doctor = {**READY, "ready": False,
                  "states": {"power": "off", "administration": "unavailable",
                             "resident": "unavailable", "desktop": "unknown"}}
        def observed(*args, **_kwargs):
            return IDENTITY if "candidate-status" in args else doctor
        with mock.patch.object(MODULE, "document", side_effect=observed), \
             mock.patch.object(MODULE, "stored_credential", return_value=False), \
             mock.patch.object(MODULE, "host_permissions", return_value={
                 "screenCapture": True, "postEvent": True}):
            report = stages(MODULE.inspect("vanilla"))
        self.assertEqual(report["credential"]["state"], "waiting")
        self.assertEqual(report["credential"]["evidence"],
                         "guest_account_setup_required")
        self.assertIsNone(report["credential"]["nextActionId"])

    def test_prepared_agent_still_needs_outer_consent_route(self):
        doctor = {**READY, "ready": False}
        def observed(*args, **_kwargs):
            if "candidate-status" in args:
                return IDENTITY
            if "doctor" in args:
                return doctor
            if "health" in args:
                return {"accessibilityTrusted": False}
            return None
        with mock.patch.object(MODULE, "document", side_effect=observed), \
             mock.patch.object(MODULE, "command", return_value=(True, "")), \
             mock.patch.object(MODULE, "stored_credential", return_value=True), \
             mock.patch.object(MODULE, "host_permissions", return_value={
                 "screenCapture": False, "postEvent": False}):
            report = stages(MODULE.inspect("prepared"))
        self.assertEqual(report["guest-agent"]["state"], "complete")
        self.assertEqual(report["accessibility"]["state"], "human_required")
        self.assertEqual(report["outer-bootstrap"]["state"], "human_required")
        self.assertEqual(report["outer-bootstrap"]["evidence"],
                         "host_outer_bootstrap_permission_missing")

    def test_screen_recording_gate_suggests_trigger_after_desktop_is_ready(self):
        doctor = {**READY, "ready": False,
                  "states": {**READY["states"], "capture": "unavailable"},
                  "extensions": {"displayState": "active"}}
        def observed(*args, **_kwargs):
            if "candidate-status" in args:
                return IDENTITY
            if "doctor" in args:
                return doctor
            if "health" in args:
                return {"accessibilityTrusted": True}
            if "claim-status" in args:
                return {"data": {"claim": {"claimId": "fixture-claim",
                                           "useClass": "disruptive"}}}
            return None
        with mock.patch.dict(os.environ, {"MACHINE_CONTROL_CLAIM_ID":
                                       "fixture-claim"}), \
             mock.patch.object(MODULE, "document", side_effect=observed), \
             mock.patch.object(MODULE, "command", return_value=(True, "")), \
             mock.patch.object(MODULE, "stored_credential", return_value=True), \
             mock.patch.object(MODULE, "host_permissions", return_value={
                 "screenCapture": True, "postEvent": True}):
            report = stages(MODULE.inspect("prepared"))
        self.assertEqual(report["capture"]["state"], "action_required")
        self.assertEqual(report["capture"]["nextActionId"],
                         "grant_guest_screen_recording")
        self.assertEqual(report["capture"]["nextCommand"][:2],
                         ["bin/macvm", "control"])

    def test_outer_bootstrap_respects_host_policy_and_claim_class(self):
        doctor = {**READY, "ready": False,
                  "states": {**READY["states"], "outer": "prohibited"}}
        claim = {"claimId": "fixture-claim", "useClass": "ordinary"}
        def observed(*args, **_kwargs):
            if "candidate-status" in args:
                return IDENTITY
            if "doctor" in args:
                return doctor
            if "health" in args:
                return {"accessibilityTrusted": False}
            if "claim-status" in args:
                return {"data": {"claim": claim}}
            return None
        with mock.patch.dict(os.environ, {"MACHINE_CONTROL_CLAIM_ID":
                                       "fixture-claim"}), \
             mock.patch.object(MODULE, "document", side_effect=observed), \
             mock.patch.object(MODULE, "command", return_value=(True, "")), \
             mock.patch.object(MODULE, "stored_credential", return_value=True), \
             mock.patch.object(MODULE, "host_permissions", return_value={
                 "screenCapture": True, "postEvent": True}):
            prohibited = stages(MODULE.inspect("prepared"))
            doctor["states"]["outer"] = "unknown"
            ordinary = stages(MODULE.inspect("prepared"))
            claim["useClass"] = "disruptive"
            allowed = stages(MODULE.inspect("prepared"))
        self.assertEqual(prohibited["outer-bootstrap"]["state"], "blocked")
        self.assertEqual(prohibited["outer-bootstrap"]["evidence"],
                         "host_outer_bootstrap_prohibited")
        self.assertEqual(ordinary["outer-bootstrap"]["state"],
                         "action_required")
        self.assertEqual(ordinary["outer-bootstrap"]["nextActionId"],
                         "reacquire_disruptive_claim")
        self.assertEqual(allowed["outer-bootstrap"]["state"], "complete")
        self.assertEqual(allowed["accessibility"]["state"], "action_required")

    def test_missing_guest_tools_names_admin_handoff(self):
        doctor = {**READY, "ready": False,
                  "states": {**READY["states"], "resident": "unavailable"}}
        def observed(*args, **_kwargs):
            if "candidate-status" in args:
                return IDENTITY
            if "doctor" in args:
                return doctor
            return None
        with mock.patch.object(MODULE, "document", side_effect=observed), \
             mock.patch.object(MODULE, "command", return_value=(False, "")), \
             mock.patch.object(MODULE, "stored_credential", return_value=True), \
             mock.patch.object(MODULE, "host_permissions", return_value=None):
            report = stages(MODULE.inspect("prepared"))
        self.assertEqual(report["guest-tools"]["state"], "human_required")
        self.assertEqual(report["administrator-authorization"]["nextActionId"],
                         "authorize_guest_tools_install_as_human")


if __name__ == "__main__":
    unittest.main()
