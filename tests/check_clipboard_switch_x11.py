"""Opt-in clipboard regression with real Kate/Firefox on a disposable X11 desktop."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker():
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    assert Path.home()==Path(os.environ['TMPDIR']).parent
    assert Path.home().name.startswith('doroshell-private-display-')
    from PySide6.QtWidgets import QApplication
    from Xlib import display,X,XK
    from Xlib.ext import xtest
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    d=display.Display();root=d.screen().root
    base=Path.home();text='Doro clipboard fixture 0123456789\nSecond line: café — copied safely.'
    doc=base/'fixture.txt';doc.write_text(text)
    page=base/'paste.html';page.write_text('<html><body style="margin:0"><textarea autofocus style="width:100vw;height:90vh">empty</textarea></body></html>')
    profile=base/'firefox-profile';profile.mkdir();(profile/'user.js').write_text('user_pref("browser.shell.checkDefaultBrowser", false);\nuser_pref("browser.startup.homepage_override.mstone", "ignore");\nuser_pref("datareporting.policy.dataSubmissionEnabled", false);\n')
    children=[];log=open(base/'clipboard-native.log','w')
    def wait(t):
        end=time.monotonic()+t
        while time.monotonic()<end:app.processEvents();time.sleep(.01)
    def key(name,ctrl=False):
        control=d.keysym_to_keycode(XK.string_to_keysym('Control_L'));code=d.keysym_to_keycode(XK.string_to_keysym(name))
        if ctrl:xtest.fake_input(d,X.KeyPress,control)
        xtest.fake_input(d,X.KeyPress,code);xtest.fake_input(d,X.KeyRelease,code)
        if ctrl:xtest.fake_input(d,X.KeyRelease,control)
        d.sync();wait(.15)
    def windows(klass):
        p=root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
        return [d.create_resource_object('window',int(w)) for w in p.value if klass.lower() in str(d.create_resource_object('window',int(w)).get_wm_class()).lower()] if p else []
    def focus(w):
        w.configure(stack_mode=X.Above);w.set_input_focus(X.RevertToParent,X.CurrentTime);d.sync();wait(.2)
    try:
        children.append(subprocess.Popen(['openbox','--sm-disable'],stdout=log,stderr=log));wait(.4)
        children.append(subprocess.Popen(['kate','--new','--startanon',str(doc)],stdout=log,stderr=log))
        children.append(subprocess.Popen(['firefox','--no-remote','--profile',str(profile),page.as_uri()],stdout=log,stderr=log))
        end=time.monotonic()+25
        while not (windows('kate') and windows('firefox')) and time.monotonic()<end:wait(.2)
        assert windows('kate') and windows('firefox'),'Fixture windows missing'
        kate=windows('kate')[0];firefox=windows('firefox')[0];wait(3)
        for i in range(12):
            focus(kate);key('a',True);key('c',True)
            assert app.clipboard().text().rstrip('\n')==text,('Kate copy',i)
            if i%2:
                menu=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'menu/start_menu.py')],stdout=log,stderr=log);children.append(menu);wait(.5);key('Escape');menu.wait(timeout=3)
            focus(firefox)
            # Use the browser address field, whose selection can be copied back without navigating.
            key('l',True);key('v',True);key('a',True);key('c',True)
            assert app.clipboard().text()==' '.join(text.splitlines()),('Firefox paste/copy',i,repr(app.clipboard().text()))
            focus(kate);key('c',True)
            focus(firefox)
            position=root.translate_coords(firefox,0,0);geometry=firefox.get_geometry()
            xtest.fake_input(d,X.MotionNotify,x=position.x+geometry.width//2,y=position.y+geometry.height//2)
            xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.2)
            key('a',True);key('v',True);key('a',True);key('c',True)
            assert app.clipboard().text().rstrip('\n')==text,('Firefox textarea paste/copy',i)
            # Re-copy in Kate and change PRIMARY by selecting Firefox text without copying it.
            focus(kate);key('c',True);assert app.clipboard().text().rstrip('\n')==text
            focus(firefox);key('l',True);key('a',True)
            assert app.clipboard().text().rstrip('\n')==text,('Focus/PRIMARY lost clipboard',i)
        print('PASS 12 real Kate/Firefox address-field and textarea copy-paste round trips, focus/PRIMARY changes and six Start open/close cycles; no clipboard manager',flush=True)
    finally:
        for p in reversed(children):
            if p.poll() is None:p.terminate();p.wait(timeout=8)
        log.close();d.close()

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--xvfb',type=Path)
    args=parser.parse_args()
    if args.worker:worker()
    elif args.run and args.xvfb:
        isolated(args.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else:parser.error('Pass --run --xvfb /path/to/Xvfb for an isolated desktop')
