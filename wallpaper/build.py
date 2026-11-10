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


def write_build_record(binary):
    helper = binary.with_name('doroshell-video-worker')
    if not helper.is_file():
        raise RuntimeError('Build did not produce the decoder helper')
    binary.with_name('doroshell-wallpaper-build.json').write_text(json.dumps(dict(
        revision=REVISION, format=2, sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest())))


def build(work):
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
    subprocess.run(['cmake','-S',source,'-B',work/'build','-G','Ninja','-DCMAKE_INSTALL_PREFIX=/usr'],check=True)
    subprocess.run(['cmake','--build',work/'build','--target','pcmanfm-qt','-j4'],check=True)
    binary=work/'build/pcmanfm/pcmanfm-qt'
    write_build_record(binary)
    print('Native desktop for next-login setup:',binary)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    build(parser.parse_args().work)
