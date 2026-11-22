"""The GNOME unlock provider must reject uncertain identities and prompts."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "guests/ubuntu/ui"))
from gnome_unlock import PasswordQuestion, UnlockRefused, observe_console


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.path = "/org/freedesktop/login1/session/_31"
        self.fields = {
            "Id": "1", "Class": "user", "Type": "wayland", "Remote": False,
            "Active": True, "TimestampMonotonic": 3123, "LockedHint": True,
        }
        self.sessions = [("1", 1000, "fixture", "seat0", self.path)]
        self.session_fields = {}
        self.pids = {":1.10": 20, ":1.11": 20}
        self.active = True

    def call(self, bus, destination, path, interface, method, parameters, signature):
        if method == "ListSessions":
            return (self.sessions,)
        if method == "GetAll":
            return ({**self.fields, "Id": next(row[0] for row in self.sessions if row[4] == path),
                     **self.session_fields.get(path, {})},)
        if method == "GetNameOwner":
            return (":1.10" if parameters[1][0] == "org.gnome.Shell.ScreenShield" else ":1.11",)
        if method == "GetConnectionUnixProcessID":
            return (self.pids[parameters[1][0]],)
        if method == "GetActive":
            self.assertEqual(destination, ":1.10")
            return (self.active,)
        self.fail(f"Unexpected method {method}")

    def observe(self):
        return observe_console("system", "session", self.call, 1000)

    def test_two_connections_can_belong_to_the_same_shell(self):
        observation = self.observe()
        self.assertTrue(observation.locked)
        self.assertFalse(observation.unlocked)
        self.assertEqual(observation.console.session_id, "1")

    def test_unlocked_requires_both_native_observations(self):
        self.active = False
        self.assertFalse(self.observe().locked)
        self.assertFalse(self.observe().unlocked)
        self.fields["LockedHint"] = False
        self.assertTrue(self.observe().unlocked)

    def test_console_must_be_an_active_local_wayland_user(self):
        for field, value in (("Class", "greeter"), ("Type", "x11"),
                             ("Active", False), ("Remote", True)):
            with self.subTest(field=field):
                original = self.fields[field]
                self.fields[field] = value
                with self.assertRaisesRegex(UnlockRefused, "gnome_console_unavailable"):
                    self.observe()
                self.fields[field] = original

    def test_refuses_second_same_user_graphical_session_without_local_seat(self):
        self.sessions.append(("2", 1000, "fixture", "", "/fixture/second"))
        with self.assertRaisesRegex(UnlockRefused, "gnome_console_unavailable"):
            self.observe()

    def test_ignores_a_closing_graphical_session(self):
        self.sessions.append(("2", 1000, "fixture", "seat0", "/fixture/old"))
        self.session_fields["/fixture/old"] = {"State": "closing", "Active": False}
        self.assertEqual(self.observe().console.session_id, "1")

    def test_refuses_screensaver_owned_by_another_process(self):
        self.pids[":1.10"] = 19
        with self.assertRaisesRegex(UnlockRefused, "gnome_console_unavailable"):
            self.observe()


class PasswordQuestionTests(unittest.TestCase):
    def test_accepts_only_expected_gdm_password_question_once(self):
        question = PasswordQuestion()
        question.accept("gdm-password", "Password: ")
        with self.assertRaisesRegex(UnlockRefused, "gnome_password_prompt_unavailable"):
            question.accept("gdm-password", "Password: ")

    def test_refuses_other_services_and_password_change_or_mfa_prompts(self):
        for service, prompt in (("gdm-fingerprint", "Password:"),
                                ("gdm-password", "New password:"),
                                ("gdm-password", "Verification code:")):
            with self.subTest(service=service, prompt=prompt):
                question = PasswordQuestion()
                with self.assertRaisesRegex(UnlockRefused, "gnome_password_prompt_unavailable"):
                    question.accept(service, prompt)
                self.assertFalse(question.sent)


if __name__ == "__main__":
    unittest.main()
