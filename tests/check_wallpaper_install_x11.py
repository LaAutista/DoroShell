"""Real staged-launch, pair fallback and rollback on a disposable private desktop."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary):
    home=Path.home()
    assert home==Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import modules
    pair=home/'build';pair.mkdir()
    for name in (binary.name,'doroshell-video-worker','doroshell-wallpaper-build.json'):
        shutil.copy2(binary.with_name(name),pair/name)
    binary=pair/binary.name
    original=home/'.config/autostart/lxqt-desktop.desktop';original.parent.mkdir(parents=True)
    baseline=b'[Desktop Entry]\nType=Application\nName=Personal baseline\nExec=pcmanfm-qt --desktop --profile=lxqt\nX-Personal=preserve\n'
    original.write_bytes(baseline)
    choices=home/'.config/doroshell/wallpaper.json';choices.parent.mkdir();choices.write_text('{"enabled":false,"muted":true}')
    for _ in range(2):modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
    launcher=home/'.local/bin/doroshell-wallpaper-desktop'
    log=open(home/'install-test.log','w');wm=subprocess.Popen(['openbox','--sm-disable'],stdout=log,stderr=log)
    processes=[]
    def terminate(p):
        if p.poll() is None:p.terminate();p.wait(timeout=5)
    try:
        p=subprocess.Popen([str(launcher)],stdout=log,stderr=log);processes.append(p);time.sleep(2)
        children=Path(f'/proc/{p.pid}/task/{p.pid}/children').read_text().split()
        assert len(children)==1,children
        child=int(children[0]);assert Path(f'/proc/{child}/exe').resolve()==binary
        reports=list(Path(os.environ['XDG_RUNTIME_DIR']).glob('doroshell-wallpaper-*.json'))
        assert reports and json.loads(reports[0].read_text())['pid']==child
        subprocess.run([str(binary),'--desktop-off'],check=True,timeout=5,stdout=log,stderr=log);p.wait(timeout=5)
        helper=pair/'doroshell-video-worker';helper.chmod(0o644)
        p=subprocess.Popen([str(launcher)],stdout=log,stderr=log);processes.append(p);time.sleep(2)
        assert p.poll() is None
        assert Path(f'/proc/{p.pid}/exe').resolve()==Path('/usr/bin/pcmanfm-qt').resolve()
        terminate(p)
        modules.run(home,'wallpaper',rollback=True)
        assert original.read_bytes()==baseline
        assert not launcher.exists()
        assert choices.read_text()=='{"enabled":false,"muted":true}'
        print('PASS actual paired launcher, non-executable-helper stock fallback, repeat staging and exact rollback; personal wallpaper choices retained',flush=True)
    finally:
        for p in processes:terminate(p)
        terminate(wm);log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--xvfb',type=Path);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');a=p.parse_args()
    if a.worker:worker(a.binary.resolve())
    elif a.run and a.xvfb:isolated(a.xvfb,[sys.executable,str(Path(__file__).resolve()),'--worker','--binary',str(a.binary.resolve())])
    else:p.error('Opt in with --run --xvfb PATH')
