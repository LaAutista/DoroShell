"""Opt-in Xinerama cross-display screenshot and fractional-scaling check on private X11."""
import os, sys, tempfile, subprocess, time, secrets
from pathlib import Path
import argparse
from x11_isolation import isolated
from Xlib import X, display, XK
from Xlib.ext import xtest

def worker():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage
    assert os.environ['DISPLAY'] == os.environ['DOROSHELL_NESTED_DISPLAY']
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from runtime.menu_capture import fresh_capture, snapshot_desktop
    app=QApplication([])
    d=display.Display(); r=d.screen().root
    panes=[]
    for x,color in [(0,0xff0000),(640,0x0000ff)]:
        w=r.create_window(x,0,640,480,0,d.screen().root_depth,X.InputOutput,X.CopyFromParent,background_pixel=color,override_redirect=True)
        panes.append(w);w.map()
    d.sync(); time.sleep(.2)
    screens=[(s.name(),s.geometry().getRect(),s.devicePixelRatio(),s.grabWindow(0).size().toTuple()) for s in app.screens()]
    print('screens',screens, flush=True)
    heads = d.xinerama_query_screens().screens
    assert len(heads)==2, heads
    print('Xinerama heads', [(h.x,h.y,h.width,h.height) for h in heads],flush=True)
    image, bounds=snapshot_desktop()
    print('snapshot',bounds,image.size(), flush=True)
    for x, color in ((120, '#ff0000'), (800, '#0000ff')):
        r.warp_pointer(x, 200)
        d.sync()
        app.processEvents()
        editor = fresh_capture(True, False)
        actual = editor.rendered_image()
        assert actual.size().toTuple() == (640, 480), actual.size()
        expected = QImage(actual.size(), actual.format())
        expected.fill(color)
        assert actual == expected, (x, editor.geometry(), r.query_pointer().root_x)
    # A 9x5 solid cursor at (641,200), hotspot (4,2), crosses into the left head.
    bits = r.create_pixmap(9, 5, 1)
    bits.fill_rectangle(bits.create_gc(foreground=1), 0, 0, 9, 5)
    cursor = bits.create_cursor(bits, (65535,65535,0), (0,0,0), 4, 2)
    panes[1].change_attributes(cursor=cursor)
    r.warp_pointer(641, 200)
    d.sync()
    editor = fresh_capture(True, True)
    actual = editor.rendered_image()
    for y in range(198, 203):
        for x in range(6):
            expected.setPixelColor(x, y, Qt.GlobalColor.yellow)
    assert actual == expected, 'Pointer on right monitor must clip at its native left boundary'
    with tempfile.TemporaryDirectory() as tmp:
        out=Path(tmp)/'cross.png'
        p=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'runtime/menu_capture.py'),'--output',out])
        try:
            time.sleep(.8)
            xtest.fake_input(d,X.MotionNotify,x=600,y=150);xtest.fake_input(d,X.ButtonPress,1)
            xtest.fake_input(d,X.MotionNotify,x=679,y=209);xtest.fake_input(d,X.ButtonRelease,1)
            code=d.keysym_to_keycode(XK.string_to_keysym('Return'))
            xtest.fake_input(d,X.KeyPress,code);xtest.fake_input(d,X.KeyRelease,code);d.sync()
            assert p.wait(timeout=4)==0
            im=QImage(str(out)); print('selected',im.size(), flush=True)
            assert im.size().toTuple() == (80,60)
            assert im.pixelColor(5,5).name()=='#ff0000' and im.pixelColor(im.width()-5,5).name()=='#0000ff'
        finally:
            if p.poll() is None:p.kill();p.wait()
    print('PASS exact monitor selection, clipped cursor and cross-head region',flush=True)

def nested(xephyr):
    assert os.environ.get('DOROSHELL_TEST_DISPLAY')==os.environ['DISPLAY']
    number=next(n for n in range(221,255) if not Path(f'/tmp/.X11-unix/X{n}').exists() and not Path(f'/tmp/.X{n}-lock').exists())
    screen=f':{number}'
    auth=Path.home()/'nested-auth';auth.touch(mode=0o600)
    subprocess.run(['xauth','-f',str(auth),'add',screen,'MIT-MAGIC-COOKIE-1',secrets.token_hex(16)],check=True)
    env=dict(os.environ,DISPLAY=screen,XAUTHORITY=str(auth),DOROSHELL_NESTED_DISPLAY=screen)
    server=subprocess.Popen([str(xephyr),screen,'-auth',str(auth),'-nolisten','tcp','-extension','RANDR','+xinerama','-screen','640x480+0+0','-screen','640x480+640+0'])
    try:
        time.sleep(1)
        for scale in ('1','1.5'):
            subprocess.run([sys.executable,__file__,'--worker'],env=dict(env,QT_SCALE_FACTOR=scale),check=True)
    finally:
        server.terminate();server.wait(timeout=5)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--xephyr',type=Path)
    parser.add_argument('--xvfb',type=Path)
    parser.add_argument('--nested',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:
        worker()
    elif args.nested and args.xephyr:
        nested(args.xephyr)
    elif args.run and args.xvfb and args.xephyr:
        isolated(args.xvfb.resolve(),[sys.executable,Path(__file__).resolve(),'--nested','--xephyr',args.xephyr.resolve()])
    else:
        parser.error('Pass --run --xvfb /path/to/Xvfb --xephyr /path/to/Xephyr')
