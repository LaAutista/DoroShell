"""Opt-in capture/paste test on a private Xvfb display; never uses the live clipboard."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from x11_isolation import isolated




def paste_office(kind,base):
    import uno
    from com.sun.star.beans import PropertyValue
    from com.sun.star.connection import NoConnectException
    pipe='doro_'+secrets.token_hex(12)
    profile=base/(kind+'-profile')
    proc=subprocess.Popen(['libreoffice','-env:UserInstallation='+profile.as_uri(),'--norestore','--nodefault','--nologo','--invisible','--accept=pipe,name='+pipe+';urp;StarOffice.ComponentContext'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    doc=None
    try:
        local=uno.getComponentContext();resolver=local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',local)
        deadline=time.monotonic()+15
        while True:
            try:ctx=resolver.resolve('uno:pipe,name='+pipe+';urp;StarOffice.ComponentContext');break
            except NoConnectException:
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        sm=ctx.ServiceManager;desktop=sm.createInstanceWithContext('com.sun.star.frame.Desktop',ctx)
        doc=desktop.loadComponentFromURL('private:factory/'+kind,'_blank',0,())
        dispatch=sm.createInstanceWithContext('com.sun.star.frame.DispatchHelper',ctx)
        dispatch.executeDispatch(doc.getCurrentController().getFrame(),'.uno:Paste','',0,())
        time.sleep(.3)
        objects=doc.getGraphicObjects() if kind=='swriter' else doc.getDrawPages().getByIndex(0)
        assert objects.getCount()==1,(kind,objects.getCount())
        graphic=objects.getByIndex(0).Graphic
        assert (graphic.SizePixel.Width,graphic.SizePixel.Height)==(120,90)
        dest=base/(kind+'.png')
        def prop(name,value):
            p=PropertyValue();p.Name=name;p.Value=value;return p
        sm.createInstanceWithContext('com.sun.star.graphic.GraphicProvider',ctx).storeGraphic(graphic,(prop('URL',dest.as_uri()),prop('MimeType','image/png')))
        return dest
    finally:
        if doc:doc.setModified(False);doc.close(True)
        proc.terminate();proc.wait(timeout=5)


def worker():
    assert os.environ.get('DOROSHELL_TEST_DISPLAY')==os.environ.get('DISPLAY') and os.environ['DISPLAY']!=':0','A private display is required'
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage,QColor
    from Xlib import display,X,XK
    from Xlib.ext import xtest
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    d=display.Display();children=[]
    def wait(seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:app.processEvents();time.sleep(.01)
    def event(kind,*args,**kwargs):xtest.fake_input(d,kind,*args,**kwargs);d.sync()
    def key(name):
        code=d.keysym_to_keycode(XK.string_to_keysym(name));event(X.KeyPress,code);event(X.KeyRelease,code);wait(.2)
    try:
        with tempfile.TemporaryDirectory(prefix='doro-capture-paste-') as tmp:
            base=Path(tmp);source=base/'source.png';color=QColor('#5096d2')
            image=QImage(1024,768,QImage.Format.Format_RGB32);image.fill(color);assert image.save(str(source))
            helper=Path(__file__).resolve().parents[1]/'runtime/menu_capture.py'
            def start():
                p=subprocess.Popen([sys.executable,str(helper),'--geometry','0','0','1024','768'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL)
                children.append(p);p.stdin.write(source.read_bytes());p.stdin.close();wait(.6)
                assert p.poll() is None,'Capture helper exited before selection'
                return p
            app.clipboard().setText('isolated clipboard sentinel');wait(.1)
            cancelled=start();key('Escape');cancelled.wait(timeout=3)
            assert app.clipboard().text()=='isolated clipboard sentinel'
            capture=start()
            event(X.MotionNotify,x=100,y=180);event(X.ButtonPress,1)
            event(X.MotionNotify,x=219,y=269);wait(.1);event(X.ButtonRelease,1);key('Return')
            result=app.clipboard().image()
            assert (result.width(),result.height())==(120,90)
            assert result.pixelColor(0,0)==color and result.pixelColor(119,89)==color
            assert capture.poll() is None,'Clipboard owner exited too early'
            cancelled=start();event(X.MotionNotify,x=300,y=200);event(X.ButtonPress,1)
            event(X.MotionNotify,x=400,y=300);key('Escape');event(X.ButtonRelease,1);cancelled.wait(timeout=3)
            assert app.clipboard().image()==result,'Mid-drag cancellation replaced completed clipboard image'
            for kind in ('swriter','sdraw'):
                exported=QImage(str(paste_office(kind,base)))
                assert (exported.width(),exported.height())==(120,90)
                assert all(exported.pixelColor(x,y)==color for x in range(120) for y in range(90)),kind
            app.clipboard().setText('replacement');wait(.4);capture.wait(timeout=3)
            print('PASS private X11: capture → cancellation preserves image → Writer/Draw Paste matches every pixel; owner exits on replacement; personal clipboard never used',flush=True)
    finally:
        for p in children:
            if p.poll() is None:p.terminate();p.wait(timeout=5)
        d.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xvfb',type=Path)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:worker()
    elif args.run and args.xvfb:isolated(args.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else:parser.error('Pass --run --xvfb /path/to/Xvfb to create an isolated test display')
