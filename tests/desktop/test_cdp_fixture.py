"""The live fixture must distinguish WebSocket closure from mere silence."""
import importlib.util
from pathlib import Path
import socket
import unittest

spec = importlib.util.spec_from_file_location('cdp_fixture', Path(__file__).resolve().parents[1] / 'windows/cdp_socket.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CdpClosureTests(unittest.TestCase):
    def client(self, connection):
        client = module.CdpSocket.__new__(module.CdpSocket)
        client.socket = connection
        return client

    def test_eof_confirms_closure(self):
        connection, peer = socket.socketpair()
        with connection:
            peer.close()
            self.client(connection).wait_closed(.1)

    def test_buffered_event_then_eof_confirms_closure(self):
        connection, peer = socket.socketpair()
        with connection:
            peer.sendall(b'\x81\x02{}')
            peer.close()
            self.client(connection).wait_closed(.1)

    def test_silent_open_peer_is_not_closure(self):
        connection, peer = socket.socketpair()
        with connection, peer:
            with self.assertRaisesRegex(AssertionError, 'did not close'):
                self.client(connection).wait_closed(.02)


if __name__ == '__main__':
    unittest.main()
