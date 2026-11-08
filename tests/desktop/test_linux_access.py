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


@unittest.skipIf(sys.platform == 'win32', 'Requires POSIX Linux-adapter process and pipe semantics')
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

    def test_pending_approval_projection_does_not_revoke_other_surface_owner(self):
        active=self.active()
        self.access.configure('browser','ask',None,['work'])
        pending=self.submit('other','browser',['browser.tabs'])
        self.assertEqual(self.access.pending['intentId'],pending['intentId'])
        self.assertIsNone(self.refusal(active))
        self.access.send('approve',intentId=pending['intentId'])
        self.assertIsNone(self.access.pending);self.assertIsNone(self.refusal(active))

    def test_snapshot_serves_the_last_full_projection_without_calling_policy(self):
        self.assertEqual(self.access.snapshot()['surfaces']['desktop']['mode'],'automatic')
        calls=[];call=self.host.call
        self.host.call=lambda frame,**options:calls.append(frame) or call(frame,**options)
        self.access.fact('input',False)
        self.assertEqual(self.access.snapshot()['surfaces']['desktop']['mode'],'automatic')
        self.assertEqual([frame['method'] for frame in calls],['access.input-ready'])
        # Mutations return full projections, so the snapshot never predates them.
        self.access.configure('desktop','off',None)
        self.assertEqual(self.access.snapshot()['surfaces']['desktop']['mode'],'off')
        self.assertIn('experienceVersion',self.access.snapshot())
        self.assertTrue(self.access.status_current)
        # A query-only reply that changes the projection supersedes it.
        self.access.fact('desktop',(False,False))
        self.assertFalse(self.access.status_current)
        self.access.state();self.assertTrue(self.access.status_current)

    def test_audit_storage_loss_ends_active_and_queued_intents_with_its_reason(self):
        refusal=[None]
        def submit(owner,surface):
            return self.access.submit(owner,dict(requestId=owner,surfaces=[surface],
                profileIds=['work'] if surface=='browser' else [],reason='Audit fixture',
                waitMs=10000,durationMs=60000),lambda:refusal[0])
        offered=submit('active','desktop')
        self.access.accept('active',offered['offerGeneration'])
        self.assertEqual(submit('queued','desktop')['state'],'waiting_for_resource')
        refusal[0]='audit_storage_unavailable'
        self.access.refresh()
        for owner in ('active','queued'):
            view=self.access.send('inspect',owner=owner,intentId=self.access.owners[owner]['intent'])
            self.assertEqual((view['state'],view['terminalReason']),('ended','audit_storage_unavailable'))

    def test_other_native_refusals_still_end_as_cancelled(self):
        refusal=[None]
        self.access.submit('one',dict(requestId='one',surfaces=['desktop'],profileIds=[],
            reason='Disconnect fixture',waitMs=10000,durationMs=60000),lambda:refusal[0])
        refusal[0]='owner_disconnected';self.access.refresh()
        view=self.access.send('inspect',owner='one',intentId=self.access.owners['one']['intent'])
        self.assertEqual(view['terminalReason'],'cancelled')

    def test_common_deployment_projection(self):
        deployment=self.access.deployment()
        self.assertEqual(deployment['policy'],dict(grantMode='surface_modes',preset='workstation',
            protectedAdministration=False,protectedOperations=False))
        self.assertEqual(deployment['availability'],dict(paused=False,blockingReasons=[]))
        self.assertIn('grant',deployment)  # Compatibility key for older readers.
        self.access.pause('desktop',seconds=30);self.access.fact('desktop',(False,False))
        self.assertEqual(self.access.availability(),dict(paused=True,blockingReasons=['manual','resource_unavailable']))
        self.host.stop()
        self.assertEqual(self.access.availability()['blockingReasons'],['control_policy_unavailable'])

    def test_browser_only_while_locked_requires_lock_preference_binding_and_consent(self):
        self.access.state()
        self.assertFalse(self.access.browser_only_while_locked)
        self.access.locked=True;self.access.browser_while_locked=True
        self.assertFalse(self.access.browser_only_while_locked)
        self.access.browser_bound=True
        self.assertTrue(self.access.browser_only_while_locked)
        self.assertTrue(self.access.deployment()['browserOnlyWhileLocked'])
        self.access.configure('browser','off',None);self.access.state()
        self.assertFalse(self.access.browser_only_while_locked)

    def test_desktop_state_and_locked_refusal(self):
        import ast
        source=Path(__file__).resolve().parents[2]/'desktop/native/linux/desktop.py'
        cls=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Desktop')
        methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('desktop_state','locked_desktop_refusal')]
        namespace={};exec(compile(ast.Module(body=methods,type_ignores=[]),str(source),'exec'),namespace)
        state=lambda **f:namespace['desktop_state'](SimpleNamespace(**f))
        self.assertEqual(state(locked=True,unlocked=False,session_identity=('1',1,':1')),'locked')
        self.assertEqual(state(locked=False,unlocked=True,session_identity=('1',1,':1')),'unlocked')
        self.assertEqual(state(locked=False,unlocked=False,session_identity=None),'no_session')
        self.assertEqual(state(locked=False,unlocked=False,session_identity=('1',1,':1')),'unknown')
        refusal=lambda locked,browser:namespace['locked_desktop_refusal'](SimpleNamespace(locked=locked,
            grants=SimpleNamespace(browser_only_while_locked=browser)))
        self.assertIsNone(refusal(False,True))
        self.assertEqual(refusal(True,True),'desktop_locked_browser_only')
        self.assertEqual(refusal(True,False),'desktop_unavailable')

    def test_locked_desktop_dispatch_is_refused_before_shared_authority(self):
        server,client=socket.socketpair();client.settimeout(2)
        self.addCleanup(server.close);self.addCleanup(client.close)
        owner=SimpleNamespace(grants=self.access,native_authority=lambda _:None,
            scheduler=SimpleNamespace(post=lambda f,*a:self.callbacks.put(lambda:f(*a))),
            channels=set(),changed=lambda:None,locked_desktop_refusal=lambda:'desktop_locked_browser_only')
        channel=Channel(owner,server,os.getpid(),process_token(os.getpid()))
        channel.authority=lambda:None
        self.addCleanup(channel.close)
        def call(sequence,operation,**fields):
            channel.handle(dict(requestSequence=sequence,requestId=str(sequence),operation=operation,**fields))
            body=b''
            while not body.endswith(b'\n'):body+=client.recv(65536)
            return json.loads(body)
        call(1,'control.open',schema='machine-control-admission/v2',surfaces=['desktop'],reason='Lock fixture',
            waitSeconds=5,durationSeconds=60)
        refused=call(2,'control.dispatch',sessionId='s',resourceGenerations={},request=dict(operation='capture'))
        self.assertEqual(refused['errorCode'],'desktop_locked_browser_only')

    def test_snapshot_without_policy_is_off(self):
        self.host.stop()
        self.assertFalse(self.access.snapshot()['available'])

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
        opened=call(1,'control.open',schema='machine-control-admission/v2',surfaces=['desktop'],reason='Channel fixture',waitSeconds=5,durationSeconds=60)
        self.assertTrue(opened['accepted']);self.assertEqual(opened['data']['state'],'offered')
        self.assertEqual((opened['schema'],opened['errorCode']),('machine-control-admission-channel/v2',None))
        self.assertTrue(call(2,'control.heartbeat')['accepted'])
        # A replayed sequence is refused in the channel schema, then closes.
        refused=call(2,'control.status')
        self.assertEqual((refused['schema'],refused['accepted'],refused['errorCode'],refused['data']),
            ('machine-control-admission-channel/v2',False,'invalid_request_sequence',None))
        self.assertEqual(client.recv(65536),b'')
        self.assertTrue(channel.closed.wait(2))
        self.drain_until_closed(channel)
        self.assertNotIn(channel.label,self.access.owners)

    def drain_until_closed(self,channel):
        """close() sets `closed` before it posts cleanup from the reader
        thread; run posted callbacks until that cleanup arrives."""
        for _ in range(20):
            if channel.label not in self.access.owners:return
            try:self.callbacks.get(timeout=0.1)()
            except queue.Empty:pass

    def failed_open(self,**fields):
        server,client=socket.socketpair();client.settimeout(2)
        self.addCleanup(server.close);self.addCleanup(client.close)
        owner=SimpleNamespace(grants=self.access,native_authority=lambda _:None,
            scheduler=SimpleNamespace(post=lambda f,*a:self.callbacks.put(lambda:f(*a))),
            channels=set(),changed=lambda:None)
        channel=Channel(owner,server,os.getpid(),process_token(os.getpid()))
        channel.authority=lambda:None
        self.addCleanup(channel.close)
        frame=dict(operation='control.open',requestId='open',schema='machine-control-admission/v2',
            surfaces=['desktop'],reason='Channel fixture',waitSeconds=5,durationSeconds=60)
        frame.update(fields)
        channel.handle({key:value for key,value in frame.items() if value is not None})
        body=b''
        while not body.endswith(b'\n'):body+=client.recv(65536)
        reply=json.loads(body)
        self.assertEqual(set(reply),{'schema','requestId','accepted','errorCode','data'})
        self.assertEqual((reply['schema'],reply['accepted']),('machine-control-admission-channel/v2',False))
        self.assertEqual(client.recv(65536),b'')
        self.assertTrue(channel.closed.wait(2))
        self.assertIsNone(channel.intent)
        return reply['errorCode']

    def test_closing_unopened_or_closed_owners_sends_nothing(self):
        sent=[];original=self.access.send
        self.access.send=lambda method,**fields:(sent.append(method),original(method,**fields))[1]
        self.access.close('never-opened')
        self.submit('twice');self.access.close('twice');self.access.close('twice')
        self.assertEqual(sent.count('close'),1)

    def test_open_refusals_use_the_common_vocabulary(self):
        for fields,code in [
            (dict(schema='machine-control-admission/v9'),'unsupported_admission_schema'),
            (dict(surfaces=['desktop','printer']),'invalid_admission_surfaces'),
            (dict(surfaces=[]),'invalid_admission_surfaces'),
            (dict(surfaces=['browser']),'exact_browser_profile_required'),
            (dict(profileIds=['work']),'invalid_browser_profiles'),
            (dict(profileIds='work'),'invalid_browser_profiles'),
            (dict(operations=['browser.tabs']),'invalid_admission_operations'),
            (dict(operations=['format.disk']),'invalid_admission_operations'),
            (dict(operations=['capabilities']),'invalid_admission_operations'),
            (dict(waitSeconds=None),'invalid_admission_request'),
            (dict(durationSeconds=None),'invalid_admission_request'),
            (dict(durationSeconds=901),'invalid_admission_request'),
            (dict(requestId='r'*81),'invalid_admission_request'),
            (dict(preparedConsole=True),'locked_use_unsupported'),
            (dict(preparedConsole=1),'invalid_prepared_console_request'),
        ]:
            with self.subTest(fields=fields):self.assertEqual(self.failed_open(**fields),code)

    def test_channel_operation_and_renewal_codes(self):
        server,client=socket.socketpair();client.settimeout(2)
        self.addCleanup(server.close);self.addCleanup(client.close)
        owner=SimpleNamespace(grants=self.access,native_authority=lambda _:None,
            scheduler=SimpleNamespace(post=lambda f,*a:self.callbacks.put(lambda:f(*a))),
            channels=set(),changed=lambda:None)
        channel=Channel(owner,server,os.getpid(),process_token(os.getpid()))
        channel.authority=lambda:None
        self.addCleanup(channel.close)
        def call(sequence,operation,**fields):
            channel.handle(dict(requestSequence=sequence,requestId=str(sequence),operation=operation,**fields))
            body=b''
            while not body.endswith(b'\n'):body+=client.recv(65536)
            return json.loads(body)
        opened=call(1,'control.open',schema='machine-control-admission/v2',surfaces=['desktop'],
            operations=['snapshot'],reason='Channel fixture',waitSeconds=5,durationSeconds=60)
        self.assertTrue(opened['accepted'],opened)
        self.assertEqual(call(2,'control.teleport')['errorCode'],'unsupported_admission_operation')
        fence=dict(sessionId='s',resourceGenerations={})
        self.assertEqual(call(3,'control.renew',durationSeconds=0,**fence)['errorCode'],'invalid_renewal_duration')
        self.assertEqual(call(4,'control.renew',durationSeconds=901,**fence)['errorCode'],'invalid_renewal_duration')
        self.assertTrue(call(5,'control.status')['accepted'])

    def test_failed_open_replies_in_channel_schema_and_closes(self):
        self.assertEqual(self.failed_open(schema='machine-control-admission/v9'),'unsupported_admission_schema')
        self.assertEqual(self.failed_open(requestSequence=2),'invalid_request_sequence')

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
        opened=call(0,'control.open',schema='machine-control-admission/v2',surfaces=['desktop'],reason='Channel fixture',waitSeconds=5,durationSeconds=60)
        self.assertTrue(opened['accepted']);self.assertEqual(opened['data']['state'],'offered')
        self.assertEqual(opened['data']['requestSequencing'],'strict')
        self.assertTrue(call(1,'control.heartbeat')['accepted'])
        self.assertEqual(call(1,'control.status')['errorCode'],'invalid_request_sequence')
        self.assertTrue(channel.closed.wait(2))
        self.drain_until_closed(channel)
        self.assertNotIn(channel.label,self.access.owners)
