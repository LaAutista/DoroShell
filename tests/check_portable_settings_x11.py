"""Private installed settings UI, export/import preview cancellation and rollback."""
import argparse
import os
from pathlib import Path
import sys
from unittest.mock import patch
from x11_isolation import isolated


def worker():
    home=Path.home()
    assert home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import install
    install.install(home,True,None)
    toolkit=home/'.local/share/doroshell/toolkit';sys.path.insert(0,str(toolkit))
    import settings,portable_settings as ps
    from PySide6.QtWidgets import QApplication,QPushButton,QMessageBox,QFileDialog
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    assert Path(ps.__file__).parent==toolkit
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    store=ps.Store(home);store.base.mkdir(parents=True,exist_ok=True)
    private=store.base/'folders.json'
    private.write_bytes(ps.encode({'version':1,'folders':[],'portrait':'/private/portrait.png','portraitCrop':{'x':.7,'y':.5,'zoom':2}}))
    before=private.read_bytes();export=home/'portable.json';errors=[];done=[]
    window=settings.Settings(home);window.show()
    def checks():
        dialog=app.activeModalWidget()
        try:
            buttons={b.text():b for b in dialog.findChildren(QPushButton)}
            with patch.object(QFileDialog,'getSaveFileName',return_value=(str(export),'')):
                QTest.mouseClick(buttons['Export portable preferences…'],Qt.MouseButton.LeftButton)
            assert b'/private/' not in export.read_bytes()
            value=ps.decode(export.read_bytes());value['preferences']['primary']='lockscreen';export.write_bytes(ps.encode(value))
            with patch.object(QFileDialog,'getOpenFileName',return_value=(str(export),'')),patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Cancel):
                QTest.mouseClick(buttons['Preview and import…'],Qt.MouseButton.LeftButton)
            assert private.read_bytes()==before and not (store.base/'session-button.json').exists()
            with patch.object(QFileDialog,'getOpenFileName',return_value=(str(export),'')),patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Apply),patch.object(QMessageBox,'information'):
                QTest.mouseClick(buttons['Preview and import…'],Qt.MouseButton.LeftButton)
            assert ps.decode((store.base/'session-button.json').read_bytes())['action']=='lockscreen'
            assert ps.decode(private.read_bytes())['portraitCrop']['x']==.7
            with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes),patch.object(QMessageBox,'information'):
                QTest.mouseClick(buttons['Restore last import'],Qt.MouseButton.LeftButton)
            assert private.read_bytes()==before and not (store.base/'session-button.json').exists()
            done.append(True)
        except Exception as error:errors.append(error)
        finally:dialog.reject()
    QTimer.singleShot(100,checks);QTest.mouseClick(window.portable,Qt.MouseButton.LeftButton)
    if errors:raise errors[0]
    assert done;window.close()
    install.rollback(home);assert private.read_bytes()==before
    print('PASS installed private preferences dialog: path-free export, preview Cancel, apply, preserved portrait/crop, exact rollback; no live changes')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);a=p.parse_args()
    if a.worker:worker()
    elif a.run and a.xvfb:isolated(a.xvfb,[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else:p.error('Opt in with --run --xvfb PATH')
