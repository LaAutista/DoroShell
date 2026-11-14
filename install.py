#!/usr/bin/env python3
"""Install only the menu module. Packages and panel settings are never changed."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import os
import tempfile
import re
import sys

SOURCE = Path(__file__).resolve().parent
PACKAGES = ['pyside6', 'python-gobject', 'python-xlib', 'systemd', 'lxqt-panel', 'xdg-user-dirs', 'lxqt-session', 'lxqt-globalkeys', 'lxqt-config', 'procps-ng']


class PlanError(ValueError):
    """An expected missing prerequisite or invalid user-supplied plan input."""


def validate_backup(entry, data_key='data'):
    """Validate recovery bytes/mode before any part of a transaction writes."""
    if not isinstance(entry, dict) or data_key not in entry or 'mode' not in entry:
        raise ValueError('Invalid backup record; preserve the manifest and recover it before retrying')
    data, mode = entry[data_key], entry['mode']
    if data is not None:
        if not isinstance(data, str) or type(mode) is not int or not 0 <= mode <= 0o777:
            raise ValueError('Invalid backup bytes or mode; preserve the recovery manifest')
        base64.b64decode(data, validate=True)
    elif mode is not None and (type(mode) is not int or not 0 <= mode <= 0o777):
        raise ValueError('Invalid backup mode; preserve the recovery manifest')


def validate_menu_record(record):
    if not isinstance(record, dict):
        raise ValueError('Invalid menu manifest; preserve it for recovery')
    for entry in record.values():
        validate_backup(entry, 'original')
        for field in ('installed_mode', 'pending_mode'):
            if field in entry and entry[field] is not None and (type(entry[field]) is not int or not 0 <= entry[field] <= 0o777):
                raise ValueError('Invalid menu recovery mode; preserve the recovery manifest')
        for field in ('installed', 'pending_from'):
            if field == 'pending_from' and entry.get(field) is None:
                continue
            value = entry.get(field)
            if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
                raise ValueError('Invalid menu recovery hash; preserve the recovery manifest')


def check_menu_mode(path, entry, installed_mode, rollback=False):
    if not path.exists():
        return
    current = (digest(path.read_bytes()), path.stat().st_mode & 0o777)
    allowed = {(entry['installed'], entry.get('installed_mode', installed_mode))}
    if 'pending_from' in entry:
        # Older interrupted manifests recorded hashes only. Existing payload modes
        # and the original mode are the only supported legacy recovery states.
        pending_modes = [entry['pending_mode']] if 'pending_mode' in entry else [installed_mode, entry['mode']]
        allowed.update((entry['pending_from'], mode) for mode in pending_modes)
    if rollback and entry['original'] is not None:
        allowed.add((digest(base64.b64decode(entry['original'], validate=True)), entry['mode']))
    if current not in allowed:
        raise RuntimeError(f'Locally modified file contents or mode; preserve it before retrying: {path}')


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
    body = line.sub(lambda _: key+'='+value,body) if line.search(body) else body.rstrip()+'\n'+key+'='+value+'\n'
    return text[:match.end()]+body+text[end:]


def start_tile(data):
    from PySide6.QtCore import Qt, QRect, QByteArray, QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage, QPainter, QLinearGradient, QPen

    art = QImage.fromData(data)
    if art.isNull():
        raise ValueError('Start image could not be decoded')
    art = art.scaled(192, 192, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)
    visible = QRect()
    for y in range(art.height()):
        for x in range(art.width()):
            if art.pixelColor(x, y).alpha() > 10:
                visible |= QRect(x, y, 1, 1)
    if not visible.isEmpty():
        art = art.copy(visible)
    tile = QImage(96, 96, QImage.Format.Format_ARGB32_Premultiplied)
    tile.fill(Qt.GlobalColor.transparent)
    brush = QLinearGradient(0, 0, 68, 96)
    for stop, color in [(0, '#fffaff'), (.43, '#ffe2f4'), (.49, '#efadd0'), (1, '#ce74a7')]:
        brush.setColorAt(stop, QColor(color))
    painter = QPainter(tile)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setBrush(brush)
    painter.setPen(QPen(QColor('#723255'), 3))
    painter.drawRoundedRect(2, 2, 92, 92, 12, 12)
    painter.setPen(QPen(QColor('#fff6fc'), 2))
    painter.drawRoundedRect(5, 5, 86, 86, 10, 10)
    size = art.size().scaled(78, 78, Qt.AspectRatioMode.KeepAspectRatio)
    painter.drawImage(QRect((96-size.width())//2, (96-size.height())//2,
                            size.width(), size.height()), art)
    painter.end()
    encoded = QByteArray()
    buf = QBuffer(encoded)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    if not tile.save(buf, 'PNG'):
        raise ValueError('Start tile encoding failed')
    return bytes(encoded)


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
    if custom_data is not None:
        icon_path = custom.with_name('framed-start-icon.png')
    desktop = '[Desktop Entry]\nType=Application\nName=DoroShell Start\nComment=Two-column application and personal folder menu\nExec="' + quoted + '"\nIcon=' + str(icon_path) + '\nTerminal=false\nCategories=Utility;\n'
    files = {app: (SOURCE.joinpath('menu/start_menu.py').read_bytes(), 0o644),
            home / '.local/share/lxqt-comfort/app_search.py': (SOURCE.joinpath('menu/app_search.py').read_bytes(), 0o644),
            home / '.local/share/lxqt-comfort/wallpaper_glass.py': (SOURCE.joinpath('menu/wallpaper_glass.py').read_bytes(), 0o644),
            home / '.local/share/lxqt-comfort/themes.py': (SOURCE.joinpath('themes.py').read_bytes(), 0o644),
            home / '.local/share/lxqt-comfort/folder_cascade.py': (SOURCE.joinpath('menu/folder_cascade.py').read_bytes(), 0o644),
            home / '.local/share/lxqt-comfort/portrait_crop.py': (SOURCE.joinpath('menu/portrait_crop.py').read_bytes(), 0o644),
            home / '.local/share/lxqt-comfort/start.svg': (SOURCE.joinpath('menu/start.svg').read_bytes(), 0o644),
            launcher: (wrapper.encode(), 0o755),
            home / '.local/share/applications/lxqt-comfort.desktop': (desktop.encode(), 0o644)}
    if custom_data is not None:
        files[custom] = (custom_data, 0o644)
        files[icon_path] = (start_tile(custom_data), 0o644)
    toolkit = home / '.local/share/doroshell/toolkit'
    for name in ['clipboard/__init__.py','clipboard/clipboard.py','clipboard/install.py','clipboard/clipboard.svg','wallpaper/control.py','wallpaper/install.py','settings.py','input_preferences.py','input_diagnostics.py','portable_settings.py','setup.py','themes.py','modules.py','cursor.py','install.py','integrate.py',
                 'panel/profile.py','panel/layout.py','runtime/snap.py','runtime/screenshot.py','runtime/menu_capture.py','runtime/dockbarx_drag.py','menu/start_menu.py','menu/app_search.py','menu/portrait_crop.py','menu/folder_cascade.py','menu/wallpaper_glass.py','menu/start.svg']:
        files[toolkit/name] = ((SOURCE/name).read_bytes(), 0o644)
    settings_launcher = home / '.local/bin/doroshell-settings'
    files[settings_launcher] = (('#!/usr/bin/python\nimport runpy\nrunpy.run_path('+repr(str(toolkit/'settings.py'))+', run_name="__main__")\n').encode(), 0o755)
    quoted_settings = str(settings_launcher).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
    files[home/'.local/share/applications/doroshell-settings.desktop'] = (
        ('[Desktop Entry]\nType=Application\nName=DoroShell Settings\nExec="'+quoted_settings+'"\nIcon=preferences-desktop\nTerminal=false\nCategories=Settings;DesktopSettings;\n').encode(), 0o644)
    return files


def atomic(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.doroshell-', dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


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
    validate_menu_record(record)
    for path, (data, mode) in files.items():
        key = str(path.relative_to(home))
        current = path.read_bytes() if path.exists() else None
        if key in record:
            check_menu_mode(path, record[key], mode)
        if current == data and (path.stat().st_mode & 0o777) == mode:
            print('Unchanged:', key)
            continue
        if key in record and (digest(current) if current is not None else None) not in (
                record[key]['installed'], record[key].get('pending_from', record[key]['installed'])):
            raise RuntimeError(f'Locally modified file; preserve or move it before updating: {path}')
        print('Write:', key)
    if not apply:
        print('Plan only. No package or file changes. Use --apply to install the menu.')
        return
    state.mkdir(parents=True, exist_ok=True)
    # Snapshot desktop settings for reference only. We never edit or automatically restore them.
    snapshot = state / 'desktop-before'
    safe(snapshot, home)
    snapshot.mkdir(exist_ok=True)
    for name in ['panel.conf', 'globalkeyshortcuts.conf']:
        original = home / '.config/lxqt' / name
        dest = snapshot / name
        safe(dest, home)
        if original.exists() and not dest.exists():
            safe(original, home)
            atomic(dest, original.read_bytes())
    for path, (data, mode) in files.items():
        key = str(path.relative_to(home))
        if key not in record:
            record[key] = {'original': base64.b64encode(path.read_bytes()).decode() if path.exists() else None,
                           'mode': path.stat().st_mode & 0o777 if path.exists() else None}
        current = path.read_bytes() if path.exists() else None
        if current != data or (path.exists() and path.stat().st_mode & 0o777 != mode):
            record[key]['pending_mode'] = path.stat().st_mode & 0o777 if path.exists() else None
            record[key]['pending_from'] = digest(current) if current is not None else None
        record[key]['installed'] = digest(data)
        record[key]['installed_mode'] = mode
    # Save rollback evidence before writing any managed files.
    atomic(manifest, (json.dumps(record, indent=2) + '\n').encode())
    for path, (data, mode) in files.items():
        if path.exists() and path.read_bytes() == data and path.stat().st_mode & 0o777 == mode:
            continue
        atomic(path, data, mode)
    if any('pending_from' in entry for entry in record.values()):
        for entry in record.values():
            entry.pop('pending_from', None)
            entry.pop('pending_mode', None)
        atomic(manifest, (json.dumps(record, indent=2) + '\n').encode())
    print('Installed. Run:', home / '.local/bin/lxqt-comfort-menu')


def rollback(home):
    from input_preferences import Preferences
    store = Preferences(home)
    if store.helper.exists() or store.path.exists() or store.startup.exists():
        with store.locked():
            store.require_inactive()
            return _rollback(home)
    return _rollback(home)


def _rollback(home):
    manifest = home / '.local/state/lxqt-comfort/menu-install.json'
    safe(manifest, home)
    if not manifest.exists():
        print('Nothing installed.')
        return
    record = json.loads(manifest.read_text())
    validate_menu_record(record)
    if (manifest.parent / 'menu-integration.json').exists():
        raise RuntimeError('Restore the Start button and shortcut integration before removing its launcher.')
    if (home/'.local/state/doroshell/native-panel.json').is_file():
        from PySide6.QtCore import QSettings
        cfg = QSettings(str(home/'.config/doroshell/panel.conf'), QSettings.Format.IniFormat)
        desktop = str(home/'.local/share/applications/lxqt-comfort.desktop')
        if any(cfg.value(key) == desktop for key in cfg.allKeys() if key.endswith('/desktop')):
            raise RuntimeError('Restore the native panel integration before removing its Start launcher.')
    payloads = targets(home)
    allowed = set(payloads) | {home/".local/share/lxqt-comfort/start-icon.png"}
    for name, entry in record.items():
        path = home / name
        safe(path, home)
        if path not in allowed:
            raise RuntimeError(f'Unexpected manifest target: {path}')
        check_menu_mode(path, entry, payloads.get(path, (None, 0o644))[1], rollback=True)
        current = path.read_bytes() if path.exists() else None
        before = base64.b64decode(entry['original'], validate=True) if entry['original'] is not None else None
        if current != before and (digest(current) if current is not None else None) not in (
                entry['installed'], entry.get('pending_from', entry['installed'])):
            raise RuntimeError(f'Refusing to overwrite an edited file during rollback: {path}')
    for name, entry in record.items():
        path = home / name
        if entry['original'] is None:
            path.unlink(missing_ok=True)
        else:
            atomic(path, base64.b64decode(entry['original']), entry['mode'])
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
