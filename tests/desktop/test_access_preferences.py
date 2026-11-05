"""Persistence carries operator choices, not grants; unsafe files are refused."""
import importlib.util
from pathlib import Path
import os
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('access_preferences',Path(__file__).resolve().parents[2]/'desktop/native/linux/access_preferences.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class AccessPreferencesTests(unittest.TestCase):
    def test_restart_keeps_return_approval_and_immediate_choice(self):
        with tempfile.TemporaryDirectory() as root:
            store=module.AccessPreferences(root,'fixture')
            self.assertIsNone(store.read())
            value=dict(desktopNoticeSeconds=0,browserNoticeSeconds=30,yieldWaitSeconds=10,yieldReapprove=True)
            store.set(value)
            self.assertEqual(module.AccessPreferences(root,'fixture').read(),value)
            self.assertEqual(store.path.stat().st_mode&0o777,0o600)
            self.assertNotIn('grant',store.path.read_text())
    def test_symlink_and_public_file_never_supply_preferences(self):
        with tempfile.TemporaryDirectory() as root:
            store=module.AccessPreferences(root,'fixture'); target=Path(root)/'other'
            target.write_text('private content'); store.path.symlink_to(target)
            self.assertIsNone(store.read())
            with self.assertRaises(ValueError):store.set({})
            self.assertEqual(target.read_text(),'private content')
            store.path.unlink();store.path.write_text('{}');os.chmod(store.path,0o644)
            self.assertIsNone(store.read())
            with self.assertRaises(ValueError):store.set({})

if __name__=='__main__':unittest.main()
