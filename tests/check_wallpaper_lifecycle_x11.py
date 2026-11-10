import os,time,subprocess,json,sys,argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication,QWidget
from Xlib import X,display
from Xlib.ext import xtest
parser=argparse.ArgumentParser(description='Private wallpaper icon, fullscreen and mock-lock acceptance')
parser.add_argument('--run',action='store_true');parser.add_argument('--inside',action='store_true')
parser.add_argument('--xvfb',type=Path);parser.add_argument('--binary',type=Path,required=True);parser.add_argument('--media',type=Path,required=True)
args=parser.parse_args()
if not args.inside:
 if not args.run or not args.xvfb:parser.error('Opt in with --run --xvfb PATH')
 sys.path.insert(0,str(Path(__file__).resolve().parent))
 from x11_isolation import isolated
 isolated(args.xvfb,[sys.executable,__file__,'--inside','--binary',str(args.binary.resolve()),'--media',str(args.media.resolve())])
 raise SystemExit(0)
home=Path.home()
assert home == Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY'] and os.environ['DISPLAY']!=':0'
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
def wait(t):
 end=time.monotonic()+t
 while time.monotonic()<end:app.processEvents();time.sleep(.025)
(home/'Desktop/Clickable folder').mkdir(parents=True)
(home/'.config').mkdir(exist_ok=True)
(home/'.config/user-dirs.dirs').write_text('XDG_DESKTOP_DIR="$HOME/Desktop"\n')
c=home/'.config/pcmanfm-qt/lxqt/settings.conf';c.parent.mkdir(parents=True)
c.write_text('[Desktop]\nDesktopShortcuts=\nWallpaperMode=none\nBgColor=#234567\n[Behavior]\nSingleClick=false\n')
server=display.Display();root=server.screen().root
wm=subprocess.Popen(['openbox','--sm-disable'])
video=args.media;assert video.is_file()
(home/'.config/doroshell').mkdir()
config=home/'.config/doroshell/wallpaper.json'
config.write_text(json.dumps(dict(enabled=True,file=str(video),muted=True)))
bus_script=home/'mock-login.py'
bus_script.write_text('from gi.repository import Gio,GLib\nfrom pathlib import Path\nimport os\nconnection=Gio.bus_get_sync(Gio.BusType.SESSION,None)\nGio.bus_own_name_on_connection(connection,\'org.freedesktop.login1\',Gio.BusNameOwnerFlags.NONE,None,None)\nxml=\'<node><interface name="org.freedesktop.DBus.Properties"><method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method></interface></node>\'\ndef call(conn,sender,path,iface,method,args,invocation):\n locked=(Path.home()/\'locked\').exists()\n invocation.return_value(GLib.Variant(\'(v)\',(GLib.Variant(\'b\',locked),)))\nconnection.register_object(\'/org/freedesktop/login1/session/auto\',Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0],call,None,None)\nGLib.MainLoop().run()\n')
bus=subprocess.Popen([sys.executable,str(bus_script)])
wait(.4)
env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'],QT_MEDIA_BACKEND='ffmpeg')
p=subprocess.Popen([str(args.binary),'--desktop','--profile=lxqt'],env=env)
try:
 import signal
 def state():
  return json.loads((Path(os.environ['XDG_RUNTIME_DIR'])/('doroshell-wallpaper-'+app.primaryScreen().name()+'.json')).read_text())
 def children():
  ids=Path(f'/proc/{p.pid}/task/{p.pid}/children').read_text().split()
  return [int(pid) for pid in ids if Path(f'/proc/{pid}/exe').resolve().name=='doroshell-video-worker']
 def shm():
  return [link for link in Path(f'/proc/{p.pid}/fd').iterdir() if 'memfd:doroshell-video' in str(link.resolve())] if Path(f'/proc/{p.pid}').exists() else []
 def until(check,seconds=8):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   assert p.poll() is None,'Desktop died'
   try:
    if check():return
   except FileNotFoundError:pass
   wait(.05)
  raise AssertionError('Condition timed out: '+repr(state()))
 cfg=json.loads(config.read_text())
 def save():
  temp=config.with_suffix('.tmp');temp.write_text(json.dumps(cfg));temp.replace(config)
 until(lambda:state()['frames']>0 and state()['playing'])
 assert len(children())==1
 # A stopped helper cannot handle graceful termination. Off must kill it asynchronously.
 stopped=children()[0];os.kill(stopped,signal.SIGSTOP);cfg['enabled']=False;save()
 until(lambda:not children() and not Path(f'/proc/{stopped}').exists(),4)
 assert not shm(),'Shared frame segment survived Off'
 assert app.primaryScreen().grabWindow(0).toImage().pixelColor(900,700).name()=='#234567'
 # Repeat transitions without accumulating helpers or shared segments.
 for i in range(6):
  cfg['enabled']=True;save();until(lambda:state()['playing'] and len(children())==1)
  assert len(shm())==1,shm()
  cfg['enabled']=False;save();until(lambda:not children() and not state()['media_loaded'])
  assert not shm()
 cfg['enabled']=True;save();until(lambda:state()['playing'] and len(children())==1)
 crashed=children()[0];os.kill(crashed,signal.SIGKILL)
 until(lambda:'renderer error' in state()['reasons'] and not children())
 assert not shm()
 cfg['generation']=1;save();until(lambda:state()['playing'] and len(children())==1)
 cfg['paused']=True;save();until(lambda:'manual' in state()['reasons'])
 cfg['generation']=2;save();wait(2)
 assert len(children())==1 and not state()['playing'] and 'manual' in state()['reasons']
 cfg['paused']=False;save();until(lambda:state()['playing'])
 folder=home/'Keep this file window';folder.mkdir()
 subprocess.run([str(args.binary),'--new-window',str(folder)],env=env,check=True,timeout=5);wait(.5)
 def normal_windows():
  clients=root.get_full_property(server.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
  result=set()
  for wid in clients.value if clients else []:
   win=server.create_resource_object('window',int(wid));pid=win.get_full_property(server.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
   types=win.get_full_property(server.intern_atom('_NET_WM_WINDOW_TYPE'),X.AnyPropertyType)
   if pid and int(pid.value[0])==p.pid and types and server.intern_atom('_NET_WM_WINDOW_TYPE_NORMAL') in types.value and server.intern_atom('_NET_WM_WINDOW_TYPE_DESKTOP') not in types.value:result.add(int(wid))
  return result
 kept=normal_windows();assert kept
 os.kill(children()[0],signal.SIGSTOP)
 subprocess.run([str(args.binary),'--desktop-off'],env=env,check=True,timeout=2)
 until(lambda:not children(),4)
 assert p.poll() is None and normal_windows()==kept and not shm(),(p.poll(),normal_windows(),kept,shm())
 subprocess.run([str(args.binary),'--desktop','--profile=lxqt'],env=env,check=True,timeout=3)
 until(lambda:state()['playing'] and len(children())==1)
 assert normal_windows()==kept
 remaining=children()[0]
 os.kill(remaining,signal.SIGSTOP);p.kill();p.wait(timeout=5);wait(1.5)
 assert not Path(f'/proc/{remaining}').exists() or Path(f'/proc/{remaining}/stat').read_text().rsplit(')',1)[1].split()[0]=='Z','Helper survived desktop SIGKILL'
 assert not shm(),'Shared segment survived desktop shutdown'
 print('PASS stopped-helper Off, repeated On/Off, helper crash/error/retry, source reload while paused, desktop-off preserves file window, SIGSTOP helper + SIGKILL parent and anonymous-mapping cleanup',flush=True)
finally:
 if p.poll() is None:p.terminate();p.wait(timeout=5)
 bus.terminate();bus.wait(timeout=5);wm.terminate();wm.wait(timeout=5);server.close()
