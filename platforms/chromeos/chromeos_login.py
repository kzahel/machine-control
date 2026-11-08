"""ChromeOS sign-in and lock-screen PIN entry for the on-device client.

The controller sends one ``login`` request over SSH stdin. This module runs the
whole flow on the Chromebook so it needs one round trip:

1. Read session state from session_manager (signed in, locked, which account).
2. Check the account's recorded sign-in requirements in ``Local State`` without
   typing anything (PIN configured, no forced online re-authentication, PIN
   length matches the auto-submit length).
3. Obtain a ``chrome.automation`` host. The sign-in profile blocks the
   Select-to-speak and Accessibility Common extensions on stable channel, but
   ChromeVox is allowed, so ChromeVox is enabled briefly with its keyboard
   accelerator when no other accessibility host is running.
4. Select and confirm the exact account, require PIN entry, focus the PIN
   field, and disable ChromeVox again before any secret is typed.
5. Type the PIN once and confirm that exactly the requested account is signed
   in and unlocked. A failed attempt is never retried.

The PIN is used only to emit key events. It never appears in results, errors,
logs, or process arguments.
"""

import json
import re
import subprocess
import time

LOCAL_STATE = "/home/chronos/Local State"
CHROMEVOX_EXTENSION_ID = "mndnfokpggljbaajbnioimlmbfngpief"
AUTH_VIEW_CLASS = "LoginAuthUserView"
PIN_FIELD_NAME = "Enter your PIN"
PASSWORD_FIELD_PREFIX = "Password for "
SWITCH_TO_PIN = "Switch to PIN"
DISABLE_CHROMEVOX = "Disable ChromeVox"

# ChromeOS modifier identifiers used by keyboard modifier_remappings
# (physical modifier -> logical modifier).
MOD_SEARCH, MOD_CONTROL, MOD_ALT, MOD_VOID, MOD_CAPS_LOCK, MOD_ESCAPE = 0, 1, 2, 3, 4, 5
MODIFIER_KEYCODES = {
    MOD_SEARCH: 125,
    MOD_CONTROL: 29,
    MOD_ALT: 56,
    MOD_CAPS_LOCK: 58,
    MOD_ESCAPE: 1,
}
KEY_Z = 44
KEY_SLASH = 53  # The physical key that produces "z" on US Dvorak.
KEY_BACKSPACE = 14
KEY_ENTER = 28
KEY_LEFTSHIFT = 42
DIGIT_KEYCODES = {
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6,
    "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
}

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PIN_RE = re.compile(r"^[0-9]{4,20}$")


class LoginError(Exception):
    """A refusal or failure with a stable code. Messages never contain secrets."""

    def __init__(self, code, message, typed=False):
        super().__init__(message)
        self.code = code
        self.typed = typed


# === Session manager ===

def _session_manager_call(method):
    proc = subprocess.run(
        [
            "dbus-send", "--system", "--print-reply",
            "--dest=org.chromium.SessionManager",
            "/org/chromium/SessionManager",
            f"org.chromium.SessionManagerInterface.{method}",
        ],
        capture_output=True, text=True, timeout=10,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise LoginError("session-manager", f"{method} failed: {detail[-1] if detail else 'no output'}")
    return proc.stdout


def parse_active_sessions(text):
    """Return account emails from a RetrieveActiveSessions reply."""
    return re.findall(r'dict entry\(\s*string "([^"]*)"', text)


def parse_boolean(text):
    match = re.search(r"\bboolean (true|false)\b", text)
    if not match:
        raise LoginError("session-manager", "unexpected boolean reply from session_manager")
    return match.group(1) == "true"


def parse_string(text):
    match = re.search(r'\bstring "([^"]*)"', text)
    return match.group(1) if match else ""


def session_state(call=_session_manager_call):
    """Describe the current screen: sign-in, locked, or an active session."""
    state = parse_string(call("RetrieveSessionState"))
    users = [u.lower() for u in parse_active_sessions(call("RetrieveActiveSessions"))]
    locked = parse_boolean(call("IsScreenLocked")) if users else False
    if not users:
        screen = "signin"
    elif locked:
        screen = "locked"
    else:
        screen = "active"
    return {"session": state, "active_users": users, "locked": locked, "screen": screen}


def lock_screen(call=_session_manager_call, state_fn=None, sleep=time.sleep, timeout=10):
    """Ask session_manager to lock the active session and wait for the lock."""
    state_fn = state_fn or (lambda: session_state(call))
    before = state_fn()
    if before["screen"] == "signin":
        raise LoginError("no-session", "no user session is active; nothing to lock")
    if before["locked"]:
        return {"ok": True, "result": "already-locked", "account": before["active_users"][0]}
    call("LockScreen")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if state_fn()["locked"]:
            return {"ok": True, "result": "locked", "account": before["active_users"][0]}
        sleep(0.5)
    raise LoginError("lock-not-confirmed", f"screen lock was not confirmed after {timeout}s")


# === Local State ===

def load_local_state(path=LOCAL_STATE):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def known_user(local_state, account):
    account = (account or "").lower()
    for user in local_state.get("KnownUsers", []) or []:
        if str(user.get("email", "")).lower() == account:
            return user
    return None


def account_requirements(local_state, account):
    """Summarize what the device records about signing this account in."""
    user = known_user(local_state, account)
    if user is None:
        raise LoginError("unknown-account", f"{account} is not a known account on this device")
    pin = ((user.get("quick_unlock") or {}).get("pin")) or {}
    length = user.get("pin_autosubmit_length")
    reauth = user.get("reauth_reason")
    force_online = (local_state.get("UserForceOnlineSignin") or {}).get(account) is True
    return {
        "pin_configured": bool(pin),
        "autosubmit_length": length if isinstance(length, int) and length > 0 else None,
        "online_reauth_required": bool(reauth) or force_online,
    }


def keyboard_profile(user):
    """Return the layout and internal-keyboard modifier remappings for an account."""
    user = user or {}
    keyboard = ((user.get("settings") or {}).get("keyboard") or {}).get("internal") or {}
    remaps = {}
    for physical, logical in (keyboard.get("modifier_remappings") or {}).items():
        try:
            remaps[int(physical)] = int(logical)
        except (TypeError, ValueError):
            continue
    return {"layout": str(user.get("last_input_method") or ""), "remaps": remaps}


def physical_modifier_keycode(logical, remaps):
    """Physical key that acts as ``logical`` under the account's remapping."""
    if remaps.get(logical, logical) == logical and logical in MODIFIER_KEYCODES:
        return MODIFIER_KEYCODES[logical]
    for physical, mapped in sorted(remaps.items()):
        if mapped == logical and physical in MODIFIER_KEYCODES:
            return MODIFIER_KEYCODES[physical]
    raise LoginError("keyboard-remap", f"no physical key acts as modifier {logical}")


def z_keycode(layout):
    """Physical key that produces "z" for an xkb input method identifier."""
    match = re.search(r"xkb:([a-z]+):([a-z0-9_-]*):", layout or "")
    if not layout:
        return KEY_Z
    if not match:
        raise LoginError("keyboard-layout", f"unsupported input method {layout!r}")
    base, variant = match.groups()
    if base == "us" and variant == "dvorak":
        return KEY_SLASH
    if base == "us" and variant in ("", "intl", "altgr-intl"):
        return KEY_Z
    raise LoginError("keyboard-layout", f"unsupported input method {layout!r}")


def chromevox_toggle_keycodes(profile):
    """Keys for Ctrl+Alt+Z, the ChromeVox toggle, under the account's settings."""
    return [
        physical_modifier_keycode(MOD_CONTROL, profile["remaps"]),
        physical_modifier_keycode(MOD_ALT, profile["remaps"]),
        z_keycode(profile["layout"]),
    ]


# === Login UI ===

def summarize_auth_views(raw):
    """Interpret the raw login-UI scan from the automation host.

    ``raw`` has ``views`` (one per LoginAuthUserView with its account buttons,
    text fields, and buttons) and ``accounts`` (every account button visible).
    The selected account is the one whose view holds an auth field.
    """
    selected = None
    mode = None
    pin_focused = False
    buttons = set()
    for view in raw.get("views", []):
        fields = view.get("fields", [])
        pin_fields = [f for f in fields if f.get("name") == PIN_FIELD_NAME]
        password_fields = [f for f in fields if str(f.get("name", "")).startswith(PASSWORD_FIELD_PREFIX)]
        if not pin_fields and not password_fields:
            continue
        accounts = [a.lower() for a in view.get("accounts", []) if EMAIL_RE.match(a)]
        if len(accounts) != 1:
            continue
        if selected is not None:
            raise LoginError("ambiguous-ui", "more than one account shows an authentication field")
        selected = accounts[0]
        mode = "pin" if pin_fields else "password"
        pin_focused = any(f.get("focused") for f in pin_fields)
        buttons.update(view.get("buttons", []))
    return {
        "selected_account": selected,
        "auth_mode": mode,
        "pin_focused": pin_focused,
        "switch_to_pin": SWITCH_TO_PIN in buttons,
        "accounts": sorted({a.lower() for a in raw.get("accounts", []) if EMAIL_RE.match(a)}),
    }


SCAN_JS = """
new Promise((resolve, reject) => chrome.automation.getDesktop(root => {
  if (!root) { reject(new Error('No desktop root')); return; }
  const email = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
  const views = [];
  const accounts = [];
  const walk = (node, view) => {
    let current = view;
    if (node.className === '%s') {
      current = {accounts: [], fields: [], buttons: []};
      views.push(current);
    }
    const name = node.name || '';
    if (node.role === 'button' && email.test(name)) accounts.push(name);
    if (current) {
      if (node.role === 'button') {
        if (email.test(name)) current.accounts.push(name); else current.buttons.push(name);
      } else if (node.role === 'textField') {
        current.fields.push({name: name, focused: !!(node.state && node.state.focused)});
      }
    }
    for (const child of node.children || []) walk(child, current);
  };
  walk(root, null);
  resolve(JSON.stringify({views: views, accounts: accounts}));
}))
""" % AUTH_VIEW_CLASS


def _action_js(role, name, action):
    return """
new Promise((resolve, reject) => chrome.automation.getDesktop(root => {
  if (!root) { reject(new Error('No desktop root')); return; }
  const node = root.find({role: %s, attributes: {name: %s}});
  if (!node) { resolve(JSON.stringify({found: false})); return; }
  node.%s();
  resolve(JSON.stringify({found: true}));
}))
""" % (json.dumps(role), json.dumps(name), action)


class AutomationHost:
    """A chrome.automation host, enabling ChromeVox only when none is running."""

    def __init__(self, cdp, press, sleep=time.sleep, clock=time.monotonic):
        self.cdp = cdp
        self.press = press
        self.sleep = sleep
        self.clock = clock
        self.enabled_chromevox = False

    def chromevox_running(self):
        return any(
            CHROMEVOX_EXTENSION_ID in t.get("url", "") and "/background/" in t.get("url", "")
            for t in self.cdp.list_targets()
        )

    def _wait_chromevox(self, running, timeout):
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            if self.chromevox_running() == running:
                return True
            self.sleep(0.25)
        return self.chromevox_running() == running

    def open(self, profiles):
        """Find or start an automation host.

        ``profiles`` are candidate keyboard profiles for the focused account,
        most likely first. Returns the profile whose ChromeVox shortcut worked,
        or None when an existing host was used.
        """
        try:
            self.cdp.find_automation_target()
            return None
        except RuntimeError:
            pass
        tried = []
        for profile in profiles:
            try:
                keys = chromevox_toggle_keycodes(profile)
            except LoginError:
                continue
            if keys in tried:
                continue
            tried.append(keys)
            self.press(keys)
            if self._wait_chromevox(True, 6 if len(tried) == 1 else 3):
                self.enabled_chromevox = True
                # ChromeVox loads its automation tree asynchronously after the page appears.
                self.sleep(1.0)
                return profile
        if self.chromevox_running():
            # A late start: closing falls back to ChromeVox's own Disable button
            # if the first profile's shortcut does not match.
            self.enabled_chromevox = True
            self.sleep(1.0)
            return profiles[0]
        raise LoginError("automation-unavailable", "ChromeVox did not start; no accessibility host is available")

    def close(self, profile):
        if not self.enabled_chromevox:
            return
        self.press(chromevox_toggle_keycodes(profile))
        if not self._wait_chromevox(False, 5):
            self.do(DISABLE_CHROMEVOX, "button", "doDefault")
            if not self._wait_chromevox(False, 5):
                raise LoginError("chromevox-still-on", "ChromeVox could not be turned off; nothing was typed")
        self.enabled_chromevox = False

    def evaluate(self, js):
        return json.loads(self.cdp.desktop_evaluate(js))

    def scan(self):
        return summarize_auth_views(self.evaluate(SCAN_JS))

    def do(self, name, role, action):
        return self.evaluate(_action_js(role, name, action)).get("found", False)

    def wait_for(self, predicate, timeout):
        deadline = self.clock() + timeout
        snapshot = self.scan()
        while not predicate(snapshot) and self.clock() < deadline:
            self.sleep(0.25)
            snapshot = self.scan()
        return snapshot


# === Login flow ===

def _validate_request(request):
    account = str(request.get("account") or "").strip().lower()
    if account and not EMAIL_RE.match(account):
        raise LoginError("bad-request", "account must be an email address")
    pin = request.get("pin")
    if not isinstance(pin, str) or not PIN_RE.match(pin):
        raise LoginError("bad-request", "PIN must contain 4-20 digits")
    timeout = request.get("timeout", 20)
    if not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
        raise LoginError("bad-request", "timeout must be 1-120 seconds")
    return account, pin, timeout


def login(request, *, cdp, press, type_keys, state_fn=session_state,
          local_state_fn=load_local_state, sleep=time.sleep, clock=time.monotonic):
    """Sign in or unlock one account with a PIN. Returns a result dict.

    ``press`` presses one key combination; ``type_keys`` taps keys in order.
    """
    started = clock()
    account, pin, timeout = _validate_request(request)
    steps = []
    before = state_fn()
    active = before["active_users"]

    if before["screen"] != "signin":
        if account and account not in active:
            raise LoginError("other-user-active", f"another account is signed in ({', '.join(active)})")
        account = account or active[0]
        if before["screen"] == "active":
            return {"ok": True, "result": "already-active", "account": account, "typed": False, "steps": steps}
        mode = "unlock"
    else:
        mode = "signin"

    local_state = local_state_fn()
    if not account:
        account = str(local_state.get("LastActiveUser") or "").lower()
        if not account:
            raise LoginError("bad-request", "no account given and no last-used account recorded")
    requirements = account_requirements(local_state, account)
    if not requirements["pin_configured"]:
        raise LoginError("pin-unavailable", f"{account} has no PIN configured")
    if mode == "signin" and requirements["online_reauth_required"]:
        raise LoginError("online-reauth", f"{account} must complete an online Google sign-in")
    length = requirements["autosubmit_length"]
    if length is not None and length != len(pin):
        raise LoginError("pin-length-mismatch", "the stored PIN length does not match this account's PIN")

    target_profile = keyboard_profile(known_user(local_state, account))
    if mode == "signin":
        # The sign-in screen applies the focused account's keyboard settings.
        # It is normally the last-used account, but someone may have selected
        # another one, so every account's distinct shortcut is a fallback.
        candidates = [keyboard_profile(known_user(local_state, local_state.get("LastActiveUser"))),
                      target_profile]
        candidates += [keyboard_profile(u) for u in local_state.get("KnownUsers", []) or []]
        candidates.append(keyboard_profile(None))
    else:
        candidates = [target_profile]

    press([KEY_LEFTSHIFT])  # A modifier-only key wakes the display without typing.
    sleep(0.5)
    host = AutomationHost(cdp, press, sleep=sleep, clock=clock)
    focused_profile = host.open(candidates) or target_profile
    steps.append("chromevox-enabled" if host.enabled_chromevox else "automation-host-found")
    try:
        snapshot = host.wait_for(lambda s: s["selected_account"] is not None, 5)
        if snapshot["selected_account"] is None:
            raise LoginError("no-auth-ui", "no PIN or password field is visible")
        if snapshot["selected_account"] != account:
            if mode == "unlock":
                raise LoginError("wrong-account", f"the lock screen shows {snapshot['selected_account']}")
            if account not in snapshot["accounts"]:
                raise LoginError("account-not-listed", f"{account} is not listed on the sign-in screen")
            host.do(account, "button", "doDefault")
            focused_profile = target_profile
            snapshot = host.wait_for(lambda s: s["selected_account"] == account, 5)
            if snapshot["selected_account"] != account:
                raise LoginError("selection-failed", f"could not select {account}")
            steps.append("account-selected")
        steps.append("account-confirmed")
        if snapshot["auth_mode"] == "password":
            if not snapshot["switch_to_pin"]:
                raise LoginError("pin-unavailable", "only password entry is offered for this account")
            host.do(SWITCH_TO_PIN, "button", "doDefault")
            snapshot = host.wait_for(lambda s: s["auth_mode"] == "pin", 5)
            if snapshot["auth_mode"] != "pin":
                raise LoginError("pin-unavailable", "could not switch to PIN entry")
            steps.append("switched-to-pin")
        if not snapshot["pin_focused"]:
            host.do(PIN_FIELD_NAME, "textField", "focus")
            snapshot = host.wait_for(lambda s: s["pin_focused"], 3)
            if not snapshot["pin_focused"]:
                raise LoginError("focus-failed", "the PIN field could not be focused")
        steps.append("pin-field-focused")
    except BaseException:
        try:
            host.close(focused_profile)
        except LoginError:
            pass  # Report the original failure; nothing has been typed.
        raise
    was_enabled = host.enabled_chromevox
    host.close(focused_profile)
    if was_enabled:
        steps.append("chromevox-disabled")

    # One attempt: clear any partial entry, type the PIN, and submit. With
    # auto-submit, ChromeOS submits on the last digit and Enter is not sent.
    keys = [KEY_BACKSPACE] * (len(pin) + 2) + [DIGIT_KEYCODES[d] for d in pin]
    if length is None:
        keys.append(KEY_ENTER)
    type_keys(keys)
    steps.append("pin-submitted")

    deadline = clock() + timeout
    while clock() < deadline:
        state = state_fn()
        if account in state["active_users"] and not state["locked"]:
            return {
                "ok": True,
                "result": "signed-in" if mode == "signin" else "unlocked",
                "account": account,
                "typed": True,
                "steps": steps,
                "elapsed_s": round(clock() - started, 1),
            }
        sleep(0.5)
    raise LoginError(
        "not-confirmed",
        f"{account} was not confirmed {'signed in' if mode == 'signin' else 'unlocked'} "
        f"after {timeout}s; no retry was attempted",
        typed=True,
    )


def login_status(request, *, state_fn=session_state, local_state_fn=load_local_state):
    """Report screen state and the account's recorded sign-in requirements."""
    state = state_fn()
    result = {"ok": True, **state}
    try:
        local_state = local_state_fn()
    except (OSError, ValueError):
        return result
    result["last_active_user"] = str(local_state.get("LastActiveUser") or "").lower() or None
    account = str(request.get("account") or "").strip().lower()
    if account:
        try:
            req = account_requirements(local_state, account)
            result["account"] = {
                "email": account,
                "known": True,
                "pin_configured": req["pin_configured"],
                "online_reauth_required": req["online_reauth_required"],
            }
        except LoginError:
            result["account"] = {"email": account, "known": False}
    return result


def error_result(error):
    return {"error": str(error), "code": error.code, "typed": error.typed}
