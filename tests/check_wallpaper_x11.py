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
 wait(4)
 a=app.primaryScreen().grabWindow(0).toImage();wait(.6);b=app.primaryScreen().grabWindow(0).toImage()
 assert a!=b,'No moving frames'
 b.save(str(home/'wallpaper-proof.png'))
 xtest.fake_input(server,X.MotionNotify,x=75,y=40);server.sync()
 for _ in range(2):
  xtest.fake_input(server,X.ButtonPress,1);xtest.fake_input(server,X.ButtonRelease,1);server.sync();wait(.08)
 wait(1)
 prop=root.get_full_property(server.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
 names=[]
 for wid in prop.value if prop else []:
  w=server.create_resource_object('window',int(wid));names.append(w.get_wm_name())
 print('WINDOWS',names)
 assert any(n and 'Clickable folder' in n for n in names),'Desktop folder did not open'
 print('PASS moving video beneath clickable native PCManFM desktop folder',flush=True)
 status=Path(os.environ['XDG_RUNTIME_DIR'])/('doroshell-wallpaper-'+app.primaryScreen().name()+'.json')
 def state(): return json.loads(status.read_text())
 full=QWidget();full.showFullScreen();wait(1.5);assert 'fullscreen' in state()['reasons'],state()
 (home/'locked').touch();wait(1.5);assert not state()['playing'] and any('locked' in r for r in state()['reasons'])
 full.close();wait(1);assert not state()['playing'],state()
 cfg=json.loads(config.read_text());cfg['paused']=True;config.write_text(json.dumps(cfg));wait(.8)
 (home/'locked').unlink();wait(1.5);assert not state()['playing'] and 'manual' in state()['reasons']
 cfg['paused']=False;config.write_text(json.dumps(cfg));wait(1);assert state()['playing'],state()
 server.force_screen_saver(X.ScreenSaverActive);server.sync();wait(1)
 assert 'screen saver' in state()['reasons'],state()
 server.force_screen_saver(X.ScreenSaverReset);server.sync();wait(1)
 from PIL import Image
 gif=home/'synthetic.gif'
 Image.new('RGB',(32,32),'red').save(gif,save_all=True,append_images=[Image.new('RGB',(32,32),'blue')],duration=150,loop=0)
 cfg['file']=str(gif);cfg['generation']=1;config.write_text(json.dumps(cfg));wait(1)
 colors=set()
 for _ in range(8):
  colors.add(app.primaryScreen().grabWindow(0).toImage().pixelColor(900,700).name());wait(.11)
 assert '#ff0000' in colors and '#0000ff' in colors,colors
 bad=home/'invalid.mp4';bad.write_text('not media');cfg['file']=str(bad);cfg['generation']=2;config.write_text(json.dumps(cfg));wait(1.5)
 assert 'renderer error' in state()['reasons'],state()
 first=state();wait(1);assert state()==first,'Failing renderer retried unexpectedly'
 cfg['enabled']=False;config.write_text(json.dumps(cfg));wait(1);assert not state()['playing']
 expected=QApplication.primaryScreen().grabWindow(0).toImage().pixelColor(900,700)
 assert expected.name()=='#234567',expected.name()
 print('PASS fullscreen/mock-lock/manual pause composition, resume, screen-saver pause, GIF playback, error latch and original background restoration',flush=True)
finally:
 p.terminate();p.wait(timeout=5);bus.terminate();bus.wait(timeout=5);wm.terminate();wm.wait(timeout=5);server.close()
