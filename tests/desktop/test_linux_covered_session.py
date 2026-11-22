"""Cover ownership and relock fencing independent of the graphical VM."""

from pathlib import Path
import sys
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / path) for path in (
    "desktop/native/linux", "platforms/linux/guests/ubuntu/ui",
)]

from covered_session import CoveredSession
from gnome_unlock import Console, Observation, UnlockRefused


class Native:
    def __init__(self):
        self.console = Console("/session", "c1", 1, ":1.1")
        self.locked = True

    def observe(self):
        return Observation(self.console, self.locked, not self.locked)


class Cover:
    def __init__(self, provider, _console, permitted):
        self.native = provider
        self.permitted = permitted
        self.begin_attempted = False

    def open(self, _seconds):
        self.begin_attempted = True

    def opaque_frame(self):
        return self.covered()

    def covered(self):
        return self.begin_attempted and self.permitted()

    def close(self):
        self.native.locked = True

    def status(self):
        return "inactive", "owner_ended"


class CoveredSessionTests(unittest.TestCase):
    def start(self, authenticate, lifetime=3, cover=Cover):
        native = Native()
        alive = threading.Event()
        alive.set()
        task = CoveredSession(("c1", 1, ":1.1"), alive.is_set, authenticate, lambda: None,
                              time.monotonic() + lifetime, native=lambda: native, cover=cover)
        task.start()
        self.addCleanup(task.stop)
        return task, alive, native

    def test_hard_deadline_ends_active_task_even_with_a_fresh_pulse(self):
        class Broker:
            def __init__(self, native):
                self.native = native
                self.unlocked = False

            def keep(self):
                pass

            def next(self, _deadline):
                if not self.unlocked:
                    self.native.locked = False
                    self.unlocked = True
                    return {"event": "unlocked"}
                time.sleep(.02)
                return {"event": "ended"} if self.native.locked else None

            def end(self):
                pass

            close = end

        task, _, native = self.start(lambda _console, cover, _seconds: Broker(cover.native))
        self.assertTrue(task.active.wait(1))
        self.assertFalse(native.locked)
        task.until = time.monotonic() + .4
        task.pulse()
        self.assertTrue(task.finished.wait(2))
        self.assertTrue(task.relock_verified and native.locked)
        with self.assertRaises(UnlockRefused):
            task.require_active()

    def test_stop_during_authentication_never_admits_a_late_result(self):
        authenticating = threading.Event()
        respond = threading.Event()

        def authenticate(_session, cover, _seconds):
            authenticating.set()
            respond.wait(1)
            cover.native.locked = False
            return None

        task, _, native = self.start(authenticate)
        self.assertTrue(authenticating.wait(1))
        task.stop()
        respond.set()
        self.assertTrue(task.finished.wait(2))
        self.assertFalse(task.unlocked)
        self.assertTrue(task.relock_verified and native.locked)

    def test_preflight_failure_does_not_get_stuck_waiting_for_a_missing_cover(self):
        class Unavailable(Cover):
            def open(self, _seconds):
                raise UnlockRefused("gnome_cover_unavailable")

            def status(self):
                raise AssertionError("There was no attempt to create a cover")

        task, _, native = self.start(lambda *_: self.fail("Unexpected authentication"), cover=Unavailable)
        self.assertTrue(task.finished.wait(1))
        self.assertEqual(task.reason, "gnome_cover_unavailable")
        self.assertTrue(task.relock_verified and native.locked)


if __name__ == "__main__":
    unittest.main()
