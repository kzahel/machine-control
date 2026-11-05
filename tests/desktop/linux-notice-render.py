"""Presentation-only native GNOME notification pixels and withdrawal."""
import argparse,contextlib,json,os,pathlib,subprocess,sys,threading,time
import gi
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf,GLib
import linux_notice_ui
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime',type=pathlib.Path,required=True)
parser.add_argument('--output',type=pathlib.Path,required=True)
parser.add_argument('--terminate',action='store_true',help='Verify SIGTERM cleanup while the inherited stdin remains open')
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True,mode=0o700)
sys.dont_write_bytecode=True;sys.path.insert(0,str(args.runtime))
import linuxui,notice_environment
linuxui.Atspi.init();child=None;result=dict(complete=False,passed=False)
try:
 with (args.output/'notice.log').open('wb') as log:
  child=subprocess.Popen(['/usr/bin/python3',str(args.runtime/'notice.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,env=notice_environment.prepare(os.environ))
  thread=threading.Thread(target=lambda:list(iter(child.stdout.readline,b'')),daemon=True);thread.start()
  frame=dict(schema='machine-control-admission/v2',requests=[dict(state='waiting_for_approval',intentId='presentation-only',
      reason='Presentation-only fixture; no authority or effect provider',caller='Local fixture (identity unverified)',surfaces=['desktop'])],globalPauses=[])
  child.stdin.write(json.dumps(frame).encode()+b'\n');child.stdin.flush()
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   context=GLib.MainContext.default()
   while context.pending():context.iteration(False)
   control=linux_notice_ui.find(linuxui,'Allow now')
   if control:break
   assert child.poll() is None,'Native notice exited'
   time.sleep(.1)
  else:raise AssertionError('No actual native approval control')
  capture=args.output/'native-notification.png'
  subprocess.run(['/usr/bin/gnome-screenshot','--file',str(capture)],env={**os.environ,'GDK_BACKEND':'wayland'},check=True,timeout=15,stdout=subprocess.DEVNULL,stderr=log)
  image=GdkPixbuf.Pixbuf.new_from_file(str(capture));bounds=control[1]['bounds']
  x,y,w,h=(bounds[name] for name in ('x','y','width','height'))
  assert 0<=x<x+w<=image.get_width() and 0<=y<y+h<=image.get_height(),'Native notification coordinates outside capture'
  data=image.get_pixels();channels=image.get_n_channels();stride=image.get_rowstride()
  colors=len({tuple(data[(y+dy)*stride+(x+dx)*channels:(y+dy)*stride+(x+dx)*channels+3]) for dy in range(h) for dx in range(w)})
  assert colors>32,'Native notification action is blank'
  if args.terminate:child.terminate()
  else:child.stdin.close()
  child.wait(5);assert child.returncode==0,'Native notice did not exit cleanly'
  if not child.stdin.closed:child.stdin.close()
  deadline=time.monotonic()+5
  while linux_notice_ui.find(linuxui,'Allow now'):
   assert time.monotonic()<deadline,'Owned notification survived its owner'
   time.sleep(.1)
  result.update(passed=True,pixelKinds=colors,provider='freedesktop_notifications',withdrawn=True,exitMode='terminate' if args.terminate else 'eof')
except BaseException as error:
 result['failure']=type(error).__name__+': '+str(error);raise
finally:
 if child and child.poll() is None:
  child.terminate()
  with contextlib.suppress(subprocess.TimeoutExpired):child.wait(5)
  if child.poll() is None:child.kill();child.wait(2)
 result['complete']=True;(args.output/'summary.json').write_text(json.dumps(result))
