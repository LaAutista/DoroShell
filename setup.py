#!/usr/bin/env python3
"""Select modules for an existing LXQt installation. Default is a dry run."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
PACKAGES={
 'wallpaper-glass':['pyside6','python-pillow'],
 'wallpaper':['pcmanfm-qt','qt6-multimedia','qt6-multimedia-ffmpeg','pyside6'],
 'theme':['pyside6','openbox','breeze-icons'],
 'menu':['python','pyside6','python-gobject','lxqt-panel','lxqt-session','lxqt-globalkeys','lxqt-config','xdg-user-dirs','procps-ng'],
 'native-panel':['lxqt-panel','python-gobject','pyside6'],
 'panel':['lxqt-panel','lxqt-globalkeys','procps-ng'],
 'snapping':['openbox','python-xlib','pyside6'],
 'screenshots':['screengrab','python-xlib','pyside6','lxqt-globalkeys','python-gobject'],
 'dolphin':['dolphin','xdg-utils'], 'kate':['kate','xdg-utils'],
 'kate-dark':['kate','breeze'], 'dolphin-dark':['dolphin','breeze'],
 'single-desktop':['openbox'], 'taskbar':['lxqt-panel'],
 'cursor':['python-pillow'],
 'taskbar-drag':['python-gobject'], 'taskbar-size':['lxqt-panel'],
}
DEFAULT=['menu']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('modules',nargs='*',default=DEFAULT)
    actions=p.add_mutually_exclusive_group()
    actions.add_argument('--apply',action='store_true')
    actions.add_argument('--rollback',action='store_true')
    p.add_argument('--live',action='store_true',help='Start edge snapping; panel/shortcut restarts are disabled')
    p.add_argument('--home',type=Path,default=Path.home())
    p.add_argument('--gif',type=Path,help='Local animated loading cursor; never copied into the repository')
    p.add_argument('--pink-pointer',action='store_true')
    p.add_argument('--icon',type=Path,help='Personal Start image; stored locally, never bundled')
    p.add_argument('--taskbar-size',choices=('small','medium','large'),default='medium')
    p.add_argument('--taskbar-style',choices=('icons','standard'),default='icons')
    p.add_argument('--wallpaper-binary', type=Path, help='Verified optional native desktop executable; takes effect at normal login')
    p.add_argument('--theme', choices=('windows','polar','heretic','spring'), default='windows')
    p.add_argument('--native-preview',type=Path,help='Import-enabled native ScreenGrab executable for screenshots')
    p.add_argument('--keep-panel-edits',action='store_true',help='Back up changed native panel settings before rollback')
    p.add_argument('--prepared',type=Path,help='Prepared native panel profile directory')
    p.add_argument('--gui',action='store_true',help='Open DoroShell settings')
    p.add_argument('--packages',action='store_true',help='Print the exact Arch/CachyOS full-update installation command and exit')
    args=p.parse_args()
    if args.gui:
        from settings import main as settings_main
        return settings_main(args.home)
    if not args.modules or any(m not in PACKAGES for m in args.modules):
        p.error('Choose modules: '+', '.join(PACKAGES))
    selected=list(dict.fromkeys(args.modules))
    if args.keep_panel_edits and (not args.rollback or 'native-panel' not in selected):
        p.error('--keep-panel-edits requires native-panel --rollback')
    if args.native_preview and ('screenshots' not in selected or args.rollback):
        p.error('--native-preview requires the screenshots module and an install or preview action')
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
    if 'menu' in selected and ('panel' in selected or 'native-panel' in selected):
        selected.remove('menu')
        selected.insert(0, 'menu')
    if args.rollback:
        selected.reverse()
    for module in selected:
        cmd=[sys.executable]
        if module=='menu':
            cmd += [str(ROOT/'install.py'),'menu']
            if args.icon: cmd += ['--icon',str(args.icon.absolute())]
        elif module=='native-panel':
            action = 'restore-next-login' if args.rollback else 'enable-next-login' if args.apply else 'preview-next-login'
            cmd += [str(ROOT/'panel/profile.py'), action, '--home', str(args.home.absolute())]
            if args.keep_panel_edits:
                cmd.append('--keep-panel-edits')
            if not args.rollback:
                prepared = args.prepared or args.home/'.local/state/doroshell/core-panel-profile'
                if not (prepared/'plan.json').is_file():
                    p.error('Prepare a native panel profile with panel/profile.py prepare before selecting native-panel')
                cmd += ['--prepared', str(prepared.absolute())]
            subprocess.run(cmd, check=True)
            continue
        elif module=='panel': cmd += [str(ROOT/'integrate.py')]
        elif module=='cursor':
            cmd += [str(ROOT/'cursor.py')]
            if args.gif: cmd += ['--gif',str(args.gif.absolute())]
            if args.pink_pointer: cmd += ['--pink-pointer']
        else: cmd += [str(ROOT/'modules.py'),module]
        cmd += ['--home',str(args.home.absolute())]
        if args.apply: cmd += ['--apply']
        if args.rollback: cmd += ['--rollback']
        if module=='screenshots' and args.native_preview: cmd += ['--native-preview',str(args.native_preview.resolve())]
        if module=='wallpaper' and args.wallpaper_binary: cmd += ['--wallpaper-binary',str(args.wallpaper_binary.resolve())]
        if module=='theme': cmd += ['--theme',args.theme]
        if module=='taskbar-size': cmd += ['--taskbar-size',args.taskbar_size]
        if module=='taskbar': cmd += ['--taskbar-style',args.taskbar_style]
        if args.live and module not in ('menu','cursor','single-desktop','kate','dolphin','kate-dark','dolphin-dark','theme','wallpaper','wallpaper-glass'): cmd += ['--live']
        print('\n'+module+':',flush=True)
        subprocess.run(cmd,check=True)
    print('\nFinished selected modules. Package state was not changed. No session was restarted.')

if __name__=='__main__':
    main()
