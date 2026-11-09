"""Manual opt-in test. Only synthetic icons and temporary settings are changed."""
import os,sys,time,tempfile,subprocess,ast
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from Xlib import X, XK, display
from Xlib.ext import xtest
if '--run' not in sys.argv:
 raise SystemExit('Opt-in X11 test: pass --run to open a temporary panel and simulate dragging synthetic icons.')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import modules
app=QApplication([]);d=display.Display();root=d.screen().root;pointer=root.query_pointer()
def wait(t):
 end=time.monotonic()+t
 while time.monotonic()<end:app.processEvents();time.sleep(.02)
def find_panel(pid):
 found=[]
 def scan(win):
  try:
   prop=win.get_full_property(d.intern_atom('_NET_WM_PID'),X.AnyPropertyType);g=win.get_geometry()
   if prop is not None and int(prop.value[0])==pid and g.width>200 and 10<g.height<100 and win.get_attributes().map_state==X.IsViewable:found.append(win)
   for c in win.query_tree().children:scan(c)
  except Exception:pass
 scan(root);return found
with tempfile.TemporaryDirectory(prefix='doroshell-dock-drag-') as t:
 home=Path(t);conf=home/'.config/lxqt/panel.conf';conf.parent.mkdir(parents=True)
 conf.write_text('panels=panel1\n[panel1]\nplugins=dockbarx\nposition=Top\nsize=40\n[dockbarx]\ntype=dockbarx\nSetIconSize=true\nIconSize=28\n')
 env=dict(os.environ,HOME=t,XDG_CONFIG_HOME=t+'/.config',XDG_DATA_HOME=t+'/.local/share',XDG_CACHE_HOME=t+'/.cache',GSETTINGS_BACKEND='keyfile')
 modules.run(home,'taskbar-drag',apply=True)
 launchers=[];colors=['#01e37e','#e3017e','#017ee3']
 for i,c in enumerate(colors):
  icon=home/f'test{i}.png';im=QImage(32,32,QImage.Format.Format_ARGB32);im.fill(QColor(c));im.save(str(icon))
  desktop=home/f'test{i}.desktop';desktop.write_text(f'[Desktop Entry]\nType=Application\nName=DoroShell Drag Test {i}\nExec=/bin/true\nIcon={icon}\n')
  launchers.append(f'doroshelltest{i};{desktop}')
 subprocess.run(['gsettings','set','org.dockbarx.dockbarx','launchers',repr(launchers)],env=env,check=True)
 p=subprocess.Popen(['lxqt-panel','--config',str(conf)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
 try:
  wait(2);panels=find_panel(p.pid);assert len(panels)==1,len(panels);panel=panels[0]
  image=app.primaryScreen().grabWindow(panel.id).toImage();centers=[]
  for c in colors:
   points=[(x,y) for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x,y)==QColor(c)]
   assert len(points)>10,('Test icon missing',c)
   centers.append((round(sum(a for a,b in points)/len(points)),round(sum(b for a,b in points)/len(points))))
  pos=root.translate_coords(panel,0,0);(x,y)=centers[0];dx,dy=centers[2]
  xtest.fake_input(d,X.MotionNotify,x=pos.x+x,y=pos.y+y);xtest.fake_input(d,X.ButtonPress,1);d.sync();wait(.15)
  for step in range(1,16):
   xtest.fake_input(d,X.MotionNotify,x=pos.x+round(x+(dx+7-x)*step/15),y=pos.y+y);d.sync();wait(.05)
  wait(.3);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.8)
  value=ast.literal_eval(subprocess.check_output(['gsettings','get','org.dockbarx.dockbarx','launchers'],env=env,text=True))
  print('Order after real drag:',[a.split(';')[0] for a in value],flush=True)
  assert value==[launchers[1],launchers[2],launchers[0]],'Drag order did not persist'
  # Escape over another icon must not reorder anything.
  xtest.fake_input(d,X.MotionNotify,x=pos.x+centers[0][0],y=pos.y+y);xtest.fake_input(d,X.ButtonPress,1);d.sync();wait(.15)
  xtest.fake_input(d,X.MotionNotify,x=pos.x+centers[2][0],y=pos.y+y);d.sync();wait(.3)
  code=d.keysym_to_keycode(XK.string_to_keysym('Escape'))
  xtest.fake_input(d,X.KeyPress,code);xtest.fake_input(d,X.KeyRelease,code);d.sync();wait(.2)
  xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.4)
  assert ast.literal_eval(subprocess.check_output(['gsettings','get','org.dockbarx.dockbarx','launchers'],env=env,text=True))==value
  # A fresh panel/app child must load the saved order, not just an in-memory move.
  p.terminate();p.wait(timeout=5);xtest.fake_input(d,X.MotionNotify,x=500,y=500);d.sync();wait(.3)
  p=subprocess.Popen(['lxqt-panel','--config',str(conf)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
  wait(4);panels=find_panel(p.pid);assert len(panels)==1
  image=app.primaryScreen().grabWindow(panels[0].id).toImage();positions=[]
  for color in colors:
   xs=[x for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x,y)==QColor(color)]
   assert xs;positions.append(sum(xs)/len(xs))
  assert positions[1] < positions[2] < positions[0],positions
  print('PASS DockBarX left-drag, Escape cancellation, saved order after applet/panel restart',flush=True)
 finally:
  p.terminate();p.wait(timeout=5);xtest.fake_input(d,X.ButtonRelease,1);xtest.fake_input(d,X.MotionNotify,x=pointer.root_x,y=pointer.root_y);d.sync();d.close()
