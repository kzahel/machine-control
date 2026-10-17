"""Transport boundary regressions; native effects are covered by live.py."""
import importlib.util
import json
from pathlib import Path
import socket
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


if __name__ == '__main__': unittest.main()
