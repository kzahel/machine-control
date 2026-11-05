"""Actual pinned policy plus hostile framing; no GTK or Python policy model."""
import importlib.util
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'desktop/native/linux'))
from policy import Policy, PolicyError


@unittest.skipIf(sys.platform == 'win32', 'Requires POSIX Linux-adapter process and pipe semantics')
class TransportTests(unittest.TestCase):
    def fixture(self, mode):
        callbacks=queue.Queue()
        host=Policy(lambda f,*a:callbacks.put(lambda:f(*a)),lambda _:None,lambda _:None,
                    root=ROOT,command=[sys.executable,'-I',str(Path(__file__).with_name('linux-policy-fixture.py')),mode])
        self.addCleanup(host.stop)
        return host

    def test_reply_does_not_need_coordinator_and_environment_is_cleared(self):
        host=self.fixture('environment')
        data=host.call({'method':'inspect'})
        self.assertNotIn('HOME',data['keys'])
        self.assertNotIn('PATH',data['keys'])
        self.assertNotIn('NODE_OPTIONS',data['keys'])
        # Python may add LC_CTYPE itself; the parent contributes no environment.

    def test_malformed_reply_and_truncated_frame_fence_and_reap(self):
        for mode in ['bad-reply','partial']:
            with self.subTest(mode=mode):
                host=self.fixture(mode)
                with self.assertRaises(PolicyError):host.call({'method':'inspect'},timeout=.5)
                self.assertTrue(host.reaped.wait(2))
                self.assertIsNotNone(host.process.poll())
                with self.assertRaises(PolicyError):host.call({'method':'again'})

    def test_reply_deadline_kills_without_replay(self):
        host=self.fixture('timeout')
        with self.assertRaisesRegex(PolicyError,'ipc_reply_timeout'):
            host.call({'method':'inspect'},timeout=.1)
        self.assertTrue(host.reaped.wait(2))

    def test_stderr_flood_is_drained(self):
        host=self.fixture('stderr')
        self.assertEqual(host.call({'method':'inspect'}),{})

    def test_informational_completion_does_not_replace_or_duplicate_rpc(self):
        host=self.fixture('finished')
        self.assertEqual(host.call({'method':'inspect'}),{'completed':True})
        self.assertTrue(host.alive)
        self.assertEqual(host.call({'method':'inspect'}),{'completed':True})

    def test_blocked_writer_is_bounded_and_reaped(self):
        host=self.fixture('no-read')
        started=time.monotonic()
        with self.assertRaises(PolicyError):host.call({'method':'inspect','padding':'x'*1048576},timeout=5)
        self.assertLess(time.monotonic()-started,5)
        self.assertTrue(host.reaped.wait(2))


@unittest.skipIf(sys.platform == 'win32', 'Requires POSIX Linux-adapter process and pipe semantics')
class SharedPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Explicitly stage the real pinned native child, without a global-Node
        # fallback or a silently skipped conformance test.
        cls.root=ROOT/'.artifacts/linux-policy-native-tests'
        spec=importlib.util.spec_from_file_location('policy_package',ROOT/'runtime/scripts/package.py')
        package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
        import platform
        arch={'arm64':'arm64','aarch64':'arm64','x86_64':'x64'}[platform.machine().lower()]
        target={'darwin':'darwin','linux':'linux'}[sys.platform]+'-'+arch
        import shutil
        if cls.root.exists():shutil.rmtree(cls.root)
        cache=ROOT/'.artifacts/runtime-cache';cache.mkdir(parents=True,exist_ok=True)
        package.build('node',target,cls.root,cache,None)

    def test_packaged_usr_share_layout_does_not_use_a_system_node(self):
        import os
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            prefix=Path(temporary)/'usr'
            native=prefix/'lib/machine-control/linux-runtime';native.mkdir(parents=True)
            for name in ('policy.py','policy_exec.py'):
                shutil.copyfile(ROOT/'desktop/native/linux'/name,native/name)
            shared=prefix/'share/machine-control/shared-policy'
            shutil.copytree(self.root,shared)
            spec=importlib.util.spec_from_file_location('installed_policy',native/'policy.py')
            installed=importlib.util.module_from_spec(spec);spec.loader.exec_module(installed)
            host=installed.Policy(lambda *_:None,lambda _:None,lambda _:None)
            try:self.assertEqual(host.call({'method':'access.state'})['schema'],'machine-control-admission/v2')
            finally:host.stop()
            # A corrupt explicit staging tree fails closed, rather than quietly
            # selecting another interpreter or an ambient/global Node binary.
            (native/'shared-policy').mkdir()
            with self.assertRaises(installed.PolicyError):
                installed.Policy(lambda *_:None,lambda _:None,lambda _:None)

    def test_actual_core_owns_modes_offer_session_and_stop(self):
        callbacks=queue.Queue()
        host=Policy(lambda f,*a:callbacks.put(lambda:f(*a)),lambda _:None,lambda _:None,root=self.root)
        self.addCleanup(host.stop)
        def call(method,**fields):return host.call(dict(method='access.'+method,**fields))
        call('input-ready',ready=True)
        call('ready',surface='desktop',ready=True,noticeVisible=True)
        call('notice',milliseconds=0)
        call('configure',surface='desktop',configuration=dict(mode='automatic',durationMs=None))
        call('open',owner='fixture')
        offered=call('submit',owner='fixture',request=dict(requestId='one',surfaces=['desktop'],profileIds=[],
            reason='Fixture',waitMs=10000,durationMs=60000))
        self.assertEqual(offered['state'],'offered')
        active=call('accept',owner='fixture',intentId=offered['intentId'],offerGeneration=offered['offerGeneration'])
        fence=dict(intentId=active['intentId'],sessionId=active['sessionId'],resourceGenerations=active['resourceGenerations'])
        self.assertIsNone(call('authorize',owner='fixture',fence=fence,operation='snapshot')['refusal'])
        call('stop')
        ended=call('inspect',owner='fixture',intentId=active['intentId'])
        self.assertEqual(ended['state'],'ended')
        self.assertIsNotNone(call('authorize',owner='fixture',fence=fence,operation='snapshot')['refusal'])
        self.assertEqual(call('query')['surfaces']['desktop']['mode'],'off')
