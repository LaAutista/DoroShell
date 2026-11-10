"""Open the actual printer manager through Start on a disposable X11 desktop."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker():
    assert Path.home() == Path(os.environ['TMPDIR']).parent
    assert os.environ['DISPLAY'] == os.environ['DOROSHELL_TEST_DISPLAY'] != ':0'
    from PySide6.QtWidgets import QApplication, QPushButton
    from Xlib import display, X
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from menu.start_menu import StartMenu
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    wm = subprocess.Popen(['openbox', '--sm-disable'])
    d = display.Display()
    root = d.screen().root
    menu = StartMenu()
    menu.error = lambda message: (_ for _ in ()).throw(AssertionError(message))
    menu.show()
    button = next(b for b in menu.findChildren(QPushButton, 'folderLink') if b.text() == 'Printers')
    button.click()
    end = time.monotonic() + 15
    found = None
    while time.monotonic() < end:
        app.processEvents()
        clients = root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'), X.AnyPropertyType)
        for wid in clients.value if clients else []:
            window = d.create_resource_object('window', int(wid))
            if 'kcmshell6' in (window.get_wm_class() or ()):
                found = window
                break
        if found:
            break
        time.sleep(.1)
    try:
        assert found, 'Printer management window did not appear'
        time.sleep(2)
        app.processEvents()
        app.primaryScreen().grabWindow(found.id).save('/tmp/doro-printers-private.png')
        print('PASS Start opened real printer management:', found.get_wm_name(), flush=True)
    finally:
        # Only the isolated fixture process and its private bus are torn down.
        if found:
            pid = found.get_full_property(d.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
            if pid:
                os.kill(int(pid.value[0]), 15)
        menu.close()
        wm.terminate()
        wm.wait(timeout=5)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', action='store_true')
    p.add_argument('--worker', action='store_true')
    p.add_argument('--xvfb', type=Path)
    args = p.parse_args()
    if args.worker:
        worker()
    elif args.run and args.xvfb:
        isolated(args.xvfb, [sys.executable, str(Path(__file__).resolve()), '--worker'])
    else:
        p.error('Opt in with --run --xvfb PATH')
