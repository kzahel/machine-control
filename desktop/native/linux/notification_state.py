"""Native notification identity/actions only; all access policy stays in Node."""
import uuid


class Notification:
    def __init__(self,owner,notify,close,emit,show):
        self.owner,self.notify,self.close,self.emit,self.show=owner,notify,close,emit,show
        self.identifier=0;self.binding=None;self.actions={};self.message=None
        self.dismissed=None;self.acted=False;self.opened=False;self.stopped=False;self.intent=None;self.state=None

    def update(self,binding,summary,body,choices,intent,state):
        if binding!=self.binding:
            self.binding=binding;self.actions={('stop' if method=='stop' else uuid.uuid4().hex):(method,fields) for _,method,fields in choices}
            self.message=None;self.acted=False;self.opened=False;self.stopped=False;self.dismissed=None
        self.intent,self.state=intent,state
        if self.dismissed==binding:return
        message=(summary,body)
        if self.identifier and self.message==message:return
        actions=['default','Open task controls']
        for token,(label,_,_) in zip(self.actions,choices):actions.extend((token,label))
        identifier=self.notify(self.identifier,summary,body,actions)
        if type(identifier) is not int or identifier<=0 or self.identifier and identifier!=self.identifier:
            raise ValueError('Native notification identity changed')
        self.identifier=identifier;self.message=message

    def action(self,sender,identifier,key):
        if sender!=self.owner or not self.identifier or identifier!=self.identifier:return
        if key=='default':self.opened=True;self.show();return
        selected=self.actions.get(key)
        if selected is None:return
        # One decision per published binding. Late/double actions never replay.
        method,fields=selected
        if method=='stop':
            if not self.stopped:self.stopped=True;self.emit(method,**fields)
            return
        if self.acted:return
        self.acted=True;self.emit(method,**fields)

    def closed(self,sender,identifier,reason):
        if sender!=self.owner or not self.identifier or identifier!=self.identifier:return
        self.identifier=0;self.message=None;self.dismissed=self.binding
        if reason in (1,2) and not self.acted and not self.opened and self.intent and self.state!='paused':
            self.acted=True;self.emit('intent.defer',intentId=self.intent,duration=60)

    def withdraw(self):
        identifier=self.identifier
        self.identifier=0;self.binding=None;self.actions={};self.message=None
        self.dismissed=None;self.intent=None;self.state=None;self.acted=False;self.opened=False;self.stopped=False
        if identifier:self.close(identifier)
