"""A dead policy or failed cleanup cannot strand native lifetime resources."""
import ast
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest


source=Path(__file__).resolve().parents[2]/'desktop/native/linux/desktop.py'
cls=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Desktop')
method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='shutdown')
namespace={'subprocess':subprocess}
exec(compile(ast.Module(body=[method],type_ignores=[]),str(source),'exec'),namespace)
shutdown=namespace['shutdown']


@unittest.skipUnless(hasattr(socket, 'AF_UNIX'), 'Requires native Unix-domain sockets')
class ShutdownTests(unittest.TestCase):
    def test_each_cleanup_failure_still_closes_endpoints_and_reaps_notice(self):
        for failed in ('audit','work','access','policy','portal','browser','channel','activity','presentation'):
            with self.subTest(failed=failed),tempfile.TemporaryDirectory(prefix='mc-shutdown-') as tmp:
                events=[];inhibit=threading.Event()
                def action(name):
                    def run(*args,**kwargs):
                        self.assertTrue(inhibit.is_set(),'authority must be fenced before cleanup')
                        events.append(name)
                        if name==failed:raise RuntimeError('resource already lost')
                    return run
                endpoint=Path(tmp)/'desktop.sock';recovery_endpoint=Path(tmp)/'operator.sock'
                listener=socket.socket(socket.AF_UNIX);listener.bind(str(endpoint))
                recovery=socket.socket(socket.AF_UNIX);recovery.bind(str(recovery_endpoint))
                self.addCleanup(listener.close);self.addCleanup(recovery.close)
                notice=SimpleNamespace(poll=lambda:None,terminate=action('notice-terminate'),wait=action('notice-wait'))
                owner=SimpleNamespace(stopped=False,inhibit=inhibit,
                    journal=SimpleNamespace(event=action('audit'),diagnostic=action('diagnostic')),
                    work=SimpleNamespace(cancel=action('work')),grants=SimpleNamespace(stop=action('access')),
                    policy=SimpleNamespace(stop=action('policy')),portal=SimpleNamespace(close=action('portal')),
                    browser=SimpleNamespace(close=action('browser')),channels=[SimpleNamespace(close=action('channel'))],
                    activity=SimpleNamespace(close=action('activity')),socket=listener,endpoint=endpoint,
                    recovery=recovery,recovery_endpoint=recovery_endpoint,
                    presentation=SimpleNamespace(close=action('presentation')),safety_condition=threading.Condition(),
                    safety=notice,loop=SimpleNamespace(quit=action('loop-quit')))
                shutdown(owner)
                self.assertEqual(listener.fileno(),-1);self.assertEqual(recovery.fileno(),-1)
                self.assertFalse(endpoint.exists());self.assertFalse(recovery_endpoint.exists())
                self.assertIn('policy',events);self.assertIn('notice-wait',events)
                self.assertEqual(events[-1],'loop-quit')
                previous=list(events);shutdown(owner);self.assertEqual(events,previous)


if __name__=='__main__':unittest.main()
