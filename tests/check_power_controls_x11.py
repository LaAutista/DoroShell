"""Exercise split power controls on private X11; all session dispatch is mocked."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import Mock,patch
from x11_isolation import isolated


def worker():
    assert os.environ.get('DOROSHELL_TEST_DISPLAY')==os.environ.get('DISPLAY') and os.environ['DISPLAY']!=':0'
    import shiboken6
    from PySide6.QtCore import QTimer
    from Xlib import display,X,XK
    from Xlib.ext import xtest
    spec=importlib.util.spec_from_file_location('menu',Path(__file__).resolve().parents[1]/'menu/start_menu.py')
    menu=importlib.util.module_from_spec(spec);spec.loader.exec_module(menu)
    app=menu.QApplication([]);app.setQuitOnLastWindowClosed(False);d=display.Display()
    def wait(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:app.processEvents();time.sleep(.01)
    def key(name):
        code=d.keysym_to_keycode(XK.string_to_keysym(name))
        xtest.fake_input(d,X.KeyPress,code);xtest.fake_input(d,X.KeyRelease,code);d.sync()
    def click(widget):
        point=widget.mapToGlobal(widget.rect().center())
        xtest.fake_input(d,X.MotionNotify,x=point.x(),y=point.y());xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.8)
    with tempfile.TemporaryDirectory(prefix='doro-power-controls-') as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp,'XDG_DATA_HOME':tmp}):
        window=menu.StartMenu();window.exit_on_hide=True;window.move(40,40);window.show();wait(.3)
        fixture=Mock();fixture.launch.return_value=True;default_cancel=[]
        try:
            # Replacing GIO lookup prevents every route, including lock, from reaching the real session.
            with patch.object(menu.Gio.DesktopAppInfo,'new',return_value=fixture) as lookup, patch.object(app,'quit') as quit_app:
                def cancel():
                    dialog=app.activeModalWidget()
                    default_cancel.append(isinstance(dialog,menu.QMessageBox) and dialog.defaultButton()==dialog.button(menu.QMessageBox.StandardButton.Cancel))
                    key('Escape')
                QTimer.singleShot(300,cancel);click(window.session_button)
                assert default_cancel==[True] and window.isVisible()
                fixture.launch.assert_not_called();quit_app.assert_not_called()
                # Open the adjacent menu, choose Log out with keyboard, then cancel its dialog.
                QTimer.singleShot(180,lambda:key('Down'))
                QTimer.singleShot(260,lambda:key('Down'))
                QTimer.singleShot(340,lambda:key('Return'))
                QTimer.singleShot(500,cancel)
                click(window.power_arrow)
                assert default_cancel==[True,True] and window.isVisible()
                lookup.assert_called_with('lxqt-logout.desktop');fixture.launch.assert_not_called();quit_app.assert_not_called()
                # Confirm a primary-button action against the fake dispatcher only.
                QTimer.singleShot(250,lambda:key('Left'))
                QTimer.singleShot(350,lambda:key('Return'))
                click(window.session_button)
                fixture.launch.assert_called_once_with([],None);quit_app.assert_called_once()
                lookup.assert_called_with('lxqt-shutdown.desktop')
                assert not window.isVisible() and not window.recent.path.exists()
                print('PASS private X11: split arrow keyboard menu, Cancel-default dialogs, Escape cancellation, confirmed fake dispatch; no real power/session action',flush=True)
        finally:window.close();shiboken6.delete(window);d.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');parser.add_argument('--xvfb',type=Path);parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:worker()
    elif args.run and args.xvfb:isolated(args.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else:parser.error('Pass --run --xvfb /path/to/Xvfb')
