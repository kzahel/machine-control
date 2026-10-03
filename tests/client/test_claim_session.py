import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
from claim_session import ClaimSession, validate_capabilities
import machine_control as mc


class ClaimSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.adapter = self.directory / "adapter.py"
        self.adapter.write_text('''import os,sys
from pathlib import Path
root=Path(sys.argv[1]); state=Path(sys.argv[2]); operation=sys.argv[3]
policy=['--state-dir',str(state),'--minimum-duration','1','--default-duration','30','--maximum-duration','120','--maximum-lifetime','120']
if operation=='claim-channel':
 command=[sys.executable,str(root/'providers/claims/admission_channel.py'),*policy,'--provider','fixture','--resource-id','exact-fixture']
elif operation=='doctor':
 command=[sys.executable,str(root/'tests/client/fixtures/mock-testbed.py'),'doctor','--json']
else:
 name=operation.removeprefix('claim-'); rest=[v for v in sys.argv[4:] if v!='--json']
 command=[sys.executable,str(root/'providers/claims/claims.py'),*policy,name,*([] if name=='capabilities' else ['--provider','fixture','--resource-id','exact-fixture']),*rest]
os.execv(sys.executable,command)
''')
        self.target = dict(command=[sys.executable, str(self.adapter), str(ROOT), str(self.directory)],
                           environment={}, claimPolicy="required", interface="machine-control-v0")
        self.children = []

    def tearDown(self):
        for child in self.children:
            if child.poll() is None:
                child.terminate()
            child.communicate(timeout=5)
        self.temporary.cleanup()

    def session(self, **options):
        return ClaimSession(self.target, reason="Fixture queue", claimant_authority="fixture",
                            claimant_id="caller", **options)

    def invoke(self, operation, *arguments):
        result = subprocess.run([*self.target["command"], "claim-" + operation, *arguments],
                                capture_output=True, text=True, timeout=5)
        return json.loads(result.stdout)

    def raw(self):
        process = subprocess.Popen([*self.target["command"], "claim-channel"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.children.append(process)
        return process

    def rpc(self, child, sequence, operation, **fields):
        child.stdin.write(json.dumps(dict(operation=operation, requestId=str(sequence),
                                         requestSequence=sequence, **fields)).encode() + b"\n")
        child.stdin.flush()
        self.assertTrue(select.select([child.stdout], [], [], 5)[0], "No bounded reply")
        return json.loads(child.stdout.readline())

    def open(self, child):
        return self.rpc(child, 1, "claim.open", schema="machine-control-claim-admission/v1",
                        reason="Fixture queue", claimantAuthority="fixture", claimantId="caller", waitSeconds=30)["data"]

    def test_two_sdk_contexts_handoff_once_and_cleanup_exact_claim(self):
        with self.session() as first:
            first.wait()
            with self.session() as second:
                self.assertEqual(second.status()["state"], "waiting_for_resource")
                old = first.bound_target()["_claimId"]
                first.cancel()
                second.wait()
                new = second.bound_target()["_claimId"]
                self.assertNotEqual(old, new)
                first.close()
                self.assertEqual(second.status()["state"], "active")
        self.assertEqual(self.invoke("status")["data"]["state"], "available")

    def test_heartbeat_retains_liveness_without_renewing_authority(self):
        with self.session() as owner:
            initial = owner.wait()["claim"]["expiresAt"]
            time.sleep(2.1)
            self.assertEqual(owner.status()["claim"]["expiresAt"], initial)
            self.assertTrue(owner.renew(60)["accepted"])
            self.assertNotEqual(owner.status()["claim"]["expiresAt"], initial)

    def test_explicit_capabilities_keep_v0_compatibility(self):
        self.assertFalse(self.invoke("capabilities")["queueing"])
        self.assertTrue(validate_capabilities(self.invoke("capabilities", "--version", "1"))["queueing"])

    def test_parent_connection_eof_releases_before_next_owner(self):
        child = self.raw()
        offered = self.open(child)
        self.assertTrue(self.rpc(child, 2, "claim.accept", offerGeneration=offered["offerGeneration"])["accepted"])
        child.stdin.close()
        child.stdin = None
        child.wait(timeout=3)
        self.assertEqual(self.invoke("status")["data"]["state"], "available")

    def test_raw_active_owner_expires_without_polling_or_renewal(self):
        child = self.raw()
        offered = self.open(child)
        active = self.rpc(child, 2, "claim.accept", offerGeneration=offered["offerGeneration"])["data"]
        time.sleep(5.3)
        self.assertFalse(self.invoke("check", "--claim-id", active["claim"]["claimId"])["accepted"])
        ended = self.rpc(child, 3, "claim.heartbeat")["data"]
        self.assertEqual(ended["terminalReason"], "heartbeat_expired")
        self.assertFalse(self.rpc(child, 4, "claim.accept", offerGeneration=offered["offerGeneration"])["accepted"])

    def test_sequence_replay_closes_owner_and_fences_claim(self):
        child = self.raw()
        offered = self.open(child)
        self.rpc(child, 2, "claim.accept", offerGeneration=offered["offerGeneration"])
        child.stdin.write(b'{"operation":"claim.heartbeat","requestId":"replay","requestSequence":2}\n')
        child.stdin.flush()
        child.wait(timeout=3)
        self.assertEqual(self.invoke("status")["data"]["state"], "available")

    def test_stalled_stdout_does_not_extend_owned_claim_or_hang_exit(self):
        child = self.raw()
        offered = self.open(child)
        self.rpc(child, 2, "claim.accept", offerGeneration=offered["offerGeneration"])
        def flood():
            try:
                for number in range(3, 2000):
                    child.stdin.write(json.dumps(dict(operation="claim.heartbeat", requestId=str(number),
                                                     requestSequence=number)).encode()+b"\n")
                    child.stdin.flush()
            except (OSError, ValueError):
                pass
        thread = threading.Thread(target=flood, daemon=True)
        thread.start()
        child.wait(timeout=7)
        thread.join(timeout=1)
        self.assertEqual(self.invoke("status")["data"]["state"], "available")

    def test_cancelled_wait_does_not_borrow_existing_holder(self):
        with self.session() as first:
            first.wait()
            with self.session() as second:
                with self.assertRaises(mc.ClientError):
                    second.wait(cancelled=lambda:True)
                self.assertEqual(second.status()["terminalReason"], "cancelled")
                self.assertEqual(first.status()["state"], "active")

    def test_queued_cli_run_waits_then_scopes_child_and_releases(self):
        registry = self.directory / "registry.json"
        target = {**self.target, "platform":"linux", "profile":"fixture",
                  "controllerPlatforms":[mc.controller_platform()], "launcher":"auto"}
        registry.write_text(json.dumps({"schema":mc.TARGET_SCHEMA, "targets":{"fixture":target}}))
        marker = self.directory / "effect"
        command = [str(ROOT/'bin/machine-control'), '--registry', str(registry), '--target', 'fixture',
            'run', '--wait', '10s', '--reason', 'Validate queued task', '--claimant-authority', 'fixture',
            '--claimant-id', 'queued-task', '--', sys.executable, '-c',
            "import os,pathlib; assert 'MACHINE_CONTROL_SCOPE_FILE' in os.environ; pathlib.Path("+repr(str(marker))+").touch()"]
        with self.session() as first:
            first.wait()
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.children.append(child)
            time.sleep(.4)
            self.assertIsNone(child.poll())
            self.assertFalse(marker.exists())
            first.cancel()
            output, error = child.communicate(timeout=8)
            self.assertEqual(child.returncode, 0, error.decode())
            self.assertTrue(marker.exists())
        self.assertEqual(self.invoke('status')['data']['state'], 'available')

    def test_queued_cli_cancellation_never_starts_child(self):
        import signal
        registry = self.directory / "registry.json"
        target = {**self.target, "platform":"linux", "profile":"fixture",
                  "controllerPlatforms":[mc.controller_platform()], "launcher":"auto"}
        registry.write_text(json.dumps({"schema":mc.TARGET_SCHEMA, "targets":{"fixture":target}}))
        marker = self.directory / "effect"
        with self.session() as first:
            first.wait()
            child = subprocess.Popen([str(ROOT/'bin/machine-control'),'--registry',str(registry),'--target','fixture',
                'run','--wait','30s','--reason','Validate cancellation','--claimant-authority','fixture','--claimant-id','queued-task',
                '--',sys.executable,'-c',"from pathlib import Path; Path("+repr(str(marker))+").touch()"],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.children.append(child)
            ready = select.select([child.stderr], [], [], 5)[0]
            self.assertTrue(ready)
            child.send_signal(signal.SIGTERM)
            _, error = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 128 + signal.SIGTERM, error.decode())
            self.assertFalse(marker.exists())
            self.assertEqual(first.status()['state'], 'active')


if __name__ == "__main__":
    unittest.main()
