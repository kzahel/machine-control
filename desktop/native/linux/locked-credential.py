#!/usr/bin/python3
"""Root-owned locked-use credential enrollment and guarded GDM authentication.

The packaged copy lives at /usr/lib/machine-control/locked-runtime, owned
by dpkg. Each operation is a fixed verb. No caller-supplied path,
environment value or code is consumed.

  setup   pkexec only. Enrol PKEXEC_UID from its exact unlocked local
          Wayland console. The one-shot secret arrives on inherited stdin.
  remove  pkexec or root. Erase PKEXEC_UID's enrollment (every enrollment
          without PKEXEC_UID); uninstall the service when none remain.
  serve   systemd only. The persistent typed root socket service.
  worker  serve only. One exact GDM conversation as the console UID.

Secret frame (setup stdin; serve to worker uses the binary form):
  binary   b"MCSECRET1\\0" + u16 big-endian length + bytes, then EOF
  newline  bytes + b"\\n", then EOF
  1..4096 bytes of UTF-8 without NUL, CR or LF.

Socket /run/machine-control-locked-use/credential.sock: newline JSON, no
secrets, one request per connection, "schema":S required on every request.
Only the kernel-verified installed resident is served (see Provenance).

  {"schema":S,"operation":"status"}
  -> {"schema":S,"accepted":true,"operation":"status","enrolled":b,
      "enrollment":"absent|ready|invalidated","reason":code|null,"busy":b}

  {"schema":S,"operation":"authenticate","sessionId":"2",
   "sessionStarted":<logind TimestampMonotonic>,"coverOwner":":1.42",
   "coverToken":<cover id>,"deadlineSeconds":1..900}
  -> {"event":"accepted"}   worker started; the cover is not yet proven
  -> {"event":"submitted"}  the secret went to GDM
  -> {"accepted":true,"event":"unlocked","credential":"kept",
      "delivery":"verified"}   GDM verified, exact console unlocked
  -> {"event":"renewed","deadlineSeconds":n}   after each accepted renewal
  -> {"event":"ended","accepted":b,"errorCode":code|null,
      "relock":"verified|unverified|session_ended",
      "credential":"unused|kept|invalidated",
      "delivery":"none|verified|rejected|unknown"}
  Refusals before the worker starts are one line with accepted:false and
  errorCode. The client sends {"schema":S,"operation":"keep"} at least once
  a second, {"schema":S,"operation":"renew","deadlineSeconds":n} to set its
  deadline n seconds from now, and {"schema":S,"operation":"end"} to finish.
  "ended" is accepted only for "end" after unlock and a verified relock.
  Every ending, including a closed connection, cancels a submitted GDM
  conversation, waits for its native end, relocks the exact session and
  waits until logind reports it locked.

The worker reads two read-only methods on the cover object
(/dev/machinecontrol/CoveredDesktop, dev.machinecontrol.CoveredDesktop1),
addressed to the unique name owning org.gnome.ScreenShield:

  CheckAuthority(s owner, s token) -> (b)  before the secret is requested
      and again before it is answered: exact owner and lease, locked,
      pixels verified, idle, no unlock observed.
  CheckLive(s owner, s token) -> (b)  after submission and after unlock:
      exact current covered owner and lease with verified pixels.

Security limitation: the service accepts only the installed resident. It
checks kernel process facts: SO_PEERCRED and pidfd, executable inodes, the
root-owned resident script and Tauri parent, executable mappings, loader
environment and ptrace state. Code running as the same user still controls
that user's session bus, compositor and session, and it can launch the real
application. Where ptrace policy allows, it can inspect its own
descendants. The service prevents export and replay of the secret. It does
not prevent same-user control of the unlocked desktop.
"""

from __future__ import annotations

from collections import deque
import contextlib
import ctypes
import dataclasses
import errno
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import threading
import time


SCHEMA = 'machine-control-locked-credential/v1'
RECEIPT_SCHEMA = 'machine-control-locked-credential-enrollment/v1'
SEALED_SCHEMA = 'machine-control-locked-credential-sealed/v1'
ATTEMPT_SCHEMA = 'machine-control-locked-credential-attempt/v1'
RUNTIME_SCHEMA = 'machine-control-linux-desktop-runtime/v0'

RUNTIME = Path('/usr/lib/machine-control/locked-runtime')
SCRIPT = RUNTIME / 'locked-credential.py'
RUNTIME_FILES = ('locked-credential.py', 'gnome_unlock.py', 'activity.py')
MANIFEST = Path('/usr/lib/Machine Control/linux-runtime/desktop-runtime.json')
RESIDENT = Path('/usr/lib/Machine Control/linux-runtime/desktop.py')
APPLICATION = Path('/usr/bin/machine-control')
PYTHON = Path('/usr/bin/python3')
SETPRIV = '/usr/bin/setpriv'
LOGINCTL = '/usr/bin/loginctl'
SYSTEMCTL = '/usr/bin/systemctl'
SYSTEMD_CREDS = '/usr/bin/systemd-creds'
LIBCRYPT = 'libcrypt.so.1'
STATE = Path('/var/lib/machine-control-locked-use')
RUNDIR = Path('/run/machine-control-locked-use')
SOCKET_PATH = RUNDIR / 'credential.sock'
UNIT = Path('/etc/systemd/system/machine-control-locked-use.service')
SERVICE = 'machine-control-locked-use.service'
INSTALL_LOCK = Path('/run/machine-control-locked-use-install.lock')
COVER_PATH = '/dev/machinecontrol/CoveredDesktop'
COVER_INTERFACE = 'dev.machinecontrol.CoveredDesktop1'

MAX_SECRET = 4096
SECRET_MAGIC = b'MCSECRET1\0'
FRAME_LIMIT = len(SECRET_MAGIC) + 2 + MAX_SECRET
MAX_REQUEST = 1024
CRYPT_DATA_SIZE = 32768
ROOT_OWNERS = frozenset({0})
CLEAN_ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}
SO_PEERPIDFD = getattr(socket, 'SO_PEERPIDFD', 77)

SESSION_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.]{0,63}')
OWNER = re.compile(r':[0-9]{1,10}\.[0-9]{1,10}')
TOKEN = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}')
USER_NAME = re.compile(r'[a-z_][a-z0-9_.-]{0,31}')
CRYPT_HASH = re.compile(r'\$[A-Za-z0-9./$=,+-]{2,1024}')
HEX32 = re.compile(r'[0-9a-f]{32}')
HEX64 = re.compile(r'[0-9a-f]{64}')

ERRORS = frozenset('''
locked_credential_refused locked_credential_root_required
locked_credential_operation_invalid locked_credential_runtime_unverified
locked_credential_operator_unverified locked_console_unavailable
locked_console_changed locked_console_not_locked locked_console_locked
locked_console_relocked locked_account_unavailable
locked_account_password_change_required locked_secret_unavailable
unlock_credential_invalid locked_credential_sealing_unavailable
locked_credential_unenrolled locked_credential_invalidated
locked_credential_stale locked_credential_busy
locked_credential_store_unverified locked_credential_delivery_unknown
locked_installation_unowned locked_service_unavailable
locked_service_stopping locked_request_invalid locked_peer_unverified
locked_owner_disconnected locked_owner_exited locked_owner_ended
locked_owner_heartbeat_lost locked_guard_deadline locked_worker_failed
locked_worker_spawn_denied locked_worker_spawn_failed locked_worker_job_invalid
locked_worker_executable_denied locked_worker_files_denied locked_worker_identity_denied
locked_worker_console_probe_failed locked_worker_guard_probe_failed locked_worker_gdm_adapter_failed
locked_worker_check_failed locked_worker_secret_prompt_failed
locked_worker_exited locked_cover_unverified locked_cover_lost
locked_activity_observer_lost locked_local_input
locked_session_bus_unverified gnome_console_unavailable
gnome_locked_console_changed gnome_password_prompt_unavailable
gnome_password_invalid gnome_password_unavailable
gnome_authentication_failed gnome_authentication_unavailable
gnome_authentication_timeout gnome_unlock_delivery_unknown
gnome_unlocked_effect_unverified gnome_unlock_cancelled
'''.split())
INVALIDATION_REASONS = frozenset({
    'locked_credential_stale', 'gnome_authentication_failed',
    'locked_credential_delivery_unknown', 'locked_credential_store_unverified'})
WORKER_EVENTS = frozenset({
    'ready', 'prompt', 'dispatched', 'verified', 'unlocked', 'locked', 'failed', 'guard_lost'})

UNIT_MARKER = b'# machine-control-locked-use/v1'
UNIT_BYTES = UNIT_MARKER + b'''
[Unit]
Description=Machine Control locked-use credential service
After=systemd-logind.service
Requires=systemd-logind.service
ConditionPathExists=/usr/lib/machine-control/locked-runtime/locked-credential.py
[Service]
Type=simple
ExecStart=/usr/bin/python3 -I -B /usr/lib/machine-control/locked-runtime/locked-credential.py serve
User=root
RuntimeDirectory=machine-control-locked-use
RuntimeDirectoryMode=0755
StateDirectory=machine-control-locked-use
StateDirectoryMode=0700
UMask=0077
Environment=LANG=C LC_ALL=C
NoNewPrivileges=true
CapabilityBoundingSet=CAP_SETUID CAP_SETGID CAP_KILL CAP_SYS_PTRACE CAP_DAC_READ_SEARCH
ProtectSystem=strict
ProtectHome=read-only
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX
RestrictNamespaces=true
RestrictSUIDSGID=true
LockPersonality=true
KillMode=control-group
TimeoutStopSec=30
Restart=on-failure
RestartSec=2
[Install]
WantedBy=multi-user.target
'''


class Refused(Exception):
    """A stable code from ERRORS. Never carries paths, input or secrets."""

    def __init__(self, code):
        super().__init__(code if code in ERRORS else 'locked_credential_refused')

    @property
    def code(self):
        return self.args[0]


class Closed(Exception):
    pass


def code_of(error, fallback='locked_worker_failed'):
    text = str(error)
    return text if text in ERRORS else fallback


def wipe(buffer):
    if buffer is not None:
        buffer[:] = bytes(len(buffer))


def strict_int(text, minimum=0, maximum=2**63 - 1):
    if (not isinstance(text, str) or not re.fullmatch(r'[0-9]{1,19}', text)
            or (len(text) > 1 and text[0] == '0')):
        raise ValueError('integer')
    value = int(text)
    if not minimum <= value <= maximum:
        raise ValueError('integer')
    return value


def exact_int(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


# Filesystem trust ---------------------------------------------------------

def secure_path(path, kind='file', owners=ROOT_OWNERS, chain_root='/',
                code='locked_credential_runtime_unverified', seen=None):
    """Require a canonical path whose every component is owner-controlled."""
    path, chain_root = Path(path), Path(chain_root)
    try:
        if (not path.is_absolute() or os.path.realpath(path) != str(path)
                or (path != chain_root and chain_root not in path.parents)):
            raise Refused(code)
        for directory in reversed(path.parents):
            if directory != chain_root and chain_root not in directory.parents:
                continue
            if seen is not None and directory in seen:
                continue
            info = os.lstat(directory)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid not in owners or info.st_mode & 0o022:
                raise Refused(code)
            if seen is not None:
                seen.add(directory)
        info = os.lstat(path)
    except OSError:
        raise Refused(code) from None
    expected = stat.S_ISDIR if kind == 'directory' else stat.S_ISREG
    if not expected(info.st_mode) or info.st_uid not in owners or info.st_mode & 0o022:
        raise Refused(code)
    return info


def read_secure_file(path, limit, owners=ROOT_OWNERS, private=False,
                     code='locked_credential_runtime_unverified'):
    """Read a regular file without following a final symlink."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid not in owners
                or info.st_mode & (0o077 if private else 0o022) or info.st_size > limit):
            raise Refused(code)
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                return b''.join(chunks)
            total += len(chunk)
            if total > limit:
                raise Refused(code)
            chunks.append(chunk)
    finally:
        os.close(fd)


def sync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_atomic(path, data, mode):
    path = Path(path)
    staged = path.parent / f'.{path.name}.{secrets.token_hex(8)}'
    fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
    try:
        try:
            os.fchmod(fd, mode)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(staged, path)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    sync_directory(path.parent)


def file_digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_runtime(runtime=RUNTIME, manifest=MANIFEST, owners=ROOT_OWNERS, chain_root='/'):
    """Installed helper files must match the packaged runtime receipt."""
    secure_path(runtime, 'directory', owners, chain_root)
    secure_path(manifest, 'file', owners, chain_root)
    try:
        value = json.loads(read_secure_file(manifest, 1 << 20, owners))
        if value.get('schema') != RUNTIME_SCHEMA:
            raise Refused('locked_credential_runtime_unverified')
        entries = {row['path']: row['sha256'] for row in value['files']
                   if isinstance(row, dict) and row.get('path') in RUNTIME_FILES}
    except (ValueError, KeyError, TypeError):
        raise Refused('locked_credential_runtime_unverified') from None
    if set(entries) != set(RUNTIME_FILES):
        raise Refused('locked_credential_runtime_unverified')
    for name in RUNTIME_FILES:
        file = Path(runtime) / name
        secure_path(file, 'file', owners, chain_root)
        if file_digest(read_secure_file(file, 1 << 22, owners)) != entries[name]:
            raise Refused('locked_credential_runtime_unverified')


# Secret frames --------------------------------------------------------------

def validate_secret(body):
    if not 1 <= len(body) <= MAX_SECRET or any(byte in (0, 10, 13) for byte in body):
        raise Refused('locked_secret_unavailable')
    try:
        body.decode('utf-8')
    except UnicodeDecodeError:
        raise Refused('locked_secret_unavailable') from None
    return body


def parse_secret_frame(frame):
    """Return a fresh bytearray; the caller wipes both buffers."""
    view = memoryview(frame)
    try:
        if frame[:len(SECRET_MAGIC)] == SECRET_MAGIC:
            start = len(SECRET_MAGIC) + 2
            if len(frame) < start or int.from_bytes(frame[start - 2:start], 'big') != len(frame) - start:
                raise Refused('locked_secret_unavailable')
            body = bytearray(view[start:])
        elif frame.endswith(b'\n') and frame.count(b'\n') == 1:
            body = bytearray(view[:-1])
        else:
            raise Refused('locked_secret_unavailable')
    finally:
        view.release()
    try:
        return validate_secret(body)
    except BaseException:
        wipe(body)
        raise


def encode_secret_frame(secret):
    validate_secret(secret)
    frame = bytearray(len(SECRET_MAGIC) + 2 + len(secret))
    frame[:len(SECRET_MAGIC)] = SECRET_MAGIC
    frame[len(SECRET_MAGIC):len(SECRET_MAGIC) + 2] = len(secret).to_bytes(2, 'big')
    frame[len(SECRET_MAGIC) + 2:] = secret
    return frame


def read_fd_bounded(fd, limit, deadline, code='locked_secret_unavailable'):
    buffer = bytearray(limit + 1)
    view = memoryview(buffer)
    size = 0
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Refused(code)
            if not select.select([fd], [], [], remaining)[0]:
                continue
            count = os.readv(fd, [view[size:]])
            if not count:
                return bytearray(view[:size])
            size += count
            if size > limit:
                raise Refused(code)
    finally:
        view.release()
        wipe(buffer)


def read_secret_stream(fd, seconds=120):
    if os.isatty(fd):
        raise Refused('locked_secret_unavailable')
    frame = read_fd_bounded(fd, FRAME_LIMIT, time.monotonic() + seconds)
    try:
        return parse_secret_frame(frame)
    finally:
        wipe(frame)


# Local account --------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Account:
    name: str
    uid: int
    gid: int
    home: str
    hashed: str = dataclasses.field(repr=False)
    changed: str

    @property
    def binding(self):
        material = '\0'.join(('machine-control-locked-shadow/v1', self.name, self.hashed, self.changed))
        return hashlib.sha256(material.encode()).hexdigest()


def local_account(uid, passwd=Path('/etc/passwd'), shadow=Path('/etc/shadow'),
                  owners=ROOT_OWNERS, today=None):
    """A files-backed account with a usable crypt hash, checked without PAM."""
    code = 'locked_account_unavailable'
    try:
        def rows(path, width):
            lines = read_secure_file(path, 4 << 20, owners, code=code).decode('utf-8').splitlines()
            values = [line.split(':') for line in lines if line and not line.startswith(('#', '+', '-'))]
            if any(len(value) != width for value in values):
                raise Refused(code)
            return values
        users = rows(passwd, 7)
        matches = [row for row in users if row[2] == str(uid)]
        if len(matches) != 1:
            raise Refused(code)
        name, password, _uid, gid, _gecos, home, _shell = matches[0]
        if (not USER_NAME.fullmatch(name) or password != 'x'
                or sum(row[0] == name for row in users) != 1 or not home.startswith('/')):
            raise Refused(code)
        gid = strict_int(gid, 0, 2**32 - 2)
        entries = [row for row in rows(shadow, 9) if row[0] == name]
        if len(entries) != 1:
            raise Refused(code)
        _name, hashed, changed, _minimum, maximum, _warn, inactive, expire, _reserved = entries[0]
    except (OSError, UnicodeError, ValueError):
        raise Refused(code) from None
    if not CRYPT_HASH.fullmatch(hashed):
        raise Refused(code)
    today = int(time.time() // 86400) if today is None else today
    try:
        changed_day = strict_int(changed) if changed else None
        maximum_days = strict_int(maximum) if maximum else None
        inactive_days = strict_int(inactive) if inactive else None
        expire_day = strict_int(expire) if expire else None
    except ValueError:
        raise Refused(code) from None
    # pam_unix account management runs after GDM authentication. Refuse
    # here so an expired account cannot consume and invalidate enrollment.
    if expire_day is not None and today >= expire_day:
        raise Refused(code)
    if changed_day == 0:
        raise Refused('locked_account_password_change_required')
    if changed_day is not None and maximum_days is not None:
        if inactive_days is not None and today - changed_day > maximum_days + inactive_days:
            raise Refused(code)
        if today - changed_day > maximum_days:
            raise Refused('locked_account_password_change_required')
    return Account(name, uid, gid, home, hashed, changed)


def shadow_accepts(secret, hashed, library=LIBCRYPT):
    """Compare locally through libxcrypt; no PAM attempt or faillock count."""
    try:
        crypt_rn = ctypes.CDLL(library).crypt_rn
    except (OSError, AttributeError):
        raise Refused('locked_account_unavailable') from None
    crypt_rn.restype = ctypes.c_void_p
    crypt_rn.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int)
    setting = hashed.encode('ascii')
    phrase = ctypes.create_string_buffer(len(secret) + 1)
    data = ctypes.create_string_buffer(CRYPT_DATA_SIZE)
    source = (ctypes.c_char * len(secret)).from_buffer(secret)
    try:
        ctypes.memmove(phrase, source, len(secret))
        result = crypt_rn(ctypes.addressof(phrase), setting, ctypes.addressof(data), CRYPT_DATA_SIZE)
        return bool(result) and hmac.compare_digest(ctypes.string_at(result), setting)
    finally:
        del source
        ctypes.memset(phrase, 0, len(phrase))
        ctypes.memset(data, 0, CRYPT_DATA_SIZE)


# Sealing --------------------------------------------------------------------

def run_bounded(argv, data, limit, seconds, code):
    """Run a fixed root tool with the payload on stdin; never argv or env."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, env=CLEAN_ENV, cwd='/', close_fds=True)
    deadline = time.monotonic() + seconds
    try:
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(process.stdin.fileno(), view):]
        finally:
            process.stdin.close()
        output = read_fd_bounded(process.stdout.fileno(), limit, deadline, code)
        try:
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            wipe(output)
            raise Refused(code) from None
        if process.returncode:
            wipe(output)
            raise Refused(code)
        return output
    except OSError:
        raise Refused(code) from None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()


class Sealer:
    """Host-bound (and TPM-bound when available) systemd credentials."""

    def __init__(self, run=run_bounded):
        self.run = run

    @staticmethod
    def name(uid):
        return f'machine-control-locked-use-{uid}'

    def seal(self, uid, payload):
        output = self.run([SYSTEMD_CREDS, 'encrypt', f'--name={self.name(uid)}', '--with-key=auto', '-', '-'],
                          payload, 1 << 16, 30, 'locked_credential_sealing_unavailable')
        return bytes(output)

    def unseal(self, uid, sealed):
        return self.run([SYSTEMD_CREDS, 'decrypt', f'--name={self.name(uid)}', '-', '-'],
                        sealed, 8192, 12, 'locked_credential_sealing_unavailable')


def sealed_header(account, enrollment):
    return dict(schema=SEALED_SCHEMA, uid=account.uid, user=account.name,
                enrollment=enrollment, shadow=account.binding)


def sealed_payload(account, enrollment, secret):
    header = json.dumps(sealed_header(account, enrollment), sort_keys=True, separators=(',', ':')).encode()
    payload = bytearray(len(header) + 1 + len(secret))
    payload[:len(header)] = header
    payload[len(header)] = 10
    payload[len(header) + 1:] = secret
    return payload


def open_payload(payload, receipt):
    index = payload.find(b'\n')
    try:
        header = json.loads(bytes(payload[:index])) if index > 0 else None
    except ValueError:
        header = None
    expected = dict(schema=SEALED_SCHEMA, uid=receipt['uid'], user=receipt['user'],
                    enrollment=receipt['enrollment'], shadow=receipt['shadow'])
    if header != expected:
        raise Refused('locked_credential_store_unverified')
    view = memoryview(payload)
    try:
        body = bytearray(view[index + 1:])
    finally:
        view.release()
    try:
        return validate_secret(body)
    except Refused:
        wipe(body)
        raise Refused('locked_credential_store_unverified') from None


# Enrollment store -----------------------------------------------------------

class Store:
    """Root 0700 directory of per-UID receipts, sealed blobs and attempts."""

    def __init__(self, root=STATE, owners=ROOT_OWNERS):
        self.root = Path(root)
        self.owners = owners
        self.mutex = threading.RLock()
        self.depth = 0

    def ensure(self):
        try:
            self.root.mkdir(mode=0o700)
        except FileExistsError:
            pass
        self.verify()

    def verify(self):
        try:
            info = os.lstat(self.root)
        except OSError:
            raise Refused('locked_credential_store_unverified') from None
        if not stat.S_ISDIR(info.st_mode) or info.st_uid not in self.owners or info.st_mode & 0o077:
            raise Refused('locked_credential_store_unverified')

    def exists(self):
        return self.root.exists()

    @contextlib.contextmanager
    def locked(self):
        with self.mutex:
            if self.depth:
                # flock is per open description; a second open would block on
                # this thread's own lock. Nesting reuses the held lock.
                self.depth += 1
                try:
                    yield
                finally:
                    self.depth -= 1
                return
            self.verify()
            fd = os.open(self.root / 'store.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_uid not in self.owners or info.st_mode & 0o077:
                    raise Refused('locked_credential_store_unverified')
                fcntl.flock(fd, fcntl.LOCK_EX)
                self.depth = 1
                try:
                    yield
                finally:
                    self.depth = 0
            finally:
                os.close(fd)

    def path(self, uid, suffix):
        return self.root / f'{int(uid)}.{suffix}'

    def read(self, uid, suffix, limit):
        return read_secure_file(self.path(uid, suffix), limit, self.owners, private=True,
                                code='locked_credential_store_unverified')

    def receipt(self, uid):
        try:
            value = json.loads(self.read(uid, 'json', 4096))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            raise Refused('locked_credential_store_unverified') from None
        ready = isinstance(value, dict) and value.get('state') == 'ready'
        if (not isinstance(value, dict)
                or set(value) != {'schema', 'uid', 'user', 'enrollment', 'shadow', 'state', 'reason', 'sealedSha256'}
                or value['schema'] != RECEIPT_SCHEMA or value['uid'] != uid
                or not isinstance(value['user'], str) or not USER_NAME.fullmatch(value['user'])
                or not isinstance(value['enrollment'], str) or not HEX32.fullmatch(value['enrollment'])
                or not isinstance(value['shadow'], str) or not HEX64.fullmatch(value['shadow'])
                or value['state'] not in ('ready', 'invalidated')
                or (ready and (value['reason'] is not None or not isinstance(value['sealedSha256'], str)
                               or not HEX64.fullmatch(value['sealedSha256'])))
                or (not ready and (value['reason'] not in INVALIDATION_REASONS or value['sealedSha256'] is not None))):
            raise Refused('locked_credential_store_unverified')
        return value

    def state(self, uid):
        receipt = self.receipt(uid)
        return ('absent', None) if receipt is None else (receipt['state'], receipt['reason'])

    def ready(self, uid):
        receipt = self.receipt(uid)
        if receipt is None:
            raise Refused('locked_credential_unenrolled')
        if receipt['state'] != 'ready':
            raise Refused('locked_credential_invalidated')
        return receipt

    def sealed(self, receipt):
        try:
            data = self.read(receipt['uid'], 'cred', 1 << 16)
        except OSError:
            raise Refused('locked_credential_store_unverified') from None
        if file_digest(data) != receipt['sealedSha256']:
            raise Refused('locked_credential_store_unverified')
        return data

    def write_receipt(self, uid, value):
        write_atomic(self.path(uid, 'json'), json.dumps(value, sort_keys=True).encode() + b'\n', 0o600)

    def commit(self, account, enrollment, sealed):
        # A crash between these replacements leaves a digest mismatch, which
        # refuses use rather than pairing a receipt with another credential.
        write_atomic(self.path(account.uid, 'cred'), sealed, 0o600)
        self.write_receipt(account.uid, dict(
            schema=RECEIPT_SCHEMA, uid=account.uid, user=account.name, enrollment=enrollment,
            shadow=account.binding, state='ready', reason=None, sealedSha256=file_digest(sealed)))
        self.unlink(account.uid, 'attempt')

    def unlink(self, uid, suffix):
        path = self.path(uid, suffix)
        if path.exists() or path.is_symlink():
            path.unlink()
            sync_directory(self.root)

    def invalidate(self, uid, reason):
        if reason not in INVALIDATION_REASONS:
            reason = 'locked_credential_delivery_unknown'
        self.unlink(uid, 'cred')
        try:
            receipt = self.receipt(uid)
        except Refused:
            self.remove(uid)
            return
        if receipt is not None:
            self.write_receipt(uid, {**receipt, 'state': 'invalidated', 'reason': reason, 'sealedSha256': None})
        self.unlink(uid, 'attempt')

    def begin_attempt(self, uid, enrollment):
        write_atomic(self.path(uid, 'attempt'),
                     json.dumps(dict(schema=ATTEMPT_SCHEMA, uid=uid, enrollment=enrollment)).encode() + b'\n', 0o600)

    def end_attempt(self, uid):
        self.unlink(uid, 'attempt')

    def remove(self, uid):
        for suffix in ('cred', 'json', 'attempt'):
            self.unlink(uid, suffix)

    def uids(self, suffix='json'):
        pattern = re.compile(r'([1-9][0-9]{0,9})\.' + suffix)
        return sorted(int(match.group(1)) for entry in os.listdir(self.root)
                      if (match := pattern.fullmatch(entry)))

    def recover(self):
        """Any attempt marker left by a crash is an unknown delivery."""
        for uid in self.uids('attempt'):
            self.invalidate(uid, 'locked_credential_delivery_unknown')


# logind -----------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Console:
    session_id: str
    uid: int
    started: int
    locked: bool


SESSION_PROPERTIES = ('Id', 'User', 'Active', 'Type', 'Class', 'Remote', 'Seat', 'State',
                      'TimestampMonotonic', 'LockedHint')


def loginctl(*args):
    try:
        result = subprocess.run([LOGINCTL, *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=CLEAN_ENV, timeout=3, check=True)
    except (OSError, subprocess.SubprocessError):
        raise Refused('locked_console_unavailable') from None
    if len(result.stdout) > 8192:
        raise Refused('locked_console_unavailable')
    return result.stdout.decode('utf-8', 'strict').strip()


def parse_session(text, session_id):
    fields = {}
    for line in text.splitlines():
        key, separator, value = line.partition('=')
        if not separator or key in fields or key not in SESSION_PROPERTIES:
            raise Refused('locked_console_unavailable')
        fields[key] = value
    try:
        if (set(fields) != set(SESSION_PROPERTIES) or fields['Id'] != session_id
                or fields['Type'] != 'wayland' or fields['Class'] != 'user' or fields['Remote'] != 'no'
                or fields['Seat'] != 'seat0' or fields['LockedHint'] not in ('yes', 'no')
                or fields['Active'] not in ('yes', 'no')):
            raise Refused('locked_console_unavailable')
        uid = strict_int(fields['User'], 1, 2**32 - 2)
        started = strict_int(fields['TimestampMonotonic'], 1)
    except ValueError:
        raise Refused('locked_console_unavailable') from None
    return fields, Console(session_id, uid, started, fields['LockedHint'] == 'yes')


def session_query(run, session_id):
    if not SESSION_ID.fullmatch(session_id):
        raise Refused('locked_console_unavailable')
    return run('show-session', *(f'--property={name}' for name in SESSION_PROPERTIES), '--', session_id)


def read_console(run=loginctl):
    """The exact active, local, user Wayland session on seat0."""
    session_id = run('show-seat', '--property=ActiveSession', '--value', '--', 'seat0')
    fields, console = parse_session(session_query(run, session_id), session_id)
    if fields['Active'] != 'yes' or fields['State'] != 'active':
        raise Refused('locked_console_unavailable')
    return console


def read_session(run, session_id):
    return parse_session(session_query(run, session_id), session_id)[1]


class Host:
    def __init__(self, run=loginctl, account=local_account):
        self.run = run
        self.account = account

    def console(self):
        return read_console(self.run)

    def session(self, session_id):
        return read_session(self.run, session_id)

    def lock(self, session_id):
        if not SESSION_ID.fullmatch(session_id):
            raise Refused('locked_console_unavailable')
        self.run('lock-session', '--', session_id)


# Peer provenance --------------------------------------------------------------

class PidFd:
    def __init__(self, fd):
        self.fd = fd

    def alive(self):
        if self.fd is None:
            return False
        poller = select.poll()
        poller.register(self.fd, select.POLLIN)
        return not poller.poll(0)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def open_pidfd(pid):
    return PidFd(os.pidfd_open(pid))


def kernel_peer(sock):
    pid, uid, _gid = struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    try:
        # The pidfd names the exact connecting process, so a later PID reuse
        # cannot redirect the /proc checks to the real resident.
        live = PidFd(sock.getsockopt(socket.SOL_SOCKET, SO_PEERPIDFD))
    except OSError:
        live = open_pidfd(pid)
    return pid, uid, live


@dataclasses.dataclass(frozen=True)
class Peer:
    pid: int
    uid: int
    start: int
    parent: int
    parent_start: int


class ProcessView:
    """One /proc/PID directory, read through a held directory descriptor."""

    def __init__(self, proc, pid):
        self.pid = pid
        self.fd = os.open(Path(proc) / str(pid), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)

    def close(self):
        os.close(self.fd)

    def read(self, name, limit):
        fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC, dir_fd=self.fd)
        try:
            chunks, total = [], 0
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    return b''.join(chunks)
                total += len(chunk)
                if total > limit:
                    raise ValueError('proc')
                chunks.append(chunk)
        finally:
            os.close(fd)

    def status(self):
        fields = {}
        for line in self.read('status', 65536).decode('utf-8', 'replace').splitlines():
            key, _, value = line.partition(':')
            fields[key] = value.split()
        uids = tuple(int(value) for value in fields['Uid'])
        gids = tuple(int(value) for value in fields['Gid'])
        if len(uids) != 4 or len(gids) != 4:
            raise ValueError('proc')
        return uids, gids, int(fields['PPid'][0]), int(fields['TracerPid'][0])

    def stat(self):
        text = self.read('stat', 4096).decode('ascii', 'replace')
        fields = text[text.rindex(')') + 2:].split()
        return int(fields[1]), int(fields[19])

    def executable(self):
        return os.stat('exe', dir_fd=self.fd), os.readlink('exe', dir_fd=self.fd)

    def argv(self):
        raw = self.read('cmdline', 65536)
        if not raw.endswith(b'\0'):
            raise ValueError('proc')
        return raw[:-1].split(b'\0')

    def environment(self):
        return {entry.split(b'=', 1)[0] for entry in self.read('environ', 1 << 20).split(b'\0') if entry}

    def maps(self):
        return self.read('maps', 8 << 20).decode('utf-8', 'surrogateescape')


PEER_FORBIDDEN = frozenset({
    b'LD_PRELOAD', b'LD_LIBRARY_PATH', b'LD_AUDIT', b'PYTHONPATH', b'PYTHONHOME',
    b'PYTHONUSERBASE', b'PYTHONPLATLIBDIR', b'PYTHONINSPECT', b'PYTHONSTARTUP'})
PARENT_FORBIDDEN = frozenset({b'LD_PRELOAD', b'LD_LIBRARY_PATH', b'LD_AUDIT'})
RESIDENT_FLAGS = frozenset({b'-I', b'-B', b'-s', b'-E', b'-P'})


class Provenance:
    """The peer is the installed resident under system Python, parented by
    the installed Tauri binary. Request contents play no part."""

    def __init__(self, proc='/proc', python=PYTHON, application=APPLICATION, resident=RESIDENT,
                 owners=ROOT_OWNERS, chain_root='/', pidfd=open_pidfd):
        self.proc = Path(proc)
        self.python, self.application, self.resident = Path(python), Path(application), Path(resident)
        self.owners, self.chain_root, self.pidfd = owners, Path(chain_root), pidfd

    def secure(self, path, seen=None):
        return secure_path(path, 'file', self.owners, self.chain_root, 'locked_peer_unverified', seen)

    def image(self, view, info, path):
        executable, target = view.executable()
        if (executable.st_dev, executable.st_ino) != (info.st_dev, info.st_ino) or target != str(path):
            raise Refused('locked_peer_unverified')

    def mappings(self, text, cache, seen):
        """Every executable file mapping is a root-owned, unreplaced file.
        This catches LD_PRELOAD, user extension modules and memfd code."""
        for line in text.splitlines():
            parts = line.split(None, 5)
            if len(parts) < 5:
                raise Refused('locked_peer_unverified')
            if 'x' not in parts[1]:
                continue
            name = parts[5] if len(parts) == 6 else ''
            if not name or (name.startswith('[') and name.endswith(']')):
                continue
            key = (int(parts[4]), name)
            if key in cache:
                continue
            if not name.startswith('/') or name.endswith(' (deleted)'):
                raise Refused('locked_peer_unverified')
            # Device numbers differ between maps and stat on btrfs; the
            # kernel's current path plus inode identifies the mapped file.
            if self.secure(Path(name), seen).st_ino != key[0]:
                raise Refused('locked_peer_unverified')
            cache.add(key)

    def verify(self, pid, uid, alive):
        """Return (Peer, parent liveness). The caller closes the liveness."""
        if uid <= 0 or pid <= 1:
            raise Refused('locked_peer_unverified')
        python = Path(os.path.realpath(self.python))
        application = Path(os.path.realpath(self.application))
        seen, cache = set(), set()
        python_info = self.secure(python, seen)
        application_info = self.secure(application, seen)
        self.secure(self.resident, seen)
        parent_live = None
        try:
            peer = ProcessView(self.proc, pid)
            try:
                if not alive():
                    raise Refused('locked_peer_unverified')
                uids, gids, ppid, tracer = peer.status()
                stat_ppid, start = peer.stat()
                if (any(value != uid for value in uids) or len(set(gids)) != 1 or tracer
                        or ppid != stat_ppid or ppid <= 1):
                    raise Refused('locked_peer_unverified')
                self.image(peer, python_info, python)
                argv = peer.argv()
                if (len(argv) < 2 or argv[0] != str(self.python).encode()
                        or argv[-1] != str(self.resident).encode()
                        or len(set(argv[1:-1])) != len(argv) - 2
                        or any(flag not in RESIDENT_FLAGS for flag in argv[1:-1])):
                    raise Refused('locked_peer_unverified')
                if peer.environment() & PEER_FORBIDDEN:
                    raise Refused('locked_peer_unverified')
                self.mappings(peer.maps(), cache, seen)
                parent_live = self.pidfd(ppid)
                parent = ProcessView(self.proc, ppid)
                try:
                    if not parent_live.alive():
                        raise Refused('locked_peer_unverified')
                    parent_uids, _gids, _ppid, parent_tracer = parent.status()
                    _parent_ppid, parent_start = parent.stat()
                    if any(value != uid for value in parent_uids) or parent_tracer or parent_start > start:
                        raise Refused('locked_peer_unverified')
                    self.image(parent, application_info, application)
                    if parent.environment() & PARENT_FORBIDDEN:
                        raise Refused('locked_peer_unverified')
                    self.mappings(parent.maps(), cache, seen)
                    # Both descriptors still name live processes, and the peer
                    # was not reparented, so every fact belongs to them.
                    if peer.stat() != (ppid, start) or not alive() or not parent_live.alive():
                        raise Refused('locked_peer_unverified')
                finally:
                    parent.close()
            finally:
                peer.close()
        except Refused:
            if parent_live is not None:
                parent_live.close()
            raise
        except (OSError, ValueError, KeyError, IndexError):
            if parent_live is not None:
                parent_live.close()
            raise Refused('locked_peer_unverified') from None
        return Peer(pid, uid, start, ppid, parent_start), parent_live


# Line protocol ----------------------------------------------------------------

def strict_json(line):
    def pairs(items):
        keys = [key for key, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError('duplicate')
        return dict(items)
    try:
        value = json.loads(line, object_pairs_hook=pairs)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise Refused('locked_request_invalid') from None
    if not isinstance(value, dict):
        raise Refused('locked_request_invalid')
    return value


def parse_request(line):
    value = strict_json(line)
    operation = value.get('operation')
    if value.get('schema') != SCHEMA:
        raise Refused('locked_request_invalid')
    if operation == 'status' and set(value) == {'schema', 'operation'}:
        return value
    if (operation != 'authenticate'
            or set(value) != {'schema', 'operation', 'sessionId', 'sessionStarted', 'coverOwner',
                              'coverToken', 'deadlineSeconds'}
            or not isinstance(value['sessionId'], str) or not SESSION_ID.fullmatch(value['sessionId'])
            or not exact_int(value['sessionStarted'], 1, 2**63 - 1)
            or not isinstance(value['coverOwner'], str) or not OWNER.fullmatch(value['coverOwner'])
            or not isinstance(value['coverToken'], str) or not TOKEN.fullmatch(value['coverToken'])
            or not exact_int(value['deadlineSeconds'], 1, 900)):
        raise Refused('locked_request_invalid')
    return value


def parse_control(line):
    value = strict_json(line)
    operation = value.get('operation')
    if value.get('schema') != SCHEMA:
        raise Refused('locked_request_invalid')
    if operation in ('keep', 'end') and set(value) == {'schema', 'operation'}:
        return operation, None
    if (operation == 'renew' and set(value) == {'schema', 'operation', 'deadlineSeconds'}
            and exact_int(value['deadlineSeconds'], 1, 900)):
        return operation, value['deadlineSeconds']
    raise Refused('locked_request_invalid')


def parse_worker(line):
    value = strict_json(line)
    if (value.get('event') not in WORKER_EVENTS or not set(value) <= {'event', 'code'}
            or ('code' in value) != (value['event'] in ('failed', 'guard_lost'))
            or ('code' in value and value['code'] not in ERRORS)):
        raise Refused('locked_worker_failed')
    return value


def parse_job(line):
    value = strict_json(line)
    if (set(value) != {'uid', 'sessionId', 'sessionStarted', 'coverOwner', 'coverToken', 'peerPid'}
            or not exact_int(value['uid'], 1, 2**32 - 2)
            or not isinstance(value['sessionId'], str) or not SESSION_ID.fullmatch(value['sessionId'])
            or not exact_int(value['sessionStarted'], 1, 2**63 - 1)
            or not isinstance(value['coverOwner'], str) or not OWNER.fullmatch(value['coverOwner'])
            or not isinstance(value['coverToken'], str) or not TOKEN.fullmatch(value['coverToken'])
            or not exact_int(value['peerPid'], 2, 2**31 - 1)):
        raise Refused('locked_worker_failed')
    return value


def send_line(sock, value, seconds=2.0):
    view = memoryview(json.dumps(value, separators=(',', ':')).encode() + b'\n')
    deadline = time.monotonic() + seconds
    while view:
        try:
            view = view[sock.send(view):]
        except BlockingIOError:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [sock], [], remaining)[1]:
                raise OSError(errno.ETIMEDOUT, 'send') from None


class Lines:
    """Bounded newline framing over a non-blocking stream socket."""

    def __init__(self, sock, limit):
        self.sock = sock
        self.limit = limit
        self.buffer = bytearray()
        self.pending = deque()
        self.closed = False

    def fileno(self):
        return self.sock.fileno()

    def pump(self):
        if not self.closed:
            try:
                chunk = self.sock.recv(4096, socket.MSG_DONTWAIT)
            except (BlockingIOError, InterruptedError):
                chunk = None
            except OSError:
                chunk = b''
            if chunk == b'':
                self.closed = True
            elif chunk:
                self.buffer += chunk
        while (index := self.buffer.find(b'\n')) >= 0:
            if index > self.limit:
                raise Refused('locked_request_invalid')
            self.pending.append(bytes(self.buffer[:index]))
            del self.buffer[:index + 1]
        if len(self.buffer) > self.limit:
            raise Refused('locked_request_invalid')
        lines = list(self.pending)
        self.pending.clear()
        return lines

    def next(self, deadline):
        while not self.pending:
            if self.closed:
                raise Closed()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Refused('locked_request_invalid')
            select.select([self.sock], [], [], remaining)
            self.pending.extend(self.pump())
        return self.pending.popleft()


# Guarded authentication ------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Timing:
    keep: float = 3.0          # client heartbeat gap
    prompt: float = 20.0       # worker start through the GDM password prompt
    native: float = 60.0       # submission through GDM's own completion
    teardown: float = 7.0      # cancelled submitted conversation to native end
    unlock: float = 12.0       # GDM verification to the observed unlock
    relock: float = 20.0       # ending to logind's locked report
    poll: float = 0.2


class WorkerProcess:
    """The GDM worker: this script, as the console UID, with no root state."""

    def __init__(self, job, account):
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        read_fd, write_fd = os.pipe()
        try:
            env = dict(PATH='/usr/bin:/bin', HOME=account.home, USER=account.name, LOGNAME=account.name,
                       LANG='C', LC_ALL='C', XDG_RUNTIME_DIR=f'/run/user/{account.uid}',
                       DBUS_SESSION_BUS_ADDRESS=f'unix:path=/run/user/{account.uid}/bus')
            self.process = subprocess.Popen(
                [SETPRIV, '--reuid', str(account.uid), '--regid', str(account.gid), '--clear-groups',
                 '--no-new-privs', '--', str(PYTHON), '-I', '-B', str(SCRIPT), 'worker',
                 str(child.fileno()), str(read_fd), str(os.getpid())],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd='/',
                umask=0o077, pass_fds=(child.fileno(), read_fd), close_fds=True, start_new_session=True)
        except BaseException:
            parent.close()
            os.close(write_fd)
            raise
        finally:
            child.close()
            os.close(read_fd)
        parent.setblocking(False)
        self.control = parent
        self.lines = Lines(parent, 2048)
        self.secret = write_fd
        send_line(parent, job)

    def deliver(self, frame):
        try:
            view = memoryview(frame)
            while view:
                view = view[os.write(self.secret, view):]
        finally:
            os.close(self.secret)
            self.secret = None

    def cancel(self):
        try:
            send_line(self.control, {'op': 'cancel'}, 0.5)
        except OSError:
            pass

    def alive(self):
        return self.process.poll() is None

    def stop(self):
        if self.secret is not None:
            os.close(self.secret)
            self.secret = None
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.control.close()


def spawn_worker(job, account):
    try:
        return WorkerProcess(job, account)
    except PermissionError as error:
        if error.filename in (str(PYTHON), SETPRIV):
            code = 'locked_worker_executable_denied'
        elif error.filename is not None:
            code = 'locked_worker_files_denied'
        elif error.errno == errno.EPERM:
            code = 'locked_worker_identity_denied'
        else:
            code = 'locked_worker_spawn_denied'
        raise Refused(code) from None
    except (OSError, subprocess.SubprocessError, KeyError):
        raise Refused('locked_worker_spawn_failed') from None


class Attempt:
    """One exact credential use, held until positive native teardown and an
    observed relock. Released secrets that are not positively verified
    invalidate enrollment; nothing retries automatically."""

    def __init__(self, service, lines, peer, alive, request):
        self.s = service
        self.timing = service.timing
        self.lines = lines
        self.peer = peer
        self.alive = alive
        self.request = request
        self.identity = (request['sessionId'], request['sessionStarted'])
        self.worker = None
        self.receipt = None
        self.phase = 'preparing'
        self.phase_deadline = None
        self.released = False
        self.verified = False
        self.rejected = False

    def send(self, **fields):
        try:
            send_line(self.lines.sock, dict(schema=SCHEMA, **fields))
        except OSError:
            pass

    def exact_console(self, locked):
        console = self.s.host.console()
        if (console.session_id, console.started, console.uid) != (*self.identity, self.peer.uid):
            raise Refused('locked_console_changed')
        if console.locked != locked:
            raise Refused('locked_console_not_locked' if locked else 'locked_console_relocked')

    def check_binding(self, account, receipt):
        """Caller holds store.locked(). Stale credentials fail before PAM."""
        if account.binding != receipt['shadow'] or account.name != receipt['user']:
            self.s.store.invalidate(self.peer.uid, 'locked_credential_stale')
            raise Refused('locked_credential_stale')

    def run(self):
        self.exact_console(True)
        if not self.s.busy.acquire(blocking=False):
            raise Refused('locked_credential_busy')
        try:
            with self.s.store.locked():
                self.receipt = self.s.store.ready(self.peer.uid)
                self.check_binding(self.s.host.account(self.peer.uid), self.receipt)
            self.worker = self.s.spawn(dict(
                uid=self.peer.uid, sessionId=self.identity[0], sessionStarted=self.identity[1],
                coverOwner=self.request['coverOwner'], coverToken=self.request['coverToken'],
                peerPid=self.peer.pid), self.s.host.account(self.peer.uid))
            self.send(event='accepted')
            code = 'locked_worker_failed'
            try:
                code = self.loop()
            finally:
                self.finish(code)
        finally:
            self.s.busy.release()

    def loop(self):
        clock, timing = self.s.clock, self.timing
        keep = clock() + timing.keep
        ceiling = clock() + self.request['deadlineSeconds']
        self.phase_deadline = clock() + timing.prompt
        while True:
            if self.s.stopping.is_set():
                return 'locked_service_stopping'
            deadline = min(keep, ceiling, self.phase_deadline or ceiling)
            wait = max(0.0, min(timing.poll, deadline - clock()))
            ready = select.select([self.lines.sock, self.worker.control], [], [], wait)[0]
            if self.lines.sock in ready:
                try:
                    for line in self.lines.pump():
                        operation, seconds = parse_control(line)
                        keep = clock() + timing.keep
                        if operation == 'renew':
                            ceiling = clock() + seconds
                            self.send(event='renewed', deadlineSeconds=seconds)
                        elif operation == 'end':
                            return 'locked_owner_ended'
                except Refused:
                    return 'locked_owner_disconnected'
                if self.lines.closed:
                    return 'locked_owner_disconnected'
            if self.worker.control in ready:
                try:
                    for line in self.worker.lines.pump():
                        code = self.event(parse_worker(line))
                        if code:
                            return code
                except Refused as error:
                    return error.code
                if self.worker.lines.closed:
                    return 'locked_worker_exited'
            if not self.alive():
                return 'locked_owner_exited'
            if not self.worker.alive():
                return 'locked_worker_exited'
            now = clock()
            if now >= keep:
                return 'locked_owner_heartbeat_lost'
            if now >= ceiling:
                return 'locked_guard_deadline'
            if self.phase_deadline is not None and now >= self.phase_deadline:
                return 'gnome_unlock_delivery_unknown' if self.released else 'gnome_authentication_timeout'

    def event(self, message):
        kind = message['event']
        try:
            if kind == 'ready' and self.phase == 'preparing':
                return None
            if kind == 'prompt' and self.phase == 'preparing':
                return self.release()
            if kind == 'dispatched' and self.phase == 'released':
                self.phase = 'dispatched'
                self.send(event='submitted')
                return None
            if kind == 'verified' and self.phase in ('released', 'dispatched'):
                self.mark_verified()
                self.phase = 'verified'
                self.phase_deadline = self.s.clock() + self.timing.unlock
                return None
            if kind == 'unlocked' and self.phase == 'verified':
                self.exact_console(False)
                self.phase = 'guarding'
                self.phase_deadline = None
                self.send(accepted=True, event='unlocked', credential='kept', delivery='verified')
                return None
            if kind == 'locked' and self.phase == 'guarding':
                return 'locked_console_relocked'
            if kind in ('failed', 'guard_lost'):
                self.rejected |= kind == 'failed' and message['code'] == 'gnome_authentication_failed' and self.released
                return message['code']
        except Refused as error:
            return error.code
        return 'locked_worker_failed'

    def mark_verified(self):
        self.verified = True
        with self.s.store.locked():
            self.s.store.end_attempt(self.peer.uid)

    def release(self):
        """Final checks, then the only secret transfer: root to its worker."""
        uid = self.peer.uid
        if self.lines.closed or not self.alive():
            return 'locked_owner_disconnected'
        self.exact_console(True)
        store = self.s.store
        with store.locked():
            receipt = store.ready(uid)
            if receipt['enrollment'] != self.receipt['enrollment']:
                return 'locked_credential_stale'
            self.check_binding(self.s.host.account(uid), receipt)
            try:
                sealed = store.sealed(receipt)
                payload = self.s.sealer.unseal(uid, sealed)
                try:
                    secret = open_payload(payload, receipt)
                finally:
                    wipe(payload)
            except Refused as error:
                if error.code == 'locked_credential_store_unverified':
                    store.invalidate(uid, error.code)
                raise
            try:
                frame = encode_secret_frame(secret)
            finally:
                wipe(secret)
            try:
                store.begin_attempt(uid, receipt['enrollment'])
                self.released = True
                self.worker.deliver(frame)
            finally:
                wipe(frame)
        self.phase = 'released'
        self.phase_deadline = self.s.clock() + self.timing.native
        return None

    def finish(self, code):
        clock = self.s.clock
        try:
            if self.worker is not None:
                self.worker.cancel()
                if self.released and not self.verified:
                    # Keep the exact attempt until GDM itself reports the end of
                    # the submitted conversation, bounded by the teardown window.
                    deadline = clock() + self.timing.teardown
                    while clock() < deadline and not self.verified and not self.rejected:
                        if select.select([self.worker.control], [], [], self.timing.poll)[0]:
                            try:
                                for line in self.worker.lines.pump():
                                    message = parse_worker(line)
                                    if message['event'] == 'verified':
                                        self.mark_verified()
                                    elif message['event'] == 'failed':
                                        self.rejected |= message['code'] == 'gnome_authentication_failed'
                                        deadline = 0
                            except Refused:
                                break
                        if self.worker.lines.closed or not self.worker.alive():
                            break
        finally:
            if self.worker is not None:
                self.worker.stop()
        credential, delivery = 'unused', 'none'
        if self.released:
            if self.verified:
                credential, delivery = 'kept', 'verified'
            else:
                reason = 'gnome_authentication_failed' if self.rejected else 'locked_credential_delivery_unknown'
                with self.s.store.locked():
                    self.s.store.invalidate(self.peer.uid, reason)
                credential, delivery = 'invalidated', ('rejected' if self.rejected else 'unknown')
        relock = self.relock()
        accepted = code == 'locked_owner_ended' and relock == 'verified' and self.phase == 'guarding'
        self.send(event='ended', accepted=accepted, errorCode=None if accepted else code,
                  relock=relock, credential=credential, delivery=delivery)

    def relock(self):
        clock, timing = self.s.clock, self.timing
        session_id, started = self.identity
        deadline = clock() + timing.relock
        requests = 0
        while True:
            try:
                session = self.s.host.session(session_id)
                if session.started != started or session.uid != self.peer.uid:
                    return 'session_ended'
                if session.locked:
                    return 'verified'
                if requests == 0 or (requests == 1 and clock() >= deadline - timing.relock / 2):
                    requests += 1
                    self.s.host.lock(session_id)
            except Refused:
                pass
            if clock() >= deadline:
                return 'unverified'
            self.s.sleep(timing.poll)


class Service:
    def __init__(self, store, sealer, host, provenance, spawn=spawn_worker, peer=kernel_peer,
                 timing=Timing(), clock=time.monotonic, sleep=time.sleep):
        self.store, self.sealer, self.host, self.provenance = store, sealer, host, provenance
        self.spawn, self.peer, self.timing, self.clock, self.sleep = spawn, peer, timing, clock, sleep
        self.busy = threading.Lock()
        self.stopping = threading.Event()
        self.slots = threading.BoundedSemaphore(8)
        self.threads = set()

    def serve(self, listener):
        listener.settimeout(0.5)
        while not self.stopping.is_set():
            try:
                conn, _ = listener.accept()
            except (socket.timeout, InterruptedError):
                continue
            except OSError:
                if self.stopping.is_set():
                    break
                time.sleep(0.1)
                continue
            if not self.slots.acquire(blocking=False):
                conn.close()
                continue
            thread = threading.Thread(target=self.slot, args=(conn,), daemon=True)
            self.threads.add(thread)
            thread.start()
            self.threads = {item for item in self.threads if item.is_alive()}
        deadline = time.monotonic() + self.timing.teardown + self.timing.relock + 2
        for thread in list(self.threads):
            thread.join(max(0.0, deadline - time.monotonic()))

    def slot(self, conn):
        try:
            self.connection(conn)
        finally:
            self.slots.release()

    def connection(self, conn):
        live = parent = None
        try:
            conn.setblocking(False)
            lines = Lines(conn, MAX_REQUEST)
            pid, uid, live = self.peer(conn)
            request = parse_request(lines.next(time.monotonic() + 2))
            peer, parent = self.provenance.verify(pid, uid, live.alive)
            if request['operation'] == 'status':
                state, reason = self.store.state(peer.uid)
                send_line(conn, dict(schema=SCHEMA, accepted=True, operation='status', enrolled=state == 'ready',
                                     enrollment=state, reason=reason, busy=self.busy.locked()))
            else:
                Attempt(self, lines, peer, lambda: live.alive() and parent.alive(), request).run()
        except Closed:
            pass
        except Refused as error:
            self.refuse(conn, error.code)
        except Exception:
            self.refuse(conn, 'locked_service_unavailable')
        finally:
            for item in (live, parent):
                if item is not None:
                    item.close()
            conn.close()

    @staticmethod
    def refuse(conn, code):
        try:
            send_line(conn, dict(schema=SCHEMA, accepted=False, errorCode=code))
        except OSError:
            pass


# Worker (console UID) ----------------------------------------------------------

class WorkerChannel:
    def __init__(self, control_fd, secret_fd):
        self.sock = socket.socket(fileno=control_fd)
        self.sock.setblocking(False)
        self.lines = Lines(self.sock, 2048)
        self.secret_fd = secret_fd
        self.cancelled = False

    def emit(self, event, **fields):
        try:
            send_line(self.sock, dict(event=event, **fields))
        except OSError:
            self.cancelled = True

    def job(self, deadline):
        return parse_job(self.lines.next(deadline))

    def poll(self):
        try:
            for line in self.lines.pump():
                if strict_json(line) != {'op': 'cancel'}:
                    raise Refused('locked_worker_failed')
                self.cancelled = True
        except Refused:
            self.cancelled = True
        self.cancelled |= self.lines.closed
        return self.cancelled

    def secret(self, deadline):
        """Read the one frame root releases after its own final checks."""
        if self.secret_fd is None:
            raise Refused('gnome_password_unavailable')
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Refused('gnome_password_unavailable')
                ready = select.select([self.secret_fd, self.sock], [], [], remaining)[0]
                if self.sock in ready and self.poll():
                    raise Refused('gnome_unlock_cancelled')
                if self.secret_fd in ready:
                    break
            frame = read_fd_bounded(self.secret_fd, FRAME_LIMIT, deadline, 'gnome_password_unavailable')
            try:
                body = parse_secret_frame(frame)
            except Refused:
                raise Refused('gnome_password_invalid') from None
            finally:
                wipe(frame)
            try:
                return body.decode('utf-8')
            finally:
                wipe(body)
        finally:
            os.close(self.secret_fd)
            self.secret_fd = None


def activity_sampler(activity, console):
    binding = activity.console_binding((console.session_id, console.started, console.shell_owner))

    def sample():
        try:
            value = activity.read_sample(activity.ENDPOINT, True, binding)
            motion = value.get('motionToken')
            if (not value['healthy'] or not isinstance(motion, str) or len(motion) != 32
                    or time.monotonic() - value['observedThroughUptime'] > 1.5):
                return None
            return value['generation'], value['activityToken'], motion
        except (OSError, ValueError, KeyError):
            return None
    return sample


class WorkerGuard:
    """Independent session-bus proof of the resident's cover and the root
    activity observer's input facts, as seen by the worker."""

    def __init__(self, provider, console, job, sample, sleep=time.sleep):
        self.provider, self.console, self.job, self.sample, self.sleep = provider, console, job, sample, sleep
        self.baseline = None

    def bus(self, method, signature):
        return self.provider.call(self.provider.session, 'org.freedesktop.DBus', '/org/freedesktop/DBus',
                                  'org.freedesktop.DBus', method, ('(s)', (self.job['coverOwner'],)), signature)[0]

    def bind(self):
        try:
            # Unique names are never reused on a bus, so this binds the cover
            # owner to the kernel-verified resident for the cover's lifetime.
            if (self.bus('GetConnectionUnixProcessID', '(u)') != self.job['peerPid']
                    or self.bus('GetConnectionUnixUser', '(u)') != self.job['uid']):
                raise Refused('locked_cover_unverified')
        except Refused:
            raise
        except Exception:
            raise Refused('locked_cover_unverified') from None
        if not self.authority():
            raise Refused('locked_cover_unverified')
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.baseline = self.sample()
            if self.baseline is not None:
                return
            self.sleep(0.1)
        raise Refused('locked_activity_observer_lost')

    def ask(self, method):
        try:
            return self.provider.call(
                self.provider.session, self.console.shell_owner, COVER_PATH, COVER_INTERFACE, method,
                ('(ss)', (self.job['coverOwner'], self.job['coverToken'])), '(b)', timeout=500)[0] is True
        except Exception:
            return False

    def authority(self):
        """Locked, pixel-verified, idle cover of this exact owner and lease."""
        return self.ask('CheckAuthority')

    def live(self):
        """The same exact covered owner and lease, valid after unlock."""
        return self.ask('CheckLive')

    def problem(self, submitted=False):
        if not (self.live() if submitted else self.authority()):
            return 'locked_cover_lost'
        current = self.sample()
        if current is None or current[0] != self.baseline[0]:
            return 'locked_activity_observer_lost'
        if current != self.baseline:
            return 'locked_local_input'
        return None


@dataclasses.dataclass(frozen=True)
class WorkerTiming:
    prompt: float = 10.0
    secret: float = 15.0
    native: float = 55.0
    teardown: float = 5.0
    unlock: float = 10.0


class Conversation:
    """GDM conversation policy, independent of GLib so it can be tested.

    One recognised C-locale password prompt is admitted. The secret is
    requested only after the guard, the exact lock and the prompt pass.
    After submission only GDM's native completion, failure or a bounded
    teardown ends the attempt.
    """

    def __init__(self, gnome, provider, console, channel, guard, timing=WorkerTiming(), clock=time.monotonic):
        self.gnome, self.provider, self.console = gnome, provider, console
        self.channel, self.guard, self.timing, self.clock = channel, guard, timing, clock
        self.question = gnome.PasswordQuestion()
        self.phase = 'opening'
        self.deadline = clock() + timing.prompt
        self.cancel_verifier = None
        self.problem = None
        self.succeeded = False
        self.done = False

    def finish(self, event, **fields):
        if not self.done:
            self.done = True
            self.phase = 'done'
            self.channel.emit(event, **fields)

    def fail(self, code):
        self.finish('failed', code=code if code in ERRORS else 'locked_worker_failed')

    def check(self):
        if self.channel.poll():
            raise Refused('gnome_unlock_cancelled')
        problem = self.guard.problem()
        if problem:
            raise Refused(problem)
        self.provider.require_locked(self.console)

    def opened(self):
        try:
            self.check()
            return True
        except Exception as error:
            self.fail(code_of(error, 'locked_worker_check_failed'))
            return False

    def query(self, service, prompt):
        """Return the secret to answer, or None after ending the attempt."""
        if self.done:
            return None
        if self.phase != 'opening':
            self.native('gnome_authentication_failed')
            return None
        try:
            self.question.accept(service, prompt)
            self.check()
            self.channel.emit('prompt')
            secret = self.channel.secret(self.clock() + self.timing.secret)
            self.check()
        except Exception as error:
            self.fail(code_of(error, 'locked_worker_secret_prompt_failed'))
            return None
        self.channel.emit('dispatched')
        self.phase = 'dispatched'
        self.deadline = self.clock() + self.timing.native
        return secret

    def delivery_failed(self):
        if self.phase in ('dispatched', 'teardown'):
            self.fail('gnome_unlock_delivery_unknown')

    def complete(self, service):
        if self.done or self.phase in ('verified', 'guarding'):
            return
        if self.phase not in ('dispatched', 'teardown') or service != self.gnome.GDM_PASSWORD_SERVICE:
            self.fail('gnome_password_prompt_unavailable')
            return
        self.succeeded = True
        self.channel.emit('verified')
        if self.phase == 'teardown':
            self.finish('guard_lost', code=self.problem)
            return
        self.phase = 'verified'
        self.deadline = self.clock() + self.timing.unlock

    def native(self, code):
        # Completion is followed by ordinary teardown signals; ignore them.
        if not self.done and self.phase not in ('verified', 'guarding'):
            self.fail(code)

    def tick(self):
        if self.done:
            return False
        cancelled = self.channel.poll()
        now = self.clock()
        if self.phase == 'opening':
            problem = 'gnome_unlock_cancelled' if cancelled else self.guard.problem()
            if problem:
                self.fail(problem)
            elif now >= self.deadline:
                self.fail('gnome_authentication_timeout')
        elif self.phase == 'dispatched':
            problem = 'gnome_unlock_cancelled' if cancelled else self.guard.problem(True)
            if problem:
                self.problem = problem
                self.phase = 'teardown'
                self.deadline = now + self.timing.teardown
                try:
                    if self.cancel_verifier is not None:
                        self.cancel_verifier()
                except Exception:
                    pass
            elif now >= self.deadline:
                self.fail('gnome_unlock_delivery_unknown')
        elif self.phase == 'teardown':
            if now >= self.deadline:
                self.fail('gnome_unlock_delivery_unknown')
        elif cancelled:
            self.done = True
            self.phase = 'done'
        else:
            problem = self.guard.problem(True)
            if problem:
                self.finish('guard_lost', code=problem)
                return False
            try:
                state = self.provider.observe()
            except Exception as error:
                self.finish('guard_lost', code=code_of(error, 'gnome_console_unavailable'))
                return False
            if state.console != self.console:
                self.finish('guard_lost', code='gnome_locked_console_changed')
            elif self.phase == 'verified':
                if state.unlocked:
                    self.channel.emit('unlocked')
                    self.phase = 'guarding'
                elif now >= self.deadline:
                    self.fail('gnome_unlocked_effect_unverified')
            elif state.locked:
                self.finish('locked')
        return not self.done


def run_gdm(conversation, provider, username):
    """GLib adapter: GDM reauthentication on the existing session."""
    Gdm, Gio, GLib = provider.Gdm, provider.Gio, provider.GLib
    gnome = conversation.gnome
    client = Gdm.Client.new()
    cancel = Gio.Cancellable.new()
    context = GLib.MainContext.new()
    loop = GLib.MainLoop.new(context, False)
    holder = {}

    def settle():
        if conversation.done:
            loop.quit()

    def answered(source, result):
        try:
            source.call_answer_query_finish(result)
        except GLib.Error:
            conversation.delivery_failed()
        settle()

    def query(source, service, prompt):
        secret = conversation.query(service, prompt)
        if secret is not None:
            source.call_answer_query(service, secret, cancel, answered)
        del secret
        settle()

    def native(code):
        def handler(*_):
            conversation.native(code)
            settle()
        return handler

    def complete(_source, service):
        conversation.complete(service)
        settle()

    def started(source, result):
        try:
            source.call_begin_verification_for_user_finish(result)
        except GLib.Error:
            conversation.native('gnome_authentication_unavailable')
        settle()

    def opened(source, result):
        try:
            verifier = source.open_reauthentication_channel_finish(result)
        except GLib.Error:
            conversation.fail('gnome_authentication_unavailable')
            settle()
            return
        holder['verifier'] = verifier
        conversation.cancel_verifier = lambda: verifier.call_cancel(None, None)
        if not conversation.opened():
            settle()
            return
        verifier.connect('secret-info-query', query)
        verifier.connect('verification-complete', complete)
        verifier.connect('info-query', native('gnome_password_prompt_unavailable'))
        verifier.connect('verification-failed', native('gnome_authentication_failed'))
        verifier.connect('conversation-stopped', native('gnome_authentication_failed'))
        verifier.connect('service-unavailable', native('gnome_authentication_unavailable'))
        verifier.connect('reset', native('gnome_authentication_failed'))
        verifier.call_begin_verification_for_user(gnome.GDM_PASSWORD_SERVICE, username, cancel, started)

    def tick(*_):
        if not conversation.tick():
            loop.quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    context.push_thread_default()
    timer = GLib.timeout_source_new(250)
    timer.set_callback(tick)
    timer.attach(context)
    try:
        client.open_reauthentication_channel(username, cancel, opened)
        loop.run()
    finally:
        timer.destroy()
        cancel.cancel()
        verifier = holder.get('verifier')
        if verifier is not None and not conversation.succeeded:
            verifier.call_cancel(None, None)
        context.pop_thread_default()


def verify_session_bus(uid, base=Path('/run/user')):
    try:
        directory = os.lstat(base / str(uid))
        bus = os.lstat(base / str(uid) / 'bus')
    except OSError:
        raise Refused('locked_session_bus_unverified') from None
    if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != uid or directory.st_mode & 0o077
            or not stat.S_ISSOCK(bus.st_mode) or bus.st_uid != uid):
        raise Refused('locked_session_bus_unverified')


def worker_main(argv):
    try:
        control_fd, secret_fd, parent = (strict_int(value) for value in argv[2:5])
        if len(argv) != 5:
            return 2
    except ValueError:
        return 2
    libc = ctypes.CDLL(None, use_errno=True)
    uid = os.getuid()
    # Not dumpable: same-UID processes cannot ptrace or read this memory.
    if (libc.prctl(4, 0, 0, 0, 0) != 0 or libc.prctl(1, int(signal.SIGKILL), 0, 0, 0) != 0
            or os.getppid() != parent or uid == 0 or os.getresuid() != (uid, uid, uid) or os.getgroups()):
        return 2
    channel = WorkerChannel(control_fd, secret_fd)
    stage = 'locked_worker_job_invalid'
    try:
        job = channel.job(time.monotonic() + 5)
        if job['uid'] != uid:
            raise Refused('locked_worker_failed')
        verify_session_bus(uid)
        secure_path(RUNTIME, 'directory')
        for name in ('gnome_unlock.py', 'activity.py'):
            secure_path(RUNTIME / name)
        sys.path.insert(0, str(RUNTIME))
        import pwd
        import gnome_unlock
        import activity
        stage = 'locked_worker_console_probe_failed'
        provider = gnome_unlock.GnomeUnlock()
        state = provider.observe()
        console = state.console
        if (console.session_id, console.started) != (job['sessionId'], job['sessionStarted']) or not state.locked:
            raise Refused('gnome_locked_console_changed')
        guard = WorkerGuard(provider, console, job, activity_sampler(activity, console))
        stage = 'locked_worker_guard_probe_failed'
        guard.bind()
        channel.emit('ready')
        conversation = Conversation(gnome_unlock, provider, console, channel, guard)
        stage = 'locked_worker_gdm_adapter_failed'
        run_gdm(conversation, provider, pwd.getpwuid(uid).pw_name)
        if not conversation.done:
            conversation.fail('locked_worker_failed')
    except Exception as error:
        channel.emit('failed', code=code_of(error, stage))
    return 0


# Root CLI ---------------------------------------------------------------------

def require_self():
    if os.path.abspath(__file__) != str(SCRIPT):
        raise Refused('locked_credential_runtime_unverified')
    secure_path(RUNTIME, 'directory')
    secure_path(SCRIPT)


@contextlib.contextmanager
def install_lock():
    fd = os.open(INSTALL_LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise Refused('locked_installation_unowned')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused('locked_credential_busy') from None
        yield
    finally:
        os.close(fd)


def operator_uid(env, required=True):
    value = env.get('PKEXEC_UID')
    if value is None and not required:
        return None
    try:
        uid = strict_int(value, 1, 2**32 - 2)
    except (TypeError, ValueError):
        raise Refused('locked_credential_operator_unverified') from None
    if uid == 65534:
        raise Refused('locked_credential_operator_unverified')
    return uid


def systemctl(*args):
    try:
        subprocess.run([SYSTEMCTL, *args], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, env=CLEAN_ENV, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        raise Refused('locked_service_unavailable') from None


def installed_unit():
    try:
        current = read_secure_file(UNIT, 65536, code='locked_installation_unowned')
    except FileNotFoundError:
        return None
    if not current.startswith(UNIT_MARKER + b'\n'):
        raise Refused('locked_installation_unowned')
    return current


def install_service():
    if installed_unit() != UNIT_BYTES:
        write_atomic(UNIT, UNIT_BYTES, 0o644)
        systemctl('daemon-reload')
    systemctl('enable', SERVICE)
    systemctl('restart', SERVICE)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            info = os.lstat(SOCKET_PATH)
            if stat.S_ISSOCK(info.st_mode) and info.st_uid == 0:
                return
        except OSError:
            pass
        time.sleep(0.1)
    raise Refused('locked_service_unavailable')


def uninstall_service():
    if installed_unit() is not None:
        systemctl('disable', '--now', SERVICE)
        UNIT.unlink()
        systemctl('daemon-reload')


def setup(env=None, stdin_fd=0):
    env = os.environ if env is None else env
    with install_lock():
        uid = operator_uid(env)
        console = read_console()
        if console.uid != uid:
            raise Refused('locked_console_unavailable')
        if console.locked:
            raise Refused('locked_console_locked')
        account = local_account(uid)
        verify_runtime()
        store = Store()
        store.ensure()
        secret = read_secret_stream(stdin_fd)
        try:
            if read_console() != console:
                raise Refused('locked_console_changed')
            if not shadow_accepts(secret, account.hashed):
                raise Refused('unlock_credential_invalid')
            enrollment = secrets.token_hex(16)
            payload = sealed_payload(account, enrollment, secret)
            try:
                sealed = Sealer().seal(uid, payload)
            finally:
                wipe(payload)
        finally:
            wipe(secret)
        with store.locked():
            store.commit(account, enrollment, sealed)
        install_service()
    return dict(accepted=True, enrolled=True)


def remove(env=None):
    env = os.environ if env is None else env
    with install_lock():
        uid = operator_uid(env, required=False)
        store = Store()
        remaining = []
        if store.exists():
            with store.locked():
                for enrolled in store.uids():
                    if uid is None or enrolled == uid:
                        store.remove(enrolled)
                for orphan in store.uids('cred') + store.uids('attempt'):
                    if uid is None or orphan == uid:
                        store.remove(orphan)
                remaining = store.uids()
        if not remaining:
            uninstall_service()
    return dict(accepted=True, removed=True)


def bind_listener(path=SOCKET_PATH):
    directory = os.lstat(path.parent)
    if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != 0 or directory.st_mode & 0o022:
        raise Refused('locked_service_unavailable')
    with contextlib.suppress(FileNotFoundError):
        info = os.lstat(path)
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0:
            raise Refused('locked_service_unavailable')
        path.unlink()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    # Authorization is the kernel peer and provenance check, not file mode.
    os.chmod(path, 0o666)
    listener.listen(16)
    return listener


def serve():
    verify_runtime()
    store = Store()
    store.ensure()
    with store.locked():
        store.recover()
    listener = bind_listener()
    service = Service(store, Sealer(), Host(), Provenance())
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: service.stopping.set())
    try:
        service.serve(listener)
    finally:
        listener.close()
        SOCKET_PATH.unlink(missing_ok=True)
    return 0


def main(argv=None, euid=None):
    argv = sys.argv if argv is None else argv
    operation = argv[1] if len(argv) >= 2 else None
    if operation == 'worker':
        return worker_main(argv)
    try:
        if (os.geteuid() if euid is None else euid) != 0:
            raise Refused('locked_credential_root_required')
        if len(argv) != 2 or operation not in ('setup', 'remove', 'serve'):
            raise Refused('locked_credential_operation_invalid')
        require_self()
        if operation == 'serve':
            return serve()
        result = setup() if operation == 'setup' else remove()
    except Refused as error:
        result = dict(accepted=False, errorCode=error.code)
    except Exception:
        # No argument, path, input, exception text or secret reaches output.
        result = dict(accepted=False, errorCode='locked_credential_refused')
    print(json.dumps(result, separators=(',', ':')), flush=True)
    return 0 if result.get('accepted') else 1


# Resident client ---------------------------------------------------------------

def connect(path=SOCKET_PATH, timeout=2.0):
    """Connect only to the root service's own socket."""
    path = Path(path)
    try:
        directory, entry = os.lstat(path.parent), os.lstat(path)
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != 0 or directory.st_mode & 0o022
                or not stat.S_ISSOCK(entry.st_mode) or entry.st_uid != 0):
            raise Refused('locked_service_unavailable')
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(timeout)
            sock.connect(str(path))
            _pid, uid, _gid = struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != 0:
                raise Refused('locked_service_unavailable')
        except BaseException:
            sock.close()
            raise
    except OSError:
        raise Refused('locked_service_unavailable') from None
    sock.setblocking(False)
    return sock


class Client:
    """One status or authenticate connection from the desktop resident."""

    def __init__(self, sock):
        self.sock = sock
        self.lines = Lines(sock, 4096)

    @classmethod
    def status(cls, path=SOCKET_PATH):
        client = cls(connect(path))
        try:
            client.send(operation='status')
            return client.next(time.monotonic() + 3)
        finally:
            client.close()

    @classmethod
    def authenticate(cls, session_id, started, cover_owner, cover_token, deadline_seconds, path=SOCKET_PATH):
        client = cls(connect(path))
        client.send(operation='authenticate', sessionId=session_id, sessionStarted=started,
                    coverOwner=cover_owner, coverToken=cover_token, deadlineSeconds=deadline_seconds)
        return client

    def send(self, **fields):
        send_line(self.sock, dict(schema=SCHEMA, **fields))

    def keep(self):
        self.send(operation='keep')

    def renew(self, seconds):
        self.send(operation='renew', deadlineSeconds=seconds)

    def end(self):
        self.send(operation='end')

    def next(self, deadline):
        """Next server message, or None at the deadline. Raises Closed."""
        try:
            line = self.lines.next(deadline)
        except Refused:
            if time.monotonic() >= deadline:
                return None
            raise
        value = strict_json(line)
        if value.get('schema') != SCHEMA:
            raise Refused('locked_service_unavailable')
        return value

    def close(self):
        self.sock.close()


if __name__ == '__main__':
    raise SystemExit(main())
