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
    from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen
    from PySide6.QtWidgets import (QApplication, QFileDialog, QLineEdit, QCheckBox, QDoubleSpinBox,
                                   QFontComboBox, QPushButton)
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    from runtime.menu_capture import FrozenCapture, transfer_png
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
    for y in range(420, 432):
        for x in range(444, 492):
            value = 40 + 120*(x % 2)
            image.setPixelColor(x, y, QColor(value, value, value))
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
        click(overlay.tool_buttons['Edit marks'])
        drag((285, 285), (245, 285))
        # Moving 40 left clips the redaction at the crop boundary.
        marked = image.copy(crop)
        for y in range(270, 321):
            for x in range(crop.left(), 291):
                marked.setPixelColor(x-crop.x(), y-crop.y(), QColor('black'))
        assert overlay.rendered_image() == marked
        key('Delete')
        wait()
        assert overlay.rendered_image() == image.copy(crop)
        click(overlay.actions['Undo'])
        assert overlay.rendered_image() == marked
        click(overlay.actions['Redo'])
        assert overlay.rendered_image() == image.copy(crop)
        click(overlay.actions['Undo'])
        assert overlay.rendered_image() == marked
        click(overlay.tool_buttons['Line'])
        event(X.KeyPress, shift)
        drag((310, 360), (410, 364))
        event(X.KeyRelease, shift)
        assert overlay.strokes[-1][1] == [QPoint(310, 360), QPoint(410, 360)]
        click(overlay.tool_buttons['Number'])
        drag((380, 400), (380, 400))
        click(overlay.tool_buttons['Edit marks'])
        drag((380, 400), (390, 410))
        assert overlay.strokes[-1][1] == [QPoint(390, 410)]
        def change_number():
            event(X.KeyPress, ctrl_key)
            key('a')
            event(X.KeyRelease, ctrl_key)
            key('7')
            key('Return')
        ctrl_key = server.keysym_to_keycode(XK.string_to_keysym('Control_L'))
        QTimer.singleShot(200, change_number)
        key('F2')
        wait()
        assert overlay.strokes[-1][2] == '7'
        key('Delete')
        wait()
        click(overlay.actions['Undo'])
        assert overlay.strokes[-1][2] == '7'
        # Independent reference raster, in desktop coordinates clipped to the crop.
        with QPainter(marked) as painter:
            painter.translate(-crop.topLeft())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            ink = QColor('#f04761')
            painter.setPen(QPen(ink, width+1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(310, 360, 410, 360)
            font = QFont(overlay.font())
            font.setPixelSize(14)
            font.setBold(True)
            painter.setFont(font)
            size = QFontMetrics(font).height()+10
            circle = QRect(0, 0, size, size)
            circle.moveCenter(QPoint(390, 410))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(ink)
            painter.drawEllipse(circle)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, '7')
        assert overlay.rendered_image() == marked
        for tool, x in (('Pixelate', 444), ('Blur', 468)):
            click(overlay.tool_buttons[tool])
            drag((x, 420), (x+7, 427))
        click(overlay.tool_buttons['Edit marks'])
        drag((449, 425), (461, 425))
        key('Delete')
        wait()
        click(overlay.actions['Undo'])
        for y in range(420, 428):
            for x in (*range(456, 464), *range(468, 476)):
                marked.setPixelColor(x-crop.x(), y-crop.y(), QColor(100, 100, 100))
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
        # Cancel with a selected annotation on the private clipboard sentinel.
        editor = FrozenCapture(image, image.rect())
        editor.show()
        wait()
        click(editor.tool_buttons['Redact'])
        drag((250, 250), (280, 280))
        def point_click(x, y):
            event(X.MotionNotify, x=x, y=y)
            event(X.ButtonPress, 1)
            event(X.ButtonRelease, 1)
            wait()

        def enter_text(value):
            # The text editor runs its own modal event loop.
            event(X.KeyPress, ctrl)
            key('a')
            event(X.KeyRelease, ctrl)
            for letter in value:
                key(letter)
            key('Return')

        click(editor.tool_buttons['Text'])
        QTimer.singleShot(200, lambda: enter_text('old'))
        point_click(255, 270)
        old_text = editor.rendered_image()
        click(editor.tool_buttons['Edit marks'])
        point_click(260, 266)
        assert editor.selected_mark == 1  # Text over the filled redaction.
        edited_family = None
        def set_style():
            nonlocal edited_family
            form = app.activeModalWidget()
            family = form.findChild(QFontComboBox)
            family.setCurrentIndex((family.currentIndex()+1) % family.count())
            edited_family = family.currentFont().family()
            form.findChild(QDoubleSpinBox).setValue(19)
            for check in form.findChildren(QCheckBox):
                check.setChecked(True)
            return form
        def cancel_style():
            set_style()
            key('Escape')
        QTimer.singleShot(200, cancel_style)
        key('F2')
        wait()
        assert editor.isVisible() and editor.rendered_image() == old_text
        def accept_style():
            form = set_style()
            swatch = next(b for b in form.findChildren(QPushButton) if b.text().startswith('#'))
            def choose_blue():
                picker = app.activeModalWidget()
                picker.setCurrentColor(QColor('#1648ad'))
                picker.accept()
            QTimer.singleShot(150, choose_blue)
            swatch.click()
            text_field = form.findChildren(QLineEdit)[0]
            text_field.setFocus()
            enter_text('new')
        QTimer.singleShot(200, accept_style)
        click(editor.color_button)
        wait()
        edited = editor.rendered_image()
        assert editor.strokes[1][2] == 'new' and edited != old_text
        style = editor.strokes[1][5]
        assert style.family() == edited_family and style.pointSizeF() == 19
        assert style.bold() and style.italic() and editor.strokes[1][3] == QColor('#1648ad')
        click(editor.actions['Undo'])
        assert editor.rendered_image() == old_text
        click(editor.actions['Redo'])
        assert editor.rendered_image() == edited
        point_click(313, 300)
        assert editor.selected_mark is None
        drag((254, 275), (264, 285))
        click(editor.tool_buttons['Line'])
        drag((300, 300), (360, 320))
        click(editor.tool_buttons['Number'])
        point_click(360, 320)
        click(editor.tool_buttons['Blur'])
        drag((444, 420), (455, 431))
        key('Escape')
        wait()
        assert editor.selected_image() is None and not editor.isVisible()
        assert app.clipboard().text() == 'editing sentinel'
        helper = Path(__file__).resolve().parents[1]/'runtime/menu_capture.py'
        transfer_png(overlay.selected_image(), [sys.executable, str(helper), '--clipboard-owner'], b'OWNED\n')
        assert app.clipboard().image().convertToFormat(marked.format()) == marked
        app.clipboard().setText('replacement')
        wait()
        print('PASS real X11 crop resize/move, redaction, snapped line, numbered stamp, blur/pixelate regions, Undo/Redo, text font and color editing, save-dialog cancel/save, exact edited PNG and clipboard pixels, full-desktop Enter and Escape preservation',flush=True)
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
