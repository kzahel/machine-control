"""Authenticated native transports; shared Node owns profile/CDP policy."""

import hashlib
import base64
import json
import os
from pathlib import Path
import shutil
import uuid
import queue
import threading
import select
import time

import subprocess
import socket
import artifacts

LIMIT = 1024 * 1024
HOST_NAME = "org.machine_control.browser"
# Unpacked development copy and Chrome Web Store release.
ORIGINS = ["chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/",
           "chrome-extension://epejchbeajneooefnklikkfhbaeadkpc/"]


class Peer:
    def __init__(self,client,origin):
        self.client,self.origin=client,origin
        self.tag=uuid.uuid4().hex;self.connection=None;self.problem=None
        self.attaching=False;self.waiting=[];self.closed=threading.Event()
        self.outgoing=queue.Queue(maxsize=32);self.inbound=threading.BoundedSemaphore(8)


class Browser:
    def __init__(self,owner):
        self.owner=owner;self.policy=owner.policy
        self.generation=uuid.uuid4().hex;self.native_state=None;self.stopped=True
        self.peers={};self.authorities={};self.audits={}
        self.lock=threading.Lock();self.output_bytes=0
        self.directory=Path(os.environ.get("XDG_DATA_HOME",Path.home()/".local/share"))/"machine-control"
        self.host=self.directory/"browser_host.py";self.extension=self.directory/"extension"

    def refresh_owned_installation(self):
        """Refresh an existing opt-in after replacement without opting in again."""
        config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        paths = [config / name / "NativeMessagingHosts" / (HOST_NAME + ".json")
                 for name in ["google-chrome", "google-chrome-for-testing", "chromium"]]
        if any(path.exists() and json.loads(path.read_text()).get("path") == str(self.host)
               for path in paths):
            self.setup(copy_path=False)

    def setup(self, copy_path=True):
        root = Path(__file__).resolve().parent
        self.directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        manifest = {"name": HOST_NAME, "description": "Machine Control browser provider",
                    "path": str(self.host), "type": "stdio", "allowed_origins": ORIGINS}
        paths = [config / browser / "NativeMessagingHosts" / (HOST_NAME + ".json")
                 for browser in ["google-chrome", "google-chrome-for-testing", "chromium"]]
        # Refuse to overwrite another installation's registration.
        for path in paths:
            if path.exists() and json.loads(path.read_text()).get("path") != str(self.host):
                raise ValueError("Another Machine Control browser host is registered")
        temporary = self.host.with_suffix(".new")
        shutil.copyfile(root / "browser_host.py", temporary)
        temporary.chmod(0o700)
        temporary.replace(self.host)
        self.extension.mkdir(mode=0o700, exist_ok=True)
        for source in (root / "extension").rglob("*"):
            if source.is_file():
                target = self.extension / source.relative_to(root / "extension")
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_name(target.name + ".new")
                shutil.copyfile(source, temp)
                temp.replace(target)
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".new")
            temp.write_text(json.dumps(manifest, indent=2) + "\n")
            temp.chmod(0o600)
            temp.replace(path)
        if copy_path:
            subprocess.run(["/usr/bin/wl-copy"], input=str(self.extension).encode(),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=True)
        return str(self.extension)

    def trusted(self, pid):
        try:
            args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            return len(args) >= 3 and Path(os.fsdecode(args[1])) == self.host and (
                os.fsdecode(args[2]) in ORIGINS) and hashlib.sha256(self.host.read_bytes()).digest() == (
                hashlib.sha256((Path(__file__).parent / "browser_host.py").read_bytes()).digest())
        except (OSError, ValueError):
            return False

    @property
    def connected(self):return any(row.get('connected') for row in self.profiles())
    def profiles(self):return self.policy.browser_state().get('profiles',[])
    def state(self):
        return dict(connected=self.connected,available=self.policy.alive,route='chrome.extension/cdp',
            profiles=self.profiles(),approvedProfiles=self.policy.browser_state().get('selectedProfiles',[]),
            profileSelectionSupported=True,sharedRuntime='typescript_node',
            callerAssurance='cooperative_same_user',
            streamingCdp=dict(available=self.policy.alive,browserLevel=True,
                binding='live_browser_surface_owner',transport='target_loopback_websocket'),
            knownOmissions=['incognito tabs','browser chrome UI','OS file dialogs','typed file upload'])

    def configure(self,profiles,duration,enabled):
        self.invalidate()
        self.policy.call(dict(method='operator.configure',scopes=['browser','devtools'] if enabled else [],
            profileIds=profiles,durationMs=duration))
        self.stopped=not enabled;self.native_state=None

    def invalidate(self):
        self.generation=uuid.uuid4().hex
        for value in self.authorities.values():value['revoked'].set()
        self.authorities.clear()
        for identifier in list(self.audits):self.end_audit(identifier,False)

    def stop_access(self):
        self.stopped=True;self.invalidate();self.native_state=None
        if self.policy.alive:self.policy.call(dict(method='operator.stop'))

    def sync(self):
        if not self.policy.alive:return
        state=self.owner.grants.view.get('surfaces',{}).get('browser',{})
        allowed=(not self.stopped and state.get('mode','off')!='off' and state.get('ready') is True
                 and not state.get('expired') and not state.get('pauses'))
        signature=(self.generation,allowed)
        if self.native_state!=signature:
            self.policy.call(dict(method='native.state',generation=self.generation,readable=allowed,writable=allowed))
            self.native_state=signature

    def register(self,client,pid):
        if not self.trusted(pid) or not self.policy.alive or len(self.peers)>=16:
            return None
        args=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        peer=Peer(client,os.fsdecode(args[2]).split('://',1)[1].strip('/'))
        self.peers[client]=peer
        threading.Thread(target=self.writer,args=(peer,),daemon=True,name='mc-browser-writer').start()
        self.enqueue(peer,dict(type='registered',protocolVersion=1))
        return peer

    def enqueue(self,peer,frame,authority=None):
        if peer.closed.is_set():return
        data=json.dumps(frame,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()+b'\n'
        if len(data)>16*LIMIT:self.disconnect(peer.client);return
        with self.lock:
            if self.output_bytes+len(data)>32*LIMIT:
                self.owner.scheduler.post(self.disconnect,peer.client);return
            try:peer.outgoing.put_nowait((data,authority,self.generation))
            except queue.Full:
                self.owner.scheduler.post(self.disconnect,peer.client);return
            self.output_bytes+=len(data)

    def writer(self,peer):
        try:
            while not peer.closed.is_set():
                try:data,authority,generation=peer.outgoing.get(timeout=.1)
                except queue.Empty:continue
                try:
                    offset=0;deadline=time.monotonic()+3
                    while offset<len(data):
                        if (peer.closed.is_set() or not self.policy.alive or generation!=self.generation or
                            authority is not None and (authority['revoked'].is_set() or self.owner.inhibit.is_set() or not authority['alive']())):
                            break
                        if time.monotonic()>=deadline:raise OSError('browser_write_timeout')
                        if not select.select([], [peer.client], [], .1)[1]:continue
                        try:count=peer.client.send(data[offset:],socket.MSG_DONTWAIT)
                        except BlockingIOError:continue
                        if count<=0:raise OSError('browser_write_closed')
                        offset+=count
                    # A partly written frame cannot be followed by another.
                    if offset and offset!=len(data):raise OSError('browser_frame_interrupted')
                finally:
                    with self.lock:self.output_bytes-=len(data)
        except (OSError,ValueError):self.owner.scheduler.post(self.disconnect,peer.client)
        finally:
            while True:
                try:data,_,_=peer.outgoing.get_nowait()
                except queue.Empty:break
                with self.lock:self.output_bytes-=len(data)

    def message(self,client,frame,completed=lambda:None):
        peer=self.peers.get(client)
        if peer is None or peer.closed.is_set() or peer.problem:
            completed();return
        if peer.connection is None:
            if peer.attaching:
                if len(peer.waiting)>=8:self.disconnect(client)
                else:peer.waiting.append(frame)
                completed();return
            if frame.get('type')!='hello':self.disconnect(client);completed();return
            peer.attaching=True
            def attached(value,error):
                peer.attaching=False
                if not peer.closed.is_set():
                    if error:
                        peer.problem=error
                        self.enqueue(peer,dict(type='profile.refused',protocolVersion=1,reason=error))
                    else:
                        peer.connection=value.get('connectionId')
                        if not peer.connection:self.disconnect(client)
                        else:
                            queued,peer.waiting=peer.waiting,[]
                            for waiting in queued:self.message(client,waiting)
                completed()
            self.policy.request(dict(method='browser.attach',extensionId=peer.origin,hello=frame,
                                     transportTag=peer.tag),attached,timeout=10)
        else:
            def received(_value,error):
                if error:self.disconnect(client)
                completed()
            self.policy.request(dict(method='provider.frame',connectionId=peer.connection,frame=frame),received)

    def disconnect(self,client):
        peer=self.peers.pop(client,None)
        if peer is None or peer.closed.is_set():return
        peer.closed.set()
        try:client.shutdown(socket.SHUT_RDWR)
        except OSError:pass
        if peer.connection and self.policy.alive:
            identifier=peer.connection
            self.policy.request(dict(method='provider.disconnect',connectionId=identifier),
                lambda *_:self.policy.request(dict(method='provider.retire',connectionId=identifier),lambda *_:None)
                if self.policy.alive else None)

    def event(self,message):
        kind=message.get('type')
        if kind=='access.event':
            if message.get('event') in {'yielded','ended'}:
                session=message.get('sessionId')
                for identifier,value in list(self.authorities.items()):
                    if session and value['session']==session:
                        value['revoked'].set();self.authorities.pop(identifier,None)
            return
        if kind=='native.check':
            allowed=self.check(message)
            self.policy.request(dict(method='native.reply',nativeId=message['nativeId'],accepted=allowed),lambda *_:None)
            return
        peer=next((peer for peer in self.peers.values() if peer.tag==message.get('transportTag') or
                   peer.connection and peer.connection==message.get('connectionId')),None)
        if peer is None:return
        if kind=='provider.close':self.disconnect(peer.client);return
        frame=message.get('frame')
        if not isinstance(frame,dict):self.disconnect(peer.client);return
        authority=None
        if frame.get('type') in {'request','session.open','session.command'}:
            authority=self.authorities.get(message.get('authorityId'))
            if not self.valid(authority):self.disconnect(peer.client);return
        if frame.get('type')=='grant' and (frame.get('browser') or frame.get('devtools')):
            expected='shared:'+str(self.policy.browser_state().get('authorizationGeneration'))+':'
            if self.stopped or not str(frame.get('grantGeneration','')).startswith(expected):return
        self.enqueue(peer,frame,authority)

    def valid(self,authority):
        return (authority is not None and not self.stopped and self.policy.alive and
                not self.owner.inhibit.is_set() and not authority['revoked'].is_set() and
                authority['generation']==self.generation and authority['validate']() is None)

    def cancel_invalid(self):
        for identifier,value in list(self.authorities.items()):
            if not self.valid(value):
                value['revoked'].set();self.authorities.pop(identifier,None)

    def check(self,frame):
        authority=self.authorities.get(frame.get('authorityId'));allowed=self.valid(authority)
        phase=frame.get('phase');identifier=frame.get('auditId')
        if phase=='check':return allowed
        if phase=='begin':
            if not allowed or not isinstance(identifier,str) or len(self.audits)>=256 or identifier in self.audits:return False
            if not self.owner.journal.begin('browser.cdp',identifier,self.generation,authority['pid']):return False
            self.audits[identifier]=authority;return True
        if phase=='result' and identifier in self.audits:
            return self.end_audit(identifier,allowed and frame.get('delivery')=='confirmed') and allowed
        return False

    def end_audit(self,identifier,confirmed):
        self.audits.pop(identifier,None)
        return self.owner.journal.record(dict(operation='browser.cdp',requestId=identifier,
            generation=self.generation,actualRoute='chrome.extension/cdp',accepted=confirmed,
            delivery='confirmed' if confirmed else 'unknown',effect='unverifiable',
            uncertainty='application_effect_not_independently_observed' if confirmed else 'browser_completion_not_observed'))

    def execute(self,request,finish,authority=None):
        operation=request.get('operation')
        if operation=='browser.upload':
            finish(self.owner.provider.fail(request,operation,'unsupported_operation','Typed upload is unavailable'));return
        if not self.policy.alive:
            finish(self.owner.provider.fail(request,operation,'control_policy_unavailable','Shared authority unavailable'));return
        if operation!='browser.profiles' and (authority is None or authority['validate']() is not None):
            finish(self.owner.provider.fail(request,operation,'control_session_required','Use one live Browser owner'));return
        self.sync();identifier=uuid.uuid4().hex;retained=operation=='browser.endpoint'
        authority_id='metadata'
        if authority is not None:
            if len(self.authorities)>=128:
                finish(self.owner.provider.fail(request,operation,'browser_stream_capacity','Browser owner capacity reached'));return
            authority_id=uuid.uuid4().hex
            authority={**authority,'generation':self.generation,'revoked':threading.Event()}
            self.authorities[authority_id]=authority
        def completed(reply,error):
            result=self.owner.provider.envelope(request,operation)
            result['actualRoute']='chrome.extension/cdp'
            if error:
                uncertain=error.startswith('ipc_') or error in ('resident_stopping','control_policy_unavailable')
                result.update(accepted=False,errorCode=error if not uncertain else 'browser_completion_unavailable',
                    delivery='unknown' if uncertain else 'refused',effect='unknown' if uncertain else 'refused',
                    uncertainty='browser_completion_not_observed' if uncertain else 'none',
                    retrySafety='unsafe_delivery_unknown' if uncertain else 'safe_not_dispatched')
            else:
                for key in ('accepted','errorCode','message','delivery','effect','uncertainty','retrySafety'):
                    if key in reply:result[key]=reply[key]
                data=dict(reply.get('data',{}))
                if 'profileId' in reply:data['browserProfileId']=reply['profileId']
                if 'providerGeneration' in reply:data['providerGeneration']=reply['providerGeneration']
                if operation=='browser.capture' and result.get('accepted'):
                    try:data['artifact']=artifacts.write(base64.b64decode(data.pop('png'),validate=True))
                    except (ValueError,KeyError,OSError):result=self.owner.provider.fail(request,operation,'artifact_failed','Capture artifact unavailable')
                result['data']=data
            if authority is not None and not self.valid(authority):
                result.update(accepted=False,errorCode='stale_control_session',uncertainty='interrupted_after_possible_dispatch',retrySafety='unsafe')
            if not retained:self.authorities.pop(authority_id,None)
            finish(result)
        self.policy.request(dict(method='browser.call',requestId=identifier,authorityId=authority_id,
            ownerSession=authority['owner']+':'+authority['session'] if authority else None,
            ownerProfileIds=authority['profiles'] if authority else [],request=request),completed,timeout=50)

    def close(self):
        self.stop_access()
        for client in list(self.peers):self.disconnect(client)
