"""Private keyboard search acceptance with synthetic desktop entries and fake launches."""
import argparse
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
from x11_isolation import isolated


def worker():
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from menu import start_menu as menu
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    import shiboken6
    app=menu.QApplication([]);app.setQuitOnLastWindowClosed(False);connection=display.Display()
    directory=Path.home()/'.local/share/applications';directory.mkdir(parents=True)
    entries=[]
    for ident,name,extra in [('a','Search Fixture',''),('b','Search Fixture Beta',''),('c','Other App','Keywords=Search;Fixture;\n'),('hidden','Search Fixture Hidden','Hidden=true\n')]:
        path=directory/(ident+'.desktop');path.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec=/usr/bin/true\n'+extra)
        entries.append(menu.Gio.DesktopAppInfo.new_from_filename(str(path)))
    def wait(t=.1):
        end=time.monotonic()+t
        while time.monotonic()<end:app.processEvents();time.sleep(.005)
    def key(name):
        code=connection.keysym_to_keycode(XK.string_to_keysym(name));xtest.fake_input(connection,X.KeyPress,code);xtest.fake_input(connection,X.KeyRelease,code);connection.sync();wait()
    with patch.object(menu,'applications',return_value=entries):window=menu.StartMenu()
    window.show();window.activateWindow();wait(.2);window.search.setFocus()
    try:
        for c in 'search':key(c)
        assert [window.list.item(i).text() for i in range(window.list.count())]==['Search Fixture','Search Fixture Beta','Other App']
        key('Down');assert window.list.hasFocus() and window.list.currentRow()==0
        key('Down');assert window.list.currentRow()==1,'Down intercepted instead of navigating results'
        key('Up');assert window.list.currentRow()==0
        with patch.object(window,'launch_item') as launch:
            # Search Enter uses the existing launch_item callback with the selected row.
            window.search.setFocus();key('Return')
            launch.assert_called_once_with(window.list.item(0))
        # QListWidget activation still routes through the existing safe dispatcher.
        with patch.object(menu.Gio.DesktopAppInfo,'launch',return_value=True) as launch:
            key('Down');key('Down');key('Return');assert launch.call_count==1
        window.show();window.activateWindow();wait();window.search.setFocus()
        window.search.setText('nothing-matches');wait();assert window.list.count()==0
        assert window.search_notice.isVisible() and 'No matching' in window.search_notice.text()
        with patch.object(menu.Gio.DesktopAppInfo,'launch') as launch:
            key('Down');assert window.search.hasFocus();key('Return');launch.assert_not_called()
        key('Escape');assert window.search.text()=='' and window.isVisible()
        window.search.setText('   ');wait();assert window.programs.text()=='All Programs'
        # New metadata enters the index only on catalog refresh, retaining current search.
        window.search.setText('new keyword')
        path=directory/'new.desktop';path.write_text('[Desktop Entry]\nType=Application\nName=Added app\nExec=/usr/bin/true\nKeywords=new;keyword;\n')
        new=menu.Gio.DesktopAppInfo.new_from_filename(str(path))
        with patch.object(menu,'applications',return_value=entries+[new]):window.refresh_catalog()
        assert window.list.count()==1 and window.list.item(0).text()=='Added app'
        print('PASS private X11: ranked results, hidden entries, Down/Up, search/list Enter, no-result no-op, Escape, empty query and rebuilt catalog index')
    finally:
        window.close();shiboken6.delete(window);connection.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);a=p.parse_args()
    if a.worker:worker()
    elif a.run and a.xvfb:isolated(a.xvfb.resolve(),[sys.executable,__file__,'--worker'])
    else:p.error('Pass --run --xvfb PATH')
