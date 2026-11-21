"""The Linux transport delegates routing and deadlines to the real child."""
from pathlib import Path
import queue
import socket
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest import mock
import test_linux_policy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'desktop/native/linux'))
from browser import Browser, Peer
from policy import Policy


@unittest.skipIf(sys.platform == 'win32', 'Requires POSIX Linux-adapter process and pipe semantics')
class BrowserBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_linux_policy.SharedPolicyTests.setUpClass()
        cls.root=test_linux_policy.SharedPolicyTests.root

    def setUp(self):
        self.callbacks=queue.Queue()
        self.host=Policy(lambda f,*a:self.callbacks.put(lambda:f(*a)),lambda _:None,lambda _:None,root=self.root)
        self.addCleanup(self.host.stop)
        self.owner=SimpleNamespace(policy=self.host,inhibit=threading.Event(),
            grants=SimpleNamespace(view={}),scheduler=SimpleNamespace(post=lambda f,*a:self.callbacks.put(lambda:f(*a))),
            provider=SimpleNamespace(fail=lambda req,op,code,msg:dict(accepted=False,errorCode=code),
                envelope=lambda req,op:dict(accepted=True,operation=op)))
        self.browser=Browser(self.owner)

    def test_plain_effects_require_a_live_owner_before_enqueue(self):
        replies=[]
        self.browser.execute(dict(operation='browser.eval'),replies.append)
        self.assertEqual(replies,[dict(accepted=False,errorCode='control_session_required')])
        self.assertEqual(self.browser.authorities,{})

    def test_profiles_use_actual_shared_registry_without_native_authority(self):
        replies=[]
        self.browser.execute(dict(operation='browser.profiles'),replies.append)
        while not replies:self.callbacks.get(timeout=2)()
        self.assertTrue(replies[0]['accepted'])
        self.assertEqual(replies[0]['data']['profiles'],[])

    def test_endpoints_reuse_authority_and_failed_first_lookup_releases_it(self):
        profile=self.host.call(dict(method='browser.attach',extensionId='a'*32,hello=self.hello()))['profileId']
        self.owner.grants.view={'surfaces':{'browser':{'mode':'automatic','ready':True}}}
        self.browser.configure([profile],None,True)
        authority=dict(owner='fixture-owner',session='fixture-session',profiles=[profile],validate=lambda:None)

        def endpoint(selector):
            replies=[]
            self.browser.execute(dict(operation='browser.endpoint',browserProfileId=selector),replies.append,authority)
            while not replies:self.callbacks.get(timeout=2)()
            return replies[0]

        self.assertFalse(endpoint('unknown-profile')['accepted'])
        self.assertEqual(self.browser.authorities,{})

        overlapping=[]
        for selector in ('unknown-profile',profile):
            self.browser.execute(dict(operation='browser.endpoint',browserProfileId=selector),overlapping.append,authority)
        self.assertEqual(len(self.browser.authorities),1)
        while len(overlapping)<2:self.callbacks.get(timeout=2)()
        self.assertFalse(overlapping[0]['accepted'])
        first=overlapping[1]
        self.assertTrue(first['accepted'],first.get('errorCode'))
        self.assertFalse(endpoint('unknown-profile')['accepted'])
        for _ in range(20):
            self.assertEqual(endpoint(profile)['data']['browserEndpoint'],first['data']['browserEndpoint'])
        self.assertEqual(len(self.browser.authorities),1)
        self.browser.event(dict(type='access.event',event='ended',sessionId=authority['session']))
        self.assertEqual(self.browser.authorities,{})

    @staticmethod
    def hello():
        return dict(type='hello',protocolVersion=1,extensionVersion='fixture',profile=dict(
            protocolVersion=1,installationId='00000000-0000-4000-8000-000000000001',name='Fixture',enabled=True))

    def test_disconnect_before_attach_completion_releases_profile(self):
        peer,remote=socket.socketpair()
        with peer,remote:
            self.browser.peers[peer]=Peer(peer,'a'*32)
            completed=[]
            self.browser.message(peer,self.hello(),lambda:completed.append(True))
            self.assertTrue(self.browser.peers[peer].attaching)
            self.browser.disconnect(peer)
            # A synchronous call is a pipe barrier without running any of the
            # coordinator callbacks, including the abandoned attach reply.
            registry=self.host.call(dict(method='browser.call',requestId='profiles',authorityId='metadata',
                                         request=dict(operation='browser.profiles')))
            self.assertFalse(registry['data']['profiles'][0]['connected'])
            replacement=self.host.call(dict(method='browser.attach',extensionId='a'*32,hello=self.hello()))
            self.assertEqual(replacement['profileId'],registry['data']['profiles'][0]['profileId'])
            while not completed:self.callbacks.get(timeout=2)()
            self.assertEqual(self.browser.peers,{})

    def test_claim_attribution_reaches_the_shared_runtime_unchanged(self):
        claim='c-'+'a1'*12
        request=dict(operation='browser.release',requestId='owned',ownerClaimId=claim,
                     owner=dict(claimId=claim,leaseSeconds=60,sessionRef='fixture-agent'))
        authority=dict(owner='fixture-owner',session='fixture-session',profiles=['fixture-profile'],validate=lambda:None)
        sent=[]
        # Native-state publication is covered elsewhere; only routing matters here.
        with mock.patch.object(self.browser,'sync'), \
                mock.patch.object(self.host,'request',side_effect=lambda frame,*_,**__:sent.append(frame)):
            self.browser.execute(dict(request),lambda _:None,authority)
        self.assertEqual(sent[0]['method'],'browser.call')
        self.assertEqual(sent[0]['request'],request)

    def test_policy_exit_fences_existing_browser_authority(self):
        self.browser.stopped=False
        authority=dict(generation=self.browser.generation,revoked=threading.Event(),validate=lambda:None)
        self.assertTrue(self.browser.valid(authority))
        self.host.stop()
        self.assertFalse(self.browser.valid(authority))
        replies=[];self.browser.execute(dict(operation='browser.tabs'),replies.append,authority)
        self.assertEqual(replies[0]['errorCode'],'control_policy_unavailable')
