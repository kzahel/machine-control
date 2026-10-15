"""Offline contract tests; never contact a deployment or start a YA session."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SPEC = importlib.util.spec_from_file_location(
    "ya_sessions", Path(__file__).resolve().parents[2] / "scripts/ya-sessions.py")
ya = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ya)


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, route, body=None, missing=False):
        self.calls.append((method, route, body, missing))
        return next(self.responses)


def receipt():
    return {"projectId": ya.project_id("/workspace/project"), "processId": "process-a",
            "sessionId": "provisional", "requested": {
                "provider": "codex", "model": ya.MODEL, "thinking": "low", "serviceTier": "default"}}


def process(**changes):
    row = {"id": "process-a", "sessionId": "canonical", "projectId": receipt()["projectId"],
           "provider": "codex", "state": "idle", "requestedModel": ya.MODEL,
           "model": ya.MODEL, "effort": "low", "queueDepth": 0,
           "sessionTitle": "SECRET", "unrelated": "SECRET"}
    return {**row, **changes}


def metadata(effort="low"):
    return {"session": {"initialPrompt": "SECRET", "effectiveLaunchSettings": {
        "revision": 2, "requestedModel": ya.MODEL, "effort": effort, "serviceTier": None,
        "permissionMode": "SECRET"}}}


class SessionsTests(unittest.TestCase):
    def test_mutation_supplies_ya_csrf_header(self):
        client = ya.Client("https://example.invalid")
        response = io.BytesIO(b'{"ok":true}')
        with patch.object(client.opener, "open", return_value=response) as opened:
            self.assertEqual(client.request("POST", "/processes/owned/abort", {}), {"ok": True})
        request = opened.call_args.args[0]
        self.assertEqual(request.get_header("X-yep-anywhere"), "true")

    def test_project_id_is_target_verbatim_unicode(self):
        import base64
        path = "C:\\work\\測試"
        encoded = ya.project_id(path)
        self.assertEqual(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode(), path)
        with self.assertRaises(ya.Error):
            ya.project_id("relative")

    def test_remap_by_stable_process_and_allowlist(self):
        client = FakeClient([{"process": None}, {"processes": [process(), process(id="other")],
                                                   "terminatedProcesses": []}, metadata()])
        result = ya.status(client, receipt())
        self.assertEqual(result["sessionId"], "canonical")
        self.assertEqual(result["previousSessionIds"], ["provisional"])
        self.assertTrue(result["observation"]["selectionMatchesRequest"])
        self.assertTrue(result["observation"]["appliedMatchesRequest"])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_selected_effort_is_not_applied_effort(self):
        result = ya.status(FakeClient([{"process": process()}, metadata("high")]), receipt())
        self.assertTrue(result["observation"]["selectionMatchesRequest"])
        self.assertFalse(result["observation"]["appliedMatchesRequest"])

    def test_absent_applied_snapshot_is_unverified(self):
        result = ya.status(FakeClient([{"process": process()}, {"session": {}}]), receipt())
        self.assertFalse(result["observation"]["appliedMatchesRequest"])

    def test_wrong_project_or_provider_refused(self):
        for row in (process(projectId="other"), process(provider="other")):
            with self.subTest(row=row), self.assertRaises(ya.Error):
                ya.status(FakeClient([{"process": row}]), receipt())

    def test_queue_departure_does_not_guess_session(self):
        item = {"projectId": receipt()["projectId"], "queueId": "queue-a"}
        result = ya.status(FakeClient([None]), item)
        self.assertEqual(result["outcome"], "queue-departed-unresolved")
        self.assertNotIn("sessionId", result)

    def test_queue_position(self):
        result = ya.status(FakeClient([{"position": 3}]), {"queueId": "queue-a"})
        self.assertEqual((result["outcome"], result["position"]), ("queued", 3))

    def test_fast_uses_advertised_tier_and_normal_default(self):
        catalog = {"provider": {"models": [{"id": ya.MODEL,
                   "supportedReasoningEfforts": [{"reasoningEffort": "low"}],
                   "serviceTiers": [{"id": "priority", "name": "Fast"}]}]}}
        self.assertEqual(ya.settings(FakeClient([catalog]), "low", "fast")["serviceTier"], "priority")
        self.assertEqual(ya.settings(FakeClient([catalog]), "low", "normal")["serviceTier"], "default")
        for effort, speed in (("high", "normal"), ("low", "fast")):
            absent = {"provider": {"models": [{"id": ya.MODEL,
                      "supportedReasoningEfforts": [{"reasoningEffort": "low"}]}]}}
            with self.subTest(effort=effort, speed=speed), self.assertRaises(ya.Error):
                ya.settings(FakeClient([absent]), effort, speed)

    def test_receipt_private_atomic_and_duplicate_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            ya.save(path, {"value": 1}, exclusive=True)
            with self.assertRaises(FileExistsError):
                ya.save(path, {"value": 2}, exclusive=True)
            ya.save(path, {"value": 3})
            self.assertEqual(ya.private_json(path), {"value": 3})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            path.chmod(0o644)
            with self.assertRaises(ya.Error):
                ya.private_json(path)

    def test_private_file_symlink_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            ya.save(path, {}, exclusive=True)
            alias = Path(directory) / "alias"
            alias.symlink_to(path)
            with self.assertRaises((OSError, ya.Error)):
                ya.private_json(alias)

    def test_auth_headers_and_url_constraints(self):
        for url in ("http://user:SECRET@example.invalid", "http://example.invalid/?token=SECRET",
                    "file:///tmp/value", "http://example.invalid/#SECRET"):
            with self.subTest(url=url), self.assertRaises(ya.Error):
                ya.Client(url)
        for headers in ({"X-Other": "SECRET"}, {"Cookie": "SECRET\nX: y"}):
            with self.assertRaises(ya.Error):
                ya.Client("https://example.invalid", headers)

    def test_redirect_not_followed_with_credentials(self):
        self.assertIsNone(ya.NoRedirect().redirect_request(None, None, 307, "", {},
                                                        "https://other.invalid"))

    def test_http_and_transport_errors_do_not_echo_secrets(self):
        client = ya.Client("https://example.invalid", {"Cookie": "SECRET"})
        errors = [urllib.error.HTTPError("SECRET", 403, "SECRET", {}, io.BytesIO(b"SECRET")),
                  urllib.error.URLError("SECRET"), TimeoutError("SECRET")]
        for error in errors:
            with self.subTest(error=type(error)), patch.object(client.opener, "open", side_effect=error):
                with self.assertRaises(ya.Error) as caught:
                    client.request("POST", "/sessions", {"message": "SECRET"})
                self.assertNotIn("SECRET", str(caught.exception))

    def test_accept_does_not_store_prompt_or_server_errors(self):
        item = receipt()
        ya.accept(item, {"queued": True, "queueId": "queue-a", "position": 1,
                         "message": "SECRET", "error": "SECRET"})
        self.assertEqual(item["outcome"], "queued")
        self.assertNotIn("SECRET", json.dumps(item))

    def test_run_mismatch_sends_no_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            ya.save(path, {**receipt(), "baseUrl": "https://different.invalid"}, exclusive=True)
            args = argparse.Namespace(command="abort", receipt=str(path), auth_headers_file=None,
                                      base_url="https://example.invalid", project_path="/workspace/project")
            with patch.object(ya.Client, "request") as request, self.assertRaises(ya.Error):
                ya.run(args)
            request.assert_not_called()

    def test_resume_queue_checks_queue_before_old_terminated_process(self):
        item = {**receipt(), "queueId": "queue-a", "queuePending": True}
        client = FakeClient([{"position": 2}])
        self.assertEqual(ya.status(client, item)["outcome"], "queued")
        self.assertEqual(len(client.calls), 1)
        departed = FakeClient([None, {"process": process(state="terminated")}])
        self.assertEqual(ya.status(departed, item)["outcome"], "queue-departed-unresolved")

    def test_unknown_create_dispatch_stays_unknown(self):
        result = ya.status(FakeClient([]), {"outcome": "dispatch-pending"})
        self.assertEqual(result["outcome"], "dispatch-outcome-unknown")
        self.assertEqual(ya.status(FakeClient([]), result)["outcome"], "dispatch-outcome-unknown")

    def test_create_preserves_acceptance_if_observation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("PRIVATE PROMPT")
            args = argparse.Namespace(command="create", receipt=str(path), auth_headers_file=None,
                                      base_url="https://example.invalid", project_path="/workspace/project",
                                      message_file=str(prompt), effort="low", speed="normal")
            chosen = receipt()["requested"]
            with patch.object(ya, "settings", return_value=chosen), patch.object(
                    ya.Client, "request", return_value={"sessionId": "provisional", "processId": "process-a"}
            ) as request, patch.object(ya, "status", side_effect=ya.Error("observation failed")):
                with self.assertRaises(ya.Error):
                    ya.run(args)
            saved = ya.private_json(path)
            self.assertEqual(saved["processId"], "process-a")
            self.assertEqual(saved["outcome"], "accepted")
            self.assertNotIn("PRIVATE PROMPT", json.dumps(saved))
            self.assertEqual(set(request.call_args.args[2]),
                             {"model", "provider", "thinking", "serviceTier", "message"})
            with patch.object(ya, "settings", return_value=chosen), patch.object(ya.Client, "request") as request:
                with self.assertRaises(FileExistsError):
                    ya.run(args)
                request.assert_not_called()

    def test_receipt_cannot_add_permission_fields_to_followup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("followup")
            item = {**receipt(), "baseUrl": "https://example.invalid"}
            item["requested"]["mode"] = "bypassPermissions"
            ya.save(path, item, exclusive=True)
            args = argparse.Namespace(command="message", receipt=str(path), auth_headers_file=None,
                                      base_url="https://example.invalid", project_path="/workspace/project",
                                      message_file=str(prompt))
            with patch.object(ya.Client, "request") as request, self.assertRaises(ya.Error):
                ya.run(args)
            request.assert_not_called()

    def test_abort_requires_verified_stop_and_limits_exemption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            ya.save(path, {**receipt(), "baseUrl": "https://example.invalid"}, exclusive=True)
            args = argparse.Namespace(command="abort", receipt=str(path), auth_headers_file=None,
                                      base_url="https://example.invalid", project_path="/workspace/project")
            fake = FakeClient([{"process": process()}, metadata(), {
                "aborted": True, "verifiedStopped": False,
                "resumeExemption": {"error": "SECRET", "autoResumeDisabled": False}}])
            with patch.object(ya.Client, "request", side_effect=fake.request):
                result = ya.run(args)
            self.assertEqual(result["outcome"], "stop-unverified")
            self.assertEqual(fake.calls[-1][2], {"blockResume": True})
            self.assertNotIn("SECRET", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
