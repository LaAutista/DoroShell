"""Read-only platform probes for the supported LXQt/X11 installation adapters."""
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess


def os_release(path=Path('/etc/os-release')):
    result = {}
    for line in path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            words = shlex.split(value)
            result[key] = ' '.join(words)
    return result


def package_versions(packages):
    result = {}
    if shutil.which('pacman'):
        for name in packages:
            query = subprocess.run(['pacman', '-Q', name], capture_output=True, text=True)
            result[name] = query.stdout.strip().split(' ', 1)[-1] if query.returncode == 0 else None
    else:
        result = dict.fromkeys(packages)
    return result


def inspect(home, selected, environ=None, release=None):
    env = os.environ if environ is None else environ
    release = os_release() if release is None else release
    distro = release.get('ID', 'unknown')
    arch = distro == 'arch' or 'arch' in release.get('ID_LIKE', '').split()
    desktop = env.get('XDG_CURRENT_DESKTOP', '')
    session = env.get('XDG_SESSION_TYPE') or ('wayland' if env.get('WAYLAND_DISPLAY') else 'x11' if env.get('DISPLAY') else 'unknown')
    issues = []
    if not arch: issues.append('This installer needs Arch or an Arch derivative with pacman.')
    if not shutil.which('pacman'): issues.append('pacman is unavailable; no alternative package manager is guessed.')
    if 'lxqt' not in desktop.casefold().split(':'): issues.append('Run from your existing LXQt session.')
    if session != 'x11': issues.append('This release supports X11 only; Wayland is not implemented.')
    for variable, default in [('XDG_CONFIG_HOME', '.config'), ('XDG_DATA_HOME', '.local/share'), ('XDG_STATE_HOME', '.local/state')]:
        if env.get(variable) and Path(env[variable]) != home/default:
            issues.append(variable+' must use the default home layout for these existing installers.')
    if 'native-panel' in selected:
        path = home/'.config/lxqt/panel.conf'
        text = path.read_text() if path.is_file() else ''
        panels = re.search(r'(?m)^\s*panels\s*=(.*)$', text)
        # LXQt omits `panels=` for its default single-panel layout, so a missing key means panel1.
        if (panels and panels[1].strip() != 'panel1') or not re.search(r'(?m)^\[panel1\]$', text):
            issues.append('Native taskbar needs an initialized single panel1 layout; custom layouts are preserved.')
    if any(m in selected for m in ('snapping', 'theme')):
        if not (home/'.config/openbox/rc.xml').is_file():
            issues.append('Snapping/themes need an initialized Openbox rc.xml; other window managers are preserved.')
    return dict(distribution=distro, arch_based=arch, desktop=desktop, session=session,
                issues=issues, adapter='LXQt INI / Openbox XML / native upstream 2.4 patches')
