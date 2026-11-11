"""Regression: launcher identity and icons on an authenticated disposable X11 panel."""
import argparse
import os
import signal
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary, evidence):
    home = Path.home()
    assert home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY'] == os.environ['DOROSHELL_TEST_DISPLAY'] != ':0'
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QPixmap, QColor, QIcon
    from Xlib import display, X
    app = QApplication([])
    server = display.Display()
    root = server.screen().root
    def wait():
        until = time.monotonic() + .7
        while time.monotonic() < until:
            app.processEvents(); time.sleep(.01)
    entries = home/'.local/share/applications'
    entries.mkdir(parents=True)
    paths = []
    for name, cls, color in [('org.example.Manager', '', '#01e3c7'), ('wine-editor', 'editor.exe', '#e3c701'), ('instance-tool', 'unique-instance', '#e301c7'), ('ambiguous-a', 'shared.exe', '#550011'), ('ambiguous-b', 'shared.exe', '#115500')]:
        icon = home/(name+'.png'); pix = QPixmap(28,28); pix.fill(QColor(color)); pix.save(str(icon))
        path = entries/(name+'.desktop')
        path.write_text(f'[Desktop Entry]\nType=Application\nName={name}\nExec=/usr/bin/false\nIcon={icon}\nStartupWMClass={cls}\n')
        paths.append(str(path))
    conf = home/'panel.conf'
    conf.write_text('panels=panel1\n[panel1]\nplugins=taskbar\nposition=Bottom\nwidth=900\nwidth-percent=false\nreserve-space=false\npanelSize=40\n[taskbar]\ntype=taskbar\nbuttonStyle=Icon\nbuttonWidth=48\ngroupingEnabled=true\niconByClass=true\nshowOnlyOneDesktopTasks=false\n')
    cfg=QSettings(str(conf),QSettings.Format.IniFormat);cfg.setValue('taskbar/doroshellPinned',paths);cfg.sync()
    before={p:Path(p).read_bytes() for p in paths}
    wm=subprocess.Popen(['openbox','--sm-disable'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    panel=None;windows=[]
    evidence.mkdir(parents=True,exist_ok=True)
    log=open(evidence/'identity-panel.log','w')
    def fixture(cls, instance='fixture', appid=None):
        w=QWidget();w.setWindowTitle('Disposable identity fixture');w.show();windows.append(w)
        xw=server.create_resource_object('window',int(w.winId()));xw.set_wm_class(instance,cls)
        if appid:xw.change_property(server.intern_atom('_GTK_APPLICATION_ID'),server.intern_atom('UTF8_STRING'),8,appid.encode())
        server.sync();wait();return w,xw
    def panel_image():
        prop=root.get_full_property(server.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
        for wid in prop.value:
            w=server.create_resource_object('window',int(wid));pid=w.get_full_property(server.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
            if pid and int(pid.value[0])==panel.pid and w.get_geometry().width>200:
                pos=root.translate_coords(w,0,0)
                return app.primaryScreen().grabWindow(w.id).toImage(),pos.x
        raise AssertionError('panel missing')
    def icon_x(color):
        im,x=panel_image();points=[i for i in range(im.width()) for j in range(im.height()) if im.pixelColor(i,j)==QColor(color)]
        assert points,('missing icon',color)
        return x+sum(points)//len(points)
    def geometry(xw):
        p=xw.get_full_property(server.intern_atom('_NET_WM_ICON_GEOMETRY'),X.AnyPropertyType)
        assert p is not None
        return list(p.value)
    def matches(xw,color):
        x,y,w,h=geometry(xw);return x<=icon_x(color)<x+w
    try:
        wait();panel=subprocess.Popen([str(binary),'--config',str(conf)],stdout=log,stderr=log);wait();wait()
        pin_x=icon_x('#01e3c7')
        w,xw=fixture('ModOrganizer','ModOrganizer-core','org.example.Manager')
        panel_image()[0].save(str(evidence/'identity-appid.png'))
        assert matches(xw,'#01e3c7'),('app-ID window did not join pin',geometry(xw),pin_x)
        w2,xw2=fixture('ModOrganizer','ModOrganizer-core','org.example.Manager')
        assert geometry(xw)==geometry(xw2),'multiple windows did not share pin'
        w2.close();wait()
        wine,xwine=fixture('editor.exe');assert matches(xwine,'#e3c701'),'StartupWMClass mismatch'
        ins,xins=fixture('GenericWrapper','unique-instance');assert matches(xins,'#e301c7'),'instance mismatch'
        amb,xamb=fixture('shared.exe');assert not matches(xamb,'#550011') and not matches(xamb,'#115500'),'ambiguous class guessed'
        basename,xb=fixture('org.example.Manager')
        assert matches(xb,'#01e3c7'),'desktop basename mismatch'
        kde,xk=fixture('KdeWrapper')
        xk.change_property(server.intern_atom('_KDE_NET_WM_DESKTOP_FILE'),server.intern_atom('UTF8_STRING'),8,paths[0].encode())
        server.sync();wait();assert matches(xk,'#01e3c7'),'desktop-file property mismatch'
        # Explicit app ID outranks a contradictory wrapper class.
        xw.set_wm_class('fixture','editor.exe');server.sync();wait();assert matches(xw,'#01e3c7')
        # Late identity changes regroup, including removing an ID.
        xw.change_property(server.intern_atom('_GTK_APPLICATION_ID'),server.intern_atom('UTF8_STRING'),8,b'wine-editor');server.sync();wait();assert matches(xw,'#e3c701')
        xw.delete_property(server.intern_atom('_GTK_APPLICATION_ID'));xw.set_wm_class('unique-instance','GenericWrapper');server.sync();wait();assert matches(xw,'#e301c7')
        # Missing theme/class icon must retain a real window icon.
        fallback,xf=fixture('NoSuchThemeIcon')
        pix=QPixmap(28,28);pix.fill(QColor('#1278ef'));fallback.setWindowIcon(QIcon(pix));app.sync()
        # Qt publishes the new X11 icon asynchronously; allow both clients to repaint.
        wait();wait();wait()
        assert matches(xf,'#1278ef')
        panel_image()[0].save(str(evidence/'identity-fallback.png'))
        panel.terminate();panel.wait(timeout=5)
        cfg.setValue('taskbar/iconByClass',False);cfg.sync()
        panel=subprocess.Popen([str(binary),'--config',str(conf)],stdout=log,stderr=log);wait();wait()
        assert matches(xf,'#1278ef'),'native icon lost in window-icon mode'
        # Openbox actively publishes its own generic _NET_WM_ICON whenever it is
        # absent. Pause only this disposable WM to test a truly missing icon.
        wm.send_signal(signal.SIGSTOP)
        try:
            xwine.delete_property(server.intern_atom('_NET_WM_ICON'))
            xwine.set_wm_hints(flags=1,input=1);server.sync();wait();wait()
            assert xwine.get_full_property(server.intern_atom('_NET_WM_ICON'),X.AnyPropertyType) is None
            assert matches(xwine,'#e3c701'),'launcher fallback missing in window-icon mode'
        finally:
            wm.send_signal(signal.SIGCONT)
        for p,data in before.items():assert Path(p).read_bytes()==data
        assert panel.poll() is None
        print('PASS app-ID/desktop-file/basename grouping, multiple windows, StartupWMClass, instance, ambiguity, precedence, late changes, both icon modes, missing-native fallback, unchanged launchers')
    finally:
        for w in windows:w.close()
        if panel and panel.poll() is None:panel.terminate();panel.wait(timeout=5)
        wm.terminate();wm.wait(timeout=5);log.close();server.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--xvfb',type=Path);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true')
    a=p.parse_args()
    if a.worker:worker(a.binary.resolve(),a.evidence.resolve())
    elif a.run and a.xvfb:isolated(a.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker','--binary',str(a.binary.resolve()),'--evidence',str(a.evidence.resolve())])
    else:p.error('Opt in with --run --xvfb PATH')
