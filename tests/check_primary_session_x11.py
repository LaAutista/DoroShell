"""Private Qt pointer/keyboard acceptance; session dispatch is always mocked."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock,patch
from x11_isolation import isolated


def worker():
    home=Path.home()
    assert home==Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from menu import start_menu as menu
    from PySide6.QtCore import QTimer,QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton,QMessageBox
    app=menu.QApplication([]);app.setQuitOnLastWindowClosed(False)
    window=menu.StartMenu();window.show();QTest.qWait(200)
    fixture=Mock();fixture.launch.return_value=True
    with patch.object(menu,'desktop_entry',return_value=fixture):
        options=next(b for b in window.findChildren(QPushButton) if b.text()=='Menu options…')
        submenu=next(a.menu() for a in options.menu().actions() if a.text()=='Primary session button')
        submenu.popup(window.mapToGlobal(QPoint(100,100)))
        submenu.setActiveAction(submenu.actions()[0]);QTest.keyClick(submenu,menu.Qt.Key.Key_Down)
        QTest.keyClick(submenu,menu.Qt.Key.Key_Return);QTest.qWait(100)
        assert window.primary_action=='reboot' and window.session_button.text()=='Restart…'
        fixture.launch.assert_not_called()
        dialogs=[]
        def cancel():
            dialog=app.activeModalWidget();assert isinstance(dialog,QMessageBox)
            assert dialog.standardButton(dialog.defaultButton())==QMessageBox.StandardButton.Cancel
            dialogs.append(dialog.windowTitle());QTest.keyClick(dialog,menu.Qt.Key.Key_Escape)
        QTimer.singleShot(150,cancel)
        QTest.mouseClick(window.session_button,menu.Qt.MouseButton.LeftButton)
        assert dialogs==['Restart?'];fixture.launch.assert_not_called()
        assert window.isVisible() and not window.launching
        window.close()
        reopened=menu.StartMenu();assert reopened.primary_action=='reboot'
        assert any(a.data()=='shutdown' and a.isVisible() for a in reopened.power_menu.actions())
        reopened.close();fixture.launch.assert_not_called()
    print('PASS private primary-button keyboard selection, persistent restart choice, real Cancel-default confirmation and Escape; zero session launches')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);a=p.parse_args()
    if a.worker:worker()
    elif a.run and a.xvfb:isolated(a.xvfb,[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else:p.error('Opt in with --run --xvfb PATH')
