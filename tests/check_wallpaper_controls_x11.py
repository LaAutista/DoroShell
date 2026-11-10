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
 def state():return json.loads((Path(os.environ['XDG_RUNTIME_DIR'])/('doroshell-wallpaper-'+app.primaryScreen().name()+'.json')).read_text())
 cfg=json.loads(config.read_text())
 def save():
  temp=config.with_suffix('.tmp');temp.write_text(json.dumps(cfg));temp.replace(config)
 media=home/'red-source.mp4'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=red:s=200x100:r=60','-t','2','-c:v','libx264','-pix_fmt','yuv420p',str(media)],check=True,timeout=15)
 cfg.update(file=str(media),generation=1);save();wait(3)
 def red(color):return color.red()>200 and color.green()<40 and color.blue()<40
 for fit in ('fit','crop','stretch'):
  cfg['fit']=fit;save();wait(1)
  shot=app.primaryScreen().grabWindow(0).toImage()
  assert red(shot.pixelColor(500,380)),fit
  if fit=='fit':assert shot.pixelColor(900,700).name()=='#000000'
  else:assert red(shot.pixelColor(900,700)),fit
 for fps in (15,30,60):
  cfg['fps']=fps;save();wait(1)
  before=state()['frames'];wait(3);count=state()['frames']-before
  assert 0<count<=fps*3+2,(fps,count)
  print('CAP',fps,'accepted frames / 3 seconds',count,flush=True)
 print('PASS fit/crop/stretch geometry and 15/30/60 maximum repaint caps',flush=True)
finally:
 if p.poll() is None:p.terminate();p.wait(timeout=5)
 bus.terminate();bus.wait(timeout=5);wm.terminate();wm.wait(timeout=5);server.close()
