import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'client'))
from agent_session import Session, SessionError, SessionTimeout
from agent_session_mcp import Namespace, BoundedOutput, Worker, serve


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


if __name__=='__main__':unittest.main()
