#!/usr/bin/env python3
"""Build the optional PCManFM background renderer; never replace system binaries."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

REVISION = '8c4715a327170c20e7d7f3088e9cdc29ca485ba0'
ROOT = Path(__file__).resolve().parent


def write_build_record(binary, display_controls=False):
    helper = binary.with_name('doroshell-video-worker')
    if not helper.is_file():
        raise RuntimeError('Build did not produce the decoder helper')
    record = dict(revision=REVISION, format=2, sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest())
    if display_controls:
        display_helper = binary.with_name('doroshell-display-backend.py')
        if not display_helper.is_file():
            raise RuntimeError('Build did not produce the display helper')
        record.update(format=3, display_helper_sha256=hashlib.sha256(display_helper.read_bytes()).hexdigest())
    binary.with_name('doroshell-wallpaper-build.json').write_text(json.dumps(record))


def build(work, display_controls=False):
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()): raise ValueError('Choose an empty permanent build directory')
    source = work/'source'
    subprocess.run(['git','clone','--depth','1','--branch','2.4.0','https://github.com/lxqt/pcmanfm-qt.git',source],check=True)
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()!=REVISION:
        raise RuntimeError('Upstream tag changed; refusing unreviewed source')
    subprocess.run(['git','apply','--check',ROOT/'desktop-video.patch'],cwd=source,check=True)
    subprocess.run(['git','apply',ROOT/'desktop-video.patch'],cwd=source,check=True)
    for name in ('dorowallpaper.cpp','dorowallpaper.h','dorovideoworker.cpp','dorovideotransport.h'): shutil.copy2(ROOT/name,source/'pcmanfm'/name)
    if display_controls:
        import sys
        sys.path.insert(0, str(ROOT.parent))
        from display.build_candidate import prepare
        prepare(source, work/'build/pcmanfm')
    import sys
    sys.path.insert(0, str(ROOT.parent))
    from wallpaper.preferences import prepare as prepare_preferences
    prepare_preferences(source)
    subprocess.run(['cmake','-S',source,'-B',work/'build','-G','Ninja','-DCMAKE_INSTALL_PREFIX=/usr'],check=True)
    subprocess.run(['cmake','--build',work/'build','--target','pcmanfm-qt','-j4'],check=True)
    binary=work/'build/pcmanfm/pcmanfm-qt'
    write_build_record(binary, display_controls)
    print('Native desktop for next-login setup:',binary)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--display-controls', action='store_true', help='Include session-only Advanced display controls and their guarded helper')
    args=parser.parse_args();build(args.work, args.display_controls)
