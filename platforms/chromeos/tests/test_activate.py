"""Execute activation against an isolated filesystem and fake OS services."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SOURCE = (SCRIPTS / "activate.sh").read_text()
FAKE = r'''#!/bin/bash
name=${0##*/}
printf '%s %s\n' "$name" "$*" >> "$FIXTURE_ROOT/calls"
case "$name" in
  id) echo 0 ;;
  crossystem) echo 1 ;;
  rootdev) echo "${FIXTURE_DEVICE:-/dev/mmcblk0p5}" ;;
  update_engine_client) echo "CURRENT_OP=${FIXTURE_UPDATE:-UPDATE_STATUS_IDLE}" ;;
  make_dev_fixture) exit "${FIXTURE_SIGNING_STATUS:-0}" ;;
  flock) exit "${FIXTURE_LOCK_STATUS:-0}" ;;
  touch)
    if [[ "$*" == *testbed-probe* && "$FIXTURE_WRITABLE" != yes ]]; then exit 1; fi
    exec /usr/bin/touch "$@" ;;
  ip) echo '2: wlan0 inet 192.0.2.2/24' ;;
  ssh-keyscan) echo '[localhost]:2223 ssh-ed25519 fixture' ;;
  status) echo "$1 start/running" ;;
  iptables|ip6tables) [[ " $* " != *' -D '* ]] ;;
  python3|dev_install) exit "${FIXTURE_PYTHON_STATUS:-0}" ;;
  restart)
    if [ "$1" = ui ]; then echo '0: 0100007F:2406 0:0 0A' > "$FIXTURE_ROOT/proc/net/tcp"; fi ;;
  sleep) exit "${FIXTURE_SLEEP_STATUS:-0}" ;;
esac
'''


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "Requires Bash")
class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ssh = self.root / "mnt/stateful_partition/etc/ssh"
        for directory in [self.ssh / "root_ssh", self.root / "etc/init",
                          self.root / "proc/net", self.root / "bin", self.root / "run"]:
            directory.mkdir(parents=True)
        (self.ssh / "root_ssh/authorized_keys").write_text("ssh-ed25519 fixture\n")
        for name in ["ssh_host_ed25519_key", "ssh_host_rsa_key"]:
            (self.ssh / name).write_text("fixture\n")
        (self.root / "etc/lsb-release").write_text(
            "CHROMEOS_RELEASE_NAME=Chrome OS\nCHROMEOS_RELEASE_VERSION=fixture-release\n")
        (self.root / "proc/net/tcp").write_text("")
        source = re.sub(r"(?<![\w/])/(mnt/stateful_partition|etc|var|proc|run)(?=/)",
                        lambda m: f"{self.root}/{m[1]}", SOURCE)
        source = source.replace("/usr/sbin/sshd", "sshd")
        source = source.replace("/usr/share/vboot/bin/make_dev_ssd.sh", "make_dev_fixture")
        source = re.sub(r"^(export )?PATH=.*$", 'export PATH="$FIXTURE_BIN:$PATH"', source, flags=re.M)
        self.script = self.root / "activate.sh"
        self.script.write_text(source)
        for name in ["id", "crossystem", "rootdev", "update_engine_client", "make_dev_fixture",
                     "touch", "ip", "ss", "ssh-keyscan", "sshd", "status", "iptables",
                     "ip6tables", "python3", "dev_install", "restart", "start", "stop",
                     "initctl", "ectool", "pkill", "sleep", "sync", "reboot", "flock"]:
            executable = self.root / "bin" / name
            executable.write_text(FAKE)
            executable.chmod(0o755)

    def run_activation(self, *args, writable="no", input_text="", **overrides):
        env = dict(os.environ, FIXTURE_ROOT=str(self.root), FIXTURE_BIN=str(self.root / "bin"),
                   PATH=str(self.root / "bin") + os.pathsep + os.environ["PATH"],
                   FIXTURE_WRITABLE=writable, CHROMEOS_TESTBED_CONTROLLER_PUBKEY="",
                   CHROMEOS_TESTBED_REPORT_URL="", **overrides)
        # User shell hooks are unrelated to this simulated ChromeOS environment.
        env.pop("BASH_ENV", None)
        env.pop("ENV", None)
        return subprocess.run(["bash", str(self.script), *args], env=env, input=input_text,
                              text=True, capture_output=True, timeout=15)

    def calls(self):
        return (self.root / "calls").read_text()

    def assert_minimal(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SETUP: SSH-only", result.stdout)
        for forbidden in ["make_dev_fixture", "reboot", "ectool", "dev_install", "restart ui"]:
            self.assertNotIn(forbidden, self.calls())
        self.assertFalse((self.root / "etc/init/openssh-server.conf").exists())
        self.assertFalse((self.root / "etc/chrome_dev.conf").exists())
        self.assertFalse((self.ssh / "prepared-release").exists())
        self.assertTrue((self.ssh / "activate.sh").exists())
        self.assertTrue((self.ssh / "start_sshd.sh").exists())

    def test_explicit_minimal_overrides_saved_full_approval(self):
        (self.ssh / "setup-approved").write_text("dedicated-appliance-v1\n")
        self.assert_minimal(self.run_activation("--ssh-only", "--yes"))

    def test_declining_full_activation_still_starts_minimal_ssh(self):
        self.assert_minimal(self.run_activation(input_text="n\n"))
        self.assertFalse((self.ssh / "setup-approved").exists())

    def test_eof_does_not_grant_any_activation(self):
        result = self.run_activation()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("sshd ", self.calls())
        self.assertFalse((self.ssh / "setup-approved").exists())

    def test_full_activation_saves_resume_and_reboots_then_finishes(self):
        result = self.run_activation("--yes")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("make_dev_fixture --remove_rootfs_verification --partitions 4", self.calls())
        self.assertIn("reboot ", self.calls())
        self.assertIn("SAME activation command", result.stdout)
        self.assertEqual((self.ssh / "setup-state").read_text().strip(), "awaiting-rootfs-reboot")
        self.assertFalse((self.ssh / "prepared-release").exists())
        # Same command, saved approval; the new writable image needs no prompt.
        (self.root / "calls").write_text("")
        result = self.run_activation(writable="yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("make_dev_fixture", self.calls())
        self.assertNotIn("reboot ", self.calls())
        self.assertIn("restart ui", self.calls())
        self.assertTrue((self.root / "etc/init/openssh-server.conf").exists())
        self.assertEqual((self.ssh / "prepared-release").read_text().strip(), "fixture-release")
        self.assertFalse((self.ssh / "setup-approved").exists())
        (self.root / "calls").write_text("")
        result = self.run_activation("--yes", writable="yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("restart ui", self.calls())
        self.assertNotIn("reboot ", self.calls())

    def test_failed_preparation_never_reboots(self):
        for overrides in [{"FIXTURE_SIGNING_STATUS": "1"}, {"FIXTURE_DEVICE": "/dev/dm-0"},
                          {"FIXTURE_PYTHON_STATUS": "1"}]:
            with self.subTest(overrides=overrides):
                result = self.run_activation("--yes", **overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("reboot ", self.calls())
                self.assertFalse((self.ssh / "prepared-release").exists())

    def test_cancelled_countdown_does_not_reboot(self):
        result = self.run_activation("--yes", FIXTURE_SLEEP_STATUS="1")
        self.assertEqual(result.returncode, 130, result.stdout + result.stderr)
        self.assertNotIn("reboot ", self.calls())
        self.assertTrue((self.ssh / "setup-approved").exists())

    def test_pending_update_is_booted_before_kernel_change(self):
        result = self.run_activation("--yes", FIXTURE_UPDATE="UPDATE_STATUS_UPDATED_NEED_REBOOT")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("make_dev_fixture", self.calls())
        self.assertEqual((self.ssh / "setup-state").read_text().strip(), "awaiting-update-reboot")

    def test_incompatible_modes_fail_before_mutation(self):
        result = self.run_activation("--ssh-only", "--repair-only")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "calls").exists())

    def test_busy_activation_does_not_start_a_second_mutating_run(self):
        result = self.run_activation("--yes", FIXTURE_LOCK_STATUS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Another activation is still running", result.stderr)
        self.assertNotIn("sshd ", self.calls())
        self.assertNotIn("make_dev_fixture", self.calls())
        self.assertFalse((self.ssh / "setup-approved").exists())


class CompatibilityTests(unittest.TestCase):
    @unittest.skipIf(not shutil.which("bash"), "Requires Bash")
    def test_legacy_entry_uses_local_activation_and_preserves_arguments(self):
        result = subprocess.run(["bash", str(SCRIPTS / "bootstrap.sh"), "--help"],
                                capture_output=True, text=True, check=True)
        self.assertIn("Usage: bash activate.sh", result.stdout)
        self.assertIn("--ssh-only", result.stdout)
