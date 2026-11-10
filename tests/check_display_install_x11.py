"""Private real paired-launch, display-helper integrity fallback and rollback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(source):
    home=Path.home();assert home==Path(os.environ['TMPDIR']).parent
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import modules
    build=home/'build';build.mkdir()
    names=('pcmanfm-qt','doroshell-video-worker','doroshell-display-backend.py','doroshell-wallpaper-build.json')
    baseline={name:hashlib.sha256((source.parent/name).read_bytes()).hexdigest() for name in names}
    for name in names:shutil.copy2(source.parent/name,build/name)
    binary=build/'pcmanfm-qt';helper=build/'doroshell-display-backend.py';original_helper=helper.read_bytes()
    autostart=home/'.config/autostart/lxqt-desktop.desktop';autostart.parent.mkdir(parents=True)
    original=b'[Desktop Entry]\nType=Application\nName=Existing private desktop\nExec=pcmanfm-qt --desktop --profile=lxqt\nX-Preserve=true\n'
    autostart.write_bytes(original)
    settings=home/'.config/doroshell/wallpaper.json';settings.parent.mkdir();settings.write_bytes(b'{"enabled":false,"muted":true}')
    for _ in range(2):modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
    launcher=home/'.local/bin/doroshell-wallpaper-desktop'
    with (home/'display-install.log').open('w') as log:
        def stop(process):
            if process.poll() is None:process.terminate();process.wait(timeout=5)
        process=subprocess.Popen([str(launcher)],stdout=log,stderr=log)
        try:
            time.sleep(2)
            children=Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
            assert len(children)==1
            child=int(children[0]);assert Path(f'/proc/{child}/exe').resolve()==binary
            reports=list(Path(os.environ['XDG_RUNTIME_DIR']).glob('doroshell-wallpaper-*.json'))
            assert reports and json.loads(reports[0].read_text())['pid']==child
            subprocess.run([str(binary),'--desktop-off'],check=True,timeout=5,stdout=log,stderr=log)
            process.wait(timeout=5)
        finally:stop(process)
        for kind in ('changed','missing'):
            if kind=='changed':helper.write_bytes(original_helper+b'\n# synthetic tamper\n')
            else:helper.unlink()
            process=subprocess.Popen([str(launcher)],stdout=log,stderr=log)
            try:
                time.sleep(1)
                assert process.poll() is None
                assert Path(f'/proc/{process.pid}/exe').resolve()==Path('/usr/bin/pcmanfm-qt').resolve()
            finally:stop(process)
            helper.write_bytes(original_helper)
        modules.run(home,'wallpaper',rollback=True)
        assert autostart.read_bytes()==original
        assert settings.read_bytes()==b'{"enabled":false,"muted":true}'
        assert not launcher.exists()
        assert {name:hashlib.sha256((source.parent/name).read_bytes()).hexdigest() for name in names}==baseline
        print('PASS private staged desktop: paired candidate launch, intact wallpaper reporting, moved helper path, changed/missing display-helper stock fallback, repeat staging, exact rollback; source build untouched')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true')
    p.add_argument('--xvfb',type=Path);p.add_argument('--binary',type=Path,required=True);a=p.parse_args()
    if a.worker:worker(a.binary.resolve())
    elif a.run and a.xvfb:isolated(a.xvfb.resolve(),[sys.executable,__file__,'--worker','--binary',str(a.binary.resolve())])
    else:p.error('Pass --run --xvfb PATH --binary CANDIDATE')
