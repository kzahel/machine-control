"""Pure checks for the root locked-use credential helper and GDM worker."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'platforms/linux/guests/ubuntu/ui'))
import gnome_unlock  # noqa: E402  (no GI import at module load)

SPEC = importlib.util.spec_from_file_location('locked_credential', ROOT / 'desktop/native/linux/locked-credential.py')
lc = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lc
SPEC.loader.exec_module(lc)

ME = os.getuid() or 1000
OWNERS = frozenset({0, os.getuid()})
TOKEN = '0f5b2a4e-1c3d-4e5f-8a9b-0c1d2e3f4a5b'
HASH = '$y$j9T$abcdefghijklmnopqrstu.$ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm01'


def temporary(test):
    path = Path(os.path.realpath(tempfile.mkdtemp()))
    os.chmod(path, 0o700)
    test.addCleanup(lambda: __import__('shutil').rmtree(path, ignore_errors=True))
    return path


def write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    os.chmod(path, mode)
    return path


class FrameTests(unittest.TestCase):
    def test_newline_and_binary_frames(self):
        self.assertEqual(lc.parse_secret_frame(bytearray(b'p\xc3\xa4ss word\n')), bytearray('päss word'.encode()))
        frame = lc.encode_secret_frame(bytearray(b'secret'))
        self.assertTrue(frame.startswith(lc.SECRET_MAGIC))
        self.assertEqual(lc.parse_secret_frame(frame), bytearray(b'secret'))

    def test_invalid_frames_refuse_with_static_code(self):
        cases = [b'', b'\n', b'secret', b'a\nb\n', b'a\rb\n', b'a\0b\n', b'\xff\n',
                 b'x' * 4097 + b'\n', lc.SECRET_MAGIC + b'\x00\x05abc', lc.SECRET_MAGIC + b'\x00\x01ab',
                 lc.SECRET_MAGIC + b'\x00']
        for case in cases:
            with self.assertRaises(lc.Refused) as caught:
                lc.parse_secret_frame(bytearray(case))
            self.assertEqual(caught.exception.code, 'locked_secret_unavailable', case[:20])

    def test_stream_is_bounded_and_wiped(self):
        read, write_fd = os.pipe()
        os.write(write_fd, b'hunter2\n')
        os.close(write_fd)
        self.assertEqual(lc.read_secret_stream(read), bytearray(b'hunter2'))
        os.close(read)
        read, write_fd = os.pipe()
        writer = threading.Thread(target=lambda: (os.write(write_fd, b'x' * (lc.FRAME_LIMIT + 50)), os.close(write_fd)))
        writer.start()
        with self.assertRaises(lc.Refused):
            lc.read_secret_stream(read)
        os.close(read)
        writer.join()
        buffer = bytearray(b'abc')
        lc.wipe(buffer)
        self.assertEqual(buffer, bytearray(3))

    def test_stream_deadline(self):
        read, write_fd = os.pipe()
        self.addCleanup(os.close, read)
        self.addCleanup(os.close, write_fd)
        with self.assertRaises(lc.Refused):
            lc.read_secret_stream(read, seconds=0.05)


class AccountTests(unittest.TestCase):
    def files(self, shadow_line, passwd_extra=''):
        root = temporary(self)
        passwd = write(root / 'passwd', f'root:x:0:0:root:/root:/bin/bash\nalice:x:{ME}:{ME}::/home/alice:/bin/bash\n'
                       + passwd_extra)
        shadow = write(root / 'shadow', 'root:*:19000:0:99999:7:::\n' + shadow_line + '\n', 0o640)
        return passwd, shadow

    def account(self, shadow_line, today=20000, **kwargs):
        passwd, shadow = self.files(shadow_line, **kwargs)
        return lc.local_account(ME, passwd, shadow, OWNERS, today)

    def test_local_shadow_account(self):
        account = self.account(f'alice:{HASH}:19990:0:99999:7:::')
        self.assertEqual((account.name, account.uid, account.gid, account.home), ('alice', ME, ME, '/home/alice'))
        self.assertNotIn(HASH, repr(account))
        changed = self.account(f'alice:{HASH}:19991:0:99999:7:::')
        rehashed = self.account(f'alice:{HASH[:-1]}2:19990:0:99999:7:::')
        self.assertEqual(len({account.binding, changed.binding, rehashed.binding}), 3)

    def test_unusable_accounts(self):
        for line, code in [
                (f'alice:!{HASH}:19990:0:99999:7:::', 'locked_account_unavailable'),
                ('alice:*:19990:0:99999:7:::', 'locked_account_unavailable'),
                ('alice::19990:0:99999:7:::', 'locked_account_unavailable'),
                ('bob:' + HASH + ':19990:0:99999:7:::', 'locked_account_unavailable'),
                (f'alice:{HASH}:0:0:99999:7:::', 'locked_account_password_change_required'),
                (f'alice:{HASH}:19000:0:90:7:::', 'locked_account_password_change_required'),
                (f'alice:{HASH}:19000:0:90:7:5::', 'locked_account_unavailable'),
                (f'alice:{HASH}:19990:0:99999:7::20000:', 'locked_account_unavailable'),
                (f'alice:{HASH}:19990:0:99999:7:x::', 'locked_account_unavailable')]:
            with self.assertRaises(lc.Refused) as caught:
                self.account(line)
            self.assertEqual(caught.exception.code, code, line)

    def test_ambiguous_or_unshadowed_passwd(self):
        with self.assertRaises(lc.Refused):
            self.account(f'alice:{HASH}:19990:0:99999:7:::', passwd_extra=f'alias:x:{ME}:{ME}::/home/a:/bin/sh\n')
        root = temporary(self)
        passwd = write(root / 'passwd', f'alice:$6$inline:{ME}:{ME}::/home/alice:/bin/bash\n')
        shadow = write(root / 'shadow', f'alice:{HASH}:19990:0:99999:7:::\n', 0o640)
        with self.assertRaises(lc.Refused):
            lc.local_account(ME, passwd, shadow, OWNERS, 20000)
        os.chmod(shadow, 0o666)
        with self.assertRaises(lc.Refused):
            lc.local_account(ME, passwd, shadow, OWNERS, 20000)


class RequestTests(unittest.TestCase):
    def authenticate(self, **changes):
        value = dict(schema=lc.SCHEMA, operation='authenticate', sessionId='2', sessionStarted=123456,
                     coverOwner=':1.42', coverToken=TOKEN, deadlineSeconds=60)
        value.update(changes)
        return json.dumps({k: v for k, v in value.items() if v is not ...}).encode()

    def test_valid_requests(self):
        self.assertEqual(lc.parse_request(b'{"schema":"%s","operation":"status"}' % lc.SCHEMA.encode())['operation'], 'status')
        self.assertEqual(lc.parse_request(self.authenticate())['deadlineSeconds'], 60)
        self.assertEqual(lc.parse_request(self.authenticate(deadlineSeconds=900))['deadlineSeconds'], 900)

    def test_invalid_requests(self):
        for line in [self.authenticate(sessionId='-h'), self.authenticate(sessionId='a b'),
                     self.authenticate(sessionStarted=True), self.authenticate(sessionStarted=0),
                     self.authenticate(coverOwner='org.gnome.Shell'), self.authenticate(coverToken='x'),
                     self.authenticate(deadlineSeconds=901), self.authenticate(deadlineSeconds=0),
                     self.authenticate(extra=1), self.authenticate(coverOwner=...),
                     self.authenticate(schema='other'), self.authenticate(schema=...),
                     self.authenticate(deadlineSeconds=...), b'{"operation":"status"}',
                     b'{"operation":"status","operation":"status"}',
                     b'[]', b'{"operation":"status","path":"/tmp/x"}', b'\xff']:
            with self.assertRaises(lc.Refused, msg=line) as caught:
                lc.parse_request(line)
            self.assertEqual(caught.exception.code, 'locked_request_invalid')

    def test_control_worker_and_job_messages(self):
        schema = lc.SCHEMA.encode()
        self.assertEqual(lc.parse_control(b'{"schema":"%s","operation":"keep"}' % schema), ('keep', None))
        self.assertEqual(lc.parse_control(b'{"schema":"%s","operation":"renew","deadlineSeconds":60}' % schema),
                         ('renew', 60))
        for line in [b'{"schema":"%s","operation":"renew","deadlineSeconds":901}' % schema,
                     b'{"schema":"%s","operation":"renew"}' % schema, b'{"schema":"%s","operation":"x"}' % schema,
                     b'{"operation":"keep"}']:
            with self.assertRaises(lc.Refused):
                lc.parse_control(line)
        self.assertEqual(lc.parse_worker(b'{"event":"failed","code":"gnome_authentication_failed"}')['code'],
                         'gnome_authentication_failed')
        for line in [b'{"event":"failed","code":"made up"}', b'{"event":"failed"}', b'{"event":"ready","code":"x"}',
                     b'{"event":"secret"}']:
            with self.assertRaises(lc.Refused):
                lc.parse_worker(line)
        job = dict(uid=ME, sessionId='2', sessionStarted=5, coverOwner=':1.2', coverToken=TOKEN, peerPid=99)
        self.assertEqual(lc.parse_job(json.dumps(job).encode()), job)
        with self.assertRaises(lc.Refused):
            lc.parse_job(json.dumps({**job, 'peerPid': 1}).encode())


SESSION_TEXT = ('Id=2\nUser={uid}\nActive=yes\nType=wayland\nClass=user\nRemote=no\nSeat=seat0\nState=active\n'
                'TimestampMonotonic=123456\nLockedHint={locked}')


class ConsoleTests(unittest.TestCase):
    def runner(self, active='2', text=None):
        calls = []

        def run(*args):
            calls.append(args)
            if args[0] == 'show-seat':
                return active
            if args[0] == 'show-session':
                return text if text is not None else SESSION_TEXT.format(uid=ME, locked='yes')
            return ''
        return run, calls

    def test_exact_active_console(self):
        run, calls = self.runner()
        self.assertEqual(lc.read_console(run), lc.Console('2', ME, 123456, True))
        self.assertEqual(calls[0][-2:], ('--', 'seat0'))
        self.assertEqual(calls[1][-2:], ('--', '2'))
        host = lc.Host(run)
        host.lock('2')
        self.assertEqual(calls[-1], ('lock-session', '--', '2'))

    def test_refused_consoles(self):
        base = SESSION_TEXT.format(uid=ME, locked='yes')
        for active, text in [('-h', base), ('2', base.replace('Id=2', 'Id=3')),
                             ('2', base.replace('Remote=no', 'Remote=yes')),
                             ('2', base.replace('Type=wayland', 'Type=x11')),
                             ('2', base.replace('Active=yes', 'Active=no')),
                             ('2', base.replace('Seat=seat0', 'Seat=seat1')),
                             ('2', base + '\nLockedHint=no'), ('2', base.replace('User=', 'User=0')),
                             ('2', base.replace('LockedHint=yes', 'LockedHint=maybe')),
                             ('2', base.replace('TimestampMonotonic=123456', 'TimestampMonotonic=0'))]:
            run, _ = self.runner(active, text)
            with self.assertRaises(lc.Refused, msg=(active, text)):
                lc.read_console(run)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.root = temporary(self) / 'state'
        self.store = lc.Store(self.root, OWNERS)
        self.store.ensure()
        self.account = lc.Account('alice', ME, ME, '/home/alice', HASH, '19990')

    def commit(self):
        with self.store.locked():
            self.store.commit(self.account, 'a' * 32, b'opaque-sealed')

    def test_commit_ready_and_files_private(self):
        self.assertEqual(self.store.state(ME), ('absent', None))
        self.commit()
        receipt = self.store.ready(ME)
        self.assertEqual(self.store.sealed(receipt), b'opaque-sealed')
        self.assertEqual(receipt['shadow'], self.account.binding)
        for suffix in ('json', 'cred'):
            self.assertEqual(os.stat(self.store.path(ME, suffix)).st_mode & 0o777, 0o600)
        self.assertNotIn(b'opaque', self.store.path(ME, 'json').read_bytes())

    def test_recover_discards_old_attempt_marker_and_keeps_enrollment(self):
        self.commit()
        marker = self.store.path(ME, 'attempt')
        with self.store.locked():
            marker.write_text(json.dumps(dict(schema='machine-control-locked-credential-attempt/v1',
                                              uid=ME, enrollment='a' * 32)))
            marker.chmod(0o600)
            self.store.recover()
        self.assertEqual(self.store.sealed(self.store.ready(ME)), b'opaque-sealed')
        self.assertFalse(marker.exists())

    def test_tamper_and_permissions_refuse(self):
        self.commit()
        self.store.path(ME, 'cred').write_bytes(b'other')
        with self.assertRaises(lc.Refused):
            self.store.sealed(self.store.ready(ME))
        os.chmod(self.store.path(ME, 'json'), 0o644)
        with self.assertRaises(lc.Refused):
            self.store.receipt(ME)
        os.chmod(self.store.path(ME, 'json'), 0o600)
        target = self.store.path(ME, 'json')
        os.replace(target, self.root / 'moved')
        os.symlink(self.root / 'moved', target)
        with self.assertRaises((lc.Refused, OSError)):
            self.store.receipt(ME)
        os.chmod(self.root, 0o755)
        with self.assertRaises(lc.Refused):
            self.store.verify()

    def test_nested_lock_does_not_self_deadlock(self):
        done = threading.Event()

        def nested():
            with self.store.locked():
                with self.store.locked():
                    self.store.invalidate(ME, 'locked_credential_stale')
            done.set()
        threading.Thread(target=nested, daemon=True).start()
        self.assertTrue(done.wait(3))

    def test_remove_and_uids(self):
        self.commit()
        self.assertEqual(self.store.uids(), [ME])
        with self.store.locked():
            self.store.remove(ME)
        self.assertEqual(self.store.uids(), [])

    def test_sealed_payload_binds_receipt(self):
        self.commit()
        receipt = self.store.ready(ME)
        payload = lc.sealed_payload(self.account, 'a' * 32, bytearray(b'pw'))
        self.assertEqual(lc.open_payload(payload, receipt), bytearray(b'pw'))
        other = lc.sealed_payload(self.account, 'b' * 32, bytearray(b'pw'))
        with self.assertRaises(lc.Refused):
            lc.open_payload(other, receipt)


class FakeLive:
    def __init__(self, value=True):
        self.value = value
        self.closed = False

    def alive(self):
        return self.value

    def close(self):
        self.closed = True


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.root = root = temporary(self)
        self.python = write(root / 'usr/bin/python3.14', b'elf', 0o755)
        os.symlink('python3.14', root / 'usr/bin/python3')
        self.app = write(root / 'usr/bin/machine-control', b'elf', 0o755)
        self.resident = write(root / 'usr/lib/Machine Control/linux-runtime/desktop.py', b'#')
        self.lib = write(root / 'usr/lib/libc.so.6', b'elf', 0o755)
        self.parent_live = FakeLive()
        self.process(100, 50, self.python, [str(root / 'usr/bin/python3'), str(self.resident)], start=500)
        self.process(50, 1, self.app, [str(self.app)], start=400)

    def maps(self, *paths):
        lines = ['55d0-55d1 r--p 00000000 00:00 0 ', '7ffd-7ffe r-xp 00000000 00:00 0 [vdso]',
                 '7f00-7f01 rwxp 00000000 00:00 0 ']
        for path in paths:
            lines.append(f'7f10-7f11 r-xp 00000000 08:01 {os.stat(path).st_ino} {path}')
        return '\n'.join(lines) + '\n'

    def process(self, pid, ppid, exe, argv, start, uid=None, tracer=0, environ=b'HOME=/home/a\0', maps=None):
        uid = ME if uid is None else uid
        base = self.root / 'proc' / str(pid)
        base.mkdir(parents=True, exist_ok=True)
        write(base / 'status', f'Name:\tx\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\nGid:\t{ME}\t{ME}\t{ME}\t{ME}\n'
              f'PPid:\t{ppid}\nTracerPid:\t{tracer}\n')
        write(base / 'stat', f'{pid} (py) thon) S {ppid} ' + '0 ' * 17 + f'{start} 0 0\n')
        write(base / 'cmdline', b''.join(arg.encode() + b'\0' for arg in argv))
        write(base / 'environ', environ)
        write(base / 'maps', maps if maps is not None else self.maps(exe, self.lib))
        if (base / 'exe').is_symlink():
            (base / 'exe').unlink()
        os.symlink(exe, base / 'exe')

    def verify(self, pid=100, uid=ME, alive=True):
        provenance = lc.Provenance(self.root / 'proc', self.root / 'usr/bin/python3', self.app, self.resident,
                                   OWNERS, self.root, lambda pid: self.parent_live)
        return provenance.verify(pid, uid, lambda: alive)

    def refused(self, **kwargs):
        with self.assertRaises(lc.Refused) as caught:
            self.verify(**kwargs)
        self.assertEqual(caught.exception.code, 'locked_peer_unverified')

    def test_installed_resident_under_tauri(self):
        peer, live = self.verify()
        self.assertEqual(peer, lc.Peer(100, ME, 500, 50, 400))
        self.assertIs(live, self.parent_live)
        argv = [str(self.root / 'usr/bin/python3'), '-I', '-B', str(self.resident)]
        self.process(100, 50, self.python, argv, start=500)
        self.verify()

    def test_wrong_identity_or_dead_peer(self):
        self.refused(uid=ME + 1)
        self.refused(alive=False)
        self.refused(uid=0)
        self.parent_live.value = False
        self.refused()

    def test_forged_resident_arguments(self):
        python = str(self.root / 'usr/bin/python3')
        for argv in [[python, str(self.resident), 'extra'], [python, '-c', 'x', str(self.resident)],
                     [str(self.python), str(self.resident)], [python, '-I', '-I', str(self.resident)],
                     [python, str(self.root / 'home/a/desktop.py')]]:
            self.process(100, 50, self.python, argv, start=500)
            self.refused()

    def test_executable_images(self):
        other = write(self.root / 'usr/bin/python-other', b'elf', 0o755)
        self.process(100, 50, other, [str(self.root / 'usr/bin/python3'), str(self.resident)], start=500)
        self.refused()
        self.setUp()
        self.process(50, 1, self.python, [str(self.app)], start=400)
        self.refused()

    def test_loader_environment_tracing_and_parent_order(self):
        argv = [str(self.root / 'usr/bin/python3'), str(self.resident)]
        self.process(100, 50, self.python, argv, start=500, environ=b'LD_PRELOAD=/tmp/x.so\0')
        self.refused()
        self.process(100, 50, self.python, argv, start=500, environ=b'PYTHONUSERBASE=/tmp\0')
        self.refused()
        self.process(100, 50, self.python, argv, start=500, tracer=77)
        self.refused()
        self.process(100, 50, self.python, argv, start=500)
        self.process(50, 1, self.app, [str(self.app)], start=600)
        self.refused()
        self.process(50, 1, self.app, [str(self.app)], start=400, environ=b'LD_LIBRARY_PATH=/home/a\0')
        self.refused()

    def test_executable_mappings(self):
        argv = [str(self.root / 'usr/bin/python3'), str(self.resident)]
        writable = write(self.root / 'usr/lib/evil.so', b'elf', 0o777)
        for maps in [self.maps(self.python, writable), self.maps(self.python) + '7f20-7f21 r-xp 0 00:01 9 /memfd:x (deleted)\n',
                     self.maps(self.python) + f'7f20-7f21 r-xp 0 08:01 1 {self.lib}\n',
                     self.maps(self.python) + f'7f20-7f21 r-xp 0 08:01 {os.stat(self.lib).st_ino} {self.lib} (deleted)\n']:
            self.process(100, 50, self.python, argv, start=500, maps=maps)
            self.refused()

    def test_untrusted_install_paths(self):
        os.chmod(self.resident.parent, 0o777)
        self.refused()
        os.chmod(self.resident.parent, 0o755)
        os.chmod(self.app, 0o775)
        self.refused()


class FakeHost:
    def __init__(self, account):
        self.account_value = account
        self.locked = True
        self.started = 123456
        self.locks = []

    def console(self):
        return lc.Console('2', ME, self.started, self.locked)

    def session(self, session_id):
        return lc.Console(session_id, ME, self.started, self.locked)

    def lock(self, session_id):
        self.locks.append(session_id)
        self.locked = True

    def account(self, uid):
        return self.account_value


class FakeSealer:
    def __init__(self, payload):
        self.payload = payload

    def unseal(self, uid, sealed):
        assert sealed == b'opaque-sealed'
        return bytearray(self.payload)


class FakeWorker:
    def __init__(self, job):
        self.job = job
        self.control, self.peer = socket.socketpair()
        self.control.setblocking(False)
        self.peer.settimeout(5)
        self.lines = lc.Lines(self.control, 2048)
        self.delivered = None
        self.running = True
        self.stopped = False
        self.cancelled = threading.Event()

    def deliver(self, frame):
        self.delivered = bytes(frame)

    def cancel(self):
        self.cancelled.set()

    def alive(self):
        return self.running

    def stop(self):
        self.stopped = True
        self.running = False
        self.control.close()

    def emit(self, event, **fields):
        self.peer.sendall(json.dumps(dict(event=event, **fields)).encode() + b'\n')


class AttemptTests(unittest.TestCase):
    def setUp(self):
        self.account = lc.Account('alice', ME, ME, '/home/alice', HASH, '19990')
        self.store = lc.Store(temporary(self) / 'state', OWNERS)
        self.store.ensure()
        with self.store.locked():
            self.store.commit(self.account, 'a' * 32, b'opaque-sealed')
        self.host = FakeHost(self.account)
        payload = lc.sealed_payload(self.account, 'a' * 32, bytearray(b'hunter2'))
        self.workers = []
        self.service = lc.Service(
            self.store, FakeSealer(payload), self.host, self, spawn=self.spawn,
            peer=lambda conn: (100, ME, FakeLive()),
            timing=lc.Timing(keep=0.6, prompt=3, native=3, teardown=1, unlock=2, relock=1, poll=0.02))

    # Provenance stand-in: the kernel-facing checks are covered above.
    def verify(self, pid, uid, alive):
        return lc.Peer(pid, uid, 500, 50, 400), FakeLive()

    def spawn(self, job, account):
        worker = FakeWorker(job)
        self.addCleanup(worker.peer.close)
        self.workers.append(worker)
        return worker

    def open(self, **changes):
        server, client = socket.socketpair()
        self.addCleanup(client.close)
        client.settimeout(5)
        thread = threading.Thread(target=self.service.connection, args=(server,), daemon=True)
        thread.start()
        request = dict(schema=lc.SCHEMA, operation='authenticate', sessionId='2', sessionStarted=123456,
                       coverOwner=':1.42', coverToken=TOKEN, deadlineSeconds=30)
        request.update(changes)
        client.sendall(json.dumps(request).encode() + b'\n')
        stream = client.makefile('rb')
        self.addCleanup(stream.close)
        keeper = threading.Event()
        self.addCleanup(keeper.set)

        def keep():
            while not keeper.wait(0.15):
                try:
                    client.sendall(b'{"schema":"%s","operation":"keep"}\n' % lc.SCHEMA.encode())
                except OSError:
                    return
        if changes.pop('keep', True):
            threading.Thread(target=keep, daemon=True).start()
        self.keeper = keeper
        return client, thread, stream

    def worker(self):
        deadline = time.monotonic() + 5
        while not self.workers and time.monotonic() < deadline:
            time.sleep(0.01)
        return self.workers[-1]

    def wait(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)

    def release(self, worker=None):
        worker = worker if worker is not None else self.worker()
        self.assertEqual(worker.job['coverOwner'], ':1.42')
        self.assertEqual(worker.job['peerPid'], 100)
        worker.emit('ready')
        worker.emit('prompt')
        self.wait(lambda: worker.delivered is not None)
        self.assertEqual(worker.delivered, bytes(lc.encode_secret_frame(bytearray(b'hunter2'))))
        return worker

    def reply(self, stream, skip=('accepted', 'submitted')):
        while True:
            value = json.loads(stream.readline())
            if value.get('event') not in skip or 'errorCode' in value:
                return value

    def test_rejection_invalidates_without_retry(self):
        client, thread, stream = self.open()
        worker = self.release()
        worker.emit('dispatched')
        worker.emit('failed', code='gnome_authentication_failed')
        value = self.reply(stream)
        self.assertEqual((value['accepted'], value['errorCode'], value['credential'], value['delivery'], value['relock']),
                         (False, 'gnome_authentication_failed', 'invalidated', 'rejected', 'verified'))
        thread.join(5)
        self.assertEqual(self.store.state(ME), ('invalidated', 'gnome_authentication_failed'))
        client, thread, stream = self.open()
        self.assertEqual(self.reply(stream)['errorCode'], 'locked_credential_invalidated')
        self.assertEqual(len(self.workers), 1)

    def test_disconnect_before_prompt_uses_no_secret(self):
        client, thread, stream = self.open()
        worker = self.worker()
        worker.emit('ready')
        client.shutdown(socket.SHUT_RDWR)
        client.close()
        thread.join(5)
        self.assertTrue(worker.cancelled.is_set())
        self.assertIsNone(worker.delivered)
        self.assertEqual(self.store.state(ME), ('ready', None))
        self.assertEqual(self.host.locks, [])

    def test_disconnect_after_submission_waits_for_native_teardown(self):
        client, thread, stream = self.open()
        worker = self.release()
        worker.emit('dispatched')
        client.shutdown(socket.SHUT_RDWR)
        client.close()
        worker.cancelled.wait(5)
        self.host.locked = False  # GDM completed and unlocked late
        worker.emit('verified')
        thread.join(5)
        self.assertEqual(self.store.state(ME), ('ready', None))
        self.assertEqual(self.host.locks, ['2'])
        self.assertTrue(self.host.locked)

    def test_worker_loss_after_submission_relocks_and_keeps_saved_password(self):
        client, thread, stream = self.open()
        worker = self.release()
        worker.emit('dispatched')
        self.host.locked = False  # The native side may still unlock.
        worker.running = False
        worker.peer.close()
        value = self.reply(stream)
        self.assertEqual((value['accepted'], value['errorCode'], value['credential'], value['delivery'], value['relock']),
                         (False, 'locked_worker_exited', 'kept', 'unknown', 'verified'))
        thread.join(5)
        self.assertEqual(self.host.locks, ['2'])
        self.assertEqual(self.store.sealed(self.store.ready(ME)), b'opaque-sealed')
        self.assertEqual(len(self.workers), 1)

        next_token = '1f5b2a4e-1c3d-4e5f-8a9b-0c1d2e3f4a5b'
        client, thread, stream = self.open(coverToken=next_token)
        self.wait(lambda: len(self.workers) == 2)
        worker = self.release(self.workers[-1])
        self.assertEqual(worker.job['coverToken'], next_token)
        worker.emit('dispatched')
        worker.emit('verified')
        self.host.locked = False
        worker.emit('unlocked')
        self.assertEqual(self.reply(stream)['event'], 'unlocked')
        client.sendall(b'{"schema":"%s","operation":"end"}\n' % lc.SCHEMA.encode())
        self.assertEqual(self.reply(stream)['relock'], 'verified')
        thread.join(5)

    def test_rejection_does_not_erase_a_replacement_enrollment(self):
        client, thread, stream = self.open()
        worker = self.release()
        worker.emit('dispatched')
        with self.store.locked():
            self.store.commit(self.account, 'b' * 32, b'replacement')
        worker.emit('failed', code='gnome_authentication_failed')
        value = self.reply(stream)
        self.assertEqual((value['credential'], value['delivery']), ('kept', 'rejected'))
        self.assertEqual(self.store.sealed(self.store.ready(ME)), b'replacement')
        thread.join(5)

    def test_stale_shadow_during_prompt_withholds_secret(self):
        client, thread, stream = self.open()
        worker = self.worker()
        worker.emit('ready')
        self.host.account_value = lc.Account('alice', ME, ME, '/home/alice', HASH, '19991')
        worker.emit('prompt')
        value = self.reply(stream)
        self.assertEqual((value['errorCode'], value['credential'], value['delivery'], value['relock']),
                         ('locked_credential_stale', 'unused', 'none', 'verified'))
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertIsNone(worker.delivered)
        self.assertEqual(self.store.state(ME), ('invalidated', 'locked_credential_stale'))

    def test_stale_shadow_fails_before_pam(self):
        self.host.account_value = lc.Account('alice', ME, ME, '/home/alice', HASH, '19991')
        client, thread, stream = self.open()
        self.assertEqual(self.reply(stream), dict(schema=lc.SCHEMA, accepted=False, errorCode='locked_credential_stale'))
        self.assertEqual(self.workers, [])
        self.assertEqual(self.store.state(ME), ('invalidated', 'locked_credential_stale'))

    def test_console_mismatch_and_busy(self):
        client, thread, stream = self.open(sessionStarted=999)
        self.assertEqual(self.reply(stream)['errorCode'], 'locked_console_changed')
        self.host.locked = False
        client, thread, stream = self.open()
        self.assertEqual(self.reply(stream)['errorCode'], 'locked_console_not_locked')
        self.host.locked = True
        with self.service.busy:
            client, thread, stream = self.open()
            self.assertEqual(self.reply(stream)['errorCode'], 'locked_credential_busy')
        self.assertEqual(self.workers, [])

    def test_status_reports_enrollment(self):
        server, client = socket.socketpair()
        self.addCleanup(client.close)
        client.settimeout(5)
        threading.Thread(target=self.service.connection, args=(server,), daemon=True).start()
        client.sendall(b'{"schema":"%s","operation":"status"}\n' % lc.SCHEMA.encode())
        with client.makefile('rb') as stream:
            value = json.loads(stream.readline())
        self.assertEqual((value['accepted'], value['enrolled'], value['enrollment'], value['busy']),
                         (True, True, 'ready', False))

    def test_guarded_stream_renews_ends_and_relocks(self):
        client, thread, stream = self.open()
        self.assertEqual(self.reply(stream, skip=())['event'], 'accepted')
        worker = self.release()
        worker.emit('dispatched')
        self.assertEqual(self.reply(stream, skip=())['event'], 'submitted')
        worker.emit('verified')
        self.host.locked = False
        worker.emit('unlocked')
        self.assertTrue(self.reply(stream)['accepted'])
        schema = lc.SCHEMA.encode()
        client.sendall(b'{"schema":"%s","operation":"renew","deadlineSeconds":45}\n' % schema)
        self.assertEqual(self.reply(stream), dict(schema=lc.SCHEMA, event='renewed', deadlineSeconds=45))
        client.sendall(b'{"schema":"%s","operation":"end"}\n' % schema)
        value = self.reply(stream)
        self.assertEqual((value['event'], value['accepted'], value['errorCode'], value['relock'], value['credential']),
                         ('ended', True, None, 'verified', 'kept'))
        self.assertEqual(self.host.locks, ['2'])

    def test_guarded_heartbeat_loss_relocks(self):
        client, thread, stream = self.open()
        worker = self.release()
        worker.emit('dispatched')
        worker.emit('verified')
        self.host.locked = False
        worker.emit('unlocked')
        self.assertTrue(self.reply(stream)['accepted'])
        self.keeper.set()
        value = self.reply(stream)
        self.assertEqual((value['errorCode'], value['relock'], value['credential']),
                         ('locked_owner_heartbeat_lost', 'verified', 'kept'))
        self.assertEqual(self.host.locks, ['2'])


class FakeChannel:
    def __init__(self):
        self.events = []
        self.cancelled = False
        self.secret_requests = 0

    def emit(self, event, **fields):
        self.events.append((event, fields.get('code')))

    def poll(self):
        return self.cancelled

    def secret(self, deadline):
        self.secret_requests += 1
        return 'hunter2'


class FakeGuard:
    def __init__(self):
        self.before = None
        self.after = None
        self.calls = []

    def problem(self, submitted=False):
        self.calls.append(submitted)
        return self.after if submitted else self.before


class FakeProvider:
    def __init__(self, console):
        self.console = console
        self.locked = True
        self.unlocked = False

    def observe(self):
        return gnome_unlock.Observation(self.console, self.locked, self.unlocked)

    def require_locked(self, console):
        if console != self.console or not self.locked:
            raise gnome_unlock.UnlockRefused('gnome_locked_console_changed')


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.console = gnome_unlock.Console('/org/freedesktop/login1/session/_32', '2', 123456, ':1.10')
        self.provider = FakeProvider(self.console)
        self.channel = FakeChannel()
        self.guard = FakeGuard()
        self.now = 0.0
        self.conversation = lc.Conversation(gnome_unlock, self.provider, self.console, self.channel, self.guard,
                                            lc.WorkerTiming(prompt=10, secret=5, native=30, teardown=5, unlock=10),
                                            clock=lambda: self.now)

    def test_unrecognised_prompt_never_requests_secret(self):
        self.assertIsNone(self.conversation.query('gdm-password', 'Passwort:'))
        self.assertEqual(self.channel.events, [('failed', 'gnome_password_prompt_unavailable')])
        self.assertEqual(self.channel.secret_requests, 0)

    def test_authority_is_required_before_secret(self):
        self.guard.before = 'locked_cover_lost'
        self.assertIsNone(self.conversation.query('gdm-password', 'Password:'))
        self.assertEqual(self.channel.events, [('failed', 'locked_cover_lost')])
        self.assertEqual(self.channel.secret_requests, 0)

    def test_success_then_live_guard(self):
        self.assertEqual(self.conversation.query('gdm-password', 'Password: '), 'hunter2')
        self.assertEqual(self.channel.events, [('prompt', None), ('dispatched', None)])
        self.assertEqual(self.guard.calls, [False, False])
        self.assertTrue(self.conversation.tick())
        self.assertEqual(self.guard.calls[-1], True)  # CheckLive after submission
        self.conversation.complete('gdm-password')
        self.assertTrue(self.conversation.succeeded)
        self.conversation.native('gnome_authentication_failed')  # ordinary teardown after completion
        self.provider.locked, self.provider.unlocked = False, True
        self.assertTrue(self.conversation.tick())
        self.assertEqual(self.conversation.phase, 'guarding')
        self.provider.locked, self.provider.unlocked = True, False
        self.assertFalse(self.conversation.tick())
        self.assertEqual([event for event, _ in self.channel.events],
                         ['prompt', 'dispatched', 'verified', 'unlocked', 'locked'])

    def test_cancel_after_submission_waits_for_native_end(self):
        cancelled = []
        self.conversation.cancel_verifier = lambda: cancelled.append(True)
        self.conversation.query('gdm-password', 'Password:')
        self.channel.cancelled = True
        self.assertTrue(self.conversation.tick())
        self.assertEqual((self.conversation.phase, cancelled), ('teardown', [True]))
        self.conversation.complete('gdm-password')
        self.assertEqual(self.channel.events[-2:], [('verified', None), ('guard_lost', 'gnome_unlock_cancelled')])
        self.assertTrue(self.conversation.done and self.conversation.succeeded)

    def test_submission_without_native_answer_is_unknown(self):
        self.conversation.query('gdm-password', 'Password:')
        self.now = 31
        self.assertFalse(self.conversation.tick())
        self.assertEqual(self.channel.events[-1], ('failed', 'gnome_unlock_delivery_unknown'))

    def test_native_stop_after_submission_is_unknown(self):
        self.conversation.query('gdm-password', 'Password:')
        self.conversation.stopped()
        self.assertEqual(self.channel.events[-1], ('failed', 'gnome_unlock_delivery_unknown'))

    def test_verification_failure_during_cancellation_is_unknown(self):
        self.conversation.query('gdm-password', 'Password:')
        self.channel.cancelled = True
        self.conversation.verification_failed('gdm-password')
        self.assertEqual(self.channel.events[-1], ('failed', 'gnome_unlock_delivery_unknown'))

    def test_second_prompt_after_submission_is_rejection(self):
        self.conversation.query('gdm-password', 'Password:')
        self.assertIsNone(self.conversation.query('gdm-password', 'Password:'))
        self.assertEqual(self.channel.events[-1], ('failed', 'gnome_authentication_failed'))
        self.assertEqual(self.channel.secret_requests, 1)

    def test_opening_timeout_and_guard(self):
        self.now = 11
        self.assertFalse(self.conversation.tick())
        self.assertEqual(self.channel.events, [('failed', 'gnome_authentication_timeout')])


class WorkerGuardTests(unittest.TestCase):
    def test_owner_binding_and_cover_methods(self):
        console = gnome_unlock.Console('/s', '2', 5, ':1.10')
        job = dict(uid=ME, sessionId='2', sessionStarted=5, coverOwner=':1.42', coverToken=TOKEN, peerPid=100)
        calls = []
        answers = {'GetConnectionUnixProcessID': 100, 'GetConnectionUnixUser': ME, 'CheckAuthority': True,
                   'CheckLive': True}

        class Provider:
            session = object()

            def call(self, bus, destination, path, interface, method, parameters, signature, timeout=1000):
                calls.append((destination, method, parameters))
                return (answers[method],)

        samples = [None, ('g', 'a', 'm'), ('g', 'a', 'm'), ('g', 'b', 'm'), ('h', 'a', 'm')]
        guard = lc.WorkerGuard(Provider(), console, job, lambda: samples.pop(0), sleep=lambda _: None)
        guard.bind()
        self.assertIn((':1.10', 'CheckAuthority', ('(ss)', (':1.42', TOKEN))), calls)
        self.assertIsNone(guard.problem(True))
        self.assertEqual(calls[-1][1], 'CheckLive')
        self.assertEqual(guard.problem(), 'locked_local_input')
        self.assertEqual(guard.problem(), 'locked_activity_observer_lost')
        answers['CheckLive'] = False
        self.assertEqual(guard.problem(True), 'locked_cover_lost')
        answers['GetConnectionUnixProcessID'] = 101
        with self.assertRaises(lc.Refused):
            lc.WorkerGuard(Provider(), console, job, lambda: ('g', 'a', 'm')).bind()


class CliTests(unittest.TestCase):
    def run_main(self, argv, euid):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = lc.main(argv, euid=euid)
        return status, json.loads(output.getvalue())

    def test_static_refusals(self):
        self.assertEqual(self.run_main(['x', 'setup'], 1000),
                         (1, {'accepted': False, 'errorCode': 'locked_credential_root_required'}))
        self.assertEqual(self.run_main(['x', '/tmp/evil'], 0)[1]['errorCode'], 'locked_credential_operation_invalid')
        self.assertEqual(self.run_main(['x', 'setup', 'extra'], 0)[1]['errorCode'], 'locked_credential_operation_invalid')
        # This source checkout is not the pinned root-owned packaged path.
        self.assertEqual(self.run_main(['x', 'setup'], 0)[1]['errorCode'], 'locked_credential_runtime_unverified')

    def test_operator_uid(self):
        self.assertEqual(lc.operator_uid({'PKEXEC_UID': '1000'}), 1000)
        self.assertIsNone(lc.operator_uid({}, required=False))
        for value in [None, '', '0', '01000', '1000 ', '-1', '65534', 'x']:
            with self.assertRaises(lc.Refused):
                lc.operator_uid({} if value is None else {'PKEXEC_UID': value})

    def test_unit_runs_only_the_pinned_runtime(self):
        text = lc.UNIT_BYTES.decode()
        self.assertTrue(text.startswith('# machine-control-locked-use/v1\n'))
        self.assertIn('\nExecStart=/usr/bin/python3 -I -B /usr/lib/machine-control/locked-runtime/locked-credential.py serve\n', text)
        self.assertNotIn('%', text)
        self.assertNotIn('/home', text)
        self.assertNotIn('/tmp', text)

    def test_runtime_receipt(self):
        root = temporary(self)
        runtime = root / 'locked-runtime'
        runtime.mkdir()
        files = []
        for name in lc.RUNTIME_FILES:
            data = f'# {name}\n'.encode()
            write(runtime / name, data)
            files.append(dict(path=name, sha256=lc.file_digest(data)))
        manifest = write(root / 'desktop-runtime.json', json.dumps(dict(schema=lc.RUNTIME_SCHEMA, files=files)))
        lc.verify_runtime(runtime, manifest, OWNERS, root)
        write(runtime / 'gnome_unlock.py', b'changed')
        with self.assertRaises(lc.Refused):
            lc.verify_runtime(runtime, manifest, OWNERS, root)

    def test_secure_path(self):
        root = temporary(self)
        file = write(root / 'a/b.py', b'x')
        lc.secure_path(file, owners=OWNERS, chain_root=root)
        link = root / 'a/link.py'
        os.symlink(file, link)
        with self.assertRaises(lc.Refused):
            lc.secure_path(link, owners=OWNERS, chain_root=root)
        os.chmod(root / 'a', 0o775)
        with self.assertRaises(lc.Refused):
            lc.secure_path(file, owners=OWNERS, chain_root=root)


if __name__ == '__main__':
    unittest.main()
