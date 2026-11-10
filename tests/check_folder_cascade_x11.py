"""Private pointer/keyboard folder cascades; URI launches always mocked."""
import argparse
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
from x11_isolation import isolated


def worker():
    home=Path.home();assert home==Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import install
    install.install(home,True,None)
    installed=home/'.local/share/lxqt-comfort'
    assert (installed/'folder_cascade.py').read_bytes()==Path(install.SOURCE,'menu/folder_cascade.py').read_bytes()
    sys.path.insert(0,str(installed))
    import start_menu as menu
    assert Path(menu.__file__).parent==installed
    from PySide6.QtWidgets import QToolButton,QPushButton
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    app=menu.QApplication([]);app.setQuitOnLastWindowClosed(False)
    docs=home/'Documents';nested=docs/'Nested & folder';nested.mkdir(parents=True);file=nested/'space & snow ☃.txt';file.write_text('fixture')
    window=menu.StartMenu();window.show();QTest.qWait(150)
    browse=next(b for b in window.findChildren(QToolButton) if b.accessibleName()=='Browse Documents contents')
    cascade=browse.menu();errors=[];states=[];deadline=time.monotonic()+5
    def fail(error):
        errors.append(error)
        for child in cascade.submenus:child.close()
        cascade.close();window.close()
    def nested_ready(child):
        try:
            if child.job['process'] is not None:
                assert time.monotonic()<deadline;QTimer.singleShot(20,lambda:nested_ready(child));return
            assert child.isVisible();action=next(a for a in child.actions() if a.data()==file.as_uri())
            states.append('nested loaded');child.setActiveAction(action);QTest.keyClick(child,Qt.Key.Key_Return)
        except Exception as error:fail(error)
    def ready():
        try:
            if cascade.job['process'] is not None:
                assert time.monotonic()<deadline;QTimer.singleShot(20,ready);return
            assert cascade.isVisible() and window.isVisible()
            action=next(a for a in cascade.actions() if a.data()==nested.as_uri());child=action.menu()
            assert child.job['process'] is None;states.append('lazy parent loaded')
            cascade.setActiveAction(action);QTest.keyClick(cascade,Qt.Key.Key_Right)
            QTimer.singleShot(50,lambda:nested_ready(child))
        except Exception as error:fail(error)
    with patch.object(menu.Gio.AppInfo,'launch_default_for_uri',return_value=True) as launch:
        QTimer.singleShot(100,ready);QTest.mouseClick(browse,Qt.MouseButton.LeftButton)
        while len(states)<2 and not errors and time.monotonic()<deadline:QTest.qWait(20)
        if errors:raise errors[0]
        assert states==['lazy parent loaded','nested loaded'],states
        launch.assert_called_once_with(file.as_uri(),None)
    window.show();QTest.qWait(100)
    with patch.object(menu.Gio.AppInfo,'launch_default_for_uri') as launch:
        QTimer.singleShot(150,lambda:QTest.keyClick(cascade,Qt.Key.Key_Escape))
        QTest.mouseClick(browse,Qt.MouseButton.LeftButton);QTest.qWait(200);launch.assert_not_called()
    window.show();QTest.qWait(100)
    button=next(b for b in window.findChildren(QPushButton,'folderLink') if b.text()=='Documents')
    with patch.object(menu.Gio.AppInfo,'launch_default_for_uri',return_value=True) as launch:
        QTest.mouseClick(button,Qt.MouseButton.LeftButton);launch.assert_called_once_with(docs.as_uri(),None)
    window.close();assert file.read_text()=='fixture'
    install.rollback(home)
    assert not (installed/'folder_cascade.py').exists()
    assert file.read_text()=='fixture'
    print('PASS installed private browse arrow, lazy nested keyboard cascade, exact URI dispatch, Escape/no launch, unchanged left-click folder behavior and fixture')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);a=p.parse_args()
    if a.worker:worker()
    elif a.run and a.xvfb:isolated(a.xvfb,[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else:p.error('Opt in with --run --xvfb PATH')
