"""Bounded private transport to the pinned shared authority; no policy here."""
from collections import deque
import json
import math
import os
from pathlib import Path
import queue
import select
import struct
import subprocess
import sys
import threading
import time

MAXIMUM = 16 * 1024 * 1024


class PolicyError(Exception):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError('ipc_duplicate_key')
        result[key] = value
    return result


def decode(body):
    def invalid(_value):
        raise PolicyError('ipc_invalid_number')
    value = json.loads(body.decode('utf-8'), object_pairs_hook=unique_object,
                       parse_constant=invalid)
    if not isinstance(value, dict):
        raise PolicyError('ipc_invalid_frame')
    return value


class Policy:
    """Replies never wait for GLib. Native events and async completions do."""
    def __init__(self, post, receive, failed, root=None, command=None):
        self.post, self.receive, self.failed = post, receive, failed
        self.lock = threading.RLock()
        self.pending = {}
        self.events = deque()
        self.event_bytes = 0
        self.event_posted = False
        self.snapshot = {}
        self.sequence = 0
        self.closed = None
        self.outgoing = queue.Queue(maxsize=64)
        self.output_bytes = 0
        self.reaped = threading.Event()
        if root is None:
            native=Path(__file__).resolve().parent
            staged=native/'shared-policy'
            # linuxdeploy rewrites ELF resources under usr/lib. The installed
            # pinned interpreter belongs beside the Python client in usr/share;
            # source-native harnesses retain the explicitly staged local tree.
            if staged.exists():root=staged
            elif len(native.parents)>2 and native.parents[1].name=='lib' and native.parents[2].name=='usr':
                root=native.parents[2]/'share/machine-control/shared-policy'
            else:raise PolicyError('packaged_policy_unavailable')
        root=Path(root)
        # command is constructor injection for transport fixtures, never an
        # environment override or a production system-Node fallback.
        if command is None:
            executable, entry = root / 'node', root / 'policy/node/main.ts'
            if not executable.is_file() or not os.access(executable, os.X_OK) or not entry.is_file():
                raise PolicyError('packaged_policy_unavailable')
            command = [str(executable), str(entry)]
        if sys.platform=='linux':
            command=[sys.executable,'-I','-B',str(Path(__file__).with_name('policy_exec.py')),str(os.getpid()),*command]
        self.process = subprocess.Popen(command, cwd=root, env={}, close_fds=True,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, bufsize=0)
        os.set_blocking(self.process.stdin.fileno(), False)
        for function, name in [(self._reader, 'reader'), (self._writer, 'writer'),
                               (self._drain, 'stderr')]:
            threading.Thread(target=function, daemon=True, name='mc-policy-'+name).start()
        try:
            hello = self.call({'method':'hello', 'protocolVersion':2}, timeout=15)
            if hello.get('protocolVersion') != 2 or hello.get('admissionSchema') != 'machine-control-admission/v2':
                raise PolicyError('unsupported_policy_protocol')
        except BaseException:
            self.stop()
            raise

    @property
    def alive(self):
        with self.lock:
            return self.closed is None

    def browser_state(self):
        with self.lock:
            return self.snapshot

    def call(self, frame, timeout=5):
        done, reply = threading.Event(), []
        def completed(value, error):
            reply.append((value, error))
            done.set()
        self.request(frame, completed, timeout=timeout, direct=True)
        done.wait()  # Independent reader/deadline path owns this completion.
        value, error = reply[0]
        if error:
            raise PolicyError(error)
        return value

    def request(self, frame, completion, timeout=5, direct=False):
        if not isinstance(frame, dict) or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise PolicyError('invalid_policy_request')
        def finish(value, error):
            if direct:
                completion(value, error)
            else:
                self.post(completion, value, error)
        with self.lock:
            if self.closed is not None or len(self.pending) >= 128:
                finish(None, 'control_policy_unavailable')
                return
            self.sequence += 1
            identifier = str(self.sequence)
            timer = threading.Timer(timeout, self._fail, args=('ipc_reply_timeout', identifier))
            timer.daemon = True
            self.pending[identifier] = (finish, timer)
            timer.start()
        try:
            self._enqueue({**frame, 'id':identifier})
        except (OSError, ValueError, TypeError, PolicyError):
            self._fail('ipc_write_invalid')

    def _enqueue(self, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':')).encode()
        if not 0 < len(body) <= MAXIMUM:
            raise PolicyError('ipc_frame_size')
        frame = struct.pack('<I', len(body)) + body
        with self.lock:
            if self.closed is not None or self.output_bytes + len(frame) > 2 * MAXIMUM:
                raise PolicyError('ipc_write_capacity')
            try:
                self.outgoing.put_nowait(frame)
            except queue.Full:
                raise PolicyError('ipc_write_capacity') from None
            self.output_bytes += len(frame)

    def _writer(self):
        try:
            while self.alive:
                try:
                    frame = self.outgoing.get(timeout=.1)
                except queue.Empty:
                    continue
                offset, deadline = 0, time.monotonic() + 3
                while offset < len(frame):
                    if not self.alive:
                        return
                    if time.monotonic() >= deadline:
                        raise PolicyError('ipc_write_timeout')
                    if not select.select([], [self.process.stdin], [], .1)[1]:
                        continue
                    try:
                        offset += os.write(self.process.stdin.fileno(), frame[offset:])
                    except BlockingIOError:
                        continue
                with self.lock:
                    self.output_bytes -= len(frame)
        except (OSError, ValueError, PolicyError):
            self._fail('ipc_write_failed')

    def _exact(self, count):
        value = bytearray()
        while len(value) < count:
            part = self.process.stdout.read(count - len(value))
            if not part:
                raise PolicyError('ipc_closed')
            value.extend(part)
        return bytes(value)

    def _reader(self):
        try:
            while self.alive:
                size = struct.unpack('<I', self._exact(4))[0]
                if not 0 < size <= MAXIMUM:
                    raise PolicyError('ipc_frame_size')
                frame = decode(self._exact(size))
                kind = frame.get('type')
                if kind == 'reply':
                    valid = frame.get('ok') is True and isinstance(frame.get('data'), dict) or (
                        frame.get('ok') is False and isinstance(frame.get('errorCode'), str) and
                        0 < len(frame['errorCode']) <= 128)
                    if not valid:
                        raise PolicyError('ipc_invalid_reply')
                    with self.lock:
                        pending = self.pending.pop(frame.get('id'), None)
                    if pending is None:
                        raise PolicyError('ipc_unknown_reply')
                    finish, timer = pending
                    timer.cancel()
                    if frame.get('ok') is True and isinstance(frame.get('data'), dict):
                        finish(frame['data'], None)
                    elif frame.get('ok') is False and isinstance(frame.get('errorCode'), str):
                        finish(None, frame['errorCode'])
                    else:
                        raise PolicyError('ipc_invalid_reply')
                elif kind == 'browser.state' and isinstance(frame.get('state'), dict):
                    with self.lock:
                        self.snapshot = frame['state']
                elif kind == 'request.finished' and isinstance(frame.get('result'), dict):
                    # Core emits this diagnostic completion as well as resolving
                    # browser.call. Only the correlated RPC owns completion;
                    # neither replay nor a second native dispatch is allowed.
                    pass
                elif kind in {'provider.send', 'provider.close', 'access.event', 'native.check'}:
                    with self.lock:
                        if len(self.events) >= 512 or self.event_bytes + size > 2 * MAXIMUM:
                            raise PolicyError('ipc_event_capacity')
                        self.events.append((frame, size))
                        self.event_bytes += size
                        if not self.event_posted:
                            self.event_posted = True
                            self.post(self._events)
                else:
                    raise PolicyError('ipc_invalid_event')
        except Exception:
            self._fail('ipc_invalid_or_closed')

    def _events(self):
        # One bounded batch preserves native Stop/notice scheduling under load.
        for _ in range(32):
            with self.lock:
                if self.closed is not None:
                    self.events.clear()
                    self.event_bytes = 0
                if not self.events:
                    self.event_posted = False
                    return False
                frame, size = self.events.popleft()
                self.event_bytes -= size
            try:
                self.receive(frame)
            except Exception:
                self._fail('native_event_failed')
                return False
        self.post(self._events)
        return False

    def _drain(self):
        try:
            while self.process.stderr.read(4096):
                pass  # No payload or inherited environment reaches diagnostics.
        except OSError:
            pass

    def _fail(self, reason, expected=None):
        with self.lock:
            if self.closed is not None or (expected is not None and expected not in self.pending):
                return
            self.closed = reason
            pending, self.pending = self.pending, {}
            self.snapshot = {}
        for finish, timer in pending.values():
            timer.cancel()
            finish(None, reason)
        if reason != 'resident_stopping':
            self.post(self.failed, reason)
        def reap():
            try:
                if self.process.poll() is None:
                    self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            finally:
                for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                    stream.close()
                self.reaped.set()
        threading.Thread(target=reap, daemon=True, name='mc-policy-reap').start()

    def stop(self):
        self._fail('resident_stopping')
        self.reaped.wait()
