#!/usr/bin/env python3
"""Compile actual calendar construction/position snippets with fake panel/screen inputs.

No X11, panel plugin process, session bus or personal configuration is used. This
is native Qt widget/source acceptance, not a complete plugin build or WM check.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='patched lxqtworldclock.cpp')
    parser.add_argument('--evidence',type=Path,required=True,help='new private output directory')
    parser.add_argument('--bounds-case',choices=('all','screen','workarea'),default='all')
    args=parser.parse_args()
    data=args.source.read_text()
    position=data[data.index('void LXQtWorldClock::positionPopup()'):data.index('void LXQtWorldClock::fitClock()')]
    position=position.replace('LXQtWorldClock::positionPopup','ClockFixture::positionPopup',1)
    start=data.index('            QCalendarWidget *calendarWidget = new QCalendarWidget(mPopup);')
    construction=data[start:data.index('            QString timeZoneName',start)]
    args.evidence.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='doro-calendar-offscreen-') as temporary:
        root=Path(temporary);home=root/'home';home.mkdir();runtime=root/'runtime';runtime.mkdir(mode=0o700)
        include=root/'calendar_from_source.inc';include.write_text('void ClockFixture::constructCalendar() {\n'+construction+'}\n'+position)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets','Qt6Test'],text=True))
        executable=root/'calendar-fixture'
        subprocess.run(['c++','-std=c++17','-fPIC',str(Path(__file__).with_name('calendar_popup.cpp')),'-I'+str(root),'-o',str(executable),*flags],check=True,timeout=60)
        env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(home/'config'),XDG_DATA_HOME=str(home/'data'),XDG_CACHE_HOME=str(home/'cache'),XDG_STATE_HOME=str(home/'state'),XDG_RUNTIME_DIR=str(runtime),QT_QPA_PLATFORM='offscreen',QT_STYLE_OVERRIDE='Fusion',QT_QPA_PLATFORMTHEME='',DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'absent-session-bus'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'absent-system-bus'))
        for key in ['DISPLAY','WAYLAND_DISPLAY','SESSION_MANAGER','QT_FONT_DPI','QT_SCREEN_SCALE_FACTORS']:
            env.pop(key,None)
        results=[]
        for scale in ['1','1.25','1.5','2']:
            out=args.evidence/scale;out.mkdir()
            result=subprocess.run([str(executable),str(out),args.bounds_case],env=dict(env,QT_SCALE_FACTOR=scale),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60)
            (out/'result.log').write_text(result.stdout)
            print(scale,result.returncode,result.stdout.strip(),flush=True)
            results.append({'scale':scale,'exit_code':result.returncode})
            if result.returncode:
                raise SystemExit(result.returncode)
        (args.evidence/'results.json').write_text(json.dumps(results,indent=2)+'\n')

if __name__=='__main__':main()
