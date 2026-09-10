import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "client"))
import machine_control as mc


class UnlockStatusTests(unittest.TestCase):
    def ready(self):
        return dict(support="experimental", installation="healthy",
                    policy="enabled", callerEligibility="allowed",
                    readiness="ready", reasons=[])

    def test_ready_requires_all_prerequisites(self):
        mc.validate_unlock_status(self.ready())
        for key, bad in [("support", "unsupported"), ("installation", "missing"),
                         ("policy", "disabled"), ("callerEligibility", "unknown"),
                         ("callerEligibility", "denied"), ("reasons", ["blocked"])]:
            with self.subTest(key=key, bad=bad), self.assertRaises(mc.ClientError):
                mc.validate_unlock_status(dict(self.ready(), **{key: bad}))

    def test_absent_authority_is_not_needed_only_when_already_unlocked(self):
        mc.validate_unlock_status(dict(self.ready(), installation="missing",
            callerEligibility="unknown", policy="unknown", readiness="not_needed",
            reasons=["unlock_not_installed"]))

    def test_malformed_values_are_typed_refusals(self):
        for value in [None, [], {}, dict(self.ready(), reasons="ready"),
                      dict(self.ready(), installation=[]),
                      dict(self.ready(), helperGeneration="")]:
            with self.subTest(value=value), self.assertRaises(mc.ClientError):
                mc.validate_unlock_status(value)

    def test_lock_screen_permission_does_not_claim_credential_input(self):
        value = dict(captureState="ready", accessibilityState="unverified",
            nativeKeyboardPermission="granted", ordinaryInputPolicy="blocked_while_locked",
            credentialEntry="not_implemented", observationRequiresUnlockHelper=False)
        mc.validate_lock_screen_status(value)
        for key, bad in [("accessibilityState", "ready"), ("credentialEntry", "ready"),
                         ("nativeKeyboardPermission", True), ("observationRequiresUnlockHelper", True)]:
            with self.subTest(key=key), self.assertRaises(mc.ClientError):
                mc.validate_lock_screen_status(dict(value, **{key: bad}))

    def test_arming_mode_is_not_an_armed_state(self):
        mc.validate_unlock_status(dict(self.ready(), armingMode="per_request", grantLifetimeSeconds=10))
        for fields in [dict(armingMode="always"), dict(grantLifetimeSeconds=60), dict(grantLifetimeSeconds=True)]:
            with self.subTest(fields=fields), self.assertRaises(mc.ClientError):
                mc.validate_unlock_status(dict(self.ready(), **fields))

    def test_unlock_command_requires_observation_and_request_identity(self):
        request, local = mc.desktop_request(["session", "unlock",
            "--expected-desktop-generation", "desktop-epoch",
            "--expected-helper-generation", "helper-epoch", "--request-id", "attempt"])
        self.assertFalse(local)
        self.assertEqual(request, {"operation": "session.unlock",
            "expectedDesktopGeneration": "desktop-epoch",
            "expectedHelperGeneration": "helper-epoch", "requestId": "attempt"})
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(mc.ClientError):
            mc.desktop_request(["session", "unlock"])


if __name__ == "__main__":
    unittest.main()
