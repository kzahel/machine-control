import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tests/macos/reliability-acceptance.py'
SPEC = importlib.util.spec_from_file_location('reliability', SCRIPT)
RELIABILITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELIABILITY)


class DevelopmentRecoveryTests(unittest.TestCase):
    def test_development_modes_cannot_enter_release_mode_or_touch_a_target(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in ['--dialog-probe','--source-sdk']:
                with self.subTest(mode=mode):
                    output=Path(directory)/mode.lstrip('-')
                    result=subprocess.run([sys.executable,str(ROOT/'tests/macos/packaged-acceptance.py'),
                        mode,'--package-directory',str(Path(directory)/'unread-package'),
                        '--team-id','UNUSED','--output',str(output)],capture_output=True,text=True)
                    self.assertEqual(result.returncode,2)
                    self.assertIn('development-only',result.stderr)
                    self.assertFalse(output.exists())

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root/'campaign').mkdir()
        (self.root/'campaign/identity.json').write_text(json.dumps({'development':True}))
        self.events = [dict(schema='machine-control-run/v0',event='acquired',claimId='claim-a',workspaceHandle='workspace-a',logicalTarget='fixture'),
            dict(schema='machine-control-run/v0',event='finished',claimId='claim-a',workspaceHandle='workspace-a',logicalTarget='fixture',
                exitCode=0,childExitCode=0,outcome='completed',cleanup={'claim':'released','workspace':'released'})]
        self.summary = dict(passed=True,faults=True,remoteArming=True,plannedRestarts=5,checks=200,repeat=3,
            reliability={'coveredDurationSeconds':900,'renewableOwnerSeconds':960})
        self.write()

    def write(self):
        (self.root/'campaign.log').write_text('\n'.join(map(json.dumps,self.events)))
        data = json.dumps(self.summary).encode()
        with tarfile.open(self.root/'campaign/guest-evidence.tar','w') as archive:
            member = tarfile.TarInfo('results/summary.json'); member.size = len(data)
            archive.addfile(member,io.BytesIO(data))

    def test_only_exact_completed_and_disposed_scope_can_resume(self):
        self.assertEqual(RELIABILITY.completed_development_campaign(self.root),self.root/'campaign')
        self.events[-1]['workspaceHandle'] = 'other'
        self.write()
        with self.assertRaises(ValueError): RELIABILITY.completed_development_campaign(self.root)
        self.events[-1]['workspaceHandle'] = 'workspace-a'
        self.events[-1]['cleanup']['workspace'] = 'unresolved'
        self.write()
        with self.assertRaises(ValueError): RELIABILITY.completed_development_campaign(self.root)

    def test_short_or_non_development_evidence_cannot_resume(self):
        self.summary['reliability']['renewableOwnerSeconds'] = 120
        self.write()
        with self.assertRaises(ValueError): RELIABILITY.completed_development_campaign(self.root)
        self.summary['reliability']['renewableOwnerSeconds'] = 960
        self.write()
        (self.root/'campaign/identity.json').write_text(json.dumps({'development':False}))
        with self.assertRaises(ValueError): RELIABILITY.completed_development_campaign(self.root)

    def test_recovery_cannot_enter_release_mode_or_touch_a_target(self):
        output = self.root/'new-output'
        result = subprocess.run([sys.executable,str(SCRIPT),'--resume-campaign',str(self.root),
            '--target','fixture','--claimant-authority','test','--claimant-id','test','--provision-run','unused',
            '--admin-secret-file',str(self.root/'unread-secret'),'--output',str(output)],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('require --development',result.stderr)
        self.assertFalse(output.exists())

    def timing_arguments(self, version, output, *options):
        package = self.root / version
        package.mkdir(exist_ok=True)
        (package / 'build.json').write_text(json.dumps({'version': version}))
        return [str(SCRIPT), '--target', 'fixture', '--claimant-authority', 'test',
            '--claimant-id', 'test', '--provision-run', 'unused',
            '--admin-secret-file', str(self.root / 'unread-secret'),
            '--output', str(output), '--package-directory', str(package),
            '--team-id', 'UNUSED', *options]

    def test_timing_profile_configures_the_complete_campaign(self):
        for index, (version, options, expected) in enumerate([
            ('0.7.6', [], ('900', '960')),
            ('0.7.7', [], ('60', '120')),
            ('0.7.7', ['--timing-profile', 'extended'], ('900', '960')),
            ('0.7.6', ['--development', '--timing-profile', 'standard'], ('60', '120')),
        ]):
            with self.subTest(version=version, options=options):
                args = self.timing_arguments(version, self.root / f'output-{index}', *options)
                with patch.object(sys, 'argv', args), \
                        patch.object(RELIABILITY, 'run_claimed', side_effect=SystemExit(17)) as run:
                    with self.assertRaises(SystemExit) as stopped:
                        RELIABILITY.main()
                self.assertEqual(stopped.exception.code, 17)
                campaign = run.call_args.args[0]
                actual = tuple(campaign[campaign.index(flag) + 1] for flag in
                               ('--covered-duration', '--covered-renewal-seconds'))
                self.assertEqual(actual, expected)
                self.assertNotIn('--covered-probe', campaign)
                self.assertIn('--faults', campaign)

    def test_historical_release_refuses_standard_timing_before_claiming(self):
        output = self.root / 'historical-output'
        args = self.timing_arguments('0.7.6', output, '--timing-profile', 'standard')
        result = subprocess.run([sys.executable, *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('starts at 0.7.7', result.stderr)
        self.assertFalse(output.exists())
