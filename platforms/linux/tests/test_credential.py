import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import types
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "scripts/credential.py"
SPEC = importlib.util.spec_from_file_location("linux_credential", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
IDENTIFIER = "00000000-0000-0000-0000-000000000000"


@unittest.skipUnless(os.name == "posix", "Linux credential checks require POSIX ownership and no-follow opens")
class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.secret = self.root / "password"
        self.secret.write_bytes(b"fixture-secret\n")
        self.secret.chmod(0o600)
        self.key = self.root / "setup-key"
        self.key.touch()
        self.hosts = self.root / "known-hosts"
        self.hosts.touch()
        environment = {
            "LINUXVM_EXPECTED_UUID": IDENTIFIER,
            "LINUXVM_PROVIDER": "libvirt-linux",
            "LINUXVM_DESKTOP_USER": "appliance",
            "LINUXVM_CREDENTIAL_PROFILE": "password",
            "LINUXVM_LOGIN_SECRET_FILE": str(self.secret),
            "LINUXVM_SETUP_SSH_KEY_FILE": str(self.key),
            "LINUXVM_SETUP_SSH_KNOWN_HOSTS_FILE": str(self.hosts),
            "LINUXVM_CREDENTIAL_STATE_DIR": str(self.root / "receipts"),
        }
        patch = mock.patch.dict(os.environ, environment)
        patch.start()
        self.addCleanup(patch.stop)
        self.commands = []
        self.inputs = []

    def command(self, *args, input_bytes=None):
        self.commands.append(args)
        if args[0] == "ssh":
            self.inputs.append(input_bytes)
            return "verified"
        if "target-id" in args:
            return IDENTIFIER
        if "getent" in " ".join(args):
            return "appliance:x:1000:1000::/home/appliance:/bin/bash"
        if "ip" in args:
            return "192.0.2.10"
        if "/etc/ssh/ssh_host_ed25519_key.pub" in args:
            return "ssh-ed25519 AAAA fixture"
        if args[0] == "ssh-keygen":
            return "192.0.2.10 ssh-ed25519 AAAA"
        if "password-free" in args:
            return "verified"
        raise AssertionError(args)

    def inspect(self, operation):
        with mock.patch.object(MODULE, "command", side_effect=self.command):
            return MODULE.inspect(operation)

    def test_password_only_travels_on_pinned_ssh_stdin(self):
        result = self.inspect("verify")
        self.assertTrue(result["ready"])
        self.assertEqual(self.inputs, [b"fixture-secret\n"])
        self.assertNotIn("fixture-secret", str(self.commands))
        self.assertNotIn("fixture-secret", json.dumps(result))
        ssh = next(args for args in self.commands if args[0] == "ssh")
        self.assertIn("StrictHostKeyChecking=yes", ssh)
        self.assertIn("HostKeyAlgorithms=ssh-ed25519", ssh)
        self.assertIn("IdentityAgent=none", ssh)
        self.assertNotIn("StrictHostKeyChecking=no", ssh)
        receipt = next((self.root / "receipts").glob("*.json"))
        self.assertEqual(stat.S_IMODE(receipt.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(receipt.parent.stat().st_mode), 0o700)
        self.assertNotIn("fixture-secret", receipt.read_text())

    def test_metadata_alone_never_qualifies_and_status_does_not_read_secret(self):
        with mock.patch.object(MODULE.os, "read", side_effect=AssertionError("secret read")):
            self.assertFalse(self.inspect("status")["ready"])
        self.inspect("verify")
        with mock.patch.object(MODULE.os, "read", side_effect=AssertionError("secret read")):
            self.assertTrue(self.inspect("status")["ready"])

    def test_missing_locator_and_wrong_identity_refuse_before_secret_read(self):
        for change in ({"LINUXVM_LOGIN_SECRET_FILE": ""},
                       {"LINUXVM_EXPECTED_UUID": "11111111-1111-1111-1111-111111111111"}):
            with self.subTest(change=change), mock.patch.dict(os.environ, change), \
                 mock.patch.object(MODULE.os, "read", side_effect=AssertionError("secret read")):
                with self.assertRaises(MODULE.Refusal):
                    self.inspect("verify")

    def test_wrong_permissions_and_symlink_refuse(self):
        self.secret.chmod(0o644)
        with self.assertRaisesRegex(MODULE.Refusal, "file_invalid"):
            self.inspect("verify")
        self.secret.chmod(0o600)
        link = self.root / "link"
        link.symlink_to(self.secret)
        with mock.patch.dict(os.environ, {"LINUXVM_LOGIN_SECRET_FILE": str(link)}):
            with self.assertRaisesRegex(MODULE.Refusal, "file_unavailable"):
                self.inspect("verify")

    def test_host_key_mismatch_refuses_before_reading_password(self):
        original = self.command

        def mismatched(*args, **kwargs):
            if args[0] == "ssh-keygen":
                return "192.0.2.10 ssh-ed25519 BBBB"
            return original(*args, **kwargs)

        with mock.patch.object(MODULE, "command", side_effect=mismatched), \
             mock.patch.object(MODULE.os, "read", side_effect=AssertionError("secret read")):
            with self.assertRaisesRegex(MODULE.Refusal, "host_key_unverified"):
                MODULE.inspect("verify")

    def test_missing_setup_route_refuses_before_reading_password(self):
        with mock.patch.dict(os.environ, {"LINUXVM_SETUP_SSH_KEY_FILE": ""}), \
             mock.patch.object(MODULE.os, "read", side_effect=AssertionError("secret read")):
            with self.assertRaisesRegex(MODULE.Refusal, "ssh_configuration_required"):
                self.inspect("verify")

    def test_failed_verification_invalidates_previous_receipt(self):
        self.inspect("verify")
        original = self.command

        def failed(*args, **kwargs):
            if args[0] == "ssh":
                raise MODULE.Refusal("guest_verification_failed")
            return original(*args, **kwargs)

        with mock.patch.object(MODULE, "command", side_effect=failed):
            with self.assertRaisesRegex(MODULE.Refusal, "guest_verification_failed"):
                MODULE.inspect("verify")
        self.assertFalse(self.inspect("status")["ready"])

    def test_rotation_account_provider_and_expiry_invalidate_receipt(self):
        self.inspect("verify")
        for change in ({"LINUXVM_DESKTOP_USER": "other"},
                       {"LINUXVM_PROVIDER": "utm-macos"},
                       {"LINUXVM_CREDENTIAL_PROFILE": "password-free"}):
            with self.subTest(change=change), mock.patch.dict(os.environ, change):
                self.assertFalse(self.inspect("status")["ready"])
        with mock.patch.object(MODULE.time, "time", return_value=time.time() + MODULE.MAX_AGE + 1):
            self.assertFalse(self.inspect("status")["ready"])
        self.secret.write_bytes(b"rotated-fixture\n")
        self.assertFalse(self.inspect("status")["ready"])

    def test_explicit_password_free_requires_guest_verification(self):
        with mock.patch.dict(os.environ, {"LINUXVM_CREDENTIAL_PROFILE": "password-free",
                                         "LINUXVM_LOGIN_SECRET_FILE": ""}), \
             mock.patch.object(MODULE.os, "read", side_effect=AssertionError("secret read")):
            self.assertFalse(self.inspect("status")["ready"])
            result = self.inspect("verify")
            self.assertTrue(result["ready"])
            self.assertEqual(result["evidence"], "explicit_locked_password_profile_verified")
            self.assertTrue(self.inspect("status")["ready"])
        self.assertFalse(self.inputs)

    def test_guest_verifier_rejects_locked_mismatched_and_expired_passwords(self):
        today = int(time.time() // 86400)
        cases = [
            ("password", "$fixture$hash", b"correct", -1, today - 1, 90, True),
            ("password", "$fixture$hash", b"correct\n", -1, today - 1, 90, True),
            ("password", "$fixture$hash", b"wrong", -1, today - 1, 90, False),
            ("password", "!", b"correct", -1, today - 1, 90, False),
            ("password", "$fixture$hash", b"correct", today, today - 1, 90, False),
            ("password", "$fixture$hash", b"correct", -1, 0, 90, False),
            ("password", "$fixture$hash", b"correct", -1, today - 90, 90, False),
            ("password-free", "!", b"", -1, today - 1, 90, True),
            ("password-free", "$fixture$hash", b"", -1, today - 1, 90, False),
        ]
        for profile, stored, password, expiry, changed, maximum, valid in cases:
            entry = types.SimpleNamespace(sp_pwdp=stored, sp_expire=expiry,
                                          sp_lstchg=changed, sp_max=maximum)
            library = types.SimpleNamespace(crypt=mock.Mock(side_effect=lambda p, _s:
                b"$fixture$hash" if p == b"correct" else b"$fixture$mismatch"))
            output = io.StringIO()
            with self.subTest(profile=profile, stored=stored, password=password, expiry=expiry,
                              changed=changed), \
                 mock.patch.dict(sys.modules, {"spwd": types.SimpleNamespace(
                     getspnam=lambda _user: entry)}), \
                 mock.patch("ctypes.CDLL", return_value=library), \
                 mock.patch.object(sys, "argv", ["verify", "appliance", profile]), \
                 mock.patch.object(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO(password))), \
                 contextlib.redirect_stdout(output):
                if valid:
                    exec(MODULE.VERIFY_SCRIPT, {})
                    self.assertEqual(output.getvalue(), "verified\n")
                else:
                    with self.assertRaises(SystemExit) as failure:
                        exec(MODULE.VERIFY_SCRIPT, {})
                    self.assertEqual(failure.exception.code, 1)
                    self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
