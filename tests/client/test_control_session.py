import os
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "client"))
import machine_control as mc
from control_session import ControlSession, validate_view, complete_session_handoff, handle_control, SCHEMA


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

    def refusal(self):
        return dict(schema="machine-control/v0", requestId="fixture", operation="type", accepted=False,
            actualRoute="fixture", generation="fixture-generation", hostInterference="none", elapsedMs=0,
            errorCode="control_session_required", delivery="refused", effect="refused", uncertainty="none",
            retrySafety="safe_not_dispatched", data={"controlSession":{"schema":SCHEMA, "scope":"control"}})

    def test_handoff_dispatches_once_and_closes(self):
        target = dict(self.target, platform="windows")
        value, elapsed = complete_session_handoff(target, {"operation":"type", "text":"fixture"}, self.refusal())
        self.assertTrue(value["accepted"])
        self.assertGreaterEqual(elapsed, 0)
        events = self.record.read_text().splitlines()
        self.assertEqual(events.count("control.open"), 1)
        self.assertEqual(events.count("effect"), 1)
        self.assertIn("control.cancel", events)
        self.assertIn("EOF", events)

    def test_handoff_requires_explicit_undispatched_result(self):
        for change in [dict(accepted=True), dict(errorCode="approval_required"), dict(data={}),
                dict(delivery="confirmed"), dict(effect="unknown"), dict(uncertainty="unknown"),
                dict(retrySafety="not_applicable")]:
            refusal = dict(self.refusal(), **change)
            with patch("control_session.ControlSession") as session:
                self.assertEqual(complete_session_handoff(self.target, {}, refusal), (refusal, None))
                session.assert_not_called()
        refusal = self.refusal()
        refusal["data"]["controlSession"]["schema"] = "future"
        with patch("control_session.ControlSession") as session:
            with self.assertRaises(mc.ClientError): complete_session_handoff(self.target, {}, refusal)
            session.assert_not_called()

    def test_handoff_does_not_replay_uncertain_channel_result(self):
        target = dict(self.target, platform="windows", environment={**self.target["environment"], "MC_ADMISSION_FIXTURE":"uncertain"})
        value, _ = complete_session_handoff(target, {"operation":"type"}, self.refusal())
        self.assertFalse(value["accepted"])
        self.assertEqual(self.record.read_text().splitlines().count("effect"), 1)

    def test_desktop_entry_handoff_and_local_route_preservation(self):
        target = dict(self.target, platform="windows", profile="workstation")
        for local in (False, True):
            refusal = self.refusal()
            completed = subprocess.CompletedProcess([], 1, stdout=json.dumps(refusal))
            with patch.object(mc, "run_adapter", return_value=(completed, refusal, 1)), redirect_stdout(io.StringIO()) as out:
                code = mc.handle_desktop("fixture", target, ["call-local" if local else "call", '{"operation":"input.text","text":"fixture"}'])
            self.assertEqual(code, 1 if local else 0)
            self.assertEqual(json.loads(out.getvalue())["accepted"], not local)
        self.assertEqual(self.record.read_text().splitlines().count("effect"), 1)

    def test_resident_entry_handoff_failure_does_not_fall_back(self):
        target = dict(self.target, platform="windows", profile="workstation",
            environment={**self.target["environment"], "MC_ADMISSION_FIXTURE":"malformed"})
        refusal = self.refusal()
        completed = subprocess.CompletedProcess([], 1, stdout=json.dumps(refusal))
        with patch.object(mc, "run_adapter", return_value=(completed, refusal, 1)) as adapter:
            with self.assertRaises(mc.ClientError) as error:
                mc.send_resident_request("fixture", target, {"operation":"type"})
        self.assertEqual(error.exception.code, "admission_unsupported")
        adapter.assert_called_once()
        self.assertNotIn("effect", self.record.read_text())

    def stream(self, text, mode="ready"):
        target = dict(self.target, platform="windows", environment={**self.target["environment"], "MC_ADMISSION_FIXTURE":mode})
        with patch("control_session.sys.stdin", io.TextIOWrapper(io.BytesIO(text))), redirect_stdout(io.StringIO()) as out:
            result = handle_control("fixture", target, ["stream", "--reason", "fixture"])
        return result, [json.loads(line) for line in out.getvalue().splitlines()]

    def test_stream_reuses_owner_and_stops_on_uncertainty(self):
        requests = b'{"operation":"snapshot"}\n{"operation":"input.text","text":"fixture"}\n'
        code, results = self.stream(requests)
        self.assertEqual(code, 0)
        self.assertEqual([row["operation"] for row in results], ["snapshot", "type"])
        events = self.record.read_text().splitlines()
        self.assertEqual(events.count("control.open"), 1)
        self.assertEqual(events.count("effect"), 2)
        self.assertIn("control.cancel", events)
        for mode in ("uncertain", "uncertain-accepted"):
            self.record.unlink()
            code, results = self.stream(requests, mode)
            self.assertEqual(code, 1)
            self.assertEqual(len(results), 1)
            self.assertEqual(self.record.read_text().splitlines().count("effect"), 1)

    @unittest.skipIf(os.name == "nt", "POSIX pipe readiness fixture")
    def test_stream_replies_before_stdin_eof(self):
        import select
        script = """import sys,json
sys.path.insert(0,sys.argv[1])
from control_session import handle_control
sys.exit(handle_control('fixture',json.loads(sys.argv[2]),['stream','--reason','fixture']))
"""
        with subprocess.Popen([sys.executable, "-c", script, str(Path(mc.__file__).parent),
                json.dumps(dict(self.target, platform="windows"))], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as child:
            try:
                for _ in range(2):
                    child.stdin.write('{"operation":"snapshot"}\n'); child.stdin.flush()
                    self.assertTrue(select.select([child.stdout], [], [], 5)[0], "Reply must not wait for EOF")
                    self.assertTrue(json.loads(child.stdout.readline())["accepted"])
                child.stdin.close()
                self.assertEqual(child.wait(timeout=5), 0)
            finally:
                if child.poll() is None: child.kill(); child.wait()
        events = self.record.read_text().splitlines()
        self.assertEqual(events.count("control.open"), 1)
        self.assertEqual(events.count("effect"), 2)
        self.assertIn("EOF", events)

    def test_stream_empty_and_malformed_input_cleanup(self):
        self.assertEqual(self.stream(b""), (0, []))
        self.assertFalse(self.record.exists())
        for text in [b"invalid\n", b"x" * 65537, b'{"operation":"snapshot"}\ninvalid\n']:
            with self.assertRaises(mc.ClientError): self.stream(text)
        events = self.record.read_text().splitlines()
        self.assertEqual(events.count("effect"), 1)
        self.assertIn("control.cancel", events)
        self.assertIn("EOF", events)

    def test_confirmed_delivery_keeps_owner_for_independent_observation(self):
        code, results = self.stream(b'{"operation":"input.text","text":"fixture"}\n{"operation":"snapshot"}\n', "unverified")
        self.assertEqual(code, 0)
        self.assertEqual([row["operation"] for row in results], ["type", "snapshot"])
        self.assertEqual(results[0]["effect"], "unverifiable")
        self.assertNotEqual(results[0]["uncertainty"], "none")
        events = self.record.read_text().splitlines()
        self.assertEqual(events.count("control.open"), 1)
        self.assertEqual(events.count("control.dispatch"), 2)
        self.assertIn("control.cancel", events)

    def test_prepared_console_is_explicit_and_uses_the_same_bounded_owner_lifecycle(self):
        with self.session("prepared-required", prepared_console=True) as session:
            session.wait()
            self.assertTrue(session.call({"operation":"snapshot"})["accepted"])
        events = self.record.read_text().splitlines()
        self.assertEqual(events.count("prepared-console"),1)
        self.assertIn("control.cancel",events)
        self.assertIn("EOF",events)
        with patch.object(subprocess,"Popen") as spawn:
            with self.assertRaises(mc.ClientError):self.session(prepared_console="true")
            with self.assertRaises(mc.ClientError):self.session(prepared_console=True, scopes=("browser",))
            spawn.assert_not_called()

    def test_effect_once_live_keepalive_and_prompt_cancel_cleanup(self):
        with self.session() as session:
            session.wait()
            self.assertTrue(session.call({"operation":"snapshot"})["accepted"])
            deadline = time.monotonic() + 10
            while "control.heartbeat" not in self.record.read_text() and time.monotonic() < deadline:
                time.sleep(0.02)
            process = session.process
        events = self.record.read_text().splitlines()
        self.assertEqual(events.count("effect"), 1)
        self.assertIn("control.heartbeat", events)
        self.assertIn("control.cancel", events)
        self.assertIn("EOF", events)
        self.assertIsNotNone(process.poll())

    def test_negotiated_ordered_wait_exceeds_legacy_budget(self):
        with self.session("sequenced", wait=14400) as session:
            self.assertTrue(session.sequenced)
            for _ in range(4200):
                self.assertEqual(session.status()["state"], "offered")
            session.wait()
            self.assertTrue(session.call({"operation":"snapshot"})["accepted"])
        self.assertEqual(self.record.read_text().splitlines().count("effect"), 1)

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

    def test_interruption_reports_state_as_data_and_keeps_numeric_exit_code(self):
        with self.session("paused") as session:
            with self.assertRaises(mc.ClientError) as error:
                session.call({"operation":"snapshot"})
            self.assertEqual(error.exception.code, "control_interrupted")
            self.assertEqual(error.exception.data["state"], "paused")
            self.assertIsInstance(error.exception.exit_code, int)
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
