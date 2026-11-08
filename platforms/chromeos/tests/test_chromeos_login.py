from pathlib import Path
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock


PLATFORM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLATFORM_ROOT))
sys.path.insert(0, str(PLATFORM_ROOT / "scripts"))
import cdp
import chromeos_login as cl
import login_request


ACTIVE_SESSIONS_REPLY = """method return time=1 sender=:1.39 -> destination=:1.230 serial=68 reply_serial=2
   array [
      dict entry(
         string "Owner@Example.com"
         string "0123abcd"
      )
   ]
"""
NO_SESSIONS_REPLY = """method return time=1 sender=:1.39 -> destination=:1.230 serial=68 reply_serial=2
   array [
   ]
"""

DVORAK = "_comp_ime_jkghodnilhceideoidjikpgommlajknkxkb:us:dvorak:eng"
QWERTY = "_comp_ime_jkghodnilhceideoidjikpgommlajknkxkb:us::eng"
TARGET = "owner@example.com"
OTHER = "other@example.com"


def known_user(email, layout=QWERTY, remaps=None, pin=True, length=6, reauth=None):
    user = {
        "email": email,
        "last_input_method": layout,
        "settings": {"keyboard": {"internal": {"modifier_remappings": remaps or {}}}},
        "pin_autosubmit_length": length,
        "reauth_reason": reauth,
    }
    if pin:
        user["quick_unlock"] = {"pin": {"salt": "x"}}
    return user


def local_state(*users, last=TARGET, force_online=None):
    return {
        "KnownUsers": list(users),
        "LastActiveUser": last,
        "UserForceOnlineSignin": force_online or {},
    }


class SessionManagerParsingTests(unittest.TestCase):
    def test_parses_active_session_accounts(self):
        self.assertEqual(["Owner@Example.com"], cl.parse_active_sessions(ACTIVE_SESSIONS_REPLY))
        self.assertEqual([], cl.parse_active_sessions(NO_SESSIONS_REPLY))

    def test_session_state_reports_screen(self):
        replies = {
            "RetrieveSessionState": '   string "started"\n',
            "RetrieveActiveSessions": ACTIVE_SESSIONS_REPLY,
            "IsScreenLocked": "   boolean true\n",
        }
        state = cl.session_state(call=lambda method: replies[method])
        self.assertEqual("locked", state["screen"])
        self.assertEqual([TARGET], state["active_users"])

    def test_sign_in_screen_skips_lock_query(self):
        calls = []

        def call(method):
            calls.append(method)
            return {"RetrieveSessionState": '   string "stopped"\n',
                    "RetrieveActiveSessions": NO_SESSIONS_REPLY}[method]

        self.assertEqual("signin", cl.session_state(call=call)["screen"])
        self.assertNotIn("IsScreenLocked", calls)


class KeyboardProfileTests(unittest.TestCase):
    def test_dvorak_with_search_control_swap(self):
        profile = cl.keyboard_profile(known_user(TARGET, DVORAK, {"0": 1, "1": 0}))
        self.assertEqual([125, 56, 53], cl.chromevox_toggle_keycodes(profile))

    def test_default_qwerty(self):
        profile = cl.keyboard_profile(known_user(TARGET))
        self.assertEqual([29, 56, 44], cl.chromevox_toggle_keycodes(profile))

    def test_caps_lock_acting_as_control(self):
        profile = cl.keyboard_profile(known_user(TARGET, remaps={"1": 3, "4": 1}))
        self.assertEqual(58, cl.physical_modifier_keycode(cl.MOD_CONTROL, profile["remaps"]))

    def test_unsupported_layout_is_refused(self):
        with self.assertRaises(cl.LoginError) as raised:
            cl.z_keycode("_comp_ime_x:de::ger")
        self.assertEqual("keyboard-layout", raised.exception.code)


class RequirementTests(unittest.TestCase):
    def test_requirements(self):
        state = local_state(known_user(TARGET), known_user(OTHER, pin=False, reauth=3))
        self.assertEqual(
            {"pin_configured": True, "autosubmit_length": 6, "online_reauth_required": False},
            cl.account_requirements(state, TARGET),
        )
        other = cl.account_requirements(state, OTHER)
        self.assertFalse(other["pin_configured"])
        self.assertTrue(other["online_reauth_required"])

    def test_forced_online_sign_in(self):
        state = local_state(known_user(TARGET), force_online={TARGET: True})
        self.assertTrue(cl.account_requirements(state, TARGET)["online_reauth_required"])

    def test_unknown_account(self):
        with self.assertRaises(cl.LoginError) as raised:
            cl.account_requirements(local_state(), TARGET)
        self.assertEqual("unknown-account", raised.exception.code)


def auth_view(account, mode="pin", focused=True, switch=True):
    if mode == "pin":
        fields = [{"name": cl.PIN_FIELD_NAME, "focused": focused}] + [{"name": "", "focused": False}] * 6
        buttons = [f"Open info dialog for {account}", "Switch to password"]
    else:
        fields = [{"name": f"Password for {account}", "focused": focused}]
        buttons = ["Submit"] + ([cl.SWITCH_TO_PIN] if switch else [])
    return {"accounts": [account], "fields": fields, "buttons": buttons}


class AuthViewTests(unittest.TestCase):
    def test_selected_account_is_the_view_with_an_auth_field(self):
        raw = {"views": [auth_view(TARGET)], "accounts": [TARGET, OTHER]}
        summary = cl.summarize_auth_views(raw)
        self.assertEqual(TARGET, summary["selected_account"])
        self.assertEqual("pin", summary["auth_mode"])
        self.assertTrue(summary["pin_focused"])
        self.assertEqual([OTHER, TARGET], summary["accounts"])

    def test_password_mode_offers_switch_to_pin(self):
        summary = cl.summarize_auth_views({"views": [auth_view(TARGET, "password")], "accounts": [TARGET]})
        self.assertEqual("password", summary["auth_mode"])
        self.assertTrue(summary["switch_to_pin"])
        self.assertFalse(summary["pin_focused"])

    def test_two_auth_views_are_ambiguous(self):
        raw = {"views": [auth_view(TARGET), auth_view(OTHER)], "accounts": []}
        with self.assertRaises(cl.LoginError):
            cl.summarize_auth_views(raw)


class FakeDevice:
    """Simulates the login screen, ChromeVox, and session_manager."""

    def __init__(self, local_state_value, selected=TARGET, mode="pin", focused=True,
                 screen="signin", active=None, correct_pin="123456", host_running=False,
                 accounts=(TARGET, OTHER), chromevox_starts=True):
        self.local = local_state_value
        self.selected = selected
        self.mode = mode
        self.focused = focused
        self.screen = screen
        self.active = list(active or [])
        self.correct_pin = correct_pin
        self.host_running = host_running
        self.chromevox = False
        self.chromevox_starts = chromevox_starts
        self.accounts = list(accounts)
        self.typed = []
        self.combos = []
        self.chromevox_on_while_typing = False
        self.now = 0.0

    # session_manager
    def state(self):
        return {"session": "started" if self.active else "stopped",
                "active_users": list(self.active),
                "locked": self.screen == "locked", "screen": self.screen}

    # keyboard
    def press(self, keycodes):
        """Only the focused account's Ctrl+Alt+Z, as ChromeOS maps it, toggles ChromeVox."""
        self.combos.append(list(keycodes))
        focused = cl.keyboard_profile(cl.known_user(self.local, self.selected))
        if self.chromevox_starts and list(keycodes) == cl.chromevox_toggle_keycodes(focused):
            self.chromevox = not self.chromevox

    def type_keys(self, keycodes):
        self.chromevox_on_while_typing |= self.chromevox
        self.typed.extend(keycodes)
        digits = {v: k for k, v in cl.DIGIT_KEYCODES.items()}
        entered = "".join(digits[k] for k in keycodes if k in digits)
        if self.focused and self.mode == "pin" and entered == self.correct_pin:
            account = self.selected
            if account not in self.active:
                self.active.append(account)
            self.screen = "active"

    # cdp
    def list_targets(self):
        if self.chromevox:
            return [{"type": "background_page",
                     "url": f"chrome-extension://{cl.CHROMEVOX_EXTENSION_ID}/chromevox/mv2/background/background.html",
                     "webSocketDebuggerUrl": "ws://chromevox"}]
        return []

    def find_automation_target(self):
        if self.host_running or self.chromevox:
            return "ws://host"
        raise RuntimeError("No accessibility extension service worker found.")

    def desktop_evaluate(self, js):
        if js == cl.SCAN_JS:
            views = [auth_view(self.selected, self.mode, self.focused)]
            return json.dumps({"views": views, "accounts": self.accounts})
        name = json.loads(js.split("attributes: {name: ")[1].split("}});")[0])
        if name in self.accounts:
            self.selected = name
            self.mode, self.focused = "pin", True
        elif name == cl.SWITCH_TO_PIN:
            self.mode, self.focused = "pin", True
        elif name == cl.PIN_FIELD_NAME:
            self.focused = True
        elif name == cl.DISABLE_CHROMEVOX:
            self.chromevox = False
        return json.dumps({"found": True})

    def sleep(self, seconds):
        self.now += seconds

    def clock(self):
        return self.now

    def login(self, **request):
        request.setdefault("pin", "123456")
        return cl.login(request, cdp=self, press=self.press, type_keys=self.type_keys,
                        state_fn=self.state, local_state_fn=lambda: self.local,
                        sleep=self.sleep, clock=self.clock)


def digits_of(keycodes):
    names = {v: k for k, v in cl.DIGIT_KEYCODES.items()}
    return "".join(names[k] for k in keycodes if k in names)


class LoginFlowTests(unittest.TestCase):
    def setUp(self):
        self.state = local_state(known_user(TARGET, DVORAK, {"0": 1, "1": 0}), known_user(OTHER))

    def test_signs_in_preselected_account_with_chromevox_off_while_typing(self):
        device = FakeDevice(self.state)
        result = device.login(account=TARGET)
        self.assertEqual("signed-in", result["result"])
        self.assertTrue(result["typed"])
        self.assertIn("chromevox-disabled", result["steps"])
        self.assertFalse(device.chromevox)
        self.assertFalse(device.chromevox_on_while_typing)
        self.assertEqual([125, 56, 53], device.combos[1])
        self.assertEqual("123456", digits_of(device.typed))
        self.assertNotIn(cl.KEY_ENTER, device.typed)  # auto-submit length is known
        self.assertNotIn("123456", json.dumps(result))

    def test_selects_target_and_disables_chromevox_with_its_keyboard(self):
        device = FakeDevice(self.state, selected=OTHER)
        self.state["LastActiveUser"] = OTHER
        result = device.login(account=TARGET)
        self.assertIn("account-selected", result["steps"])
        self.assertEqual([29, 56, 44], device.combos[1])   # OTHER is focused: QWERTY, no swap
        self.assertEqual([125, 56, 53], device.combos[2])  # TARGET's settings after selection
        self.assertEqual([TARGET], device.active)

    def test_another_selected_account_still_starts_chromevox(self):
        # The last-used account is the target, but someone selected OTHER.
        device = FakeDevice(self.state, selected=OTHER)
        result = device.login(account=TARGET)
        self.assertEqual("signed-in", result["result"])
        self.assertEqual([125, 56, 53], device.combos[1])  # last-used guess: no effect
        self.assertEqual([29, 56, 44], device.combos[2])   # OTHER's shortcut starts ChromeVox
        self.assertEqual([125, 56, 53], device.combos[3])  # TARGET's shortcut stops it
        self.assertFalse(device.chromevox_on_while_typing)

    def test_switches_from_password_to_pin(self):
        device = FakeDevice(self.state, mode="password", focused=True)
        result = device.login(account=TARGET)
        self.assertIn("switched-to-pin", result["steps"])

    def test_password_only_is_refused_before_typing(self):
        device = FakeDevice(self.state)
        device.mode = "password"
        original = device.desktop_evaluate

        def no_switch(js):
            if js == cl.SCAN_JS:
                return json.dumps({"views": [auth_view(TARGET, "password", switch=False)],
                                   "accounts": device.accounts})
            return original(js)

        device.desktop_evaluate = no_switch
        with self.assertRaises(cl.LoginError) as raised:
            device.login(account=TARGET)
        self.assertEqual("pin-unavailable", raised.exception.code)
        self.assertEqual([], device.typed)
        self.assertFalse(device.chromevox)

    def test_already_active_does_not_type(self):
        device = FakeDevice(self.state, screen="active", active=[TARGET])
        result = device.login(account=TARGET)
        self.assertEqual("already-active", result["result"])
        self.assertEqual([], device.combos)

    def test_other_active_user_is_refused(self):
        device = FakeDevice(self.state, screen="locked", active=[OTHER])
        with self.assertRaises(cl.LoginError) as raised:
            device.login(account=TARGET)
        self.assertEqual("other-user-active", raised.exception.code)
        self.assertEqual([], device.combos)

    def test_unlocks_lock_screen_using_existing_host(self):
        device = FakeDevice(self.state, screen="locked", active=[TARGET], host_running=True)
        result = device.login(account=TARGET)
        self.assertEqual("unlocked", result["result"])
        self.assertIn("automation-host-found", result["steps"])
        self.assertEqual([[cl.KEY_LEFTSHIFT]], device.combos)  # ChromeVox never toggled

    def test_pin_length_mismatch_is_refused_before_any_input(self):
        device = FakeDevice(self.state)
        with self.assertRaises(cl.LoginError) as raised:
            device.login(account=TARGET, pin="1234567")
        self.assertEqual("pin-length-mismatch", raised.exception.code)
        self.assertEqual([], device.combos)

    def test_online_reauth_is_refused(self):
        self.state["KnownUsers"][0]["reauth_reason"] = 4
        with self.assertRaises(cl.LoginError) as raised:
            FakeDevice(self.state).login(account=TARGET)
        self.assertEqual("online-reauth", raised.exception.code)

    def test_wrong_pin_is_reported_once_without_retry(self):
        device = FakeDevice(self.state, correct_pin="654321")
        with self.assertRaises(cl.LoginError) as raised:
            device.login(account=TARGET, timeout=2)
        self.assertEqual("not-confirmed", raised.exception.code)
        self.assertTrue(raised.exception.typed)
        self.assertEqual(1, digits_of(device.typed).count("123456"))
        self.assertNotIn("123456", str(raised.exception))

    def test_unlisted_account_turns_chromevox_back_off(self):
        device = FakeDevice(self.state, selected=OTHER, accounts=(OTHER,))
        with self.assertRaises(cl.LoginError) as raised:
            device.login(account=TARGET)
        self.assertEqual("account-not-listed", raised.exception.code)
        self.assertFalse(device.chromevox)
        self.assertEqual([], device.typed)

    def test_chromevox_that_never_starts_is_reported(self):
        device = FakeDevice(self.state, chromevox_starts=False)
        with self.assertRaises(cl.LoginError) as raised:
            device.login(account=TARGET)
        self.assertEqual("automation-unavailable", raised.exception.code)
        self.assertEqual([], device.typed)

    def test_bad_requests(self):
        device = FakeDevice(self.state)
        for request in ({"pin": "12a4"}, {"pin": "123"}, {"pin": "123456", "account": "nope"}):
            with self.assertRaises(cl.LoginError):
                cl.login(request, cdp=device, press=device.press, type_keys=device.type_keys,
                         state_fn=device.state, local_state_fn=lambda: self.state)


class LoginStatusTests(unittest.TestCase):
    def test_status_never_reports_pin_length(self):
        state = local_state(known_user(TARGET))
        result = cl.login_status({"account": TARGET},
                                 state_fn=lambda: {"session": "stopped", "active_users": [],
                                                   "locked": False, "screen": "signin"},
                                 local_state_fn=lambda: state)
        self.assertEqual(TARGET, result["last_active_user"])
        self.assertTrue(result["account"]["pin_configured"])
        self.assertNotIn("autosubmit", json.dumps(result))


class ChromeVoxHostTests(unittest.TestCase):
    def test_recognizes_chromevox_background_page_only(self):
        base = f"chrome-extension://{cdp._CHROMEVOX_EXT_ID}/chromevox/mv2"
        self.assertTrue(cdp._is_chromevox_background(
            {"type": "background_page", "url": base + "/background/background.html"}))
        self.assertFalse(cdp._is_chromevox_background(
            {"type": "other", "url": base + "/panel/panel.html"}))


@unittest.skipIf(os.name == "nt", "POSIX permission checks")
class LoginRequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "secrets"
        self.dir.mkdir(mode=0o700)
        os.chmod(self.dir, 0o700)
        self.file = self.dir / "login-pin.secret"
        self.file.write_text("123456\n")
        os.chmod(self.file, 0o600)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_private_file(self):
        self.assertEqual("123456", login_request.read_pin_file(self.file))

    def test_rejects_group_readable_file(self):
        os.chmod(self.file, 0o640)
        with self.assertRaises(login_request.RequestError):
            login_request.read_pin_file(self.file)

    def test_rejects_open_directory(self):
        os.chmod(self.dir, 0o755)
        with self.assertRaises(login_request.RequestError):
            login_request.read_pin_file(self.file)

    def test_rejects_symlink(self):
        link = self.dir / "link.secret"
        link.symlink_to(self.file)
        with self.assertRaises(login_request.RequestError):
            login_request.read_pin_file(link)

    def test_rejects_non_digit_content_without_echoing_it(self):
        self.file.write_text("12ab56\n")
        with self.assertRaises(login_request.RequestError) as raised:
            login_request.read_pin_file(self.file)
        self.assertNotIn("12ab56", str(raised.exception))

    def test_file_requires_account(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            self.assertEqual(2, login_request.main(["--pin-file", str(self.file)]))
        self.assertIn("explicit account", stderr.getvalue())

    def test_request_line(self):
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdout", stdout):
            code = login_request.main(["--pin-file", str(self.file), "--account", "Owner@Example.com"])
        self.assertEqual(0, code)
        self.assertEqual({"cmd": "login", "pin": "123456", "timeout": 20, "account": TARGET},
                         json.loads(stdout.getvalue()))



if __name__ == "__main__":
    unittest.main()
