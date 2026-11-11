# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native tray popup lifetime, focus and attention checks on private X11."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary,evidence,case):
    home=Path.home()
    assert home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    from PySide6.QtWidgets import QApplication,QLineEdit
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QColor
    from Xlib import display,X,XK
    from Xlib.ext import xtest
    import dbus,dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    bus=dbus.SessionBus();assert not bus.name_has_owner('org.kde.StatusNotifierWatcher')
    calls=[]
    class Item(dbus.service.Object):
        def __init__(self):
            self.status='Passive'
            self.name=dbus.service.BusName('org.kde.StatusNotifierItem.Lifecycle',bus)
            super().__init__(bus,'/StatusNotifierItem')
        @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
        def Get(self,interface,key):
            pixels=bytes([255,237,1,201])*24*24
            pix=dbus.Array([dbus.Struct((dbus.Int32(24),dbus.Int32(24),dbus.ByteArray(pixels)),signature='iiay')],signature='(iiay)')
            values={'Category':'ApplicationStatus','Id':'Lifecycle','Title':'LifecycleFixture','Status':self.status,'WindowId':dbus.Int32(0),'ItemIsMenu':False,'IconName':'','IconThemePath':'','OverlayIconName':'','AttentionIconName':'','AttentionMovieName':'','IconPixmap':pix,'OverlayIconPixmap':dbus.Array([],signature='(iiay)'),'AttentionIconPixmap':pix,'ToolTip':dbus.Struct(('',pix,'LifecycleFixture','Disposable item'),signature='sa(iiay)ss')}
            if key=='Menu' and case=='context':return dbus.ObjectPath('/Menu')
            if key not in values:raise dbus.exceptions.DBusException('Unavailable',name='org.freedesktop.DBus.Error.UnknownProperty')
            return values[key]
        @dbus.service.signal('org.kde.StatusNotifierItem',signature='s')
        def NewStatus(self,status):pass
        @dbus.service.method('org.kde.StatusNotifierItem',in_signature='ii',out_signature='')
        def Activate(self,x,y):calls.append('activate')
        @dbus.service.method('org.kde.StatusNotifierItem',in_signature='ii',out_signature='')
        def ContextMenu(self,x,y):calls.append('context')
    class TestMenu(dbus.service.Object):
        def __init__(self):super().__init__(bus,'/Menu')
        @dbus.service.method('com.canonical.dbusmenu',in_signature='iias',out_signature='u(ia{sv}av)')
        def GetLayout(self,parent,depth,names):
            child=dbus.Struct((dbus.Int32(1),dbus.Dictionary({'label':'Synthetic menu action','enabled':True,'visible':True},signature='sv'),dbus.Array([],signature='v')),signature='ia{sv}av')
            root=dbus.Struct((dbus.Int32(0),dbus.Dictionary({'children-display':'submenu'},signature='sv'),dbus.Array([child],signature='v')),signature='ia{sv}av')
            return dbus.UInt32(1),root
        @dbus.service.method('com.canonical.dbusmenu',in_signature='i',out_signature='b')
        def AboutToShow(self,item):return False
        @dbus.service.method('com.canonical.dbusmenu',in_signature='isvu',out_signature='')
        def Event(self,item,event,data,timestamp):
            if event=='clicked':calls.append('menu-clicked')
        @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
        def Get(self,interface,key):return {'Version':dbus.UInt32(3),'TextDirection':'ltr','Status':'normal','IconThemePath':dbus.Array([],signature='s')}[key]
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    d=display.Display();root=d.screen().root
    evidence.mkdir(parents=True,exist_ok=True)
    def wait(seconds=.4):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            app.processEvents()
            while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
            time.sleep(.01)
    def key(name):
        k=d.keysym_to_keycode(XK.string_to_keysym(name));xtest.fake_input(d,X.KeyPress,k);xtest.fake_input(d,X.KeyRelease,k);d.sync();wait(.15)
    def click(x,y):
        xtest.fake_input(d,X.MotionNotify,x=x,y=y);xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait()
    def windows(pid):
        found=[]
        def scan(w):
            try:
                p=w.get_full_property(d.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
                if p and int(p.value[0])==pid and w.get_attributes().map_state==X.IsViewable:found.append(w)
                for child in w.query_tree().children:scan(child)
            except Exception:pass
        scan(root);return found
    conf=home/'panel.conf';conf.write_text('panels=panel1\n[panel1]\nplugins=statusnotifier\nposition=Bottom\nwidth=900\nwidth-percent=false\nreserve-space=false\npanelSize=40\nhidable='+('true' if case=='popup' else 'false')+'\nanimationTime=0\n[statusnotifier]\ntype=statusnotifier\nalignment=Right\ndoroshellPopup=true\nattentionPeriod=1\n')
    cfg=QSettings(str(conf),QSettings.Format.IniFormat)
    cfg.setValue('statusnotifier/'+('autoHideList' if case=='attention' else 'hideList'),['LifecycleFixture']);cfg.sync();del cfg
    log=open(evidence/'panel.log','w');wm=subprocess.Popen(['openbox','--sm-disable'],stdout=log,stderr=log)
    panel=None;item=None;menu=None;fields=[]
    def panel_window():return next(w for w in windows(panel.pid) if w.get_geometry().width>200)
    def panel_visible_height():
        panel_rect=panel_window();pos=root.translate_coords(panel_rect,0,0)
        return max(0,min(768,pos.y+panel_rect.get_geometry().height)-max(0,pos.y))
    def popups():return [w for w in windows(panel.pid) if w.get_wm_name()=='Hidden icons']
    def open_popup():
        p=panel_window();pos=root.translate_coords(p,0,0);g=p.get_geometry()
        xtest.fake_input(d,X.MotionNotify,x=pos.x+g.width-12,y=767);d.sync();wait(.6)
        p=panel_window();pos=root.translate_coords(p,0,0);g=p.get_geometry();assert panel_visible_height()>=36,'panel did not reveal'
        click(pos.x+g.width-12,pos.y+g.height//2)
        assert len(popups())==1,'one arrow click did not open popup'
        popup=popups()[0];pos=root.translate_coords(popup,0,0);g=popup.get_geometry()
        xtest.fake_input(d,X.MotionNotify,x=pos.x+g.width//2,y=pos.y+g.height//2);d.sync();wait(1.6)
        return popup
    def panel_has_icon():
        im=app.primaryScreen().grabWindow(panel_window().id).toImage()
        return any(im.pixelColor(x,y)==QColor('#ed01c9') for x in range(im.width()) for y in range(im.height()))
    try:
        wait();panel=subprocess.Popen([str(binary),'--config',str(conf)],stdout=log,stderr=log);wait(1.4)
        item=Item()
        if case=='context':menu=TestMenu()
        watcher=dbus.Interface(bus.get_object('org.kde.StatusNotifierWatcher','/StatusNotifierWatcher'),'org.kde.StatusNotifierWatcher');watcher.RegisterStatusNotifierItem('org.kde.StatusNotifierItem.Lifecycle');wait(1.5)
        for i in range(2):
            field=QLineEdit();field.setWindowTitle('Disposable focus '+str(i));field.setGeometry(150+i*350,200,240,70);field.show();fields.append(field)
        if case=='entry-limit':
            # This is a limitation probe, not a claim of keyboard-only entry.
            app.sync();wait()
            pointer=root.query_pointer()
            fields[0].activateWindow();fields[0].setFocus();wait()
            key('a');assert fields[0].text()=='a','disposable app focus setup failed'
            p=panel_window();hints=p.get_wm_hints()
            assert hints is not None and not hints['input'],'panel unexpectedly accepts keyboard focus; revisit limitation'
            for _ in range(4):key('Tab')
            key('Return');key('space');key('Menu');key('Escape')
            assert not popups() and not calls,'keyboard unexpectedly entered overflow; revisit limitation'
            # Openbox normal window cycling also skips this no-focus dock.
            for _ in range(3):
                alt=d.keysym_to_keycode(XK.string_to_keysym('Alt_L'))
                xtest.fake_input(d,X.KeyPress,alt);key('Tab')
                xtest.fake_input(d,X.KeyRelease,alt);d.sync();wait()
                focused=d.get_input_focus().focus
                assert focused.id in [int(f.winId()) for f in fields],'window cycling did not remain in fixture apps'
            after=root.query_pointer()
            assert (after.root_x,after.root_y)==(pointer.root_x,pointer.root_y),'pointer moved during keyboard probe'
            assert not popups() and not calls
            print('LIMIT CONFIRMED: no-focus panel and normal Openbox keyboard cycling do not reach overflow; no pointer input used',flush=True)
            return
        app.sync();wait();click(200,230);key('a');assert fields[0].text()=='a'
        popup=open_popup()
        if case in ('context','context-fallback'):
            key('Menu');wait(.5)
            app.primaryScreen().grabWindow(0).save(str(evidence/'keyboard-menu.png'))
            if case=='context':key('Down');key('Return')
            expected='menu-clicked' if case=='context' else 'context'
            assert calls==[expected],('Menu key did not dispatch tray context action',calls)
            key('Escape');key('b');assert fields[0].text()=='ab','keyboard context close lost typing focus'
            open_popup()
            shift=d.keysym_to_keycode(XK.string_to_keysym('Shift_L'));xtest.fake_input(d,X.KeyPress,shift);d.sync()
            key('F10');xtest.fake_input(d,X.KeyRelease,shift);d.sync();wait()
            if case=='context':key('Down');key('Return')
            assert calls==[expected,expected],'Shift+F10 did not dispatch exactly once'
            key('Escape');key('c');assert fields[0].text()=='abc'
            print('PASS Menu and Shift+F10 '+case+', repeated reopen and typing focus',flush=True)
        elif case=='attention':
            assert not panel_has_icon(),'passive auto-hidden icon visible in panel'
            item.status='NeedsAttention';item.NewStatus(item.status);wait(.8)
            app.primaryScreen().grabWindow(0).save(str(evidence/'attention.png'))
            assert panel_has_icon(),'attention did not expose host icon'
            assert not popups(),'attention left a stale duplicate popup'
            key('b');assert fields[0].text()=='ab','attention closure stole typing focus'
            item.status='Active';item.NewStatus(item.status);wait(.5)
            item.status='Passive';item.NewStatus(item.status);wait(.5)
            assert panel_has_icon(),'configured attention interval was not preserved'
            deadline=time.monotonic()+65
            while panel_has_icon() and time.monotonic()<deadline:wait(.5)
            assert not panel_has_icon(),'one-minute attention interval did not auto-hide host'
            open_popup();key('Escape');assert not popups()
            print('PASS attention closes stale popup, focus preserved, Active/Passive transitions and real one-minute auto-hide/reopen',flush=True)
        else:
            app.primaryScreen().grabWindow(0).save(str(evidence/'popup-open.png'))
            assert panel_visible_height()>=36,'panel auto-hid underneath its open tray popup'
            for i in range(3):
                if i:open_popup()
                key('Escape');assert not popups(),'Escape left popup visible'
                key('b');assert fields[0].text()=='a'+'b'*(i+1),'Escape failed to restore typing focus'
            # Qt consumes the dismissing outside click; focus returns to the prior app.
            open_popup();click(550,230);key('c')
            assert not popups(),'outside click left popup open'
            assert fields[0].text()=='abbbc' and fields[1].text()=='','outside dismissal lost prior typing focus'
            click(550,230);key('c');assert fields[1].text()=='c','next deliberate click failed to focus its target'
            open_popup();key('Return');assert calls==['activate'],'keyboard dispatch repeated or failed'
            key('Escape');key('d');assert fields[1].text()=='cd','popup activation/close stole focus'
            open_popup();bus.release_name('org.kde.StatusNotifierItem.Lifecycle');wait(.7)
            assert not popups(),'disconnect left stale popup'
            key('e');assert fields[1].text()=='cde','disconnect failed to restore focus'
            xtest.fake_input(d,X.MotionNotify,x=900,y=300);d.sync();wait(1.5)
            assert panel_visible_height()<10,'panel remained held open after popup cleanup'
            print('PASS panel auto-hide hold/release, repeated reopen, Escape/outside/disconnect focus restoration and keyboard activation',flush=True)
        assert panel.poll() is None
    finally:
        for f in fields:f.close()
        if menu:menu.remove_from_connection()
        if item:item.remove_from_connection()
        for process in (panel,wm):
            if process and process.poll() is None:process.terminate();process.wait(timeout=5)
        log.close();d.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--case',choices=['popup','attention','context-fallback','context','entry-limit'],default='popup');p.add_argument('--xvfb',type=Path);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');a=p.parse_args()
    if a.worker:worker(a.binary.resolve(),a.evidence.resolve(),a.case)
    elif a.run and a.xvfb:isolated(a.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker','--binary',str(a.binary.resolve()),'--evidence',str(a.evidence.resolve()),'--case',a.case])
    else:p.error('Opt in with --run --xvfb PATH')
