#!/usr/bin/env python3
"""Install only the menu module. Packages and panel settings are never changed."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import os
import shutil
import re
import sys

SOURCE = Path(__file__).resolve().parent
PACKAGES = ['pyside6', 'python-gobject', 'lxqt-panel', 'xdg-user-dirs', 'lxqt-session', 'lxqt-globalkeys', 'lxqt-config', 'procps-ng']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def set_ini(text, section, key, value):
    pattern = re.compile(r'(?m)^\['+re.escape(section)+r'\]\s*\n')
    match = pattern.search(text)
    if not match:
        return text.rstrip()+'\n\n['+section+']\n'+key+'='+value+'\n'
    end_match = re.search(r'(?m)^\[', text[match.end():])
    end = match.end()+end_match.start() if end_match else len(text)
    body = text[match.end():end]
    line = re.compile(r'(?m)^'+re.escape(key)+r'\s*=.*$')
    body = line.sub(key+'='+value,body) if line.search(body) else body.rstrip()+'\n'+key+'='+value+'\n'
    return text[:match.end()]+body+text[end:]


def targets(home, icon=None):
    app = home / '.local/share/lxqt-comfort/start_menu.py'
    launcher = home / '.local/bin/lxqt-comfort-menu'
    wrapper = '#!/usr/bin/python\nimport runpy\nrunpy.run_path(' + repr(str(app)) + ', run_name="__main__")\n'
    # Desktop Entry Exec quoting, not shell quoting.
    quoted = str(launcher).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    icon_path = home / '.local/share/lxqt-comfort/start.svg'
    custom = home / '.local/share/lxqt-comfort/start-icon.png'
    custom_data = None
    if icon is not None:
        from PySide6.QtGui import QImage
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        image = QImage(str(icon))
        if image.isNull(): raise ValueError('Start image could not be decoded')
        data = QByteArray(); buffer = QBuffer(data); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, 'PNG'): raise ValueError('Start image conversion failed')
        custom_data = bytes(data); icon_path = custom
    elif custom.exists():
        custom_data = custom.read_bytes(); icon_path = custom
    else:
        # Retain an existing personal icon on upgrades without an explicit replacement.
        old_entry = home / '.local/share/applications/lxqt-comfort.desktop'
        if old_entry.exists():
            for line in old_entry.read_text().splitlines():
                if line.startswith('Icon=') and Path(line[5:]).is_absolute() and Path(line[5:]).is_file():
                    icon_path = Path(line[5:])
    desktop = '[Desktop Entry]\nType=Application\nName=DoroShell Start\nComment=Two-column application and personal folder menu\nExec="' + quoted + '"\nIcon=' + str(icon_path) + '\nTerminal=false\nCategories=Utility;\n'
    files = {app: (SOURCE.joinpath('menu/start_menu.py').read_bytes(), 0o644),
            home / '.local/share/lxqt-comfort/start.svg': (SOURCE.joinpath('menu/start.svg').read_bytes(), 0o644),
            launcher: (wrapper.encode(), 0o755),
            home / '.local/share/applications/lxqt-comfort.desktop': (desktop.encode(), 0o644)}
    if custom_data is not None: files[custom] = (custom_data, 0o644)
    toolkit = home / '.local/share/doroshell/toolkit'
    for name in ['settings.py','setup.py','modules.py','cursor.py','install.py','integrate.py',
                 'runtime/snap.py','runtime/screenshot.py','menu/start_menu.py','menu/start.svg']:
        files[toolkit/name] = ((SOURCE/name).read_bytes(), 0o644)
    settings_launcher = home / '.local/bin/doroshell-settings'
    files[settings_launcher] = (('#!/usr/bin/python\nimport runpy\nrunpy.run_path('+repr(str(toolkit/'settings.py'))+', run_name="__main__")\n').encode(), 0o755)
    quoted_settings = str(settings_launcher).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
    files[home/'.local/share/applications/doroshell-settings.desktop'] = (
        ('[Desktop Entry]\nType=Application\nName=DoroShell Settings\nExec="'+quoted_settings+'"\nIcon=preferences-desktop\nTerminal=false\nCategories=Settings;DesktopSettings;\n').encode(), 0o644)
    return files


def safe(path, home):
    if path.is_symlink() or not path.resolve().is_relative_to(home.resolve()):
        raise RuntimeError(f'Refusing symlink or path outside installation home: {path}')


def install(home, apply=False, icon=None):
    files = targets(home, icon)
    state = home / '.local/state/lxqt-comfort'
    manifest = state / 'menu-install.json'
    for path in [*files, manifest]:
        safe(path, home)
    record = json.loads(manifest.read_text()) if manifest.exists() else {}
    for path, (data, mode) in files.items():
        key = str(path.relative_to(home))
        current = path.read_bytes() if path.exists() else None
        if current == data and (path.stat().st_mode & 0o777) == mode:
            print('Unchanged:', key)
            continue
        if key in record and current is not None and digest(current) != record[key]['installed']:
            raise RuntimeError(f'Locally modified file; preserve or move it before updating: {path}')
        print('Write:', key)
    if not apply:
        print('Plan only. No package or file changes. Use --apply to install the menu.')
        return
    state.mkdir(parents=True, exist_ok=True)
    # Snapshot desktop settings for reference only. We never edit or automatically restore them.
    snapshot = state / 'desktop-before'
    snapshot.mkdir(exist_ok=True)
    for name in ['panel.conf', 'globalkeyshortcuts.conf']:
        original = home / '.config/lxqt' / name
        dest = snapshot / name
        if original.exists() and not dest.exists():
            shutil.copy2(original, dest)
    for path, (data, mode) in files.items():
        key = str(path.relative_to(home))
        if key not in record:
            record[key] = {'original': base64.b64encode(path.read_bytes()).decode() if path.exists() else None,
                           'mode': path.stat().st_mode & 0o777 if path.exists() else None}
        record[key]['installed'] = digest(data)
    # Save rollback evidence before writing any managed files.
    manifest.write_text(json.dumps(record, indent=2) + '\n')
    manifest.chmod(0o600)
    for path, (data, mode) in files.items():
        if path.exists() and path.read_bytes() == data and path.stat().st_mode & 0o777 == mode:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.comfort-tmp')
        safe(temporary, home)
        temporary.write_bytes(data)
        temporary.chmod(mode)
        temporary.replace(path)
    print('Installed. Run:', home / '.local/bin/lxqt-comfort-menu')


def rollback(home):
    manifest = home / '.local/state/lxqt-comfort/menu-install.json'
    safe(manifest, home)
    if not manifest.exists():
        print('Nothing installed.')
        return
    record = json.loads(manifest.read_text())
    allowed = set(targets(home)) | {home/".local/share/lxqt-comfort/start-icon.png"}
    for name, entry in record.items():
        path = home / name
        safe(path, home)
        if path not in allowed:
            raise RuntimeError(f'Unexpected manifest target: {path}')
        if path.exists() and digest(path.read_bytes()) != entry['installed']:
            raise RuntimeError(f'Refusing to overwrite an edited file during rollback: {path}')
    for name, entry in record.items():
        path = home / name
        if entry['original'] is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(entry['original']))
            path.chmod(entry['mode'])
    manifest.unlink()
    print('Menu files rolled back. Favorites and desktop backup retained; panel was never changed.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('module', choices=['menu'])
    parser.add_argument('--icon', type=Path, help='Personal Start image (kept outside the repository)')
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--apply', action='store_true')
    actions.add_argument('--rollback', action='store_true')
    parser.add_argument('--home', type=Path, default=Path.home(), help='Alternate installation home for staging/tests')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Run as your desktop user, not root.')
    print('Menu runtime packages:', ', '.join(PACKAGES))
    print('No packages are installed or removed by this script.')
    if args.rollback:
        rollback(args.home.absolute())
    else:
        if args.apply:
            try:
                import PySide6
                import gi
                gi.require_version('Gio', '2.0')
            except (ImportError, ValueError) as error:
                parser.exit(1, f'{error}\nInstall missing dependencies using your normal CachyOS full-update workflow.\nRequired packages: {", ".join(PACKAGES)}\n')
        install(args.home.absolute(), args.apply, args.icon)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        sys.exit(str(error))
