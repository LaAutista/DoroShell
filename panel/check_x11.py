# SPDX-License-Identifier: LGPL-2.1-or-later
"""Opt-in X11 checks; run inside dbus-run-session with a separately built panel."""
import os,sys,time,tempfile,subprocess,argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary',required=True)
parser.add_argument('--run',action='store_true')
parser.add_argument('--fallback-context',action='store_true')
parser.add_argument('--contrast-only',action='store_true',help='Private white-bell popup contrast regression only')
parser.add_argument('--palette',choices=('windows','polar','heretic','spring'))
parser.add_argument('--contrast-output')
args=parser.parse_args()
if not args.run:parser.error('Pass --run to allow disposable windows and mouse/keyboard simulation')
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtGui import QIcon,QPixmap,QColor
from Xlib import display,X,XK
from Xlib.ext import xtest
import dbus,dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus=dbus.SessionBus()
if bus.name_has_owner('org.kde.StatusNotifierWatcher'):
 raise SystemExit('Use a private dbus-run-session; refusing to share an existing notifier service')
class Item(dbus.service.Object):
 def __init__(self):
  self.name=dbus.service.BusName('org.kde.StatusNotifierItem.DoroTest',bus)
  super().__init__(bus,'/StatusNotifierItem')
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
 def Get(self,interface,key):
  if key=='Menu' and args.fallback_context:raise dbus.exceptions.DBusException('No menu',name='org.freedesktop.DBus.Error.UnknownProperty')
  values={'Category':'ApplicationStatus','Id':'DoroTest','Title':'DoroShellSyntheticTray','Status':'Active','WindowId':dbus.Int32(0),'ItemIsMenu':False,'IconName':'','IconThemePath':'','Menu':dbus.ObjectPath('/Menu'),'OverlayIconName':'','AttentionIconName':'','AttentionMovieName':''}
  pixels=bytes([255,237,1,201])*24*24
  if args.contrast_only:
   pixels=bytes(c for y in range(24) for x in range(24) for c in ([255,255,255,255] if (7<=x<=16 and 7<=y<=16) or (5<=x<=18 and 17<=y<=18) or (10<=x<=13 and 20<=y<=21) else [0,0,0,0]))
  pix=dbus.Array([dbus.Struct((dbus.Int32(24),dbus.Int32(24),dbus.ByteArray(pixels)),signature='iiay')],signature='(iiay)')
  values.update(IconPixmap=pix,OverlayIconPixmap=dbus.Array([],signature='(iiay)'),AttentionIconPixmap=pix,ToolTip=dbus.Struct(('',pix,'DoroShellSyntheticTray','Synthetic test icon'),signature='sa(iiay)ss'))
  return values[key]
 @dbus.service.method('org.kde.StatusNotifierItem',in_signature='ii',out_signature='')
 def Activate(self,x,y):activated.append('activated')
 @dbus.service.method('org.kde.StatusNotifierItem',in_signature='ii',out_signature='')
 def ContextMenu(self,x,y):activated.append('context')

class TestMenu(dbus.service.Object):
 def __init__(self):super().__init__(bus,'/Menu')
 @dbus.service.method('com.canonical.dbusmenu',in_signature='iias',out_signature='u(ia{sv}av)')
 def GetLayout(self,parent,depth,names):
  child=dbus.Struct((dbus.Int32(1),dbus.Dictionary({'label':'Synthetic menu action','enabled':True,'visible':True},signature='sv'),dbus.Array([],signature='v')),signature='ia{sv}av')
  root=dbus.Struct((dbus.Int32(0),dbus.Dictionary({'children-display':'submenu'},signature='sv'),dbus.Array([child],signature='v')),signature='ia{sv}av')
  return dbus.UInt32(1),root
 @dbus.service.method('com.canonical.dbusmenu',in_signature='i',out_signature='b')
 def AboutToShow(self,item):return False
 @dbus.service.method('com.canonical.dbusmenu',in_signature='isvu',out_signature='')
 def Event(self,item,event,data,timestamp):
  if event=='clicked':activated.append('menu-clicked')
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
 def Get(self,interface,key):return {'Version':dbus.UInt32(3),'TextDirection':'ltr','Status':'normal','IconThemePath':dbus.Array([],signature='s')}[key]

app=QApplication([]);app.setApplicationName('DoroShellSyntheticTray');app.setApplicationDisplayName('DoroShellSyntheticTray')
d=display.Display();root=d.screen().root;pointer=root.query_pointer();activated=[]
def wait(t):
 end=time.monotonic()+t
 while time.monotonic()<end:
  app.processEvents()
  while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
  time.sleep(.02)
def windows(pid):
 found=[]
 def scan(w):
  try:
   value=w.get_full_property(d.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
   if value is not None and int(value.value[0])==pid and w.get_attributes().map_state==X.IsViewable:found.append(w)
   for child in w.query_tree().children:scan(child)
  except Exception:pass
 scan(root);return found
with tempfile.TemporaryDirectory(prefix='doroshell-native-tray-') as tmp:
 home=Path(tmp);conf=home/'panel.conf'
 if args.palette:
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
  from themes import PALETTES,theme_files
  for name,content in theme_files(PALETTES[args.palette]).items():
   path=home/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
 conf.write_text('panels=panel1\n[panel1]\nplugins=taskbar,statusnotifier\nposition=Bottom\ndoroshellTheme=true\nwidth=900\nwidth-percent=false\nreserve-space=false\npanelSize=40\n[taskbar]\ntype=taskbar\nbuttonStyle=Icon\nbuttonWidth=48\niconByClass=false\ngroupingEnabled=true\nshowOnlyOneDesktopTasks=false\n[statusnotifier]\ntype=statusnotifier\nalignment=Right\ndoroshellPopup=true\ndoroshellCollapseNew=true\n')
 env=dict(os.environ,HOME=tmp,XDG_CONFIG_HOME=tmp+'/.config',XDG_DATA_HOME=tmp+'/.local/share',XDG_CACHE_HOME=tmp+'/.cache')
 testwindow=QWidget();testwindow.setWindowTitle('DoroShell disposable task');testwindow.resize(240,160)
 taskpix=QPixmap(28,28);taskpix.fill(QColor('#01e3c7'));testwindow.setWindowIcon(QIcon(taskpix));testwindow.show();d.create_resource_object('window',int(testwindow.winId())).set_wm_class('DoroOne','DoroOne');d.sync();wait(.3);testwindow.showMinimized()
 second=QWidget();second.setWindowTitle('DoroShell disposable second task');second.resize(240,160);secondpix=QPixmap(28,28);secondpix.fill(QColor('#e3c701'));second.setWindowIcon(QIcon(secondpix));second.show();d.create_resource_object('window',int(second.winId())).set_wm_class('DoroTwo','DoroTwo');d.sync();wait(.3);second.showMinimized()
 pins=[]
 for identity,pix in [('DoroOne',taskpix),('DoroTwo',secondpix)]:
  icon=home/(identity+'.png');pix.save(str(icon))
  desktop=home/(identity+'.desktop');desktop.write_text('[Desktop Entry]\nType=Application\nName='+identity+'\nStartupWMClass='+identity+'\nIcon='+str(icon)+'\nExec=/usr/bin/touch '+str(home/(identity+'.launched'))+'\n')
  pins.append(str(desktop))
 cfg=QSettings(str(conf),QSettings.Format.IniFormat);cfg.setValue('taskbar/doroshellPinned',pins);cfg.sync();del cfg
 panel=subprocess.Popen([args.binary,'--config',str(conf)],env=env,stdout=subprocess.DEVNULL,stderr=open(home/'panel.log','w'))
 item=None
 try:
  wait(2);item=Item();testmenu=TestMenu()
  watcher=dbus.Interface(bus.get_object('org.kde.StatusNotifierWatcher','/StatusNotifierWatcher'),'org.kde.StatusNotifierWatcher')
  watcher.RegisterStatusNotifierItem('org.kde.StatusNotifierItem.DoroTest')
  wait(3);wins=windows(panel.pid);p=next(w for w in wins if w.get_geometry().width>100 and w.get_geometry().height<100)
  pos=root.translate_coords(p,0,0);g=p.get_geometry()
  # Single notifier in this isolated panel: the arrow occupies its last icon slot.
  xtest.fake_input(d,X.MotionNotify,x=pos.x+g.width-12,y=pos.y+g.height//2);xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.8)
  popups=[w for w in windows(panel.pid) if w.get_wm_name()=='Hidden icons']
  assert len(popups)==1, ('Hidden tray popup did not open', pos.x, pos.y, g.width, g.height, root.get_geometry().width)
  popup=popups[0]
  pp=root.translate_coords(popup,0,0);pg=popup.get_geometry()
  if args.contrast_only:
   assert os.environ.get('DOROSHELL_TEST_DISPLAY')==os.environ.get('DISPLAY')!=':0'
   assert not d.get_selection_owner(d.intern_atom('_NET_WM_CM_S0'))
   for phase in ('normal','hover','focus'):
    if phase=='hover':xtest.fake_input(d,X.MotionNotify,x=pp.x+pg.width//2,y=pp.y+pg.height//2);d.sync()
    if phase=='focus':
     code=d.keysym_to_keycode(XK.string_to_keysym('Tab'));xtest.fake_input(d,X.KeyPress,code);xtest.fake_input(d,X.KeyRelease,code);d.sync()
    wait(.3)
    image=app.primaryScreen().grabWindow(popup.id).toImage()
    bg=image.pixelColor(11,11)
    linear=lambda v:v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
    luminance=sum(weight*linear(value/255) for weight,value in zip((.2126,.7152,.0722),(bg.red(),bg.green(),bg.blue())))
    assert 1.05/(luminance+.05)>=4.5,(phase,bg.name(),'white glyph contrast')
    white=sum(min(image.pixelColor(x,y).red(),image.pixelColor(x,y).green(),image.pixelColor(x,y).blue())>245 for x in range(15,image.width()-15) for y in range(15,image.height()-15))
    assert white>=5,(phase,'white bell missing')
    if args.contrast_output:image.save(args.contrast_output+'-'+phase+'.png')
   print('PASS white bell contrast in normal/hover/keyboard-focus popup:',args.palette or 'native default',flush=True)
   raise SystemExit(0)

  xtest.fake_input(d,X.MotionNotify,x=pp.x+pg.width//2,y=pp.y+pg.height//2);xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.4)
  assert activated,'Synthetic tray icon did not receive activation'
  count=len(activated);key=d.keysym_to_keycode(XK.string_to_keysym('Return'));xtest.fake_input(d,X.KeyPress,key);xtest.fake_input(d,X.KeyRelease,key);d.sync();wait(.4)
  assert len(activated)==count+1,'Keyboard activation failed'
  xtest.fake_input(d,X.ButtonPress,3);xtest.fake_input(d,X.ButtonRelease,3);d.sync();wait(.3)
  if args.fallback_context:
   assert 'context' in activated,'Context fallback failed'
  else:
   key=d.keysym_to_keycode(XK.string_to_keysym('Down'));xtest.fake_input(d,X.KeyPress,key);xtest.fake_input(d,X.KeyRelease,key)
   key=d.keysym_to_keycode(XK.string_to_keysym('Return'));xtest.fake_input(d,X.KeyPress,key);xtest.fake_input(d,X.KeyRelease,key);d.sync();wait(.5)
   assert 'menu-clicked' in activated,'DBusMenu action failed'
  key=d.keysym_to_keycode(XK.string_to_keysym('Escape'));xtest.fake_input(d,X.KeyPress,key);xtest.fake_input(d,X.KeyRelease,key);d.sync();wait(.4)
  assert not [w for w in windows(panel.pid) if w.get_wm_name()=='Hidden icons']
  # Click only the uniquely colored disposable task, never a personal application.
  image=app.primaryScreen().grabWindow(p.id).toImage()
  points=[(x,y) for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x,y)==QColor('#01e3c7')]
  assert points,'Synthetic task icon missing'
  tx=round(sum(x for x,y in points)/len(points));ty=round(sum(y for x,y in points)/len(points))
  xtest.fake_input(d,X.MotionNotify,x=pos.x+tx,y=pos.y+ty);xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.5)
  assert not testwindow.isMinimized(),'Native task click did not restore test window'
  def task_center(color):
   im=app.primaryScreen().grabWindow(p.id).toImage()
   pts=[(x,y) for y in range(im.height()) for x in range(im.width()) if im.pixelColor(x,y)==QColor(color)]
   assert pts,('Missing test task',color)
   return round(sum(x for x,y in pts)/len(pts)),round(sum(y for x,y in pts)/len(pts))
  ax,ay=task_center('#01e3c7');bx,by=task_center('#e3c701');before=ax<bx
  target=bx+18 if before else bx-18
  xtest.fake_input(d,X.MotionNotify,x=pos.x+ax,y=pos.y+ay);xtest.fake_input(d,X.ButtonPress,1);d.sync();wait(.15)
  for step in range(1,16):
   xtest.fake_input(d,X.MotionNotify,x=pos.x+round(ax+(target-ax)*step/15),y=pos.y+ay);d.sync();wait(.05)
  xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.5)
  assert (task_center('#01e3c7')[0]<task_center('#e3c701')[0])!=before,'Native task reorder failed'
  cfg=QSettings(str(conf),QSettings.Format.IniFormat)
  assert cfg.value('taskbar/doroshellPinned')==list(reversed(pins)), 'Pinned drag order was not saved'
  del cfg
  # Closed applications retain one launcher in the same position; GIO launches its desktop entry.
  testwindow.close();wait(.5)
  cx,cy=task_center('#01e3c7')
  xtest.fake_input(d,X.MotionNotify,x=pos.x+cx,y=pos.y+cy);xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.5)
  assert (home/'DoroOne.launched').exists(), 'Closed pinned icon did not launch through GIO'
  testwindow.show();d.create_resource_object('window',int(testwindow.winId())).set_wm_class('DoroOne','DoroOne');d.sync();wait(.5)
  im=app.primaryScreen().grabWindow(p.id).toImage()
  xs={x for y in range(im.height()) for x in range(im.width()) if im.pixelColor(x,y)==QColor('#01e3c7')}
  assert xs and max(xs)-min(xs)<40, 'Reopened pinned app produced duplicate icons'
  # Reopen, then unregister the disposable icon while its popup is visible.
  xtest.fake_input(d,X.MotionNotify,x=pos.x+g.width-12,y=pos.y+g.height//2);xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.5)
  assert [w for w in windows(panel.pid) if w.get_wm_name()=='Hidden icons']
  bus.release_name('org.kde.StatusNotifierItem.DoroTest');wait(.5)
  assert not [w for w in windows(panel.pid) if w.get_wm_name()=='Hidden icons']
  # Only this isolated panel is restarted; saved pin ordering must survive.
  testwindow.close();second.close();wait(.5)
  panel.terminate();panel.wait(timeout=5)
  panel=subprocess.Popen([args.binary,'--config',str(conf)],env=env,stdout=subprocess.DEVNULL,stderr=open(home/'panel-restart.log','w'))
  wait(2)
  p=next(w for w in windows(panel.pid) if w.get_geometry().width>100 and w.get_geometry().height<100)
  pos=root.translate_coords(p,0,0);g=p.get_geometry()
  assert task_center('#01e3c7')[0]>task_center('#e3c701')[0], 'Pin order did not survive panel restart'
  # Closed-pin scrolling and middle click must not address a nonexistent window.
  cx,cy=task_center('#01e3c7')
  xtest.fake_input(d,X.MotionNotify,x=pos.x+cx,y=pos.y+cy)
  for button in (4,4,4,2):
   xtest.fake_input(d,X.ButtonPress,button);xtest.fake_input(d,X.ButtonRelease,button)
  d.sync();wait(.3)
  assert panel.poll() is None and task_center('#01e3c7'), 'Closed-pin input broke panel'
  xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.3)
  marker=home/'DoroOne.launched';marker.unlink()
  xtest.fake_input(d,X.ButtonPress,3);xtest.fake_input(d,X.ButtonRelease,3);d.sync();wait(.3)
  for name in ('Down','Return'):
   key=d.keysym_to_keycode(XK.string_to_keysym(name));xtest.fake_input(d,X.KeyPress,key);xtest.fake_input(d,X.KeyRelease,key)
  d.sync();wait(.3)
  assert marker.exists(), 'Keyboard did not activate pinned Open context action'

  print('PASS native popup mouse/keyboard/context/Escape; disconnect cleanup; task restore, unified pin launch/reopen, closed-pin input and restart-persistent drag order',flush=True)
 finally:
  testwindow.close();second.close()
  if item is not None:item.remove_from_connection()
  panel.terminate();panel.wait(timeout=5);xtest.fake_input(d,X.MotionNotify,x=pointer.root_x,y=pointer.root_y);d.sync();d.close()
