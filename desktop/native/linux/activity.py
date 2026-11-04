"""Native read-only activity facts, sampled off the authority coordinator."""
import hashlib
import json
import os
from pathlib import Path
import queue
import socket
import stat
import struct
import threading
import time

SCHEMA='machine-control-physical-activity/v1'
ENDPOINT=Path('/run/machine-control-activity/activity.sock')


def console_binding(identity):
    if not isinstance(identity,tuple) or len(identity)!=3 or not isinstance(identity[0],str) or type(identity[1]) is not int or identity[1]<=0:
        return None
    return hashlib.sha256(json.dumps(list(identity[:2]),separators=(',',':')).encode()).hexdigest()


class Activity:
    def __init__(self,post,changed,endpoint=ENDPOINT):
        self.post,self.changed,self.endpoint=post,changed,Path(endpoint)
        self.pending=False;self.closed=False
        self.generation=None;self.token=None;self.binding=None
        self.observed=0.0;self.through=0.0;self.barrier_request=None
        self.installed=False;self.positive=False
        self.problem='activity_observer_unavailable'
        self.requests=queue.Queue(maxsize=1)
        self.thread=threading.Thread(target=self.worker,daemon=True,name='mc-activity')
        self.thread.start()

    def healthy(self,identity):
        return (not self.closed and self.positive and time.monotonic()-self.observed<=2.5 and
                time.monotonic()-self.through<=2.5 and
                self.binding is not None and self.binding==console_binding(identity))

    def refresh(self,watch,identity):
        if self.pending or self.closed:return
        self.pending=True
        self.requests.put_nowait((bool(watch),console_binding(identity)))

    def barrier(self,identity,completed):
        if self.closed or self.barrier_request is not None:
            completed(False);return
        self.barrier_request=(identity,time.monotonic(),completed)
        self.refresh(True,identity)

    def worker(self):
        while not self.closed:
            request=self.requests.get()
            if request is None:return
            watch,binding=request
            try:
                info=self.endpoint.lstat();parent=self.endpoint.parent.lstat()
                if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=0 or parent.st_uid!=0 or parent.st_mode&0o022:
                    raise ValueError('activity_observer_unavailable')
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as peer:
                    peer.settimeout(.7);peer.connect(str(self.endpoint))
                    _pid,uid,_gid=struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if uid!=0:raise ValueError('activity_observer_unavailable')
                    peer.sendall(json.dumps(dict(schema=SCHEMA,operation='sample',watch=watch)).encode()+b'\n')
                    with peer.makefile('rb') as stream:body=stream.readline(2049)
                if len(body)>2048 or not body.endswith(b'\n'):raise ValueError('activity_observer_unavailable')
                value=json.loads(body)
                if (not isinstance(value,dict) or value.get('schema')!=SCHEMA or value.get('accepted') is not True or
                    type(value.get('healthy')) is not bool or type(value.get('observedThroughUptime')) not in (int,float) or
                    not 0<=value['observedThroughUptime']<=time.monotonic()+.1 or any(not isinstance(value.get(key),str) or len(value[key])!=32
                    for key in ('generation','activityToken')) or value.get('consoleBinding')!=binding):
                    raise ValueError('activity_observer_unavailable')
                self.post(self.completed,value,None)
            except TimeoutError:self.post(self.completed,None,'activity_observer_silent')
            except (OSError,ValueError,KeyError,TypeError):self.post(self.completed,None,'activity_observer_unavailable')

    def completed(self,value,error):
        self.pending=False
        if self.closed:return
        if error:
            # Silence cannot renew the last positive sample. A fresh negative
            # report/endpoint loss is stronger and invalidates it immediately.
            if error!='activity_observer_silent':self.positive=False;self.installed=False
            self.problem=error
            self.changed(False,False)
            self.finish_barrier();return
        changed=self.generation is not None and self.generation!=value['generation']
        deliberate=(self.positive and not changed and self.binding==value['consoleBinding'] and
                    self.token is not None and self.token!=value['activityToken'])
        self.installed=True;self.observed=time.monotonic();self.through=value['observedThroughUptime'];self.positive=value['healthy']
        self.generation,self.token,self.binding=value['generation'],value['activityToken'],value['consoleBinding']
        self.problem=value.get('problem') if value.get('problem') in {'inactive','device_generation_changed','input_coverage_unavailable','input_stream_lost','console_generation_changed'} else None
        self.changed(changed,deliberate)
        self.finish_barrier()

    def finish_barrier(self):
        if self.barrier_request is None:return
        identity,after,completed=self.barrier_request
        if self.healthy(identity) and self.through>=after:
            self.barrier_request=None;completed(True)
        elif time.monotonic()-after>=2.5 or not self.installed:
            self.barrier_request=None;completed(False)
        else:self.refresh(True,identity)

    def state(self,identity):
        return dict(supported=True,installed=self.installed,healthy=self.healthy(identity),
                    problem=self.problem,route='linux.evdev_read_only',privilege='root_observer_no_input',
                    movementInterrupts=False,inputContentRetained=False,unknownBlocksAdmission=True)

    def close(self):
        self.closed=True;self.positive=False
        if self.barrier_request:
            _,_,completed=self.barrier_request;self.barrier_request=None;completed(False)
        # The current bounded sample retains its physical slot through exit.
        try:self.requests.put_nowait(None)
        except queue.Full:pass
