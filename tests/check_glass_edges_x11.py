"""Private Start first-paint, straight-edge, mask and idle regression check."""
import os, sys, time, json, argparse, subprocess, math
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--run',action='store_true'); parser.add_argument('--worker',action='store_true')
parser.add_argument('--launch',action='store_true'); parser.add_argument('--xvfb',type=Path)
parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
ROOT=Path(os.environ.get('DORO_RENDER_SOURCE', Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'menu'))
from x11_isolation import isolated


def launch():
    import start_menu
    from PySide6.QtCore import QTimer
    start=time.monotonic(); original=start_menu.StartMenu.paintEvent; records=[]
    def paint(menu,event):
        original(menu,event)
        if not records:
            c=menu.wallpaper_glass.controller
            records.append(dict(first_paint_ms=(time.monotonic()-start)*1000, active=c.active))
            QTimer.singleShot(100, menu.close)
    start_menu.StartMenu.paintEvent=paint
    sys.argv=[sys.argv[0]]
    start_menu.main()
    args.output.write_text(json.dumps(records[0]))


def worker():
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    assert Path.home()==Path(os.environ['TMPDIR']).parent
    assert Path.home().parent==Path('/tmp') and Path.home().name.startswith('doroshell-private-display-')
    from PySide6.QtWidgets import QApplication,QLabel
    from PySide6.QtGui import QImage,QPixmap,QColor
    from PySide6.QtCore import Qt,QPoint,QEventLoop,QTimer
    from Xlib import display
    from PIL import Image
    import start_menu
    app=QApplication([]); app.setQuitOnLastWindowClosed(False)
    screen=app.primaryScreen(); dpr=screen.devicePixelRatio()
    d=display.Display(); assert not d.get_selection_owner(d.intern_atom('_NET_WM_CM_S0'))
    def wait(ms):
        loop=QEventLoop(); QTimer.singleShot(ms,loop.quit); loop.exec()
    def until(predicate):
        end=time.monotonic()+5
        while not predicate() and time.monotonic()<end: wait(10)
        assert predicate()
    wall=Path.home()/'wall.png'
    # Deliberately noisy wallpaper and a dark covering window expose raw pixel fringes.
    im=Image.new('RGB',(1024,768)); im.putdata([(255,0,255) if (x+y)%2 else (0,255,0)
        for y in range(768) for x in range(1024)]); im.save(wall)
    cfg=Path.home()/'.config'; pc=cfg/'pcmanfm-qt/lxqt/settings.conf'; pc.parent.mkdir(parents=True)
    original='[Desktop]\nWallpaper='+str(wall)+'\nWallpaperMode=stretch\n'
    pc.write_text(original)
    p=cfg/'doroshell/wallpaper-glass.json'; p.parent.mkdir(); p.write_text('{"version":1,"enabled":true}')
    desktop=QLabel(); desktop.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    desktop.setGeometry(screen.geometry()); desktop.setStyleSheet('background:#111111'); desktop.show(); wait(20)
    out=args.output/str(dpr); out.mkdir(parents=True,exist_ok=True)
    launches=[]
    for i in range(3):
        result=out/('launch-'+str(i)+'.json')
        subprocess.run([sys.executable,__file__,'--launch','--output',str(result)],check=True,timeout=10)
        launches.append(json.loads(result.read_text()))
    menu=start_menu.StartMenu(); menu.resize(min(508,screen.size().width()-30),min(634,screen.size().height()-30)); menu.move(5,5)
    c=menu.wallpaper_glass.controller
    if hasattr(c,'present'): c.present()
    else: menu.show()
    until(lambda:menu.isVisible() and c.active); menu.search.clearFocus(); wait(100)
    image=screen.grabWindow(0).toImage(); image.save(str(out/'glass.png'))
    pos=menu.frame.mapToGlobal(QPoint(0,0)); x=math.floor(pos.x()*dpr+.5); y=math.floor(pos.y()*dpr+.5)
    w=round(menu.frame.width()*dpr); h=round(menu.frame.height()*dpr)
    image.copy(x,y,w,h).save(str(out/'frame.png'))
    # Straight frame bands must never contain the saturated raw source pixels.
    pixels=[]
    for px in range(x+round(25*dpr),x+w-round(25*dpr)):
        pixels.extend([image.pixelColor(px,y),image.pixelColor(px,y+h-1)])
    for py in range(y+round(25*dpr),y+h-round(25*dpr)):
        pixels.extend([image.pixelColor(x,py),image.pixelColor(x+w-1,py)])
    raw=sum(max(c.red(),c.green(),c.blue())-min(c.red(),c.green(),c.blue())>180 for c in pixels)
    # Pixels at the centers of all four bands remain opaque over the dark window.
    for px,py in ((x+w//2,y),(x+w//2,y+h-1),(x,y+h//2),(x+w-1,y+h//2)):
        assert image.pixelColor(px,py)!=QColor('#111111')
    before=c.backdrop.paints; started=time.process_time(); wait(1000)
    idle=dict(paints=c.backdrop.paints-before,cpu_ms=(time.process_time()-started)*1000)
    # A changing background must not leak into the opaque edge or repaint glass.
    frozen=image.pixelColor(x+w//2,y)
    for background in ('#008000','#800080','#111111'):
        desktop.setStyleSheet('background:'+background); wait(30)
        frame=screen.grabWindow(0).toImage()
        assert frame.pixelColor(0,0)==QColor(background)
        assert frame.pixelColor(x+w//2,y)==frozen
    assert c.backdrop.paints==before
    generation=c.generation; mask=menu.mask()
    menu.move(menu.x()+12,menu.y()+3); wait(100)
    geometry_redecode=c.generation!=generation
    assert menu.mask()==mask
    menu.hide(); menu.show(); wait(100); assert c.active
    for mode in ('fit','zoom'):
        pc.write_text(original.replace('stretch',mode)); until(lambda:c.mode=={'fit':'fit','zoom':'crop'}[mode] and not c.busy)
        assert c.active
    c.suspend(); wait(20); assert not c.active and menu.mask()==mask
    result=dict(dpr=dpr,launches=launches,raw_edge_pixels=raw,idle=idle,geometry_redecode=geometry_redecode)
    (out/'results.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result),flush=True)
    c.stop(); menu.close(); desktop.close(); d.close()
    assert all(item['active'] for item in launches), 'Cold first paint was opaque'
    assert raw==0, 'Raw wallpaper leaked onto straight edges'
    assert not geometry_redecode, 'Moving the menu decoded wallpaper again'
    assert idle['paints']==0

if args.launch: launch()
elif args.worker: worker()
elif args.run and args.xvfb:
    isolated(args.xvfb,[sys.executable,__file__,'--worker','--output',str(args.output.resolve())])
else: parser.error('Opt in with --run --xvfb PATH')
