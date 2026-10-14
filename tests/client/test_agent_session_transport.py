"""Claim, admission and audit ordering around a retained operation."""
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'client'))
import machine_control as mc
from agent_session import SessionError
from agent_session_transport import RetainedTransport


class TransportTest(unittest.TestCase):
    def setUp(self):
        self.events=[];self.requests=[];self.refuse_audit=False;self.lose_claim=False;self.result_failure=False
        outer=self
        class Claim:
            def __init__(self,*a,**kw):outer.events.append('claim.open')
            def wait(self):return {}
            def bound_target(self):return dict(platform='macos',_claimId='fixture')
            def renew(self,duration):outer.events.append('claim.renew');return {'accepted':True}
            def close(self):outer.events.append('claim.close')
        class Owner:
            def __init__(self,*a,**kw):outer.events.append('owner.open')
            def wait(self):return {}
            def call(self,request):
                outer.requests.append(request)
                outer.events.append('owner.check')
                if outer.lose_claim:raise mc.ClientError('claim_expired','Claim ended')
                outer.events.append('dispatch')
                return dict(accepted=True,operation=request['operation'])
            def close(self):outer.events.append('owner.close')
        class Audit:
            def __init__(self,alias,platform,words,claim,**metadata):
                outer.events.append('audit.intent')
                if outer.refuse_audit:raise OSError('storage unavailable')
            def observe(self,value):outer.events.append('audit.observe')
            def finish(self,*args):
                outer.events.append('audit.result')
                return None if outer.result_failure else True
        self.claim,self.owner,self.audit=Claim,Owner,Audit
        for name,value in [('doctor',lambda *a:({'ready':True},0)),
                           ('validate_resident',lambda v,p:v)]:
            p=patch('agent_session_transport.mc.'+name,value);p.start();self.addCleanup(p.stop)
        p=patch('agent_session_transport.audit_history.best_effort');p.start();self.addCleanup(p.stop)

    def transport(self):
        t=RetainedTransport('fixture',{'platform':'macos'},reason='test',
            claimant_authority='fixture',claimant_id='caller',claim_factory=self.claim,
            control_factory=self.owner,audit_factory=self.audit)
        self.addCleanup(t.close)
        return t

    def test_each_operation_has_audit_intent_and_uses_retained_owner(self):
        t=self.transport();self.events.clear()
        t.call({'operation':'input.text','text':'private text'})
        t.call({'operation':'snapshot'})
        self.assertEqual(self.events,['audit.intent','owner.check','dispatch','audit.observe','audit.result']*2)
        t.close();self.assertEqual(self.events[-2:],['owner.close','claim.close'])

    def test_audit_intent_failure_prevents_dispatch_and_closes_ownership(self):
        t=self.transport();self.events.clear();self.refuse_audit=True
        with self.assertRaises(SessionError):t.call({'operation':'input.text'})
        self.assertNotIn('dispatch',self.events)
        self.assertEqual(self.events[-2:],['owner.close','claim.close'])

    def test_audit_result_failure_is_unknown_and_never_replayed(self):
        t=self.transport();self.events.clear();self.result_failure=True
        with self.assertRaises(SessionError) as e:t.call({'operation':'input.text'})
        self.assertEqual(e.exception.delivered,'unknown')
        with self.assertRaises(SessionError):t.call({'operation':'input.text'})
        self.assertEqual(self.events.count('dispatch'),1)
        self.assertIn('claim.close',self.events)

    def test_expired_claim_stops_before_dispatch_and_cannot_be_reused(self):
        t=self.transport();self.events.clear();self.lose_claim=True
        with self.assertRaises(SessionError):t.call({'operation':'input.text'})
        self.assertNotIn('dispatch',self.events)
        self.assertEqual(self.events[-2:],['owner.close','claim.close'])

    def test_constructor_failure_closes_already_acquired_claim(self):
        def fail(*args,**kwargs):raise RuntimeError('owner unavailable')
        with self.assertRaises(RuntimeError):
            RetainedTransport('fixture',{'platform':'macos'},reason='test',claimant_authority='fixture',
                claimant_id='caller',claim_factory=self.claim,control_factory=fail,audit_factory=self.audit)
        self.assertEqual(self.events[-1],'claim.close')

    def test_mac_control_channel_uses_native_chords_and_preserves_plus_key(self):
        t=self.transport()
        for chord in ('cmd+s','cmd++','+'):
            t.call({'operation':'input.key','key':chord})
        self.assertEqual([r['key'] for r in self.requests],['cmd-s','cmd-+','+'])

    def test_expired_admission_releases_claim_without_another_agent_call(self):
        t=self.transport();self.events.clear()
        t.owner_deadline=time.monotonic()-1
        t.renewal.join(timeout=3)
        self.assertFalse(t.renewal.is_alive())
        self.assertEqual(self.events[-2:],['owner.close','claim.close'])
        with self.assertRaises(SessionError):t.call({'operation':'snapshot'})

    def test_image_audit_failure_closes_ownership_before_fetch(self):
        t=self.transport();self.events.clear();self.refuse_audit=True
        with patch('agent_session_transport.mc.run_adapter') as fetch:
            with self.assertRaises(SessionError):t.image({'data':{'artifactPath':'fixture.png'}})
            fetch.assert_not_called()
        self.assertEqual(self.events[-2:],['owner.close','claim.close'])

    def test_image_claim_loss_closes_ownership_without_retry(self):
        t=self.transport();self.events.clear()
        with patch('agent_session_transport.mc.require_selected_claim',side_effect=mc.ClientError('claim_expired','ended')), \
             patch('agent_session_transport.mc.run_adapter') as fetch:
            with self.assertRaises(SessionError):t.image({'data':{'artifactPath':'fixture.png'}})
            fetch.assert_not_called()
        self.assertEqual(self.events[-2:],['owner.close','claim.close'])


if __name__=='__main__':unittest.main()
