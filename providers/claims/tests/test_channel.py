from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('test_channel_claims', ROOT / 'providers/claims/claims.py')
claims = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(claims)


class ClaimChannelTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.directory = Path(self.temporary.name)
        audit_env = mock.patch.dict(os.environ, {"MACHINE_CONTROL_AUDIT_DIR": str(self.directory / "audit-history")})
        audit_env.start()
        self.addCleanup(audit_env.stop)
        self.children = []
        self.fixture = self.directory / 'fixture.py'
        self.effects = self.directory / 'effects.txt'
        self.fixture.write_text('''import sys, pathlib
for line in sys.stdin:
 with pathlib.Path(sys.argv[1]).open('a') as file: file.write(line)
 print(line, end='', flush=True)
''')
        self.identifier = self.acquire(2)
    def tearDown(self):
        for child in self.children:
            if child.poll() is None: child.terminate()
            child.communicate(timeout=5)
        self.temporary.cleanup()
    def options(self, command, extra):
        return claims.parser().parse_args(['--state-dir',str(self.directory),
            '--minimum-duration','1','--default-duration','2','--maximum-duration','10',
            '--maximum-lifetime','10',command,'--provider','fixture','--resource-id','exact-fixture',*extra])
    def acquire(self, seconds):
        options = self.options('acquire', ['--duration-seconds',str(seconds),'--reason','Channel fixture',
            '--claimant-authority','test','--claimant-id','owner'])
        return claims.command_acquire(options)['data']['claim']['claimId']
    def start(self):
        child = subprocess.Popen([sys.executable,str(ROOT / 'providers/claims/channel.py'),
            '--state-dir',str(self.directory),'--provider','fixture','--resource-id','exact-fixture',
            '--claim-id',self.identifier,'--',sys.executable,str(self.fixture),str(self.effects)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.children.append(child); return child
    def send(self, child, identifier):
        line = json.dumps({'requestId':identifier}).encode()+b'\n'
        child.stdin.write(line); child.stdin.flush()
        self.assertEqual(child.stdout.readline(),line)
    def test_raw_channel_expires_without_client_poll_and_never_renews(self):
        child = self.start(); self.send(child,'one')
        child.wait(timeout=5)
        self.assertEqual(child.returncode,1)
        self.assertIn(b'claim_expired',child.stderr.read())
        self.assertEqual(len(self.effects.read_text().splitlines()),1)
        state = claims.command_status(self.options('status',[]))
        self.assertEqual(state['data']['state'],'available')
        with self.assertRaises(claims.ClaimError):
            claims.command_check(self.options('check',['--claim-id',self.identifier]))
    def test_released_or_replaced_claim_closes_existing_transport(self):
        child = self.start(); self.send(child,'one')
        claims.command_release(self.options('release',['--claim-id',self.identifier]))
        replacement = self.acquire(3)
        child.wait(timeout=5)
        self.assertEqual(child.returncode,1)
        self.assertEqual(len(self.effects.read_text().splitlines()),1)
        self.assertEqual(claims.command_check(self.options('check',['--claim-id',replacement]))['data']['claimId'],replacement)
    def test_external_renewal_keeps_channel_live_but_does_not_replay_frames(self):
        child = self.start(); self.send(child,'one')
        time.sleep(1)
        claims.command_renew(self.options('renew',['--claim-id',self.identifier,'--duration-seconds','4']))
        time.sleep(1.2); self.send(child,'two')
        child.stdin.close(); child.stdin = None
        child.wait(timeout=5)
        self.assertEqual(len(self.effects.read_text().splitlines()),2)
    def test_stale_claim_refuses_before_launching_the_transport(self):
        claims.command_release(self.options('release',['--claim-id',self.identifier]))
        child=self.start(); child.wait(timeout=5)
        self.assertEqual(child.returncode,1); self.assertFalse(self.effects.exists())
    def test_oversized_frame_is_not_forwarded(self):
        child=self.start(); child.stdin.write(b'x' * 65537); child.stdin.flush()
        child.wait(timeout=5)
        self.assertEqual(child.returncode,1); self.assertFalse(self.effects.exists())


if __name__ == '__main__': unittest.main()
