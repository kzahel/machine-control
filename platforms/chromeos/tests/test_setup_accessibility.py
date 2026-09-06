"""Check the target setup helper without ChromeOS or an active browser."""
import runpy
from pathlib import Path
import sys
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/setup-accessibility.py'


class SetupAccessibilityTests(unittest.TestCase):
    def load(self, cdp):
        with mock.patch.dict(sys.modules, {'cdp': cdp}):
            return runpy.run_path(str(SCRIPT))

    def test_browser_connection_closes_http_transport(self):
        cdp = mock.Mock()
        helper = self.load(cdp)
        with mock.patch.object(helper['browser_connection'].__globals__['http'].client, 'HTTPConnection') as connection:
            connection.return_value.getresponse.return_value.read.return_value = b'{"webSocketDebuggerUrl":"ws://fixture.invalid/browser"}'
            self.assertIs(helper['browser_connection'](), cdp.CDP.return_value)
            connection.return_value.close.assert_called_once()
            cdp.CDP.assert_called_once_with('ws://fixture.invalid/browser')

    def test_existing_provider_preserves_preferences_and_windows(self):
        cdp = mock.Mock()
        helper = self.load(cdp)
        helper['main']()
        cdp.CDP.assert_not_called()
        cdp.list_targets.assert_not_called()
