import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop/native/linux"))
from presentation import Presentation, exchange, runtime_directory


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp.name,
                                                   "XDG_RUNTIME_DIR": self.temp.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.temp.cleanup)

    def test_defaults_all_modes_override_and_persistence(self):
        store = Presentation()
        self.assertEqual(store.state()["profile"], "personal")
        for profile in ["personal", "minimal", "appliance"]:
            store.set(profile)
            self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
            store.close()
            store = Presentation(override="personal")
            self.assertEqual(store.setting, profile)
            self.assertTrue(store.state()["temporaryOverride"])
            store.close()
            store = Presentation()
            self.assertEqual(store.state()["profile"], profile)
        store.close()

    def test_invalid_preferences_and_busy_runtime_refuse_offline_edits(self):
        store = Presentation()
        store.path.write_text('{"schema":"bad"}')
        store.path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "busy"):
            Presentation()
        store.close()
        store = Presentation()
        self.assertEqual(store.state()["profile"], "personal")
        self.assertTrue(store.state()["diagnostic"])
        store.set("personal")
        self.assertIsNone(store.state()["diagnostic"])
        store.close()

    def test_wrong_owner_permissions_and_symlink_refusal(self):
        root = Path(self.temp.name) / "machine-control"
        root.mkdir(mode=0o755)
        with self.assertRaises(ValueError):
            Presentation()
        root.chmod(0o700)
        store = Presentation()
        store.close()
        store.path.symlink_to(Path(self.temp.name) / "other")
        broken = Presentation()
        self.assertTrue(broken.state()["diagnostic"])
        broken.close()

    def test_uncertain_live_exchange_is_never_replayed_offline(self):
        endpoint = runtime_directory() / "operator.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(endpoint))
            listener.listen()
            seen = []
            def server():
                client, _ = listener.accept()
                with client:
                    seen.append(client.recv(4096))
            worker = threading.Thread(target=server)
            worker.start()
            with self.assertRaises(ValueError):
                exchange("desktop", {"method": "presentation", "profile": "minimal"})
            worker.join()
        self.assertEqual(len(seen), 1)
        self.assertFalse((Path(self.temp.name) / "machine-control/presentation.json").exists())

    def test_fifo_preferences_refuse_without_blocking(self):
        store = Presentation()
        store.close()
        os.mkfifo(store.path, 0o600)
        unsafe = Presentation()
        self.assertTrue(unsafe.state()["diagnostic"])
        self.assertEqual(unsafe.state()["profile"], "personal")
        unsafe.close()

    def test_instance_names_and_cli_without_gtk(self):
        path = Path(__file__).resolve().parents[2] / "desktop/native/linux/presentation.py"
        for action in [["set", "appliance"], ["status"], ["reset"]]:
            completed = subprocess.run([sys.executable, str(path), *action, "--instance", "fixture"],
                                       capture_output=True, text=True, check=True)
            self.assertTrue(json.loads(completed.stdout)["ok"])
        for value in ["../example", "", "-bad", "a" * 49]:
            with self.assertRaises(ValueError):
                runtime_directory(value)


if __name__ == "__main__":
    unittest.main()
