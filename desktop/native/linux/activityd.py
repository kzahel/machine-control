#!/usr/bin/python3
"""Read-only activity facts for the active console; no input or key contents."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import select
import socket
import stat
import struct
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
from activity_events import EVENT,MAXIMUM_DEVICES,bitmap,deliberate,overflow,relevant

SCHEMA='machine-control-physical-activity/v1'
SOCKET=Path('/run/machine-control-activity/activity.sock')


class Tracker:
    def __init__(self,loop):
        self.loop=loop
        self.devices={}
        self.generation=uuid.uuid4().hex
        self.activity=uuid.uuid4().hex
        self.pending_activity=False
        self.observed_through=0.0
        self.healthy=False
        self.problem='inactive'
        self.watch_until=0.0

    def close(self,problem):
        for _key,fd in self.devices.values():
            self.loop.remove_reader(fd)
            os.close(fd)
        self.devices.clear()
        self.healthy=False
        self.observed_through=0.0
        self.pending_activity=False
        self.problem=problem
        self.generation=uuid.uuid4().hex

    @staticmethod
    def candidates():
        nodes={}
        for item in sorted(Path('/sys/class/input').glob('event*')):
            if not re.fullmatch('event[0-9]{1,4}',item.name):continue
            resolved=item.resolve(strict=True)
            if not resolved.is_relative_to('/sys/devices') or resolved.is_relative_to('/sys/devices/virtual'):continue
            capabilities=item/'device/capabilities'
            def bits(name):
                with (capabilities/name).open() as stream:return bitmap(stream.read(4097))
            keys,relative,absolute=bits('key'),bits('rel'),bits('abs')
            if not relevant(keys,relative,absolute):continue
            node=Path('/dev/input')/item.name
            info=node.lstat()
            if not stat.S_ISCHR(info.st_mode):raise ValueError('invalid_input_device')
            nodes[str(node)]=(info.st_rdev,info.st_ino,str(resolved),keys,relative,absolute)
        if not nodes or len(nodes)>MAXIMUM_DEVICES:raise ValueError('input_coverage_unavailable')
        return nodes

    def reconcile(self,now):
        if now>=self.watch_until:
            if self.devices:self.close('inactive')
            return
        try:
            candidates=self.candidates()
            if {name:key for name,(key,_) in self.devices.items()}!=candidates:
                self.close('device_generation_changed')
                for name,key in candidates.items():
                    fd=os.open(name,os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC|os.O_NOFOLLOW)
                    try:
                        info=os.fstat(fd)
                        if not stat.S_ISCHR(info.st_mode) or (info.st_rdev,info.st_ino)!=key[:2]:
                            raise ValueError('input_device_changed')
                        self.devices[name]=(key,fd)
                        self.loop.add_reader(fd,self.read,name,fd)
                    except BaseException:
                        if name not in self.devices:os.close(fd)
                        raise
            self.healthy=True;self.problem=None
            self.sample_boundary()
        except (OSError,ValueError):self.close('input_coverage_unavailable')

    def read(self,name,fd):
        try:
            body=os.read(fd,EVENT.size*256)
            if not body or len(body)%EVENT.size:raise ValueError('input_stream_lost')
            changed=False
            for _seconds,_microseconds,kind,code,value in EVENT.iter_unpack(body):
                if overflow(kind,code):raise ValueError('input_overflow')
                changed=changed or deliberate(kind,code,value)
            self.pending_activity=self.pending_activity or changed
        except BlockingIOError:pass
        except (OSError,ValueError):self.close('input_stream_lost')

    def sample_boundary(self):
        # A boundary includes every already-queued kernel event. Admission can
        # wait for a boundary after its activation offer, so an operator click
        # delivered before activation cannot become a late false takeover.
        for name,(_key,fd) in list(self.devices.items()):
            for _ in range(8):
                if not select.select([fd],[],[],0)[0]:break
                self.read(name,fd)
                if not self.devices:return
            if self.devices and select.select([fd],[],[],0)[0]:
                self.close('input_stream_lost');return
        if self.pending_activity:
            self.activity=uuid.uuid4().hex;self.pending_activity=False
        self.observed_through=time.monotonic()


class Console:
    def __init__(self):self.uid=None;self.binding=None;self.observed=0.0
    async def command(self,*args):
        process=await asyncio.create_subprocess_exec('/usr/bin/loginctl',*args,
            stdin=asyncio.subprocess.DEVNULL,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        try:
            data=await asyncio.wait_for(process.stdout.read(8193),.7)
            await asyncio.wait_for(process.wait(),.2)
            if process.returncode or len(data)>8192:raise ValueError('console_unavailable')
            return data.decode().strip()
        finally:
            if process.returncode is None:
                process.kill();await process.wait()
    async def refresh(self):
        try:
            session=await self.command('show-seat','seat0','--property=ActiveSession','--value')
            if not re.fullmatch('[a-zA-Z0-9_.-]{1,128}',session):raise ValueError('console_unavailable')
            text=await self.command('show-session',session,*('--property='+name for name in
                ('Id','User','Active','Type','Class','Remote','Seat','TimestampMonotonic')))
            fields=dict(line.split('=',1) for line in text.splitlines())
            if fields.get('Id')!=session or fields.get('Active')!='yes' or fields.get('Type')!='wayland' or fields.get('Class')!='user' or fields.get('Remote')!='no' or fields.get('Seat')!='seat0':
                raise ValueError('console_unavailable')
            uid=int(fields['User']);stamp=int(fields['TimestampMonotonic'])
            if uid<=0 or stamp<=0:raise ValueError('console_unavailable')
            self.uid=uid
            self.binding=hashlib.sha256(json.dumps([session,stamp],separators=(',',':')).encode()).hexdigest()
            self.observed=time.monotonic()
        except (OSError,ValueError,KeyError,asyncio.TimeoutError):
            self.uid=None;self.binding=None;self.observed=0.0


async def main():
    if os.geteuid()!=0 or EVENT.size!=24:raise SystemExit('Root 64-bit activity observer required')
    info=SOCKET.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:raise SystemExit('Root runtime directory required')
    if SOCKET.exists():
        info=SOCKET.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=0:raise SystemExit('Unowned activity endpoint')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as probe:
            probe.settimeout(.2)
            try:probe.connect(str(SOCKET))
            except ConnectionRefusedError:pass
            else:raise SystemExit('Activity observer already running')
        SOCKET.unlink()
    loop=asyncio.get_running_loop();tracker=Tracker(loop);console=Console();clients=0
    async def sample(reader,writer):
        nonlocal clients
        if clients>=8:writer.close();return
        clients+=1
        try:
            sock=writer.get_extra_info('socket')
            _pid,uid,_gid=struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            body=await asyncio.wait_for(reader.readline(),1)
            if len(body)>1024 or not body.endswith(b'\n'):raise ValueError('invalid_activity_request')
            request=json.loads(body)
            if not isinstance(request,dict) or set(request)!={'schema','operation','watch'} or request['schema']!=SCHEMA or request['operation']!='sample' or type(request['watch']) is not bool:
                raise ValueError('invalid_activity_request')
            now=time.monotonic()
            if console.uid!=uid or now-console.observed>1.5:raise ValueError('active_console_required')
            if request['watch']:tracker.watch_until=now+4
            value=dict(schema=SCHEMA,accepted=True,generation=tracker.generation,
                       consoleBinding=console.binding,healthy=tracker.healthy and now-tracker.observed_through<=1.5,
                       activityToken=tracker.activity,observedThroughUptime=tracker.observed_through,problem=tracker.problem)
            writer.write(json.dumps(value,separators=(',',':')).encode()+b'\n')
            await asyncio.wait_for(writer.drain(),1)
        except Exception:
            try:
                writer.write(json.dumps(dict(schema=SCHEMA,accepted=False,errorCode='activity_unavailable')).encode()+b'\n')
                await asyncio.wait_for(writer.drain(),.2)
            except (OSError,asyncio.TimeoutError):pass
        finally:
            clients-=1;writer.close()
            try:await writer.wait_closed()
            except OSError:pass
    server=await asyncio.start_unix_server(sample,path=str(SOCKET),limit=1024)
    SOCKET.chmod(0o666)
    previous=None
    try:
        while True:
            await console.refresh()
            if console.binding!=previous:
                tracker.close('console_generation_changed');tracker.watch_until=0;previous=console.binding
            tracker.reconcile(time.monotonic())
            await asyncio.sleep(.5)
    finally:
        server.close();await server.wait_closed();tracker.close('stopped');SOCKET.unlink(missing_ok=True)


if __name__=='__main__':asyncio.run(main())
