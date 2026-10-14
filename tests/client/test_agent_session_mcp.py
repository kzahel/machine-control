import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'client'))
from agent_session import Session, SessionError, SessionTimeout
from agent_session_mcp import Namespace, BoundedOutput, Worker, serve, published_session


class NullPeer:
    def call(self,request):raise AssertionError('Unexpected native request')
    def image(self,result):raise AssertionError('Unexpected capture')
    def close(self):pass


class FacadeTest(unittest.TestCase):
    def test_namespace_keeps_values_and_echoes_only_final_expression(self):
        session=Session(NullPeer(),target='fixture')
        namespace=Namespace(session)
        self.assertEqual(namespace.run('x = 6\nx * 7'),42)
        self.assertEqual(namespace.run('x += 1\nx'),7)
        namespace.reset()
        with self.assertRaises(NameError):namespace.run('x')
        self.assertIs(namespace.values['mc'],session)

    def test_output_limit_stops_unbounded_printing(self):
        output=BoundedOutput()
        with self.assertRaises(SessionError):output.write('a'*25000)
        self.assertEqual(len(output.getvalue()),24000)

    def test_discovery_and_malformed_call_never_acquire_a_target(self):
        def forbidden(*args,**kwargs):raise AssertionError('No worker should start')
        incoming=io.StringIO('\n'.join(json.dumps(x) for x in [
            {'jsonrpc':'2.0','id':1,'method':'initialize'},
            {'jsonrpc':'2.0','id':2,'method':'tools/list'},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'mc','arguments':{'code':3}}}])+'\n')
        out=io.StringIO()
        self.assertEqual(serve('fixture',{},[],incoming=incoming,outgoing=out,worker_factory=forbidden),0)
        values=[json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(values[0]['result']['serverInfo']['name'],'machine-control-python')
        self.assertEqual([t['name'] for t in values[1]['result']['tools']],['mc','mc_reset'])
        self.assertIn('error',values[2])

    def test_timeout_reaps_worker_and_requires_explicit_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'peer.py'
            script.write_text('import sys,time\nsys.stdin.readline()\nsys.stdin.readline()\ntime.sleep(60)\n')
            worker=Worker({},timeout=.05,command=[sys.executable,str(script)])
            try:
                with self.assertRaises(SessionTimeout) as error:worker.request({'code':'blocked'})
                self.assertEqual(error.exception.delivered,'unknown')
                self.assertIsNotNone(worker.process.poll())
                with self.assertRaises(SessionError):worker.request({'code':'do not replay'})
            finally:worker.close()

    def test_worker_disconnection_is_unknown_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'peer.py'
            script.write_text('import sys\nsys.stdin.readline()\nsys.stdin.readline()\n')
            worker=Worker({},timeout=3,command=[sys.executable,str(script)])
            try:
                with self.assertRaises(SessionError) as error:worker.request({'code':'task'})
                self.assertEqual(error.exception.delivered,'unknown')
                self.assertTrue(worker.closed)
            finally:worker.close()

    def test_explicit_session_close_reaps_idle_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'peer.py'
            script.write_text('import sys,json\nsys.stdin.readline()\nsys.stdin.readline()\n'
                'print(json.dumps({"content":[],"isError":False,"_sessionClosed":True}),flush=True)\n'
                'sys.stdin.read()\n')
            worker=Worker({},timeout=3,command=[sys.executable,str(script)])
            try:
                result=worker.request({'code':'mc.close()'})
                self.assertEqual(result,{'content':[],'isError':False})
                self.assertTrue(worker.closed)
                self.assertEqual(worker.process.poll(),0)
            finally:worker.close()

    def test_interpreter_is_bound_to_one_explicit_session(self):
        configs=[]; calls=[]
        class PeerWorker:
            closed=False
            def __init__(self,config):configs.append(dict(config))
            def request(self,value):calls.append(value);return {'content':[], 'isError':False}
            def close(self):self.closed=True
        messages=[{'jsonrpc':'2.0','id':index,'method':'tools/call','params':{'name':'mc',
                   'arguments':{'code':'1+1','session_id':identifier}}}
                  for index,identifier in enumerate(['first-session','different-session','first-session'])]
        incoming=io.StringIO('\n'.join(map(json.dumps,messages))+'\n');out=io.StringIO()
        with patch('agent_session_mcp.audit_history.session_ref',return_value=None):
            serve('fixture',{},[],incoming=incoming,outgoing=out,worker_factory=PeerWorker)
        self.assertEqual(len(configs),1)
        self.assertEqual(configs[0]['sessionId'],'first-session')
        self.assertEqual(configs[0]['claimantId'],'first-session')
        self.assertEqual(len(calls),2)
        replies=[json.loads(line) for line in out.getvalue().splitlines()]
        self.assertTrue(replies[1]['result']['isError'])
        self.assertIn('session_mismatch',replies[1]['result']['content'][0]['text'])

    def test_coordinator_publication_binds_and_cannot_switch_the_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'session.id'
            path.write_text('published-session\n');path.chmod(0o600)
            configs=[]
            class PeerWorker:
                closed=False
                def __init__(self,config):configs.append(dict(config))
                def request(self,value):
                    path.write_text('another-session\n')
                    return {'content':[], 'isError':False}
                def close(self):self.closed=True
            messages=[{'id':0,'method':'tools/list'}, *[
                {'id':i,'method':'tools/call','params':{'name':'mc','arguments':{'code':'1+1'}}}
                for i in (1,2)]]
            out=io.StringIO()
            with patch('agent_session_mcp.audit_history.session_ref',return_value=None):
                serve('fixture',{},['--session-id-file',str(path)],
                    incoming=io.StringIO('\n'.join(map(json.dumps,messages))+'\n'),
                    outgoing=out,worker_factory=PeerWorker)
            replies=[json.loads(line) for line in out.getvalue().splitlines()]
            self.assertEqual(replies[0]['result']['tools'][0]['inputSchema']['required'],['code'])
            self.assertEqual(configs[0]['sessionId'],'published-session')
            self.assertEqual(len(configs),1)
            self.assertIn('session_mismatch',replies[2]['result']['content'][0]['text'])

    def test_unready_or_invalid_publication_refuses_before_claiming(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'session.id'
            with self.assertRaises(SessionError) as error:published_session(path)
            self.assertTrue(error.exception.retryable)
            self.assertEqual(error.exception.delivered,'no')
            path.write_text('session');path.chmod(0o644)
            with self.assertRaises(SessionError):published_session(path)
            path.chmod(0o600);path.write_text('x'*200)
            with self.assertRaises(SessionError):published_session(path)
            path.write_text('session')
            link=Path(directory)/'link';link.symlink_to(path)
            with self.assertRaises(SessionError):published_session(link)
            self.assertEqual(published_session(path),'session')


if __name__=='__main__':unittest.main()
