"""Pinned launchers survive task filters without accidentally launching duplicates."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary, evidence):
    home=Path.home()
    assert home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    from PySide6.QtWidgets import QApplication,QWidget
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QPixmap,QColor
    from Xlib import display,X,XK,protocol
    from Xlib.ext import xtest
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    d=display.Display();root=d.screen().root
    evidence.mkdir(parents=True,exist_ok=True)
    def wait(seconds=.6):
        until=time.monotonic()+seconds
        while time.monotonic()<until:app.processEvents();time.sleep(.01)
    def prop(w,name):
        p=w.get_full_property(d.intern_atom(name),X.AnyPropertyType)
        return list(p.value) if p else []
    def request(w,name,*values):
        root.send_event(protocol.event.ClientMessage(window=w,client_type=d.intern_atom(name),data=(32,list(values)+[0]*(5-len(values)))),event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask);d.sync();wait()
    def desktop(n):request(root,'_NET_CURRENT_DESKTOP',n,X.CurrentTime)
    def move(xw,n):
        request(xw,'_NET_WM_DESKTOP',n,2)
        assert prop(xw,'_NET_WM_DESKTOP')==[n]
    def key(name):
        code=d.keysym_to_keycode(XK.string_to_keysym(name));xtest.fake_input(d,X.KeyPress,code);xtest.fake_input(d,X.KeyRelease,code);d.sync();wait(.2)
    entries=home/'.local/share/applications';entries.mkdir(parents=True)
    marker=home/'launcher-invoked'
    paths=[]
    for name,color in [('FilterPin','#01e3c7'),('FilterLoose','#e3c701')]:
        icon=home/(name+'.png');pix=QPixmap(28,28);pix.fill(QColor(color));pix.save(str(icon))
        path=entries/(name+'.desktop');path.write_text(f'[Desktop Entry]\nType=Application\nName={name}\nStartupWMClass={name}\nIcon={icon}\nExec=/usr/bin/touch {marker}\n');paths.append(str(path))
    original={p:Path(p).read_bytes() for p in paths}
    rc=home/'rc.xml';rc.write_text('<openbox_config xmlns="http://openbox.org/3.4/rc"><desktops><number>2</number></desktops></openbox_config>')
    conf=home/'panel.conf';conf.write_text('panels=panel1\n[panel1]\nplugins=taskbar\nposition=Bottom\nwidth=900\nwidth-percent=false\nreserve-space=false\npanelSize=40\n[taskbar]\ntype=taskbar\nbuttonStyle=Icon\nbuttonWidth=48\ngroupingEnabled=true\niconByClass=true\nshowOnlyOneDesktopTasks=true\ncloseOnMiddleClick=true\nraiseOnCurrentDesktop=false\n')
    cfg=QSettings(str(conf),QSettings.Format.IniFormat);cfg.setValue('taskbar/doroshellPinned',[paths[0]]);cfg.sync()
    log=open(evidence/'panel.log','w');wm=subprocess.Popen(['openbox','--sm-disable','--config-file',str(rc)],stdout=log,stderr=log)
    keys=subprocess.Popen(['lxqt-globalkeysd'],stdout=log,stderr=log)
    panel=None;windows=[]
    def start():
        p=subprocess.Popen([str(binary),'--config',str(conf)],stdout=log,stderr=log);wait(1.3);assert p.poll() is None;return p
    def fixture(name):
        w=QWidget();w.setWindowTitle(name);w.setGeometry(100,100,200,100);w.show();app.sync()
        xw=d.create_resource_object('window',int(w.winId()));xw.set_wm_class(name,name);d.sync();windows.append(w);wait();return w,xw
    def image():
        for wid in prop(root,'_NET_CLIENT_LIST'):
            w=d.create_resource_object('window',int(wid))
            if prop(w,'_NET_WM_PID')==[panel.pid] and w.get_geometry().width>200:
                pos=root.translate_coords(w,0,0)
                return app.primaryScreen().grabWindow(w.id).toImage(),pos
        raise AssertionError('missing panel')
    def point(color):
        im,pos=image();pixels=[(x,y) for x in range(im.width()) for y in range(im.height()) if im.pixelColor(x,y)==QColor(color)]
        return (pos.x+sum(x for x,y in pixels)//len(pixels),pos.y+sum(y for x,y in pixels)//len(pixels)) if pixels else None
    def pin_image():
        # Layout position may shift when the placeholder disappears; compare the pin.
        im,pos=image();center=point('#01e3c7');assert center
        return im.copy(center[0]-pos.x-20,0,40,im.height())
    def click(button=1):
        p=point('#01e3c7');assert p,'filtered pin disappeared'
        xtest.fake_input(d,X.MotionNotify,x=p[0],y=p[1]);xtest.fake_input(d,X.ButtonPress,button);xtest.fake_input(d,X.ButtonRelease,button);d.sync();wait()
    def hidden_checks(xw):
        assert point('#01e3c7'),'filtered pin disappeared'
        assert point('#e3c701') is None,'unpinned filtered task stayed visible'
        active=prop(root,'_NET_ACTIVE_WINDOW');desk=prop(root,'_NET_CURRENT_DESKTOP')
        click(2);click(4);click(5)
        assert prop(root,'_NET_ACTIVE_WINDOW')==active and prop(root,'_NET_CURRENT_DESKTOP')==desk,'incidental input activated a filtered window'
        assert xw.id in prop(root,'_NET_CLIENT_LIST') and not marker.exists(),'closed hidden window or launched duplicate'
    try:
        wait();panel=start();assert point('#01e3c7')
        xtest.fake_input(d,X.MotionNotify,x=900,y=500);d.sync();wait()
        closed=pin_image();closed.save(str(evidence/'closed-before.png'))
        w,xw=fixture('FilterPin');u,xu=fixture('FilterLoose')
        assert point('#01e3c7') and point('#e3c701')
        move(xw,1);move(xu,1)
        image()[0].save(str(evidence/'workspace-filtered.png'))
        hidden_checks(xw)
        # An intentional click follows the existing window to its workspace.
        click();assert prop(root,'_NET_CURRENT_DESKTOP')==[1] and prop(root,'_NET_ACTIVE_WINDOW')==[xw.id]
        assert not marker.exists()
        desktop(0);hidden_checks(xw)
        # Filtered context offers Show existing window, not launch/close actions.
        click(3);image()[0].save(str(evidence/'filtered-context.png'));key('Down');key('Return');wait()
        assert prop(root,'_NET_CURRENT_DESKTOP')==[1] and prop(root,'_NET_ACTIVE_WINDOW')==[xw.id] and not marker.exists()
        desktop(0)
        meta=d.keysym_to_keycode(XK.string_to_keysym('Super_L'));xtest.fake_input(d,X.KeyPress,meta);key('1');xtest.fake_input(d,X.KeyRelease,meta);d.sync();wait()
        assert prop(root,'_NET_CURRENT_DESKTOP')==[1] and prop(root,'_NET_ACTIVE_WINDOW')==[xw.id],'Meta+1 failed to reuse filtered window'
        move(xw,0);move(xu,0);desktop(0);assert point('#01e3c7') and point('#e3c701')
        second,xsecond=fixture('FilterPin')
        move(xw,1);move(xsecond,1);move(xu,1);hidden_checks(xw)
        # Changing desktops reveals both at once: regroup must restore its window ID.
        desktop(1)
        request(xu,'_NET_ACTIVE_WINDOW',2,X.CurrentTime,0)
        xtest.fake_input(d,X.KeyPress,meta);key('1');xtest.fake_input(d,X.KeyRelease,meta);d.sync();wait()
        assert prop(root,'_NET_ACTIVE_WINDOW')[0] in (xw.id,xsecond.id),'Meta+1 lost representative after all-filtered to multi-visible'
        assert not marker.exists()
        move(xw,0);move(xsecond,0);move(xu,0);desktop(0)
        second.close();windows.remove(second);app.sync();wait()
        # Minimized-only filtering keeps the pin while normal running tasks disappear.
        panel.terminate();panel.wait(timeout=5);cfg.setValue('taskbar/showOnlyMinimizedTasks',True);cfg.sync();panel=start()
        hidden_checks(xw)
        w.showMinimized();u.showMinimized();app.sync();wait();assert point('#01e3c7') and point('#e3c701')
        w.showNormal();u.showNormal();app.sync();wait();hidden_checks(xw)
        # Backend's existing preference moves a minimized window here when enabled.
        panel.terminate();panel.wait(timeout=5);cfg.setValue('taskbar/showOnlyMinimizedTasks',False);cfg.setValue('taskbar/showOnlyCurrentScreenTasks',False);cfg.setValue('taskbar/raiseOnCurrentDesktop',True);cfg.sync();panel=start()
        desktop(0);w.showMinimized();app.sync();wait()
        assert prop(xw,'WM_STATE')[0]==3,'raise preference fixture is not minimized'
        move(xw,1);move(xu,1);desktop(0)
        assert prop(root,'_NET_CURRENT_DESKTOP')==[0] and prop(xw,'WM_STATE')[0]==3
        click()
        assert prop(root,'_NET_CURRENT_DESKTOP')==[0] and prop(xw,'_NET_WM_DESKTOP')==[0] and prop(root,'_NET_ACTIVE_WINDOW')==[xw.id], (prop(root,'_NET_CURRENT_DESKTOP'),prop(xw,'_NET_WM_DESKTOP'),prop(root,'_NET_ACTIVE_WINDOW'),xw.id)
        assert not marker.exists()
        # Closing the last filtered window returns a real launchable pin.
        move(xw,1);xw.set_wm_hints(flags=257,input=1);d.sync();wait();w.close();windows.remove(w);app.sync();wait();assert point('#01e3c7')
        xtest.fake_input(d,X.MotionNotify,x=900,y=500);d.sync();wait()
        image()[0].save(str(evidence/'closed-after-filtered.png'))
        pin_image().save(str(evidence/'closed-after.png'))
        assert pin_image()==closed,'closed pin retained stale running/checked/urgent appearance'
        click();assert marker.exists(),'closed pin did not launch through GIO'
        assert all(Path(p).read_bytes()==data for p,data in original.items())
        assert panel.poll() is None
        print('PASS workspace/minimized filters, pinned persistence, unpinned hiding, click/context/Meta+1 existing-window activation, raise preference, safe middle/wheel, transitions and final launch',flush=True)
    finally:
        for w in windows:w.close()
        for p in (panel,keys,wm):
            if p and p.poll() is None:p.terminate();p.wait(timeout=5)
        log.close();d.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--xvfb',type=Path);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');a=p.parse_args()
    if a.worker:worker(a.binary.resolve(),a.evidence.resolve())
    elif a.run and a.xvfb:isolated(a.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker','--binary',str(a.binary.resolve()),'--evidence',str(a.evidence.resolve())])
    else:p.error('Opt in with --run --xvfb PATH')
