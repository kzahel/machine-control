"""Linux adapter conformance against the packaged Node authority."""
import json
import os
import queue
import socket
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'desktop/native/linux'))
from access import Access
from channel import Channel,process_token
from policy import Policy,PolicyError
import test_linux_policy


class AccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_linux_policy.SharedPolicyTests.setUpClass()
        cls.root=test_linux_policy.SharedPolicyTests.root

    def setUp(self):
        self.callbacks=queue.Queue();self.changes=[]
        self.host=Policy(lambda f,*a:self.callbacks.put(lambda:f(*a)),lambda _:None,lambda _:None,root=self.root)
        self.addCleanup(self.host.stop)
        self.access=Access(self.host,self.changes.append)
        self.access.fact('input',True)
        for surface in ('desktop','browser'):self.access.fact(surface,(True,True))
        self.access.send('notice',milliseconds=0)
        self.access.configure('desktop','automatic',None)
        self.access.configure('browser','automatic',None,['work','personal'])

    def submit(self,owner='one',surface='desktop',operations=None):
        return self.access.submit(owner,dict(requestId=owner,surfaces=[surface],
            profileIds=['work'] if surface=='browser' else [],operations=operations,
            reason='Native adapter fixture',waitMs=10000,durationMs=60000),lambda:None)

    def active(self,owner='one',surface='desktop',operations=None):
        offered=self.submit(owner,surface,operations)
        self.assertEqual(offered['state'],'offered')
        return self.access.accept(owner,offered['offerGeneration'])

    def refusal(self,active,owner='one',operation='snapshot'):
        return self.access.authorize(owner,active['sessionId'],active['resourceGenerations'],operation)

    def test_shared_stop_and_owner_disconnect_revoke_without_disabling_consent(self):
        active=self.active();self.assertIsNone(self.refusal(active))
        self.access.close('one');self.assertEqual(self.refusal(active),'owner_disconnected')
        self.assertEqual(self.access.state()['surfaces']['desktop']['mode'],'automatic')
        self.active('two');self.access.stop()
        self.assertEqual(self.access.state()['surfaces']['desktop']['mode'],'off')

    def test_browser_configuration_and_pause_do_not_cancel_desktop(self):
        active=self.active();generation=self.access.generation
        self.access.pause('browser',seconds=30)
        self.access.configure('browser','ask',None,['personal'])
        self.assertEqual(self.access.generation,generation)
        self.assertIsNone(self.refusal(active))

    def test_temporary_native_loss_requeues_with_new_offer_and_session(self):
        active=self.active();self.access.fact('desktop',(False,False))
        self.assertIsNotNone(self.refusal(active))
        self.assertEqual(self.access.inspect('one')['state'],'paused')
        self.access.fact('desktop',(True,True));offered=self.access.inspect('one')
        renewed=self.access.accept('one',offered['offerGeneration'])
        self.assertNotEqual(renewed['sessionId'],active['sessionId'])
        self.assertIsNotNone(self.refusal(active));self.assertIsNone(self.refusal(renewed))

    def test_unknown_input_allows_only_enforced_background_browser_operations(self):
        self.access.fact('input',False)
        self.assertEqual(self.submit()['state'],'paused')
        active=self.active('background','browser',['browser.tabs'])
        self.assertIsNone(self.refusal(active,'background','browser.tabs'))
        self.assertIsNotNone(self.refusal(active,'background','browser.eval'))

    def test_exact_offer_and_ask_approval_are_required(self):
        self.access.configure('desktop','ask',None)
        pending=self.submit();self.assertEqual(pending['state'],'waiting_for_approval')
        self.access.send('approve',intentId=pending['intentId'])
        offered=self.access.inspect('one')
        with self.assertRaises(PolicyError):self.access.accept('one',offered['offerGeneration']+1)
        self.assertEqual(self.access.accept('one',offered['offerGeneration'])['state'],'active')

    def test_dead_policy_stays_off_and_does_not_replay(self):
        self.active();self.host.stop();self.access.stop()
        self.assertFalse(self.access.state()['available'])
        self.assertEqual(self.access.state()['surfaces']['desktop']['mode'],'off')

    def test_live_channel_sequence_owner_binding_and_close(self):
        server,client=socket.socketpair();client.settimeout(2)
        self.addCleanup(server.close);self.addCleanup(client.close)
        owner=SimpleNamespace(grants=self.access,native_authority=lambda _:None,
            scheduler=SimpleNamespace(post=lambda f,*a:self.callbacks.put(lambda:f(*a))),
            channels=set(),changed=lambda:None)
        channel=Channel(owner,server,os.getpid(),process_token(os.getpid()))
        # This portable case supplies only the authenticated native caller fact;
        # the Linux appliance gate exercises the actual /proc identity check.
        channel.authority=lambda:None
        owner.channels.add(channel);self.addCleanup(channel.close)
        def call(sequence,operation,**fields):
            channel.handle(dict(requestSequence=sequence,requestId=str(sequence),operation=operation,**fields))
            # Each response is small; no framing assumption about recv chunks.
            body=b''
            while not body.endswith(b'\n'):body+=client.recv(65536)
            return json.loads(body)
        opened=call(1,'control.open',schema='machine-control-admission/v2',surfaces=['desktop'],reason='Channel fixture')
        self.assertTrue(opened['accepted']);self.assertEqual(opened['data']['state'],'offered')
        self.assertEqual(call(1,'control.status')['errorCode'],'invalid_request_sequence')
        self.assertTrue(call(2,'control.heartbeat')['accepted'])
        channel.close()
        while not self.callbacks.empty():self.callbacks.get()()
        self.assertNotIn(channel.label,self.access.owners)

    def test_sdk_open_negotiates_the_first_required_sequence(self):
        server,client=socket.socketpair();client.settimeout(2)
        self.addCleanup(server.close);self.addCleanup(client.close)
        owner=SimpleNamespace(grants=self.access,native_authority=lambda _:None,
            scheduler=SimpleNamespace(post=lambda f,*a:self.callbacks.put(lambda:f(*a))),
            channels=set(),changed=lambda:None)
        channel=Channel(owner,server,os.getpid(),process_token(os.getpid()))
        # This portable case supplies only the authenticated native caller fact;
        # the Linux appliance gate exercises the actual /proc identity check.
        channel.authority=lambda:None
        owner.channels.add(channel);self.addCleanup(channel.close)
        def call(sequence,operation,**fields):
            channel.handle(dict(requestId=str(sequence),operation=operation,**({'requestSequence':sequence} if sequence else {}),**fields))
            # Each response is small; no framing assumption about recv chunks.
            body=b''
            while not body.endswith(b'\n'):body+=client.recv(65536)
            return json.loads(body)
        opened=call(0,'control.open',schema='machine-control-admission/v2',surfaces=['desktop'],reason='Channel fixture')
        self.assertTrue(opened['accepted']);self.assertEqual(opened['data']['state'],'offered')
        self.assertEqual(opened['data']['requestSequencing'],'strict')
        self.assertTrue(call(1,'control.heartbeat')['accepted'])
        self.assertEqual(call(1,'control.status')['errorCode'],'invalid_request_sequence')
        channel.close()
        while not self.callbacks.empty():self.callbacks.get()()
        self.assertNotIn(channel.label,self.access.owners)
