import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('sky_bridge', ROOT/'sky-external/bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
from mcp_client import approval_allowed


class Runtime:
    initialization = {'instructions': 'Genuine runtime instructions'}
    def __init__(self):
        self.calls = []
        self.closed = False
        self.result = {'content': [{'type': 'image', 'mimeType': 'image/png', 'data': 'fixture'},
                                  {'type': 'text', 'text': 'user stopped'}], 'isError': True}
    def request(self, method, params, **kwargs):
        self.calls.append((method, params))
        if method == 'tools/list':
            return {'tools': [{'name': n} for n in ['js','js_reset','js_add_node_module_dir']]}
        return self.result
    def close(self):
        self.closed = True


class SkyExternalTests(unittest.TestCase):
    def test_only_exact_connector_and_app_metadata_authorize(self):
        def request(connector, app):
            return {'params': {'_meta': {'connector_id': connector, 'tool_params': {'app': app}}}}
        self.assertTrue(approval_allowed(request('computer-use','com.apple.TextEdit'), {'com.apple.TextEdit'}))
        for r in [request('other','com.apple.TextEdit'), request('computer-use','com.apple.Finder'),
                  request('computer-use','TextEdit'), {'params': {'message': 'Allow com.apple.TextEdit'}}]:
            self.assertFalse(approval_allowed(r, {'com.apple.TextEdit'}))

    def test_documentation_preserved_and_extra_tools_hidden(self):
        runtime = Runtime(); b = bridge.Bridge(lambda: runtime)
        self.assertIn('Genuine runtime instructions', b.handle('initialize', {})['instructions'])
        self.assertEqual({t['name'] for t in b.handle('tools/list', {})['tools']},
                         {'js', 'js_reset', 'sky_close'})

    def test_images_and_stop_refusal_pass_through_without_restart(self):
        runtime = Runtime(); b = bridge.Bridge(lambda: runtime); b.handle('initialize', {})
        params = {'name': 'js', 'arguments': {'code': 'observed_action'}}
        self.assertIs(b.handle('tools/call', params), runtime.result)
        self.assertEqual(runtime.calls, [('tools/call', params)])
        self.assertFalse(runtime.closed)

    def test_close_is_terminal_and_reaps_runtime(self):
        runtime = Runtime(); b = bridge.Bridge(lambda: runtime); b.handle('initialize', {})
        b.handle('tools/call', {'name': 'sky_close'})
        self.assertTrue(runtime.closed)
        with self.assertRaises(ValueError): b.handle('tools/call', {'name': 'js'})
        with self.assertRaises(ValueError): b.handle('initialize', {})
        self.assertEqual(runtime.calls, [])

    def test_extra_tool_is_not_dispatched(self):
        runtime = Runtime(); b = bridge.Bridge(lambda: runtime); b.handle('initialize', {})
        with self.assertRaises(ValueError): b.handle('tools/call', {'name': 'js_add_node_module_dir'})
        self.assertEqual(runtime.calls, [])


if __name__ == '__main__': unittest.main()
