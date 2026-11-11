#!/usr/bin/env python3
"""Refresh or verify the tracked source inventory; never package untracked files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
MANIFEST = 'SOURCE-MANIFEST.json'
SCAN = 'SOURCE-SCAN.json'
SUMS = 'SHA256SUMS'


def source_files(root):
    if (root/'.git').exists():
        data = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root)
        return sorted(data.decode().strip('\0').split('\0'))
    # An extracted git archive has no index. Ignore only Python test caches.
    return sorted(p.relative_to(root).as_posix() for p in root.rglob('*')
                  if (p.is_file() or p.is_symlink()) and '__pycache__' not in p.parts
                  and p.suffix != '.pyc')


def payload(root, name):
    path = root/name
    if path.is_symlink() or not path.is_file():
        raise ValueError('Source must be a regular file: '+name)
    data = path.read_bytes()
    if b'\0' in data:
        raise ValueError('Binary payload in source inventory: '+name)
    data.decode('utf-8')
    return {'path': name, 'sha256': hashlib.sha256(data).hexdigest(),
            'size': len(data), 'mode': oct(path.stat().st_mode & 0o777)}


def scan_record(files):
    return {'files': files, 'file_count': len(files), 'source_payload_count': len(files)-2,
            'checks': ['Tracked regular UTF-8 source files; no NUL binaries or symlinks',
                       'Payload hashes and complete file inventory checked',
                       'Manual privacy and component-license scope: see RELEASE-CANDIDATE.md'],
            'private_deployment_plan': 'not included'}


def checksum_text(root, files):
    return ''.join(payload(root, name)['sha256']+'  '+name+'\n' for name in files if name != SUMS)


def require_tracked_patches(root, files):
    omitted = sorted(p.relative_to(root).as_posix() for p in (root/'panel/patches').glob('*.patch')
                     if p.relative_to(root).as_posix() not in files)
    if omitted:
        raise ValueError('Panel patches omitted from tracked inventory: '+str(omitted))


def refresh(root, files):
    require_tracked_patches(root, files)
    for name in files:
        payload(root, name)
    for name in (MANIFEST, SCAN, SUMS):
        if name not in files:
            raise ValueError('Missing tracked release metadata: '+name)
    (root/SCAN).write_text(json.dumps(scan_record(files), indent=2)+'\n')
    manifest = json.loads((root/MANIFEST).read_text())
    manifest['source_payloads'] = [payload(root, name) for name in files if name not in (MANIFEST, SUMS)]
    (root/MANIFEST).write_text(json.dumps(manifest, indent=2)+'\n')
    (root/SUMS).write_text(checksum_text(root, files))


def check(root, files):
    require_tracked_patches(root, files)
    if json.loads((root/SCAN).read_text()) != scan_record(files):
        raise ValueError('Source inventory changed; stage intended files and refresh metadata')
    actual = [payload(root, name) for name in files if name not in (MANIFEST, SUMS)]
    if json.loads((root/MANIFEST).read_text())['source_payloads'] != actual:
        raise ValueError('Source payload hashes or modes changed; refresh metadata')
    if (root/SUMS).read_text() != checksum_text(root, files):
        raise ValueError('SHA256SUMS is stale or incomplete')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    if args.refresh:
        if not (ROOT/'.git').exists():
            parser.error('Refresh only in a Git checkout after staging intended files')
        refresh(ROOT, source_files(ROOT))
    check(ROOT, source_files(ROOT))
    print('Source inventory, payload hashes, modes and SHA256SUMS verified')
