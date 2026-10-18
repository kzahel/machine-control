"""Transport boundary regressions; native effects are covered by live.py."""
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

spec = importlib.util.spec_from_file_location('android_spike_session', Path(__file__).with_name('session.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TransportTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        self.addCleanup(self.listener.close)
        self.receipt = Path(self.directory.name)/'grant.json'
        self.receipt.write_text(json.dumps({'schema':'mc-android-spike/v1','token':'fixture-only',
            'generation':'generation-one','port':self.listener.getsockname()[1]}))
        self.receipt.chmod(0o600)
        self.seen = []

    def peer(self, action):
        def serve():
            connection,_ = self.listener.accept()
            with connection, connection.makefile('rwb') as stream:
                self.seen.append(json.loads(stream.readline()))
                stream.write(json.dumps({'accepted':True,'generation':'generation-one'}).encode()+b'\n')
                stream.flush()
                self.seen.append(json.loads(stream.readline()))
                action(stream)
        thread = threading.Thread(target=serve,daemon=True)
        thread.start()
        self.addCleanup(lambda: thread.join(2))

    def test_unknown_delivery_closes_and_does_not_replay(self):
        self.peer(lambda stream: None)
        transport = module.AndroidTransport(self.receipt)
        with self.assertRaises(module.SessionError) as lost:
            transport.call({'operation':'action','reference':'fresh','action':'press'})
        self.assertEqual(lost.exception.delivered,'unknown')
        with self.assertRaises(module.SessionError):
            transport.call({'operation':'action','reference':'fresh','action':'press'})
        self.assertEqual(len(self.seen),2)
        self.assertEqual(self.seen[0]['operation'],'open')

    def test_generation_change_never_becomes_accepted_result(self):
        def changed(stream):
            stream.write(b'{"accepted":true,"generation":"replacement"}\n');stream.flush()
        self.peer(changed)
        transport = module.AndroidTransport(self.receipt)
        with self.assertRaises(module.SessionError) as lost:
            transport.call({'operation':'snapshot'})
        self.assertEqual(lost.exception.code,'bridge_lost')
        self.assertTrue(transport.closed)

    def test_native_refusal_ends_ownership_and_preserves_code(self):
        def refused(stream):
            stream.write(b'{"accepted":false,"generation":"generation-one","errorCode":"approval_denied","delivery":"refused"}\n')
            stream.flush()
        self.peer(refused)
        transport = module.AndroidTransport(self.receipt)
        result = transport.call({'operation':'snapshot'})
        self.assertEqual(result['errorCode'],'approval_denied')
        self.assertTrue(transport.closed)

    def test_receipt_symlink_and_broad_permissions_are_refused(self):
        link = self.receipt.with_name('link.json'); link.symlink_to(self.receipt)
        for path in (link,self.receipt):
            if path == self.receipt: path.chmod(0o644)
            with self.assertRaises(module.SessionError) as invalid:
                module.AndroidTransport(path)
            self.assertEqual(invalid.exception.code,'invalid_receipt')

    def test_stale_reference_refusal_keeps_live_connection_for_fresh_observation(self):
        def stale(stream):
            stream.write(b'{"accepted":false,"generation":"generation-one","errorCode":"stale_reference","sessionClosed":false,"delivery":"refused"}\n')
            stream.flush()
        self.peer(stale)
        transport = module.AndroidTransport(self.receipt)
        self.addCleanup(transport.close)
        result = transport.call({'operation':'action','reference':'old'})
        self.assertFalse(result['accepted'])
        self.assertFalse(transport.closed)


class DataDiscoveryTest(unittest.TestCase):
    def test_data_tool_discovery_needs_neither_grant_nor_native_service(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory)/'never-created.json'
            requests = [
                {'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},
                {'jsonrpc':'2.0','id':2,'method':'tools/list'},
            ]
            result = subprocess.run([sys.executable,str(Path(__file__).with_name('session.py')),
                '--receipt',str(missing),'--plane','data'],
                input=''.join(json.dumps(r)+'\n' for r in requests),text=True,
                capture_output=True,check=True,timeout=10)
            replies = [json.loads(line) for line in result.stdout.splitlines()]
            description = replies[1]['result']['tools'][0]['description']
            self.assertIn('phone.photos()',description)
            self.assertIn('concurrently',description)
            self.assertFalse(missing.exists())


if __name__ == '__main__': unittest.main()
