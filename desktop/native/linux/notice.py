#!/usr/bin/python3
"""Independent nonactivating native task notice; decisions use exact intents."""
import ctypes
import json
import math
import html
import os
import signal
import sys
import threading
import select
import time
import gi

gi.require_version('Gtk','3.0')
from gi.repository import GLib,Gtk,Gdk,Gio
from notification_state import Notification,primary_request,other_announcements

parent=os.getppid()
if ctypes.CDLL(None).prctl(1,signal.SIGTERM,0,0,0)!=0 or os.getppid()!=parent:
    raise SystemExit('Safety owner unavailable')
GLib.set_prgname('machine-control-safety');Gtk.init([])
if Gdk.Display.get_default().__gtype__.name!='GdkWaylandDisplay':
    raise SystemExit('Native Wayland controls unavailable')
# GTK 3 ships this public Wayland API without an introspection namespace.
# Obtain the default display from the same loaded GDK library; never derive
# a native pointer from a Python object's address or accept one from IPC.
gdk=ctypes.CDLL('libgdk-3.so.0')
gdk.gdk_display_get_default.argtypes=[]
gdk.gdk_display_get_default.restype=ctypes.c_void_p
gdk.gdk_wayland_display_set_startup_notification_id.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
gdk.gdk_wayland_display_set_startup_notification_id.restype=None
window=Gtk.Window(title='Machine Control — Agent access')
window.set_default_size(450,120);window.set_border_width(14)
window.set_keep_above(True)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);window.add(box)
heading=Gtk.Label(xalign=0);heading.set_line_wrap(True);box.pack_start(heading,False,False,0)
reason=Gtk.Label(xalign=0);reason.set_line_wrap(True);box.pack_start(reason,False,False,0)
caller=Gtk.Label(xalign=0);caller.set_line_wrap(True);box.pack_start(caller,False,False,0)
countdown=Gtk.Label(xalign=0);countdown.set_line_wrap(True);box.pack_start(countdown,False,False,0)
buttons=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5);box.pack_start(buttons,False,False,0)
binding=None;current=None;panel_requested=False;choices=[];caption_binding=None;caption_body='';activation=None


def intent(method,**fields):print(json.dumps(dict(method=method,**fields)),flush=True)


def hide_controls():
    global panel_requested
    panel_requested=False;window.hide();alive()

def button(label,method,**fields):
    value=Gtk.Button(label=label)
    value.connect('clicked',lambda *_:hide_controls() if method=='panel.hide' else intent(method,**fields))
    buttons.pack_start(value,False,False,0);choices.append((label,method,fields))


bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
service='org.freedesktop.Notifications';path='/org/freedesktop/Notifications'
owner=bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetNameOwner',
    GLib.Variant('(s)',(service,)),None,Gio.DBusCallFlags.NONE,1500,None).unpack()[0]
def call(method,parameters=None):
    return bus.call_sync(owner,path,service,method,parameters,None,Gio.DBusCallFlags.NONE,1500,None).unpack()
capabilities=call('GetCapabilities')[0]
if not {'body','actions','persistence'}<=set(capabilities):raise SystemExit('Persistent notification actions unavailable')
settings=Gio.Settings.new('org.gnome.desktop.notifications')
application=Gio.Settings.new_with_path('org.gnome.desktop.notifications.application',
    '/org/gnome/desktop/notifications/application/machine-control/')
def permitted():return (settings.get_boolean('show-banners') and application.get_boolean('enable') and application.get_boolean('show-banners'))
def notify(identifier,summary,body,actions):
    return call('Notify',GLib.Variant('(susssasa{sv}i)',('Machine Control',identifier,
        'preferences-desktop-remote-desktop',summary,body,actions,
        {'urgency':GLib.Variant('y',1 if current and current.get('state')=='paused' else 2),'resident':GLib.Variant('b',True),
         'suppress-sound':GLib.Variant('b',True),'desktop-entry':GLib.Variant('s','Machine Control')},0)))[0]
def close(identifier):call('CloseNotification',GLib.Variant('(u)',(identifier,)))
def show():
    global panel_requested,activation
    if current is None:return
    if activation and activation[0]==notification.identifier:
        gdk.gdk_wayland_display_set_startup_notification_id(gdk.gdk_display_get_default(),activation[1].encode('utf-8'))
    activation=None
    panel_requested=True;window.show_all();window.present();alive()
notification=Notification(owner,notify,close,intent,show)
def signal_received(_bus,sender,_path,_interface,signal,parameters,*_data):
    global activation
    values=parameters.unpack()
    if signal=='ActionInvoked':notification.action(sender,*values)
    elif signal=='NotificationClosed':notification.closed(sender,*values)
    elif signal=='ActivationToken':
        identifier,token=values
        if sender==owner and notification.identifier and identifier==notification.identifier and isinstance(token,str) and 0<len(token)<=4096:
            activation=(identifier,token)
# Bind to the actual service owner, never a replacement or a claimed sender.
bus.signal_subscribe(owner,service,None,path,None,Gio.DBusSignalFlags.NONE,signal_received)
def owner_changed(_bus,_sender,_path,_interface,_signal,parameters,*_data):
    if parameters.unpack()[2]!=owner:Gtk.main_quit()
bus.signal_subscribe('org.freedesktop.DBus','org.freedesktop.DBus','NameOwnerChanged',
    '/org/freedesktop/DBus',service,Gio.DBusSignalFlags.NONE,owner_changed)
bus.connect('closed',lambda *_:Gtk.main_quit())

def alive():
    intent('alive',available=permitted(),visible=notification.acknowledged() or window.get_mapped())
    return True


def update(value):
    global binding,current,panel_requested,choices,caption_binding,caption_body
    requests=value.get('requests',[])
    row=primary_request(requests)
    current=row
    if row is None:
        window.hide();panel_requested=False;binding=None;caption_binding=None;notification.withdraw();alive();return False
    state=row.get('state');identifier=row.get('intentId');surfaces=row.get('surfaces',[])
    title={'waiting_for_approval':'An agent wants to use this computer',
           'announcing':'An agent will start using this computer',
           'active':'An agent is using this computer','paused':'Agent access is paused',
           'waiting_for_availability':'An agent is waiting for access to become available',
           'waiting_for_resource':'An agent is waiting for another task to finish',
           'offered':'An agent is starting'}
    heading.set_text(title.get(state,'Agent access'))
    reason.set_text(row.get('reason',''))
    access=', '.join(surfaces)
    if row.get('profileNames'):access+=' · '+', '.join(row['profileNames'])
    caller.set_text(row.get('caller','Local process (identity unverified)')+'\nAccess: '+access)
    remaining=row.get('noticeRemainingSeconds')
    cooldown=value.get('handoffCooldownRemainingSeconds',0)
    text=('Starting in '+str(math.ceil(remaining))+' seconds.' if isinstance(remaining,(int,float)) else '')
    if state=='paused':text=('Retry in '+str(math.ceil(cooldown))+' seconds, with a fresh warning.' if cooldown else 'A fresh warning appears before access resumes.')
    if state=='waiting_for_availability':text='Check permissions and provider availability in Settings. This request remains queued.'
    others=other_announcements(requests,row)
    countdown.set_text('\n'.join([text,*others]).strip())
    if others:
        surfaces=sorted({surface for task in requests if task.get('state')=='announcing' for surface in task.get('surfaces',[])})
        heading.set_text('Starting '+' + '.join(surfaces)+' control')
    key=(identifier,state,tuple(surfaces),bool(value.get('globalPauses')))
    if key!=binding:
        binding=key;choices=[]
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
        button('Hide task controls','panel.hide')
    # The compositor owns the nonactivating banner. The full GTK panel is
    # mapped only after an explicit native notification action by the user.
    primary=[choice for choice in choices if choice[1] not in ('stop','settings','panel.hide')][:2]
    primary.extend(choice for choice in choices if choice[1]=='stop')
    if state in ('active','offered','paused','waiting_for_availability','waiting_for_resource'):
        primary=[*[choice for choice in primary if choice[1]!='stop'][:1],('Open task controls','panel.show',{}),('Stop all access','stop',{})]
    if others:primary=[('Pause all 30 seconds','pause',{'duration':30}),('Open task controls','panel.show',{}),('Stop all access','stop',{})]
    announcing=[task for task in requests if task.get('state')=='announcing']
    context=(key,tuple(task['intentId'] for task in announcing),json.dumps(primary,sort_keys=True),reason.get_text(),caller.get_text())
    if context!=caption_binding:
        caption_binding=context;lines=[]
        for task in announcing[:3]:
            remaining=task.get('noticeRemainingSeconds')
            if isinstance(remaining,(int,float)):
                deadline=time.strftime('%H:%M:%S',time.localtime(time.time()+remaining))
                access=', '.join(task.get('surfaces',[]))
                if task.get('profileNames'):access+=' ('+', '.join(task['profileNames'])+')'
                lines.append(access+' warning ends at '+deadline+'.')
        if len(announcing)>3:lines.append(str(len(announcing))+' tasks are starting. Open Settings for details.')
        lines.extend((reason.get_text(),caller.get_text()))
        if announcing:lines.append('Open task controls for the live countdown.')
        elif state=='paused':lines.append('Paused. A fresh warning appears before access resumes.')
        elif state=='waiting_for_availability':lines.append('Check permissions and provider availability in Settings.')
        caption_body='\n'.join(html.escape(text) for text in lines if text)
    # Replacing a GNOME notification rebuilds its action widgets. Keep the
    # absolute deadline caption stable so keyboard users retain action focus;
    # the explicit GTK panel continues to show Node's live countdown.
    try:notification.update(context,'Machine Control — '+heading.get_text(),caption_body,primary,identifier,state)
    except (GLib.Error,ValueError):Gtk.main_quit();return False
    if panel_requested:window.show_all()
    alive();return False


window.connect('delete-event',lambda *_:(intent('stop'),True)[1])
stopping=threading.Event()
def reader():
    # Never finalize Python with a daemon holding BufferedReader's stdin lock.
    descriptor=sys.stdin.fileno();os.set_blocking(descriptor,False);buffer=bytearray()
    try:
        while not stopping.is_set():
            if not select.select([descriptor],[],[],.2)[0]:continue
            try:chunk=os.read(descriptor,8192)
            except BlockingIOError:continue
            if not chunk:break
            buffer.extend(chunk)
            while b'\n' in buffer:
                line,_,remaining=buffer.partition(b'\n');buffer=bytearray(remaining)
                if len(line)>65535:return
                value=json.loads(line)
                if not isinstance(value,dict) or value.get('schema')!='machine-control-admission/v2':return
                GLib.idle_add(update,value)
            if len(buffer)>65535:return
    finally:GLib.idle_add(Gtk.main_quit)

reader_thread=threading.Thread(target=reader,name='mc-notice-input')
reader_thread.start()
GLib.timeout_add(500,alive)
signal.signal(signal.SIGTERM,lambda *_:GLib.idle_add(Gtk.main_quit))
signal.signal(signal.SIGINT,lambda *_:GLib.idle_add(Gtk.main_quit))
try:
    intent('ready');Gtk.main()
finally:
    stopping.set();reader_thread.join(timeout=1)
    try:notification.withdraw()
    except GLib.Error:pass
