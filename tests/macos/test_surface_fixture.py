"""Fixture lifetime must not turn native failure into acceptance evidence."""
import importlib.util
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest

spec=importlib.util.spec_from_file_location('surface_fixture',Path(__file__).with_name('surface_fixture.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


class SurfaceFixtureTests(unittest.TestCase):
    def test_surface_owner_uses_the_current_native_approval_control(self):
        approved=threading.Event();calls=[]
        class Session:
            def wait(self):
                if not approved.wait(3):raise AssertionError('Native approval not pressed')
            def close(self):calls.append('close');approved.set()
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        rig.target={};rig.profiles=[];rig.owners={}
        def sdk(*args,**fields):calls.append('open');return Session()
        rig.sdk=sdk
        def find(label):
            calls.append(label)
            return {'reference':'native-approval'} if label=='Allow this task' else None
        rig.find=find
        def observe(operation,**fields):
            self.assertEqual((operation,fields),('action',{'reference':'native-approval','action':'press'}))
            approved.set()
        rig.observe=observe
        owner=rig.owner('desktop')
        self.assertIs(rig.owners['desktop'],owner)
        self.assertEqual(calls.count('open'),1)
        self.assertIn('Allow this task',calls)
        owner.close()

    def test_observer_requires_explicit_managed_administration(self):
        value={'deployment':{'policy':{'preset':'appliance','grantMode':'surface_modes',
                'protectedAdministration':True}},'nativeSemanticState':'ready'}
        fixture.require_managed_observer(value)
        value['deployment']['policy']['protectedAdministration']=False
        with self.assertRaises(AssertionError):fixture.require_managed_observer(value)
        value['deployment']['policy'].update(preset='workstation',protectedAdministration=True)
        with self.assertRaises(AssertionError):fixture.require_managed_observer(value)
        value['deployment']['policy'].update(preset='appliance',grantMode='standing')
        fixture.require_managed_observer(value)
        value['nativeSemanticState']='unavailable'
        with self.assertRaises(AssertionError):fixture.require_managed_observer(value)

    def process(self,*,failure=False,blocked=False):
        calls=[];ready=threading.Event()
        if not blocked:ready.set()
        class Session:
            def wait(self):calls.append('wait');return {'state':'active'}
            def call(self,request):
                calls.append(request['operation']);ready.wait(3)
                return {'accepted':not failure,'errorCode':'fixture_refused' if failure else None}
            def close(self):calls.append('close');ready.set()
        rig=SimpleNamespace(sdk=lambda *a,**k:Session(),target={},owners={})
        native={'phase':'active','controlSessionId':'native-one','lastEndedReason':None}
        process=fixture.SDKOwnerProcess(rig,900,123,lambda:{'lockedUse':native})
        self.addCleanup(process.terminate)
        return process,rig,native,calls,ready

    def test_ending_requires_actual_native_reason_and_reaps_exact_owner(self):
        process,rig,native,calls,_=self.process()
        process.future.result(3)
        self.assertIsNone(process.poll())
        native.update(phase='ready',controlSessionId=None)
        with self.assertRaisesRegex(AssertionError,'without an ending reason'):process.poll()
        native['lastEndedReason']='duration_expired'
        self.assertEqual(process.poll(),0)
        output,_=process.communicate()
        self.assertIn(b'duration_expired',output)
        self.assertNotIn('desktop',rig.owners)
        self.assertEqual(calls.count('wait'),1)
        self.assertEqual(calls.count('snapshot'),1)

    def test_refused_first_read_is_not_replayed_or_accepted(self):
        process,_,native,calls,_=self.process(failure=True)
        with self.assertRaises(AssertionError):process.future.result(3)
        native.update(phase='ready',controlSessionId=None,lastEndedReason='guardian_start_failed')
        self.assertEqual(process.poll(),1)
        output,_=process.communicate()
        self.assertIn(b'"accepted": false',output)
        self.assertEqual(calls.count('snapshot'),1)

    def test_pending_first_read_cannot_claim_completion_or_retarget(self):
        process,_,native,_,ready=self.process(blocked=True)
        self.assertIsNone(process.poll())
        ready.set();process.future.result(3);self.assertIsNone(process.poll())
        native['controlSessionId']='replacement-owner'
        with self.assertRaisesRegex(AssertionError,'changed without a new task'):process.poll()

    def test_unknown_delivery_never_retries_an_operator_action(self):
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        rig.observer_owner=None;rig.observer='unused';rig.claim='fixture'
        attempts=[]
        rig.exchange=lambda *a,**k:{'accepted':False,'errorCode':'control_session_required','delivery':'unknown','uncertainty':'outcome_unknown'}
        rig.actor=SimpleNamespace(Owner=lambda *a,**k:attempts.append('open'))
        with self.assertRaises(AssertionError):rig.observer_response('action',reference='untrusted',action='press')
        self.assertEqual(attempts,[])


if __name__=='__main__':unittest.main()
