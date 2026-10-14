import json
import unittest

from measurements import transcript_metrics
from route_comparison import wait_for_agent
from unittest.mock import Mock


def event(kind, at, **values):
    return {"type": "event_msg", "timestamp": at,
            "payload": {"type": kind, "turn_id": "turn-1", **values}}


class MeasurementsTest(unittest.TestCase):
    def measure(self, items):
        return transcript_metrics("\n".join(json.dumps(x) for x in items))

    def test_timing_and_cumulative_tokens(self):
        result = self.measure([
            event("task_started", "2026-01-01T00:00:00Z"),
            event("token_count", "2026-01-01T00:00:01Z", info={"total_token_usage": {"input_tokens": 10}}),
            event("token_count", "2026-01-01T00:00:02Z", info={"total_token_usage": {"input_tokens": 20}}),
            event("task_complete", "2026-01-01T00:00:02.125Z"),
        ])
        self.assertEqual(result["agentSeconds"], 2.125)
        self.assertEqual(result["tokenUsage"]["input_tokens"], 20)

    def test_numeric_payload_times_use_precise_duration(self):
        result = self.measure([
            event("task_started", "2026-01-01T00:00:00Z", started_at=1767225600),
            event("task_complete", "2026-01-01T00:00:02Z", completed_at=1767225602,
                  duration_ms=1987),
        ])
        self.assertEqual(result["agentSeconds"], 1.987)

    def test_incomplete_turn_never_becomes_timed_success(self):
        result = self.measure([event("task_started", "2026-01-01T00:00:00Z")])
        self.assertFalse(result["transcriptComplete"])
        self.assertIsNone(result["agentSeconds"])

    def test_deduplicated_calls_and_unmatched_output(self):
        call = {"type": "response_item", "timestamp": "2026-01-01T00:00:00Z",
                "payload": {"type": "custom_tool_call", "call_id": "c1", "name": "js"}}
        output = {"type": "response_item", "timestamp": "2026-01-01T00:00:01Z",
                  "payload": {"type": "custom_tool_call_output", "call_id": "c1", "output": "é"}}
        result = self.measure([call, call, output])
        self.assertEqual(result["toolCalls"], 1)
        self.assertEqual(result["toolOutputBytes"], 2)
        self.assertEqual(result["toolRoundTripSeconds"], [1])
        self.assertIsNone(result["nativeOperations"])

    def test_malformed_and_reversed_timing(self):
        self.assertEqual(transcript_metrics('broken\n[]')["malformedTranscriptLines"], 2)
        result = self.measure([
            event("task_started", "2026-01-01T00:00:02Z"),
            event("task_complete", "2026-01-01T00:00:01Z"),
        ])
        self.assertIsNone(result["agentSeconds"])


class AgentWaitTest(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.guest = Mock()

    def sleep(self, seconds):
        self.now += seconds

    def wait(self, timeout=5):
        return wait_for_agent(self.guest, "session", timeout, 1,
                              clock=lambda: self.now, sleep=self.sleep)

    def test_missing_state_is_not_completion(self):
        self.guest.ya.side_effect = [{}, {"process":{"state":"running"}},
                                    {"process":{"state":"idle"}}]
        result = self.wait()
        self.assertEqual(result["controllerWaitSeconds"], 2)
        self.assertFalse(result["timedOut"])

    def test_timeout_stops_before_oracle(self):
        self.guest.ya.side_effect = [
            {"process":{"id":"p", "state":"running"}}, {},
            {"process":{"state":"terminated"}}]
        self.assertTrue(self.wait(timeout=1)["timedOut"])
        self.guest.ya.assert_any_call("POST", "/api/processes/p/abort", {"blockResume":True})

    def test_timeout_without_process_refuses(self):
        self.guest.ya.return_value = {}
        with self.assertRaisesRegex(RuntimeError, "skip racing oracle"):
            self.wait(timeout=1)

    def test_unconfirmed_cancellation_refuses(self):
        self.guest.ya.side_effect = [
            {"process":{"id":"p", "state":"running"}}, {},
            {"process":{"state":"running"}}]
        with self.assertRaisesRegex(RuntimeError, "cancellation not verified"):
            self.wait(timeout=1)


if __name__ == "__main__":
    unittest.main()
