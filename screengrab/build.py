#!/usr/bin/env python3
"""Build the optional native ScreenGrab PNG importer without installing packages."""
import argparse
from pathlib import Path
import subprocess

REVISION = '1fc2d35a4449706de9a2c279d6c5f79c5fbcd883'


def build(work):
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise ValueError('Choose an empty build directory')
    source = work/'source'
    subprocess.run(['git','clone','--depth','1','--branch','3.2.0',
                    'https://github.com/lxqt/screengrab.git',source],check=True)
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()!=REVISION:
        raise RuntimeError('Unexpected ScreenGrab upstream revision')
    patch = Path(__file__).resolve().with_name('import-png.patch')
    subprocess.run(['git','apply','--check',patch],cwd=source,check=True)
    subprocess.run(['git','apply',patch],cwd=source,check=True)
    # Use the installed ScreenGrab icons/translations. Only build the executable.
    subprocess.run(['cmake','-S',source,'-B',work/'build','-G','Ninja',
                    '-DCMAKE_INSTALL_PREFIX=/usr'],check=True)
    subprocess.run(['cmake','--build',work/'build','--target','screengrab','-j4'],check=True)
    print('Native preview executable:',work/'build/screengrab')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    build(parser.parse_args().work)
