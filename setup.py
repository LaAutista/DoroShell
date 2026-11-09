#!/usr/bin/env python3
"""Select modules for an existing LXQt installation. Default is a dry run."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
PACKAGES={
 'menu':['python','pyside6','python-gobject','lxqt-panel','lxqt-session','lxqt-globalkeys','lxqt-config','xdg-user-dirs','procps-ng'],
 'panel':['lxqt-panel','lxqt-globalkeys','procps-ng'],
 'snapping':['openbox','python-xlib','pyside6'],
 'screenshots':['screengrab','pyside6','lxqt-globalkeys'],
 'dolphin':['dolphin','xdg-utils'], 'kate':['kate','xdg-utils'],
 'kate-dark':['kate','breeze'], 'dolphin-dark':['dolphin','breeze'],
 'single-desktop':['openbox'], 'taskbar':['lxqt-panel'],
 'cursor':['python-pillow'],
}
DEFAULT=['menu']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('modules',nargs='*',default=DEFAULT)
    actions=p.add_mutually_exclusive_group()
    actions.add_argument('--apply',action='store_true')
    actions.add_argument('--rollback',action='store_true')
    p.add_argument('--live',action='store_true',help='Refresh panel/shortcuts and Openbox configuration without logging out')
    p.add_argument('--home',type=Path,default=Path.home())
    p.add_argument('--gif',type=Path,help='Local animated loading cursor; never copied into the repository')
    p.add_argument('--pink-pointer',action='store_true')
    p.add_argument('--icon',type=Path,help='Personal Start image; stored locally, never bundled')
    p.add_argument('--taskbar-style',choices=('icons','standard'),default='icons')
    p.add_argument('--gui',action='store_true',help='Open DoroShell settings')
    p.add_argument('--packages',action='store_true',help='Print the exact Arch/CachyOS full-update installation command and exit')
    args=p.parse_args()
    if args.gui:
        from settings import main as settings_main
        return settings_main(args.home)
    if not args.modules or any(m not in PACKAGES for m in args.modules):
        p.error('Choose modules: '+', '.join(PACKAGES))
    selected=list(dict.fromkeys(args.modules))
    packages=sorted({pkg for m in selected for pkg in PACKAGES[m]})
    print('Required packages: '+', '.join(packages),flush=True)
    if args.packages:
        print('sudo pacman -Syu --needed '+' '.join(packages))
        return
    if os.geteuid()==0:
        p.error('Run as your desktop user, not root')
    if 'cursor' in selected and not args.gif and not args.rollback:
        p.error('The cursor module requires --gif /path/to/local-animation.gif')
    if args.pink_pointer and 'cursor' not in selected:
        p.error('--pink-pointer requires the cursor module')
    if args.apply:
        missing=[pkg for pkg in packages if subprocess.run(['pacman','-Q',pkg],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode]
        if missing:
            p.error('Missing packages: '+', '.join(missing)+'. Run --packages to review the installation command.')
    if args.rollback:
        selected.reverse()
    for module in selected:
        cmd=[sys.executable]
        if module=='menu':
            cmd += [str(ROOT/'install.py'),'menu']
            if args.icon: cmd += ['--icon',str(args.icon.absolute())]
        elif module=='panel': cmd += [str(ROOT/'integrate.py')]
        elif module=='cursor':
            cmd += [str(ROOT/'cursor.py')]
            if args.gif: cmd += ['--gif',str(args.gif.absolute())]
            if args.pink_pointer: cmd += ['--pink-pointer']
        else: cmd += [str(ROOT/'modules.py'),module]
        cmd += ['--home',str(args.home.absolute())]
        if args.apply: cmd += ['--apply']
        if args.rollback: cmd += ['--rollback']
        if module=='taskbar': cmd += ['--taskbar-style',args.taskbar_style]
        if args.live and module not in ('menu','cursor','single-desktop','kate','dolphin','kate-dark','dolphin-dark'): cmd += ['--live']
        print('\n'+module+':',flush=True)
        subprocess.run(cmd,check=True)
    print('\nFinished selected modules. Package state was not changed. No session was restarted.')

if __name__=='__main__':
    main()
