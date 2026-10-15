"""Exercise the repo-local skill's setup and genuine-protocol startup probe."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PREPARE = ROOT / 'skills/claude-computer-use/scripts/prepare.py'


class SkySkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sky skill ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'runtime.json'
        self.fake = self.root / 'fake runtime.py'
        self.fake.write_text('''import json, os, pathlib, sys
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r: continue
 method=r['method']; result={}
 with open(os.environ['CALLS'], 'a') as f: f.write(method+'\\n')
 if method=='initialize':
  result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'fake','version':'1'}}
 elif method=='tools/list':
  result={'tools':[{'name':n} for n in os.environ['TOOLS'].split(',')]}
 elif method=='tools/call':
  assert r['params']['name']=='js_reset', 'probe must not request app access'
  pathlib.Path(os.environ['CLOSED']).write_text('reset')
 print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result}),flush=True)
''')
        self.write_config()

    def write_config(self, tools='js,js_reset'):
        self.config.write_text(json.dumps({'mcpServers': {'cua_repl': {
            'command': sys.executable, 'args': [str(self.fake)], 'env': {
                'TOOLS': tools, 'CALLS': str(self.root / 'calls'),
                'CLOSED': str(self.root / 'closed'), 'PRIVATE_CANARY': 'never-echo-this-value'}}}}))

    def prepare(self, output, *extra, app='com.apple.TextEdit'):
        return subprocess.run([sys.executable, str(PREPARE), '--runtime-config', str(self.config),
                               '--allow-app', app, '--output-dir', str(output), *extra],
                              capture_output=True, text=True, timeout=20)

    def test_probe_closes_without_app_access_and_config_is_private(self):
        output = self.root / 'session with spaces'
        run = self.prepare(output, '--probe', '--allow-app', 'com.apple.TextEdit')
        self.assertEqual(run.returncode, 0, run.stderr)
        status = json.loads(run.stdout)
        self.assertEqual(status['status'], 'startup-probed')
        self.assertFalse(status['appAccessVerified'])
        self.assertEqual(status['approvedApps'], ['com.apple.TextEdit'])
        config = json.loads((output / 'mcp.json').read_text())
        server = config['mcpServers']['sky_experiment']
        self.assertEqual(server['command'], sys.executable)
        self.assertEqual(server['args'][2], str(self.config.resolve()))
        self.assertNotIn('env', server)
        self.assertNotIn('never-echo-this-value', run.stdout + run.stderr)
        self.assertEqual((self.root / 'calls').read_text().splitlines(),
                         ['initialize', 'tools/list', 'tools/call'])
        self.assertEqual((self.root / 'closed').read_text(), 'reset')
        self.assertTrue(json.loads((output / 'preflight/probe.json').read_text())['ok'])
        if os.name == 'posix':
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            for path in output.rglob('*'):
                self.assertEqual(path.stat().st_mode & 0o077, 0, str(path))
        # Use the generated command exactly as a Claude MCP host would.
        requests = [('initialize', {}), ('tools/list', {}),
                    ('tools/call', {'name': 'sky_close'})]
        wire = ''.join(json.dumps({'jsonrpc': '2.0', 'id': i, 'method': method,
                                   'params': params}) + '\n'
                       for i, (method, params) in enumerate(requests))
        launched = subprocess.run([server['command'], *server['args']], input=wire,
                                  capture_output=True, text=True, timeout=20)
        self.assertEqual(launched.returncode, 0, launched.stderr)
        replies = [json.loads(line) for line in launched.stdout.splitlines()]
        self.assertTrue(all('result' in reply for reply in replies))
        self.assertEqual({tool['name'] for tool in replies[1]['result']['tools']},
                         {'js', 'js_reset', 'sky_close'})
        self.assertTrue(json.loads((output / 'runtime/closed.json').read_text())['closed'])

    def test_static_setup_does_not_launch_or_overwrite(self):
        output = self.root / 'session'
        run = self.prepare(output)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['status'], 'configuration-written')
        self.assertFalse((self.root / 'calls').exists())
        before = (output / 'mcp.json').read_bytes()
        self.assertNotEqual(self.prepare(output, app='com.apple.Finder').returncode, 0)
        self.assertEqual((output / 'mcp.json').read_bytes(), before)

    def test_invalid_scope_and_runtime_do_not_write_config(self):
        output = self.root / 'invalid'
        for app in ['*', 'TextEdit', 'com.apple.*']:
            with self.subTest(app=app):
                self.assertNotEqual(self.prepare(output, app=app).returncode, 0)
                self.assertFalse(output.exists())
        self.config.write_text('{"mcpServers": {"different_runtime": {}}}')
        run = self.prepare(output)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('mcpServers.cua_repl', run.stderr)
        self.assertFalse(output.exists())

    def test_incompatible_tools_record_failed_stage_and_close(self):
        self.write_config(tools='different_interface')
        output = self.root / 'incompatible'
        run = self.prepare(output, '--probe')
        self.assertNotEqual(run.returncode, 0)
        result = json.loads((output / 'preflight/probe.json').read_text())
        self.assertFalse(result['ok'])
        self.assertEqual(result['stage'], 'tools/list')
        self.assertEqual((self.root / 'closed').read_text(), 'reset')


if __name__ == '__main__':
    unittest.main()
