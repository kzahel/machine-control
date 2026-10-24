import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('acceptance',
    Path(__file__).resolve().parents[2] / 'desktop/scripts/packaged-acceptance.py')
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


class Acceptance(unittest.TestCase):
    def setUp(self):
        self.scope = dict(revision='a' * 40, version='0.6.9', run='123.2')
        self.receipt = {'schema': 'machine-control-packaged-acceptance/v0',
            'sourceRevision': 'a' * 40, 'version': '0.6.9', 'candidateRun': '123.2',
            'archiveSHA256': 'b' * 64, 'seed': 3407, 'checks': 35, 'cycles': 5,
            'soakSeconds': 120, 'coverage': sorted(acceptance.COVERAGE),
            'cleanupVerified': True, 'passed': True}
        self.build = {'schema': 'machine-control-desktop-build/v0', 'sourceState': 'ci_checkout',
            'bundleIdentifier': 'org.machine-control.app', 'sourceRevision': 'a' * 40,
            'version': '0.6.9', 'workflowRun': '123', 'workflowAttempt': '2',
            'artifacts': [{'name': 'MachineControl_0.6.9_arm64.app.tar.gz', 'sha256': 'b' * 64}]}

    def test_exact_bytes_and_bounded_execution(self):
        acceptance.validate(self.receipt, self.build, **self.scope)
        with self.assertRaises(ValueError):
            acceptance.validate([], self.build, **self.scope)
        with self.assertRaises(ValueError):
            acceptance.validate(self.receipt, [], **self.scope)
        for field, value in [('sourceRevision', 'c' * 40), ('version', '0.7.0'),
                             ('candidateRun', '123.1'), ('archiveSHA256', 'c' * 64),
                             ('checks', True), ('cycles', 2), ('soakSeconds', 0),
                             ('cleanupVerified', False), ('passed', False),
                             ('coverage', ['downloads']), ('target', 'private-host')]:
            with self.subTest(field=field):
                changed = dict(self.receipt, **{field: value})
                with self.assertRaises(ValueError):
                    acceptance.validate(changed, self.build, **self.scope)

    def test_development_foreign_architecture_and_replaced_candidate_refused(self):
        for field, value in [('sourceState', 'local_working_tree'), ('sourceRevision', 'c' * 40),
                             ('workflowAttempt', '3'), ('artifacts', []),
                             ('artifacts', [{'name': 'MachineControl_0.6.9_x86_64.app.tar.gz', 'sha256': 'b' * 64}])]:
            with self.subTest(field=field):
                changed = dict(copy.deepcopy(self.build), **{field: value})
                with self.assertRaises(ValueError):
                    acceptance.validate(self.receipt, changed, **self.scope)
        changed = copy.deepcopy(self.build)
        changed['artifacts'][0]['sha256'] = 'd' * 64
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            acceptance.validate(self.receipt, changed, **self.scope)


if __name__ == '__main__':
    unittest.main()
