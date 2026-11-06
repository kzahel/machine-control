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



class HostDoctorTests(unittest.TestCase):
    def doctor(self,data):
        status=dict(schema='machine-control/v0',accepted=True,generation='g',data=data)
        output=[]
        with mock.patch.object(host,'resource_id',return_value='a'*64),mock.patch.object(host,'call',return_value=status),\
                mock.patch('builtins.print',side_effect=output.append):
            host.doctor()
        return json.loads(output[0])

    def data(self,**fields):
        value=dict(desktopProduct=True,ready=False,semanticState='ready',captureState='ready',inputState='ready',
            grant=None,pendingRequest=None,policy={},admission=dict(surfaces=dict(desktop=dict(mode='off'),browser=dict(mode='off'))))
        value.update(fields);return value

    def test_desktop_state_maps_directly_including_locked(self):
        for state in ('locked','unlocked','no_session','unknown'):
            self.assertEqual(self.doctor(self.data(desktopState=state))['states']['desktop'],state)
        self.assertEqual(self.doctor(self.data(desktopState='bogus'))['states']['desktop'],'unknown')
        # Older residents without desktopState keep the readiness fallback.
        self.assertEqual(self.doctor(self.data(ready=True))['states']['desktop'],'unlocked')

    def test_access_check_reads_surface_modes_not_per_request_grants(self):
        checks={c['id']:c for c in self.doctor(self.data(desktopState='unlocked'))['checks']}
        self.assertNotIn('grant',checks);self.assertEqual(checks['access']['status'],'warn')
        on=self.data(desktopState='unlocked',admission=dict(surfaces=dict(desktop=dict(mode='ask'),browser=dict(mode='off'))))
        checks={c['id']:c for c in self.doctor(on)['checks']}
        self.assertEqual(checks['access']['status'],'pass');self.assertIn('desktop: ask',checks['access']['summary'])
        self.assertNotIn('grant',json.dumps(checks['access']).lower())

    def test_common_deployment_is_reported(self):
        deployment=dict(policy=dict(preset='workstation',grantMode='surface_modes',protectedAdministration=False),
            availability=dict(paused=False,blockingReasons=[]),browserOnlyWhileLocked=False)
        value=self.doctor(self.data(desktopState='unlocked',deployment=deployment))
        self.assertEqual(value['extensions']['deployment']['policy'],deployment['policy'])
        self.assertIn('availability',value['extensions']['deployment'])


if __name__=='__main__':unittest.main()
