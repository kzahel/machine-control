#!/usr/bin/python3
"""Independent nonactivating native task notice; decisions use exact intents."""
import ctypes
import json
import math
import os
import signal
import sys
import threading
import gi

gi.require_version('Gtk','3.0')
from gi.repository import GLib,Gtk,Gdk

parent=os.getppid()
if ctypes.CDLL(None).prctl(1,signal.SIGTERM,0,0,0)!=0 or os.getppid()!=parent:
    raise SystemExit('Safety owner unavailable')
GLib.set_prgname('machine-control-safety');Gtk.init([])
if Gdk.Display.get_default().__gtype__.name!='GdkX11Display':
    raise SystemExit('Nonactivating Xwayland notification provider unavailable')
window=Gtk.Window(title='Machine Control — Agent access')
window.set_default_size(450,120);window.set_border_width(14)
window.set_accept_focus(False);window.set_focus_on_map(False);window.set_keep_above(True)
window.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);window.add(box)
heading=Gtk.Label(xalign=0);heading.set_line_wrap(True);box.pack_start(heading,False,False,0)
reason=Gtk.Label(xalign=0);reason.set_line_wrap(True);box.pack_start(reason,False,False,0)
caller=Gtk.Label(xalign=0);caller.set_line_wrap(True);box.pack_start(caller,False,False,0)
countdown=Gtk.Label(xalign=0);countdown.set_line_wrap(True);box.pack_start(countdown,False,False,0)
buttons=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5);box.pack_start(buttons,False,False,0)
binding=None;current=None


def intent(method,**fields):print(json.dumps(dict(method=method,**fields)),flush=True)


def button(label,method,**fields):
    value=Gtk.Button(label=label)
    value.connect('clicked',lambda *_:intent(method,**fields))
    buttons.pack_start(value,False,False,0)


def alive():
    intent('alive',visible=window.get_mapped())
    return True


def update(value):
    global binding,current
    requests=value.get('requests',[])
    priority={'waiting_for_approval':0,'announcing':1,'active':2,'paused':3,
              'waiting_for_availability':4,'waiting_for_resource':5,'offered':6}
    row=min(requests,key=lambda row:priority.get(row.get('state'),9)) if requests else None
    current=row
    if row is None:
        window.hide();binding=None;alive();return False
    state=row.get('state');identifier=row.get('intentId');surfaces=row.get('surfaces',[])
    title={'waiting_for_approval':'An agent wants to use this computer',
           'announcing':'An agent will start using this computer',
           'active':'An agent is using this computer','paused':'Agent access is paused',
           'waiting_for_availability':'An agent is waiting for access to become available',
           'waiting_for_resource':'An agent is waiting for another task to finish',
           'offered':'An agent is starting'}
    heading.set_text(title.get(state,'Agent access'))
    reason.set_text(row.get('reason',''))
    caller.set_text(row.get('caller','Local process (identity unverified)')+'\nAccess: '+', '.join(surfaces))
    remaining=row.get('noticeRemainingSeconds')
    cooldown=value.get('handoffCooldownRemainingSeconds',0)
    text=('Starting in '+str(math.ceil(remaining))+' seconds.' if isinstance(remaining,(int,float)) else '')
    if state=='paused':text=('Retry in '+str(math.ceil(cooldown))+' seconds, with a fresh warning.' if cooldown else 'A fresh warning appears before access resumes.')
    if state=='waiting_for_availability':text='Check permissions and provider availability in Settings. This request remains queued.'
    countdown.set_text(text)
    key=(identifier,state,tuple(surfaces),bool(value.get('globalPauses')))
    if key!=binding:
        binding=key
        for child in buttons.get_children():buttons.remove(child);child.destroy()
        if state=='waiting_for_approval':
            button('Allow this task','intent.approve',intentId=identifier)
            button('Deny this task','intent.deny',intentId=identifier)
        if state=='announcing':button('Start now','intent.start',intentId=identifier)
        if state in ('announcing','waiting_for_approval','active','offered'):
            button('Pause 30 seconds','intent.defer',intentId=identifier,duration=30)
            button('Pause 1 minute','intent.defer',intentId=identifier,duration=60)
            button('Pause until Resume','intent.defer',intentId=identifier,duration=None)
        if state=='paused':
            if value.get('globalPauses'):button('Resume global pause','resume')
            for surface in surfaces:button('Resume '+surface,'surface.resume',surface=surface)
        button('Stop all access','stop')
        button('Open Settings…','settings')
    window.show_all();alive();return False


window.connect('delete-event',lambda *_:(intent('stop'),True)[1])
def reader():
    try:
        for line in sys.stdin.buffer:
            if len(line)>65536:break
            value=json.loads(line)
            if not isinstance(value,dict) or value.get('schema')!='machine-control-admission/v2':break
            GLib.idle_add(update,value)
    finally:GLib.idle_add(Gtk.main_quit)

threading.Thread(target=reader,daemon=True).start()
GLib.timeout_add(500,alive)
intent('ready');Gtk.main()
