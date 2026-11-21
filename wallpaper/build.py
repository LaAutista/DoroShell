#!/usr/bin/env python3
"""Build the optional PCManFM background renderer; never replace system binaries."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
# Reviewed upstream revisions. Other tags (a newer system PCManFM) still build, recorded as unreviewed.
REVISIONS = {'2.4.0': '8c4715a327170c20e7d7f3088e9cdc29ca485ba0',
             '2.5.0': 'f4be744f07d929228fcdcf0232fd3bf4d2879910'}
REVISION = REVISIONS['2.4.0']


def system_tag():
    from native_rebuild import system_version
    return system_version('desktop')


def write_build_record(binary, display_controls=False, tag='2.4.0', revision=REVISION):
    helper = binary.with_name('doroshell-video-worker')
    if not helper.is_file():
        raise RuntimeError('Build did not produce the decoder helper')
    record = dict(revision=revision, tag=tag, reviewed=REVISIONS.get(tag) == revision, format=2,
                  sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest())
    if display_controls:
        display_helper = binary.with_name('doroshell-display-backend.py')
        if not display_helper.is_file():
            raise RuntimeError('Build did not produce the display helper')
        record.update(format=3, display_helper_sha256=hashlib.sha256(display_helper.read_bytes()).hexdigest())
    binary.with_name('doroshell-wallpaper-build.json').write_text(json.dumps(record))


def clone(repo, tag, target, reviewed=None):
    subprocess.run(['git','clone','--depth','1','--branch',tag,'https://github.com/lxqt/'+repo+'.git',target],check=True)
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=target,text=True).strip()
    if reviewed is not None and revision != reviewed:
        raise RuntimeError('Upstream '+repo+' tag '+tag+' changed; refusing unreviewed source')
    return revision


def build(work, display_controls=False, tag=None, jobs=4):
    from panel.build import TOOLS
    from native_rebuild import snapshot
    work = work.resolve()
    if work.exists() and any(work.iterdir()): raise ValueError('Choose an empty permanent build directory')
    tag = tag or system_tag()
    if not re.fullmatch(r'\d+\.\d+\.\d+', tag): raise ValueError('Expected a PCManFM release tag like 2.5.0')
    work.mkdir(parents=True, exist_ok=True)
    source = work/'source'
    revision = clone('pcmanfm-qt', tag, source, REVISIONS.get(tag))
    # PCManFM states the lxqt-build-tools it needs; build that privately, like the panel does.
    needed = re.search(r'set\(LXQTBT_MINIMUM_VERSION "(\d+\.\d+\.\d+)"\)', (source/'CMakeLists.txt').read_text())
    if not needed: raise RuntimeError('PCManFM '+tag+' does not state its lxqt-build-tools version')
    pinned = dict(TOOLS.values()).get(needed[1])
    clone('lxqt-build-tools', needed[1], work/'tools', pinned)
    deps = work/'deps'
    subprocess.run(['cmake','-S',work/'tools','-B',work/'tools-build','-G','Ninja','-DCMAKE_INSTALL_PREFIX='+str(deps)],check=True)
    subprocess.run(['cmake','--build',work/'tools-build'],check=True)
    subprocess.run(['cmake','--install',work/'tools-build'],check=True)
    subprocess.run(['git','apply','--check',ROOT/'desktop-video.patch'],cwd=source,check=True)
    subprocess.run(['git','apply',ROOT/'desktop-video.patch'],cwd=source,check=True)
    for name in ('dorowallpaper.cpp','dorowallpaper.h','dorovideoworker.cpp','dorovideotransport.h'): shutil.copy2(ROOT/name,source/'pcmanfm'/name)
    if display_controls:
        from display.build_candidate import prepare
        prepare(source, work/'build/pcmanfm')
    from wallpaper.preferences import prepare as prepare_preferences
    prepare_preferences(source)
    subprocess.run(['cmake','-S',source,'-B',work/'build','-G','Ninja','-DCMAKE_INSTALL_PREFIX=/usr',
                    '-DCMAKE_PREFIX_PATH='+str(deps)],check=True)
    subprocess.run(['cmake','--build',work/'build','--target','pcmanfm-qt','-j',str(jobs)],check=True)
    binary=work/'build/pcmanfm/pcmanfm-qt'
    snapshot(work)
    write_build_record(binary, display_controls, tag, revision)
    print('Native desktop for next-login setup:',binary)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--display-controls', action='store_true', help='Include session-only Advanced display controls and their guarded helper')
    parser.add_argument('--tag', help='PCManFM release to build; default: the installed pcmanfm-qt version')
    parser.add_argument('--jobs', type=int, default=4)
    args=parser.parse_args();build(args.work, args.display_controls, args.tag, args.jobs)
