"""Opt-in open-menu Print capture check; writes temporary PNGs, never clipboard."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import time
from unittest.mock import patch
import shiboken6
from Xlib import display,X,XK
from Xlib.ext import xtest
from PySide6.QtGui import QImage

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true')
if not parser.parse_args().run:parser.error('Pass --run for disposable windows and real Print input')
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('menu',root/'menu/start_menu.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
app=m.QApplication([]);app.setQuitOnLastWindowClosed(False)
d=display.Display();xroot=d.screen().root;pointer=xroot.query_pointer()
def wait(seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.01)
def event(kind,*args,**kwargs):xtest.fake_input(d,kind,*args,**kwargs);d.sync()
def key(name):
    code=d.keysym_to_keycode(XK.string_to_keysym(name));event(X.KeyPress,code);event(X.KeyRelease,code)
def clipboard_digest():
    mime=app.clipboard().mimeData()
    return hashlib.sha256(b''.join(name.encode()+bytes(mime.data(name)) for name in sorted(mime.formats()) if name not in ('TIMESTAMP','TARGETS','SAVE_TARGETS'))).hexdigest() if mime else None
before_clipboard=clipboard_digest();children=[];real_popen=subprocess.Popen
try:
    with tempfile.TemporaryDirectory(prefix='doroshell-menu-capture-') as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp,'XDG_DATA_HOME':tmp}):
        base=Path(tmp);marker=base/'unexpected-app-launch'
        desktop=base/'test.desktop';desktop.write_text('[Desktop Entry]\nType=Application\nName=Disposable menu application\nExec=/usr/bin/touch '+str(marker)+'\n')
        fixture=m.Gio.DesktopAppInfo.new_from_filename(str(desktop))
        for cancel in (True,False):
            output=base/('cancel.png' if cancel else 'capture.png')
            def spawn(command,**kwargs):
                kwargs['stderr']=open(base/('cancel.log' if cancel else 'capture.log'),'w')
                child=real_popen(command+['--output',str(output)],**kwargs);children.append(child);return child
            with patch.object(m,'applications',return_value=[fixture]),patch.object(m.subprocess,'Popen',side_effect=spawn):
                window=m.StartMenu();window.move(80,80);window.show();wait(.4)
                expected=window.grab().toImage();geometry=window.frameGeometry();count=len(children)
                key('Print');wait(.8)
                assert len(children)==count+1,'Print was not handled by the open menu'
                assert not window.isVisible(),'Original popup was not released for region selection'
                if cancel:
                    key('Escape');wait(.4)
                    assert not output.exists(),'Cancellation published an image'
                else:
                    event(X.MotionNotify,x=geometry.x(),y=geometry.y());event(X.ButtonPress,1)
                    for step in range(1,16):
                        event(X.MotionNotify,x=geometry.x()+round((geometry.width()-1)*step/15),y=geometry.y()+round((geometry.height()-1)*step/15));wait(.025)
                    event(X.ButtonRelease,1);wait(.2)
                    assert not output.exists(),'Region copied before confirmation'
                    key('Return');wait(.5)
                    captured=QImage(str(output));assert not captured.isNull(),'Confirmed capture was not saved'
                    assert captured.size()==expected.size(),('Unexpected crop size',captured.size(),expected.size())
                    for x,y in ((30,100),(300,300),(500,300)):
                        assert captured.pixelColor(x,y)==expected.pixelColor(x,y),('Open menu pixels missing',x,y)
                assert children[-1].wait(timeout=3)==0
                assert not marker.exists(),'Capture launched the selected application'
                window.close();shiboken6.delete(window)
        assert clipboard_digest()==before_clipboard,'Clipboard changed during file-sink tests'
        print('PASS real Print with open Start: frozen menu pixels, confirmed selection, Escape cancellation, no app launch; clipboard unchanged',flush=True)
finally:
    for child in children:
        if child.poll() is None:child.terminate();child.wait(timeout=3)
    event(X.ButtonRelease,1);event(X.MotionNotify,x=pointer.root_x,y=pointer.root_y);d.close()
