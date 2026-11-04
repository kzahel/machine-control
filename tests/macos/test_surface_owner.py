"""The live acceptance owner must heartbeat while a native action is pending."""
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest

spec = importlib.util.spec_from_file_location(
    'surface_actor', Path(__file__).with_name('surface-policy-live.py'))
actor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actor)


class OwnerTransportTests(unittest.TestCase):
    def test_pending_dispatch_does_not_block_heartbeat(self):
        with tempfile.TemporaryDirectory(prefix='mc-owner-', dir='/tmp') as root:
            path = str(Path(root) / 'owner.sock')
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(path)
                listener.listen(1)
                errors = []
                heartbeats = []

                def server():
                    try:
                        with listener.accept()[0] as peer, peer.makefile('rb') as stream:
                            peer.settimeout(10)
                            deferred = None
                            sequence = 0
                            for line in stream:
                                request = json.loads(line)
                                self.assertEqual(request['requestSequence'], sequence + 1)
                                sequence += 1
                                operation = request['operation']
                                if operation == 'control.dispatch':
                                    deferred = request
                                    continue
                                if operation == 'control.heartbeat':
                                    heartbeats.append(operation)
                                view = dict(state='active', sessionId='session:test',
                                            resourceGenerations={'desktop': 1})
                                peer.sendall(json.dumps(dict(accepted=True,
                                    requestId=request['requestId'], data=view)).encode() + b'\n')
                                if deferred and len(heartbeats) >= 2:
                                    peer.sendall(json.dumps(dict(accepted=True,
                                        requestId=deferred['requestId'], data={'accepted': True})).encode() + b'\n')
                                    deferred = None
                                if operation == 'control.cancel':
                                    break
                    except BaseException as error:
                        errors.append(error)

                worker = threading.Thread(target=server)
                worker.start()
                with actor.Owner(path, 'fixture-claim', ['desktop']) as owner:
                    self.assertTrue(owner.call('snapshot')['accepted'])
                    self.assertGreaterEqual(len(heartbeats), 2)
                worker.join(10)
                self.assertFalse(worker.is_alive())
                if errors:
                    raise errors[0]
