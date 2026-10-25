"""Relay deadlines cancel abandoned work and cannot accept a late success."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop/native/linux"))
from browser import Browser


class BrowserDeadlineTests(unittest.TestCase):
    def test_forwarded_deadline_cancel_and_late_reply(self):
        timers, frames, replies = [], [], []
        owner = SimpleNamespace(
            grants=SimpleNamespace(generation="grant", authorize=lambda *_: None),
            scheduler=SimpleNamespace(timer=lambda delay, callback: timers.append((delay, callback))),
            provider=SimpleNamespace(fail=lambda request, operation, code, message: {"accepted": False, "errorCode": code}))
        relay = Browser(owner)
        relay.provider = object()
        relay.sync = lambda: None
        relay.send = frames.append
        relay.execute({"operation": "browser.eval", "timeoutMs": 1000}, replies.append)
        self.assertEqual(timers[0][0], 1000)
        self.assertEqual(frames[0]["timeoutMs"], 500)
        identifier = frames[0]["id"]
        relay.pending[identifier]["dispatched"] = True
        self.assertFalse(timers[0][1]())
        self.assertEqual(frames[-1], {"type": "cancel", "id": identifier})
        self.assertEqual(replies[0]["errorCode"], "browser_timeout")
        self.assertEqual(replies[0]["delivery"], "unknown")
        relay.complete(identifier, {"ok": True, "data": {"late": True}})
        self.assertEqual(len(replies), 1)
        self.assertEqual(relay.pending, {})

    def test_invalid_deadline_does_not_enqueue(self):
        for timeout in [True, "1000", None, 0, -1]:
            replies = []
            relay = Browser(SimpleNamespace(provider=SimpleNamespace(fail=lambda request, operation, code, message: {"errorCode": code})))
            relay.execute({"operation": "browser.tabs", "timeoutMs": timeout}, replies.append)
            self.assertEqual(replies, [{"errorCode": "invalid_request"}])
            self.assertEqual(relay.pending, {})


if __name__ == "__main__":
    unittest.main()
