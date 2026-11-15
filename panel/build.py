#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build the isolated DoroShell Panel prototype; never install system packages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

PANEL_REV = 'cffb0cd29c6ce0360356006ce727a9b01347e062'
TOOLS = {
    '2.4': ('2.4.0', '0f56cd400d2afcb6f16d4ca88538ed716439c2c2'),
    '2.5': ('2.5.0', 'ca90f9b0c5eedc3ab89d4031811dff833392bf3b'),
}
ROOT = Path(__file__).resolve().parent
PATCHES = ('0001-hidden-tray-popup.patch','0002-wallpaper-glass.patch','0003-launcher-identity.patch','0004-filtered-pins.patch','0005-tray-attention-popup.patch','0006-tray-keyboard-context.patch','0007-show-desktop-drag.patch','0008-panel-density.patch','0009-tray-registration-popup.patch','0010-tray-shortcut.patch','0011-calendar-bounds.patch')


class BuildError(RuntimeError):
    """An expected prerequisite/source/build refusal, safe to show without traceback."""


def cmake_path(path):
    path = Path(path)
    def validate(candidate):
        if not candidate.is_absolute() or any(c == ';' or ord(c) < 32 or ord(c) == 127 for c in str(candidate)):
            raise BuildError('Use an absolute prefix/work path without CMake list separators or control characters')
    validate(path)
    resolved = path.resolve()
    validate(resolved)
    return resolved


def config_dir(prefix):
    found = [prefix/p/'lxqt' for p in ('share/cmake', 'lib/cmake', 'lib64/cmake')
             if (prefix/p/'lxqt/lxqt-config.cmake').is_file()]
    if len(found) > 1:
        raise BuildError('Ambiguous liblxqt CMake metadata in prefix: '+str(prefix))
    return found[0] if found else None


def metadata(path):
    with path.open('rb') as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise BuildError('Oversized liblxqt CMake metadata: '+str(path))
    try:
        return data.decode('utf-8'), hashlib.sha256(data).hexdigest()
    except UnicodeError as exc:
        raise BuildError('Invalid liblxqt CMake metadata: '+str(path)) from exc


def literal_version(text, command, name):
    lines = re.findall(r'^\s*'+command+r'\s*\(\s*'+re.escape(name)+r'\s+([^\n]*)$', text, re.M)
    if (command, name) == ('set', 'PACKAGE_VERSION'):
        # CMake's generated version file annotates mismatched architecture later.
        lines = [line for line in lines if line.strip() != '"${PACKAGE_VERSION} (${installedBits}bit)")']
    match = re.fullmatch(r'("?)(\d+\.\d+\.\d+)\1\s*\)\s*(?:#.*)?', lines[0]) if len(lines) == 1 else None
    if not match:
        raise BuildError('Unsupported liblxqt metadata for '+name+'; use standard generated LXQt 2.4/2.5 development files')
    return match[2]


def dependencies(lxqt_prefix=None):
    """Read installed metadata only; no downloads, CMake execution or directory creation."""
    missing = [name for name in ('git', 'cmake', 'ninja', 'pkg-config', 'c++') if not shutil.which(name)]
    if missing:
        raise BuildError('Missing build tools: '+', '.join(missing)+
                         '. On Arch review: sudo pacman -Syu --needed base-devel git cmake ninja pkgconf')
    reported = None
    if lxqt_prefix is not None:
        prefix = cmake_path(lxqt_prefix)
    else:
        prefixes = [cmake_path(p) for p in os.environ.get('CMAKE_PREFIX_PATH', '').split(os.pathsep) if p]
        prefix = next((p for p in prefixes if config_dir(p)), None)
        if prefix is None:
            try:
                prefix = cmake_path(subprocess.check_output(['pkg-config', '--variable=prefix', 'lxqt'], text=True, timeout=10).strip())
                reported = subprocess.check_output(['pkg-config', '--modversion', 'lxqt'], text=True, timeout=10).strip()
            except subprocess.CalledProcessError as exc:
                raise BuildError('liblxqt development metadata is missing. Review deploy.py package plan, or pass --lxqt-prefix /prepared/prefix') from exc
    directory = config_dir(prefix)
    if directory is None:
        raise BuildError('No liblxqt CMake development files in '+str(prefix)+'; install coherent development dependencies or pass --lxqt-prefix')
    contents, hashes = {}, {}
    for name in ('lxqt-config.cmake', 'lxqt-config-version.cmake'):
        contents[name], hashes[str(directory/name)] = metadata(directory/name)
    config = contents['lxqt-config.cmake']
    version = literal_version(config, 'set', 'LXQT_VERSION')
    advertised = literal_version(contents['lxqt-config-version.cmake'], 'set', 'PACKAGE_VERSION')
    if version != advertised or reported is not None and reported != version:
        raise BuildError('Conflicting liblxqt pkg-config/CMake versions; use a coherent --lxqt-prefix')
    family = '.'.join(version.split('.')[:2])
    if family not in TOOLS:
        raise BuildError('Unsupported liblxqt '+version+'; pinned panel 2.4.1 currently supports the 2.4/2.5 build families only')
    tag, revision = TOOLS[family]
    required = literal_version(config, 'find_dependency', 'lxqt2-build-tools')
    if required != tag:
        raise BuildError('liblxqt '+version+' requires build-tools '+required+'; reviewed pin is '+tag+'. A new source pin must be reviewed')
    needs = [name+' >= '+literal_version(config, 'find_dependency', name) for name in ('Qt6Widgets', 'Qt6DBus', 'Qt6Xdg')]
    needs.append('gio-unix-2.0')
    absent = [need for need in needs if subprocess.run(['pkg-config', '--exists', need], timeout=10).returncode]
    if absent:
        raise BuildError('Missing development dependencies: '+', '.join(absent)+
                         '. Review deploy.py package plan; prepared dependencies may need PKG_CONFIG_PATH')
    return {'lxqt_version': version, 'lxqt_prefix': str(prefix), 'lxqt_dir': str(directory),
            'metadata_sha256': hashes, 'tools_tag': tag, 'tools_revision': revision}


def patch_paths():
    declared = set(PATCHES)
    present = {p.name for p in (ROOT/'patches').glob('*.patch')}
    if len(declared) != len(PATCHES) or declared != present:
        raise BuildError('Panel patch inventory mismatch: missing=' + str(sorted(declared-present))
                           + ', unlisted=' + str(sorted(present-declared)))
    return tuple(ROOT/'patches'/name for name in PATCHES)



def run(args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def build(work, jobs, lxqt_prefix=None):
    patches = patch_paths()
    work = cmake_path(work.absolute())
    if work.exists() and any(work.iterdir()):
        raise BuildError('Choose an empty build directory; existing files are preserved')
    selected = dependencies(lxqt_prefix)
    work.mkdir(parents=True, exist_ok=True)
    record = dict(selected, panel_tag='2.4.1', panel_revision=PANEL_REV, status='building',
                  patches_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in patches})
    record_path = work/'build-provenance.json'
    record_path.write_text(json.dumps(record, indent=2)+'\n')
    try:
        build_selected(work, jobs, patches, selected)
        record['status'] = 'complete'
        record_path.write_text(json.dumps(record, indent=2)+'\n')
        shutil.copy2(record_path, work/'runtime/share/doroshell-panel'/record_path.name)
    except BaseException:
        record['status'] = 'failed-or-interrupted'
        record_path.write_text(json.dumps(record, indent=2)+'\n')
        raise
    print('Built:',work/'runtime/bin/lxqt-panel')
    print('Keep this directory: runtime plugin paths are tied to its prefix. Nothing is enabled.')


def build_selected(work, jobs, patches, selected):
    for name, repo, tag, revision in [('source', 'lxqt-panel', '2.4.1', PANEL_REV),
                                      ('tools', 'lxqt-build-tools', selected['tools_tag'], selected['tools_revision'])]:
        target = work/name
        run(['git', 'clone', '--depth', '1', '--branch', tag, 'https://github.com/lxqt/'+repo+'.git', target])
        actual = subprocess.check_output(['git','rev-parse','HEAD'], cwd=target, text=True).strip()
        if actual != revision:
            raise BuildError('Upstream '+repo+' tag changed; refusing unreviewed source')
    for patch in patches:
        run(['git','apply','--check',patch], cwd=work/'source')
        run(['git','apply',patch], cwd=work/'source')
    deps, prefix = work/'deps', work/'runtime'
    run(['cmake','-S',work/'tools','-B',work/'tools-build','-G','Ninja','-DCMAKE_INSTALL_PREFIX='+str(deps)])
    run(['cmake','--build',work/'tools-build','-j',jobs])
    run(['cmake','--install',work/'tools-build'])
    for path, digest in selected['metadata_sha256'].items():
        if metadata(Path(path))[1] != digest:
            raise BuildError('liblxqt metadata changed during acquisition; use a fresh build directory after reviewing dependencies')
    run(['cmake','-S',work/'source','-B',work/'build','-G','Ninja','-DCMAKE_INSTALL_PREFIX='+str(prefix),
         '-DCMAKE_PREFIX_PATH='+str(deps)+';'+selected['lxqt_prefix'],
         '-Dlxqt_DIR='+selected['lxqt_dir'],
         '-Dlxqt2-build-tools_DIR='+str(deps/'share/cmake/lxqt2-build-tools')])
    run(['cmake','--build',work/'build','-j',jobs])
    # Upstream also installs /etc/xdg files: stage them, never write system paths.
    stage=work/'stage'
    run(['cmake','--install',work/'build'], env=dict(os.environ, DESTDIR=str(stage)))
    shutil.copytree(stage/str(prefix).lstrip('/'),prefix,dirs_exist_ok=True)
    notices=prefix/'share/doroshell-panel';notices.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'licenses',notices/'licenses',dirs_exist_ok=True)
    for patch in patches:
        shutil.copy2(patch,notices/patch.name)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path)
    parser.add_argument('--jobs',type=int,default=4)
    parser.add_argument('--lxqt-prefix',type=Path,help='Prepared liblxqt installation prefix; default: CMAKE_PREFIX_PATH, then pkg-config')
    parser.add_argument('--check-dependencies',action='store_true',help='Read-only version/pin check; no acquisition/build/install')
    args=parser.parse_args(argv)
    if args.jobs < 1: parser.error('--jobs must be positive')
    if not args.check_dependencies and args.work is None: parser.error('--work is required for a build')
    try:
        if args.check_dependencies:
            print(json.dumps(dependencies(args.lxqt_prefix), indent=2))
            print('Version selection only; CMake still checks remaining panel development dependencies. Nothing downloaded or built.')
        else:
            build(args.work,args.jobs,args.lxqt_prefix)
    except (BuildError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print('Panel build: '+str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
