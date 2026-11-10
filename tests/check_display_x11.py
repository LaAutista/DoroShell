"""Build native controls and test on private X11 with production guard/fake drivers."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from x11_isolation import isolated
ROOT=Path(__file__).resolve().parents[1]


def worker(binary, screenshot):
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY'] and os.environ['DISPLAY']!=':0'
    from test_display import Driver
    path=Path(os.environ['HOME'])/'display-fixture.json'
    original={'state':Driver().state,'calls':[]}
    path.write_text(json.dumps(original))
    env=dict(os.environ,DOROSHELL_DISPLAY_FIXTURE=str(path),DOROSHELL_DISPLAY_SCREENSHOT=str(screenshot))
    helper=str(ROOT/'tests/display_driver_fixture.py')
    subprocess.run([str(binary),helper],env=env,check=True,timeout=45)
    path.write_text(json.dumps(original))
    subprocess.run([str(binary),helper,'exit'],env=env,check=True,timeout=10)
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        if json.loads(path.read_text())['state']==original['state']:break
        time.sleep(.05)
    else:raise AssertionError('App exit failed to restore original state')
    print('PASS application exit: independent guard received EOF and restored synthetic display state')
    copied=Path(os.environ['HOME'])/'display-helper-fixture.py';shutil.copy2(helper,copied)
    path.write_text(json.dumps(original))
    env['PYTHONPATH']=str(ROOT)
    subprocess.run([str(binary),str(copied),'integrity'],env=env,check=True,timeout=10)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true')
    p.add_argument('--xvfb',type=Path);p.add_argument('--binary',type=Path);p.add_argument('--screenshot',type=Path,required=True)
    a=p.parse_args()
    if a.worker:worker(a.binary,a.screenshot.resolve())
    elif a.run and a.xvfb:
        with tempfile.TemporaryDirectory(prefix='doro-display-ui-build-') as tmp:
            binary=Path(tmp)/'test-ui'
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets','Qt6Test'],text=True))
            subprocess.run(['c++','-std=c++17','-fPIC',str(ROOT/'tests/display_ui.cpp'),'-I'+str(ROOT/'display'),*flags,'-o',str(binary)],check=True)
            isolated(a.xvfb.resolve(),[sys.executable,__file__,'--worker','--binary',str(binary),'--screenshot',str(a.screenshot.resolve())])
    else:p.error('Pass --run --xvfb PATH --screenshot PRIVATE_PATH')
