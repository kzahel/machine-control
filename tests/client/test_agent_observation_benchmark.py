"""Byte budgets are evidence about serialization, never native speed or tokens."""
import unittest

from agent_observation_fixture import benchmark


class ObservationBenchmarkTest(unittest.TestCase):
    def test_same_corpus_compares_full_and_compact_without_native_claims(self):
        report = benchmark()
        self.assertEqual(len(report['measurements']), 6)
        for measurement in report['measurements']:
            stable = measurement['identity'] == 'qualified_fixture_only'
            cases = measurement['cases']
            for case in cases.values():
                self.assertFalse(case['truncation_reported'])
                self.assertGreaterEqual(case['shown_elements'], measurement['elements'])
            unchanged = cases['unchanged']
            self.assertEqual(unchanged['all_no_change'], stable)
            if stable:
                self.assertLess(unchanged['rendered_json_bytes'], unchanged['full_rendered_json_bytes'])
                self.assertLess(cases['single_value']['rendered_json_bytes'],
                                cases['single_value']['full_rendered_json_bytes'])
            else:
                self.assertEqual(unchanged['rendered_json_bytes'], unchanged['full_rendered_json_bytes'])
            # Structural movement requires an ordered tree, not a misleading
            # no-change sentinel or an unanchored line-only insertion patch.
            for name in ('insertion', 'reorder', 'replacement', 'process_recreation', 'window_recreation'):
                self.assertEqual(cases[name]['rendered_json_bytes'], cases[name]['full_rendered_json_bytes'])
                self.assertFalse(cases[name]['no_change'])


if __name__ == '__main__':
    unittest.main()
