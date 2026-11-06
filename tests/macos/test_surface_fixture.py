"""Fixture lifetime must not turn native failure into acceptance evidence."""
import importlib.util
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest

spec=importlib.util.spec_from_file_location('surface_fixture',Path(__file__).with_name('surface_fixture.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


class SurfaceFixtureTests(unittest.TestCase):
    def test_stop_never_enables_access_or_claims_a_measurement_when_already_off(self):
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        calls=[];rig.settings=lambda:None;rig.close_owners=lambda:calls.append('close')
        rig.status=lambda:{'admission':{'surfaces':{'desktop':{'mode':'off'},'browser':{'mode':'off'}}}}
        rig.switch=lambda label:self.fail('Off access must never be toggled on by Stop')
        with self.assertRaisesRegex(AssertionError,'requires enabled access'):rig.stop()
        self.assertIsNone(rig.stop(require_active=False))
        self.assertEqual(calls,['close'])

    def test_options_disclosure_is_idempotent(self):
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        expanded=False;calls=[]
        def find(label,role='AXButton'):
            if label=='Access lifetime':return {'reference':'duration'} if expanded else None
            if label=='More options':return {'reference':'disclosure'}
        def observe(operation,**fields):
            nonlocal expanded
            calls.append((operation,fields));expanded=True
        rig.find=find;rig.observe=observe
        rig.options();rig.options()
        self.assertEqual(calls,[('action',{'reference':'disclosure','action':'press'})])

    def test_apply_requires_a_present_footer_and_refuses_a_conflict(self):
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        calls=[];rig.observe=lambda *a,**k:calls.append((a,k));rig.find=lambda *a:None
        rig.apply(timeout=0);self.assertEqual(calls,[])
        rig.find=lambda label,*a:{'reference':label}
        with self.assertRaisesRegex(AssertionError,'draft conflicts'):rig.apply(timeout=0)
        self.assertEqual(calls,[])

    def test_arming_enables_only_off_surfaces_and_applies_active_edits(self):
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        modes={'desktop':'off','browser':'ask'};calls=[];draft={}
        rig.profiles=['exact-profile'];rig.close_owners=lambda:calls.append('close')
        rig.settings=lambda:calls.append('settings');rig.options=lambda:calls.append('options')
        rig.select_profiles=lambda ids:calls.append(('profiles',ids.copy()))
        def choose(label,index):
            calls.append((label,index))
            if label.endswith(' before starting'):draft[label.split()[0].lower()]='ask' if index==2 else 'automatic'
        rig.choose=choose
        def switch(label):
            surface=label.split()[0].lower()
            self.assertEqual(modes[surface],'off','An enabled surface must never be toggled off while arming')
            calls.append(('switch',surface));modes[surface]=draft[surface]
        rig.switch=switch
        def apply():calls.append('apply');modes.update(draft)
        rig.apply=apply
        rig.status=lambda:{'admission':{'surfaces':{s:{'mode':mode,'consentRemainingSeconds':None} for s,mode in modes.items()}}}
        rig.arm()
        self.assertEqual(modes,{'desktop':'automatic','browser':'automatic'})
        self.assertEqual([c for c in calls if isinstance(c,tuple) and c[0]=='switch'],[('switch','desktop')])
        self.assertLess(calls.index(('profiles',['exact-profile'])),calls.index(('switch','desktop')))
        self.assertEqual(calls.count('apply'),1)

    def test_root_pause_requires_explicit_healthy_bounded_automatic_recovery(self):
        spec=importlib.util.spec_from_file_location('covered_recovery',Path(__file__).with_name('covered-recovery.py'))
        recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)
        value=dict(phase='paused',helperHealthy=True,pauseReason='watchdog_interrupted',
            pausedUntilManualUnlock=False,recoveryCondition='same_console_locked_healthy_and_quiet',recoveryDelaySeconds=30)
        self.assertTrue(recovery.recoverable_root_pause(value))
        for key,changed in [('helperHealthy',False),('pauseReason','physical_presence'),
                ('pausedUntilManualUnlock',True),('recoveryCondition',None),('recoveryDelaySeconds',900)]:
            with self.subTest(key=key):
                self.assertFalse(recovery.recoverable_root_pause({**value,key:changed}))

    def test_observer_metadata_and_typed_authorization_do_not_use_action_channel(self):
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        rig.observer='managed-fixture';rig.observer_owner=object();calls=[]
        def exchange(path,operation,**fields):
            calls.append((path,operation));return {'accepted':True,'data':{}}
        rig.exchange=exchange
        for operation in ['status','capabilities','authorization.begin']:
            self.assertTrue(rig.observer_response(operation)['accepted'])
        self.assertEqual(calls,[('managed-fixture',op) for op in ['status','capabilities','authorization.begin']])

    def test_automatic_owner_waits_without_desktop_ui_observation(self):
        ready=threading.Event();calls=[]
        class Session:
            def wait(self):
                if not ready.wait(3):raise AssertionError('Automatic activation missing')
            def status(self):ready.set();return {'state':'active'}
            def close(self):calls.append('close');ready.set()
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        rig.target={};rig.profiles=['fixture-profile'];rig.owners={}
        rig.sdk=lambda *args,**fields:Session()
        def find(label):raise AssertionError('Automatic Browser work must not inspect Desktop UI')
        rig.find=find
        rig.owner('browser');rig.close_owners()
        self.assertEqual(calls,['close'])

    def test_status_reobserves_only_the_typed_generation_refusal(self):
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture);rig.endpoint='fixture'
        replies=iter([{'accepted':False,'errorCode':'control_generation_changed'},
            {'accepted':True,'data':{'processId':123}}])
        calls=[]
        def exchange(*args):calls.append(args);return next(replies)
        rig.exchange=exchange
        self.assertEqual(rig.status(),{'processId':123})
        self.assertEqual(calls,[('fixture','status'),('fixture','status')])
        rig.exchange=lambda *args:{'accepted':False,'errorCode':'unrelated_failure'}
        with self.assertRaisesRegex(AssertionError,'unrelated_failure'):rig.status()

    def test_hybrid_phase_uses_one_owner_and_closes_it_once(self):
        calls=[]
        class Session:
            def wait(self):pass
            def status(self):return {'state':'active'}
            def close(self):calls.append('close')
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        rig.target={};rig.profiles=['fixture-profile'];rig.owners={}
        def sdk(*args,**fields):calls.append(fields);return Session()
        rig.sdk=sdk;rig.find=lambda label:None
        owner=rig.owner('both')
        self.assertIs(rig.owners['desktop'],owner)
        self.assertIs(rig.owners['browser'],owner)
        self.assertEqual(calls[0]['surfaces'],['desktop','browser'])
        self.assertEqual(calls[0]['profile_ids'],['fixture-profile'])
        with self.assertRaisesRegex(AssertionError,'previous human-input owner'):rig.owner('browser')
        rig.close_owners()
        self.assertEqual(calls.count('close'),1)
        self.assertEqual(rig.owners,{})

    def test_surface_owner_uses_the_current_native_approval_control(self):
        approved=threading.Event();calls=[]
        class Session:
            def wait(self):
                if not approved.wait(3):raise AssertionError('Native approval not pressed')
            def close(self):calls.append('close');approved.set()
            def status(self):return {'state':'waiting_for_approval'}
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        rig.target={};rig.profiles=[];rig.owners={}
        def sdk(*args,**fields):calls.append('open');return Session()
        rig.sdk=sdk
        def find(label):
            calls.append(label)
            return {'reference':'native-approval'} if label=='Allow now' else None
        rig.find=find
        def observe(operation,**fields):
            self.assertEqual((operation,fields),('action',{'reference':'native-approval','action':'press'}))
            approved.set()
        rig.observe=observe
        owner=rig.owner('desktop')
        self.assertIs(rig.owners['desktop'],owner)
        self.assertEqual(calls.count('open'),1)
        self.assertIn('Allow now',calls)
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

    def process(self,*,failure=False,blocked=False,profiles=()):
        calls=[];ready=threading.Event()
        if not blocked:ready.set()
        class Session:
            def wait(self):calls.append('wait');return {'state':'active'}
            def call(self,request):
                calls.append(request['operation']);ready.wait(3)
                return {'accepted':not failure,'errorCode':'fixture_refused' if failure else None,
                    'data':{'tabs':[{'tabId':1}]} if request['operation']=='browser.tabs' else {}}
            def close(self):calls.append('close');ready.set()
        rig=SimpleNamespace(sdk=lambda *a,**k:Session(),target={},owners={},profiles=list(profiles))
        rig.close_owners=lambda:rig.owners.clear()
        rig.bind_owner=lambda owner,surfaces:rig.owners.update({s:owner for s in surfaces})
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
        self.assertIn(b'fixture_refused',output)
        self.assertEqual(calls.count('snapshot'),1)

    def test_pending_first_read_cannot_claim_completion_or_retarget(self):
        process,_,native,_,ready=self.process(blocked=True)
        self.assertFalse(process.activation_reads_finished)
        self.assertIsNone(process.poll())
        ready.set();process.future.result(3);self.assertTrue(process.activation_reads_finished);self.assertIsNone(process.poll())
        native['controlSessionId']='replacement-owner'
        with self.assertRaisesRegex(AssertionError,'changed without a new task'):process.poll()

    def test_hybrid_activation_proves_both_routes_before_fault_injection(self):
        process,rig,_,calls,_=self.process(profiles=['fixture-profile'])
        process.future.result(3)
        self.assertTrue(process.activation_reads_finished)
        self.assertEqual(calls,['wait','snapshot','browser.tabs'])
        self.assertIs(rig.owners['desktop'],rig.owners['browser'])

    def test_unknown_delivery_never_retries_an_operator_action(self):
        rig=fixture.SurfaceFixture.__new__(fixture.SurfaceFixture)
        rig.observer_owner=None;rig.observer='unused';rig.claim='fixture'
        attempts=[]
        rig.exchange=lambda *a,**k:{'accepted':False,'errorCode':'control_session_required','delivery':'unknown','uncertainty':'outcome_unknown'}
        rig.actor=SimpleNamespace(Owner=lambda *a,**k:attempts.append('open'))
        with self.assertRaises(AssertionError):rig.observer_response('action',reference='untrusted',action='press')
        self.assertEqual(attempts,[])


if __name__=='__main__':unittest.main()
