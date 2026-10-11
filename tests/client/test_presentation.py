"""Local presentation controls cannot accidentally mutate a remote target."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "client"))
import machine_control as mc


class PresentationTests(unittest.TestCase):
    def test_remote_target_and_other_platforms_refuse_before_dispatch(self):
        with patch.object(mc.host_platform, "system", return_value="Darwin"), patch.object(mc.subprocess, "run") as run:
            with self.assertRaises(mc.ClientError):
                mc.run_local_presentation(["set", "appliance"], "remote-example")
            run.assert_not_called()
        with patch.object(mc.host_platform, "system", return_value="Linux"), patch.object(mc.subprocess, "run") as run:
            with self.assertRaises(mc.ClientError):
                mc.run_local_presentation(["reset"], "host")
            run.assert_not_called()

    def test_linux_routes_local_configuration_and_refuses_remote(self):
        with patch.object(mc.host_platform, "system", return_value="Linux"), patch.object(mc.Path, "is_file", return_value=True), patch.object(mc.os, "access", return_value=True), patch.object(mc.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(mc.run_local_presentation(["status", "--instance", "example"], "host"), 0)
            self.assertEqual(run.call_args.args[0][1:], ["presentation", "status", "--instance", "example"])
            run.reset_mock()
            with self.assertRaises(mc.ClientError):
                mc.run_local_presentation(["set", "appliance"], "remote-example")
            run.assert_not_called()

    def test_windows_routes_only_local_operator_configuration(self):
        with patch.object(mc.host_platform, "system", return_value="Windows"), patch.object(mc.Path, "is_file", return_value=True), patch.object(mc.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(mc.run_local_presentation(["status", "--instance", "example"], "host"), 0)
            self.assertEqual(run.call_args.args[0][1:], ["presentation", "status", "--instance", "example"])
            run.reset_mock()
            with self.assertRaises(mc.ClientError):
                mc.run_local_presentation(["set", "appliance"], "remote-example")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
