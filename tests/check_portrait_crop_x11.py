"""Private dialog drag/zoom/apply/cancel acceptance using a synthetic portrait."""
import argparse
import os
from pathlib import Path
import sys
from unittest.mock import patch
from x11_isolation import isolated


def worker():
    home=Path.home();assert home==Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from menu import start_menu as menu
    from PySide6.QtCore import QTimer,QPoint,Qt
    from PySide6.QtGui import QImage,QColor
    from PySide6.QtWidgets import QDialogButtonBox
    from PySide6.QtTest import QTest
    app=menu.QApplication([]);app.setQuitOnLastWindowClosed(False)
    image=QImage(600,300,QImage.Format.Format_RGB32);image.fill(QColor('red'))
    for y in range(300):
        for x in range(300,600):image.setPixelColor(x,y,QColor('blue'))
    path=home/'synthetic portrait.png';image.save(str(path));before=path.read_bytes()
    window=menu.StartMenu();window.show();QTest.qWait(150);results=[]
    def adjust():
        dialog=app.activeModalWidget();assert isinstance(dialog,menu.PortraitCropDialog)
        dialog.zoom.setFocus();QTest.keyClick(dialog.zoom,Qt.Key.Key_End)
        view=dialog.preview;QTest.mousePress(view,Qt.MouseButton.LeftButton,pos=QPoint(200,160))
        QTest.mouseMove(view,QPoint(80,160),30);QTest.mouseRelease(view,Qt.MouseButton.LeftButton,pos=QPoint(80,160))
        assert dialog.crop()['zoom']==4 and dialog.crop()['x']>.5,dialog.crop()
        results.append(dialog.crop());QTest.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
    with patch.object(menu.QFileDialog,'getOpenFileName',return_value=(str(path),'')):
        QTimer.singleShot(150,adjust);QTest.mouseClick(window.mascot,Qt.MouseButton.LeftButton)
    assert results and window.folder_settings.portrait_crop==results[0]
    assert window.mascot.pixmap().toImage().pixelColor(38,38)==QColor('blue')
    saved=window.folder_settings.path.read_bytes()
    def cancel():
        dialog=app.activeModalWidget();dialog.zoom.setValue(100)
        QTest.keyClick(dialog,Qt.Key.Key_Escape)
    with patch.object(menu.QFileDialog,'getOpenFileName',return_value=(str(path),'')):
        QTimer.singleShot(150,cancel);QTest.mouseClick(window.mascot,Qt.MouseButton.LeftButton)
    assert window.folder_settings.path.read_bytes()==saved and path.read_bytes()==before
    assert window.isVisible();window.close()
    reopened=menu.StartMenu();assert reopened.folder_settings.portrait_crop==results[0]
    assert reopened.mascot.pixmap().toImage().pixelColor(38,38)==QColor('blue');reopened.close()
    print('PASS actual crop drag, keyboard zoom, Apply, persisted pixels, Escape cancel and unchanged source image in private X11')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);a=p.parse_args()
    if a.worker:worker()
    elif a.run and a.xvfb:isolated(a.xvfb,[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else:p.error('Opt in with --run --xvfb PATH')
