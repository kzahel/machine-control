import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "client"))
import machine_control as mc
from control_session import ControlSession, validate_view


class ControlSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.record = Path(self.temporary.name) / "events"
        self.fixture = Path(__file__).with_name("admission_fixture.py")
        self.target = dict(command=[sys.executable, str(self.fixture)],
            environment={"MC_ADMISSION_RECORD":str(self.record)})

    def tearDown(self):
        self.temporary.cleanup()

    def session(self, mode="ready", **options):
        target = dict(self.target, environment={**self.target["environment"], "MC_ADMISSION_FIXTURE":mode})
        return ControlSession(target, reason="fixture", **options)

    def test_effect_once_live_keepalive_and_prompt_cancel_cleanup(self):
        with self.session() as session:
            session.wait()
            self.assertTrue(session.call({"operation":"snapshot"})["accepted"])
            time.sleep(1.1)
            process = session.process
        events = self.record.read_text().splitlines()
        self.assertEqual(events.count("effect"), 1)
        self.assertIn("control.heartbeat", events)
        self.assertIn("control.cancel", events)
        self.assertIn("EOF", events)
        self.assertIsNotNone(process.poll())

    def test_uncertain_effect_is_returned_without_replay(self):
        with self.session("uncertain") as session:
            session.wait()
            result = session.call({"operation":"input.text", "text":"fixture"})
            self.assertFalse(result["accepted"])
            self.assertEqual(result["uncertainty"], "interrupted_after_possible_dispatch")
        self.assertEqual(self.record.read_text().count("effect\n"), 1)

    def test_wait_deadline_and_pause_never_dispatch(self):
        with self.session("paused", wait=1) as session:
            with self.assertRaises(mc.ClientError) as error:
                session.wait()
            self.assertEqual(error.exception.code, "wait_deadline_exceeded")
        self.assertNotIn("effect", self.record.read_text())

    def test_bad_negotiation_reaps_transport(self):
        with self.assertRaises(mc.ClientError) as error:
            self.session("malformed")
        self.assertEqual(error.exception.code, "admission_unsupported")
        self.assertIn("EOF", self.record.read_text())

    def test_expired_target_claim_prevents_an_effect(self):
        with self.session() as session:
            session.wait()
            with patch.object(mc, "require_selected_claim", side_effect=mc.ClientError("claim_expired", "fixture")):
                with self.assertRaises(mc.ClientError) as error:
                    session.call({"operation":"snapshot"})
                self.assertEqual(error.exception.code, "claim_expired")
        self.assertNotIn("effect", self.record.read_text())

    def test_generation_type_and_duration_are_strict(self):
        with self.session() as session:
            view = dict(session.view, resourceGenerations={"desktop":True})
            with self.assertRaises(mc.ClientError):
                validate_view(view)
        for options in [dict(wait=True), dict(duration=901), dict(scopes=["control", "control"])]:
            with self.assertRaises(mc.ClientError):
                self.session(**options)

    @unittest.skipIf(os.name == "nt", "POSIX process-death fixture")
    def test_parent_death_closes_adapter_without_a_new_action(self):
        script = """import sys,time
sys.path.insert(0, sys.argv[1])
from control_session import ControlSession
session=ControlSession({'command':[sys.executable,sys.argv[2]],'environment':{'MC_ADMISSION_RECORD':sys.argv[3]}},reason='fixture')
session.wait()
print('ready',flush=True)
time.sleep(30)
"""
        owner = subprocess.Popen([sys.executable, "-c", script, str(Path(mc.__file__).parent),
            str(self.fixture), str(self.record)], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(owner.stdout.readline().strip(), "ready")
            owner.kill(); owner.wait(timeout=3)
            deadline = time.monotonic() + 3
            while "EOF" not in self.record.read_text() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertIn("EOF", self.record.read_text())
            self.assertNotIn("effect", self.record.read_text())
        finally:
            if owner.poll() is None:
                owner.kill(); owner.wait()
            owner.stdout.close()


if __name__ == "__main__":
    unittest.main()
