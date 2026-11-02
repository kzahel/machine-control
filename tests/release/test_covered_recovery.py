import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


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


if __name__ == '__main__':
    unittest.main()
