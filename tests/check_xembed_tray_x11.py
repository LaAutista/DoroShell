# SPDX-License-Identifier: LGPL-2.1-or-later
"""Synthetic XEmbed/SNI coexistence; opt-in authenticated private X11 only."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary, evidence):
    assert os.environ['DISPLAY'] == os.environ['DOROSHELL_TEST_DISPLAY'] != ':0'
    assert Path.home().name.startswith('doroshell-private-display-')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QColor
    from Xlib import X, display, protocol
    from Xlib.ext import xtest
    import dbus, dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    app = QApplication([])
    bus = dbus.SessionBus()
    assert not bus.name_has_owner('org.kde.StatusNotifierWatcher')
    calls = []
    service = dbus.service.BusName('org.kde.StatusNotifierItem.Coexistence', bus)

    class Item(dbus.service.Object):
        @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='ss', out_signature='v')
        def Get(self, interface, key):
            pix = dbus.Array([dbus.Struct((dbus.Int32(24), dbus.Int32(24), dbus.ByteArray(bytes([255, 19, 211, 91])*576)), signature='iiay')], signature='(iiay)')
            values = {'Category': 'ApplicationStatus', 'Id': 'NativeFixture', 'Title': 'NativeFixture', 'Status': 'Passive', 'WindowId': dbus.Int32(0), 'ItemIsMenu': False, 'IconName': '', 'IconThemePath': '', 'OverlayIconName': '', 'AttentionIconName': '', 'AttentionMovieName': '', 'IconPixmap': pix, 'OverlayIconPixmap': dbus.Array([], signature='(iiay)'), 'AttentionIconPixmap': pix, 'ToolTip': dbus.Struct(('', pix, 'NativeFixture', ''), signature='sa(iiay)ss')}
            if key not in values:
                raise dbus.exceptions.DBusException('Unavailable', name='org.freedesktop.DBus.Error.UnknownProperty')
            return values[key]

        @dbus.service.method('org.kde.StatusNotifierItem', in_signature='ii', out_signature='')
        def Activate(self, x, y):
            calls.append('native')

    item = Item(bus, '/StatusNotifierItem')
    d = display.Display()
    root = d.screen().root
    clients = []
    evidence.mkdir(parents=True, exist_ok=True)

    def wait(seconds=.3):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            app.processEvents()
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            time.sleep(.005)

    def click(x, y, button=1):
        xtest.fake_input(d, X.MotionNotify, x=x, y=y)
        xtest.fake_input(d, X.ButtonPress, button)
        xtest.fake_input(d, X.ButtonRelease, button)
        d.sync()
        wait(.5)

    def panel_windows():
        result = []
        def visit(w):
            try:
                pid = w.get_full_property(d.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
                if pid is not None and pid.value[0] == panel.pid and w.get_attributes().map_state == X.IsViewable:
                    result.append(w)
                for child in w.query_tree().children:
                    visit(child)
            except Exception:
                pass
        visit(root)
        return result

    def popup():
        return next((w for w in panel_windows() if w.get_wm_name() == 'Hidden icons'), None)

    def open_popup():
        if popup() is None:
            p = next(w for w in panel_windows() if w.get_geometry().width >= 795)
            g = p.get_geometry(); pos = root.translate_coords(p, 0, 0)
            assert pos.x >= 0 and pos.x+g.width <= 800
            click(pos.x+g.width-12, pos.y+g.height//2)
        assert popup() is not None
        return popup()

    def points(w, color):
        image = app.primaryScreen().grabWindow(w.id).toImage()
        return [(x, y) for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x, y) == QColor(color)]

    def click_icon(color, button=1):
        w = open_popup(); ps = points(w, color)
        if not ps:
            app.primaryScreen().grabWindow(0).save(str(evidence/'missing-icon.png'))
        assert ps, ('icon pixels missing', color)
        pos = root.translate_coords(w, 0, 0)
        click(pos.x+sum(x for x,y in ps)//len(ps), pos.y+sum(y for x,y in ps)//len(ps), button)

    def dock():
        # Separate X connection models a disposable legacy application's lifetime.
        c = display.Display(); clients.append(c)
        r = c.screen().root
        owner = c.get_selection_owner(c.intern_atom('_NET_SYSTEM_TRAY_S0'))
        assert owner, 'tray plugin did not claim the legacy selection'
        w = r.create_window(0, 0, 24, 24, 0, c.screen().root_depth, X.InputOutput, X.CopyFromParent,
                            background_pixel=0x000000, event_mask=X.ExposureMask | X.StructureNotifyMask | X.ButtonPressMask | X.ButtonReleaseMask)
        w.set_wm_name('LegacyFixture')
        w.set_wm_class('LegacyFixture', 'LegacyFixture')
        w.change_property(c.intern_atom('_XEMBED_INFO'), c.intern_atom('_XEMBED_INFO'), 32, [0, 1])
        owner.send_event(protocol.event.ClientMessage(window=owner.id, client_type=c.intern_atom('_NET_SYSTEM_TRAY_OPCODE'), data=(32, [X.CurrentTime, 0, w.id, 0, 0])), event_mask=0)
        c.flush(); wait(1)
        events = []
        while c.pending_events():
            e = c.next_event(); events.append(e)
        assert any(e.type == X.ClientMessage and e.client_type == c.intern_atom('_XEMBED') and e.data[1][1] == 0 for e in events), 'missing embedded notify'
        assert w.query_tree().parent.id != r.id, 'client was not reparented'
        assert w.get_attributes().map_state == X.IsViewable
        gc = w.create_gc(foreground=0xe72b91)
        g = w.get_geometry()
        # A contrasting border survives upstream RGB24 heuristic transparency.
        w.fill_rectangle(gc, 4, 4, g.width-8, g.height-8)
        c.sync(); wait(.7)
        gc.free()
        return c, w

    conf = Path.home()/'panel.conf'
    conf.write_text('panels=panel1\n[panel1]\nplugins=taskbar,tray,statusnotifier\ndoroshellTheme=true\nposition=Bottom\nwidth=100\nwidth-percent=true\nreserve-space=false\npanelSize=40\n[taskbar]\ntype=taskbar\n[tray]\ntype=tray\n[statusnotifier]\ntype=statusnotifier\nalignment=Right\ndoroshellPopup=true\n')
    cfg = QSettings(str(conf), QSettings.Format.IniFormat)
    cfg.setValue('statusnotifier/hideList', ['LegacyFixture', 'NativeFixture']); cfg.sync(); del cfg
    log = open(evidence/'panel.log', 'w')
    wm = subprocess.Popen(['openbox', '--sm-disable'], stdout=log, stderr=log)
    panel = None
    try:
        wait(.6)
        panel = subprocess.Popen([str(binary), '--config', str(conf)], stdout=log, stderr=log)
        wait(1.5)
        watcher = bus.get_object('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher')
        dbus.Interface(watcher, 'org.kde.StatusNotifierWatcher').RegisterStatusNotifierItem(service.get_name())
        props = dbus.Interface(watcher, 'org.freedesktop.DBus.Properties')
        def count():
            return len(props.Get('org.kde.StatusNotifierWatcher', 'RegisteredStatusNotifierItems'))
        wait(); assert count() == 1
        for cycle in range(2):
            c, w = dock(); assert count() == 2
            if cycle:
                assert popup() is None, 'new client left stale overflow snapshot open'
            for button in (1, 3):
                click_icon('#e72b91', button)
                events = []
                while c.pending_events():
                    events.append(c.next_event())
                assert [(e.type, e.detail) for e in events if e.type in (X.ButtonPress, X.ButtonRelease)] == [(X.ButtonPress, button), (X.ButtonRelease, button)], 'legacy input missing/duplicated'
                assert calls == ['native']*cycle, 'legacy click activated native item'
            click_icon('#13d35b'); assert calls == ['native']*(cycle+1)
            app.primaryScreen().grabWindow(0).save(str(evidence/('coexist-%s.png' % cycle)))
            c.close(); clients.remove(c); wait(1)
            assert count() == 1, 'legacy disconnect left stale SNI proxy'
            assert not points(open_popup(), '#e72b91'), 'legacy pixels remain after client exit'
            assert points(popup(), '#13d35b'), 'native item disappeared with legacy client'
        assert panel.poll() is None
        print('PASS XEmbed docking, pixels, left/right input, disconnect/restart and native SNI overflow coexistence', flush=True)
    finally:
        for c in clients:
            c.close()
        item.remove_from_connection()
        for process in (panel, wm):
            if process and process.poll() is None:
                process.terminate(); process.wait(timeout=5)
        d.close(); log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--xvfb', type=Path)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker(args.binary.resolve(), args.evidence.resolve())
    elif args.run and args.xvfb:
        isolated(args.xvfb.resolve(), ['env', 'QT_SCALE_FACTOR=1', sys.executable, str(Path(__file__).resolve()), '--worker', '--binary', str(args.binary.resolve()), '--evidence', str(args.evidence.resolve())], geometry='800x600x24')
    else:
        parser.error('Opt in with --run --xvfb PATH')
