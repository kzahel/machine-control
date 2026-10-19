import importlib.util
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "screensaver_files", Path(__file__).resolve().parents[1] / "scripts/screensaver-files.py"
)
screensaver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screensaver)


class ScreensaverFilesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.destination = self.root / "config/uioverrides/screensavers/quiet-ball"
        self.install = {"action": "install", "assets": {name: name for name in screensaver.ASSETS}}

    def test_reinstall_preserves_configuration_and_unrelated_screensavers(self):
        other = self.destination.parent / "other"
        other.mkdir(parents=True)
        (other / "index.html").write_text("keep")
        screensaver.apply(self.install, self.root)
        screensaver.apply({"action": "configure", "settings": {"brightness": 0, "size": 64}}, self.root)
        result = screensaver.apply(self.install, self.root)
        self.assertEqual(result["settings"]["brightness"], 0)
        self.assertEqual(result["settings"]["size"], 64)
        self.assertEqual((other / "index.html").read_text(), "keep")

    def test_invalid_values_are_rejected_before_writing(self):
        screensaver.apply(self.install, self.root)
        previous = (self.destination / "config.json").read_text()
        for patch in ({"size": float("nan")}, {"brightness": 101}, {"speed": 0}, {"size": True}, {"unknown": 1}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                screensaver.apply({"action": "configure", "settings": patch}, self.root)
        self.assertEqual((self.destination / "config.json").read_text(), previous)

    def test_linked_asset_does_not_overwrite_its_target(self):
        self.destination.mkdir(parents=True)
        outside = self.root / "unrelated.txt"
        outside.write_text("keep")
        (self.destination / "main.js").symlink_to(outside)
        with self.assertRaises(ValueError):
            screensaver.apply(self.install, self.root)
        self.assertEqual(outside.read_text(), "keep")
        self.assertFalse((self.destination / "config.json").exists())

    def test_status_is_read_only_and_does_not_claim_activation(self):
        result = screensaver.apply({"action": "status"}, self.root)
        self.assertFalse(result["installed"])
        self.assertFalse(self.destination.exists())
        self.assertIn("does not prove activation", result["selection"])

    def test_configure_requires_an_install(self):
        with self.assertRaisesRegex(ValueError, "install"):
            screensaver.apply({"action": "configure", "settings": {"mode": "black"}}, self.root)


if __name__ == "__main__":
    unittest.main()
