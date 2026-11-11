"""Check window picking against visible native pixels on a private Openbox display."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

from x11_isolation import isolated

ROOT = Path(__file__).resolve().parents[1]


def worker():
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication, QWidget
    from Xlib import X, XK, display
    from Xlib.ext import xtest

    assert os.environ['DISPLAY'] == os.environ['DOROSHELL_TEST_DISPLAY']
    app = QApplication([])
    server = display.Display()
    root = server.screen().root
    manager = subprocess.Popen(['openbox', '--sm-disable'])
    def wait(delay):
        end = time.monotonic() + delay
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.01)

    try:
        wait(.4)
        back = QWidget()
        back.setStyleSheet('background: #c02040')
        back.resize(220, 165)
        back.show()
        front = QWidget()
        front.setStyleSheet('background: #1675ae')
        front.resize(190, 145)
        front.show()
        wait(.3)
        back.move(-30, 110)
        front.move(75, 155)
        front.raise_()
        wait(.4)
        def bounds(widget):
            client = server.create_resource_object('window', int(widget.winId()))
            frame_window = client.query_tree().parent
            if frame_window.id == root.id:
                frame_window = client
            def rect(window):
                position = root.translate_coords(window, 0, 0)
                size = window.get_geometry()
                return QRect(position.x, position.y, size.width, size.height)
            return rect(client), rect(frame_window)
        lower_client, lower = bounds(back)
        upper_client, upper = bounds(front)
        assert lower_client.left() < 0 < lower_client.right()
        assert lower.top() < lower_client.top() and upper.top() < upper_client.top()
        overlap = lower_client.intersected(upper_client)
        upper_title = QPoint(upper_client.left()+8, upper_client.top()-4)
        lower_title = QPoint(12, lower_client.top()-4)
        assert lower_client.contains(upper_title) and upper.contains(upper_title)
        assert lower.contains(lower_title) and not upper.contains(lower_title)
        app.clipboard().setText('window picker sentinel')
        cases = [(overlap.center(), upper, True), (upper_title, upper_client, False),
                 (lower_title, lower, True), (lower_title, lower_client, False),
                 (lower_title, lower_client, False)]
        for i, (point, rect, include_borders) in enumerate(cases):
            raw = app.primaryScreen().grabWindow(0).toImage()
            expected = rect.intersected(raw.rect())
            cancel = i == len(cases)-1
            out = Path.home() / f'window-{i}.png'
            command = [sys.executable, ROOT/'runtime/menu_capture.py', '--notify']
            if not cancel:
                command.extend(['--output', out])
            proc = subprocess.Popen(command, stdout=subprocess.PIPE)
            try:
                assert proc.stdout.readline() == b'FROZEN\n'
                wait(.4)
                # Change the underlying client after freezing. Output must still match every old pixel.
                front.setStyleSheet('background: #003300')
                front.move(320, 40)
                wait(.1)
                def key(name):
                    code = server.keysym_to_keycode(XK.string_to_keysym(name))
                    for kind in (X.KeyPress, X.KeyRelease):
                        xtest.fake_input(server, kind, code)
                key('w')
                if not include_borders:
                    key('b')
                xtest.fake_input(server, X.MotionNotify, x=point.x(), y=point.y())
                xtest.fake_input(server, X.ButtonPress, 1)
                xtest.fake_input(server, X.ButtonRelease, 1)
                server.sync()
                wait(.15)
                key('Escape' if cancel else 'Return')
                server.sync()
                assert proc.wait(timeout=5) == 0
                if cancel:
                    assert app.clipboard().text() == 'window picker sentinel'
                else:
                    image = QImage(str(out)).convertToFormat(QImage.Format.Format_RGB32)
                    wanted = raw.copy(expected).convertToFormat(QImage.Format.Format_RGB32)
                    wanted.setDevicePixelRatio(1)
                    assert image == wanted, (i, image.size(), expected)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
            front.move(75, 155)
            front.setStyleSheet('background: #1675ae')
            wait(.2)
        print('PASS frozen frame/client crops, topmost titlebar hit, offscreen clipping and Escape clipboard at scale', os.environ['QT_SCALE_FACTOR'])
    finally:
        server.close()
        manager.terminate()
        manager.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--xvfb', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker()
    elif args.run and args.xvfb:
        for scale in ('1', '1.5'):
            isolated(args.xvfb.resolve(), ['env', 'QT_SCALE_FACTOR='+scale, sys.executable, __file__, '--worker'])
    else:
        parser.error('Pass --run --xvfb /path/to/Xvfb')
