"""Private no-compositor rounded-edge geometry, fallback and idle acceptance."""
import os,sys,time,json,argparse
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');parser.add_argument('--worker',action='store_true');parser.add_argument('--xvfb',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
BASE=args.output.resolve();BASE.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'menu'))
from x11_isolation import isolated

def worker():
 assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
 assert Path.home()==Path(os.environ['TMPDIR']).parent
 assert Path.home().parent==Path('/tmp') and Path.home().name.startswith('doroshell-private-display-')
 from PySide6.QtWidgets import QApplication,QLabel
 from PySide6.QtGui import QImage,QPixmap
 from PySide6.QtCore import Qt,QPoint,QEventLoop,QTimer
 from Xlib import display
 app=QApplication([]);screen=app.primaryScreen();dpr=screen.devicePixelRatio();sz=screen.size()
 d=display.Display();assert not d.get_selection_owner(d.intern_atom('_NET_WM_CM_S0'))
 def wait(ms):
  loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
 wall=Path.home()/'synthetic-wallpaper.png'
 from PySide6.QtGui import QPainter,QColor,QLinearGradient
 source=QImage(1024,768,QImage.Format.Format_RGB32);painter=QPainter(source);gradient=QLinearGradient(0,0,1024,768);gradient.setColorAt(0,QColor('#204060'));gradient.setColorAt(1,QColor('#ed80ba'));painter.fillRect(source.rect(),gradient);painter.end();source.save(str(wall))
 cfg=Path.home()/'.config';p=cfg/'pcmanfm-qt/lxqt/settings.conf';p.parent.mkdir(parents=True);p.write_text('[Desktop]\nWallpaper='+str(wall)+'\nWallpaperMode=stretch\n')
 p=cfg/'doroshell/wallpaper-glass.json';p.parent.mkdir();p.write_text('{"version":1,"enabled":true}')
 desktop=QLabel();desktop.setWindowFlags(Qt.WindowType.FramelessWindowHint);desktop.setGeometry(screen.geometry())
 img=QImage(str(wall)).scaled(round(sz.width()*dpr),round(sz.height()*dpr),Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation);img.setDevicePixelRatio(dpr);desktop.setPixmap(QPixmap.fromImage(img));desktop.show()
 import start_menu
 menu=start_menu.StartMenu();menu.resize(min(508,screen.size().width()-30),min(634,screen.size().height()-30));menu.move(5,5);menu.show()
 deadline=time.monotonic()+5
 while not menu.wallpaper_glass.controller.active and time.monotonic()<deadline:wait(20)
 c=menu.wallpaper_glass.controller;assert c.active;assert c.atlas.edge_tiles, "Edge fallback unexpectedly selected"
 menu.search.clearFocus();wait(100)
 out=BASE/('evidence-'+str(dpr));out.mkdir(exist_ok=True)
 pos=menu.frame.mapToGlobal(QPoint(0,0));w=menu.frame.width();x=round((pos.x()+w-22)*dpr);y=round(pos.y()*dpr)
 for variant in ('smooth','baseline'):
  if variant=='baseline':c.edge.hide()
  wait(100);image=screen.grabWindow(0).toImage();image.save(str(out/(variant+'.png')))
  image.copy(x-2,y-2,round(26*dpr),round(26*dpr)).scaled(416,416).save(str(out/(variant+'-corner.png')))
 c.edge.show();wait(100);n=c.edge.paints;start=time.process_time();wait(1000)
 print(json.dumps(dict(dpr=dpr,edge_idle_paints=c.edge.paints-n,idle_cpu_ms=(time.process_time()-start)*1000,raw_bytes=sum(tile.sizeInBytes() for _,_,tile in c.atlas.edge_tiles))),flush=True)
 mask=menu.mask();menu.move(menu.x()+12,menu.y()+3);deadline=time.monotonic()+5
 while time.monotonic()<deadline:
  wait(20);point=menu.frame.mapToGlobal(QPoint(0,0))-screen.geometry().topLeft()
  if c.edge.isVisible() and c.atlas.edge_geometry[:2]==(round(point.x()*dpr),round(point.y()*dpr)):break
 assert c.atlas.edge_geometry[:2]==(round(point.x()*dpr),round(point.y()*dpr))
 assert menu.mask()==mask
 c.suspend();wait(50);assert not c.edge.isVisible() and not c.active and menu.mask()==mask
 print('PASS geometry refresh, unchanged input/bounding mask, disabled opaque fallback',flush=True)
 menu.close();desktop.close()
if __name__=='__main__':
 if args.worker:worker()
 elif args.run and args.xvfb:isolated(args.xvfb,[sys.executable,__file__,'--worker','--output',str(BASE)])
 else:parser.error('Opt in with --run --xvfb PATH')
