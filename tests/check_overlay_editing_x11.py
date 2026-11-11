"""Exercise crop editing, annotation history and real save-dialog cancellation on private X11."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker():
    assert os.environ['DISPLAY'] == os.environ['DOROSHELL_TEST_DISPLAY'] != ':0'
    assert Path.home() == Path(os.environ['TMPDIR']).parent
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from PySide6.QtCore import QPoint, QRect, QTimer, Qt
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    from runtime.menu_capture import FrozenCapture
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    server = display.Display()
    wm = subprocess.Popen(['openbox', '--sm-disable'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def wait(seconds=.15):
        end = time.monotonic()+seconds
        while time.monotonic()<end:
            app.processEvents()
            time.sleep(.01)
    def event(kind, *args, **kwargs):
        xtest.fake_input(server, kind, *args, **kwargs)
        server.sync()
    def key(name):
        code = server.keysym_to_keycode(XK.string_to_keysym(name))
        event(X.KeyPress, code); event(X.KeyRelease, code)
    def click(widget):
        point = widget.mapToGlobal(widget.rect().center())
        event(X.MotionNotify, x=point.x(), y=point.y())
        event(X.ButtonPress, 1); event(X.ButtonRelease, 1); wait()
    def drag(start, end):
        event(X.MotionNotify, x=start[0], y=start[1]); event(X.ButtonPress, 1)
        for i in range(1, 9):
            event(X.MotionNotify, x=round(start[0]+(end[0]-start[0])*i/8), y=round(start[1]+(end[1]-start[1])*i/8)); wait(.015)
        event(X.ButtonRelease, 1); wait()
    image = QImage(1024,768,QImage.Format.Format_RGB32)
    image.fill(QColor('#c4d9e9'))
    for y in range(764, 768):
        for x in range(1020, 1024):
            image.setPixelColor(x, y, QColor(x-800, y-600, x+y-1700))
    overlay = FrozenCapture(image, QRect(0,0,1024,768))
    try:
        wait(.3); overlay.show(); wait(.4)
        app.clipboard().setText('editing sentinel')
        drag((200,200),(500,450))
        assert overlay.pixel_rect() == QRect(200,200,301,251)
        drag((500,450),(540,480))
        assert overlay.pixel_rect() == QRect(200,200,341,281)
        drag((350,350),(380,370))
        assert overlay.pixel_rect() == QRect(230,220,341,281)
        key('Right')
        alt = server.keysym_to_keycode(XK.string_to_keysym('Alt_L'))
        shift = server.keysym_to_keycode(XK.string_to_keysym('Shift_L'))
        event(X.KeyPress, alt)
        key('Down')
        event(X.KeyRelease, alt)
        event(X.KeyPress, shift)
        key('Left')
        wait()
        assert overlay.pixel_rect() == QRect(244, 220, 341, 296), overlay.pixel_rect()
        assert not overlay.lens_rect().isEmpty()
        assert overlay.rendered_image() == image.copy(overlay.pixel_rect())
        event(X.KeyRelease, shift)
        wait()
        assert overlay.lens_rect().isEmpty()
        crop = QRect(overlay.pixel_rect())
        click(overlay.tool_buttons['Pen'])
        spin = overlay.stroke_width
        spin.setFocus()
        assert spin.hasFocus()
        width = spin.value()
        key('Up')
        wait()
        assert spin.value() == width + 1 and overlay.pixel_rect() == crop

        click(overlay.tool_buttons['Redact'])
        drag((270,270),(330,320))
        marked = overlay.rendered_image()
        assert marked.pixelColor(60,70) == QColor('black')
        click(overlay.actions['Undo'])
        assert overlay.rendered_image().pixelColor(60,70) == QColor('#c4d9e9')
        click(overlay.actions['Redo'])
        assert overlay.rendered_image() == marked
        seen = []
        def cancel_save():
            dialog = app.activeModalWidget()
            seen.append(isinstance(dialog,QFileDialog))
            key('Escape')
        QTimer.singleShot(400,cancel_save)
        click(overlay.actions['Save…'])
        assert seen == [True] and overlay.isVisible() and overlay.selected_image() is None
        output = Path.home()/'annotated crop.png'
        def finish_save():
            dialog = app.activeModalWidget()
            assert isinstance(dialog,QFileDialog)
            field = dialog.findChild(QLineEdit,'fileNameEdit')
            assert field is not None
            field.setText(str(output)); field.setFocus(); key('Return')
        QTimer.singleShot(400,finish_save)
        click(overlay.actions['Save…'])
        assert QImage(str(output)) == marked and overlay.selected_image() == marked
        assert app.clipboard().text() == 'editing sentinel'
        overlay.close()
        full = FrozenCapture(image,QRect(0,0,1024,768)); full.show(); wait(.2)
        key('Return'); wait()
        assert full.selected_image() == image
        full.close()
        cancelled = FrozenCapture(image, QRect(0, 0, 1024, 768))
        cancelled.show()
        wait()
        drag((1020, 764), (1022, 766))
        crop = QRect(1020, 764, 3, 3)
        assert cancelled.pixel_rect() == crop
        button = cancelled.actions['Copy']
        button.setFocus()
        assert button.hasFocus()
        ctrl = server.keysym_to_keycode(XK.string_to_keysym('Control_L'))
        event(X.KeyPress, ctrl)
        event(X.KeyPress, shift)
        key('Left')
        wait()
        assert cancelled.pixel_rect() == QRect(1020, 764, 2, 3)
        for _ in range(4):
            key('Left')
            key('Up')
        wait()
        assert cancelled.pixel_rect() == QRect(1020, 764, 1, 1)
        for _ in range(5):
            key('Right')
            key('Down')
        wait()
        expected = QRect(1020, 764, 4, 4)
        assert cancelled.pixel_rect() == expected
        assert not cancelled.lens_rect().isEmpty()
        assert cancelled.rendered_image() == image.copy(expected)
        event(X.KeyRelease, shift)
        event(X.KeyRelease, ctrl)
        key('Escape')
        wait()
        assert not cancelled.isVisible() and cancelled.selected_image() is None
        assert app.clipboard().text() == 'editing sentinel'
        print('PASS real X11 crop resize/move, redaction, Undo/Redo, actual save-dialog cancel/save, exact PNG pixels, full-desktop Enter and unchanged clipboard',flush=True)
    finally:
        overlay.close(); wm.terminate(); wm.wait(timeout=5); server.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true'); parser.add_argument('--worker',action='store_true')
    parser.add_argument('--xvfb',type=Path)
    args=parser.parse_args()
    if args.worker: worker()
    elif args.run and args.xvfb:
        isolated(args.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else: parser.error('Pass --run --xvfb /path/to/Xvfb')
