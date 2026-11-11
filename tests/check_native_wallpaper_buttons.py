"""Actual native wallpaper Apply/OK/Cancel and silent preview; isolated X11 only."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from x11_isolation import isolated
ROOT=Path(__file__).resolve().parents[1]


def worker(binary, hook):
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    from PIL import Image
    home=Path.home();media=home/'synthetic.gif'
    Image.new('RGB',(64,64),'red').save(media,save_all=True,append_images=[Image.new('RGB',(64,64),'blue')],duration=100,loop=0)
    config=Path(os.environ['XDG_CONFIG_HOME'])/'doroshell/wallpaper.json';config.parent.mkdir(parents=True)
    bad=home/'invalid.mp4';bad.write_bytes(b'not media')
    for scenario in ('unchanged','static','preview-failure','cancel','apply','ok','invalid','conflict','preview','preview-cancel'):
        config.write_text(json.dumps(dict(enabled=False,muted=True,file='',monitor='all',paused=False)))
        config.with_name(config.name+'.before-native-prefs').unlink(missing_ok=True)
        result=home/'result';result.unlink(missing_ok=True)
        env=dict(os.environ,LD_PRELOAD=str(hook),DORO_WALLPAPER_SCENARIO=scenario,DORO_WALLPAPER_RESULT=str(result),DORO_TEST_MEDIA=str(media),DORO_BAD_MEDIA=str(bad))
        proc=subprocess.run([str(binary),'--desktop-pref','--profile='+scenario],env=env,capture_output=True,text=True,timeout=15)
        assert proc.returncode==0 and result.read_text()=='PASS',scenario+': '+proc.stderr
        print('PASS actual native wallpaper:',scenario,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);p.add_argument('--binary',type=Path,required=True);p.add_argument('--hook',type=Path);a=p.parse_args()
    if a.worker:worker(a.binary.resolve(),a.hook.resolve())
    elif a.run and a.xvfb:
        with tempfile.TemporaryDirectory(prefix='native-wallpaper-hook-') as tmp:
            hook=Path(tmp)/'driver.so';flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets','Qt6Test'],text=True))
            subprocess.run(['c++','-shared','-fPIC','-std=c++17',str(ROOT/'tests/native_wallpaper_buttons.cpp'),*flags,'-o',str(hook)],check=True)
            isolated(a.xvfb.resolve(),[sys.executable,__file__,'--worker','--binary',str(a.binary.resolve()),'--hook',str(hook)])
    else:p.error('Use --run --xvfb PATH --binary PRIVATE_CANDIDATE')
