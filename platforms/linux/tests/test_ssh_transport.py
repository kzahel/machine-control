import importlib.util
import base64
import io
import os
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "ssh_transport", Path(__file__).resolve().parents[1] / "scripts/ssh-transport.py")
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class SshTransportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ("key", "hosts"):
            (self.root / name).touch()
        env = {"LINUXVM_SSH_ADDRESS": "192.0.2.10",
               "LINUXVM_EXPECTED_UUID": "00000000-0000-0000-0000-000000000001",
               "LINUXVM_DESKTOP_USER": "appliance",
               "LINUXVM_SETUP_SSH_KEY_FILE": str(self.root / "key"),
               "LINUXVM_SETUP_SSH_KNOWN_HOSTS_FILE": str(self.root / "hosts")}
        self.environment = patch.dict(os.environ, env)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_exact_host_alias_survives_address_change_and_never_accepts_new_keys(self):
        original = transport.connection()
        with patch.dict(os.environ, {"LINUXVM_SSH_ADDRESS": "192.0.2.11"}):
            changed = transport.connection()
        self.assertEqual(original[:-1], changed[:-1])
        self.assertIn("StrictHostKeyChecking=yes", changed)
        self.assertIn("HostKeyAlias=00000000-0000-0000-0000-000000000001", changed)
        self.assertIn("IdentityAgent=none", changed)

    def test_arguments_and_transfer_paths_are_literal_remote_words(self):
        dangerous = "a'; $(touch /tmp/never) `id`"
        with patch.object(transport.subprocess, "call", return_value=0) as call:
            transport.run(["exec", "/usr/bin/printf", "%s", dangerous])
        self.assertEqual(shlex.split(call.call_args.args[0][-1]),
                         ["sudo", "-n", "--", "/usr/bin/printf", "%s", dangerous])
        source = self.root / "source"
        source.write_bytes(b"private fixture contents")
        with patch.object(transport.subprocess, "call", return_value=0) as call:
            transport.run(["push", str(source), dangerous])
        command = call.call_args.args[0][-1]
        self.assertEqual(shlex.split(command.removesuffix(" >/dev/null")),
                         ["sudo", "-n", "--", "/usr/bin/tee", "--", dangerous])
        self.assertNotIn("private fixture contents", command)

    def test_invalid_binding_refuses_before_starting_ssh(self):
        for key, value in (("LINUXVM_EXPECTED_UUID", "unknown"),
                           ("LINUXVM_SSH_ADDRESS", "example.test"),
                           ("LINUXVM_DESKTOP_USER", "-oProxyCommand=id")):
            with patch.dict(os.environ, {key: value}), \
                    patch.object(transport.subprocess, "call") as call:
                with self.assertRaises(ValueError):
                    transport.run(["exec", "/usr/bin/id"])
                call.assert_not_called()

    def test_pin_validates_public_key_before_atomic_replacement(self):
        hosts = self.root / "hosts"
        hosts.write_text("previous binding\n")
        with patch.object(transport.sys, "stdin", io.StringIO("ssh-ed25519 INVALID\n")):
            with self.assertRaises(transport.subprocess.CalledProcessError):
                transport.pin_host()
        self.assertEqual(hosts.read_text(), "previous binding\n")
        raw = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + bytes(32)
        public_key = "ssh-ed25519 " + base64.b64encode(raw).decode() + " fixture\n"
        with patch.object(transport.sys, "stdin", io.StringIO(public_key)), \
                patch.object(transport.sys, "stdout", io.StringIO()):
            transport.pin_host()
        self.assertEqual(hosts.stat().st_mode & 0o777, 0o600)
        self.assertEqual([line.split()[0] for line in hosts.read_text().splitlines()],
                         ["00000000-0000-0000-0000-000000000001", "192.0.2.10"])
        self.assertEqual(list(self.root.glob(".host-key-*")), [])
