# SPDX-License-Identifier: LGPL-2.1-or-later
"""Show Desktop state restoration and live orientation on private X11/Openbox."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from x11_isolation import isolated


def worker(binary, evidence=None):
    assert os.environ.get('DOROSHELL_TEST_DISPLAY') == os.environ.get('DISPLAY') != ':0'
    if evidence:
        evidence.mkdir(parents=True, exist_ok=True)
    home = Path.home()
    assert home.name.startswith('doroshell-private-display-')
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import QMimeData, Qt
    from PySide6.QtGui import QColor, QDrag
    from Xlib import X, XK, display, protocol
    from Xlib.ext import xtest
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    d = display.Display()
    root = d.screen().root

    def wait(seconds=.25):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.01)

    def prop(window, name):
        value = window.get_full_property(d.intern_atom(name), X.AnyPropertyType)
        return list(value.value) if value else []

    def message(window, name, data):
        event = protocol.event.ClientMessage(window=window.id, client_type=d.intern_atom(name), data=(32, data + [0] * (5-len(data))))
        root.send_event(event, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        d.sync()
        wait()

    def key(name):
        code = d.keysym_to_keycode(XK.string_to_keysym(name))
        xtest.fake_input(d, X.KeyPress, code)
        xtest.fake_input(d, X.KeyRelease, code)
        d.sync()
        wait(.1)

    def click(x, y, button=1):
        xtest.fake_input(d, X.MotionNotify, x=x, y=y)
        xtest.fake_input(d, X.ButtonPress, button)
        xtest.fake_input(d, X.ButtonRelease, button)
        d.sync()
        wait()

    def windows(window):
        found = []
        try:
            if prop(window, '_NET_WM_PID') == [panel.pid] and window.get_attributes().map_state == X.IsViewable:
                found.append(window)
            for child in window.query_tree().children:
                found.extend(windows(child))
        except Exception:
            pass
        return found

    def panel_window():
        return next(w for w in windows(root) if d.intern_atom('_NET_WM_WINDOW_TYPE_DOCK') in prop(w, '_NET_WM_WINDOW_TYPE'))

    def state():
        return {name: (x.get_attributes().map_state == X.IsViewable,
                       d.intern_atom('_NET_WM_STATE_HIDDEN') in prop(x, '_NET_WM_STATE'),
                       prop(x, '_NET_WM_DESKTOP')[0]) for name, (_, x) in fixtures.items()}

    def showing():
        return prop(root, '_NET_SHOWING_DESKTOP') == [1]

    def toggle(expected):
        panel_rect = panel_window()
        g = panel_rect.get_geometry()
        image = app.primaryScreen().grabWindow(panel_rect.id).toImage()
        points = [(x, y) for x in range(image.width()) for y in range(image.height())
                  if image.pixelColor(x, y) in (QColor('#803656'), QColor('#5b143d'))]
        assert points, 'Show Desktop edge border missing'
        xs, ys = zip(*points)
        vertical = g.height > g.width
        assert (max(ys)-min(ys)+1 if vertical else max(xs)-min(xs)+1) == 12, ('edge extent', g.width, g.height)
        assert (min(ys) > g.height-35 if vertical else min(xs) > g.width-35), 'edge not at panel end'
        pos = root.translate_coords(panel_rect, 0, 0)
        click(pos.x+(min(xs)+max(xs))//2, pos.y+(min(ys)+max(ys))//2)
        assert showing() == expected, ('toggle', expected, showing())

    def create(name, desktop=0, minimized=False):
        widget = QWidget()
        widget.setWindowTitle('Disposable ' + name)
        widget.setGeometry(100+len(fixtures)*35, 130, 200, 140)
        widget.show()
        wait()
        window = d.create_resource_object('window', int(widget.winId()))
        # Minimize while on this workspace: an unmapped remote window can already
        # appear minimized to Qt even though it is not EWMH-HIDDEN.
        if minimized:
            widget.showMinimized()
            wait()
        message(window, '_NET_WM_DESKTOP', [desktop, 2])
        fixtures[name] = (widget, window)

    rc = home/'rc.xml'
    rc.write_text('<openbox_config xmlns="http://openbox.org/3.4/rc"><desktops><number>2</number></desktops></openbox_config>')
    conf = home/'panel.conf'
    conf.write_text('panels=panel1\n[panel1]\nplugins=worldclock,edge\nposition=Bottom\ndoroshellTheme=true\nwidth=240\nwidth-percent=false\nreserve-space=false\npanelSize=40\n[worldclock]\ntype=worldclock\nalignment=Right\n[edge]\ntype=showdesktop\nalignment=Right\ndoroshellEdge=true\n')
    log = open(home/'process.log', 'w')
    wm = subprocess.Popen(['openbox', '--sm-disable', '--config-file', str(rc)], stdout=log, stderr=log)
    panel = None
    fixtures = {}
    drag_source = None
    try:
        wait(.7)
        for name, desktop, minimized in [('normal', 0, False), ('closing', 0, False), ('minimized', 0, True),
                                         ('remote', 1, False), ('remote-minimized', 1, True),
                                         ('sticky', 0xffffffff, False), ('sticky-minimized', 0xffffffff, True)]:
            create(name, desktop, minimized)
        panel = subprocess.Popen([str(binary), '--config', str(conf)], stdout=log, stderr=log)
        wait(1.5)
        original = state()
        assert {n for n, s in original.items() if s[0]} == {'normal', 'closing', 'sticky'}
        assert {n for n, s in original.items() if s[1]} == {'minimized', 'remote-minimized', 'sticky-minimized'}
        for _ in range(3):
            toggle(True)
            assert not any(s[0] for s in state().values()), 'window remained over desktop'
            assert {n: s[1:] for n, s in state().items()} == {n: s[1:] for n, s in original.items()}
            toggle(False)
            assert state() == original, 'toggle changed minimized/workspace/sticky state'
        toggle(True)
        message(root, '_NET_CURRENT_DESKTOP', [1, 0])
        assert showing(), 'Openbox unexpectedly canceled mode on workspace switch'
        toggle(False)
        assert {n for n, s in state().items() if s[0]} == {'remote', 'sticky'}
        assert {n: s[1:] for n, s in state().items()} == {n: s[1:] for n, s in original.items()}
        on_second = state()
        toggle(True)
        toggle(False)
        assert state() == on_second
        message(root, '_NET_CURRENT_DESKTOP', [0, 0])
        assert state() == original
        toggle(True)
        fixtures.pop('closing')[0].close()
        wait()
        assert showing()
        toggle(False)
        original.pop('closing')
        assert state() == original, 'closing a hidden window disturbed survivors'
        toggle(True)
        create('new')
        assert not showing() and state()['new'] == (True, False, 0)
        # Openbox exits mode for a newly activated window and iconifies the old
        # current-workspace windows. Respect that WM policy, including sticky ones.
        after_new = state()
        for name in ('normal', 'sticky'):
            assert after_new[name] == (False, True, original[name][2])
        for name in ('minimized', 'remote', 'remote-minimized', 'sticky-minimized'):
            assert after_new[name] == original[name]
        for _ in range(2):
            toggle(True)
            toggle(False)
            assert state() == after_new, 'new-window transition revived previously minimized windows'
        print('PASS mixed minimized/sticky/workspace states, close/create while showing, repeated toggle', flush=True)

        # Exercise the real placement dialog in this same panel process. Config
        # file edits alone are not a live panel-orientation change.
        for position, index in [('Left', 1), ('Top', 0), ('Right', 2), ('Bottom', 3)]:
            p = panel_window()
            g = p.get_geometry()
            pos = root.translate_coords(p, 0, 0)
            click(pos.x+15, pos.y+15, 3)
            key('Down')
            key('Return')
            wait(.4)
            dialog = next(w for w in windows(root) if w.get_wm_name() == 'Configure Panel')
            origin = root.translate_coords(dialog, 0, 0)
            if evidence:
                app.primaryScreen().grabWindow(0).save(str(evidence/(position+'-dialog.png')))
            # Placement dialog coordinates in the fixed private Xvfb fixture.
            click(origin.x+340, origin.y+213)
            key('Home')
            for _ in range(index):
                key('Down')
            key('Return')
            if evidence:
                app.primaryScreen().grabWindow(0).save(str(evidence/(position+'-selected.png')))
            click(origin.x+460, origin.y+473)
            wait(.4)
            assert not any(w.get_wm_name() == 'Configure Panel' for w in windows(root)), 'placement dialog did not close'
            # Inspect the live window, not the file behind LXQt's 3-second save timer.
            p = panel_window()
            g = p.get_geometry()
            pos = root.translate_coords(p, 0, 0)
            assert (g.height > g.width) == (position in ('Left', 'Right')), (position, g.width, g.height)
            assert {'Left': pos.x == 0, 'Top': pos.y == 0,
                    'Right': pos.x+g.width == 1024, 'Bottom': pos.y+g.height == 768}[position], ('wrong live edge', position, pos.x, pos.y)
            before = state()
            toggle(True)
            toggle(False)
            assert state() == before
            assert panel.poll() is None
        print('PASS same-process Bottom/Left/Top/Right/Bottom placement; 12-pixel edge and activation after every change', flush=True)
        class DragSource(QWidget):
            count = 0

            def mouseMoveEvent(self, event):
                if event.buttons() & Qt.LeftButton:
                    self.count += 1
                    drag = QDrag(self)
                    mime = QMimeData()
                    mime.setText('Disposable desktop drag')
                    drag.setMimeData(mime)
                    self.result = drag.exec(Qt.CopyAction)

        drag_source = DragSource()
        drag_source.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint)
        drag_source.setGeometry(650, 440, 200, 140)
        source_window = d.create_resource_object('window', int(drag_source.winId()))
        source_window.change_property(d.intern_atom('_NET_WM_WINDOW_TYPE'), d.intern_atom('ATOM'), 32,
                                      [d.intern_atom('_NET_WM_WINDOW_TYPE_DESKTOP')])
        d.sync()
        drag_source.show()
        wait()

        def drag_to_edge(leave_early=False, drop_early=False):
            p = panel_window()
            g = p.get_geometry()
            pos = root.translate_coords(p, 0, 0)
            count = drag_source.count
            errors = []

            def drive():
                connection = display.Display()
                try:
                    xtest.fake_input(connection, X.MotionNotify, x=700, y=500)
                    xtest.fake_input(connection, X.ButtonPress, 1)
                    connection.sync()
                    time.sleep(.1)
                    xtest.fake_input(connection, X.MotionNotify, x=730, y=500)
                    connection.sync()
                    time.sleep(.3)
                    xtest.fake_input(connection, X.MotionNotify, x=pos.x+g.width-6, y=pos.y+g.height//2)
                    connection.sync()
                    if leave_early:
                        time.sleep(.15)
                        xtest.fake_input(connection, X.MotionNotify, x=700, y=600)
                        connection.sync()
                    time.sleep(.15 if drop_early else 1.1)
                except Exception as error:
                    errors.append(error)
                finally:
                    xtest.fake_input(connection, X.ButtonRelease, 1)
                    connection.sync()
                    connection.close()

            driver = threading.Thread(target=drive)
            driver.start()
            while driver.is_alive():
                wait(.05)  # Qt's nested drag loop stays responsive to the driver.
            driver.join()
            wait(1.1 if drop_early else .25)
            assert not errors, errors
            assert drag_source.count == count+1, 'fixture did not start exactly one real Qt drag'
            assert drag_source.result == Qt.IgnoreAction, ('Show Desktop unexpectedly consumed the drop', leave_early, drop_early)

        before = state()
        drag_to_edge(leave_early=True)
        assert not showing(), 'leaving before hover delay activated Show Desktop'
        assert state() == before, 'early drag leave changed window state'
        drag_to_edge(drop_early=True)
        assert not showing() and state() == before, 'quick drop left the hover timer running'
        drag_to_edge()
        assert showing(), 'drag hover did not expose desktop'
        drag_to_edge()
        assert showing(), 'drag hover restored applications over the already exposed desktop'
        toggle(False)
        assert state() == before, 'click after drag did not restore the original state'
        print('PASS real Qt drag: early leave/drop cancel without accepting drops; repeated hover keeps desktop exposed; click still restores', flush=True)

    finally:
        if drag_source:
            drag_source.close()
        for widget, _ in fixtures.values():
            widget.close()
        if panel:
            panel.terminate()
            panel.wait(timeout=5)
        wm.terminate()
        wm.wait(timeout=5)
        log.close()
        d.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--xvfb', type=Path)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.binary.resolve(), args.evidence.resolve() if args.evidence else None)
    elif args.run and args.xvfb:
        isolated(args.xvfb.resolve(), [sys.executable, str(Path(__file__).resolve()), '--worker', '--binary', str(args.binary.resolve())] + (['--evidence', str(args.evidence.resolve())] if args.evidence else []))
    else:
        parser.error('Pass --run --xvfb /path/to/Xvfb --binary /path/to/lxqt-panel')
