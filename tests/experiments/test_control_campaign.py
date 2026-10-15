import copy
import os
import signal
import time
import types
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from urllib.parse import urlencode

import control_campaign as campaign


IDENTITY = {'service': {'version': 'fixture'}, 'artifacts': {'fixture': {'sha256': 'a' * 64}},
            'commands': {'os': {'stdout': 'fixture'}}, 'configSha256': 'b' * 64}
RUNTIME = {'status': 'matched', 'observedFingerprint': campaign.fingerprint(IDENTITY),
           'referenceFingerprint': campaign.fingerprint(IDENTITY)}


def write_runtime(root, identity=None):
    trial = root/'run-fixture/task/route-1'
    trial.mkdir(parents=True, exist_ok=True)
    (trial/'runtime.json').write_text(json.dumps(identity or IDENTITY))
    (root/'run-fixture/runtime-reference.json').write_text(json.dumps(identity or IDENTITY))
    return trial


def receipt(plan, cell, **changes):
    return {'provider': plan['profile']['provider'], 'requestedModel': plan['profile']['model'],
            'requestedEffort': plan['profile']['effort'], 'instructionProfile': cell['arm'],
            'task': cell['task'], 'route': cell['route'], 'repetition': 1,
            'fixtureSeed': cell['fixtureSeed'], 'validTrial': True,
            'profileQualification': {'qualified': True}, 'passed': True,
            'oracleExit': 0, 'oracle': {'passed': True}, 'released': 'discarded',
            'credentialVerification': 'inherited_base_bytes_equal_mode_0600',
            'routeReview': {'routeAdherence': 'conforming', 'confirmationPolicyAdherence': 'conforming'},
            'agentSeconds': 10, 'toolCalls': 4, 'toolOutputBytes': 80,
            'tokenUsage': {'input_tokens': 100, 'cached_input_tokens': 60, 'output_tokens': 20}, **changes}


class CampaignTest(unittest.TestCase):
    def setUp(self):
        self.plan = campaign.make_plan('revision', 'codex', 'exact-model', 'medium',
                                       ['machine-control', 'mc-python'], 128)

    def test_seeded_balanced_paired_arms_and_bounded_matrix(self):
        self.assertEqual(len(self.plan['rows']), 48)
        self.assertEqual(sum(r['stage'] == 'pilot' for r in self.plan['rows']), 12)
        self.assertEqual(self.plan, campaign.make_plan('revision', 'codex', 'exact-model', 'medium',
                         ['machine-control', 'mc-python'], 128))
        changed = campaign.make_plan('revision', 'codex', 'exact-model', 'medium',
                                    ['machine-control', 'mc-python'], 129)
        self.assertNotEqual(self.plan['rows'], changed['rows'])
        for task in campaign.TASKS:
            for repetition in (1, 2, 3, 4):
                rows = [r for r in self.plan['rows'] if r['task'] == task and r['repetition'] == repetition]
                self.assertEqual(len(rows), 3)
                self.assertEqual(len({r['fixtureSeed'] for r in rows}), 1)
                self.assertEqual({r['arm'] for r in rows if r['route'] == 'machine-control'}, set(campaign.ARMS))
                self.assertEqual([r['arm'] for r in rows if r['route'] == 'mc-python'], ['current'])
        for routes in (['mc-python'], ['machine-control'] * 2,
                       ['machine-control', 'mc-python', 'mc-repl']):
            with self.assertRaises(ValueError):
                campaign.make_plan('r', 'codex', 'm', 'medium', routes, 1)
        with self.assertRaises(ValueError):
            campaign.make_plan('r', 'claude', 'm', 'medium', ['machine-control', 'computer-use'], 1)

    def test_default_sol_cli_campaign_is_eight_pilot_and_twenty_four_paired(self):
        plan = campaign.make_plan('r', 'codex', 'gpt-6.1-sol', 'medium', ['machine-control'], 128)
        self.assertEqual(len(plan['rows']), 32)
        self.assertEqual(sum(r['stage'] == 'pilot' for r in plan['rows']), 8)
        self.assertEqual(sum(r['heldOut'] for r in plan['rows']), 16)
        self.assertEqual({r['arm'] for r in plan['rows']}, {'discovery', 'quickstart'})
        diagnostic = campaign.make_plan('r', 'codex', 'gpt-6.1-sol', 'medium', ['machine-control'], 128, include_current=True)
        self.assertEqual(len(diagnostic['rows']), 48)

    def test_strict_ui_and_separate_lifecycle(self):
        row = receipt(self.plan, self.plan['rows'][0])
        self.assertTrue(campaign.ui_pass(row))
        self.assertEqual(campaign.lifecycle(row)['doctor'], 'unknown')
        self.assertEqual(campaign.lifecycle(row)['oracle'], 'pass')
        for changes in ({'oracle': {'passed': False}}, {'released': None}, {'tunnelCleanupError': 'left open'},
                        {'profileQualification': {'qualified': False}}, {'routeReview': {}},
                        {'routeReview': {'routeAdherence': 'conforming', 'confirmationPolicyAdherence': 'violated'}}):
            self.assertFalse(campaign.ui_pass({**row, **changes}))
        self.assertEqual(campaign.lifecycle({**row, 'released': None},
            {'disposal': {'status': 'pass', 'evidence': 'assertion'}})['disposal'], 'fail')
        with self.assertRaises(ValueError):
            campaign.lifecycle(row, {'doctor': {'status': 'pass'}})

    def test_aggregation_keeps_failures_unknowns_and_overlapping_usage(self):
        attempts = [{'cell': cell['id'], 'runtime': RUNTIME, 'record': receipt(self.plan, cell)} for cell in self.plan['rows']]
        attempts[0]['record'].update(passed=False, oracle={'passed': False}, agentSeconds=35)
        # Retain an infrastructure failure alongside the qualified result; never erase costs.
        attempts.append({'cell': attempts[1]['cell'], 'runtime': RUNTIME, 'record': {'error': 'setup failed', 'agentSeconds': 5}})
        result = campaign.summarize(self.plan, attempts)
        self.assertTrue(result['qualifiedComplete'])
        self.assertEqual(result['attempts'], 49)
        self.assertEqual(result['uiVerifiedSuccesses'], 47)
        self.assertFalse(result['wholePackageAccepted'])
        self.assertEqual(result['lifecycleAcceptedAttempts'], 0)
        self.assertEqual(sum(g['outcomes']['invalid']['attempts'] for g in result['groups']), 1)
        success = next(g['outcomes']['success'] for g in result['groups'] if g['outcomes']['success']['attempts'])
        self.assertEqual(success['usage']['totalTokens']['median'], 120)
        self.assertEqual(success['usage']['nonCachedInputTokens']['median'], 40)
        self.assertEqual(success['usage']['cachedInputTokens']['median'], 60)
        self.assertIsNone(success['usage']['cacheWriteInputTokens'])
        self.assertTrue(all(p['plannedPairs'] == 12 for p in result['pairedComparisons']))
        self.assertTrue(all(p['bothUIVerified'] == 12 for p in result['pairedComparisons']))  # Pilot excluded.
        # Duplicate qualified results cannot establish completeness.
        attempts.append(copy.deepcopy(attempts[2]))
        self.assertFalse(campaign.summarize(self.plan, attempts)['qualifiedComplete'])

    def test_missing_wrong_profile_and_tampered_plan(self):
        self.assertEqual(campaign.summarize(self.plan, [])['missing'], 48)
        row = self.plan['rows'][0]
        with self.assertRaisesRegex(ValueError, 'identity'):
            campaign.summarize(self.plan, [{'cell': row['id'], 'runtime': RUNTIME, 'record': receipt(self.plan, row, requestedModel='other')}])
        modified = copy.deepcopy(self.plan)
        modified['rows'][0]['arm'] = 'other'
        with self.assertRaisesRegex(ValueError, 'deterministic'):
            campaign.summarize(modified, [])

    def test_offline_report_cli_handles_missing_and_unreviewed_trials(self):
        cell = self.plan['rows'][0]
        result = campaign.summarize(self.plan, [{'cell': cell['id'], 'runtime': RUNTIME, 'record': receipt(self.plan, cell, routeReview={})}])
        self.assertEqual(result['groups'][0]['outcomes']['unverified']['attempts'], 1)
        self.assertEqual(result['uiVerifiedSuccesses'], 0)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            campaign.write_new(directory/'campaign.json', self.plan)
            completed = subprocess.run([sys.executable, str(Path(campaign.__file__)), 'report', temp],
                                       capture_output=True, text=True, check=True)
            report = json.loads(completed.stdout)
            self.assertEqual(report['missing'], 48)
            self.assertFalse(report['wholePackageAccepted'])
            self.assertIn('control_campaign.py', report['evaluatorHashes'])

    def test_driver_failure_after_a_receipt_cannot_be_scored_as_success(self):
        cell = self.plan['rows'][0]
        result = campaign.summarize(self.plan, [{'cell': cell['id'], 'runtime': RUNTIME, 'record': receipt(self.plan, cell),
                                               'driverError': 'journal finish failed'}])
        self.assertEqual(result['uiVerifiedSuccesses'], 0)
        self.assertFalse(result['qualifiedComplete'])
        self.assertEqual(result['groups'][0]['outcomes']['invalid']['attempts'], 1)

    def test_whole_package_requires_lifecycle_and_ui_not_speed(self):
        annotations = {key: {'status': 'pass', 'evidence': 'independent receipt'} for key in campaign.CHECKS}
        attempts = [{'cell': cell['id'], 'runtime': RUNTIME, 'record': receipt(self.plan, cell), 'lifecycle': annotations}
                    for cell in self.plan['rows']]
        self.assertTrue(campaign.summarize(self.plan, attempts)['wholePackageAccepted'])
        attempts[0]['record']['oracle']['passed'] = False
        result = campaign.summarize(self.plan, attempts)
        self.assertTrue(result['lifecycleChecksAccepted'])
        self.assertFalse(result['wholePackageAccepted'])

    def test_runner_boundary_pins_seed_profile_and_stops_on_invalid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for task in campaign.TASKS:
                directory = root/'source/tests/experiments'/('control-scenarios' if task in campaign.HELD_OUT else 'tasks')/task
                directory.mkdir(parents=True)
                (directory/'task.json').write_text(json.dumps({'id': task}))
            result = root/'results'
            result.mkdir()
            seen = []
            def run(args, task, route, index, directory):
                seen.append((args, task, route, index, directory))
                cell = next(r for r in self.plan['rows'] if r['id'] == directory.name)
                return receipt(self.plan, cell, validTrial=False, error='provider failed')
            with self.assertRaisesRegex(RuntimeError, 'Unqualified'):
                campaign.run_stage(root/'source', self.plan, result, 'pilot', SimpleNamespace(target='example'),
                                   SimpleNamespace(run_trial=run))
            self.assertEqual(len(seen), 1)
            args, task, route, index, directory = seen[0]
            self.assertEqual((args.seed, args.model, args.revision), (128, 'exact-model', 'revision'))
            self.assertEqual(args.instructions, self.plan['rows'][0]['arm'])
            self.assertEqual(json.loads((directory/'attempt.json').read_text())['record']['error'], 'provider failed')
            with self.assertRaises(FileExistsError):
                campaign.run_stage(root/'source', self.plan, result, 'pilot', SimpleNamespace(), SimpleNamespace(run_trial=run))

    def test_pre_receipt_exception_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            def broken(*args):
                raise RuntimeError('acquire interrupted')
            with self.assertRaises(FileNotFoundError):
                campaign.run_stage(Path(temp), self.plan, Path(temp), 'pilot', SimpleNamespace(), SimpleNamespace(run_trial=broken))
            path = next(Path(temp).glob('cell-*/attempt.json'))
            attempt = json.loads(path.read_text())
            self.assertIn('driverError', attempt)
            self.assertFalse(campaign.clean(attempt['record']))

    def test_pause_stop_and_pilot_gate_are_offline(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory/'stop').touch()
            with self.assertRaisesRegex(RuntimeError, 'Stopped between'):
                campaign.run_stage(directory, self.plan, directory, 'pilot', SimpleNamespace(), None)
            self.assertFalse(list(directory.glob('cell-*')))
            with self.assertRaisesRegex(ValueError, 'continue gate'):
                campaign.require_pilot_review(directory, self.plan)
            (directory/'continue').touch()
            campaign.write_new(directory/'campaign.json', self.plan)
            campaign.write_new(directory/'runtime-reference.json', IDENTITY)
            campaign.write_new(directory/'pilot-review.json', {
                'campaignSha256': campaign.digest(directory/'campaign.json'),
                'evidenceHashes': campaign.pilot_evidence_hashes(directory), 'decision': 'continue', 'notes': 'reviewed'})
            attempts = [{'cell': cell['id'], 'runtime': RUNTIME, 'record': receipt(self.plan, cell)}
                        for cell in self.plan['rows'] if cell['stage'] == 'pilot']
            with patch.object(campaign, 'load_attempts', return_value=attempts):
                campaign.require_pilot_review(directory, self.plan)
                attempts[0]['record']['routeReview'] = {}
                with self.assertRaisesRegex(ValueError, 'route/policy'):
                    campaign.require_pilot_review(directory, self.plan)
            # A pause waits only between trials and an explicit stop cancels the wait.
            (directory/'stop').unlink()
            (directory/'pause').touch()
            def request_stop(*args):
                (directory/'stop').touch()
            with patch.object(campaign.time, 'sleep', side_effect=request_stop) as sleep:
                with self.assertRaisesRegex(RuntimeError, 'Stopped between'):
                    campaign.run_stage(directory, self.plan, directory, 'pilot', SimpleNamespace(), None)
                sleep.assert_called_once_with(1)

    def test_receipt_mutation_and_unbound_acceptance_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cell = self.plan['rows'][0]
            trial = root/cell['id']/'trial'
            trial.mkdir(parents=True)
            raw = trial/'trial.json'
            raw.write_text(json.dumps(receipt(self.plan, cell)))
            attempt = {'cell': cell['id'], 'trial': str(trial.relative_to(root)), 'receiptSha256': campaign.digest(raw)}
            campaign.write_new(trial.parent/'attempt.json', attempt)
            (trial.parent/'acceptance.json').write_text(json.dumps({'receiptSha256': 'wrong', 'checks': {}}))
            with self.assertRaisesRegex(ValueError, 'receipt-bound'):
                campaign.load_attempts(root, self.plan)
            (trial.parent/'acceptance.json').unlink()
            raw.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'changed'):
                campaign.load_attempts(root, self.plan)


class RuntimeAndInvocationTest(unittest.TestCase):
    def setUp(self):
        self.plan = campaign.make_plan('revision', 'codex', 'exact-model', 'medium', ['machine-control'], 128)

    def prepare_source(self, root):
        for cell in self.plan['rows']:
            task = root/'source/tests/experiments'/cell['taskRoot']/cell['task']
            task.mkdir(parents=True, exist_ok=True)
            (task/'task.json').write_text(json.dumps({'id': cell['task']}))
        directory = root/'results'
        directory.mkdir()
        return directory

    def runner(self, identity=None, missing=False):
        def run(args, task, route, index, root):
            cell = next(c for c in self.plan['rows'] if c['id'] == root.name)
            trial = write_runtime(root, identity)
            (trial/'trial.json').write_text(json.dumps(receipt(self.plan, cell)))
            if missing:
                (trial/'runtime.json').unlink()
            return receipt(self.plan, cell)
        return SimpleNamespace(run_trial=run)

    def test_runtime_pin_survives_pilot_to_paired_and_binds_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.prepare_source(root)
            campaign.run_stage(root/'source', self.plan, directory, 'pilot', SimpleNamespace(), self.runner())
            pinned = (directory/'runtime-reference.json').read_bytes()
            hashes = campaign.pilot_evidence_hashes(directory)
            self.assertIn('runtime-reference.json', hashes)
            self.assertTrue(any(name.endswith('/runtime.json') for name in hashes))
            campaign.run_stage(root/'source', self.plan, directory, 'paired', SimpleNamespace(), self.runner())
            self.assertEqual((directory/'runtime-reference.json').read_bytes(), pinned)
            attempts = campaign.load_attempts(directory, self.plan)
            self.assertEqual(len(attempts), 32)
            self.assertEqual(attempts[0]['runtime']['status'], 'pinned')
            self.assertTrue(all(campaign.runtime_qualified(a['runtime']) for a in attempts))
            # Replacing the reference invalidates retained evidence, not just the next cell.
            (directory/'runtime-reference.json').write_text(json.dumps({**IDENTITY, 'configSha256': 'changed'}))
            with self.assertRaisesRegex(ValueError, 'runtime evidence changed'):
                campaign.load_attempts(directory, self.plan)

    def test_drift_in_paired_stage_preserves_attempt_and_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.prepare_source(root)
            campaign.run_stage(root/'source', self.plan, directory, 'pilot', SimpleNamespace(), self.runner())
            changed = {**IDENTITY, 'service': {'version': 'different'}}
            with self.assertRaisesRegex(RuntimeError, 'Unqualified'):
                campaign.run_stage(root/'source', self.plan, directory, 'paired', SimpleNamespace(), self.runner(changed))
            paths = sorted(directory.glob('cell-*/attempt.json'))
            self.assertEqual(len(paths), 9)
            drifting = json.loads(paths[-1].read_text())
            self.assertEqual(drifting['runtime']['status'], 'mismatch')
            self.assertTrue((directory/drifting['trial']/'runtime.json').exists())
            self.assertEqual(drifting['record']['tokenUsage']['input_tokens'], 100)
            result = campaign.summarize(self.plan, campaign.load_attempts(directory, self.plan))
            self.assertEqual(sum(g['outcomes']['invalid']['attempts'] for g in result['groups']), 1)
            self.assertEqual(result['uiVerifiedSuccesses'], 0)  # Real route reviews absent.

    def test_missing_fingerprint_or_reference_never_repins(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.prepare_source(root)
            with self.assertRaisesRegex(RuntimeError, 'Unqualified'):
                campaign.run_stage(root/'source', self.plan, directory, 'pilot', SimpleNamespace(), self.runner(missing=True))
            attempt = json.loads(next(directory.glob('cell-*/attempt.json')).read_text())
            self.assertEqual(attempt['runtime']['status'], 'missing')
            self.assertTrue((directory/attempt['trial']/'trial.json').exists())
            self.assertFalse((directory/'runtime-reference.json').exists())
            paired = next(c for c in self.plan['rows'] if c['stage'] == 'paired')
            trial_root = directory/paired['id']
            trial_root.mkdir()
            write_runtime(trial_root)
            check = campaign.check_runtime(directory, trial_root)
            self.assertEqual(check['status'], 'missing')
            self.assertIn('refusing to repin', check['error'])
            self.assertFalse((directory/'runtime-reference.json').exists())

    def test_full_invocation_time_on_success_exit_failure_and_spawn_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name, code in [('success', 0), ('failure', 7)]:
                root = directory/name
                root.mkdir()
                command = [sys.executable, '-c', f'import time; time.sleep(.06); raise SystemExit({code})']
                if code:
                    with self.assertRaisesRegex(RuntimeError, 'exited 7'):
                        campaign.execute_runner(command, directory, root)
                else:
                    campaign.execute_runner(command, directory, root)
                timing = json.loads((root/'invocation.json').read_text())
                self.assertGreaterEqual(timing['runnerInvocationSeconds'], .06)
                self.assertEqual(timing['returncode'], code)
            root = directory/'spawn-failure'
            root.mkdir()
            with self.assertRaises(FileNotFoundError):
                campaign.execute_runner([str(root/'absent-executable')], directory, root)
            timing = json.loads((root/'invocation.json').read_text())
            self.assertGreaterEqual(timing['runnerInvocationSeconds'], 0)
            self.assertIn('FileNotFoundError', timing['error'])

    def test_driver_failure_timing_is_retained_and_old_wall_is_labeled(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.prepare_source(root)
            def run(args, task, route, index, cell_root):
                cell = self.plan['rows'][0]
                trial = write_runtime(cell_root)
                value = receipt(self.plan, cell, wallSeconds=2)
                (trial/'trial.json').write_text(json.dumps(value))
                campaign.execute_runner([sys.executable, '-c', 'import time; time.sleep(.06); raise SystemExit(3)'], root, cell_root)
            with self.assertRaisesRegex(RuntimeError, 'exited 3'):
                campaign.run_stage(root/'source', self.plan, directory, 'pilot', SimpleNamespace(), SimpleNamespace(run_trial=run))
            attempts = campaign.load_attempts(directory, self.plan)
            self.assertEqual(len(attempts), 1)
            self.assertGreaterEqual(attempts[0]['runnerInvocationSeconds'], .06)
            resources = campaign.summarize(self.plan, attempts)['groups'][0]['outcomes']['invalid']['resources']
            self.assertGreaterEqual(resources['runnerInvocationSeconds']['sum'], .06)
            self.assertEqual(resources['postAcquisitionPreCleanupSeconds']['sum'], 2)
            self.assertNotIn('wallSeconds', resources)

    @unittest.skipUnless(os.name == 'posix', 'POSIX terminal process group signals')
    def test_terminal_group_signals_wait_for_isolated_child_cleanup_and_stop_scheduling(self):
        child_code = """import json,os,sys,time
from pathlib import Path
root=Path(sys.argv[1])
(root/'ready.tmp').write_text(json.dumps({'pid':os.getpid(),'group':os.getpgrp()}))
(root/'ready.tmp').replace(root/'ready.json')
while not (root/'release').exists(): time.sleep(.01)
time.sleep(.05)
(root/'cleanup').write_text('finished normally')
"""
        driver_code = """import json,signal,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
import control_campaign as campaign
import test_control_campaign as fixtures
root=Path(sys.argv[2]);plan=json.loads((root/'plan.json').read_text())
def stop(signum,frame): campaign.STOP_REQUESTED=True
signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
def run(args,task,route,index,cell_root):
    cell=plan['rows'][0]
    trial=fixtures.write_runtime(cell_root)
    (trial/'trial.json').write_text(json.dumps(fixtures.receipt(plan,cell)))
    campaign.execute_runner([sys.executable,'-c',sys.argv[3],str(root)],root,cell_root)
    return fixtures.receipt(plan,cell)
try:
    campaign.run_stage(root/'source',plan,root/'results','pilot',SimpleNamespace(),SimpleNamespace(run_trial=run))
except RuntimeError as error:
    if 'Stopped between' not in str(error): raise
    (root/'stopped').write_text('after cleanup')
"""
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=signum), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.prepare_source(root)
                (root/'plan.json').write_text(json.dumps(self.plan))
                driver = subprocess.Popen([sys.executable, '-c', driver_code, str(Path(campaign.__file__).parent),
                                           str(root), child_code], start_new_session=True,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                child_pid = None
                try:
                    deadline = time.monotonic() + 5
                    while not (root/'ready.json').exists():
                        if driver.poll() is not None or time.monotonic() > deadline:
                            self.fail('Fake runner did not become ready')
                        time.sleep(.01)
                    child = json.loads((root/'ready.json').read_text())
                    child_pid = child['pid']
                    self.assertNotEqual(child['group'], os.getpgid(driver.pid))
                    os.killpg(os.getpgid(driver.pid), signum)
                    time.sleep(.08)
                    self.assertIsNone(driver.poll())  # Parent is still waiting for cleanup.
                    self.assertFalse((root/'cleanup').exists())
                    (root/'release').touch()
                    stdout, stderr = driver.communicate(timeout=5)
                    self.assertEqual(driver.returncode, 0, stderr)
                    self.assertEqual((root/'cleanup').read_text(), 'finished normally')
                    self.assertTrue((root/'stopped').exists())
                    attempts = list((root/'results').glob('cell-*/attempt.json'))
                    self.assertEqual(len(attempts), 1)
                    attempt = json.loads(attempts[0].read_text())
                    self.assertGreater(attempt['runnerInvocationSeconds'], .08)
                    with self.assertRaises(ProcessLookupError):
                        os.kill(child_pid, 0)  # Reaped; no blind orphaning.
                finally:
                    (root/'release').touch(exist_ok=True)
                    try:
                        driver.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        driver.kill()
                        driver.communicate()
                    if child_pid:
                        try:
                            os.kill(child_pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass


class HeldOutTest(unittest.TestCase):
    def load(self, name):
        path = Path(__file__).parent/'control-scenarios'/name/'fixture.py'
        module = types.ModuleType(name.replace('-', '_'))
        exec(compile(path.read_text(), str(path), 'exec'), module.__dict__)
        return module

    def test_finder_requires_correct_target_bytes_and_unchanged_decoy(self):
        fixture = self.load('finder-decoy')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'fixture'
            fixture.setup(root, 'seed')
            self.assertFalse(fixture.oracle(root)['passed'])
            (root/'incoming/draft.txt').rename(root/'archive/reviewed.txt')
            self.assertTrue(fixture.oracle(root)['passed'])
            (root/'decoy/draft.txt').write_text('wrong')
            self.assertFalse(fixture.oracle(root)['passed'])
            with self.assertRaises(FileExistsError):
                fixture.setup(root, 'seed')

    def test_form_missing_wrong_duplicate_and_exact_effects(self):
        fixture = self.load('browser-form')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'fixture'
            fixture.setup(root, 'seed')
            expected = json.loads((root/'expected.json').read_text())
            self.assertFalse(fixture.oracle(root)['passed'])
            fixture.observe_submission(root, urlencode({**expected, 'category': 'draft'}))
            self.assertFalse(fixture.oracle(root)['passed'])
            (root/'submissions.jsonl').unlink()
            fixture.observe_submission(root, urlencode(expected))
            self.assertTrue(fixture.oracle(root)['passed'])
            fixture.observe_submission(root, urlencode(expected))
            self.assertFalse(fixture.oracle(root)['passed'])
            other = Path(temp)/'other'
            fixture.setup(other, 'other-seed')
            self.assertNotEqual(expected['nonce'], json.loads((other/'expected.json').read_text())['nonce'])


if __name__ == '__main__':
    unittest.main()
