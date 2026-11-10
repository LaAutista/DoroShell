"""Opt-in private audio acceptance.
Requires PipeWire with Pulse protocol, pactl/parec, pw-cli/pw-link/pw-dump,
FFmpeg (libx264/AAC), Openbox and the usual private-X11 test dependencies.
A custom null-only server and manual links replace the audio session manager;
no ALSA, Bluetooth or physical audio devices are loaded. This verifies decoded
waveforms and controls, not real-device routing or perceived audio latency.
"""
import os,time,subprocess,json,sys,argparse,atexit
from pathlib import Path
from PySide6.QtWidgets import QApplication
from Xlib import display
parser=argparse.ArgumentParser(description='Private null-only waveform acceptance for wallpaper audio; never uses physical devices')
parser.add_argument('--run',action='store_true');parser.add_argument('--inside',action='store_true')
parser.add_argument('--xvfb',type=Path);parser.add_argument('--binary',type=Path,required=True)
args=parser.parse_args()
if not args.inside:
 if not args.run or not args.xvfb:parser.error('Opt in with --run --xvfb PATH')
 from x11_isolation import isolated
 isolated(args.xvfb,[sys.executable,__file__,'--inside','--binary',str(args.binary.resolve())])
 raise SystemExit(0)
home=Path.home()
assert home == Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY'] and os.environ['DISPLAY']!=':0'
def stop(process):
 if process.poll() is None:
  process.terminate()
  try: process.wait(timeout=5)
  except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)
def start(*args,**kwargs):
 process=subprocess.Popen(*args,**kwargs);atexit.register(stop,process);return process
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
wm=start(['openbox','--sm-disable'])
video=home/'not-yet-created.mp4'
(home/'.config/doroshell').mkdir()
config=home/'.config/doroshell/wallpaper.json'
config.write_text(json.dumps(dict(enabled=False,file=str(video),muted=True)))
bus_script=home/'mock-login.py'
bus_script.write_text('from gi.repository import Gio,GLib\nfrom pathlib import Path\nimport os\nconnection=Gio.bus_get_sync(Gio.BusType.SESSION,None)\nGio.bus_own_name_on_connection(connection,\'org.freedesktop.login1\',Gio.BusNameOwnerFlags.NONE,None,None)\nxml=\'<node><interface name="org.freedesktop.DBus.Properties"><method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method></interface></node>\'\ndef call(conn,sender,path,iface,method,args,invocation):\n locked=(Path.home()/\'locked\').exists()\n invocation.return_value(GLib.Variant(\'(v)\',(GLib.Variant(\'b\',locked),)))\nconnection.register_object(\'/org/freedesktop/login1/session/auto\',Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0],call,None,None)\nGLib.MainLoop().run()\n')
bus=start([sys.executable,str(bus_script)])
wait(.4)
# Private null-only PipeWire: no ALSA/udev modules or hardware devices.
private_audio = Path(os.environ['XDG_RUNTIME_DIR'])/'audio'; private_audio.mkdir()
os.environ.update(PIPEWIRE_RUNTIME_DIR=str(private_audio),PIPEWIRE_REMOTE='pipewire-0',PULSE_RUNTIME_PATH=str(private_audio/'pulse'),PULSE_SERVER='unix:'+str(private_audio/'pulse/native'),PULSE_SINK='test_sink')
audio_config=home/'null-audio.conf';audio_config.write_text('context.properties = { core.daemon = true core.name = pipewire-0 }\ncontext.spa-libs = { audio.convert.* = audioconvert/libspa-audioconvert support.* = support/libspa-support }\ncontext.modules = [\n{ name = libpipewire-module-protocol-native }\n{ name = libpipewire-module-spa-node-factory }\n{ name = libpipewire-module-client-node }\n{ name = libpipewire-module-access }\n{ name = libpipewire-module-adapter }\n{ name = libpipewire-module-link-factory }\n{ name = libpipewire-module-metadata }\n{ name = libpipewire-module-protocol-pulse }\n]\npulse.properties = { server.address = [ "unix:native" ] }\nstream.properties = { adapter.auto-port-config = { mode = dsp } }\ncontext.objects = [\n{ factory = spa-node-factory args = { factory.name = support.node.driver node.name = Dummy-Driver priority.driver = 20000 } }\n{ factory = adapter args = { factory.name = support.null-audio-sink node.name = test_sink media.class = Audio/Sink audio.position = [ FL FR ] adapter.auto-port-config = { mode = dsp monitor = true } } }\n]\n')
audio_log=open(home/'audio.log','w')
audio_server=start(['pipewire','-c',str(audio_config)],stdout=audio_log,stderr=audio_log)
wait(1)
assert subprocess.check_output(['pactl','list','short','sinks'],text=True).count('test_sink')==1
record=open(home/'capture.raw','wb')
recorder=start(['parec','--latency-msec=50','--device=test_sink.monitor','--format=float32le','--rate=48000','--channels=2'],stdout=record)
env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'],QT_MEDIA_BACKEND='ffmpeg')
p=start([str(args.binary),'--desktop','--profile=lxqt'],env=env)
try:
 cfg=json.loads(config.read_text())
 def save():
  temp=config.with_suffix('.tmp');temp.write_text(json.dumps(cfg));temp.replace(config)
 media=home/'tone.mp4'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=red:s=200x100:r=15','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','8','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(media)],check=True,timeout=15)
 cfg.update(enabled=True,file=str(media),generation=1);cfg.pop('muted',None);save();wait(3)
 data=json.loads(subprocess.check_output(['pw-dump'],text=True))
 node=next(x['id'] for x in data if x['type']=='PipeWire:Interface:Node' and x.get('info',{}).get('props',{}).get('node.name')=='doroshell-video-worker')
 subprocess.run(['pw-cli','set-param',str(node),'PortConfig','{ direction = Output mode = dsp format = { mediaType = audio mediaSubtype = raw format = F32P rate = 48000 channels = 2 position = [ FL FR ] } }'],check=True,stdout=subprocess.DEVNULL)
 wait(.5)
 for ch in ('FL','FR'):
  subprocess.run(['pw-link','doroshell-video-worker:output_'+ch,'test_sink:playback_'+ch],check=True)
  subprocess.run(['pw-link','test_sink:monitor_'+ch,'parec:input_'+ch],check=True)
 wait(1)
 import array,math
 def rms(label):
  wait(2);offset=(home/'capture.raw').stat().st_size;wait(.7)
  raw=(home/'capture.raw').read_bytes()[offset:];raw=raw[:len(raw)//4*4]
  values=array.array('f');values.frombytes(raw)
  assert len(values)>4800,(label,'no captured samples',len(values))
  value=math.sqrt(sum(v*v for v in values)/len(values));print('RMS',label,value,'samples',len(values),flush=True);return value
 assert rms('default-muted')<1e-6
 cfg['muted']=False;save();assert rms('unmuted')>.01
 cfg['paused']=True;save();assert rms('paused')<1e-6
 cfg['paused']=False;save();assert rms('resumed')>.01
 cfg['muted']=True;save();assert rms('remuted')<1e-6
 cfg['muted']=False;save();assert rms('unmuted-again')>.01
 cfg['enabled']=False;save();assert rms('off')<1e-6
 assert subprocess.check_output(['pactl','list','short','sink-inputs'],text=True).strip()==''
 assert not Path('/proc/'+str(p.pid)+'/task/'+str(p.pid)+'/children').read_text().strip()
 print('PASS null-only audio default mute, unmute, pause/resume, remute and Off stream/worker removal',flush=True)

finally:
 stop(p)
 stop(recorder);record.close()
 stop(audio_server);audio_log.close()
 print((home/'audio.log').read_text(),flush=True)
 stop(bus);stop(wm);server.close()
