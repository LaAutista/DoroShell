"""Opt-in real pointer check for Start pins; synthetic apps and temporary settings."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
import shiboken6
from Xlib import display, X, XK
from Xlib.ext import xtest
from PySide6.QtCore import QTimer, QPoint

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run',action='store_true')
if not parser.parse_args().run:parser.error('Pass --run to move the pointer over a disposable Start menu')
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('menu',root/'menu/start_menu.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
app=m.QApplication([])
d=display.Display();pointer=d.screen().root.query_pointer()
def wait(seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        app.processEvents();time.sleep(.01)
def input_event(kind,*args,**kwargs):
    xtest.fake_input(d,kind,*args,**kwargs);d.sync()
def drag(window,source,target,cancel=False):
    view=window.list
    start=view.viewport().mapToGlobal(view.visualItemRect(view.item(source)).center())
    rect=view.visualItemRect(view.item(target))
    end=view.viewport().mapToGlobal(rect.bottomLeft()+QPoint(rect.width()//2,-2))
    input_event(X.MotionNotify,x=start.x(),y=start.y())
    input_event(X.ButtonPress,1)
    for step in range(1,16):
        x=round(start.x()+(end.x()-start.x())*step/15)
        y=round(start.y()+(end.y()-start.y())*step/15)
        QTimer.singleShot(step*40,lambda x=x,y=y:input_event(X.MotionNotify,x=x,y=y))
    if cancel:
        key=d.keysym_to_keycode(XK.string_to_keysym('Escape'))
        QTimer.singleShot(650,lambda:input_event(X.KeyPress,key))
        QTimer.singleShot(670,lambda:input_event(X.KeyRelease,key))
    QTimer.singleShot(750,lambda:input_event(X.ButtonRelease,1))
    wait(1.1)
try:
    with tempfile.TemporaryDirectory(prefix='doroshell-start-drag-') as tmp, patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp}):
        directory=Path(tmp);apps=[]
        marker=directory/'unexpected-launch'
        for name in ('Alpha','Beta','Gamma'):
            path=directory/(name+'.desktop')
            path.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec=/usr/bin/touch '+str(marker)+'\nIcon=application-x-executable\n')
            apps.append(m.Gio.DesktopAppInfo.new_from_filename(str(path)))
        ids=[entry.get_id() for entry in apps]
        state=directory/'lxqt-comfort/favorites.json';state.parent.mkdir();state.write_text(json.dumps(ids))
        with patch.object(m,'applications',return_value=apps):
            window=m.StartMenu();window.move(80,80);window.show();wait(.3)
            drag(window,0,2)
            expected=[ids[1],ids[2],ids[0]]
            assert json.loads(state.read_text())==expected,'Pointer drag did not persist pin order'
            assert window.isVisible() and not marker.exists(),'Drag launched an application or closed menu'
            drag(window,0,2,cancel=True)
            assert json.loads(state.read_text())==expected,'Escape changed pin order'
            assert not marker.exists(),'Cancel/release launched an application'
            window.show();wait(.2)
            point=window.list.viewport().mapToGlobal(window.list.visualItemRect(window.list.item(2)).center())
            input_event(X.MotionNotify,x=point.x(),y=point.y())
            input_event(X.ButtonPress,3);input_event(X.ButtonRelease,3)
            for delay,name in ((150,'Down'),(220,'Down'),(300,'Return')):
                key=d.keysym_to_keycode(XK.string_to_keysym(name))
                QTimer.singleShot(delay,lambda key=key:input_event(X.KeyPress,key))
                QTimer.singleShot(delay+15,lambda key=key:input_event(X.KeyRelease,key))
            wait(.6)
            expected=[ids[1],ids[0],ids[2]]
            assert json.loads(state.read_text())==expected,'Keyboard Move pin up failed'
            assert not marker.exists(),'Move command launched an application'

            window.close();shiboken6.delete(window)
            restored=m.StartMenu()
            assert restored.favorites==expected,'Pin order did not survive reopening Start'
            restored.close();shiboken6.delete(restored)
        print('PASS: real Start pin drag, Escape cancellation, keyboard move, no accidental launch, persisted reopen order',flush=True)
finally:
    input_event(X.ButtonRelease,1)
    input_event(X.MotionNotify,x=pointer.root_x,y=pointer.root_y)
    d.close()
