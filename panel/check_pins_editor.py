#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compile and run the native pin editor input check using a patched source tree."""
import argparse
from pathlib import Path
import os
import shlex
import subprocess
import tempfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--run',action='store_true')
args=parser.parse_args()
if not args.run:parser.error('Pass --run to allow disposable dialogs')
source=args.source.resolve()/'plugin-taskbar'
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets','Qt6Test','Qt6Xdg','lxqt'],text=True))
with tempfile.TemporaryDirectory(prefix='doroshell-pins-test-') as temp:
    binary=Path(temp)/'check'
    panel=source.parent/'panel'
    moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
    generated=Path(temp)/'moc_pluginsettings.cpp'
    subprocess.run([str(moc),str(panel/'pluginsettings.h'),'-o',str(generated)],check=True)
    subprocess.run(['c++','-fPIC','-std=c++17','-I'+str(source),'-I'+str(panel),str(panel/'pluginsettings.cpp'),str(generated),str(Path(__file__).with_suffix('.cpp')),str(source/'doroshellpinsdialog.cpp'),'-o',str(binary),*flags],check=True)
    subprocess.run([str(binary)],check=True,timeout=30,env=dict(os.environ,HOME=temp,XDG_CONFIG_HOME=temp+'/.config',XDG_CACHE_HOME=temp+'/.cache',XDG_DATA_HOME=temp+'/.local/share'))
