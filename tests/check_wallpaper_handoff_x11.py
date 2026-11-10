"""Probe supported desktop-only commands without touching the personal session."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary):
    home=Path.home()
    assert home==Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY'] and os.environ['DISPLAY']!=':0'
    from PySide6.QtWidgets import QApplication
    from Xlib import display,X
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from wallpaper.control import deployment_status
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    d=display.Display();root=d.screen().root
    def wait(t):
        end=time.monotonic()+t
        while time.monotonic()<end:app.processEvents();time.sleep(.02)
    def windows(pid,kind):
        result=set();clients=root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
        for wid in clients.value if clients else []:
            w=d.create_resource_object('window',int(wid));owner=w.get_full_property(d.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
            types=w.get_full_property(d.intern_atom('_NET_WM_WINDOW_TYPE'),X.AnyPropertyType)
            if owner and int(owner.value[0])==pid and types and d.intern_atom(kind) in types.value:
                if kind=='_NET_WM_WINDOW_TYPE_NORMAL' and d.intern_atom('_NET_WM_WINDOW_TYPE_DESKTOP') in types.value:continue
                result.add(int(wid))
        return result
    def invoke(exe,*args):subprocess.run([str(exe),*args],check=True,timeout=5,stdout=log,stderr=log);wait(.5)
    folder=home/'Keep this window';folder.mkdir()
    (home/'Desktop/Clickable folder').mkdir(parents=True)
    (home/'.config').mkdir(exist_ok=True)
    (home/'.config/user-dirs.dirs').write_text('XDG_DESKTOP_DIR="$HOME/Desktop"\n')
    log=open(home/'handoff.log','w');wm=subprocess.Popen(['openbox','--sm-disable'],stdout=log,stderr=log)
    stock=None;native=None
    normal='_NET_WM_WINDOW_TYPE_NORMAL';desktop='_NET_WM_WINDOW_TYPE_DESKTOP'
    try:
        wait(.5)
        stock=subprocess.Popen(['/usr/bin/pcmanfm-qt','--desktop','--profile=lxqt'],stdout=log,stderr=log);wait(1)
        invoke('/usr/bin/pcmanfm-qt','--new-window',str(folder))
        kept=windows(stock.pid,normal);assert kept and windows(stock.pid,desktop)
        invoke(binary,'--desktop','--profile=lxqt')
        assert stock.poll() is None and windows(stock.pid,normal)==kept and windows(stock.pid,desktop)
        assert 'not installed' in deployment_status()
        invoke('/usr/bin/pcmanfm-qt','--desktop-off')
        assert not windows(stock.pid,desktop) and windows(stock.pid,normal)==kept, (stock.poll(),kept,windows(stock.pid,normal),windows(stock.pid,desktop))
        invoke(binary,'--desktop','--profile=doroshell-probe')
        assert stock.poll() is None and windows(stock.pid,normal)==kept and windows(stock.pid,desktop)
        assert 'not installed' in deployment_status()
        print('PASS desktop-off preserves file window but candidate --desktop forwards to existing stock owner, including alternate profile',flush=True)
        # Only the disposable stock process is now cleaned up for a separate status check.
        stock.terminate();stock.wait(timeout=5)
        native=subprocess.Popen([str(binary),'--desktop','--profile=lxqt'],stdout=log,stderr=log);wait(1.5)
        invoke(binary,'--new-window',str(folder))
        kept=windows(native.pid,normal);assert kept and windows(native.pid,desktop)
        assert 'renderer active' in deployment_status(),deployment_status()
        invoke(binary,'--desktop-off')
        assert native.poll() is None and windows(native.pid,normal)==kept and not windows(native.pid,desktop)
        assert 'not installed' in deployment_status(),deployment_status()
        print('PASS process-identified active renderer status clears on desktop-off while its file-manager window survives',flush=True)
    except Exception:
        log.flush();print((home/'handoff.log').read_text(),flush=True)
        raise
    finally:
        for p in (native,stock,wm):
            if p and p.poll() is None:p.terminate();p.wait(timeout=5)
        log.close();d.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--xvfb',type=Path);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true')
    args=p.parse_args()
    if args.worker:worker(args.binary.resolve())
    elif args.run and args.xvfb:isolated(args.xvfb,[sys.executable,str(Path(__file__).resolve()),'--worker','--binary',str(args.binary.resolve())])
    else:p.error('Opt in with --run --xvfb PATH')
