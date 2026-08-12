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
DOCTOR = REPO_DIR / "scripts" / "doctor.sh"
DIAGNOSTICS = REPO_DIR / "scripts" / "diagnostics.sh"
BASH = shutil.which("bash")


@unittest.skipIf(BASH is None, "doctor SSH fixture requires Bash")
@unittest.skipIf(os.name == "nt", "doctor SSH fixture requires POSIX execution")
class PassiveDoctorTests(unittest.TestCase):
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
            invocations = log.read_text(encoding="utf-8")
            self.assertNotIn("adb devices", invocations)
            self.assertNotIn("adb connect", invocations)

    def test_diagnostics_never_invokes_explicit_adb_probe(self):
        source = DIAGNOSTICS.read_text(encoding="utf-8")

        self.assertNotIn('"$CLI" --json adb-status', source)
        self.assertNotIn("adb devices", source)
        self.assertIn("authorization=not_probed", source)


if __name__ == "__main__":
    unittest.main()
