"""Real Unix/stdio framing, EOF and bounded writer behavior."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

SOURCE=Path(__file__).resolve().parents[1]/'host/desktop_channel.py'
spec=importlib.util.spec_from_file_location('desktop_channel',SOURCE)
channel=importlib.util.module_from_spec(spec);spec.loader.exec_module(channel)


@unittest.skipUnless(sys.platform=='linux','Requires Linux Unix peer credentials')
class DesktopChannelTests(unittest.TestCase):
    def setUp(self):
        self.root=tempfile.TemporaryDirectory();self.addCleanup(self.root.cleanup)
        self.path=Path(self.root.name)/'desktop.sock'
        self.listener=socket.socket(socket.AF_UNIX);self.listener.bind(str(self.path));self.path.chmod(0o600)
        self.listener.listen(1);self.listener.settimeout(3);self.addCleanup(self.listener.close)
        self.child=subprocess.Popen([sys.executable,'-B',str(SOURCE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,env={**os.environ,'MACHINE_CONTROL_DESKTOP_SOCKET':str(self.path)})
        self.addCleanup(self.cleanup)
    def cleanup(self):
        if self.child.poll() is None:self.child.kill()
        self.child.wait(3)
        for stream in (self.child.stdin,self.child.stdout):stream.close()
    def test_frames_are_not_forwarded_until_complete_and_eof_closes_owner(self):
        with self.listener.accept()[0] as peer:
            peer.settimeout(.2);self.child.stdin.write(b'{"operation":');self.child.stdin.flush()
            with self.assertRaises(socket.timeout):peer.recv(1)
            self.child.stdin.write(b'"control.status"}\n');self.child.stdin.flush();peer.settimeout(2)
            self.assertEqual(peer.recv(65536),b'{"operation":"control.status"}\n')
            peer.sendall(b'{"accepted":true}\n');self.assertEqual(self.child.stdout.readline(),b'{"accepted":true}\n')
            self.child.stdin.close();self.child.wait(3);self.assertEqual(peer.recv(1),b'')
    def test_oversized_incomplete_frame_closes_without_forwarding(self):
        with self.listener.accept()[0] as peer:
            peer.settimeout(3);self.child.stdin.write(b'x'*65537);self.child.stdin.flush()
            self.child.wait(3);self.assertNotEqual(self.child.returncode,0);self.assertEqual(peer.recv(1),b'')
    def test_socket_with_unsafe_mode_refuses(self):
        # Check the actual stat contract separately from the child connection,
        # whose start may already have observed the original safe mode.
        self.path.chmod(0o666)
        with mock.patch.dict(os.environ,MACHINE_CONTROL_DESKTOP_SOCKET=str(self.path)):
            with self.assertRaises(ValueError):channel.endpoint()
    def test_unread_output_does_not_hold_owner_forever(self):
        with self.listener.accept()[0] as peer:
            peer.settimeout(1)
            def flood():
                try:
                    for _ in range(1024):peer.sendall(b'x'*65536)
                except (OSError,TimeoutError):pass
            writer=threading.Thread(target=flood,daemon=True);writer.start()
            started=time.monotonic();self.child.wait(6)
            self.assertLess(time.monotonic()-started,6);self.assertNotEqual(self.child.returncode,0)
            writer.join(2)
