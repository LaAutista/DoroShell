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


def snapshot(work):
    """Keep the sources that made this build beside it, so it can rebuild itself."""
    shutil.copytree(ROOT, work/'recipe', symlinks=True,
                    ignore=shutil.ignore_patterns('assets', 'tests', '.git', '__pycache__', 'recipe', 'SOURCE-*', 'SHA256SUMS'))


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
        run([sys.executable, ROOT/'modules.py', 'wallpaper', '--home', home, '--wallpaper-binary', binary, '--apply'])
    else:
        run([sys.executable, ROOT/'panel/build.py', '--work', work, '--jobs', jobs])
        binary = work/'runtime/bin/lxqt-panel'
        sys.path.insert(0, str(ROOT))
        from panel.profile import upgrade
        upgrade(home, binary)
    if missing_libraries(binary):
        raise RuntimeError('The new build still has missing libraries')
    return binary


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
            build_and_stage(kind, version, work, current, home, log)
    except Exception as exc:
        status[kind] = dict(version=version, result='failed', time=time.time(), work=str(work))
        status_path.write_text(json.dumps(status, indent=2))
        notify('DoroShell '+label+' rebuild failed',
               str(exc)[:200]+'. Still using the stock '+label+'. Details: '+str(log_path), urgent=True)
        return 1
    status[kind] = dict(version=version, result='ready', time=time.time(), work=str(work))
    status_path.write_text(json.dumps(status, indent=2))
    notify('DoroShell '+label+' is ready', 'Rebuilt for LXQt '+version+'. It will be used from your next login.')
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
