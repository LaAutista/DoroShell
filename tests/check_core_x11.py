"""Exercise the core setup, installed snap helper and native panel on private X11."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

from x11_isolation import isolated

ROOT = Path(__file__).resolve().parents[1]


def worker(binary):
    if os.environ.get('DOROSHELL_TEST_DISPLAY') != os.environ['DISPLAY'] or Path.home() != Path(os.environ['TMPDIR']).parent:
        raise RuntimeError('A private test home and display are required')
    home = Path.home()
    rc = home/'.config/openbox/rc.xml'
    rc.parent.mkdir(parents=True)
    rc.write_text('<openbox_config xmlns="http://openbox.org/3.4/rc"><keyboard>\n</keyboard></openbox_config>')
    panel = home/'.config/lxqt/panel.conf'
    panel.parent.mkdir(parents=True)
    panel.write_text('[panel1]\nplugins=fancymenu, taskbar, statusnotifier, worldclock\n')
    shortcuts = panel.with_name('globalkeyshortcuts.conf')
    shortcuts.write_text('[Print.1]\nComment=Previous Print binding\nExec=screengrab\nEnabled=true\n')
    daemon = subprocess.Popen(['/usr/bin/lxqt-globalkeysd'])
    try:
        from gi.repository import Gio
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.DO_NOT_AUTO_START, None,
                                      'org.lxqt.global_key_shortcuts', '/daemon',
                                      'org.lxqt.global_key_shortcuts.daemon', None)
        for attempt in range(50):
            if proxy.get_name_owner():
                break
            if daemon.poll() is not None:
                raise RuntimeError('Private shortcut daemon exited')
            from gi.repository import GLib
            GLib.MainContext.default().iteration(False)
            time.sleep(.05)
        assert proxy.get_name_owner()
        exercise(home, rc, panel, shortcuts, binary)
    finally:
        daemon.terminate()
        daemon.wait(timeout=5)


def exercise(home, rc, panel, shortcuts, binary):
    from PySide6.QtWidgets import QApplication, QWidget
    from Xlib import display, X, XK
    from Xlib.ext import xtest
    originals = {path: path.read_bytes() for path in (rc, panel, shortcuts)}
    setup = [sys.executable, ROOT/'setup.py', 'menu', 'snapping', 'screenshots']
    for action in ([], ['--apply'], ['--apply']):
        subprocess.run(setup + action, check=True)
    prepared = home/'prepared'
    switch = [sys.executable, ROOT/'panel/profile.py']
    subprocess.run(switch + ['prepare', '--prepared', prepared, '--binary', binary], check=True)
    native_setup = [sys.executable, ROOT/'setup.py', 'native-panel', '--prepared', prepared]
    subprocess.run(native_setup, check=True)
    assert not (home/'.config/autostart/lxqt-panel.desktop').exists()
    subprocess.run(native_setup + ['--apply'], check=True)
    assert panel.read_bytes() == originals[panel]

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    def wait(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.01)

    wm = subprocess.Popen(['openbox', '--sm-disable', '--config-file', rc])
    helper = None
    try:
        wait(.6)
        window = QWidget()
        window.setStyleSheet("background-color: #5096d2;")
        window.setGeometry(160, 120, 260, 170)
        window.show()
        window.activateWindow()
        wait(.4)
        before = window.frameGeometry().getRect()
        helper = subprocess.Popen([home/'.local/bin/doroshell-snap'])
        wait(.4)
        assert helper.poll() is None
        d = display.Display()
        try:
            super_key = d.keysym_to_keycode(XK.string_to_keysym('Super_L'))
            screen = app.primaryScreen().geometry()
            for key, expected in [('Left', (0, 0, screen.width()//2, screen.height())),
                                  ('Right', (screen.width()//2, 0, screen.width()-screen.width()//2, screen.height())),
                                  ('Down', before)]:
                code = d.keysym_to_keycode(XK.string_to_keysym(key))
                for kind, button in [(X.KeyPress, super_key), (X.KeyPress, code), (X.KeyRelease, code), (X.KeyRelease, super_key)]:
                    xtest.fake_input(d, kind, button)
                d.sync()
                wait(.5)
                actual = window.frameGeometry().getRect()
                assert actual == expected, (key, actual, expected)
            def press(key):
                code = d.keysym_to_keycode(XK.string_to_keysym(key))
                xtest.fake_input(d, X.KeyPress, code)
                xtest.fake_input(d, X.KeyRelease, code)
                d.sync()
            app.clipboard().setText('before capture')
            press('Print')
            wait(1.3)
            press('Escape')
            wait(.4)
            assert app.clipboard().text() == 'before capture'
            press('Print')
            wait(1.3)
            start = window.mapToGlobal(window.rect().topLeft())
            for kind, x, y in [(X.MotionNotify, 15, 15), (X.ButtonPress, 15, 15),
                               (X.MotionNotify, 135, 105), (X.ButtonRelease, 135, 105)]:
                if kind == X.MotionNotify:
                    xtest.fake_input(d, kind, x=start.x()+x, y=start.y()+y)
                else:
                    xtest.fake_input(d, kind, 1)
                d.sync()
                wait(.1)
            press('Return')
            wait(.8)
            image = app.clipboard().image()
            assert (image.width(), image.height()) == (120, 90), image.size()
            assert all(image.pixelColor(x, y).name() == '#5096d2' for x in range(120) for y in range(90))
        finally:
            d.close()
            window.close()
        # Supply the stock system entry so LXQt must resolve the user's override.
        system_config = home/'system-xdg'
        autostart = system_config/'autostart'
        autostart.mkdir(parents=True)
        stock = Path('/etc/xdg/autostart/lxqt-panel.desktop')
        (autostart/stock.name).write_bytes(stock.read_bytes())
        env = dict(os.environ, XDG_CONFIG_DIRS=str(system_config), XDG_CURRENT_DESKTOP='LXQt',
                   DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(home/'no-system-bus'))
        env.pop('SESSION_MANAGER', None)
        session = subprocess.Popen(['lxqt-session'], env=env)
        d = display.Display()
        try:
            deadline = time.monotonic() + 12
            while True:
                docks = []
                clients = d.screen().root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'), X.AnyPropertyType)
                for wid in clients.value if clients else []:
                    w = d.create_resource_object('window', wid)
                    kinds = w.get_full_property(d.intern_atom('_NET_WM_WINDOW_TYPE'), X.AnyPropertyType)
                    if kinds and d.intern_atom('_NET_WM_WINDOW_TYPE_DOCK') in kinds.value:
                        pid = w.get_full_property(d.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
                        docks.append(Path(f'/proc/{pid.value[0]}/exe').resolve())
                if docks:
                    assert docks == [binary], docks
                    break
                assert session.poll() is None and time.monotonic() < deadline, 'LXQt did not start the replacement dock'
                wait(.1)
            print('PASS private LXQt session selected the staged panel over the stock autostart entry', flush=True)
        finally:
            d.close()
            session.terminate()
            session.wait(timeout=12)
        runtime_settings = (home/'.config/doroshell/panel.conf').read_bytes()
        subprocess.run([sys.executable, home/'.local/share/doroshell/toolkit/setup.py', 'native-panel', '--rollback', '--keep-panel-edits'], check=True)
        if runtime_settings != (prepared/'panel.conf').read_bytes():
            assert next((home/'.local/state/doroshell').glob('panel-edited-*.conf')).read_bytes() == runtime_settings
        # LXQt registers its own panel shortcuts. Keep those additions across rollback.
        import re
        group = re.compile(rb'(?ms)^\[Print\.\d+\]\n.*?(?=^\[|\Z)')
        previous_print = group.search(originals[shortcuts]).group()
        originals[shortcuts], replacements = group.subn(lambda m: previous_print, shortcuts.read_bytes())
        assert replacements == 1
        subprocess.run(setup + ['--rollback'], check=True)
        for path, original in originals.items():
            assert path.read_bytes() == original, path
        assert not (home/'.config/autostart/lxqt-panel.desktop').exists()
        subprocess.run([sys.executable, ROOT/'panel/check_x11.py', '--run', '--binary', binary], check=True)
    finally:
        if helper:
            helper.terminate()
            helper.wait(timeout=5)
        wm.terminate()
        wm.wait(timeout=5)
    print('PASS core setup, repeat apply, staged panel, keyboard snap left/right/restore, Print capture/cancel and rollback', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--xvfb', type=Path)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.binary.resolve())
    elif args.run and args.xvfb:
        isolated(args.xvfb.resolve(), [sys.executable, Path(__file__).resolve(), '--worker', '--binary', args.binary.resolve()])
    else:
        parser.error('Pass --run --xvfb /path/to/Xvfb --binary /path/to/lxqt-panel')
