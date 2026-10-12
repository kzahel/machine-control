import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop/native/linux"))
from one_shot import read_reply


@unittest.skipUnless(os.name == "posix", "Native reply reader requires POSIX pipe polling")
class OneShotTests(unittest.TestCase):
    def test_silent_native_child_expires_and_is_reaped(self):
        with subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], stdout=subprocess.PIPE) as child:
            started = time.monotonic()
            self.assertEqual(read_reply(child, threading.Event(), started + .1), b"")
            self.assertIsNotNone(child.poll())
            self.assertLess(time.monotonic() - started, 2)

    @unittest.skipUnless(sys.platform == "linux", "Linux native child fault")
    def test_stopped_native_child_cancellation_uses_kernel_kill(self):
        with subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('ready',flush=True); time.sleep(30)"], stdout=subprocess.PIPE) as child:
            self.assertEqual(child.stdout.readline(), b"ready\n")
            os.kill(child.pid, signal.SIGSTOP)
            _, status = os.waitpid(child.pid, os.WUNTRACED)
            self.assertTrue(os.WIFSTOPPED(status))
            cancelled = threading.Event()
            cancelled.set()
            self.assertEqual(read_reply(child, cancelled, time.monotonic() + 30), b"")
            self.assertEqual(child.returncode, -signal.SIGKILL)

    def test_partial_reply_cannot_hold_ui_capacity(self):
        with subprocess.Popen([sys.executable, "-c", "import sys,time; sys.stdout.write('{'); sys.stdout.flush(); time.sleep(30)"], stdout=subprocess.PIPE) as child:
            self.assertEqual(read_reply(child, threading.Event(), time.monotonic() + .1), b"")
            self.assertIsNotNone(child.poll())


if __name__ == "__main__":
    unittest.main()
