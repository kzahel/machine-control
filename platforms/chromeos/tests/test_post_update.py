import json
import os
from pathlib import Path
import stat
import shutil
import subprocess
import tempfile
import textwrap
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]
CLI = REPO_DIR / "bin" / "chromeos"
BASH = shutil.which("bash")


@unittest.skipIf(BASH is None, "post-update audit tests require Bash")
class PostUpdateAuditTests(unittest.TestCase):
    def run_audit(self, snapshot, ssh_up=True):
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory)
            fake_ssh = fake_bin / "ssh"
            fake_ssh.write_text(textwrap.dedent("""\
                #!/bin/sh
                if [ "${FAKE_SSH_UP:-yes}" != yes ]; then
                    exit 255
                fi
                case "$*" in
                    *"echo ok"*) printf 'ok\\n' ;;
                    *) printf '%s\\n' "$FAKE_SNAPSHOT" ;;
                esac
            """))
            fake_ssh.chmod(fake_ssh.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env.update({
                "PATH": f"{fake_bin}:{env['PATH']}",
                "CHROMEBOOK_HOST": "fake-chromebook",
                "FAKE_SSH_UP": "yes" if ssh_up else "no",
                "FAKE_SNAPSHOT": textwrap.dedent(snapshot).strip(),
            })
            return subprocess.run(
                [BASH, str(CLI), "--json", "post-update"],
                cwd=REPO_DIR,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_ready_image_is_reboot_proven(self):
        result = self.run_audit("""
            release\t16700.60.0
            boot_id\tnew-boot
            update_operation\tUPDATE_STATUS_IDLE
            rootfs_writable\tyes
            autostart\trunning
            fallback\tyes
            prepared_release\t16700.60.0
            boot_evidence\tautomatic
            devtools_configured\tyes
            devtools_listening\tyes
            repair_staged\tno
        """)

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual("ready", payload["status"])

    def test_updated_read_only_image_requires_repair(self):
        result = self.run_audit("""
            release\t16700.60.0
            boot_id\tupdated-boot
            update_operation\tUPDATE_STATUS_IDLE
            rootfs_writable\tno
            autostart\tmissing
            fallback\tyes
            prepared_release\tmissing
            boot_evidence\tnone
            devtools_configured\tno
            devtools_listening\tno
            repair_staged\tno
        """)

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("repair_required", payload["status"])
        failed = {item["name"] for item in payload["checks"]
                  if item["status"] == "fail"}
        self.assertIn("SSH autostart job is missing", failed)
        self.assertIn("Rootfs verification is enabled", failed)

    def test_pending_update_is_not_reported_ready(self):
        result = self.run_audit("""
            release\t16700.46.0
            boot_id\told-boot
            update_operation\tUPDATE_STATUS_UPDATED_NEED_REBOOT
            rootfs_writable\tyes
            autostart\trunning
            fallback\tyes
            prepared_release\t16700.46.0
            boot_evidence\tautomatic
            devtools_configured\tyes
            devtools_listening\tyes
            repair_staged\tno
        """)

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("update_pending", payload["status"])

    def test_unreachable_ssh_has_actionable_json(self):
        result = self.run_audit("", ssh_up=False)

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("ssh_unreachable", payload["status"])

    def test_mutating_mode_rejects_structured_output(self):
        result = subprocess.run(
            [BASH, str(CLI), "--json", "post-update", "--repair"],
            cwd=REPO_DIR,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("read-only post-update audit", result.stderr)


if __name__ == "__main__":
    unittest.main()
