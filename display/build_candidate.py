#!/usr/bin/env python3
"""Copy an existing PCManFM source candidate, add controls and build privately."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
ROOT = Path(__file__).resolve().parent



def prepare(source, output):
    """Add the native controls to a private source and pin the colocated helper."""
    subprocess.run(['git','apply','--check',str(ROOT/'pcmanfm-advanced.patch')],cwd=source,check=True)
    subprocess.run(['git','apply',str(ROOT/'pcmanfm-advanced.patch')],cwd=source,check=True)
    shutil.copy2(ROOT/'dorodisplaycontrols.h',source/'pcmanfm/dorodisplaycontrols.h')
    output.mkdir(parents=True, exist_ok=True)
    helper=output/'doroshell-display-backend.py'
    shutil.copy2(ROOT/'backend.py',helper)
    digest=hashlib.sha256(helper.read_bytes()).hexdigest()
    with (source/'pcmanfm/CMakeLists.txt').open('a') as f:
        f.write('\ntarget_compile_definitions(pcmanfm-qt PRIVATE DOROSHELL_DISPLAY_SHA256="'+digest+'")\n')


def build(source, work, prefix=None):
    source, work = source.resolve(), work.resolve()
    if work.exists() and any(work.iterdir()):
        raise ValueError('Choose an empty private candidate directory')
    work.mkdir(parents=True, exist_ok=True)
    target = work/'source'
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    prepare(target, work/'build/pcmanfm')
    command=['cmake','-S',str(target),'-B',str(work/'build'),'-G','Ninja','-DCMAKE_INSTALL_PREFIX=/usr']
    if prefix:command.append('-DCMAKE_PREFIX_PATH='+str(prefix))
    subprocess.run(command,check=True)
    subprocess.run(['cmake','--build',str(work/'build'),'--target','pcmanfm-qt','-j4'],check=True)
    print(work/'build/pcmanfm/pcmanfm-qt')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--prefix',type=Path)
    a=p.parse_args();build(a.source,a.work,a.prefix)
