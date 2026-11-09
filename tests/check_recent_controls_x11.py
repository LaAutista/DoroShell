"""Verify recent-count menu clicks and persistence on an isolated X11 display."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import time
from x11_isolation import isolated


def worker():
    assert os.environ.get('DOROSHELL_TEST_DISPLAY') == os.environ.get('DISPLAY')
    assert os.environ['DISPLAY'] != ':0'
    from PySide6.QtCore import QTimer
    from Xlib import display, X
    from Xlib.ext import xtest
    spec = importlib.util.spec_from_file_location('menu', Path(__file__).resolve().parents[1] / 'menu/start_menu.py')
    menu = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(menu)
    app = menu.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    connection = display.Display()

    def wait(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.01)

    def click_at(point):
        xtest.fake_input(connection, X.MotionNotify, x=point.x(), y=point.y())
        xtest.fake_input(connection, X.ButtonPress, 1)
        xtest.fake_input(connection, X.ButtonRelease, 1)
        connection.sync()

    window = menu.StartMenu()
    try:
        for i in range(12):
            window.recent.save(launched=f'fixture-{i}.desktop')
        window.show()
        wait(.3)
        options = next(b for b in window.findChildren(menu.QPushButton) if b.text() == 'Menu options…')
        popup = options.menu()
        submenu = next(a.menu() for a in popup.actions() if a.text() == 'Recent program count')
        submenu_action = next(a for a in popup.actions() if a.menu() == submenu)
        choice = next(a for a in submenu.actions() if a.data() == 5)
        # QMenu runs a nested loop: drive all three clicks with timers.
        QTimer.singleShot(180, lambda: click_at(popup.mapToGlobal(popup.actionGeometry(submenu_action).center())))
        QTimer.singleShot(500, lambda: click_at(submenu.mapToGlobal(submenu.actionGeometry(choice).center())))
        QTimer.singleShot(2000, popup.close)
        click_at(options.mapToGlobal(options.rect().center()))
        wait(2.2)
        assert window.recent.value['limit'] == 5
        assert len(window.recent.value['items']) == 5
        window.close()
        reopened = menu.StartMenu()
        assert reopened.recent.value['limit'] == 5
        assert next(a for a in reopened.recent_counts.actions() if a.isChecked()).data() == 5
        reopened.close()
        print('PASS private X11: pointer-selected recent count, immediate trim, persisted value and reopened checkmark; personal settings unchanged', flush=True)
    finally:
        window.close()
        connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--xvfb', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker()
    elif args.run and args.xvfb:
        isolated(args.xvfb.resolve(), [sys.executable, str(Path(__file__).resolve()), '--worker'])
    else:
        parser.error('Pass --run --xvfb /path/to/Xvfb')
