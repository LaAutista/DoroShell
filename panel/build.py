#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build the isolated DoroShell Panel prototype; never install system packages."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

PANEL_REV = 'cffb0cd29c6ce0360356006ce727a9b01347e062'
TOOLS_REV = '0f56cd400d2afcb6f16d4ca88538ed716439c2c2'
ROOT = Path(__file__).resolve().parent


def run(args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def build(work, jobs):
    work = work.resolve()
    if work.exists() and any(work.iterdir()):
        raise RuntimeError('Choose an empty build directory; existing files are preserved')
    work.mkdir(parents=True, exist_ok=True)
    for name, repo, tag, revision in [('source', 'lxqt-panel', '2.4.1', PANEL_REV), ('tools', 'lxqt-build-tools', '2.4.0', TOOLS_REV)]:
        target = work/name
        run(['git', 'clone', '--depth', '1', '--branch', tag, 'https://github.com/lxqt/'+repo+'.git', target])
        actual = subprocess.check_output(['git','rev-parse','HEAD'], cwd=target, text=True).strip()
        if actual != revision:
            raise RuntimeError('Upstream tag changed; refusing unreviewed source')
    run(['git','apply','--check',ROOT/'patches/0001-hidden-tray-popup.patch'], cwd=work/'source')
    run(['git','apply',ROOT/'patches/0001-hidden-tray-popup.patch'], cwd=work/'source')
    deps, prefix = work/'deps', work/'runtime'
    run(['cmake','-S',work/'tools','-B',work/'tools-build','-G','Ninja','-DCMAKE_INSTALL_PREFIX='+str(deps)])
    run(['cmake','--build',work/'tools-build','-j',jobs])
    run(['cmake','--install',work/'tools-build'])
    run(['cmake','-S',work/'source','-B',work/'build','-G','Ninja','-DCMAKE_INSTALL_PREFIX='+str(prefix),'-DCMAKE_PREFIX_PATH='+str(deps)])
    run(['cmake','--build',work/'build','-j',jobs])
    # Upstream also installs /etc/xdg files: stage them, never write system paths.
    stage=work/'stage'
    run(['cmake','--install',work/'build'], env=dict(os.environ, DESTDIR=str(stage)))
    shutil.copytree(stage/str(prefix).lstrip('/'),prefix,dirs_exist_ok=True)
    notices=prefix/'share/doroshell-panel';notices.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'licenses',notices/'licenses',dirs_exist_ok=True)
    shutil.copy2(ROOT/'patches/0001-hidden-tray-popup.patch',notices/'0001-hidden-tray-popup.patch')
    print('Built:',prefix/'bin/lxqt-panel')
    print('Keep this directory: runtime plugin paths are tied to its prefix. Nothing is enabled.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=4)
    args=parser.parse_args()
    if args.jobs < 1: parser.error('--jobs must be positive')
    build(args.work,args.jobs)
