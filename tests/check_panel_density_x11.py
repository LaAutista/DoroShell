# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bounded panel/tray density acceptance on an authenticated private X11 server."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary, evidence, case):
    assert os.environ['DISPLAY'] == os.environ['DOROSHELL_TEST_DISPLAY'] != ':0'
    home = Path.home()
    assert home.name.startswith('doroshell-private-display-')
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QColor, QIcon, QPixmap
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    import dbus, dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    bus = dbus.SessionBus()
    assert not bus.name_has_owner('org.kde.StatusNotifierWatcher')
    service = 'org.kde.StatusNotifierItem.Density'
    name = dbus.service.BusName(service, bus)
    calls = []
    colors = [QColor(QColor.fromHsv(i*29 % 360, 180, 200).name()) for i in range(60)]
    titles = ['Density %02d — long notification application label' % i for i in range(60)]

    class Item(dbus.service.Object):
        def __init__(self, index):
            self.index = index
            self.path = '/Item%03d' % index
            super().__init__(bus, self.path)

        @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='ss', out_signature='v')
        def Get(self, interface, key):
            color = colors[self.index]
            pixels = bytes([255, color.red(), color.green(), color.blue()])*24*24
            pix = dbus.Array([dbus.Struct((dbus.Int32(24), dbus.Int32(24), dbus.ByteArray(pixels)), signature='iiay')], signature='(iiay)')
            values = {'Category': 'ApplicationStatus', 'Id': 'Density%02d' % self.index, 'Title': titles[self.index], 'Status': 'Passive', 'WindowId': dbus.Int32(0), 'ItemIsMenu': False, 'IconName': '', 'IconThemePath': '', 'OverlayIconName': '', 'AttentionIconName': '', 'AttentionMovieName': '', 'IconPixmap': pix, 'OverlayIconPixmap': dbus.Array([], signature='(iiay)'), 'AttentionIconPixmap': pix, 'ToolTip': dbus.Struct(('', pix, titles[self.index], 'Disposable fixture'), signature='sa(iiay)ss')}
            if key not in values:
                raise dbus.exceptions.DBusException('Unavailable', name='org.freedesktop.DBus.Error.UnknownProperty')
            return values[key]

        @dbus.service.method('org.kde.StatusNotifierItem', in_signature='ii', out_signature='')
        def Activate(self, x, y):
            calls.append(self.index)

    evidence.mkdir(parents=True, exist_ok=True)
    d = display.Display()
    root = d.screen().root
    screen = root.get_geometry()
    scale = float(os.environ['QT_SCALE_FACTOR'])

    def wait(seconds=.2):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            app.processEvents()
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            time.sleep(.005)

    def key(value):
        code = d.keysym_to_keycode(XK.string_to_keysym(value))
        xtest.fake_input(d, X.KeyPress, code)
        xtest.fake_input(d, X.KeyRelease, code)
        d.sync()
        wait(.06)

    def click(x, y):
        xtest.fake_input(d, X.MotionNotify, x=x, y=y)
        xtest.fake_input(d, X.ButtonPress, 1)
        xtest.fake_input(d, X.ButtonRelease, 1)
        d.sync()
        wait()

    def windows(window):
        found = []
        try:
            pid = window.get_full_property(d.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
            if pid is not None and pid.value[0] == panel.pid and window.get_attributes().map_state == X.IsViewable:
                found.append(window)
            for child in window.query_tree().children:
                found.extend(windows(child))
        except Exception:
            pass
        return found

    def panel_window():
        return next(w for w in windows(root) if w.get_geometry().width >= screen.width-5)

    def popups():
        return [w for w in windows(root) if w.get_wm_name() == 'Hidden icons']

    def color_points(image, color):
        return [(x, y) for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x, y) == color]

    conf = home/'panel.conf'
    conf.write_text('panels=panel1\n[panel1]\nplugins=taskbar,statusnotifier\ndoroshellTheme=true\nposition=Bottom\nwidth=100\nwidth-percent=true\nreserve-space=false\npanelSize=40\n[taskbar]\ntype=taskbar\nbuttonStyle=IconText\nbuttonWidth=220\niconByClass=false\ngroupingEnabled=false\n[statusnotifier]\ntype=statusnotifier\nalignment=Right\ndoroshellPopup=true\n')
    cfg = QSettings(str(conf), QSettings.Format.IniFormat)
    cfg.setValue('statusnotifier/hideList', titles)
    cfg.sync()
    del cfg
    stylesheet = home/'large-font.qss'
    stylesheet.write_text('* { font-size: 18pt; }')
    log = open(evidence/'panel.log', 'w')
    wm = subprocess.Popen(['openbox', '--sm-disable'], stdout=log, stderr=log)
    panel = None
    items = []
    tasks = []
    try:
        wait(.6)
        for i in range(12):
            widget = QWidget()
            widget.setWindowTitle('Application %02d: a deliberately long document title with many words and an & ampersand for narrow taskbar layout' % i)
            pix = QPixmap(24, 24)
            color = QColor(QColor.fromHsv(i*27, 230, 250).name())
            pix.fill(color)
            widget.setWindowIcon(QIcon(pix))
            widget.show()
            wait(.08)
            widget.showMinimized()
            tasks.append((widget, color))
        panel = subprocess.Popen([str(binary), '-stylesheet', str(stylesheet), '--config', str(conf)], stdout=log, stderr=log)
        wait(1.5)
        watcher = dbus.Interface(bus.get_object('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher'), 'org.kde.StatusNotifierWatcher')
        for i in range(60):
            item = Item(i)
            items.append(item)
            watcher.RegisterStatusNotifierItem(item.path)
        wait(2)
        properties = dbus.Interface(bus.get_object('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher'), 'org.freedesktop.DBus.Properties')
        assert len(properties.Get('org.kde.StatusNotifierWatcher', 'RegisteredStatusNotifierItems')) == 60
        p = panel_window()
        g = p.get_geometry()
        pos = root.translate_coords(p, 0, 0)
        assert pos.x >= 0 and pos.x+g.width <= screen.width, 'long labels expanded panel off-screen'
        image = app.primaryScreen().grabWindow(p.id).toImage()
        image.save(str(evidence/'tasks.png'))
        assert image.width() == g.width, 'fixture mixed logical and physical image coordinates'
        for _, color in tasks:
            assert color_points(image, color), ('task icon unavailable in dense panel', color.name())
        if case != 'tasks':
            click(pos.x+g.width-round(12*scale), pos.y+g.height//2)
            assert len(popups()) == 1, 'overflow did not open'
            popup = popups()[0]
            pg = popup.get_geometry()
            pp = root.translate_coords(popup, 0, 0)
            app.primaryScreen().grabWindow(0).save(str(evidence/'overflow.png'))
            assert pp.x >= 0 and pp.y >= 0 and pp.x+pg.width <= screen.width and pp.y+pg.height <= screen.height, ('overflow outside screen', pp.x, pp.y, pg.width, pg.height, screen.width, screen.height)
            for i in range(60):
                if i:
                    key('Tab')
                key('Return')
                assert calls == list(range(i+1)), ('keyboard skipped or duplicated an icon', i, calls)
                if i in (0, 15, 31, 47, 59):
                    visible = app.primaryScreen().grabWindow(popup.id).toImage()
                    assert color_points(visible, colors[i]), ('focused icon is outside visible viewport', i)
            app.primaryScreen().grabWindow(0).save(str(evidence/'last-icon.png'))
            for i in range(58, -1, -1):
                shift = d.keysym_to_keycode(XK.string_to_keysym('Shift_L'))
                xtest.fake_input(d, X.KeyPress, shift)
                key('Tab')
                xtest.fake_input(d, X.KeyRelease, shift)
                d.sync()
                key('Return')
                assert calls == list(range(60))+list(range(58, i-1, -1))
            assert color_points(app.primaryScreen().grabWindow(popup.id).toImage(), colors[0]), 'reverse traversal did not reveal first icon'
            key('Escape')
            assert not popups(), 'Escape failed after scrolling through overflow'
        if case != 'overflow':
            for widget, color in tasks:
                image = app.primaryScreen().grabWindow(p.id).toImage()
                points = color_points(image, color)
                assert points
                x = round(sum(x for x, y in points)/len(points))
                y = round(sum(y for x, y in points)/len(points))
                click(pos.x+x, pos.y+y)
                assert not widget.isMinimized(), 'dense task was not reachable'
                widget.showMinimized()
                wait(.1)
            for widget, _ in tasks[3:]:
                widget.close()
            wait(.4)
            image = app.primaryScreen().grabWindow(p.id).toImage()
            image.save(str(evidence/'long-labels.png'))
            points = color_points(image, tasks[0][1])
            assert points, 'remaining long-label task missing'
            x = round(sum(x for x, y in points)/len(points))
            y = round(sum(y for x, y in points)/len(points))
            xtest.fake_input(d, X.MotionNotify, x=50, y=100)
            d.sync()
            wait(.1)
            xtest.fake_input(d, X.MotionNotify, x=pos.x+x, y=pos.y+y)
            d.sync()
            wait(1.2)
            tooltips = []
            for window in windows(root):
                kind = window.get_full_property(d.intern_atom('_NET_WM_WINDOW_TYPE'), X.AnyPropertyType)
                if kind is not None and d.intern_atom('_NET_WM_WINDOW_TYPE_TOOLTIP') in kind.value:
                    tooltips.append(window)
            assert tooltips, 'long task label tooltip did not open'
            for tooltip in tooltips:
                tg = tooltip.get_geometry()
                tp = root.translate_coords(tooltip, 0, 0)
                assert tp.x >= 0 and tp.y >= 0 and tp.x+tg.width <= screen.width and tp.y+tg.height <= screen.height, ('long label tooltip outside screen', tp.x, tp.y, tg.width, tg.height)
                tip_image = app.primaryScreen().grabWindow(tooltip.id).toImage()
                tip_image.save(str(evidence/'tooltip-text.png'))
                assert any(max(tip_image.pixelColor(x, y).red(), tip_image.pixelColor(x, y).green(), tip_image.pixelColor(x, y).blue()) < 90
                           for y in range(tip_image.height()//2, tip_image.height()-8)
                           for x in range(8, tip_image.width()-8)), 'long tooltip text was elided instead of wrapping into its reserved space'
            app.primaryScreen().grabWindow(0).save(str(evidence/'long-label-tooltip.png'))
        assert panel.poll() is None
        print('PASS', screen.width, screen.height, 'scale', scale, 'case', case, '18pt labels, bounded task/overflow geometry and requested input checks', flush=True)
    finally:
        for item in items:
            item.remove_from_connection()
        for widget, _ in tasks:
            widget.close()
        for process in (panel, wm):
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        log.close()
        d.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--xvfb', type=Path)
    parser.add_argument('--scale', choices=('1.5', '2'), default='1.5')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--case', choices=('tasks', 'overflow', 'both'), default='both')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker(args.binary.resolve(), args.evidence.resolve(), args.case)
    elif args.run and args.xvfb:
        isolated(args.xvfb.resolve(), ['env', 'QT_SCALE_FACTOR='+args.scale, sys.executable, str(Path(__file__).resolve()), '--worker', '--binary', str(args.binary.resolve()), '--evidence', str(args.evidence.resolve()), '--case', args.case], geometry='800x600x24')
    else:
        parser.error('Opt in with --run --xvfb PATH')
