"""Client guidance and doctor projection for Only verified callers (Tactical 161)."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
import agent_interface  # noqa: E402
import machine_control  # noqa: E402

spec = importlib.util.spec_from_file_location("caller_machost", ROOT / "platforms/macos/host/machost.py")
machost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(machost)


class CallerVerificationGuidanceTests(unittest.TestCase):
    def test_instructions_explain_refusal_and_operator_approval(self):
        text = " ".join(agent_interface.instructions().split())
        self.assertIn("caller_not_verified", text)
        self.assertIn("data.callerHost", text)
        self.assertIn("approvable is true, ask the operator to approve that app", text)
        self.assertIn("never replayed", text)
        self.assertIn("launchd jobs", text)
        self.assertIn("Do not work around the refusal", text)

    def test_help_names_the_status_projection_offline(self):
        status = machine_control.command_help(["desktop", "status", "--help"])
        self.assertIn("data.callerVerification", status)
        self.assertIn("caller_not_verified", status)
        self.assertIn("caller_not_verified", machine_control.usage())


class CallerVerificationDoctorTests(unittest.TestCase):
    def doctor(self, verification):
        response = {"accepted": True, "data": {
            "desktopState": "unlocked", "semanticState": "ready", "captureState": "ready", "inputState": "ready",
            "callerVerification": verification,
        }}
        output = io.StringIO()
        with patch.object(machost, "call", return_value=response), contextlib.redirect_stdout(output):
            machost.doctor()
        return json.loads(output.getvalue())

    def test_doctor_projects_mode_without_requirements(self):
        value = self.doctor({"schema": "machine-control-caller-verification/v1", "mode": "verified_only",
                             "supported": True, "approvedHosts": [{"name": "Agent", "publisher": "Example Inc",
                                                                   "teamId": "SHOULDNOTLEAK"}],
                             "limits": ["same_user_not_contained"], "discoveryOperations": ["status"]})
        projection = value["extensions"]["callerVerification"]
        self.assertEqual(projection["mode"], "verified_only")
        self.assertEqual(projection["limits"], ["same_user_not_contained"])
        self.assertNotIn("discoveryOperations", projection)
        self.assertEqual(projection["approvedHosts"], [{"name": "Agent", "publisher": "Example Inc"}])
        self.assertIn("caller_verification", [check["id"] for check in value["checks"]])

    def test_doctor_is_unchanged_when_off(self):
        value = self.doctor({"mode": "off", "supported": False, "unsupportedReason": "development_signature",
                             "approvedHosts": [], "limits": ["same_user_not_contained"]})
        self.assertEqual(value["extensions"]["callerVerification"]["mode"], "off")
        self.assertNotIn("caller_verification", [check["id"] for check in value["checks"]])


if __name__ == "__main__":
    unittest.main()
