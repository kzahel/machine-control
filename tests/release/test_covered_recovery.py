import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, call, patch


spec = importlib.util.spec_from_file_location('covered_recovery',
    Path(__file__).resolve().parents[1] / 'macos/covered-recovery.py')
covered = importlib.util.module_from_spec(spec)
spec.loader.exec_module(covered)


class SavedModelOracle(unittest.TestCase):
    def context(self, saves):
        self.checks = []
        return {
            'last_saved_model': {'tab': 1, 'value': 'owned fixture', 'saves': 1},
            'effects': {'saved': 'owned fixture', 'modelSaves': saves},
            'poll': lambda predicate, *_args, **_kwargs: predicate(),
            'raw': lambda *_args: {'accepted': True},
            'call': lambda *_args, **_kwargs: {
                'value': {'value': 'owned fixture', 'model': 'owned fixture'}},
            'check': self.checks.append,
        }

    def test_same_value_duplicate_save_is_not_mistaken_for_success(self):
        for saves in [0, 2]:
            with self.subTest(saves=saves), patch.object(covered.time, 'monotonic', return_value=0):
                with self.assertRaisesRegex(AssertionError, 'HTTP save'):
                    covered.verify_saved_model(self.context(saves), 'completion')
                self.assertEqual(self.checks, [])

    def test_single_save_and_exact_model_pass_passive_check(self):
        context = self.context(1)
        with patch.object(covered.time, 'monotonic', side_effect=[0, 0, 3]), \
                patch.object(covered.time, 'sleep'):
            covered.verify_saved_model(context, 'completion')
        self.assertEqual(len(self.checks), 1)

    def test_browser_preflight_reobserves_a_generation_refusal(self):
        context = self.context(1)
        refusal = ValueError('Browser capability observation was refused')
        refusal.code = 'control_generation_changed'
        refusal.data = {'accepted': False, 'delivery': 'not_applicable', 'uncertainty': 'none'}
        context['raw'] = Mock(side_effect=[refusal, {'accepted': True}])

        def poll(predicate, *_args, **_kwargs):
            self.assertFalse(predicate())
            self.assertTrue(predicate())

        context['poll'] = poll
        with patch.object(covered.time, 'monotonic', side_effect=[0, 0, 3]), \
                patch.object(covered.time, 'sleep'):
            covered.verify_saved_model(context, 'completion')
        self.assertEqual(context['raw'].call_args_list, [call('browser.tabs'), call('browser.tabs')])
        self.assertEqual(len(self.checks), 1)

    def test_other_browser_preflight_errors_propagate(self):
        for code, accepted, delivery, uncertainty in [
            ('not_authorized', False, 'refused', 'none'),
            ('control_generation_changed', True, 'not_applicable', 'none'),
            ('control_generation_changed', False, 'confirmed', 'none'),
            ('control_generation_changed', False, 'refused', 'interrupted_after_possible_dispatch'),
        ]:
            with self.subTest(code=code, accepted=accepted, delivery=delivery, uncertainty=uncertainty):
                context = self.context(1)
                refusal = ValueError('Browser capability observation was refused')
                refusal.code = code
                refusal.data = {'accepted': accepted, 'delivery': delivery, 'uncertainty': uncertainty}
                context['raw'] = Mock(side_effect=refusal)
                with self.assertRaises(ValueError) as raised:
                    covered.verify_saved_model(context, 'completion')
                self.assertIs(raised.exception, refusal)
                context['raw'].assert_called_once_with('browser.tabs')
                self.assertEqual(self.checks, [])


if __name__ == '__main__':
    unittest.main()
