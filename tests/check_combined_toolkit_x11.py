"""Combined installed toolkit: helper packaging, format-3 launch and rollback."""
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
    import install
    install.install(home,apply=True)
    toolkit=home/'.local/share/doroshell/toolkit';menu_home=home/'.local/share/lxqt-comfort'
    for name in ('app_search.py','folder_cascade.py'):
        expected=(Path(install.SOURCE)/'menu'/name).read_bytes()
        assert (menu_home/name).read_bytes()==expected
        assert (toolkit/'menu'/name).read_bytes()==expected
    for name in ('portable_settings.py','setup.py','wallpaper/install.py'):
        assert (toolkit/name).read_bytes()==(Path(install.SOURCE)/name).read_bytes()
    env=dict(os.environ);env.pop('PYTHONPATH',None)
    code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[2]);sys.path.insert(0,sys.argv[1]);import start_menu,app_search,folder_cascade,portable_settings;assert Path(app_search.__file__).parent==Path(sys.argv[1]);assert Path(folder_cascade.__file__).parent==Path(sys.argv[1]);assert Path(portable_settings.__file__).parent==Path(sys.argv[2])"
    subprocess.run([sys.executable,'-c',code,str(menu_home),str(toolkit)],cwd=home,env=env,check=True)
    def setup(action,binary):
        subprocess.run([sys.executable,str(toolkit/'setup.py'),'wallpaper','--home',str(home),
                        '--wallpaper-binary',str(binary),action],cwd=home,env=env,check=True,timeout=15)
    build=home/'build';build.mkdir()
    names=('pcmanfm-qt','doroshell-video-worker','doroshell-display-backend.py','doroshell-wallpaper-build.json')
    baseline={name:hashlib.sha256((source.parent/name).read_bytes()).hexdigest() for name in names}
    for name in names:shutil.copy2(source.parent/name,build/name)
    binary=build/'pcmanfm-qt';helper=build/'doroshell-display-backend.py';original_helper=helper.read_bytes()
    autostart=home/'.config/autostart/lxqt-desktop.desktop';autostart.parent.mkdir(parents=True)
    original=b'[Desktop Entry]\nType=Application\nName=Existing private desktop\nExec=pcmanfm-qt --desktop --profile=lxqt\nX-Preserve=true\n'
    autostart.write_bytes(original)
    settings=home/'.config/doroshell/wallpaper.json';settings.parent.mkdir();settings.write_bytes(b'{"enabled":false,"muted":true}')
    for _ in range(2):setup('--apply',binary)
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
        setup('--rollback',binary)
        assert autostart.read_bytes()==original
        assert settings.read_bytes()==b'{"enabled":false,"muted":true}'
        assert not launcher.exists()
        assert {name:hashlib.sha256((source.parent/name).read_bytes()).hexdigest() for name in names}==baseline
        install.rollback(home)
        assert not (menu_home/'app_search.py').exists() and not (menu_home/'folder_cascade.py').exists()
        assert not (toolkit/'portable_settings.py').exists()
        assert autostart.read_bytes()==original and settings.read_bytes()==b'{"enabled":false,"muted":true}'
        print('PASS combined installed setup/toolkit: search/cascade/portable helper payloads and imports, format-3 wallpaper installer, full helper rollback; paired candidate launch, intact wallpaper reporting, moved helper path, changed/missing display-helper stock fallback, repeat staging, exact rollback; source build untouched')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true')
    p.add_argument('--xvfb',type=Path);p.add_argument('--binary',type=Path,required=True);a=p.parse_args()
    if a.worker:worker(a.binary.resolve())
    elif a.run and a.xvfb:isolated(a.xvfb.resolve(),[sys.executable,__file__,'--worker','--binary',str(a.binary.resolve())])
    else:p.error('Pass --run --xvfb PATH --binary CANDIDATE')
