"""Check native ScreenGrab displays and copies the overlay's final pixels on private X11."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated

ROOT = Path(__file__).resolve().parents[1]


def worker(binary):
    assert os.environ.get('DOROSHELL_TEST_DISPLAY') == os.environ['DISPLAY']
    assert Path.home() == Path(os.environ['TMPDIR']).parent
    sys.path.insert(0,str(ROOT))
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    from runtime.menu_capture import FrozenCapture
    setup=[sys.executable,ROOT/'setup.py','screenshots','--home',Path.home()]
    installer_env=dict(os.environ,HOME=str(Path.home()/'installer'))

    subprocess.run(setup+['--apply','--native-preview',binary],env=installer_env,check=True)
    subprocess.run(setup+['--apply'],env=installer_env,check=True)
    app=QApplication([])
    app.setQuitOnLastWindowClosed(False)
    def wait(seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            app.processEvents()
            time.sleep(.01)
    wm=subprocess.Popen(['openbox','--sm-disable'])
    connection=display.Display()
    pid=None
    try:
        wait(.5)
        source=QImage(400,300,QImage.Format.Format_RGB32)
        source.fill(QColor('#d9c5ed'))
        for y in range(180, 192):
            for x in range(140, 164):
                value = 40 + 120*(x % 2)
                source.setPixelColor(x, y, QColor(value, value, value))
        overlay=FrozenCapture(source,QRect(0,0,400,300), [QRect(20,70,260,180)])
        overlay.show()
        wait(.15)
        def drag(a,b):
            QTest.mousePress(overlay,Qt.MouseButton.LeftButton,pos=QPoint(*a))
            QTest.mouseRelease(overlay,Qt.MouseButton.LeftButton,pos=QPoint(*b))
        overlay.actions['Window'].click()
        QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=QPoint(120,130))
        overlay.set_tool('Arrow')
        overlay.stroke_width.setValue(7)
        drag((45,105),(200,170))
        expected=overlay.rendered_image()
        for tool, x in (('Blur', 140), ('Pixelate', 152)):
            overlay.set_tool(tool)
            drag((x, 180), (x+7, 187))
        for y in range(180, 188):
            for x in (*range(140, 148), *range(152, 160)):
                expected.setPixelColor(x-20, y-70, QColor(100, 100, 100))
        font = QFont('DejaVu Serif', 17)
        font.setBold(True)
        font.setItalic(True)
        ink = QColor('#123477')
        overlay.strokes.append(('Text', [QPoint(65, 220)], 'Import', ink, 3, font))
        with QPainter(expected) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            reference = QFont(font)
            reference.setPixelSize(round(17*overlay.logicalDpiY()/72))
            painter.setFont(reference)
            painter.setPen(ink)
            painter.drawText(QPoint(45, 150), 'Import')
        assert overlay.rendered_image()==expected
        assert expected.size().toTuple()==(260,180)
        assert expected.pixelColor(25,35)!=source.pixelColor(45,105)
        app.clipboard().setText('native copy sentinel')
        overlay.actions['Open in ScreenGrab'].click()
        assert overlay.selected_image()==expected
        wait(.6)
        clients=connection.screen().root.get_full_property(connection.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
        for wid in clients.value:
            window=connection.create_resource_object('window',wid)
            prop=window.get_full_property(connection.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
            if prop and Path(f'/proc/{prop.value[0]}/exe').resolve()==overlay.native_binary.resolve():
                pid=int(prop.value[0])
                window.set_input_focus(X.RevertToParent,X.CurrentTime)
                break
        assert pid, 'No native import window appeared'
        # Copy from the native window itself; an overlay clipboard copy cannot satisfy this.
        assert app.clipboard().text()=='native copy sentinel'
        for key,kind in [('Control_L',X.KeyPress),('c',X.KeyPress),('c',X.KeyRelease),('Control_L',X.KeyRelease)]:
            xtest.fake_input(connection,kind,connection.keysym_to_keycode(XK.string_to_keysym(key)))
        connection.sync()
        wait(.3)
        copied=app.clipboard().image()
        assert copied.size()==expected.size()
        assert all(copied.pixelColor(x,y)==expected.pixelColor(x,y)
                   for x in range(expected.width()) for y in range(expected.height()))
    finally:
        if pid:
            import signal
            os.kill(pid,signal.SIGTERM)
        connection.close()
        wm.terminate()
        wm.wait(timeout=5)
    subprocess.run(setup+['--rollback'],env=installer_env,check=True)
    assert not overlay.native_binary.exists()
    print('PASS native ScreenGrab imported, displayed and copied every annotated pixel including blur/pixelate regions; rollback removed the private executable')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--xvfb',type=Path)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:
        worker(args.binary.resolve())
    elif args.run and args.xvfb:
        isolated(args.xvfb.resolve(),[sys.executable,Path(__file__).resolve(),'--worker','--binary',args.binary.resolve()])
    else:
        parser.error('Pass --run --xvfb /path/to/Xvfb --binary /path/to/import-enabled/screengrab')
