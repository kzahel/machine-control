"""Real stalled threads prove physical capacity and cancellation fences."""
import queue
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop/native/linux"))
from work import Work, Ticket, Cancelled
from grants import Grants


class WorkTests(unittest.TestCase):
    def test_late_worker_holds_slot_and_cannot_dispatch_after_new_authority(self):
        callbacks = queue.Queue()
        work = Work(callbacks.put)
        release = threading.Event()
        started = threading.Event()
        effects = []
        replies = []
        old = Ticket("old")

        def run(ticket):
            started.set()
            release.wait(2)
            ticket.effect()
            effects.append("effect")
        self.assertTrue(work.submit(old, run, lambda value, error: replies.append(error)))
        self.assertTrue(started.wait(1))
        work.cancel()
        self.assertFalse(work.submit(Ticket("new"), run, lambda *_: None))
        release.set()
        callbacks.get(timeout=2)()
        self.assertEqual(effects, [])
        self.assertIsInstance(replies[0], Cancelled)
        self.assertIsNone(work.active)

    def test_deadline_expiry_and_effect_uncertainty(self):
        ticket = Ticket("old", timeout=.01)
        ticket.effect()
        ticket.cancelled.set()
        with self.assertRaises(Cancelled):
            ticket.effect()
        self.assertTrue(ticket.dispatched)
        deadline = Ticket("old", timeout=0)
        with self.assertRaises(Cancelled):
            deadline.check()
        expired = Ticket("old", expires=time.monotonic() - 1)
        with self.assertRaises(Cancelled):
            expired.effect()
        self.assertFalse(expired.dispatched)

    def test_provider_thread_and_dependency_callbacks_have_one_owner(self):
        callbacks = queue.Queue()
        setup = []
        runs = []
        work = Work(callbacks.put, setup=lambda: setup.append(threading.get_ident()))
        for generation in ["first", "second", "third"]:
            self.assertTrue(work.submit(Ticket(generation),
                                        lambda _: runs.append(threading.get_ident()), lambda *_: None))
            callbacks.get(timeout=2)()
        self.assertEqual(len(setup), 1)
        self.assertEqual(set(runs), set(setup))

    def test_pause_rotates_authority_and_update_stays_excluded(self):
        grants = Grants()
        grants.set_ready(True)
        grants.arm(["observe", "control"], 60)
        old = grants.generation
        grants.pause(True)
        self.assertEqual(grants.authorize("snapshot", old), "stale_generation")
        self.assertEqual(grants.authorize("snapshot"), "access_paused")
        with self.assertRaises(ValueError):
            grants.prepare_update()
        grants.pause(False)
        self.assertIsNone(grants.authorize("snapshot"))
        grants.stop()
        grants.prepare_update()
        self.assertEqual(grants.authorize("snapshot"), "update_in_progress")


if __name__ == "__main__":
    unittest.main()
