import importlib.util
import os
import select
from pathlib import Path
import unittest
import json
import subprocess
import sys
import tempfile

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
    def test_real_stdio_handshake_approval_images_and_cleanup(self):
        source = '''import json,sys
def send(v): print(json.dumps(v),flush=True)
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r: continue
 method=r['method'];result={}
 if method=='initialize':
  assert 'elicitation' in r['params']['capabilities']
  result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'fake','version':'1'},'instructions':'native help'}
 elif method=='tools/list': result={'tools':[{'name':'js'},{'name':'js_reset'}]}
 elif method=='tools/call' and r['params']['name']=='js':
  app=r['params']['arguments']['app']
  send({'jsonrpc':'2.0','id':'approval','method':'elicitation/create','params':{'_meta':{'connector_id':'computer-use','tool_params':{'app':app}}}})
  answer=json.loads(sys.stdin.readline())['result']['action']
  result={'content':[{'type':'text','text':answer},{'type':'image','mimeType':'image/png','data':'fixture'}]}
 send({'jsonrpc':'2.0','id':r['id'],'result':result})
'''
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); fake=root/'fake.py';fake.write_text(source)
            config=root/'config.json';config.write_text(json.dumps({'mcpServers':{'cua_repl':
                {'command':sys.executable,'args':[str(fake)]}}}))
            requests=[('server/discover',{}),('initialize',{}),('tools/list',{}),
                      ('tools/call',{'name':'js','arguments':{'app':'com.apple.TextEdit'}}),
                      ('tools/call',{'name':'js','arguments':{'app':'com.apple.Finder'}}),
                      ('tools/call',{'name':'sky_close'})]
            data=''.join(json.dumps({'jsonrpc':'2.0','id':i,'method':m,'params':p})+'\n'
                         for i,(m,p) in enumerate(requests))
            run=subprocess.run([sys.executable,str(ROOT/'sky-external/bridge.py'),'--config',str(config),
                '--allow-app','com.apple.TextEdit','--evidence',str(root/'evidence')],
                input=data,capture_output=True,text=True,timeout=15)
            self.assertEqual(run.returncode,0,run.stderr)
            rows=[json.loads(line) for line in run.stdout.splitlines()]
            self.assertEqual(rows[0]['error']['code'],-32601)
            self.assertEqual(rows[3]['result']['content'][0]['text'],'accept')
            self.assertEqual(rows[4]['result']['content'][0]['text'],'decline')
            self.assertEqual(rows[3]['result']['content'][1]['data'],'fixture')
            self.assertTrue(json.loads((root/'evidence/closed.json').read_text())['closed'])

    def test_successful_runtime_teardown_is_reported_while_wrapper_remains_alive(self):
        source = """import json,os,pathlib,sys
pathlib.Path(os.environ['PID_FILE']).write_text(str(os.getpid()))
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r: continue
 result={}
 if r['method']=='initialize':result={'instructions':'native docs','capabilities':{}}
 print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result}),flush=True)
"""
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fake=root/'fake.py';fake.write_text(source)
            pid_file=root/'pid';config=root/'config.json';evidence=root/'evidence'
            config.write_text(json.dumps({'mcpServers':{'cua_repl':{'command':sys.executable,
                'args':[str(fake)],'env':{'PID_FILE':str(pid_file)}}}}))
            process=subprocess.Popen([sys.executable,str(ROOT/'sky-external/bridge.py'),'--config',str(config),
                '--allow-app','com.apple.TextEdit','--evidence',str(evidence)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            def request(identifier,method,params):
                process.stdin.write(json.dumps({'jsonrpc':'2.0','id':identifier,'method':method,'params':params})+'\n')
                process.stdin.flush()
                self.assertTrue(select.select([process.stdout],[],[],10)[0], 'wrapper reply timed out')
                return json.loads(process.stdout.readline())
            try:
                self.assertIn('result',request(1,'initialize',{}))
                native_pid=int(pid_file.read_text())
                reply=request(2,'tools/call',{'name':'sky_close'})
                self.assertEqual(reply['result']['content'][0]['text'],'Computer Use runtime closed.')
                self.assertIsNone(process.poll(), 'MCP wrapper must still be alive')
                with self.assertRaises(ProcessLookupError):os.kill(native_pid,0)
                marker=json.loads((evidence/'closed.json').read_text())
                events=[json.loads(line) for line in (evidence/'protocol-events.jsonl').read_text().splitlines()]
                teardown=[e for e in events if e['event']=='runtime-closed']
                self.assertTrue(marker['runtimeClosed'])
                self.assertEqual(len(teardown),1)
                self.assertEqual(teardown[0]['reason'],'sky_close')
                self.assertEqual(teardown[0]['runtimeId'],marker['runtimeId'])
                self.assertFalse(any(e['event']=='wrapper-process-closed' for e in events))
                self.assertEqual(request(3,'ping',{})['result'],{})
                process.stdin.close();process.stdin=None
                process.communicate(timeout=10)
                events=[json.loads(line) for line in (evidence/'protocol-events.jsonl').read_text().splitlines()]
                self.assertEqual(sum(e['event']=='runtime-closed' for e in events),1)
                self.assertTrue(any(e['event']=='wrapper-process-closed' and e['runtimeClosed'] for e in events))
            finally:
                if process.poll() is None:process.terminate()
                process.communicate(timeout=10)

    def test_teardown_failure_does_not_report_runtime_closed(self):
        class FailingRuntime(Runtime):
            def close(self):raise RuntimeError('teardown failed')
        events=[];runtime=FailingRuntime();b=bridge.Bridge(lambda:runtime,on_runtime_closed=events.append)
        b.handle('initialize',{})
        with self.assertRaisesRegex(RuntimeError,'teardown failed'):
            b.handle('tools/call',{'name':'sky_close'})
        self.assertFalse(b.runtime_closed)
        self.assertTrue(b.closed)
        self.assertEqual(events,[])

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
