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

    def test_new_release_requires_sustained_reliability_and_closed_profile(self):
        scope = dict(self.scope, version='0.6.11')
        receipt = dict(self.receipt, version='0.6.11')
        with self.assertRaisesRegex(ValueError, 'reliability'):
            acceptance.validate_envelope(receipt, **scope)
        receipt.update(schema='machine-control-packaged-acceptance/v1',
            coverage=sorted(acceptance.COVERAGE | acceptance.RELIABILITY_COVERAGE),
            reliability={'coveredDurationSeconds':900, 'renewableOwnerSeconds':960,
                         'sipEnabled':False, 'onlineDisplays':1,
                         'stopRelaunchUI':True,'coldBootChoices':True})
        acceptance.validate_envelope(receipt, **scope)
        for field, value in [('coveredDurationSeconds', 60), ('renewableOwnerSeconds', 900),
                             ('sipEnabled', 'enabled'), ('onlineDisplays', True), ('target', 'private'),
                             ('stopRelaunchUI',False),('coldBootChoices',False)]:
            changed = copy.deepcopy(receipt)
            changed['reliability'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                acceptance.validate_envelope(changed, **scope)
        changed = dict(receipt, cleanupVerified=False)
        with self.assertRaises(ValueError):
            acceptance.validate_envelope(changed, **scope)

    def test_disposal_is_bound_to_the_same_successful_scope(self):
        spec = importlib.util.spec_from_file_location('reliability',
            Path(__file__).resolve().parents[1] / 'macos/reliability-acceptance.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        start = dict(schema='machine-control-run/v0', event='acquired',
                     claimId='one', workspaceHandle='workspace', logicalTarget='example')
        end = dict(start, event='finished', outcome='completed', exitCode=0, childExitCode=0,
                   cleanup={'claim':'released', 'workspace':'released'})
        runner.finished_scope([start, end])
        for value in [dict(end, workspaceHandle='other'), dict(end, childExitCode=1),
                      dict(end, outcome='interrupted'), dict(end, cleanup={'claim':'released','workspace':'unknown'})]:
            with self.assertRaises(ValueError):
                runner.finished_scope([start, value])
        with self.assertRaises(ValueError):
            runner.finished_scope([start, end, end])

    def test_standard_timing_requires_a_new_release_and_the_complete_pair(self):
        for version, expiry, renewal, accepted in [
            ('0.7.6', 60, 120, False),
            ('0.7.7', 60, 120, True),
            ('0.7.7', 900, 960, True),
            ('0.7.7', 60, 119, False),
            ('0.7.7', 60, 960, False),
            ('0.7.7', 900, 120, False),
        ]:
            with self.subTest(version=version, expiry=expiry, renewal=renewal):
                scope = dict(self.scope, version=version)
                receipt = dict(self.receipt, version=version,
                    schema='machine-control-packaged-acceptance/v1',
                    coverage=sorted(acceptance.COVERAGE | acceptance.RELIABILITY_COVERAGE),
                    reliability={'coveredDurationSeconds': expiry, 'renewableOwnerSeconds': renewal,
                                 'sipEnabled': False, 'onlineDisplays': 1,
                                 'stopRelaunchUI': True, 'coldBootChoices': True})
                if accepted:
                    acceptance.validate_envelope(receipt, **scope)
                else:
                    with self.assertRaisesRegex(ValueError, 'reliability timing'):
                        acceptance.validate_envelope(receipt, **scope)

    def test_smoke_receipt_binds_the_exact_package_and_closed_coverage(self):
        scope = dict(self.scope, version='0.7.7')
        build = dict(self.build, version='0.7.7',
                     artifacts=[{'name': 'MachineControl_0.7.7_arm64.app.tar.gz', 'sha256': 'b' * 64}])
        receipt = {key: self.receipt[key] for key in acceptance.SMOKE_FIELDS}
        receipt.update(schema=acceptance.SMOKE_SCHEMA, version='0.7.7',
                       coverage=sorted(acceptance.SMOKE_COVERAGE))
        acceptance.validate(receipt, build, **scope)
        for changes in [
            {'archiveSHA256': 'c' * 64}, {'candidateRun': '123.1'}, {'cleanupVerified': False},
            {'coverage': receipt['coverage'][1:]}, {'coverage': sorted(acceptance.RELIABILITY_COVERAGE)},
            {'target': 'private'}, {'passed': False},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                acceptance.validate(dict(receipt, **changes), build, **scope)
        with self.assertRaisesRegex(ValueError, 'starts with desktop 0.7.7'):
            acceptance.validate_envelope(dict(receipt, version='0.7.6'), **dict(scope, version='0.7.6'))


if __name__ == '__main__':
    unittest.main()
