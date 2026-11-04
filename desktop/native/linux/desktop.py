#!/usr/bin/env python3
"""Supervised ordinary-user Linux desktop companion and private operator pipe."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import select
import socket
import stat
import struct
import subprocess
import sys
import threading
import time
from browser_preference import BrowserPreference
import session as desktop_session

# The resident has no operator window. Exporting its GTK invisible clipboard
# surface into the AT-SPI bus creates an in-process accessibility recursion.
# Visible approvals run in their own accessible process below.
os.environ["NO_AT_BRIDGE"] = "1"
os.environ.pop("GTK_MODULES", None)

import gi

from gi.repository import Gio, GLib

from operations import OBSERVE, CONTROL
from work import Work, Ticket, Cancelled
from presentation import Presentation, runtime_directory
from coordinator import Coordinator
from one_shot import read_reply
from journal import Journal
import uuid
from portal import Portal
from provider import Provider
from shortcut import Shortcut
from startup import Startup
from browser import Browser
from updates import Updates
import linuxui

from wire import read_frame,encode,SocketFrames
from policy import Policy,PolicyError
from access import Access
from activity import Activity
from channel import Channel,process_token
import notice_environment

class Desktop:
    def __init__(self, operator_pid, executable, instance="desktop", override=None):
        self.scheduler = Coordinator()
        self.loop = self.scheduler.loop
        self.operator_pid = operator_pid
        self.instance = instance
        self.executable = executable
        self.presentation = Presentation(instance, override)
        self.safety_available = False
        self.safety_observed=0.0;self.notice_visible=False
        self.safety_condition = threading.Condition()
        self.safety_state = None
        self.journal = Journal()
        def pump():
            context = GLib.MainContext.default()
            # One bounded event batch keeps queued provider admission progressing.
            for _ in range(16):
                if not context.pending():
                    break
                context.iteration(False)
        self.work = Work(self.scheduler.post, linuxui.Atspi.init, pump)
        self.stopped=False;self.channels=set();self.inhibit=threading.Event()
        self.configuration_sessions={'desktop':None,'browser':None}
        self.notice_pending=False;self.notice_seconds=10
        self.policy=Policy(self.scheduler.post,self.policy_event,self.policy_failed)
        self.grants=Access(self.policy,self.policy_changed)
        self.browser_preference = BrowserPreference(self.presentation.root, instance)
        self.grants.browser_while_locked = self.browser_preference.enabled
        self.locked = False
        self.session_identity = None
        self.session_pending = False
        self.session_observed = 0.0
        self.updates = Updates()
        self.provider = Provider(self)
        self.last_portal_state = "off"
        self.portal = Portal(self.changed, self.scheduler)
        self.shortcut = Shortcut(executable)
        self.startup = Startup(executable)
        self.browser = Browser(self)
        try:self.browser.refresh_owned_installation()
        except (OSError,ValueError):self.journal.diagnostic('browser.setup','browser_registration_invalid')
        self.activity=Activity(self.scheduler.post,self.activity_changed)
        self.activity_setup=None;self.activity_setup_error=None
        self.dialog = None
        self.dialog_id = None
        self.unlocked = False
        self.stopped = False
        self.directory = runtime_directory(instance)
        identity = Path(__file__).with_name("desktop-runtime.json")
        self.identity = json.loads(identity.read_text()) if identity.exists() else {}
        self.endpoint = self.directory / "desktop.sock"
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # A live socket is never unlinked; Tauri's single-instance gate owns normal launches.
        if self.endpoint.exists():
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as check:
                try:
                    check.connect(str(self.endpoint))
                except ConnectionRefusedError:
                    self.endpoint.unlink()
                else:
                    raise RuntimeError("Desktop resident is already running")
        self.socket.bind(str(self.endpoint))
        os.chmod(self.endpoint, 0o600)
        self.socket.listen(16)
        self.slots = threading.BoundedSemaphore(16)
        self.recovery = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.recovery_endpoint = self.directory / "operator.sock"
        self.recovery_endpoint.unlink(missing_ok=True)
        self.recovery.bind(str(self.recovery_endpoint))
        os.chmod(self.recovery_endpoint, 0o600)
        self.recovery.listen(4)
        self.recovery_slots = threading.BoundedSemaphore(4)
        threading.Thread(target=self.accept_recovery, daemon=True).start()
        self.start_safety()
        self.monitor()
        self.scheduler.timer(1000, self.monitor)

    def policy_changed(self,desktop_changed):
        if desktop_changed:self.work.cancel()
        if hasattr(self,'browser'):self.browser.cancel_invalid()
        self.changed()

    def policy_event(self,event):
        if event.get('type')=='access.event':
            if not self.journal.event('access.'+str(event.get('event','unknown'))):
                self.policy_failed('audit_storage_unavailable');return
            self.browser.event(event)
            self.grants.refresh();self.changed()
        else:self.browser.event(event)

    def policy_failed(self,code):
        self.inhibit.set();self.work.cancel()
        if hasattr(self,'browser'):
            self.browser.invalidate()
            for client in list(self.browser.peers):self.browser.disconnect(client)
        if self.policy.alive:self.policy._fail(code)
        self.journal.diagnostic('resident.policy',code)
        self.changed()

    def changed(self):
        if not self.notice_pending:
            self.notice_pending=True;self.scheduler.post(self.publish)

    def publish(self):
        self.notice_pending=False
        if self.stopped:return False
        if hasattr(self,'browser'):self.browser.sync()
        value=self.grants.state()
        callers={channel.intent:'Local process '+str(channel.pid)+' (identity unverified)' for channel in self.channels}
        profiles={row['profileId']:row.get('name','Browser profile')+' · '+row['profileId'][-8:] for row in self.browser.profiles()}
        value={**value,'requests':[{**row,'caller':callers.get(row.get('intentId'),'Local process (identity unverified)'),
            'profileNames':[profiles.get(identifier,'Unavailable profile · '+identifier[-8:]) for identifier in row.get('profileIds',[])]}
            for row in value.get('requests',[])]}
        with self.safety_condition:
            self.safety_state=value;self.safety_condition.notify()
        return False

    def activity_changed(self,generation,deliberate):
        if not self.policy.alive:return
        if generation:self.grants.fact('input',False)
        if deliberate:self.grants.input()
        self.refresh_availability();self.changed()

    def refresh_availability(self):
        if not self.policy.alive:return
        state=self.grants.view
        watch=any(row.get('mode','off')!='off' and not row.get('expired') for row in state.get('surfaces',{}).values())
        self.activity.refresh(watch,self.session_identity)
        self.grants.locked=self.locked;self.grants.session=self.session_identity
        self.grants.browser_while_locked=self.browser_preference.enabled
        known=self.session_identity is not None and time.monotonic()-self.session_observed<=2
        self.grants.fact('input',known and self.activity.healthy(self.session_identity))
        notice_health=self.safety_available and time.monotonic()-self.safety_observed<=2
        healthy=notice_health and self.journal.health['available'] and not self.grants.updating
        self.grants.ready=bool(self.unlocked and healthy)
        # Presentability is true before the first request; a hidden idle window
        # must not make Core skip its warning. Once a task exists, an actually
        # unmapped notice is a readiness floor until GTK acknowledges it.
        notice_ready=not self.unlocked or not state.get('requests') or self.notice_visible
        for surface in ('desktop','browser'):
            bound=known and self.configuration_sessions[surface]==self.session_identity
            ready=healthy and notice_ready and bound and (self.unlocked or surface=='browser' and self.locked and self.browser_preference.enabled)
            if surface=='desktop' and self.portal.state=='pending':ready=False
            self.grants.fact(surface,(bool(ready),bool(self.unlocked and notice_health)))
        self.browser.sync()

    def apply_session(self,unlocked,locked,identity):
        if identity is not None and any(binding is not None and binding!=identity for binding in self.configuration_sessions.values()):
            self.stop_access('console_session_changed')
            self.configuration_sessions={'desktop':None,'browser':None}
        self.unlocked,self.locked,self.session_identity=unlocked,locked,identity
        self.session_observed=time.monotonic()
        if not unlocked and self.portal.state!='off':self.portal.close()
        self.refresh_availability()

    def monitor(self):
        if self.stopped:return False
        if time.monotonic()-self.session_observed>2:
            self.unlocked=False;self.locked=False;self.session_identity=None
        if not self.session_pending:
            self.session_pending=True
            def observed(unlocked,locked,identity):
                self.session_pending=False;self.apply_session(unlocked,locked,identity)
            try:desktop_session.observe(self.portal.bus,observed)
            except GLib.Error:observed(False,False,None)
        if self.policy.alive:
            self.refresh_availability();self.grants.refresh()
        self.changed()
        return True

    def native_authority(self,_surfaces):
        if not self.policy.alive:return 'control_policy_unavailable'
        if not self.journal.health['available']:return 'audit_storage_unavailable'
        return None

    def emergency_fence(self):
        self.inhibit.set();self.work.cancel()
        for authority in list(self.browser.authorities.values()):authority['revoked'].set()

    def stop_access(self,reason='stopped_by_person'):
        self.emergency_fence();self.grants.stop(reason);self.browser.stop_access()
        self.changed()

    def state(self):
        admission=self.grants.state()
        return dict(deployment=self.grants.deployment(),accessPolicy=admission,admission=admission,
            nativeApproval=True,presentation=self.presentation.state(),platform='linux',
            manualUntilStoppedSupported=True,pauseSupported=True,
            providerWork=dict(busy=self.work.active is not None),
            sessionObservation=dict(ageSeconds=time.monotonic()-self.session_observed,refreshing=self.session_pending),
            safetyAvailable=self.safety_available,physicalActivity=self.activity.state(self.session_identity),
            nativeNotice=self.notice_capability(),
            activityObserver={**self.activity.state(self.session_identity),
                'setupState':'authorizing' if self.activity_setup else 'idle','setupError':self.activity_setup_error},
            permissions=dict(accessibility=self.unlocked,screenRecording=self.portal.ready),
            portal=dict(state=self.portal.state,error=self.portal.error,pointer=bool(self.portal.devices&2),keyboard=bool(self.portal.devices&1)),
            browser=self.browser.state(),browserWhileLocked=dict(supported=True,enabled=self.browser_preference.enabled),
            socket=str(self.endpoint),startOnLogin=self.startup.enabled,stopShortcutAvailable=self.shortcut.available,
            stopShortcut='Ctrl+Alt+Shift+.',activity=[],logging=self.journal.health)

    def notice_capability(self):
        return dict(route='freedesktop_notifications_wayland_controls',requiresNotificationActions=True,
            available=self.safety_available and time.monotonic()-self.safety_observed<=2)

    def operator(self, command):
        method = command.get("method")
        expected = command.get("expectedGeneration")
        if expected is not None and expected != self.grants.generation:
            raise ValueError("Operator authority changed before dispatch")
        if method == "presentation.status":
            return {"ok": True, "presentation": self.presentation.state(), "runtimeId": os.getpid()}
        if method == "presentation":
            if self.grants.pending:
                raise ValueError("Finish pending approval before changing presentation")
            return {"ok": True, "presentation": self.presentation.set(command.get("profile")), "runtimeId": os.getpid()}
        if method == "update_sync":
            return {"ok": True, "checkRequested": self.updates.sync(command.get("state"))}
        if method == "state":
            return {"ok": True, "state": self.state()}
        if method == "logs.query":
            return {"ok": True, "history": self.journal.query(command.get("offset", 0), command.get("operation", ""), command.get("outcome", ""), command.get("stream", "audit"))}
        if method == "logs.debug":
            self.journal.debug(command.get("enabled") is True)
            return {"ok": True}
        if method == "logs.preview":
            return {"ok": True, "preview": self.journal.preview()}
        if method == "logs.export":
            return {"ok": True, "path": self.journal.export()}
        if method == "logs.location":
            return {"ok": True, "path": str(self.journal.root)}
        if method == "logs.diagnostic":
            self.journal.diagnostic("desktop.supervisor", command.get("code", "unknown"))
            return {"ok": True}
        if method in {'surface.configure','configure_surface'}:
            surface=command.get('surface');mode=command.get('mode')
            if surface not in ('desktop','browser') or mode not in ('off','ask','automatic'):raise ValueError('Choose a surface mode')
            if mode!='off' and (not self.unlocked or self.session_identity is None or self.grants.updating or not self.journal.health['available']):
                raise ValueError('Use the unlocked console before enabling access')
            duration=command.get('duration',900)
            if type(duration) is not int or duration<0 or duration>28800:raise ValueError('Invalid duration')
            duration_ms=None if command.get('lifetime')=='until_stopped' else max(60,duration)*1000
            profiles=command.get('browserProfileIds',[]) if surface=='browser' else []
            if not isinstance(profiles,list) or any(not isinstance(p,str) for p in profiles):raise ValueError('Choose exact profiles')
            if surface=='browser':self.browser.configure(profiles,duration_ms,mode!='off')
            self.grants.configure(surface,mode,duration_ms,profiles)
            if mode!='off':
                self.inhibit.clear();self.configuration_sessions[surface]=self.session_identity
            self.refresh_availability();self.changed()
        elif method in {'arm','decision'}:raise ValueError('Use surface modes and one live task')
        elif method=='stop':self.stop_access()
        elif method in {'surface.pause','pause_surface'}:
            duration=command.get('duration')
            if duration is not None and (type(duration) is not int or not 1<=duration<=28800):raise ValueError('Invalid pause')
            self.grants.pause(command.get('surface'),seconds=duration)
        elif method in {'surface.resume','resume_surface'}:
            self.grants.resume(command.get('surface'))
            self.grants.send('resume',surface=command.get('surface'),reason='physical_takeover')
        elif method in {'intent.approve','approve_intent','intent.start','start_intent','intent.deny','deny_intent','intent.defer','defer_intent'}:
            action={'approve_intent':'approve','start_intent':'start','deny_intent':'deny','defer_intent':'defer'}.get(method,method.split('.')[-1])
            fields=dict(intentId=command.get('intentId'))
            if action=='defer':
                duration=command.get('duration')
                if duration is not None and (type(duration) is not int or not 1<=duration<=28800):raise ValueError('Invalid deferral')
                fields['milliseconds']=None if duration is None else duration*1000
            self.grants.send(action,**fields);self.changed()
        elif method=='control_notice':
            seconds=command.get('noticeSeconds')
            if type(seconds) is not int or seconds not in (5,10,30,60):raise ValueError('Invalid warning')
            self.grants.send('notice',milliseconds=seconds*1000)
        elif method=='browser_while_locked':
            enabled=command.get('enabled')
            if type(enabled) is not bool or enabled and not self.unlocked:raise ValueError('Use the unlocked console')
            self.browser_preference.set(enabled);self.refresh_availability()
        elif method=='activity.setup':self.prepare_activity()
        elif method in {'pause','resume'}:
            if method=='pause':
                duration=command.get('duration')
                if duration is not None and (type(duration) is not int or not 1<=duration<=28800):raise ValueError('Invalid pause')
                self.grants.pause(seconds=duration)
            else:self.grants.resume();self.grants.send('resume',surface='all',reason='physical_takeover')
        elif method == "shortcut":
            self.shortcut.set(command.get("enabled"))
        elif method == "startup":
            self.startup.set(command.get("enabled"))
        elif method == "browser.setup":
            bundled = command.get("bundled") is True
            extension = self.browser.setup(copy_path=bundled)
            if not bundled:
                if not Gio.AppInfo.launch_default_for_uri(
                        "https://chromewebstore.google.com/detail/machine-control/epejchbeajneooefnklikkfhbaeadkpc", None):
                    raise ValueError("Browser registered; could not open the Chrome Web Store")
            return {"ok": True, "extensionPath": extension}
        elif method == "permission":
            if not self.unlocked or self.grants.updating:
                raise ValueError("Stop access before changing sharing")
            self.portal.connect()
        elif method == "permission.disconnect":
            self.stop_access()
            self.portal.close()
        elif method == "prepare_update":
            if any(row.get('mode','off')!='off' for row in self.grants.view.get('surfaces',{}).values()):
                raise ValueError('Turn access Off before updating')
            self.stop_access();self.grants.updating=True
            self.portal.close()
        elif method == "cancel_update":
            self.grants.updating = False
        elif method == "quit":
            self.shutdown()
        else:
            raise ValueError("Unknown operator command")
        self.changed()
        return {"ok": True}

    def prepare_activity(self):
        if not self.unlocked or self.grants.updating or self.activity_setup:
            raise ValueError('Use the unlocked console before installing the activity observer')
        process=subprocess.Popen(['/usr/bin/pkexec','/usr/bin/python3','-I','-B',
            str(Path(__file__).with_name('activity-install.py')),'install'],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        self.activity_setup=process;self.activity_setup_error=None
        def wait():
            error=None
            try:
                output,_=process.communicate(timeout=180)
                if process.returncode or len(output)>1024 or json.loads(output).get('installed') is not True:
                    error='Activity observer installation was not confirmed'
            except (OSError,ValueError,subprocess.TimeoutExpired):
                error='Activity observer installation was not confirmed'
                try:process.terminate()
                except (OSError,PermissionError):pass
                try:process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    try:process.kill()
                    except (OSError,PermissionError):pass
                    process.wait()  # Retain the physical slot through privileged exit.
            def finished():
                if self.activity_setup is process:
                    self.activity_setup=None;self.activity_setup_error=error
                    if not self.stopped:self.refresh_availability();self.changed()
                return False
            self.scheduler.post(finished)
        threading.Thread(target=wait,daemon=True,name='mc-activity-setup').start()
        self.changed()

    def discovery(self,request):
        operation=request.get('operation')
        result=self.provider.envelope(request,operation)
        result.update(delivery='not_applicable',effect='not_applicable')
        if operation in ('status','grant.status'):
            result['data']={**self.grants.deployment(),'admission':self.grants.state(),
                'desktopProduct':True,'ready':self.grants.ready,'sourceRevision':self.identity.get('sourceRevision'),
                'semanticState':'ready' if self.unlocked else 'unavailable',
                'captureState':'ready' if self.portal.ready else 'unavailable',
                'inputState':'ready' if self.provider.input_ready() else 'unavailable',
                'browser':self.browser.state(),'physicalActivity':self.activity.state(self.session_identity),
                'nativeNotice':self.notice_capability(),
                'admissionChannel':dict(schema='machine-control-admission-channel/v2',
                    ownerBinding='live_same_user_transport',callerAssurance='unverified_same_user')}
        else:
            result['data']=dict(provider='linux-desktop',profile='gnome_wayland',privilege='ordinary_user',
                operations=sorted(OBSERVE|CONTROL|{'browser.profiles','browser.tabs','browser.snapshot','browser.click',
                    'browser.type','browser.key','browser.navigate','browser.wait','browser.capture','browser.release',
                    'browser.cdp','browser.eval','browser.endpoint','update.check','update.status'}),
                browser=self.browser.state(),capture=dict(route='user/linux.portal-pipewire',state=self.portal.state,scope='shared_screen'),
                input=dict(route='user/linux.portal-notify',authorization='portal_consent',coordinateSpace='portal_shared_screen'),
                physicalActivity=self.activity.state(self.session_identity),nativeNotice=self.notice_capability(),
                protectedDesktop=False,hostInterference='none',
                operatorProtection=dict(processTree=True,approvalPrompt='physical_input_and_gnome_shell_semantics_withheld_while_pending'))
        return result

    def handle(self,request,caller,complete,caller_pid=None):
        request['requestId']=request.get('requestId') or uuid.uuid4().hex
        operation=request.get('operation','')
        if operation in ('status','capabilities','grant.status'):
            complete(self.discovery(request));return
        if operation=='browser.profiles':self.browser.execute(request,complete);return
        if operation in ('update.check','update.status'):
            result=self.provider.envelope(request,operation);result['data']=self.updates.request(operation=='update.check');complete(result);return
        if operation=='grant.revoke':
            result=self.provider.envelope(request,operation);result['data']={**self.grants.deployment(),'revoked':False,'retained':'person_armed'};complete(result);return
        if operation=='grant.request':
            complete(self.provider.fail(request,operation,'legacy_grant_request_unsupported','Configure a surface mode and open one live task'));return
        result=self.provider.fail(request,operation,'control_session_required','Use one live surface task')
        surface='browser' if operation.startswith('browser.') else 'desktop'
        result['retrySafety']='safe_not_dispatched'
        result['data']=dict(requiredSurface=surface,requestOperation='control.open',
            controlSession=dict(schema='machine-control-admission/v2',surface=surface,profileSelection='exact'))
        complete(result)

    def dispatch(self,channel,request,fence,finish):
        operation=request['operation'];started=time.monotonic()
        def complete(value):
            value['generation']=self.grants.generation;value['elapsedMs']=int((time.monotonic()-started)*1000)
            refusal=self.grants.authorize(channel.label,fence['sessionId'],fence['resourceGenerations'],operation)
            if refusal:
                value.update(accepted=False,errorCode=refusal,uncertainty='interrupted_after_possible_dispatch',retrySafety='unsafe')
            if not self.journal.record(value):
                value.update(accepted=False,errorCode='audit_storage_unavailable',uncertainty='audit_result_not_persisted',retrySafety='unsafe')
            finish(value)
        if self.inhibit.is_set() or channel.authority():
            finish(self.provider.fail(request,operation,'owner_disconnected','Owner ended'));return
        if not self.journal.begin(operation,request['requestId'],self.grants.generation,channel.pid):
            finish(self.provider.fail(request,operation,'audit_storage_unavailable','Audit unavailable'));return
        if operation=='capabilities':complete(self.discovery(request));return
        if operation.startswith('browser.'):
            def validate():
                return channel.authority() or self.grants.authorize(channel.label,fence['sessionId'],fence['resourceGenerations'],operation)
            authority=dict(owner=channel.label,session=fence['sessionId'],profiles=channel.profiles,pid=channel.pid,
                validate=validate,alive=lambda:not channel.closed.is_set() and process_token(channel.pid)==channel.start)
            self.browser.execute(request,complete,authority);return
        # Fresh native session read before occupying the one provider slot.
        # Observation and Node ownership are revalidated before any effect.
        def observed(unlocked,locked,identity):
            self.apply_session(unlocked,locked,identity)
            refusal=channel.authority() or self.grants.authorize(channel.label,fence['sessionId'],fence['resourceGenerations'],operation)
            if refusal or not unlocked:
                finish(self.provider.fail(request,operation,refusal or 'desktop_unavailable','Desktop owner unavailable'));return
            self.provider_work(request,complete,channel,fence)
        try:desktop_session.observe(self.portal.bus,observed)
        except GLib.Error:observed(False,False,None)

    def start_safety(self):
        environment=notice_environment.prepare(os.environ)
        self.safety = subprocess.Popen(["/usr/bin/python3", str(Path(__file__).with_name("notice.py"))],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=sys.stderr, env=environment)

        def write():
            while not self.stopped:
                with self.safety_condition:
                    self.safety_condition.wait_for(lambda: self.safety_state is not None or self.stopped)
                    value, self.safety_state = self.safety_state, None
                if self.stopped:
                    return
                try:
                    self.safety.stdin.write(encode(value))
                    self.safety.stdin.flush()
                except OSError:
                    return

        def read():
            try:
                while True:
                    value = read_frame(self.safety.stdout)
                    if value and value.get("method")=="stop":self.emergency_fence()
                    if value is None:
                        break
                    def intent(value=value):
                        method = value.get("method")
                        if method == "ready":
                            self.safety_available = True;self.safety_observed=time.monotonic()
                            self.monitor()
                        elif method=="alive":
                            self.safety_observed=time.monotonic();self.safety_available=value.get("available") is True;self.notice_visible=value.get("visible") is True
                            self.refresh_availability()
                        elif method in {"stop", "pause", "resume", "surface.pause", "surface.resume", "intent.approve", "intent.start", "intent.deny", "intent.defer"}:
                            try:
                                self.operator(value)
                            except ValueError:
                                pass
                        elif method == "settings":
                            subprocess.Popen([self.executable, "--instance", self.instance, "--settings"],
                                             stdout=subprocess.DEVNULL, stderr=sys.stderr)
                        return False
                    self.scheduler.post(intent)
            finally:
                self.safety.wait()
                def lost():
                    self.safety_available = False
                    self.stop_access("safety_unavailable")
                    self.refresh_availability()
                    return False
                self.scheduler.post(lost)
        threading.Thread(target=write, daemon=True).start()
        threading.Thread(target=read, daemon=True).start()

    def accept_recovery(self):
        while not self.stopped:
            try:
                client, _ = self.recovery.accept()
            except OSError:
                return
            if not self.recovery_slots.acquire(blocking=False):
                client.close()
                continue
            threading.Thread(target=self.recovery_client, args=(client,), daemon=True).start()

    def recovery_client(self, client):
        try:
            _pid, uid, _gid = struct.unpack("3i", client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != os.getuid():
                return
            client.settimeout(3)
            request = read_frame(SocketFrames(client))
            if not request or request.get("method") not in {"presentation", "presentation.status", "stop"}:
                return
            event = threading.Event()
            reply = []
            cancelled = threading.Event()
            def run():
                if cancelled.is_set():
                    return False
                try:
                    reply.append(self.operator(request))
                except Exception as error:
                    reply.append({"ok": False, "error": str(error)})
                event.set()
                return False
            self.scheduler.post(run)
            if event.wait(3):
                client.sendall(encode(reply[0]))
            else:
                cancelled.set()
        except (OSError, ValueError):
            pass
        finally:
            client.close()
            self.recovery_slots.release()

    def provider_work(self, request, finish, channel, fence):
        operation = request["operation"]
        grant = self.grants.grant
        ticket = Ticket(self.grants.generation, grant["expires"] if grant else None)
        channel.ticket=ticket
        def authority():
            if channel.closed.is_set() or self.inhibit.is_set() or process_token(channel.pid)!=channel.start:
                raise Cancelled('Owner ended')
            value=self.policy.call(dict(method='access.authorize',owner=channel.label,fence=fence,operation=operation))
            if value.get('refusal'):raise Cancelled('Shared authority ended')
        ticket.authority=authority
        ticket.request_id = request["requestId"]
        replied = False
        timer = None

        def completed(value, error):
            nonlocal replied
            if replied:
                return
            replied = True
            if channel.ticket is ticket:channel.ticket=None
            if timer:
                self.scheduler.remove(timer)
            stale = ticket.generation != self.grants.generation
            if error or stale or ticket.cancelled.is_set() or time.monotonic() >= ticket.deadline:
                observed = value
                value = self.provider.fail(request, operation, "operation_cancelled", "Work ended or authority changed")
                if observed:
                    value.update(actualRoute=observed.get("actualRoute", value["actualRoute"]),
                                 fidelity=observed.get("fidelity", value["fidelity"]))
                elif operation.startswith("input."):
                    value.update(actualRoute="user/linux.portal-notify", fidelity="foreground_input")
                if ticket.dispatched:
                    value.update(delivery="unknown", effect="unknown", uncertainty="cancelled_after_dispatch",
                                 retrySafety="unsafe_delivery_unknown")
            finish(value)

        def run(active):
            active.check()
            if self.provider.generation != active.generation:
                self.provider.generation = active.generation
                self.provider.snapshots.clear()
            self.provider.ticket = active
            self.portal.ticket = active
            try:
                return self.provider.handle(request)
            finally:
                self.provider.ticket = self.portal.ticket = None

        if not self.work.submit(ticket, run, completed):
            if channel.ticket is ticket:channel.ticket=None
            finish(self.provider.fail(request, operation, "provider_busy", "Provider work is still running"))
            return

        def deadline():
            if not replied:
                ticket.cancelled.set()
                completed(None, Cancelled())
            return False
        timer = self.scheduler.timer(20000, deadline)

    def accept(self):
        while not self.stopped:
            try:
                client, _ = self.socket.accept()
            except OSError:
                break
            if not self.slots.acquire(blocking=False):
                client.close()
                continue
            threading.Thread(target=self.client, args=(client,), daemon=True).start()

    def client(self,client):
        channel=None;peer=None;event=threading.Event()
        try:
            pid,uid,_gid=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if uid!=os.getuid():return
            start=process_token(pid)
            if start is None:return
            client.settimeout(3);reader=SocketFrames(client);request=read_frame(reader)
            if request is None:return
            if request.get('operation')=='browser.register':
                result=[]
                def register():
                    result.append(self.browser.register(client,pid));event.set();return False
                self.scheduler.post(register)
                if not event.wait(5) or not result or result[0] is None:return
                peer=result[0]
                while not self.stopped and not peer.closed.is_set():
                    if not reader.buffer and not select.select([client],[],[],.5)[0]:continue
                    value=read_frame(reader,16*1024*1024)
                    if value is None:break
                    if not peer.inbound.acquire(timeout=1):break
                    self.scheduler.post(self.browser.message,client,value,peer.inbound.release)
                return
            if request.get('operation')=='control.open':
                channel=Channel(self,client,pid,start)
                self.scheduler.post(lambda:self.channels.add(channel) or False)
                while not self.stopped and not channel.closed.is_set():
                    if not channel.incoming.acquire(timeout=1):break
                    def delivered(value=request):
                        try:return channel.handle(value)
                        finally:channel.incoming.release()
                    self.scheduler.post(delivered)
                    while not reader.buffer and not select.select([client],[],[],.5)[0]:
                        if channel.closed.is_set() or self.stopped:return
                    request=read_frame(reader)
                    if request is None:break
                return
            result=[]
            def complete(value):result.append(value);event.set()
            self.scheduler.post(lambda:self.handle(request,'local process',complete,caller_pid=pid) or False)
            deadline=time.monotonic()+55
            while not event.wait(.1):
                if time.monotonic()>=deadline or select.select([client],[],[],0)[0]:return
            if result:client.sendall(encode(result[0]))
        except (OSError,ValueError,PolicyError):pass
        finally:
            if channel:channel.close()
            if peer:self.scheduler.post(self.browser.disconnect,client)
            client.close();self.slots.release()

    def operator_reader(self):
        while not self.stopped:
            try:
                command = read_frame(sys.stdin.buffer)
                if command and command.get("method")=="stop":self.emergency_fence()
                if command is None:
                    break
                complete = threading.Event()
                replies = []

                def run(command=command):
                    try:
                        reply = self.operator(command)
                    except Exception as error:
                        reply = {"ok": False, "error": str(error)}
                    reply["coordinatorGeneration"] = self.grants.generation
                    replies.append(reply)
                    complete.set()
                    return False

                self.scheduler.post(run)
                complete.wait()
                sys.stdout.buffer.write(encode(replies[0]))
                sys.stdout.buffer.flush()
            except (ValueError, OSError):
                break
        self.scheduler.post(lambda: self.shutdown() or False)

    def shutdown(self):
        self.journal.event("resident.stop")
        if self.stopped:
            return
        self.stopped = True
        self.work.cancel()
        self.grants.stop("operator_disconnected")
        self.portal.close()
        self.browser.close()
        for channel in list(self.channels):channel.close()
        self.activity.close()
        self.policy.stop()
        self.socket.close()
        self.endpoint.unlink(missing_ok=True)
        self.recovery.close()
        self.recovery_endpoint.unlink(missing_ok=True)
        self.presentation.close()
        with self.safety_condition:
            self.safety_condition.notify_all()
        if self.safety.poll() is None:
            self.safety.terminate()
        try:self.safety.wait(timeout=4)
        except subprocess.TimeoutExpired:
            self.safety.kill();self.safety.wait(timeout=1)
        self.loop.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--call", help="One agent request on stdin")
    args = parser.parse_args()
    if args.call:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(610)
            client.connect(args.call)
            client.sendall(encode(json.loads(sys.stdin.read())))
            with client.makefile("rb") as reader:
                sys.stdout.buffer.write(reader.read())
        return
    hello = read_frame(sys.stdin.buffer)
    if not hello or hello.get("method") != "hello" or hello.get("processId") != os.getppid():
        raise ValueError("Inherited operator handshake required")
    desktop = Desktop(os.getppid(), hello["executable"], hello.get("instance", "desktop"), hello.get("presentation"))
    for sig in [signal.SIGTERM, signal.SIGINT]:
        desktop.scheduler.signal(sig, lambda: desktop.shutdown() or False)
    threading.Thread(target=desktop.accept, daemon=True).start()
    threading.Thread(target=desktop.operator_reader, daemon=True).start()
    sys.stdout.buffer.write(encode({"ok": True}))
    sys.stdout.buffer.flush()
    try:
        desktop.loop.run()
    finally:
        desktop.shutdown()


if __name__ == "__main__":
    main()
