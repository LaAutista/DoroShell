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


PANEL = '.config/lxqt/panel.conf'
OPENBOX = '.config/openbox/rc.xml'


def system_dirs(environ=None):
    env = os.environ if environ is None else environ
    return [Path(d) for d in (env.get('XDG_CONFIG_DIRS') or '/etc/xdg').split(':') if d.startswith('/')]


def system_default(relative, environ=None):
    """First system copy of an XDG config file, as LXQt and Openbox resolve it."""
    return next((d/relative for d in system_dirs(environ) if (d/relative).is_file()), None)


def panel_groups(text):
    return re.findall(r'(?m)^\[(panel[1-9][0-9]*)\]$', text)


def single_panel1(text):
    # LXQt omits `panels=` for its default single-panel layout, so a missing key means panel1.
    panels = re.search(r'(?m)^\s*panels\s*=(.*)$', text)
    return not (panels and panels[1].strip() != 'panel1') and panel_groups(text) == ['panel1']


def merge_ini(system, user):
    """System INI with the user's keys laid over it, the way QSettings falls back per key."""
    def parse(text):
        sections = {}; current = sections.setdefault('General', {})
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('[') and line.endswith(']'): current = sections.setdefault(line[1:-1], {})
            elif '=' in line and not line.startswith((';', '#')):
                key, value = line.split('=', 1); current[key.strip()] = value.strip()
        return sections
    merged = parse(system)
    for section, keys in parse(user).items(): merged.setdefault(section, {}).update(keys)
    return ''.join('['+section+']\n'+''.join(k+'='+v+'\n' for k, v in keys.items())+'\n' for section, keys in merged.items() if keys)


def effective_defaults(home, selected, environ=None):
    """Per-user files this install would write down from system defaults: {relative path: bytes}.

    A fresh LXQt/Openbox login runs from /etc/xdg and leaves the user's panel.conf with
    plugin overrides only and no rc.xml. Only the unambiguous case is resolved: the user
    defines no panel at all and the system layout is a single panel1."""
    result = {}
    if 'native-panel' in selected:
        path = home/PANEL
        user = path.read_text() if path.is_file() else ''
        system = system_default('lxqt/panel.conf', environ)
        if system is not None and not panel_groups(user) and not re.search(r'(?m)^\s*panels\s*=', user):
            merged = merge_ini(system.read_text(), user)
            if single_panel1(merged): result[PANEL] = merged.encode()
    if any(m in selected for m in ('snapping', 'theme', 'single-desktop')) and not (home/OPENBOX).exists():
        system = system_default('openbox/rc.xml', environ)
        if system is not None: result[OPENBOX] = system.read_bytes()
    return result


def inspect(home, selected, environ=None, release=None, config_root=None):
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
    if config_root is not None:
        from config_root import validate, SUPPORTED
        config_root=validate(home,config_root)
        if not selected or not set(selected).issubset(SUPPORTED):raise ValueError('Custom configuration roots support only snapping and single-desktop')
    for variable, default in [('XDG_CONFIG_HOME', '.config'), ('XDG_DATA_HOME', '.local/share'), ('XDG_STATE_HOME', '.local/state')]:
        expected=config_root if variable=='XDG_CONFIG_HOME' and config_root is not None else home/default
        if env.get(variable) and Path(env[variable]) != expected:
            issues.append(variable+' must use the default home layout for these existing installers.')
    defaults = effective_defaults(home, selected, env) if config_root is None else {}
    if 'native-panel' in selected and PANEL not in defaults:
        path = home/PANEL
        text = path.read_text() if path.is_file() else ''
        if not panel_groups(text) and not re.search(r'(?m)^\s*panels\s*=', text):
            issues.append('Native taskbar: ~/'+PANEL+' defines no panel and no system default with a single panel1 was found ('
                          +', '.join(str(d/'lxqt/panel.conf') for d in system_dirs(env))+'). Open LXQt panel settings once, change and '
                          'apply any setting so LXQt writes its layout, then run this again; or pass --panel panelN for an existing panel.')
        elif not single_panel1(text):
            issues.append('Native taskbar needs a single panel1 layout or explicit --panel panelN; custom layouts are preserved.')
    if any(m in selected for m in ('snapping', 'theme')) and OPENBOX not in defaults:
        if not ((config_root or home/'.config')/'openbox/rc.xml').is_file():
            issues.append('Snapping/themes: '+(str(config_root/'openbox/rc.xml') if config_root else '~/'+OPENBOX)+' is missing and no system default was found ('
                          +', '.join(str(d/'openbox/rc.xml') for d in system_dirs(env))+'). Install openbox, or copy your Openbox default there '
                          '(for example: install -Dm644 /etc/xdg/openbox/rc.xml ~/.config/openbox/rc.xml); other window managers are preserved.')
    return dict(distribution=distro, arch_based=arch, desktop=desktop, session=session,
                issues=issues, effective_defaults=sorted(defaults), adapter='LXQt INI / Openbox XML / native upstream 2.4 patches')
