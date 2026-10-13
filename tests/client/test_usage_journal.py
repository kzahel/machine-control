"""Usage notes: session attribution, audit correlation, bounds and privacy."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "client" / "machine_control.py"
MOCK = ROOT / "tests" / "client" / "fixtures" / "mock-testbed.py"
sys.path.insert(0, str(ROOT / "client"))
import audit_history as audit
import usage_journal as journal

SESSION_VARIABLES = ("AGENTCTL_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "AI_AGENT")


class UsageJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        environment = {name: "" for name in SESSION_VARIABLES}
        environment.update(MACHINE_CONTROL_USAGE_DIR=str(self.root / "usage"),
                           MACHINE_CONTROL_AUDIT_DIR=str(self.root / "audit"))
        patch = mock.patch.dict(os.environ, environment)
        patch.start()
        self.addCleanup(patch.stop)

    def test_session_reference_precedence_and_validation(self):
        self.assertIsNone(audit.session_ref())
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "thread-1",
                                          "CLAUDE_CODE_SESSION_ID": "claude-1"}):
            self.assertEqual(audit.session_ref(), {"id": "claude-1", "source": "CLAUDE_CODE_SESSION_ID"})
            with mock.patch.dict(os.environ, {"AGENTCTL_SESSION_ID": "ya-1"}):
                self.assertEqual(audit.session_ref()["source"], "AGENTCTL_SESSION_ID")
                self.assertEqual(audit.session_ref("explicit-1"),
                                 {"id": "explicit-1", "source": "explicit"})
        with mock.patch.dict(os.environ, {"AGENTCTL_SESSION_ID": "../escape path"}):
            self.assertIsNone(audit.session_ref())
        self.assertIsNone(audit.session_ref("bad id"))

    def test_note_records_session_and_attaches_claim_commands(self):
        claim = "c-" + "a" * 24
        with mock.patch.dict(os.environ, {"AGENTCTL_SESSION_ID": "ya-session",
                                          "AI_AGENT": "codex_1_agent"}):
            command = audit.Command("host", "macos", ["desktop", "input", "text", "secret-ish"], claim)
            command.observe({"accepted": False, "errorCode": "usage"})
            command.finish(2)
            value = journal.note("friction", "Go-to sheet missing from snapshot",
                                 goal="load unpacked extension", target="host", claim=claim)
        self.assertEqual(value["sessionRef"], {"id": "ya-session", "source": "AGENTCTL_SESSION_ID"})
        self.assertEqual(value["agent"], "codex_1_agent")
        shown = journal.show(with_commands=True)
        trail = shown["notes"][0]["audit"]
        self.assertEqual(trail["selector"], "claim")
        self.assertEqual(trail["commands"][0]["command"], "desktop input text")
        self.assertEqual(trail["commands"][0]["errorCode"], "usage")
        self.assertNotIn("secret-ish", json.dumps(shown))
        self.assertIn("ya-session", journal.markdown(shown))
        self.assertEqual(audit.history(session="ya-session")["events"][0]["sessionRef"]["id"], "ya-session")
        if os.name != "nt":
            self.assertEqual((self.root / "usage").stat().st_mode & 0o777, 0o700)
            self.assertEqual((self.root / "usage/notes.sqlite3").stat().st_mode & 0o777, 0o600)

    def test_session_fallback_filters_and_pagination(self):
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "thread-a"}):
            audit.Command("host", "macos", ["browser", "navigate"]).finish(0)
            journal.note("fallback", "Switched to Computer Use")
        journal.note("handoff", "Person took over", session="thread-b")
        journal.note("summary", "Done", session="thread-b")
        self.assertEqual(len(journal.show(session="thread-b")["notes"]), 2)
        self.assertEqual(journal.show(kind="fallback")["notes"][0]["sessionRef"]["id"], "thread-a")
        trail = journal.show(session="thread-a", with_commands=True)["notes"][0]["audit"]
        self.assertEqual((trail["selector"], trail["commands"][0]["command"]), ("session", "browser navigate"))
        first = journal.show(limit=2)
        self.assertEqual([n["kind"] for n in first["notes"]], ["handoff", "summary"])
        older = journal.show(limit=2, before=first["nextBeforeId"])
        self.assertEqual([n["kind"] for n in older["notes"]], ["fallback"])
        self.assertIsNone(older["nextBeforeId"])
        with mock.patch.object(journal, "MAX_NOTES", 2):
            journal.note("summary", "Newest", session="thread-b")
        self.assertEqual(len(journal.show()["notes"]), 2)

    def test_invalid_context_is_refused(self):
        for arguments in (dict(goal="two\nlines"), dict(goal="x" * 201), dict(target="../x"),
                          dict(claim="c-bad"), dict(session="bad id")):
            with self.assertRaises(journal.JournalError):
                journal.note("friction", "text", **arguments)
        with self.assertRaises(journal.JournalError):
            journal.note("unknown", "text")
        self.assertFalse(journal.show()["available"])

    def run_cli(self, *arguments, stdin="", environment=None):
        env = os.environ.copy()
        env.update(environment or {})
        return subprocess.run([sys.executable, str(CLI), *arguments], input=stdin,
                              text=True, capture_output=True, check=False, env=env)

    def test_cli_note_show_and_bounds(self):
        claim = "c-" + "b" * 24
        result = self.run_cli("--target", "host", "--claim", claim, "usage", "note",
                              "--kind", "friction", "--goal", "open folder chooser",
                              stdin="Select button not found\n",
                              environment={"CLAUDE_CODE_SESSION_ID": "claude-cli"})
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual((value["claimId"], value["logicalTarget"], value["sessionRef"]["id"]),
                         (claim, "host", "claude-cli"))
        result = self.run_cli("usage", "show", "--markdown", "--commands")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("open folder chooser", result.stdout)
        self.assertEqual(self.run_cli("usage", "note", "--kind", "friction",
                                      stdin="x" * 4097).returncode, 2)
        self.assertEqual(self.run_cli("usage", "note", "--kind", "friction",
                                      stdin="  \n").returncode, 2)
        self.assertEqual(self.run_cli("usage", "show", "--limit", "0").returncode, 2)


class ClaimantDefaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = self.root / "targets.json"
        self.registry.write_text(json.dumps({"schema": "machine-control-targets/v0", "targets": {
            "fixture": {"platform": "linux", "profile": "fixture", "launcher": "auto",
                        "controllerPlatforms": [__import__("machine_control").controller_platform()],
                        "claimPolicy": "optional", "command": [sys.executable, str(MOCK)]}}}))

    def acquire(self, *extra, environment):
        log = self.root / "arguments.json"
        env = {k: v for k, v in os.environ.items() if k not in SESSION_VARIABLES}
        env.update(environment, MACHINE_CONTROL_MOCK_LOG=str(log), MACHINE_CONTROL_MOCK_PLATFORM="linux",
                   MACHINE_CONTROL_AUDIT_DIR=str(self.root / "audit"),
                   XDG_CONFIG_HOME=str(self.root / "config"))
        result = subprocess.run([sys.executable, str(CLI), "--registry", str(self.registry),
                                 "--target", "fixture", "claim", "acquire", "--reason", "test", *extra],
                                text=True, capture_output=True, check=False, env=env)
        return result, json.loads(log.read_text()) if log.exists() else None

    def test_session_becomes_claimant_only_without_explicit_pair(self):
        result, arguments = self.acquire(environment={"AGENTCTL_SESSION_ID": "ya-claim"})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(arguments[arguments.index("--claimant-authority") + 1], "yepanywhere")
        self.assertEqual(arguments[arguments.index("--claimant-id") + 1], "ya-claim")
        self.assertEqual(arguments[arguments.index("--session-id") + 1], "ya-claim")
        result, arguments = self.acquire("--claimant-authority", "ci", "--claimant-id", "job-1",
                                         environment={"CODEX_THREAD_ID": "thread"})
        self.assertEqual(arguments[arguments.index("--claimant-id") + 1], "job-1")
        self.assertNotIn("--session-id", arguments)
        result, _ = self.acquire("--claimant-id", "partial", environment={"CODEX_THREAD_ID": "thread"})
        self.assertEqual(result.returncode, 2)
        result, _ = self.acquire(environment={})
        self.assertEqual(json.loads(result.stdout)["errorCode"], "usage")


if __name__ == "__main__":
    unittest.main()
