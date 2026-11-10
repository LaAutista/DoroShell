"""Exercise real native Pin/Unpin menus on an authenticated private desktop."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary):
    home=Path.home()
    assert home == Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY'] and os.environ['DISPLAY']!=':0'
    from PySide6.QtWidgets import QApplication,QWidget
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QPixmap,QColor,QIcon
    from Xlib import display,X,XK
    from Xlib.ext import xtest
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    server=display.Display();root=server.screen().root
    def wait(t):
        until=time.monotonic()+t
        while time.monotonic()<until:app.processEvents();time.sleep(.015)
    def key(name):
        code=server.keysym_to_keycode(XK.string_to_keysym(name))
        xtest.fake_input(server,X.KeyPress,code);xtest.fake_input(server,X.KeyRelease,code);server.sync()
    entries=home/'.local/share/applications';entries.mkdir(parents=True)
    paths=[];icons=[]
    for identity,color in [('DoroPinA','#01e3c7'),('DoroPinB','#e3c701')]:
        pix=QPixmap(28,28);pix.fill(QColor(color));icon=home/(identity+'.png');pix.save(str(icon));icons.append(QIcon(pix))
        entry=entries/(identity+'.desktop');entry.write_text('[Desktop Entry]\nType=Application\nName='+identity+'\nStartupWMClass='+identity+'\nIcon='+str(icon)+'\nExec=/usr/bin/true\n')
        paths.append(str(entry))
    originals={p:Path(p).read_bytes() for p in paths}
    conf=home/'panel.conf'
    conf.write_text('panels=panel1\n[panel1]\nplugins=taskbar\nposition=Bottom\nwidth=900\nwidth-percent=false\nreserve-space=false\npanelSize=40\n[taskbar]\ntype=taskbar\nbuttonStyle=Icon\nbuttonWidth=48\ngroupingEnabled=true\nshowOnlyOneDesktopTasks=false\n')
    def config():return QSettings(str(conf),QSettings.Format.IniFormat)
    cfg=config();cfg.setValue('taskbar/doroshellPinned',paths);cfg.sync();del cfg
    def pins():
        cfg=config();cfg.sync();value=cfg.value('taskbar/doroshellPinned',[])
        return [value] if isinstance(value,str) and value else value
    wm=subprocess.Popen(['openbox','--sm-disable'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    panel=None;windows=[]
    log=open(home/'panel.log','w')
    def start_panel():
        process=subprocess.Popen([str(binary),'--config',str(conf)],stdout=log,stderr=log);wait(1.3);assert process.poll() is None
        return process
    def panel_window():
        prop=root.get_full_property(server.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
        for wid in prop.value if prop else []:
            w=server.create_resource_object('window',int(wid));pid=w.get_full_property(server.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
            if pid and int(pid.value[0])==panel.pid and w.get_geometry().width>200:return w
        raise AssertionError('Panel window unavailable')
    def center(color):
        w=panel_window();im=app.primaryScreen().grabWindow(w.id).toImage()
        pts=[(x,y) for x in range(im.width()) for y in range(im.height()) if im.pixelColor(x,y)==QColor(color)]
        if not pts:return None
        pos=root.translate_coords(w,0,0)
        return pos.x+sum(x for x,y in pts)//len(pts),pos.y+sum(y for x,y in pts)//len(pts)
    def menu(color,label,choose=False,closed=False):
        point=center(color);assert point,(color,label)
        if windows:
            prop=server.create_resource_object('window',int(windows[0].winId())).get_full_property(server.intern_atom('_NET_WM_ICON_GEOMETRY'),X.AnyPropertyType)
            if prop is not None:
                x,y,w,h=map(int,prop.value);point=(x+w//2,y+h//2)
        xtest.fake_input(server,X.MotionNotify,x=point[0],y=point[1]);xtest.fake_input(server,X.ButtonPress,3);xtest.fake_input(server,X.ButtonRelease,3);server.sync();wait(.3)
        out=Path(__file__).resolve().parents[1]/'previews';out.mkdir(exist_ok=True)
        app.primaryScreen().grabWindow(0).save(str(out/('pin-menu-'+label+'.png')))
        if choose:
            key('Down')
            if closed:key('Down')
            key('Return')
        else:key('Escape')
        wait(.6)
    def fixture():
        w=QWidget();w.setWindowTitle('Disposable pin fixture');w.setWindowIcon(icons[0]);w.setGeometry(200,150,200,140);w.show()
        server.create_resource_object('window',int(w.winId())).set_wm_class('DoroPinA','DoroPinA');server.sync();windows.append(w);wait(.5)
        return w
    def alive():
        for w in windows:
            assert w.isVisible() and server.create_resource_object('window',int(w.winId())).get_attributes().map_state==X.IsViewable
    try:
        wait(.5);panel=start_panel()
        menu('#01e3c7','closed-unpin',True,True)
        assert pins()==[paths[1]] and center('#01e3c7') is None,pins()
        a=fixture();menu('#01e3c7','single-pin',True);assert pins()==[paths[1],paths[0]],pins();alive()
        menu('#01e3c7','single-unpin',True);assert pins()==[paths[1]],pins();assert center('#01e3c7');alive()
        b=fixture();menu('#01e3c7','group-pin',True);assert pins()==[paths[1],paths[0]],pins();alive()
        menu('#01e3c7','group-unpin',True);assert pins()==[paths[1]],pins();assert center('#01e3c7');alive()
        panel.terminate();panel.wait(timeout=5);panel=start_panel()
        assert pins()==[paths[1]] and center('#01e3c7');alive()
        duplicate=entries/'ambiguous.desktop';duplicate.write_bytes(Path(paths[0]).read_bytes());wait(.5)
        menu('#01e3c7','ambiguous-no-pin');assert pins()==[paths[1]];alive()
        duplicate.unlink()
        # Ungrouped tasks still allow removing an existing pin; adding requires grouping.
        panel.terminate();panel.wait(timeout=5)
        cfg=config();cfg.setValue('taskbar/doroshellPinned',paths);cfg.setValue('taskbar/groupingEnabled',False);cfg.sync();del cfg
        panel=start_panel();b.close();windows.remove(b);wait(.4)
        menu('#01e3c7','ungrouped-unpin',True);assert pins()==[paths[1]],pins();alive()
        menu('#01e3c7','ungrouped-disabled-pin');assert pins()==[paths[1]];alive()
        a.close();windows.remove(a);wait(.4);assert center('#01e3c7') is None
        for p,data in originals.items():assert Path(p).read_bytes()==data
        assert panel.poll() is None
        print('PASS closed/single/grouped/ungrouped pin contexts, order, persistence, live fixture survival and untouched desktop entries',flush=True)
    except Exception:
        log.flush();print((home/'panel.log').read_text(),flush=True)
        raise
    finally:
        for w in windows:w.close()
        if panel and panel.poll() is None:panel.terminate();panel.wait(timeout=5)
        wm.terminate();wm.wait(timeout=5);log.close();server.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--xvfb',type=Path);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true')
    a=p.parse_args()
    if a.worker:worker(a.binary.resolve())
    elif a.run and a.xvfb:isolated(a.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker','--binary',str(a.binary.resolve())])
    else:p.error('Opt in with --run --xvfb PATH')
