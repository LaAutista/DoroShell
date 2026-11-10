"""Combined installed search/folder interaction; URI launches always mocked."""
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
    for name in ('folder_cascade.py','app_search.py'):
        assert (installed/name).read_bytes()==Path(install.SOURCE,'menu',name).read_bytes()
        assert (home/'.local/share/doroshell/toolkit/menu'/name).read_bytes()==Path(install.SOURCE,'menu',name).read_bytes()
    assert (home/'.local/share/doroshell/toolkit/portable_settings.py').read_bytes()==Path(install.SOURCE,'portable_settings.py').read_bytes()
    sys.path.insert(0,str(installed))
    import start_menu as menu
    assert Path(menu.__file__).parent==installed
    from PySide6.QtWidgets import QToolButton,QPushButton
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    app=menu.QApplication([]);app.setQuitOnLastWindowClosed(False)
    docs=home/'Documents';nested=docs/'Nested & folder';nested.mkdir(parents=True);file=nested/'space & snow ☃.txt';file.write_text('fixture')
    entry=home/'.local/share/applications/combined-search-fixture.desktop'
    entry.write_text('[Desktop Entry]\nType=Application\nName=Combined Search Fixture\nExec=/usr/bin/true\nKeywords=Integration;\n')
    window=menu.StartMenu();window.show();QTest.qWait(150)
    window.search.setText('combined fixture')
    assert window.list.count()==1 and window.list.item(0).text()=='Combined Search Fixture'
    window.search.setFocus();QTest.keyClick(window.search,Qt.Key.Key_Down)
    assert window.list.hasFocus()
    selected=window.list.item(0).data(Qt.ItemDataRole.UserRole)
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
    assert window.search.text()=='combined fixture' and window.list.currentItem().data(Qt.ItemDataRole.UserRole)==selected
    with patch.object(menu.Gio.AppInfo,'launch_default_for_uri') as launch:
        QTimer.singleShot(150,lambda:QTest.keyClick(cascade,Qt.Key.Key_Escape))
        QTest.mouseClick(browse,Qt.MouseButton.LeftButton);QTest.qWait(200);launch.assert_not_called()
    window.show();QTest.qWait(100)
    button=next(b for b in window.findChildren(QPushButton,'folderLink') if b.text()=='Documents')
    with patch.object(menu.Gio.AppInfo,'launch_default_for_uri',return_value=True) as launch:
        QTest.mouseClick(button,Qt.MouseButton.LeftButton);launch.assert_called_once_with(docs.as_uri(),None)
    window.show();QTest.qWait(100)
    assert window.search.text()=='combined fixture' and window.list.currentItem().data(Qt.ItemDataRole.UserRole)==selected
    window.search.setFocus()
    with patch.object(window,'launch_item') as launch:
        QTest.keyClick(window.search,Qt.Key.Key_Return);launch.assert_called_once_with(window.list.currentItem())
    window.close();assert file.read_text()=='fixture'
    install.rollback(home)
    assert not (installed/'folder_cascade.py').exists()
    assert not (installed/'app_search.py').exists()
    assert not (home/'.local/share/doroshell/toolkit/portable_settings.py').exists()
    assert file.read_text()=='fixture'
    print('PASS combined helper packaging/rollback, preserved ranked search across cascades, search Enter after cascade; installed private browse arrow, lazy nested keyboard cascade, exact URI dispatch, Escape/no launch, unchanged left-click folder behavior and fixture')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);a=p.parse_args()
    if a.worker:worker()
    elif a.run and a.xvfb:isolated(a.xvfb,[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else:p.error('Opt in with --run --xvfb PATH')
