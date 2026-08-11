from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "guests"
    / "ubuntu"
    / "bootstrap"
    / "post_update.py"
)
SPEC = importlib.util.spec_from_file_location("linux_post_update", SOURCE)
assert SPEC and SPEC.loader
POST_UPDATE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = POST_UPDATE
SPEC.loader.exec_module(POST_UPDATE)


class PostUpdateTests(unittest.TestCase):
    def run_main(self, mode: str, state: dict[str, bool]) -> tuple[int, dict]:
        output = io.StringIO()
        repairs = {key: "not_needed" for key in state}
        with (
            mock.patch.object(POST_UPDATE.os, "geteuid", return_value=0),
            mock.patch.object(POST_UPDATE, "collect_state", return_value=state),
            mock.patch.object(POST_UPDATE, "repair_state", return_value=repairs),
            redirect_stdout(output),
        ):
            status = POST_UPDATE.main(
                [
                    "--mode",
                    mode,
                    "--profile",
                    "development",
                    "--nonce",
                    "abcdefghijklmnopqrstuvwx",
                ],
                runner=mock.Mock(),
            )
        return status, json.loads(output.getvalue())

    def test_audit_is_minimized_and_healthy(self) -> None:
        state = {
            "package_manager": True,
            "pending_reboot": True,
            "profile_packages": True,
            "guest_agent": True,
            "spice_system": True,
            "desktop_session": True,
            "spice_session": True,
            "input_broker": True,
            "resident_service": True,
            "target_native": True,
        }
        status, report = self.run_main("audit", state)
        self.assertEqual(status, 0)
        self.assertTrue(report["healthy"])
        self.assertEqual(report["schema"], POST_UPDATE.SCHEMA)
        self.assertNotIn("user", report)
        self.assertNotIn("boot_id", report)
        self.assertTrue(
            all(check["repair"] == "not_requested" for check in report["checks"])
        )

    def test_failure_and_repair_dispositions_remain_typed(self) -> None:
        state = {
            "package_manager": False,
            "pending_reboot": True,
            "profile_packages": True,
            "guest_agent": True,
            "spice_system": True,
            "desktop_session": True,
            "spice_session": True,
            "input_broker": True,
            "resident_service": True,
            "target_native": True,
        }
        status, report = self.run_main("repair", state)
        self.assertEqual(status, 1)
        self.assertFalse(report["healthy"])
        failed = next(
            check for check in report["checks"] if check["id"] == "package_manager"
        )
        self.assertEqual(failed["status"], "fail")
        self.assertEqual(failed["observed"], "inconsistent")
        self.assertEqual(failed["repair"], "not_needed")


if __name__ == "__main__":
    unittest.main()
