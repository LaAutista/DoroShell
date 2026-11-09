"""Verify Show Desktop mouse activation and orientation on a private X11 desktop."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from x11_isolation import isolated


def worker(binary):
    assert os.environ.get('DOROSHELL_TEST_DISPLAY')==os.environ.get('DISPLAY') and os.environ['DISPLAY']!=':0'
    from PySide6.QtWidgets import QApplication,QWidget
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QColor
    from Xlib import display,X
    from Xlib.ext import xtest
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    d=display.Display();root=d.screen().root
    def wait(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:app.processEvents();time.sleep(.01)
    def showing():
        value=root.get_full_property(d.intern_atom('_NET_SHOWING_DESKTOP'),X.AnyPropertyType)
        return int(value.value[0]) if value else 0
    def windows(w,pid):
        found=[]
        try:
            value=w.get_full_property(d.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
            if value is not None and value.value[0]==pid and w.get_attributes().map_state==X.IsViewable:found.append(w)
            for child in w.query_tree().children:found.extend(windows(child,pid))
        except Exception:pass
        return found
    def visible(window):return d.create_resource_object('window',int(window.winId())).get_attributes().map_state==X.IsViewable
    with tempfile.TemporaryDirectory(prefix='doroshell-show-desktop-') as tmp:
        base=Path(tmp);rc=base/'rc.xml'
        rc.write_text('<openbox_config xmlns="http://openbox.org/3.4/rc"><desktops><number>1</number></desktops></openbox_config>')
        conf=base/'panel.conf'
        conf.write_text('panels=panel1\n[panel1]\nplugins=worldclock,edge\nposition=Bottom\ndoroshellTheme=true\nwidth=240\nwidth-percent=false\nreserve-space=false\npanelSize=40\n[worldclock]\ntype=worldclock\nalignment=Right\n[edge]\ntype=showdesktop\nalignment=Right\ndoroshellEdge=true\n')
        with open(base/'wm.log','w') as wmlog,open(base/'panel.log','w') as panellog:
            wm=subprocess.Popen(['openbox','--sm-disable','--config-file',str(rc)],stdout=wmlog,stderr=wmlog)
            panel=None;fixtures=[]
            try:
                wait(.7);assert wm.poll() is None,'Private Openbox failed'
                for x in (120,430):
                    w=QWidget();w.setWindowTitle('Disposable Show Desktop fixture');w.setGeometry(x,150,200,150);w.show();fixtures.append(w)
                panel=subprocess.Popen([str(binary),'--config',str(conf)],stdout=panellog,stderr=panellog)
                wait(1.5)
                assert all(visible(w) for w in fixtures) and showing()==0
                for vertical in (False,True):
                    if vertical:
                        panel.terminate();panel.wait(timeout=5)
                        cfg=QSettings(str(conf),QSettings.Format.IniFormat);cfg.setValue('panel1/position','Left');cfg.sync();del cfg
                        panel=subprocess.Popen([str(binary),'--config',str(conf)],stdout=panellog,stderr=panellog);wait(1.5)
                    candidates=[w for w in windows(root,panel.pid) if max(w.get_geometry().width,w.get_geometry().height)>=200]
                    assert candidates,'No panel found'
                    target=candidates[0];im=app.primaryScreen().grabWindow(target.id).toImage()
                    coords=[(x,y) for x in range(im.width()) for y in range(im.height()) if im.pixelColor(x,y) in (QColor('#803656'),QColor('#5b143d'))]
                    assert coords,('Edge target border not rendered',vertical,im.width(),im.height())
                    xs=[p[0] for p in coords];ys=[p[1] for p in coords]
                    extent=max(ys)-min(ys)+1 if vertical else max(xs)-min(xs)+1
                    assert extent==12,(vertical,extent,im.width(),im.height())
                    assert (min(ys)>im.height()-35 if vertical else min(xs)>im.width()-35),'Target not at panel end'
                    pos=root.translate_coords(target,0,0)
                    for expected in (1,0):
                        xtest.fake_input(d,X.MotionNotify,x=pos.x+(min(xs)+max(xs))//2,y=pos.y+(min(ys)+max(ys))//2)
                        xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(.4)
                        assert showing()==expected,('Desktop toggle failed',vertical,expected,showing())
                        assert all(visible(w)==(expected==0) for w in fixtures),'Fixture visibility not restored'
                print('PASS private X11/Openbox: horizontal and vertical 12-pixel edge target; real click hides/restores both windows',flush=True)
            finally:
                for w in fixtures:w.close()
                if panel:panel.terminate();panel.wait(timeout=5)
                wm.terminate();wm.wait(timeout=5)
    d.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--xvfb',type=Path)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:worker(args.binary.resolve())
    elif args.run and args.xvfb:isolated(args.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker','--binary',str(args.binary.resolve())])
    else:parser.error('Pass --run --xvfb /path/to/Xvfb --binary /path/to/lxqt-panel')
