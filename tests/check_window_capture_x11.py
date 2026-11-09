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
    from PySide6.QtCore import QPoint, QRect, Qt
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
        front = QWidget(None, Qt.WindowType.FramelessWindowHint)
        front.setStyleSheet('background: #1675ae')
        front.resize(190, 145)
        front.show()
        wait(.3)
        back.move(-30, 110)
        front.move(75, 155)
        front.raise_()
        wait(.4)
        def frame(widget):
            client = server.create_resource_object('window', int(widget.winId()))
            frame_window = client.query_tree().parent
            if frame_window.id == root.id:
                frame_window = client
            position = root.translate_coords(frame_window, 0, 0)
            size = frame_window.get_geometry()
            return QRect(position.x, position.y, size.width, size.height)
        raw = app.primaryScreen().grabWindow(0).toImage()
        lower = frame(back)
        assert lower.left() < 0 and lower.right() > 0, lower
        upper = frame(front)
        overlap = lower.intersected(upper)
        assert not overlap.isEmpty() and lower.left() < upper.left()
        for i, (point, rect) in enumerate(((overlap.center(), upper), (lower.intersected(raw.rect()).topLeft() + QPoint(12, 38), lower))):
            expected = rect.intersected(raw.rect())
            out = Path.home() / f'window-{i}.png'
            command = [sys.executable, ROOT/'runtime/menu_capture.py', '--notify', '--output', out]
            proc = subprocess.Popen(command, stdout=subprocess.PIPE)
            try:
                assert proc.stdout.readline() == b'FROZEN\n'
                wait(.4)
                # Change the underlying client after freezing. Output must still match every old pixel.
                front.setStyleSheet('background: #003300')
                wait(.1)
                def key(name):
                    code = server.keysym_to_keycode(XK.string_to_keysym(name))
                    for kind in (X.KeyPress, X.KeyRelease):
                        xtest.fake_input(server, kind, code)
                key('w')
                xtest.fake_input(server, X.MotionNotify, x=point.x(), y=point.y())
                xtest.fake_input(server, X.ButtonPress, 1)
                xtest.fake_input(server, X.ButtonRelease, 1)
                server.sync()
                wait(.15)
                key('Return')
                server.sync()
                assert proc.wait(timeout=5) == 0
                image = QImage(str(out)).convertToFormat(QImage.Format.Format_RGB32)
                wanted = raw.copy(expected).convertToFormat(QImage.Format.Format_RGB32)
                wanted.setDevicePixelRatio(1)
                assert image == wanted, (image.size(), expected)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
            front.setStyleSheet('background: #1675ae')
            wait(.2)
        print('PASS overlapping windows, clipped decorated frame and frozen pixels at scale', os.environ['QT_SCALE_FACTOR'])
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
