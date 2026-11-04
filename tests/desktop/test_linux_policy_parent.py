"""The native kernel bond ends even an uncooperative child on parent loss."""
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import unittest

LAUNCHER=Path(__file__).resolve().parents[2]/'desktop/native/linux/policy_exec.py'


@unittest.skipUnless(sys.platform=='linux','Requires Linux parent-death signal')
class ParentLifetimeTests(unittest.TestCase):
    def test_parent_loss_kills_child_that_ignores_term_and_eof(self):
        parent_code="""import os,subprocess,sys,time
child=subprocess.Popen([sys.executable,'-I','-B',sys.argv[1],str(os.getpid()),sys.executable,'-c',
 'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print(\"ready\",flush=True);time.sleep(120)'],stdout=subprocess.PIPE,text=True)
assert child.stdout.readline().strip()=='ready'
print(child.pid,flush=True)
time.sleep(120)
"""
        parent=subprocess.Popen([sys.executable,'-c',parent_code,str(LAUNCHER)],stdout=subprocess.PIPE,text=True)
        child=None
        try:
            self.assertTrue(select.select([parent.stdout],[],[],10)[0])
            child=int(parent.stdout.readline())
            parent.kill();parent.wait(5)
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                try:state=Path(f'/proc/{child}/stat').read_text().rsplit(')',1)[1].split()[0]
                except FileNotFoundError:break
                if state=='Z':break
                time.sleep(.02)
            else:self.fail('Policy child survived native parent loss')
        finally:
            if parent.poll() is None:parent.kill();parent.wait(5)
            parent.stdout.close()
            if child:
                try:os.kill(child,signal.SIGKILL)
                except ProcessLookupError:pass


if __name__=='__main__':unittest.main()
