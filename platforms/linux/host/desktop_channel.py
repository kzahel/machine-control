#!/usr/bin/env python3
"""Bounded same-user Unix/stdio transport. Admission remains in the resident."""
import os
from pathlib import Path
import select
import socket
import stat
import struct
import sys
import time

MAXIMUM=16*1024*1024


def endpoint():
    path=Path(os.environ.get('MACHINE_CONTROL_DESKTOP_SOCKET',
        f'/run/user/{os.getuid()}/machine-control-desktop/desktop.sock'))
    value=path.lstat()
    if not stat.S_ISSOCK(value.st_mode) or value.st_uid!=os.getuid() or stat.S_IMODE(value.st_mode)!=0o600:
        raise ValueError('Private desktop socket required')
    return path


def relay(check=lambda:None):
    check();parent=os.getppid()
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(3);client.connect(str(endpoint()))
        _pid,uid,_gid=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if uid!=os.getuid():raise ValueError('Same-user resident required')
        client.setblocking(False)
        incoming=sys.stdin.fileno();outgoing=sys.stdout.fileno()
        old=os.get_blocking(outgoing);os.set_blocking(outgoing,False)
        request=bytearray();to_socket=bytearray();to_stdout=bytearray()
        check_at=time.monotonic();write_at=None;output_at=None
        # A side that closes still gets its peer's pending bytes delivered:
        # a resident often replies with a refusal and closes immediately.
        resident_closed=caller_closed=False
        try:
            while os.getppid()==parent:
                if resident_closed and not to_stdout:return 0
                if caller_closed and not to_socket:return 0
                now=time.monotonic()
                if now>=check_at:
                    check();check_at=time.monotonic()+1;now=time.monotonic()
                if write_at is not None and now-write_at>3:raise ValueError('Resident write timeout')
                if output_at is not None and now-output_at>3:raise ValueError('Caller write timeout')
                readable=[incoming] if len(to_socket)<65536 and not caller_closed and not resident_closed else []
                if len(to_stdout)<MAXIMUM and not resident_closed:readable.append(client)
                writable=([client] if to_socket and not resident_closed else [])+([outgoing] if to_stdout else [])
                ready,writes,_=select.select(readable,writable,[],.1)
                if incoming in ready:
                    chunk=os.read(incoming,16384)
                    if not chunk:
                        caller_closed=True;continue
                    request.extend(chunk)
                    while b'\n' in request:
                        count=request.index(b'\n')+1
                        if count>65536:raise ValueError('Request frame too large')
                        check()  # Each complete frame retains exact-target claim authority.
                        now=time.monotonic();check_at=now+1
                        if not to_socket:write_at=now
                        to_socket.extend(request[:count]);del request[:count]
                    if len(request)>65536:raise ValueError('Request frame too large')
                if client in ready:
                    chunk=client.recv(65536)
                    if not chunk:
                        resident_closed=True;continue
                    if not to_stdout:output_at=now
                    to_stdout.extend(chunk)
                if client in writes:
                    try:count=client.send(to_socket)
                    except BlockingIOError:count=0
                    if count:
                        del to_socket[:count];write_at=now if to_socket else None
                if outgoing in writes:
                    try:count=os.write(outgoing,to_stdout)
                    except BlockingIOError:count=0
                    if count:
                        del to_stdout[:count];output_at=now if to_stdout else None
            return 1
        finally:os.set_blocking(outgoing,old)


if __name__=='__main__':
    try:raise SystemExit(relay())
    except (OSError,ValueError):raise SystemExit(1)
