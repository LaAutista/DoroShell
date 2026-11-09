"""Exercise categorized settings with real input and temporary-home apply/restore."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
from x11_isolation import isolated


def worker():
    assert os.environ.get('DOROSHELL_TEST_DISPLAY')==os.environ.get('DISPLAY') and os.environ['DISPLAY']!=':0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import settings
    import shiboken6
    from Xlib import display,X,XK
    from Xlib.ext import xtest
    app=settings.QApplication([]);d=display.Display()
    def wait(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:app.processEvents();time.sleep(.01)
    def click(widget,point=None):
        p=widget.mapToGlobal(point or widget.rect().center())
        xtest.fake_input(d,X.MotionNotify,x=p.x(),y=p.y());xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.15)
    def key(name):
        code=d.keysym_to_keycode(XK.string_to_keysym(name))
        xtest.fake_input(d,X.KeyPress,code);xtest.fake_input(d,X.KeyRelease,code);d.sync();wait(.1)
    def finished(window):
        deadline=time.monotonic()+15
        while window.process is not None:
            if time.monotonic()>deadline:raise RuntimeError('Settings subprocess did not finish')
            wait(.05)
        assert 'Stopped.' not in window.output.toPlainText(),window.output.toPlainText()
    with tempfile.TemporaryDirectory(prefix='doro-settings-fixture-') as tmp:
        home=Path(tmp);mime=home/'.config/mimeapps.list';mime.parent.mkdir()
        original='[Default Applications]\ntext/plain=original.desktop;\ninode/directory=original-files.desktop;\n';mime.write_text(original)
        manifest=home/'.local/state/doroshell/kate.json'
        window=settings.Settings(home);window.show();wait(.3)
        try:
            assert window.commands(True)==[]
            rect=window.categories.visualItemRect(window.categories.item(3))
            click(window.categories.viewport(),rect.center())
            assert window.pages.currentIndex()==3
            choice=window.choices['kate'];click(choice);key('Down');key('Return')
            assert choice.currentData()=='enable'
            assert window.selection_summary.text()=='1 selected change across all pages'
            click(window.preview);finished(window)
            assert not manifest.exists() and mime.read_text()==original,'Preview changed settings'
            click(window.apply);finished(window)
            assert manifest.exists() and 'text/plain=org.kde.kate.desktop;' in mime.read_text()
            # Navigate away and back with actual keyboard input; the selected operation remains visible.
            click(window.categories.viewport(),rect.center())
            for _ in range(3):key('Up')
            assert window.pages.currentIndex()==0
            for _ in range(3):key('Down')
            assert window.pages.currentIndex()==3 and choice.currentData()=='enable'
            click(choice);key('End');key('Return')
            assert choice.currentData()=='restore'
            click(window.apply);finished(window)
            assert not manifest.exists() and mime.read_text()==original,'Restore did not preserve original associations'
            print('PASS private X11: category mouse/keyboard navigation, selection persistence, preview no-op, real temporary-home apply and exact restore',flush=True)
        finally:
            window.close();app.processEvents();shiboken6.delete(window);d.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xvfb',type=Path)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:worker()
    elif args.run and args.xvfb:isolated(args.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else:parser.error('Pass --run --xvfb /path/to/Xvfb')
