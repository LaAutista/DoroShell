"""Actual fixed clipboard button click on disposable native panel."""
import argparse,os,sys,time,subprocess
from pathlib import Path
from x11_isolation import isolated
ROOT=Path(__file__).resolve().parents[1]

def worker(binary):
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    sys.path.insert(0,str(ROOT))
    from PySide6.QtWidgets import QApplication
    from Xlib import display,X
    from Xlib.ext import xtest
    import modules
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    d=display.Display();root=d.screen().root
    def wait(t):
        end=time.monotonic()+t
        while time.monotonic()<end:app.processEvents();time.sleep(.01)
    home=Path.home();conf=home/'.config/doroshell/panel.conf';conf.parent.mkdir(parents=True)
    conf.write_text('panels=panel1\n[panel1]\nplugins=taskbar,notifier,clock\nposition=Bottom\nwidth=900\nwidth-percent=false\npanelSize=40\niconSize=24\n[taskbar]\ntype=taskbar\n[notifier]\ntype=statusnotifier\nalignment=Right\ndoroshellPopup=true\ndoroshellCollapseNew=true\n[clock]\ntype=worldclock\nalignment=Right\n')
    modules.run(home,'clipboard',apply=True)
    wm=subprocess.Popen(['openbox','--sm-disable'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    wait(.3)
    panel=subprocess.Popen([str(binary),'--config',str(conf)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        wait(1.5)
        image=app.primaryScreen().grabWindow(0).toImage()
        points=[]
        for y in range(image.height()-80,image.height()):
            for x in range(image.width()):
                c=image.pixelColor(x,y)
                if abs(c.red()-119)<8 and abs(c.green()-60)<8 and abs(c.blue()-98)<8:points.append((x,y))
        assert points,'Clipboard SVG not visible on actual panel'
        x=sum(p[0] for p in points)//len(points);y=sum(p[1] for p in points)//len(points)
        xtest.fake_input(d,X.MotionNotify,x=x,y=y);xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(1)
        found=[]
        def scan(w):
            try:
                if w.get_wm_name()=='DoroClipboard' and w.get_attributes().map_state==X.IsViewable:found.append(w)
                for c in w.query_tree().children:scan(c)
            except Exception:pass
        scan(root);assert found,'Visible fixed button did not open DoroClipboard'
        print('PASS: fixed clipboard icon visible on native panel and real mouse click opens history')
    finally:
        # Only processes carrying this private HOME were launched here.
        for p in (panel,wm):p.terminate();p.wait(timeout=3)
        for entry in Path('/proc').iterdir():
            if entry.name.isdigit():
                try:
                    env=(entry/'environ').read_bytes()
                    cmd=(entry/'cmdline').read_bytes()
                    if ('HOME='+str(home)).encode()+b'\0' in env and b'doroshell/clipboard.py' in cmd:
                        os.kill(int(entry.name),15)
                except (OSError,ValueError):pass
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);p.add_argument('--binary',type=Path,required=True);a=p.parse_args()
    if a.worker:worker(a.binary)
    else:isolated(a.xvfb,[sys.executable,__file__,'--worker','--binary',str(a.binary)])
