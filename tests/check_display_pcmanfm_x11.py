"""Inspect the actual private PCManFM candidate Advanced tab, read-only on Xvfb."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary, screenshot):
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY'] and os.environ['DISPLAY']!=':0'
    from PySide6.QtWidgets import QApplication
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    app=QApplication([]);server=display.Display();root=server.screen().root
    # Private D-Bus + home prevent finding an existing personal PCManFM instance.
    process=subprocess.Popen([str(binary),'--desktop-pref','--profile=display-test'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+10;window=None
        while time.monotonic()<deadline:
            app.processEvents()
            for w in root.query_tree().children:
                if w.get_wm_name()=='Desktop Preferences':window=w;break
            if window:break
            if process.poll() is not None:raise RuntimeError(process.stderr.read().decode())
            time.sleep(.05)
        assert window,'Preferences window did not appear'
        # Focus then traverse tabs with the native keyboard shortcut.
        window.set_input_focus(X.RevertToParent,X.CurrentTime);server.sync()
        def key(name, pressed):xtest.fake_input(server,X.KeyPress if pressed else X.KeyRelease,server.keysym_to_keycode(XK.string_to_keysym(name)))
        for _ in range(3):
            key('Control_L',True);key('Tab',True);key('Tab',False);key('Control_L',False);server.sync();time.sleep(.15)
        scale=float(os.environ.get('QT_SCALE_FACTOR','1'))
        window.configure(width=min(round(520*scale),server.screen().width_in_pixels-30),
                         height=min(round(680*scale),server.screen().height_in_pixels-40))
        server.sync();time.sleep(1);app.processEvents()
        app.primaryScreen().grabWindow(window.id).save(str(screenshot))
        geometry=window.get_geometry()
        xtest.fake_input(server,X.MotionNotify,x=geometry.x+geometry.width//2,y=geometry.y+geometry.height//2)
        for _ in range(15):
            xtest.fake_input(server,X.ButtonPress,5);xtest.fake_input(server,X.ButtonRelease,5)
        server.sync();time.sleep(.3);app.processEvents()
        app.primaryScreen().grabWindow(window.id).save(str(screenshot.with_stem(screenshot.stem+'-scrolled')))
        print('PASS actual PCManFM candidate: private Preferences opened, Advanced selected, screenshot captured; no Apply used')
    finally:
        process.terminate();process.wait(timeout=5);server.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--screenshot',type=Path,required=True);a=p.parse_args()
    if a.worker:worker(a.binary.resolve(),a.screenshot.resolve())
    elif a.run and a.xvfb:isolated(a.xvfb.resolve(),[sys.executable,__file__,'--worker','--binary',str(a.binary.resolve()),'--screenshot',str(a.screenshot.resolve())])
    else:p.error('Pass --run --xvfb PATH --binary CANDIDATE --screenshot PRIVATE_PATH')
