"""Real GIO install/remove notifications while Start remains open; private X11 only."""
import argparse
import os
from pathlib import Path
import sys
import time
from x11_isolation import isolated


def worker():
    home=Path.home()
    assert home==Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY'] and os.environ['DISPLAY']!=':0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from menu.start_menu import StartMenu
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    folder=home/'.local/share/applications';folder.mkdir(parents=True,exist_ok=True)
    a='doroshell-catalog-a.desktop';b='doroshell-catalog-b.desktop'
    def entry(key,name):
        (folder/key).write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec=/usr/bin/true\nCategories=System;\n')
    entry(a,'Doro catalog alpha')
    menu=StartMenu();menu.show();menu.category.setCurrentText('System');menu.search.setText('Doro catalog')
    def ids():return [menu.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(menu.list.count())]
    def until(condition):
        end=time.monotonic()+5
        while not condition() and time.monotonic()<end:app.processEvents();time.sleep(.025)
        assert condition(),ids()
    until(lambda:a in ids())
    menu.save_favorites([a,'missing-personal-choice.desktop'])
    before=menu.state.read_bytes()
    menu.list.setCurrentRow(ids().index(a))
    entry(b,'Doro catalog beta')
    until(lambda:b in ids())
    assert menu.list.currentItem().data(Qt.ItemDataRole.UserRole)==a
    assert menu.category.currentText()=='System' and menu.search.text()=='Doro catalog'
    (folder/a).unlink();until(lambda:a not in ids())
    assert menu.list.currentItem().data(Qt.ItemDataRole.UserRole)==b
    assert menu.state.read_bytes()==before and menu.favorites==[a,'missing-personal-choice.desktop']
    entry(a,'Doro catalog alpha');until(lambda:a in ids())
    assert menu.list.currentItem().data(Qt.ItemDataRole.UserRole)==b
    menu.search.clear();menu.category.setCurrentText('Home')
    assert ids()==[a]
    assert menu.state.read_bytes()==before
    menu.close()
    import shiboken6
    shiboken6.delete(menu)
    print('PASS GIO install/remove/reinstall notifications, preserved search/category/selection and untouched missing pins',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path)
    a=p.parse_args()
    if a.worker:worker()
    elif a.run and a.xvfb:isolated(a.xvfb,[sys.executable,str(Path(__file__).resolve()),'--worker'])
    else:p.error('Opt in with --run --xvfb PATH')
