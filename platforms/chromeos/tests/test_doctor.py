import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]
CLI = REPO_DIR / "bin" / "chromeos"
DOCTOR = REPO_DIR / "scripts" / "doctor.sh"
DIAGNOSTICS = REPO_DIR / "scripts" / "diagnostics.sh"
BASH = shutil.which("bash")


@unittest.skipIf(BASH is None, "doctor SSH fixture requires Bash")
@unittest.skipIf(os.name == "nt", "doctor SSH fixture requires POSIX execution")
class PassiveDoctorTests(unittest.TestCase):
    def test_restore_power_requires_explicit_unavailable_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory)
            log = fake_bin / "ssh.log"
            fake_ssh = fake_bin / "ssh"
            fake_ssh.write_text(textwrap.dedent("""\
                #!/bin/sh
                printf '%s\n' "$*" >> "$FAKE_SSH_LOG"
            """), encoding="utf-8")
            fake_ssh.chmod(fake_ssh.stat().st_mode | stat.S_IXUSR)
            environment = os.environ.copy()
            environment.update({
                "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                "CHROMEBOOK_HOST": "fake-chromebook",
                "FAKE_SSH_LOG": str(log),
            })

            refused = subprocess.run(
                [BASH, str(CLI), "restore-power"],
                cwd=REPO_DIR,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(2, refused.returncode)
            self.assertIn("Always-awake is the required baseline", refused.stderr)
            self.assertFalse(log.exists())

            accepted = subprocess.run(
                [
                    BASH,
                    str(CLI),
                    "restore-power",
                    "--confirm-make-unavailable",
                ],
                cwd=REPO_DIR,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, accepted.returncode, accepted.stderr)
            invocation = log.read_text(encoding="utf-8")
            self.assertIn("chromeos-testbed-power-policy.override", invocation)
            self.assertIn("ectool forcelidopen 0", invocation)

    def test_power_status_distinguishes_configured_from_effective_lid_action(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory)
            fake_ssh = fake_bin / "ssh"
            fake_ssh.write_text(textwrap.dedent("""\
                #!/bin/sh
                printf '%s\n' \
                    'use_lid\t0\toverride' \
                    'disable_idle_suspend\t1\toverride' \
                    'power_policy_helper\tyes\tstate' \
                    'current_boot_applied\tyes\tstate' \
                    'ac_connected\t1\tstatus' \
                    'policy\tUpdated settings: idle=8m (no-op) lid_closed=suspend\tlog'
            """), encoding="utf-8")
            fake_ssh.chmod(fake_ssh.stat().st_mode | stat.S_IXUSR)
            environment = os.environ.copy()
            environment["PATH"] = (
                f"{fake_bin}{os.pathsep}{environment['PATH']}"
            )

            result = subprocess.run(
                [BASH, str(CLI), "--json", "power-status"],
                cwd=REPO_DIR,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["current_lid_action"], "suspend")
            self.assertEqual(payload["effective_lid_action"], "ignored")
            self.assertTrue(payload["closed_lid_ready"])

    def test_doctor_never_starts_or_queries_adb(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory)
            log = fake_bin / "ssh.log"
            fake_ssh = fake_bin / "ssh"
            fake_ssh.write_text(textwrap.dedent("""\
                #!/bin/sh
                printf '%s\n' "$*" >> "$FAKE_SSH_LOG"
                case "$*" in
                    *"adb devices"*|*"adb connect"*) exit 97 ;;
                    *"echo ok"*) printf 'ok\n' ;;
                    *"update_engine_client"*) printf 'UPDATE_STATUS_IDLE\n' ;;
                    *"start_sshd.sh"*) printf 'yes\n' ;;
                    *"status openssh-server"*) printf 'running\n' ;;
                    *"cryptohome --action=is_mounted"*) printf 'true\n' ;;
                    *"chromeos-testbed-probe"*) printf 'yes\n' ;;
                    *"apply_power_policy.sh"*"power-policy.log"*)
                        printf 'ready\n' ;;
                    *"cat /etc/chrome_dev.conf"*)
                        printf '%s\n' '--remote-debugging-port=9222' ;;
                    *"cat /proc/net/tcp"*)
                        printf '0: 00000000:2406 00000000:0000 0A\n' ;;
                    *"command -v python3"*) printf '/usr/bin/python3\n' ;;
                    *"test -f"*) printf 'yes\n' ;;
                    *"LD_LIBRARY_PATH="*)
                        printf '{"touch_max":[100,100],"keyboard":{"layout":"qwerty"}}\n' ;;
                    *"command -v adb"*) printf '/usr/bin/adb\n' ;;
                esac
            """), encoding="utf-8")
            fake_ssh.chmod(fake_ssh.stat().st_mode | stat.S_IXUSR)
            environment = os.environ.copy()
            environment.update({
                "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                "CHROMEBOOK_HOST": "fake-chromebook",
                "CHROMEOS_OUTPUT": "json",
                "FAKE_SSH_LOG": str(log),
            })

            result = subprocess.run(
                [BASH, str(DOCTOR)],
                cwd=REPO_DIR,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn(
                "ARCVM ADB was not probed (optional)",
                [check["name"] for check in payload["checks"]],
            )
            self.assertIn(
                "Closed-lid availability policy is active for the current boot",
                [check["name"] for check in payload["checks"]],
            )
            invocations = log.read_text(encoding="utf-8")
            self.assertNotIn("adb devices", invocations)
            self.assertNotIn("adb connect", invocations)

    def test_bootstrap_installs_and_reapplies_required_power_policy(self):
        source = (REPO_DIR / "scripts" / "bootstrap.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("apply_power_policy.sh", source)
        self.assertIn("disable_idle_suspend", source)
        self.assertIn("use_lid", source)
        self.assertIn("ectool forcelidopen 1", source)
        self.assertIn('bash "$POWER_POLICY" upstart', source)
        self.assertIn("chromeos-testbed-power-policy.conf", source)
        self.assertIn("start on started powerd", source)
        self.assertIn('bash "$POWER_POLICY" powerd-started', source)

    def test_diagnostics_never_invokes_explicit_adb_probe(self):
        source = DIAGNOSTICS.read_text(encoding="utf-8")

        self.assertNotIn('"$CLI" --json adb-status', source)
        self.assertNotIn("adb devices", source)
        self.assertIn("authorization=not_probed", source)


if __name__ == "__main__":
    unittest.main()
