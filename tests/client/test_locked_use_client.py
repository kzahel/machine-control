import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("locked_use_machost",
    Path(__file__).resolve().parents[2] / "platforms/macos/host/machost.py")
machost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(machost)


class LockedUseConnectionTests(unittest.TestCase):
    def test_connection_stays_open_and_heartbeats_until_task_end(self):
        with tempfile.TemporaryDirectory(prefix="mc-session-") as directory:
            path = str(Path(directory) / "control.sock")
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(path)
            listener.listen(1)
            observed = []

            def resident():
                try:
                    peer, _ = listener.accept()
                    with peer:
                        stream = peer.makefile("rb")
                        observed.append(json.loads(stream.readline()))
                        peer.sendall(b'{"accepted":true,"data":{"phase":"waiting_for_lock"}}\n')
                        observed.append(json.loads(stream.readline()))
                        # The final result, rather than initial acceptance,
                        # is returned to the common CLI when the task ends.
                        peer.sendall(b'{"accepted":true,"data":{"reason":"completed","lockObserved":true}}\n')
                finally:
                    listener.close()

            thread = threading.Thread(target=resident, daemon=True)
            thread.start()
            with patch.object(machost, "socket_path", return_value=path):
                final = machost.call({"operation":"session.control", "durationSeconds":30})
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(observed[0]["operation"], "session.control")
            self.assertEqual(observed[1], {"operation":"heartbeat"})
            self.assertEqual(final["data"]["reason"], "completed")
            self.assertTrue(final["data"]["lockObserved"])


if __name__ == "__main__":
    unittest.main()
