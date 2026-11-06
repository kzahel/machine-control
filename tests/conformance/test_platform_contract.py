import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import platform_contract as pc  # noqa: E402


def reply(accepted, code=None, data=None):
    return {"schema": "machine-control-admission-channel/v2", "requestId": "r1",
            "accepted": accepted, "errorCode": code, "data": data}


VIEW = {"schema": "machine-control-admission/v2", "revision": 3, "intentId": "i1",
        "state": "waiting_for_resource", "terminalReason": None, "offerGeneration": 0,
        "resourceGenerations": {"desktop": 2}, "blockingReasons": ["resource_unavailable"],
        "surfaces": ["desktop"], "profileIds": [], "requestSequencing": "strict"}


class ContractSchemaTests(unittest.TestCase):
    def test_all_contract_files_are_json(self):
        for path in pc.CONTRACTS.glob("*.schema.json"):
            json.loads(path.read_text())

    def test_status_requires_common_fields(self):
        good = {"desktopState": "locked", "deployment": {
            "policy": {"preset": "workstation", "grantMode": "surface_modes", "protectedAdministration": False},
            "availability": {"paused": False, "blockingReasons": []}, "browserOnlyWhileLocked": False},
            "lockedUse": {"supported": True, "enabled": True, "phase": "ready"}}
        self.assertTrue(pc.evaluate_status({"data": good})["pass"])
        for broken in ({**good, "desktopState": "asleep"},
                       {k: v for k, v in good.items() if k != "deployment"},
                       {**good, "lockedUse": {"supported": True, "enabled": True, "phase": "task_owned"}}):
            self.assertFalse(pc.evaluate_status({"data": broken})["pass"])


class RefusalEvaluationTests(unittest.TestCase):
    def test_conformant_refusal_closes(self):
        result = pc.evaluate_refusal("x", [reply(False, "invalid_admission_surfaces"), {"event": "closed"}],
                                     "invalid_admission_surfaces")
        self.assertTrue(result["pass"], result)

    def test_v0_envelope_wrong_code_or_open_channel_fail(self):
        v0 = {"schema": "machine-control/v0", "accepted": False, "errorCode": "invalid_admission_surfaces"}
        cases = [[v0, {"event": "closed"}],
                 [reply(False, "invalid_admission_request"), {"event": "closed"}],
                 [reply(False, "invalid_admission_surfaces")]]
        for replies in cases:
            self.assertFalse(pc.evaluate_refusal("x", replies, "invalid_admission_surfaces")["pass"], replies)


class SequenceEvaluationTests(unittest.TestCase):
    def test_gap_must_close_after_a_valid_open(self):
        closed = [reply(True, data=VIEW), reply(True, data=VIEW), {"event": "closed"}]
        self.assertTrue(pc.evaluate_sequence(closed)["pass"])
        still_open = [reply(True, data=VIEW), reply(True, data=VIEW),
                      reply(False, "invalid_request_sequence"), reply(True, data=VIEW)]
        self.assertFalse(pc.evaluate_sequence(still_open)["pass"])

    def test_renewal_is_optional_but_exact(self):
        self.assertTrue(pc.evaluate_sequence([reply(True, data={**VIEW, "renewal": "owner_connection/v1"}),
                                              {"event": "closed"}])["pass"])
        self.assertFalse(pc.evaluate_sequence([reply(True, data={**VIEW, "renewal": "yes"}),
                                               {"event": "closed"}])["pass"])

    def test_locked_windows_without_flag_is_conformant(self):
        self.assertTrue(pc.evaluate_sequence([reply(False, "prepared_console_required"),
                                              {"event": "closed"}])["pass"])


if __name__ == "__main__":
    unittest.main()
