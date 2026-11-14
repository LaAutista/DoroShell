#!/usr/bin/env python3
"""Plan/install/update/remove DoroShell through its existing reversible modules."""
import argparse
import base64
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

import compatibility
from install import atomic, safe as install_safe
from setup import PACKAGES

ROOT = Path(__file__).resolve().parent
CORE = ['menu', 'native-panel', 'theme', 'cursor', 'snapping', 'screenshots', 'maintenance']
ORDER = [*CORE, 'clipboard', 'wallpaper', 'wallpaper-glass', 'display']
OPTIONAL = ['clipboard', 'wallpaper', 'wallpaper-glass', 'display']
POINTER = '.local/state/doroshell/deployment.json'
TRANSACTION = r'[0-9]{8}T[0-9]{6}-[0-9a-f]{12}'
BUILD_PACKAGES = ['base-devel', 'git', 'cmake', 'ninja', 'pkgconf', 'qt6-base', 'qt6-tools',
                  'liblxqt', 'lxqt-build-tools', 'libqtxdg', 'kwindowsystem', 'layer-shell-qt']
PANEL_PACKAGES = ['libdbusmenu-lxqt', 'solid', 'libsysstat', 'libstatgrab', 'libxdamage',
                  'libxkbcommon-x11', 'libpulse', 'alsa-lib', 'lm_sensors', 'libxtst']


def safe(path, home):
    install_safe(path, home)
    for part in [path, *path.parents]:
        if part.is_symlink(): raise ValueError('Refusing symlink in managed path: '+str(part))
        if part == home: break


def select_modules(names, extras=(), expand=True):
    requested = set(names) | set(extras)
    if 'core' in requested: requested = (requested-{'core'}) | set(CORE)
    unknown = requested-set(ORDER)
    if unknown: raise ValueError('Unknown modules: '+', '.join(sorted(unknown)))
    if 'display' in requested: requested.add('wallpaper')
    if expand and 'clipboard' in requested: requested.add('native-panel')
    if expand and 'native-panel' in requested: requested.add('menu')
    return [name for name in ORDER if name in requested]


def packages_for(selected):
    packages = {'git', 'python'}
    for name in selected: packages.update(PACKAGES.get(name, []))
    if 'cursor' in selected: packages.add('breeze-cursors')
    if 'native-panel' in selected: packages.update(BUILD_PACKAGES+PANEL_PACKAGES)
    if 'wallpaper' in selected: packages.update(BUILD_PACKAGES+['libfm-qt', 'xorg-xrandr'])
    return sorted(packages)


def run(argv, **kwargs):
    subprocess.run([str(a) for a in argv], check=True, **kwargs)


def file_state(home, name):
    path = home/name
    safe(path, home)
    if not path.exists(): return {'data': None, 'mode': None}
    if not path.is_file(): raise ValueError('Expected regular file: '+name)
    return {'data': base64.b64encode(path.read_bytes()).decode(), 'mode': path.stat().st_mode & 0o777}


def validate_snapshot(home, snapshot):
    from install import validate_backup
    if not isinstance(snapshot, dict): raise ValueError('Invalid recovery snapshot')
    for name, value in snapshot.items():
        if (not isinstance(name, str) or not name or name == '.' or '\0' in name
                or Path(name).is_absolute() or '..' in Path(name).parts or str(Path(name)) != name):
            raise ValueError('Invalid recovery path')
        safe(home/name, home)
        validate_backup(value)
        if set(value) != {'data', 'mode'} or (value['data'] is None) != (value['mode'] is None):
            raise ValueError('Invalid recovery snapshot bytes/mode')


def module_list(value):
    if (not isinstance(value, list) or any(not isinstance(m, str) or m not in ORDER for m in value)
            or len(value) != len(set(value))):
        raise ValueError('Invalid recovery module list')
    return value


def validate_pointer(record):
    if (not isinstance(record, dict) or type(record.get('format')) is not int or record['format'] != 1
            or record.get('status') not in ('pending', 'complete')
            or not isinstance(record.get('transaction'), str) or not re.fullmatch(TRANSACTION, record['transaction'])):
        raise ValueError('Unsupported or invalid deployment record; no migration is guessed')
    module_list(record.get('modules'))
    if record['status'] == 'complete' and not valid_hash(record.get('source')):
        raise ValueError('Invalid deployment source hash')


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def validate_journal(home, journal, identifier):
    """Validate every consumed field before recovery, finalization or undo writes."""
    if (not isinstance(journal, dict) or type(journal.get('format')) is not int or journal['format'] not in (1, 2)
            or journal.get('status') not in ('pending', 'complete', 'undoing', 'undone')):
        raise ValueError('Unsupported or invalid deployment journal')
    if journal['format'] == 1 and journal['status'] == 'pending':
        raise ValueError('Legacy pending journal has no completed-step evidence; preserve it for manual inspection')
    request = journal.get('request')
    if (not isinstance(request, dict) or set(request) != {'modules', 'remove', 'theme', 'source'}
            or type(request.get('remove')) is not bool
            or request.get('theme') not in ('windows', 'polar', 'heretic', 'spring')
            or not valid_hash(request.get('source'))):
        raise ValueError('Invalid recovery request')
    selected = module_list(request.get('modules'))
    module_list(journal.get('installed_before'))
    sequence = [m for m in selected if m != 'display']
    if request['remove']: sequence.reverse()
    done = module_list(journal.get('done'))
    active = journal.get('active')
    if ('active' not in journal or done != sequence[:len(done)] or len(done) > len(sequence)
            or (active is not None and (len(done) == len(sequence) or active != sequence[len(done)]))):
        raise ValueError('Invalid recovery progress')
    before, after = journal.get('before'), journal.get('after')
    validate_snapshot(home, before); validate_snapshot(home, after)
    if POINTER not in before: raise ValueError('Missing original deployment record')
    if before[POINTER]['data'] is not None:
        previous = json.loads(base64.b64decode(before[POINTER]['data'], validate=True))
        validate_pointer(previous)
        if previous['status'] != 'complete': raise ValueError('Invalid original deployment status')
    if journal['format'] == 2:
        names = journal.get('active_files')
        if (not isinstance(names, list) or any(not isinstance(n, str) or n not in before or n == POINTER for n in names)
                or len(names) != len(set(names)) or (active is None and names)):
            raise ValueError('Invalid active recovery inventory')
        if journal['status'] == 'pending' and (POINTER in after or set(after) | set(names) != set(before)-{POINTER}):
            raise ValueError('Missing completed-step recovery evidence')
    if journal['status'] != 'pending':
        if active is not None or done != sequence or set(before) != set(after):
            raise ValueError('Incomplete recovery inventory')
        if after[POINTER]['data'] is None: raise ValueError('Missing final deployment record')
        final = json.loads(base64.b64decode(after[POINTER]['data'], validate=True))
        validate_pointer(final)
        if final['status'] != 'complete' or final['transaction'] != identifier or final['source'] != request['source']:
            raise ValueError('Mismatched final deployment record')


def load_journal(home, identifier):
    if not isinstance(identifier, str) or not re.fullmatch(TRANSACTION, identifier):
        raise ValueError('Choose the exact transaction ID printed after installation')
    path = home/'.local/state/doroshell/deployments'/identifier/'journal.json'
    safe(path, home)
    journal = json.loads(path.read_text())
    validate_journal(home, journal, identifier)
    return path, journal


def check_completed(home, journal, changing=()):
    for name, value in journal['after'].items():
        if name != POINTER and name not in changing and file_state(home, name) != value:
            raise RuntimeError('Edited completed deployment file; recovery/finalization refused: '+name)


def recovery_journal(home, previous):
    if not previous or previous['status'] != 'pending': raise ValueError('No pending deployment')
    path, journal = load_journal(home, previous['transaction'])
    if journal['status'] not in ('pending', 'complete') or journal['request']['modules'] != previous['modules']:
        raise ValueError('Mismatched pending deployment journal')
    check_completed(home, journal)
    return path, journal


def undo(home, identifier):
    path, journal = load_journal(home, identifier)
    if journal['status'] not in ('complete', 'undoing', 'undone'):
        raise ValueError('Incomplete transaction: use --recover first; original module backups are retained')
    if journal['status'] == 'undone': return
    before, after = journal['before'], journal['after']
    for name in before:
        current = file_state(home, name)
        allowed = (after[name], before[name]) if journal['status'] == 'undoing' else (after[name],)
        if current not in allowed: raise RuntimeError('Edited file; undo refused: '+name)
    journal['status'] = 'undoing'; atomic(path, json.dumps(journal).encode())
    for name, value in reversed(list(before.items())):
        current = file_state(home, name)
        if current not in (before[name], after[name]): raise RuntimeError('Concurrent edit; undo stopped: '+name)
        if value['data'] is None: (home/name).unlink(missing_ok=True)
        else: atomic(home/name, base64.b64decode(value['data'], validate=True), value['mode'])
    journal['status'] = 'undone'; atomic(path, json.dumps(journal).encode())
    print('Restored exact pre-transaction files and manifests. No running process changed.')


def build_native(home, selected, versions):
    result = {}
    for name in ('native-panel', 'wallpaper'):
        if name not in selected: continue
        folders = ['panel'] if name == 'native-panel' else ['wallpaper', 'display']
        digest = hashlib.sha256(json.dumps(versions, sort_keys=True).encode())
        for folder in folders:
            for path in sorted((ROOT/folder).rglob('*')):
                if path.is_file() and path.suffix in ('.py', '.cpp', '.h', '.patch') and '__pycache__' not in path.parts:
                    digest.update(str(path.relative_to(ROOT)).encode()); digest.update(path.read_bytes())
        digest.update(str('display' in selected).encode())
        work = home/'.local/share/doroshell/builds'/(name+'-'+digest.hexdigest()[:16])
        safe(work, home)
        proof = work/'deployment-build.json'
        relative = 'runtime/bin/lxqt-panel' if name == 'native-panel' else 'build/pcmanfm/pcmanfm-qt'
        runtime = work/'runtime' if name == 'native-panel' else work/'build/pcmanfm'
        def inventory():
            return {str(p.relative_to(work)): dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mode=p.stat().st_mode & 0o777)
                    for p in runtime.rglob('*') if p.is_file()}
        if proof.is_file():
            record = json.loads(proof.read_text())
            if relative not in record or inventory() != record:
                raise RuntimeError('Changed native build; preserve it and build in a new directory: '+str(work))
        else:
            if work.exists() and any(work.iterdir()):
                raise RuntimeError('Incomplete build retained at '+str(work)+'; move it aside before retrying.')
            script = 'panel/build.py' if name == 'native-panel' else 'wallpaper/build.py'
            cmd = [sys.executable, ROOT/script, '--work', work]
            if name == 'wallpaper' and 'display' in selected: cmd.append('--display-controls')
            run(cmd)
            atomic(proof, json.dumps(inventory(), sort_keys=True).encode())
        result[name] = work/relative
    return result


def manifest_for(home, name):
    if name == 'menu': return home/'.local/state/lxqt-comfort/menu-install.json'
    if name == 'cursor': return home/'.local/state/lxqt-comfort/cursor-install.json'
    return home/'.local/state/doroshell'/(name+'.json')


def installed_modules(home):
    """Recognize legacy module manifests without importing personal preferences."""
    result = [name for name in ORDER if name != 'display' and manifest_for(home, name).is_file()]
    wrapper = home/'.local/bin/doroshell-wallpaper-desktop'
    safe(wrapper, home)
    if 'wallpaper' in result and wrapper.is_file() and 'doroshell-display-backend.py' in wrapper.read_text():
        result.append('display')
    return result


def step(home, name, binaries, theme, remove=False, job=None):
    """Return the managed path inventory and the existing adapter operation."""
    import install, modules
    manifest = manifest_for(home, name)
    paths = {manifest}
    if name == 'menu':
        icon = ROOT/'assets/doro/start.png' if not manifest.exists() and not (home/'.local/share/lxqt-comfort/start-icon.png').exists() else None
        paths.update(install.targets(home, icon))
        paths.update(home/'.local/state/lxqt-comfort/desktop-before'/p for p in ('panel.conf', 'globalkeyshortcuts.conf'))
        operation = lambda: install.rollback(home) if remove else install.install(home, True, icon)
    elif name == 'cursor':
        import cursor
        if remove:
            record = json.loads(manifest.read_text()) if manifest.exists() else {}
            paths.update(home/key for key in record)
        else: paths.update(cursor.targets(home, ROOT/'assets/cursors/spin-doro-transparent.apng', Path('/usr/share/icons/breeze_cursors')))
        operation = lambda: cursor.run(home, ROOT/'assets/cursors/spin-doro-transparent.apng', apply=not remove, rollback=remove)
    elif name == 'native-panel':
        from panel import profile
        paths.update(home/p for p in ('.config/doroshell/panel.conf', '.config/autostart/lxqt-panel.desktop', '.local/bin/doroshell-native-panel'))
        if remove: operation = lambda: profile.switch(home, rollback=True)
        elif manifest.exists(): operation = lambda: profile.upgrade(home, binaries[name])
        else:
            prepared = job/'panel'
            if not (prepared/'plan.json').exists(): profile.prepare(home, prepared, binaries[name])
            operation = lambda: profile.switch(home, prepared)
    else:
        kwargs = dict(theme=theme, wallpaper_binary=binaries.get('wallpaper'))
        edits = json.loads(manifest.read_text())['edits'] if remove and manifest.exists() else [] if remove else modules.plans(home, name, **kwargs)
        paths.update(home/e['file'] for e in edits)
        if manifest.exists(): paths.update(home/p for p in json.loads(manifest.read_text())['backup'])
        operation = lambda: modules.run(home, name, apply=not remove, rollback=remove, **kwargs)
    return [str(p.relative_to(home)) for p in sorted(paths)], operation


def deploy(home, selected, binaries, theme='windows', remove=False, recover=False):
    state = home/'.local/state/doroshell'
    pointer = state/'deployment.json'
    safe(pointer, home)
    previous = json.loads(pointer.read_text()) if pointer.exists() else None
    if previous is not None: validate_pointer(previous)
    if previous and previous['status'] == 'pending' and not recover:
        raise RuntimeError('Interrupted deployment '+previous['transaction']+'; use --recover from the same source or inspect its private journal')
    if recover:
        if not previous or previous['status'] != 'pending': raise ValueError('No pending deployment')
        identifier = previous['transaction']
    else: identifier = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S-')+uuid.uuid4().hex[:12]
    job = state/'deployments'/identifier
    path = job/'journal.json'; safe(path, home)
    source = hashlib.sha256((ROOT/'SHA256SUMS').read_bytes()).hexdigest()
    request = dict(modules=selected, remove=remove, theme=theme, source=source)
    if recover:
        path, journal = recovery_journal(home, previous)
        if journal['request'] != request: raise ValueError('Recovery needs the same revision, modules, theme and action')
        if journal['status'] == 'complete':
            target = str(pointer.relative_to(home))
            atomic(pointer, base64.b64decode(journal['after'][target]['data'], validate=True), journal['after'][target]['mode'])
            print('Completed interrupted deployment finalization:', identifier)
            return identifier
    else:
        job.mkdir(parents=True); job.chmod(0o700)
        journal = dict(format=2, status='pending', request=request, done=[], active=None, active_files=[], installed_before=installed_modules(home),
                       before={str(pointer.relative_to(home)):file_state(home, str(pointer.relative_to(home)))}, after={})
        validate_journal(home, journal, identifier)
        atomic(path, json.dumps(journal).encode())
        atomic(pointer, json.dumps(dict(format=1,status='pending',transaction=identifier,modules=selected)).encode())
    sequence = [m for m in selected if m != 'display']
    if remove: sequence.reverse()
    for index, name in enumerate(sequence, 1):
        if name in journal['done']: continue
        check_completed(home, journal)
        # Existing preferences stay as chosen on update. Their original manifests
        # still support removal; explicit changes use setup.py/settings.
        if not remove and name in ('theme', 'cursor', 'wallpaper-glass') and manifest_for(home, name).exists() and journal['active'] != name:
            print('Preserve existing '+name+' selection'); journal['done'].append(name)
            atomic(path, json.dumps(journal).encode()); continue
        print(f'[{index}/{len(sequence)}] {"Restore" if remove else "Install/update"} {name}', flush=True)
        names, operation = step(home, name, binaries, theme, remove, job)
        if journal['active'] == name and set(names) != set(journal['active_files']):
            raise ValueError('Changed pending module inventory; preserve the journal for inspection')
        for target in names:
            journal['before'].setdefault(target, file_state(home, target))
        journal['active'] = name; journal['active_files'] = names
        atomic(path, json.dumps(journal).encode())
        operation()
        # Only the successful adapter's declared paths may replace earlier evidence.
        # An interrupted overlapping step has no such proof and is refused on retry.
        check_completed(home, journal, names)
        journal['after'].update({target:file_state(home, target) for target in names})
        journal['done'].append(name); journal['active'] = None; journal['active_files'] = []
        atomic(path, json.dumps(journal).encode())
    check_completed(home, journal)
    previous_data = journal['before'][str(pointer.relative_to(home))]['data']
    installed = set(json.loads(base64.b64decode(previous_data))['modules']) if previous_data else set(journal['installed_before'])
    installed = installed-set(selected) if remove else installed|set(selected)
    final_pointer = json.dumps(dict(format=1,status='complete',transaction=identifier,
                                   modules=[m for m in ORDER if m in installed], source=source)).encode()
    journal['after'][str(pointer.relative_to(home))] = dict(data=base64.b64encode(final_pointer).decode(), mode=0o600)
    journal['status'] = 'complete'; validate_journal(home, journal, identifier)
    atomic(path, json.dumps(journal).encode())
    atomic(pointer, final_pointer)
    print('Transaction:', identifier)
    print('Exact previous-upgrade undo: python '+str(ROOT/'deploy.py')+' --apply --undo '+identifier)
    print('Module --remove restores first-install originals. Builds/backups and personal preferences remain.')
    print('No session restarted. Native panel/desktop changes take effect at your next normal login.')
    return identifier


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modules', nargs='+', help='Default: recorded modules, or core on first install')
    parser.add_argument('--with', dest='extras', action='append', choices=OPTIONAL, default=[])
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--theme', choices=('windows','polar','heretic','spring'), default='windows')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--remove', action='store_true', help='Restore selected modules to first-install baseline; requires --apply')
    parser.add_argument('--recover', action='store_true', help='Retry pending module using existing conflict checks; requires --apply')
    parser.add_argument('--undo', metavar='TRANSACTION', help='Exact prior-upgrade restoration; requires --apply')
    parser.add_argument('--no-packages', action='store_true', help='Refuse missing packages instead of offering pacman')
    args = parser.parse_args(argv)
    home = args.home.absolute()
    safe(home, home)
    pointer = home/'.local/state/doroshell/deployment.json'; safe(pointer, home)
    previous = json.loads(pointer.read_text()) if pointer.exists() else None
    if previous is not None: validate_pointer(previous)
    previous = previous or {}
    if args.undo:
        _, journal = load_journal(home, args.undo)
        if journal['status'] == 'pending': raise ValueError('Incomplete transaction: use --recover first')
    if args.recover:
        _, journal = recovery_journal(home, previous)
        request = journal['request']
        if args.modules is None: args.modules = request['modules']
        args.theme = request['theme']; args.remove = request['remove']
    defaults = previous.get('modules', list(dict.fromkeys([*CORE, *installed_modules(home)])))
    selected = select_modules(args.modules if args.modules is not None else defaults, args.extras, not args.remove)
    if args.recover and selected != request['modules']:
        raise ValueError('Recovery needs the recorded module set; no prerequisites or files were changed')
    report = compatibility.inspect(home, selected)
    packages = packages_for(selected); versions = compatibility.package_versions(packages)
    print(json.dumps(dict(platform=report, package_versions=versions, modules=selected), indent=2))
    if not args.apply:
        print('Plan only. Add --apply. Optional modules: '+', '.join(OPTIONAL))
        if args.undo: print('Would undo transaction:', args.undo)
        return 0
    if os.geteuid() == 0: raise ValueError('Run as the desktop user, not root')
    if args.undo and (args.remove or args.recover): raise ValueError('--undo cannot combine with --remove/--recover')
    if previous.get('status') == 'pending':
        if not args.recover: raise RuntimeError('Interrupted deployment; use --apply --recover with the same source before another action')
        if request['source'] != hashlib.sha256((ROOT/'SHA256SUMS').read_bytes()).hexdigest():
            raise ValueError('Recovery needs the same source revision; no packages or files were changed')
    if not (args.remove or args.undo):
        if report['issues']: raise ValueError('\n'.join(report['issues']))
        import source_release
        source_release.check(ROOT, source_release.source_files(ROOT))
        missing = [p for p,v in versions.items() if v is None]
        if missing:
            if args.no_packages: raise ValueError('Missing packages: '+', '.join(missing))
            print('Missing packages: '+', '.join(missing)+'. pacman will offer a full-system update; review its prompt.', flush=True)
            run(['sudo', 'pacman', '-Syu', '--needed', *packages])
            versions = compatibility.package_versions(packages)
            if any(v is None for v in versions.values()): raise RuntimeError('Required packages are still unavailable')
    state = home/'.local/state/doroshell'; lock = state/'deployment.lock'; safe(lock, home)
    state.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        binaries = {} if args.remove or args.undo else build_native(home, selected, versions)
        # Lock the existing optional-module writer locks too, retaining their inodes.
        with contextlib.ExitStack() as locks:
            for name in ('theme', 'wallpaper', 'clipboard'):
                if name in selected or args.undo:
                    path = state/(name+'.lock'); safe(path, home)
                    handle = locks.enter_context(path.open('a')); fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.undo: undo(home, args.undo); return 0
            deploy(home, selected, binaries, args.theme, args.remove, args.recover)
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit('DoroShell: '+str(error)+'\nNo session was restarted. Keep the private manifests/journal; do not delete them to bypass a conflict.')
