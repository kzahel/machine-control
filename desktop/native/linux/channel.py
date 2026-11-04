"""One UID/process-bound v2 owner. The shared child owns admission policy."""
import json
import os
import queue
import re
import select
import socket
import threading
import time
import uuid
from policy import PolicyError

SCHEMA='machine-control-admission-channel/v2'


def process_token(pid):
    try:
        with open(f'/proc/{pid}/stat') as stream:return stream.read().rsplit(')',1)[1].split()[19]
    except (OSError,IndexError):return None


class Channel:
    def __init__(self,owner,client,pid,start):
        self.owner,self.client,self.pid,self.start=owner,client,pid,start
        self.label=uuid.uuid4().hex;self.sequence=0;self.intent=None
        self.surfaces=[];self.profiles=[];self.closed=threading.Event()
        self.incoming=threading.BoundedSemaphore(32)
        self.outgoing=queue.Queue(maxsize=32);self.bytes=0;self.lock=threading.Lock()
        self.dispatching=False;self.accepting=False;self.ticket=None
        threading.Thread(target=self.writer,daemon=True,name='mc-owner-writer').start()

    def authority(self):
        if self.closed.is_set() or self.start is None or process_token(self.pid)!=self.start:return 'owner_disconnected'
        return self.owner.native_authority(self.surfaces)

    def reply(self,request,data=None,error=None):
        value=dict(schema=SCHEMA,requestId=request.get('requestId',''),accepted=error is None)
        if error:value.update(errorCode=error,message='Control request refused')
        else:value['data']=data or {}
        body=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()+b'\n'
        with self.lock:
            if self.closed.is_set():return
            if len(body)>16*1024*1024 or self.bytes+len(body)>32*1024*1024:self.close();return
            try:self.outgoing.put_nowait(body)
            except queue.Full:self.close();return
            self.bytes+=len(body)

    def writer(self):
        try:
            while not self.closed.is_set():
                try:body=self.outgoing.get(timeout=.1)
                except queue.Empty:continue
                try:
                    offset=0;deadline=time.monotonic()+3
                    while offset<len(body):
                        if self.closed.is_set():return
                        if time.monotonic()>=deadline:raise OSError('owner_write_timeout')
                        if not select.select([], [self.client], [], .1)[1]:continue
                        try:count=self.client.send(body[offset:],socket.MSG_DONTWAIT)
                        except BlockingIOError:continue
                        if count<=0:raise OSError('owner_closed')
                        offset+=count
                finally:
                    with self.lock:self.bytes-=len(body)
        except (OSError,ValueError):self.close()

    def close(self):
        if self.closed.is_set():return
        self.closed.set()
        if self.ticket:self.ticket.cancelled.set()
        try:self.client.shutdown(socket.SHUT_RDWR)
        except OSError:pass
        self.owner.scheduler.post(self.cleanup)

    def cleanup(self):
        self.owner.channels.discard(self)
        self.owner.grants.close(self.label)
        self.owner.changed()
        return False

    @staticmethod
    def integer(value,low,high):
        if type(value) is not int or not low<=value<=high:raise ValueError('invalid_admission_request')
        return value

    def handle(self,request):
        try:
            if self.closed.is_set():return False
            if not isinstance(request.get('requestId'),str) or not 0<len(request['requestId'])<=128:
                raise ValueError('invalid_admission_request')
            sequence=self.integer(request.get('requestSequence'),1,2**53-1)
            if sequence!=self.sequence+1:raise ValueError('invalid_request_sequence')
            self.sequence=sequence
            operation=request.get('operation')
            common={'operation','requestId','requestSequence'}
            if self.intent is None:
                if operation!='control.open' or request.get('schema')!='machine-control-admission/v2':
                    raise ValueError('unsupported_admission_schema')
                allowed=common|{'schema','surfaces','profileIds','operations','waitSeconds','durationSeconds','reason','claimId'}
                if not set(request)<=allowed:raise ValueError('invalid_admission_request')
                surfaces=request.get('surfaces');profiles=request.get('profileIds',[]);operations=request.get('operations')
                if not isinstance(surfaces,list) or not surfaces or len(set(surfaces))!=len(surfaces) or any(s not in ('desktop','browser') for s in surfaces):raise ValueError('invalid_admission_request')
                if not isinstance(profiles,list) or len(profiles)>64 or any(not isinstance(p,str) or not 0<len(p)<=128 for p in profiles) or len(set(profiles))!=len(profiles):raise ValueError('invalid_admission_request')
                if ('browser' in surfaces)!=bool(profiles):raise ValueError('browser_profiles_required')
                if operations is not None and (not isinstance(operations,list) or not 0<len(operations)<=64 or any(not isinstance(op,str) or not op or len(op)>96 for op in operations)):
                    raise ValueError('invalid_admission_request')
                reason=request.get('reason')
                if not isinstance(reason,str) or not 0<len(reason.strip())<=240:raise ValueError('invalid_admission_request')
                self.surfaces,self.profiles=surfaces,profiles
                refusal=self.authority()
                if refusal:raise ValueError(refusal)
                value=self.owner.grants.submit(self.label,dict(requestId=request['requestId'],surfaces=surfaces,
                    profileIds=profiles,operations=operations,reason=reason.strip(),
                    waitMs=self.integer(request.get('waitSeconds',300),1,14400)*1000,
                    durationMs=self.integer(request.get('durationSeconds',300),1,900)*1000),self.authority)
                self.intent=value['intentId'];self.reply(request,value);self.owner.changed();return False
            if operation not in ('control.status','control.heartbeat','control.cancel') and self.authority():
                raise ValueError(self.authority())
            allowed=common|({'offerGeneration'} if operation=='control.accept' else
                {'sessionId','resourceGenerations','request'} if operation=='control.dispatch' else
                {'sessionId','resourceGenerations','durationSeconds'} if operation=='control.renew' else set())
            if not set(request)<=allowed:raise ValueError('invalid_admission_request')
            access=self.owner.grants
            if operation in ('control.status','control.heartbeat'):
                self.reply(request,access.inspect(self.label,operation=='control.heartbeat'))
            elif operation=='control.cancel':
                access.cancel(self.label);self.reply(request,access.inspect(self.label));self.owner.changed()
            elif operation=='control.accept':
                if self.accepting:raise ValueError('activation_in_progress')
                generation=self.integer(request.get('offerGeneration'),1,2**53-1)
                self.accepting=True
                def accept(ready):
                    self.accepting=False
                    if self.closed.is_set():return
                    try:
                        self.owner.refresh_availability()
                        if self.authority():raise ValueError(self.authority())
                        # Node revalidates the exact offer after the native
                        # boundary. No effect is dispatched by acceptance.
                        self.reply(request,access.accept(self.label,generation))
                    except (ValueError,PolicyError,KeyError) as error:self.reply(request,error=str(error))
                    self.owner.changed()
                self.owner.refresh_availability()
                if self.owner.activity.healthy(self.owner.session_identity):
                    self.owner.activity.barrier(self.owner.session_identity,accept)
                else:accept(False)  # Only Node's background offer can survive unknown input.
            elif operation=='control.renew':
                fence=self.fence(request)
                self.reply(request,access.send('renew',owner=self.label,fence=fence,
                    durationMs=self.integer(request.get('durationSeconds'),1,900)*1000))
            elif operation=='control.dispatch':
                if self.dispatching or self.accepting:raise ValueError('control_action_in_progress')
                fence=self.fence(request);action=request.get('request')
                if not isinstance(action,dict) or not isinstance(action.get('operation'),str):raise ValueError('invalid_control_action')
                action={**action,'requestId':request['requestId']}
                operation=action['operation']
                refusal=access.authorize(self.label,fence['sessionId'],fence['resourceGenerations'],operation)
                if refusal:raise ValueError(refusal)
                self.dispatching=True
                def completed(value):
                    self.dispatching=False
                    self.reply(request,value)
                self.owner.dispatch(self,action,fence,completed)
            else:raise ValueError('unsupported_control_operation')
        except (ValueError,TypeError,KeyError,PolicyError) as error:
            code=str(error)
            self.reply(request,error=code if re.fullmatch('[a-z][a-z0-9_]{0,95}',code) else 'invalid_admission_request')
        return False

    def fence(self,request):
        session=request.get('sessionId');generations=request.get('resourceGenerations')
        if not isinstance(session,str) or not session or not isinstance(generations,dict) or any(not isinstance(key,str) or type(value) is not int or value<0 for key,value in generations.items()):
            raise ValueError('invalid_control_fence')
        return dict(intentId=self.intent,sessionId=session,resourceGenerations=generations)
