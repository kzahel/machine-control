"""Offline pinning and CLI boundary tests for optional campaign inputs."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import route_comparison as route
from agent_profiles import DEFAULT_MODELS


class PinnedInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.file = self.root / 'fixtures/example/prompt.md'
        self.file.parent.mkdir(parents=True)
        self.file.write_bytes(b'frozen task')
        self.tree = b'100644 blob fixture-blob\tfixtures/example/prompt.md\0'
        patch.object(route, 'ROOT', self.root).start()
        self.git = patch.object(subprocess, 'check_output', side_effect=self.read_git).start()
        self.addCleanup(patch.stopall)

    def read_git(self, command, **kwargs):
        self.assertEqual(kwargs['cwd'], self.root)
        if command[1] == 'ls-tree':
            self.assertEqual(command[4], 'pin')
            return self.tree
        self.assertEqual(command, ['git', 'cat-file', 'blob', 'fixture-blob'])
        return b'frozen task'

    def test_file_and_task_tree_pins_include_exact_bytes(self):
        expected = {'fixtures/example/prompt.md': hashlib.sha256(b'frozen task').hexdigest()}
        self.assertEqual(route.pinned_input(self.file, 'pin')['hashes'], expected)
        self.assertEqual(route.pinned_input(self.root / 'fixtures', 'pin', directory=True)['hashes'], expected)

    def test_changed_untracked_linked_and_outside_inputs_refuse(self):
        self.file.write_bytes(b'edited')
        with self.assertRaisesRegex(ValueError, 'differs'):
            route.pinned_input(self.file, 'pin')
        self.file.write_bytes(b'frozen task')
        extra = self.file.parent / 'untracked.md'
        extra.write_bytes(b'untracked')
        with self.assertRaisesRegex(ValueError, 'untracked'):
            route.pinned_input(self.root / 'fixtures', 'pin', directory=True)
        extra.unlink()
        self.tree = self.tree.replace(b'100644', b'120000')
        with self.assertRaisesRegex(ValueError, 'regular tracked'):
            route.pinned_input(self.file, 'pin')
        with self.assertRaisesRegex(ValueError, 'within the pinned'):
            route.pinned_input(self.root.parent, 'pin', directory=True)

    def test_untracked_instruction_file_refuses(self):
        self.tree = b''
        with self.assertRaisesRegex(ValueError, 'untracked'):
            route.pinned_input(self.file, 'pin')


class InputProfileTests(unittest.TestCase):
    def args(self, **overrides):
        values = dict(provider='claude', model=DEFAULT_MODELS['claude'], instructions='skill', revision='pin')
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_skill_cannot_swap_fixture_tree_or_supply_hidden_instructions(self):
        with self.assertRaisesRegex(ValueError, 'public guide only'):
            route.trial_inputs(self.args(task_root=route.TASKS.parent), {'id': 'textedit-save'}, 'sky-external')
        with self.assertRaisesRegex(ValueError, 'public guide only'):
            route.trial_inputs(self.args(instruction_file=route.TASKS / 'common-chrome.sh'),
                               {'id': 'textedit-save'}, 'sky-external')

    def test_instruction_file_restricted_to_mc_and_frozen_defaults_need_no_override(self):
        with self.assertRaisesRegex(ValueError, 'only to machine-control'):
            route.trial_inputs(self.args(instructions='current', instruction_file=Path('file')),
                               {'id': 'textedit-save'}, 'sky-external')
        for instruction in ['current', 'discovery', 'quickstart']:
            self.assertEqual(route.trial_inputs(self.args(instructions=instruction),
                             {'id': 'textedit-save'}, 'sky-external'), route.TASKS)

    def test_invalid_profiles_refuse_before_any_machine_operation(self):
        with patch.object(route, 'mc') as machine:
            with self.assertRaisesRegex(ValueError, 'skill requires'):
                route._run_trial(self.args(model='wrong'), {'id': 'textedit-save'}, 'sky-external', 1, Path('/unused'))
        machine.assert_not_called()


if __name__ == '__main__':
    unittest.main()
