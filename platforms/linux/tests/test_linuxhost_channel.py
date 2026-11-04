"""The live host path retains exact claim checks without per-frame spawning."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('linuxhost',ROOT/'platforms/linux/host/linuxhost.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)


class HostClaimCheckerTests(unittest.TestCase):
    def test_live_checker_observes_release_and_identity_without_processes(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)/'claims';identity='a'*64
            command=[sys.executable,str(ROOT/'providers/claims/claims.py'),'--state-dir',str(directory)]
            acquired=subprocess.run([*command,'acquire','--provider','linux-host','--resource-id',identity,
                '--duration-seconds','180','--reason','Verify exact live host checks',
                '--claimant-authority','unit-test','--claimant-id','fixture'],capture_output=True,text=True,check=True)
            identifier=json.loads(acquired.stdout)['data']['claim']['claimId']
            with mock.patch.object(host,'claim_state',return_value=directory),mock.patch.object(host,'resource_id',return_value=identity):
                check=host.live_claim_checker(identifier)
                with mock.patch.object(subprocess,'run',side_effect=AssertionError('Live checks must not spawn')):
                    for _ in range(10):check()
                    with mock.patch.object(host,'resource_id',return_value='b'*64):
                        with self.assertRaisesRegex(ValueError,'identity changed'):check()
                subprocess.run([*command,'release','--provider','linux-host','--resource-id',identity,
                    '--claim-id',identifier],capture_output=True,check=True)
                with self.assertRaisesRegex(ValueError,'claim ended'):check()


if __name__=='__main__':unittest.main()
