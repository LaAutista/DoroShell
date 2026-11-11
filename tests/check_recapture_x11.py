"""Exercise one-shot recapture on a synthetic desktop and authenticated private X11."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

from x11_isolation import isolated


def worker():
    assert os.environ['DISPLAY'] == os.environ['DOROSHELL_TEST_DISPLAY']
    assert Path.home() == Path(os.environ['TMPDIR']).parent
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from PySide6.QtCore import QPoint, Qt, QTimer
    from PySide6.QtGui import QColor, QCursor, QImage, QPainter, QPixmap
    from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialogButtonBox,
                                   QSpinBox, QWidget)
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    from runtime.menu_capture import FrozenCapture, edit_capture, publish, transfer_png
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    server = display.Display()
    screen = app.primaryScreen()
    area = screen.geometry()
    background = QWidget(None, Qt.WindowType.FramelessWindowHint)
    background.setGeometry(area)
    background.setStyleSheet('background: #123456')
    # Native cursor pixels and an asymmetric hotspot, independent of Qt UI scale.
    sprite = QImage(11, 9, QImage.Format.Format_ARGB32_Premultiplied)
    sprite.fill(Qt.GlobalColor.transparent)
    sprite.setPixelColor(0, 0, QColor('yellow'))
    sprite.setPixelColor(7, 2, QColor('red'))
    sprite.setPixelColor(4, 6, QColor('white'))
    sprite.setPixelColor(5, 6, QColor(64, 128, 240, 128))
    pixmap = QPixmap.fromImage(sprite)
    background.setCursor(QCursor(pixmap, 4, 6))
    background.show()
    app.processEvents()
    old = screen.grabWindow(0).toImage()
    app.clipboard().setText('recapture sentinel')
    def key(name):
        code = server.keysym_to_keycode(XK.string_to_keysym(name))
        for kind in (X.KeyPress, X.KeyRelease):
            xtest.fake_input(server, kind, code)
        server.sync()
    for cancel, pointer in ((True, False), (False, False), (False, True)):
        background.setStyleSheet('background: #123456')
        editor = FrozenCapture(old, area)
        editor.strokes.append(('Redact', [QPoint(32, 80), QPoint(70, 110)], '', QColor(), 3))
        before = editor.rendered_image()
        errors = []
        seen = set()
        started = time.monotonic()
        def step():
            # Schedule the options action separately so this timer can service its modal loop.
            try:
                active = app.activeModalWidget()
                if time.monotonic()-started > 8:
                    raise AssertionError((cancel, pointer, seen, active, app.activeWindow()))
                if active is None or not active.isActiveWindow():
                    return
                title = active.windowTitle()
                if active is editor and 'started' not in seen:
                    seen.add('started')
                    QTimer.singleShot(0, editor.actions['New capture…'].click)
                elif title == 'New capture' and 'options' not in seen:
                    seen.add('options')
                    delay = active.findChild(QSpinBox)
                    scope = active.findChild(QComboBox)
                    check = active.findChild(QCheckBox)
                    assert (scope.currentIndex(), delay.value(), check.isChecked()) == (0, 0, False)
                    scope.setCurrentIndex(int(pointer))
                    check.setChecked(pointer)
                    delay.setValue(1)
                    active.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
                elif title == 'Capture countdown' and 'countdown' not in seen:
                    seen.add('countdown')
                    assert not editor.isVisible()
                    if cancel:
                        key('Escape')
                    else:
                        # Change pixels well after the old editor was hidden.
                        QTimer.singleShot(400, lambda: background.setStyleSheet('background: #194f86'))
                        xtest.fake_input(server, X.MotionNotify, x=21, y=26)
                        server.sync()
                elif isinstance(active, FrozenCapture) and 'countdown' in seen and 'finished' not in seen:
                    if cancel:
                        assert active is editor and active.rendered_image() == before
                        key('Escape')
                    else:
                        assert active is not editor and time.monotonic()-started >= 1
                        key('Return')
                    seen.add('finished')

            except Exception as exc:
                errors.append(exc)
                timer.stop()
                app.exit(1)
        timer = QTimer()
        timer.timeout.connect(step)
        timer.start(40)
        result = edit_capture(editor)
        timer.stop()
        if errors:
            raise errors[0]
        assert 'finished' in seen and app.clipboard().text() == 'recapture sentinel'
        if cancel:
            assert result is None
            continue
        native = server.screen().root.get_geometry()
        expected = QImage(native.width, native.height, QImage.Format.Format_RGB32)
        expected.fill(QColor('#194f86'))
        if pointer:
            with QPainter(expected) as painter:
                painter.drawImage(QPoint(21-4, 26-6), sprite)
        actual = result.convertToFormat(expected.format())
        assert actual == expected, (pointer, actual.size(), expected.size())
        output = Path.home()/f'new-{pointer}.png'
        publish(result, app, output)
        assert QImage(str(output)).convertToFormat(expected.format()) == expected
        if pointer:
            helper = Path(__file__).resolve().parents[1]/'runtime/menu_capture.py'
            transfer_png(result, [sys.executable, str(helper), '--clipboard-owner'], b'OWNED\n')
            assert app.clipboard().image().convertToFormat(expected.format()) == expected
            app.clipboard().setText('replacement')
    server.close()
    print('PASS native private countdown cancellation, fresh timed pixels, hotspot and exact PNG/clipboard at scale',
          os.environ['QT_SCALE_FACTOR'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--xvfb', type=Path)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        assert os.environ['DISPLAY'] == os.environ['DOROSHELL_TEST_DISPLAY']
        wm = subprocess.Popen(['openbox', '--sm-disable'])
        try:
            time.sleep(.4)
            worker()
        finally:
            wm.terminate()
            wm.wait(timeout=5)
    elif args.run and args.xvfb:
        for scale in ('1', '1.5'):
            isolated(args.xvfb.resolve(), ['env', 'QT_SCALE_FACTOR='+scale, sys.executable, __file__, '--worker'])
    else:
        parser.error('Pass --run --xvfb /path/to/Xvfb')
