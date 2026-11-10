"""Copy-only Start drags to the real native taskbar and PCManFM desktop; private X11."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary):
    home=Path.home()
    assert home==Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from PySide6.QtCore import QTimer,QPoint,QSettings,QMimeData,QUrl,Qt
    from PySide6.QtGui import QDrag
    from PySide6.QtWidgets import QApplication,QWidget
    from Xlib import display,X,XK
    from Xlib.ext import xtest
    from menu import start_menu as m
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    d=display.Display();root=d.screen().root
    assert not d.get_selection_owner(d.intern_atom('_NET_WM_CM_S0'))
    def wait(t):
        end=time.monotonic()+t
        while time.monotonic()<end:app.processEvents();time.sleep(.01)
    def event(kind,*args,**kwargs):xtest.fake_input(d,kind,*args,**kwargs);d.sync()
    desktop=home/'Desktop with spaces';desktop.mkdir()
    (home/'.config').mkdir(exist_ok=True)
    (home/'.config/user-dirs.dirs').write_text('XDG_DESKTOP_DIR="'+str(desktop)+'"\n')
    settings=home/'.config/pcmanfm-qt/lxqt/settings.conf';settings.parent.mkdir(parents=True)
    settings.write_text('[Desktop]\nDesktopShortcuts=\nWallpaperMode=none\nBgColor=#234567\n')
    applications=home/'.local/share/applications';applications.mkdir(parents=True)
    paths=[];apps=[]
    marker=home/'MUST NOT LAUNCH'
    for name in ("Alpha space & 'quote' %", 'Beta unpinned'):
        path=applications/(name+'.desktop')
        path.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nIcon=application-x-executable\nExec=/usr/bin/touch "'+str(marker)+'" %F\nCategories=Utility;\n')
        paths.append(path);apps.append(m.Gio.DesktopAppInfo.new_from_filename(str(path)))
    original={p:(p.read_bytes(),p.stat().st_mode&0o777) for p in paths}
    m.applications=lambda:apps
    conf=home/'panel.conf'
    conf.write_text('panels=panel1\n[panel1]\nplugins=taskbar\nposition=Bottom\nwidth=100\nwidth-percent=true\nreserve-space=false\npanelSize=40\ndoroshellTheme=true\n[taskbar]\ntype=taskbar\nbuttonStyle=Icon\nbuttonWidth=48\ngroupingEnabled=true\nshowOnlyOneDesktopTasks=false\n')
    def pins():
        cfg=QSettings(str(conf),QSettings.Format.IniFormat);cfg.sync();v=cfg.value('taskbar/doroshellPinned',[])
        return [v] if isinstance(v,str) and v else v or []
    def window(pid):
        clients=root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
        for wid in clients.value if clients else []:
            w=d.create_resource_object('window',int(wid));owner=w.get_full_property(d.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
            if owner and int(owner.value[0])==pid:return w
        raise AssertionError('Missing fixture window')
    log=open(home/'desktop.log','w')
    wm=subprocess.Popen(['openbox','--sm-disable'],stdout=log,stderr=log);wait(.4)
    pc=subprocess.Popen(['/usr/bin/pcmanfm-qt','--desktop','--profile=lxqt'],stdout=log,stderr=log)
    panel=subprocess.Popen([str(binary),'--config',str(conf)],stdout=log,stderr=log)
    menu=None
    try:
        wait(1.5)
        panel_window=window(panel.pid);pos=root.translate_coords(panel_window,0,0);g=panel_window.get_geometry()
        empty=QPoint(pos.x+g.width//2,pos.y+g.height//2)
        button=QPoint(pos.x+24,pos.y+g.height//2)
        menu=m.StartMenu();menu.save_favorites([apps[0].get_id()]);saved=menu.state.read_bytes()
        def show(category,query=''):
            menu.category.setCurrentText(category);menu.search.setText(query);menu.move(10,40);menu.show();wait(.2)
        def drag(point,cancel=False,raw=None,actions=Qt.DropAction.CopyAction,start=None):
            item=menu.list.item(0)
            if start is None:start=menu.list.viewport().mapToGlobal(menu.list.visualItemRect(item).center())
            source=None
            if raw:
                menu.hide();source=QWidget();source.setGeometry(600,50,80,80);source.show();wait(.2)
                start=source.mapToGlobal(source.rect().center())
            event(X.MotionNotify,x=start.x(),y=start.y());event(X.ButtonPress,1)
            for step in range(1,16):
                x=round(start.x()+(point.x()-start.x())*step/15);y=round(start.y()+(point.y()-start.y())*step/15)
                QTimer.singleShot(step*40,lambda x=x,y=y:event(X.MotionNotify,x=x,y=y))
            if cancel:
                key=d.keysym_to_keycode(XK.string_to_keysym('Escape'))
                QTimer.singleShot(650,lambda:event(X.KeyPress,key));QTimer.singleShot(670,lambda:event(X.KeyRelease,key))
            QTimer.singleShot(800,lambda:event(X.ButtonRelease,1))
            if raw:
                drag=QDrag(source);data=QMimeData();data.setUrls([raw]);drag.setMimeData(data)
                drag.exec(actions,actions)
            wait(1.2)
            if source:source.close()
        show('Home');drag(empty);assert pins()==[str(paths[0])],pins()
        show('All applications','Beta');drag(button);assert pins()==list(map(str,paths)),pins()
        show('Home');drag(button);assert pins()==list(map(str,paths)),'Duplicate pin'
        show('All applications','Beta');drag(QPoint(850,300),cancel=True)
        assert not list(desktop.glob('*.desktop')),'Canceled drag created a launcher'
        def finish_desktop_copy(target):
            wait(.3)
            if not target.exists():
                menus=[]
                for w in root.query_tree().children:
                    owner=w.get_full_property(d.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
                    types=w.get_full_property(d.intern_atom('_NET_WM_WINDOW_TYPE'),X.AnyPropertyType)
                    if w.get_attributes().map_state == X.IsViewable and owner and int(owner.value[0])==pc.pid and types and d.intern_atom('_NET_WM_WINDOW_TYPE_POPUP_MENU') in types.value:
                        menus.append(w)
                assert menus,'Expected native Copy here confirmation'
                popup=menus[0];position=root.translate_coords(popup,0,0);geometry=popup.get_geometry()
                event(X.MotionNotify,x=position.x+geometry.width//2,y=position.y+geometry.height//4)
                event(X.ButtonPress,1);event(X.ButtonRelease,1)
                deadline=time.monotonic()+4
                while not target.exists() and time.monotonic()<deadline:wait(.05)
            assert target.is_file(),'Desktop did not create a launcher'
        show('Home');drag(QPoint(850,300));finish_desktop_copy(desktop/paths[0].name)
        assert (desktop/paths[0].name).read_bytes()==original[paths[0]][0]
        show('All applications','Beta');drag(QPoint(850,450));finish_desktop_copy(desktop/paths[1].name)
        assert (desktop/paths[1].name).read_bytes()==original[paths[1]][0]
        before=pins()
        invalid=home/'not an application.txt';invalid.write_text('not a desktop entry')
        show('Home');drag(empty,raw=QUrl.fromLocalFile(str(invalid)))
        assert pins()==before,'Unsupported file was pinned'
        show('Home');drag(empty,raw=QUrl('https://example.invalid/app.desktop'))
        assert pins()==before,'Remote URL was pinned'
        third=applications/'Move only.desktop';third.write_bytes(paths[1].read_bytes())
        show('Home');drag(empty,raw=QUrl.fromLocalFile(str(third)),actions=Qt.DropAction.MoveAction)
        assert pins()==before,'Move-only source was accepted'
        assert menu.state.read_bytes()==saved,'External drag changed Start pins'
        assert not marker.exists(),'Dragging accidentally launched an app'
        for path,(data,mode) in original.items():assert path.read_bytes()==data and path.stat().st_mode&0o777==mode
        assert third.is_file(),'Move-only drop removed the source'
        menu.hide()
        # Exercise the normal one-shot launcher, including deferred X11 URI transfer.
        child_code = """
import json,sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from menu import start_menu as m
app=QApplication([])
entry=m.Gio.DesktopAppInfo.new_from_filename(sys.argv[1])
m.applications=lambda:[entry]
w=m.StartMenu();w.category.setCurrentText('All applications');w.move(10,40)
w.exit_on_hide=True;w.show()
def ready():
 p=w.list.viewport().mapToGlobal(w.list.visualItemRect(w.list.item(0)).center())
 Path(sys.argv[2]).write_text(json.dumps([p.x(),p.y()]))
QTimer.singleShot(200,ready)
app.exec()
"""
        for destination in (empty,QPoint(850,550)):
            coords=home/'child-coordinates.json';coords.unlink(missing_ok=True)
            child=subprocess.Popen([sys.executable,'-c',child_code,str(third),str(coords)],stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+4
                while not coords.exists() and time.monotonic()<deadline:wait(.05)
                assert coords.exists(),'One-shot launcher did not open'
                drag(destination,start=QPoint(*json.loads(coords.read_text())))
                if destination==empty:
                    before=[*before,str(third)];assert pins()==before,pins()
                else:
                    finish_desktop_copy(desktop/third.name)
                    assert (desktop/third.name).read_bytes()==third.read_bytes()
                deadline=time.monotonic()+4
                while child.poll() is None and time.monotonic()<deadline:wait(.05)
                assert child.poll()==0,'One-shot launcher did not exit after drop'
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=5)
        panel.terminate();panel.wait(timeout=5)
        panel=subprocess.Popen([str(binary),'--config',str(conf)],stdout=log,stderr=log);wait(1)
        assert panel.poll() is None and pins()==before,'Pins did not persist'
        print('PASS Start pinned/search/all-app exports, empty/existing taskbar targets, deduplication, desktop copies, special filenames, cancellation, unsupported/move-only rejection, source preservation and panel-restart pin persistence',flush=True)
    finally:
        if menu:menu.close()
        for process in (panel,pc,wm):
            if process.poll() is None:process.terminate();process.wait(timeout=5)
        d.close();log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);p.add_argument('--binary',type=Path,required=True)
    a=p.parse_args()
    if a.worker:worker(a.binary)
    elif a.run and a.xvfb:isolated(a.xvfb,[sys.executable,str(Path(__file__).resolve()),'--worker','--binary',str(a.binary.resolve())])
    else:p.error('Opt in with --run --xvfb PATH')
