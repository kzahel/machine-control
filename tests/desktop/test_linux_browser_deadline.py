"""The Linux transport delegates routing and deadlines to the real child."""
from pathlib import Path
import queue
import sys
import threading
from types import SimpleNamespace
import unittest
import test_linux_policy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'desktop/native/linux'))
from browser import Browser
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

    def test_policy_exit_fences_existing_browser_authority(self):
        self.browser.stopped=False
        authority=dict(generation=self.browser.generation,revoked=threading.Event(),validate=lambda:None)
        self.assertTrue(self.browser.valid(authority))
        self.host.stop()
        self.assertFalse(self.browser.valid(authority))
        replies=[];self.browser.execute(dict(operation='browser.tabs'),replies.append,authority)
        self.assertEqual(replies[0]['errorCode'],'control_policy_unavailable')
