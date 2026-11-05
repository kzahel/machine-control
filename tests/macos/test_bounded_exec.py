"""Guest transport timeouts retain complete common-CLI journal coverage."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == 'darwin', 'Requires the Mac adapter')
class BoundedExecTests(unittest.TestCase):
    def test_timeout_records_result_and_keeps_the_same_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root/'targets.json'
            environment = dict(MACVM_CONFIG_FILE='/dev/null',
                MACVM_NAME='fixture-bounded', MACVM_EXPECTED_NAME='fixture-bounded',
                MACVM_CLAIM_STATE_DIR=str(root/'claims'),
                MACVM_TART=str(ROOT/'platforms/macos/tests/fixtures/tart'))
            registry.write_text(json.dumps(dict(schema='machine-control-targets/v0',
                targets=dict(fixture=dict(platform='macos', profile='fixture',
                    launcher='direct', claimPolicy='required',
                    controllerPlatforms=['darwin'], environment=environment,
                    command=['/bin/bash', str(ROOT/'platforms/macos/bin/macvm')])))))

            def cli(*args):
                return subprocess.run([sys.executable,str(ROOT/'bin/machine-control'),
                    '--registry',str(registry),'--target','fixture',*args],
                    capture_output=True,text=True,timeout=20,
                    env={**os.environ, 'MACHINE_CONTROL_PROVISION_DIR':str(root/'journals'),
                        'MACHINE_CONTROL_AUDIT_DIR':str(root/'audit'),
                        'MACHINE_CONTROL_CLAIM_POLICY':'required'})

            run = json.loads(cli('provision','begin','--platform','macos').stdout)['runId']
            acquired = cli('--provision-run',run,'claim','acquire',
                '--claimant-authority','fixture','--claimant-id','owner',
                '--reason','Bound read-only transport observations')
            self.assertEqual(acquired.returncode,0,acquired.stdout+acquired.stderr)
            claim = json.loads(acquired.stdout)['data']['claim']['claimId']
            prefix = ['--provision-run',run,'--claim',claim]
            try:
                expired = cli(*prefix,'testbed','--','exec','--timeout-seconds',
                    '1','--','/bin/sleep','5')
                self.assertEqual(expired.returncode,124,expired.stdout+expired.stderr)
                observed = cli(*prefix,'testbed','--','exec','--timeout-seconds',
                    '5','--','/usr/bin/printf','ready')
                self.assertEqual(observed.returncode,0,observed.stdout+observed.stderr)
                self.assertEqual(observed.stdout,'ready')
            finally:
                released = cli('--provision-run',run,'claim','release',claim)
                self.assertEqual(released.returncode,0,released.stdout+released.stderr)
            finished = cli('provision','finish',run,'--outcome','ready')
            self.assertEqual(finished.returncode,0,finished.stdout+finished.stderr)
            report = json.loads(cli('provision','show',run).stdout)
            self.assertEqual(report['coverage']['unpairedCommands'],0)
            self.assertTrue(any(e.get('event')=='command.result' and
                e.get('exitCode')==124 for e in report['events']))


if __name__ == '__main__':
    unittest.main()
