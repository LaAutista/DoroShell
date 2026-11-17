#!/usr/bin/env python3
"""Rebuild a native DoroShell desktop or panel after a system update breaks it.

Each native build keeps a copy of the DoroShell sources that made it (``recipe/``).
Its login launcher runs ``login``: when a library the build needs is gone, that
starts ``rebuild`` in the background and the launcher falls back to the stock
program for this session. The rebuild follows the system's current LXQt version,
stages the new build for the next login and reports the result as a notification.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
LABEL = {'desktop': 'desktop', 'panel': 'taskbar'}
RETRY_SECONDS = 24*3600


RECIPE_FILES = 'RECIPE-FILES.json'


def recipe_inventory():
    """Tracked build sources only: git's index, a recipe's own list, or a release manifest."""
    if (ROOT/'.git').exists():
        names = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True, capture_output=True).stdout.decode().strip('\0').split('\0')
    elif (ROOT/RECIPE_FILES).is_file():
        names = json.loads((ROOT/RECIPE_FILES).read_text())
    else:
        names = [entry['path'] for entry in json.loads((ROOT/'SOURCE-MANIFEST.json').read_text())['source_payloads']]
    skip = ('assets/', 'tests/')
    return sorted(n for n in names if n and not n.startswith(skip) and n not in ('SOURCE-MANIFEST.json', 'SOURCE-SCAN.json', 'SHA256SUMS', RECIPE_FILES))


def snapshot(work):
    """Keep the sources that made this build beside it, so it can rebuild itself."""
    recipe = (work/'recipe').resolve()
    names = recipe_inventory()
    for name in names:
        source = ROOT/name
        if source.is_symlink() or not source.is_file():
            raise RuntimeError('Recipe source must be a regular file: '+name)
        target = recipe/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (recipe/RECIPE_FILES).write_text(json.dumps(names, indent=1))


def missing_libraries(path):
    try:
        out = subprocess.run(['ldd', str(path)], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return []  # Can't tell: let the launcher try the build as before.
    return sorted({line.split()[0] for line in out.splitlines() if line.rstrip().endswith('not found')})


def system_version(kind):
    """Version the rebuild targets: installed PCManFM for the desktop, liblxqt for the panel."""
    if kind == 'desktop':
        out = subprocess.run(['pcmanfm-qt', '--version'], capture_output=True, text=True, timeout=20).stdout
        match = re.search(r'^pcmanfm-qt (\d+\.\d+\.\d+)$', out, re.M)
    else:
        out = subprocess.run(['pkg-config', '--modversion', 'lxqt'], capture_output=True, text=True, timeout=20).stdout
        match = re.fullmatch(r'(\d+\.\d+\.\d+)\s*', out)
    if not match:
        raise RuntimeError('Could not read the installed '+('PCManFM' if kind == 'desktop' else 'liblxqt')+' version')
    return match[1]


def notify(summary, body, urgent=False):
    try:
        subprocess.run(['notify-send', '--app-name=DoroShell', '--urgency='+('critical' if urgent else 'normal'),
                        '--icon='+('dialog-warning' if urgent else 'system-software-update'), summary, body],
                       timeout=20, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        pass


def login(kind, current):
    """Exit 1 (and start a background rebuild) only when the build's libraries are missing."""
    paths = [current]
    if kind == 'desktop':
        paths.append(current.with_name('doroshell-video-worker'))
    missing = sorted({name for path in paths if path.exists() for name in missing_libraries(path)})
    if not missing:
        return 0
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'rebuild', kind, '--current', str(current)],
                     start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 1


def still_selected(kind, current, home):
    """True while the owner's staged launcher still runs the broken build we replace."""
    wrapper = home/'.local/bin'/('doroshell-wallpaper-desktop' if kind == 'desktop' else 'doroshell-native-panel')
    try:
        if wrapper.is_symlink() or repr(str(current)) not in wrapper.read_text():
            return False
        if kind == 'desktop':
            return str(wrapper) in (home/'.config/autostart/lxqt-desktop.desktop').read_text()
        return (home/'.local/state/doroshell/native-panel.json').is_file()
    except OSError:
        return False


def stage(kind, binary, current, home):
    """Stage the new build unless the owner rolled back or chose another build meanwhile."""
    sys.path.insert(0, str(ROOT))
    if kind == 'panel':
        if not still_selected(kind, current, home):
            return False
        from panel.profile import upgrade
        upgrade(home, binary)  # Refuses a launcher edited since its manifest record.
        return True
    # Same lock and call as `modules.py wallpaper --apply`, held across the check.
    from modules import run, safe
    from config_root import choose
    lock = home/'.local/state/doroshell/wallpaper.lock'
    safe(lock, home)
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        if not still_selected(kind, current, home):
            return False
        run(home, 'wallpaper', True, False, wallpaper_binary=binary, config_root=choose(home, ['wallpaper'], None))
    return True


def build_and_stage(kind, version, work, current, home, log):
    def run(args):
        log.write('$ '+' '.join(map(str, args))+'\n'); log.flush()
        subprocess.run(['nice', '-n', '10', *map(str, args)], check=True, stdout=log, stderr=subprocess.STDOUT,
                       stdin=subprocess.DEVNULL, cwd=ROOT)
    jobs = str(os.cpu_count() or 4)
    if kind == 'desktop':
        record = json.loads(current.with_name('doroshell-wallpaper-build.json').read_text())
        run([sys.executable, ROOT/'wallpaper/build.py', '--work', work, '--tag', version, '--jobs', jobs]
            + (['--display-controls'] if record.get('format') == 3 else []))
        binary = work/'build/pcmanfm/pcmanfm-qt'
        required = [binary, binary.with_name('doroshell-video-worker')]
    else:
        run([sys.executable, ROOT/'panel/build.py', '--work', work, '--jobs', jobs])
        binary = work/'runtime/bin/lxqt-panel'
        required = [binary]
    missing = sorted({name for path in required for name in missing_libraries(path)})
    if missing:
        raise RuntimeError('The new build still has missing libraries: '+', '.join(missing))
    return binary, stage(kind, binary, current, home)


def rebuild(kind, current, home, force=False):
    state = home/'.local/state/doroshell'
    state.mkdir(parents=True, exist_ok=True)
    with (state/('native-rebuild-'+kind+'.lock')).open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0  # Another login already started this rebuild.
        return locked_rebuild(kind, current, home, state, force)


def locked_rebuild(kind, current, home, state, force):
    label, log_path, status_path = LABEL[kind], state/('native-rebuild-'+kind+'.log'), state/'native-rebuild.json'
    try:
        status = json.loads(status_path.read_text())
        status = status if isinstance(status, dict) else {}
    except (OSError, ValueError):
        status = {}
    try:
        version = system_version(kind)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        notify('DoroShell '+label+' needs attention', str(exc)+'. Using the stock '+label+'.', urgent=True)
        return 1
    last = status.get(kind) if isinstance(status.get(kind), dict) else {}
    if (not force and last.get('version') == version and last.get('result') == 'failed'
            and time.time() - last.get('time', 0) < RETRY_SECONDS):
        notify('DoroShell '+label+' still needs attention',
               'Rebuilding for LXQt '+version+' failed earlier. Using the stock '+label+'. Details: '+str(log_path), urgent=True)
        return 1
    notify('Rebuilding the DoroShell '+label,
           'A system update changed LXQt ('+version+'). Using the stock '+label+' for now; you will be told when the rebuild is ready.')
    work = home/'.local/share/doroshell/builds'/(kind+'-'+version+'-'+time.strftime('%Y%m%d-%H%M%S'))
    try:
        with log_path.open('w') as log:
            log.write('DoroShell '+label+' rebuild for '+version+' from '+str(ROOT)+'\n')
            _, staged = build_and_stage(kind, version, work, current, home, log)
    except Exception as exc:
        status[kind] = dict(version=version, result='failed', time=time.time(), work=str(work))
        status_path.write_text(json.dumps(status, indent=2))
        notify('DoroShell '+label+' rebuild failed',
               str(exc)[:200]+'. Still using the stock '+label+'. Details: '+str(log_path), urgent=True)
        return 1
    status[kind] = dict(version=version, result='ready' if staged else 'built-not-staged', time=time.time(), work=str(work))
    status_path.write_text(json.dumps(status, indent=2))
    if staged:
        notify('DoroShell '+label+' is ready', 'Rebuilt for LXQt '+version+'. It will be used from your next login.')
    else:
        notify('DoroShell '+label+' rebuilt but not switched',
               'Your '+label+' setting changed while it was building, so it was left as you set it. The new build is in '+str(work))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('login', 'rebuild'))
    parser.add_argument('kind', choices=tuple(LABEL))
    parser.add_argument('--current', type=Path, required=True, help='The staged build executable')
    parser.add_argument('--force', action='store_true', help='Rebuild even if this version failed recently')
    args = parser.parse_args(argv)
    if args.action == 'login':
        return login(args.kind, args.current)
    return rebuild(args.kind, args.current, Path.home(), args.force)


if __name__ == '__main__':
    sys.exit(main())
