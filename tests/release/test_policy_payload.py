"""Pinned Node stays immutable through the publisher-catalog packaging path."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('policy_payload', Path(__file__).resolve().parents[2] / 'runtime/scripts/verify.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyPayloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        files = {}
        for name in ['node.exe', 'LICENSE.node', 'policy/node/main.ts', 'policy/node_modules/ws/LICENSE']:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
            files[name] = dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        self.manifest = dict(schema='machine-control-policy-payload/v1', engine='node', executable='node.exe',
                             target='win-arm64', arguments=['policy/node/main.ts'], files=files)
        self.save()

    def save(self):
        (self.root / 'payload.json').write_text(json.dumps(self.manifest))

    def test_complete_bytes(self):
        self.assertEqual(policy.verify(self.root), self.manifest)
        path = self.root / 'node.exe'
        path.write_bytes(b'x' * path.stat().st_size)
        with self.assertRaisesRegex(ValueError, 'bytes changed'): policy.verify(self.root)

    def test_extra_code_is_refused(self):
        (self.root / 'policy/extra.ts').write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'file set'): policy.verify(self.root)

    def test_traversal_and_foreign_entry_are_refused(self):
        self.manifest['files']['../escape'] = dict(bytes=1, sha256='a' * 64)
        self.save()
        with self.assertRaisesRegex(ValueError, 'Unsafe'): policy.verify(self.root)
        self.manifest['arguments'] = ['foreign.ts']
        self.save()
        with self.assertRaisesRegex(ValueError, 'identity'): policy.verify(self.root)
