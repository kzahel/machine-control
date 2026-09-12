"""Validate explicit adapter endpoint selection without contacting a target."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which('bash')
if os.name == 'nt':
    # System32/bash.exe is a WSL launcher, not the Git Bash interpreter used
    # by the Windows runner. Select Git's interpreter explicitly.
    git = Path(shutil.which('git') or 'git')
    BASH = next((str(path) for path in (
        git.parent / 'bash.exe', git.parent.parent / 'bin/bash.exe',
        Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/bin/bash.exe',
    ) if path.is_file()), None)


@unittest.skipUnless(BASH, 'Git/POSIX Bash adapter required')
class WindowsProfileTests(unittest.TestCase):
    def render(self, profile='appliance', instance='default', session=''):
        return subprocess.run([BASH, '-c', 'source platforms/windows/scripts/resident-profile.sh; resident_profile_powershell'],
                              cwd=ROOT, env={**os.environ, 'WINVM_RESIDENT_PROFILE': profile,
                                            'WINVM_USER_INSTANCE': instance, 'WINVM_USER_SESSION_ID': session},
                              text=True, capture_output=True)

    def test_appliance_default(self):
        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("$env:ProgramData", result.stdout)
        self.assertIn("$callArguments = @('call')", result.stdout)
        self.assertNotIn('--profile', result.stdout)

    def test_explicit_user_selection_and_artifact_root(self):
        result = self.render('user', 'candidate', '2')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MachineControl/packages/candidate', result.stdout)
        self.assertIn('MachineControl/workstation/candidate/session-2/artifacts', result.stdout)
        self.assertIn("'--session-id', '2'", result.stdout)
        self.assertNotIn('$instance', result.stdout)
        self.assertNotIn('$env:ProgramData', result.stdout)

    def test_refuses_ambiguous_or_injectable_selection(self):
        for profile, instance, session in [('wrong', 'default', '1'), ('user', 'default', ''),
                                            ('user', 'default', '0'), ('user', "a';exit", '1'),
                                            ('user', '../other', '1'), ('user', 'default', '1;exit')]:
            with self.subTest(profile=profile, instance=instance, session=session):
                self.assertNotEqual(self.render(profile, instance, session).returncode, 0)
