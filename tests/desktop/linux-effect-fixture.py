#!/usr/bin/env python3
"""Small GTK effect oracle; each run owns an explicit state file."""
import argparse
import json
import os
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state',type=Path,required=True)
args=parser.parse_args()
GLib.set_prgname('machine-control-surface-fixture')
state={'pid':os.getpid(),'count':0,'text':''}
def save():
    temporary=args.state.with_suffix('.tmp')
    temporary.write_text(json.dumps(state));temporary.replace(args.state)
def clicked(*_):state['count']+=1;save()
def typed(entry):state['text']=entry.get_text();save()
window=Gtk.Window(title='Unified native fixture');window.set_default_size(420,180)
window.connect('destroy',Gtk.main_quit)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_border_width(16);window.add(box)
button=Gtk.Button(label='Increment fixture');button.connect('clicked',clicked);box.pack_start(button,False,False,0)
entry=Gtk.Entry();entry.get_accessible().set_name('Fixture text');entry.connect('changed',typed);box.pack_start(entry,False,False,0)
save();window.show_all();Gtk.main()
