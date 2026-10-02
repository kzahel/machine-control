#!/usr/bin/env python3
"""XDG registration preservation and native executable parsing/launch evidence."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'desktop/native/linux'))
from startup import Startup


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root / 'config'))
        env.start()
        self.addCleanup(env.stop)
        self.executable = self.root / 'app with spaces'
        self.executable.write_text('#!/bin/sh\nexit 0\n')
        self.executable.chmod(0o700)
        self.startup = Startup(self.executable)

    def test_opt_in_atomic_private_registration_and_removal(self):
        self.assertFalse(self.startup.enabled)
        self.startup.set(True)
        self.assertTrue(self.startup.enabled)
        self.assertEqual(self.startup.path.stat().st_mode & 0o777, 0o600)
        self.startup.set(False)
        self.assertFalse(self.startup.path.exists())

    def test_foreign_and_symlink_entries_are_preserved(self):
        path = self.startup.path
        path.parent.mkdir(parents=True)
        path.write_text('foreign entry')
        self.assertFalse(self.startup.enabled)
        for enabled in [False, True]:
            with self.assertRaises(ValueError): self.startup.set(enabled)
        self.assertEqual(path.read_text(), 'foreign entry')
        path.unlink()
        path.symlink_to(self.executable)
        with self.assertRaises(ValueError): self.startup.set(True)
        self.assertTrue(path.is_symlink())

    @unittest.skipUnless(sys.platform == 'linux', 'native Linux GIO required')
    def test_native_launch_preserves_reserved_path_characters(self):
        from gi.repository import Gio
        import shlex
        for name in ['app with spaces', 'app"quoted', 'app$dollar', 'app`tick', 'app\\slash', 'app%percent']:
            executable = self.root / name
            marker = self.root / 'launched'
            marker.unlink(missing_ok=True)
            executable.write_text('#!/bin/sh\ntest "$1" = --background || exit 1\ntouch ' + shlex.quote(str(marker)) + '\n')
            executable.chmod(0o700)
            startup = Startup(executable)
            startup.set(True)
            try:
                entry = Gio.DesktopAppInfo.new_from_filename(str(startup.path))
            except TypeError as error:
                raise AssertionError(name + " failed native parsing: " + startup.path.read_text()) from error
            self.assertIsNotNone(entry, name)
            self.assertTrue(entry.launch([], None), name)
            deadline = time.monotonic() + 3
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(marker.exists(), name)
            startup.set(False)


if __name__ == '__main__':
    unittest.main()
