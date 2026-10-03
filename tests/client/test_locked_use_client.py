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
    def test_delegated_proxy_uses_shipped_native_bundle_executable(self):
        with tempfile.TemporaryDirectory(prefix="mc-packaged-proxy-") as directory:
            contents = Path(directory) / "Machine Control.app/Contents"
            native = contents / "MacOS/macui"
            native.parent.mkdir(parents=True)
            native.touch()
            module = contents / "Resources/mc-cli/platforms/macos/host/machost.py"
            proxy = "/tmp/ya-mc-fixture/control.sock"
            with patch.object(machost, "__file__", str(module)), \
                    patch.dict(machost.os.environ, {"MACHINE_CONTROL_DESKTOP_PROXY":proxy}), \
                    patch.object(machost.os, "execv", side_effect=RuntimeError("exec transferred")) as execute, \
                    patch.object(machost.socket, "socket") as resident:
                with self.assertRaisesRegex(RuntimeError, "exec transferred"):
                    machost.channel()
                execute.assert_called_once_with(str(native.resolve()), [str(native.resolve()), "delegated-channel", proxy])
                resident.assert_not_called()

    def test_delegated_proxy_never_falls_back_to_ambient_resident(self):
        with patch.dict(machost.os.environ, {"MACHINE_CONTROL_DESKTOP_PROXY":"/tmp/ya-mc-fixture/control.sock"}), \
                patch.object(machost.Path, "is_file", return_value=False), \
                patch.object(machost.socket, "socket") as resident:
            with self.assertRaisesRegex(OSError, "Installed native desktop proxy client unavailable"):
                machost.channel()
            resident.assert_not_called()
        with patch.dict(machost.os.environ, {"MACHINE_CONTROL_DESKTOP_PROXY":"foreign"}), \
                patch.object(machost.socket, "socket") as resident:
            with self.assertRaises(ValueError):
                machost.channel()
            resident.assert_not_called()

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
