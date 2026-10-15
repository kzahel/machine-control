"""Exact runtime manifests and secret-safe delivery; no installed runtime launches."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from route_comparison import runtime_selection as selection, runtime_input, ROOT


class RuntimeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.checkout = self.root / 'checkout'
        self.checkout.mkdir()
        patch.object(Path, 'home', return_value=self.home).start()
        self.addCleanup(patch.stopall)
        self.launcher = self.root / 'installed/launcher'
        self.script = self.root / 'installed/cua.js'
        self.repl = self.root / 'installed/repl.js'
        self.node = self.root / 'installed/node'
        self.service = self.root / 'installed/Native.app'
        for path in [self.launcher, self.script, self.repl, self.node, self.service / 'Contents/MacOS/Native']:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture: never execute')
            path.chmod(0o700)
        (self.service / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable': 'Native'}))
        self.config = self.root / 'private-manifest.json'
        self.data = {'mcpServers': {'cua_repl': {'command': str(self.launcher), 'args': [str(self.script)],
            'env': {'CUA_REPL_NODE_REPL_PATH': str(self.repl), 'SKY_CUA_SERVICE_PATH': str(self.service),
                    'NODE_REPL_NODE_PATH': str(self.node), 'PRIVATE_CANARY': 'SECRET_VALUE_DO_NOT_ECHO'}}}}
        self.write()

    def write(self):
        self.raw = json.dumps(self.data).encode()
        self.config.write_bytes(self.raw)
        self.config.chmod(0o600)
        self.sha = hashlib.sha256(self.raw).hexdigest()

    def cached(self, version):
        path = self.home / '.codex/plugins/cache/openai-bundled/unified-computer-use' / version / '.mcp.json'
        path.parent.mkdir(parents=True)
        path.write_bytes(self.raw)
        return path

    def test_private_controller_config_accepts_target_only_paths_without_rewriting_bytes(self):
        self.data['mcpServers']['cua_repl']['command'] = '/target-only/installed/launcher'
        self.write()
        raw, receipt = selection.private_input(self.config, self.checkout)
        self.assertEqual(raw, self.raw)
        self.assertEqual(receipt, {'path': str(self.config), 'sha256': self.sha, 'mode': '0o600'})
        self.assertNotIn('SECRET_VALUE', json.dumps(receipt))
        with self.assertRaisesRegex(selection.RuntimeConfigError, 'missing or not usable'):
            selection.select_config(self.config, checkout=self.checkout, private=True)

    def test_missing_fallback_and_ambiguous_fallback_are_distinct(self):
        with self.assertRaisesRegex(selection.RuntimeConfigError, 'No cached runtime config'):
            selection.select_config(checkout=self.checkout)
        only = self.cached('one')
        self.assertEqual(selection.select_config(checkout=self.checkout), (only, 'cache-exact-one'))
        self.cached('two')
        with self.assertRaisesRegex(selection.RuntimeConfigError, 'ambiguous'):
            selection.select_config(checkout=self.checkout)
        selected, source = selection.select_config(self.config, checkout=self.checkout, expected_sha256=self.sha, private=True)
        self.assertEqual(selected, self.config)
        self.assertEqual(source, 'explicit-private')

    def test_hash_mismatch_prevents_fingerprint_and_selected_path_is_consistent(self):
        collect = Mock(side_effect=lambda path: {'configSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                               'artifacts': {}, 'commands': {}, 'service': {}})
        with patch.dict(sys.modules, {'provenance': SimpleNamespace(collect=collect)}):
            with self.assertRaisesRegex(selection.RuntimeConfigError, 'SHA-256'):
                selection.fingerprint(self.config, checkout=self.checkout, expected_sha256='wrong', private=True)
            collect.assert_not_called()
            value = selection.fingerprint(self.config, checkout=self.checkout, expected_sha256=self.sha, private=True)
        collect.assert_called_once_with(self.config)
        self.assertEqual(value['configPath'], str(self.config))
        self.assertEqual(value['configSha256'], self.sha)
        self.assertEqual(value['configSelection'], 'explicit-private')
        self.assertNotIn('SECRET_VALUE', json.dumps(value))

    def test_disabled_templates_and_missing_target_artifacts_refuse_before_launch(self):
        original = json.loads(self.raw)
        for field, value in [('enabled', False), ('disabled', True), ('command', 'node')]:
            self.data = json.loads(json.dumps(original))
            self.data['mcpServers']['cua_repl'][field] = value
            self.write()
            with self.subTest(field=field), self.assertRaises(selection.RuntimeConfigError):
                selection.private_input(self.config, self.checkout)
        self.data = original
        self.write()
        for path in [self.launcher, self.script, self.repl, self.node, self.service / 'Contents/MacOS/Native']:
            saved = path.read_bytes()
            path.unlink()
            with self.subTest(path=path), self.assertRaises(selection.RuntimeConfigError):
                selection.select_config(self.config, checkout=self.checkout, private=True)
            path.write_bytes(saved)
            path.chmod(0o700)

    def test_private_mode_symlink_checkout_and_unresolved_templates_refuse(self):
        self.config.chmod(0o644)
        with self.assertRaisesRegex(selection.RuntimeConfigError, '0600'):
            selection.private_input(self.config, self.checkout)
        self.config.chmod(0o600)
        linked = self.root / 'linked.json'
        linked.symlink_to(self.config)
        with self.assertRaisesRegex(selection.RuntimeConfigError, 'regular'):
            selection.private_input(linked, self.checkout)
        copied = self.checkout / 'manifest.json'
        copied.write_bytes(self.raw)
        copied.chmod(0o600)
        with self.assertRaisesRegex(selection.RuntimeConfigError, 'outside checkout'):
            selection.private_input(copied, self.checkout)
        self.data['mcpServers']['cua_repl']['env']['CUA_REPL_NODE_REPL_PATH'] = '/${PLUGIN_ROOT}/node.js'
        self.write()
        with self.assertRaisesRegex(selection.RuntimeConfigError, 'templates'):
            selection.private_input(self.config, self.checkout)

    def test_receive_uses_exact_stdin_bytes_with_owner_only_guest_file_and_no_echo(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            received = selection.receive(self.raw, checkout=self.checkout, expected_sha256=self.sha)
        destination = Path(received['configPath'])
        self.assertEqual(destination.read_bytes(), self.raw)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(destination.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(received['configSha256'], self.sha)
        self.assertNotIn('SECRET_VALUE', output.getvalue() + json.dumps(received))
        with self.assertRaises(FileExistsError):
            selection.receive(self.raw, checkout=self.checkout, expected_sha256=self.sha)

    def test_receive_hash_or_validation_failure_writes_nothing(self):
        for data, sha in [(self.raw, 'wrong'), (b'{"SECRET_VALUE_DO_NOT_ECHO": true}', hashlib.sha256(b'{"SECRET_VALUE_DO_NOT_ECHO": true}').hexdigest())]:
            with self.subTest(data=data), self.assertRaises(selection.RuntimeConfigError) as error:
                selection.receive(data, checkout=self.checkout, expected_sha256=sha)
            self.assertNotIn('SECRET_VALUE', str(error.exception))
            self.assertFalse((self.home / 'experiment/runtime-input').exists())

    def test_structural_errors_never_echo_manifest_or_environment(self):
        for raw in [b'{"PRIVATE":"SECRET_VALUE_DO_NOT_ECHO",', b'{"mcpServers":{"cua_repl":"SECRET_VALUE_DO_NOT_ECHO"}}']:
            with self.subTest(raw=raw), self.assertRaises(selection.RuntimeConfigError) as error:
                selection.validate_bytes(raw)
            self.assertNotIn('SECRET_VALUE', str(error.exception))
        self.data['mcpServers']['cua_repl']['command'] = '/missing/SECRET_VALUE_DO_NOT_ECHO'
        self.write()
        run = subprocess.run([sys.executable, str(Path(selection.__file__)), 'fingerprint', '--checkout', str(self.checkout),
            '--config', str(self.config), '--expected-sha256', self.sha, '--private'], capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertNotIn('SECRET_VALUE', run.stdout + run.stderr)
        self.assertEqual(json.loads(run.stdout)['stage'], 'fingerprint')

    def test_runner_checks_private_input_hash_again_before_trial(self):
        args = SimpleNamespace(runtime_config_file=self.config, runtime_config_expected_sha256=self.sha)
        self.assertEqual(runtime_input(args)[0], self.raw)
        self.config.write_bytes(self.raw + b'\n')
        with self.assertRaisesRegex(ValueError, 'changed after batch selection'):
            runtime_input(args)
        self.assertEqual(runtime_input(SimpleNamespace()), (None, None))


if __name__ == '__main__':
    unittest.main()
