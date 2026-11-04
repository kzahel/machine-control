"""Presentation-only probe: no control endpoint, grant or effect provider."""
import os
os.environ['GDK_BACKEND']='x11'
import argparse,json,pathlib,re,subprocess,sys,threading,time
import gi
gi.require_version('Gdk','3.0');gi.require_version('GdkX11','3.0')
from gi.repository import Gdk,GdkX11,GdkPixbuf
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime',type=pathlib.Path,required=True)
parser.add_argument('--output',type=pathlib.Path,required=True)
parser.add_argument('--composited',action='store_true',help='Also require an independent GNOME compositor capture')
args=parser.parse_args();runtime=args.runtime;output=args.output
output.mkdir(parents=True,exist_ok=True,mode=0o700)
sys.dont_write_bytecode=True;sys.path.insert(0,str(runtime))
import notice_environment
results=[]
try:
 for mode in ('default','production'):
  env=notice_environment.prepare(os.environ)
  if mode=='default':env.pop('GDK_RENDERING',None);env.pop('GDK_GL',None)
  with (output/(mode+'.log')).open('wb') as log:
   child=subprocess.Popen(['/usr/bin/python3',str(runtime/'notice.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,env=env)
   thread=threading.Thread(target=lambda:list(iter(child.stdout.readline,b'')),daemon=True);thread.start()
   try:
    frame={'schema':'machine-control-admission/v2','requests':[{'state':'active','intentId':'presentation-fixture',
     'reason':'Presentation-only rendering fixture','caller':'Local fixture (identity unverified)','surfaces':['desktop']}], 'globalPauses':[]}
    child.stdin.write(json.dumps(frame).encode()+b'\n');child.stdin.flush();time.sleep(2)
    tree=subprocess.check_output(['xwininfo','-root','-tree'],text=True,timeout=3)
    candidates=[int(re.search(r'(0x[0-9a-f]+)',line).group(1),16) for line in tree.splitlines() if 'Machine Control — Agent access' in line]
    owned=[]
    for candidate in candidates:
     props=subprocess.check_output(['xprop','-id',str(candidate),'_NET_WM_PID'],text=True,timeout=3)
     if '=' in props and props.rsplit('=',1)[1].strip()==str(child.pid):owned.append(candidate)
    assert len(owned)==1,'Expected exact owned client XID'
    xid=owned[0];info=subprocess.check_output(['xwininfo','-id',str(xid)],text=True,timeout=3)
    width=int(re.search(r'Width: (\d+)',info).group(1));height=int(re.search(r'Height: (\d+)',info).group(1))
    display=Gdk.Display.get_default();window=GdkX11.X11Window.foreign_new_for_display(display,xid)
    pixels=Gdk.pixbuf_get_from_window(window,0,0,width,height);assert pixels is not None
    pixels.savev(str(output/(mode+'.png')),'png',[],[])
    data=pixels.get_pixels();channels=pixels.get_n_channels();stride=pixels.get_rowstride()
    values={tuple(data[y*stride+x*channels:y*stride+x*channels+3]) for y in range(height) for x in range(width)}
    composite_colors=None
    if args.composited and mode=='production':
     capture=output/'production-composite.png'
     subprocess.run(['/usr/bin/gnome-screenshot','--file',str(capture)],check=True,timeout=15,stdout=subprocess.DEVNULL,stderr=log)
     image=GdkPixbuf.Pixbuf.new_from_file(str(capture))
     x=int(re.search(r'Absolute upper-left X: +(-?\d+)',info).group(1));y=int(re.search(r'Absolute upper-left Y: +(-?\d+)',info).group(1))
     assert x>=0 and y>=0 and x+width<=image.get_width() and y+height<=image.get_height(),'Notice outside captured native coordinates'
     data=image.get_pixels();channels=image.get_n_channels();stride=image.get_rowstride()
     composite_colors=len({tuple(data[(y+dy)*stride+(x+dx)*channels:(y+dy)*stride+(x+dx)*channels+3]) for dy in range(height) for dx in range(width)})
     assert composite_colors>32,'Compositor shows blank notice despite valid own-window pixels'
    results.append({'compositePixelKinds':composite_colors,'mode':mode,'pixelKinds':len(values),'width':width,'height':height,'presentationOnly':True})
   finally:
    child.stdin.close()
    try:child.wait(3)
    except subprocess.TimeoutExpired:child.kill();child.wait(3)
    thread.join(1)
 assert results[-1]['pixelKinds']>32,'Production notice did not render its contents'
 (output/'summary.json').write_text(json.dumps({'complete':True,'passed':True,'results':results}));print(json.dumps(results))
except BaseException as error:
 (output/'summary.json').write_text(json.dumps({'complete':True,'failure':type(error).__name__+': '+str(error),'results':results}));raise
