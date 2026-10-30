import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tests/macos/reliability-acceptance.py'
SPEC = importlib.util.spec_from_file_location('reliability', SCRIPT)
RELIABILITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELIABILITY)


class DevelopmentRecoveryTests(unittest.TestCase):
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
