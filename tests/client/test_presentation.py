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
        with patch.object(mc.host_platform, "system", return_value="Windows"), patch.object(mc.subprocess, "run") as run:
            with self.assertRaises(mc.ClientError):
                mc.run_local_presentation(["reset"], "host")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
