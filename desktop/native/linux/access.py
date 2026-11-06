"""Native facts/projections over v2. Consent, queues and time live in Node."""
import json
import time
import uuid
from policy import PolicyError

SCHEMA='machine-control-admission/v2'


class Access:
    def __init__(self,host,changed):
        self.host,self.changed=host,changed
        self.owners={};self.facts={};self.fingerprint=None
        self.generation=uuid.uuid4().hex
        self.desktop_consent=uuid.uuid4().hex
        self.updating=False;self.ready=False;self.locked=False;self.session=None
        self.browser_while_locked=False
        self.view=self.offline()
        # Last full status projection. The coordinator refreshes it about once
        # a second (publish) and after each change, so presentation never waits.
        self.status=None;self.status_current=False

    @staticmethod
    def offline():
        return dict(schema=SCHEMA,available=False,revision=0,requests=[],active=0,
            surfaces={surface:dict(mode='off',ready=False,expired=False,pauses=[],profileIds=[],
                consentRemainingSeconds=0,noticeVisible=False) for surface in ('desktop','browser')})

    def observe(self,value):
        if not isinstance(value.get('surfaces'),dict):return value
        desktop=value['surfaces'].get('desktop',{})
        sessions=sorted(row['sessionId'] for row in value.get('requests',[]) if
                        'desktop' in row.get('surfaces',[]) and row.get('sessionId'))
        fingerprint=json.dumps(dict(mode=desktop.get('mode'),ready=desktop.get('ready'),
            expired=desktop.get('expired'),pauses=[(row.get('scope'),row.get('reason')) for row in desktop.get('pauses',[])],
            sessions=sessions),sort_keys=True)
        revision=self.view.get('revision')
        self.view=value
        desktop_changed=self.fingerprint!=fingerprint
        if 'experienceVersion' in value:self.status=value;self.status_current=True
        elif desktop_changed or revision!=value.get('revision'):self.status_current=False
        if desktop_changed:
            self.fingerprint=fingerprint;self.generation=uuid.uuid4().hex
        if desktop_changed or revision!=value.get('revision'):self.changed(desktop_changed)
        return value

    def send(self,method,**fields):
        value=self.observe(self.host.call(dict(method='access.'+method,**fields)))
        if 'intentId' in value:
            self.observe(self.host.call(dict(method='access.query')))
        return value

    def state(self):
        if not self.host.alive:return self.offline()
        self.refresh()
        return self.send('state')

    def snapshot(self):
        """The last full projection; the first call populates it directly."""
        if not self.host.alive:return self.offline()
        return self.status if self.status is not None else self.state()

    def refresh(self):
        for owner,record in list(self.owners.items()):
            if record['authority']() is not None:
                self.send('cancel',owner=owner,intentId=record['intent'])
        return self.send('query')

    def fact(self,key,value):
        if self.facts.get(key)==value:return
        self.facts[key]=value
        if key=='input':self.send('input-ready',ready=value)
        else:self.send('ready',surface=key,ready=value[0],noticeVisible=value[1])

    def configure(self,surface,mode,duration,profiles=()):
        self.send('configure',surface=surface,configuration=dict(mode=mode,durationMs=duration,
            profileIds=list(profiles) if surface=='browser' else []))
        if surface=='desktop':self.desktop_consent=uuid.uuid4().hex

    def submit(self,owner,request,authority):
        self.send('open',owner=owner)
        try:
            value=self.send('submit',owner=owner,request=request)
            self.owners[owner]=dict(intent=value['intentId'],authority=authority)
            return value
        except BaseException:
            if self.host.alive:self.send('close',owner=owner)
            raise

    def inspect(self,owner,heartbeat=False):
        self.refresh()
        return self.send('inspect',owner=owner,intentId=self.owners[owner]['intent'],heartbeat=heartbeat)

    def accept(self,owner,generation):
        self.refresh()
        return self.send('accept',owner=owner,intentId=self.owners[owner]['intent'],offerGeneration=generation)

    def authorize(self,owner,session,generations,operation=None):
        if owner not in self.owners or not self.host.alive:return 'owner_disconnected'
        refusal=self.owners[owner]['authority']()
        if refusal:return refusal
        try:
            return self.send('authorize',owner=owner,fence=dict(intentId=self.owners[owner]['intent'],
                sessionId=session,resourceGenerations=generations),operation=operation).get('refusal')
        except PolicyError:return 'control_policy_unavailable'

    def cancel(self,owner):
        if owner in self.owners:self.send('cancel',owner=owner,intentId=self.owners[owner]['intent'])

    def close(self,owner):
        self.owners.pop(owner,None)
        if self.host.alive:self.send('close',owner=owner)

    def stop(self,_reason='stopped'):
        if self.host.alive:self.send('stop')
        else:self.view=self.offline();self.generation=uuid.uuid4().hex;self.changed(True)

    def pause(self,surface='all',reason='manual',seconds=None):
        self.send('pause',surface=surface,reason=reason,milliseconds=None if seconds is None else seconds*1000)

    def resume(self,surface='all'):
        for reason in ('manual','operator_deferral'):
            self.send('resume',surface=surface,reason=reason)

    def input(self):
        for surface in ('desktop','browser'):self.send('input',surface=surface,kind='key')

    @property
    def grant(self):
        desktop=self.view.get('surfaces',{}).get('desktop',{})
        if desktop.get('mode','off')=='off' or desktop.get('expired'):return None
        remaining=desktop.get('consentRemainingSeconds')
        return dict(id=self.desktop_consent,scopes=['observe','control'],
            expires=None if remaining is None else time.monotonic()+remaining)

    @property
    def pending(self):
        return next((row for row in self.view.get('requests',[]) if row.get('state')=='waiting_for_approval'),None)
    @property
    def paused(self):return bool(self.view.get('surfaces',{}).get('desktop',{}).get('pauses'))
    @property
    def browser_only_while_locked(self):return self.locked and self.browser_while_locked

    def deployment(self):
        grant=self.grant
        projected=None if grant is None else dict(grantId=grant['id'],scopes=grant['scopes'],
            lifetime='until_stopped' if grant['expires'] is None else 'timed',
            remainingSeconds=None if grant['expires'] is None else max(0,grant['expires']-time.monotonic()),
            origin='person',binding='desktop_surface_consent_projection')
        return dict(policy=dict(grantMode='surface_modes',preset='workstation',protectedOperations=False),
            grant=projected,pendingRequest=None,armed=None,paused=self.paused,generation=self.generation)
