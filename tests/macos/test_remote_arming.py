"""The reattachment check observes readiness without replaying an action."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, call


spec = importlib.util.spec_from_file_location('remote_arming', Path(__file__).with_name('remote-arming.py'))
remote_arming = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote_arming)


class DialogReattachmentTests(unittest.TestCase):
    def test_pending_observer_must_report_ready_before_passing(self):
        status = Mock(side_effect=[
            {'observerState': 'pending', 'state': 'not_observed'},
            {'observerState': 'ready', 'state': 'not_observed'},
        ])

        def poll(observe, _label, *, timeout):
            self.assertEqual(timeout, 5)
            self.assertFalse(observe())
            return observe()

        self.assertTrue(remote_arming.wait_for_dialog_reattachment(status, poll, 17))
        self.assertEqual(status.call_args_list, [call('browser.dialog', tabId=17)] * 2)

    def test_failed_observer_or_open_dialog_stops_immediately(self):
        def poll(observe, _label, *, timeout):
            return observe()

        for observer, state in [('failed', 'not_observed'), ('pending', 'open'), ('ready', 'open')]:
            with self.subTest(observer=observer, state=state):
                status = Mock(return_value={'observerState': observer, 'state': state})
                with self.assertRaises(AssertionError):
                    remote_arming.wait_for_dialog_reattachment(status, poll, 17)
                status.assert_called_once_with('browser.dialog', tabId=17)


if __name__ == '__main__':
    unittest.main()
