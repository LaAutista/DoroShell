#!/usr/bin/env python3
"""Reversible panel and Alt+F1 integration. Run after install.py menu --apply."""
import argparse
import base64
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from PySide6.QtCore import QSettings
from install import safe


def desired(home):
    return {
        'panel.conf': {
            'comfortstart/type': 'quicklaunch',
            'comfortstart/apps/1/desktop': str(home / '.local/share/applications/lxqt-comfort.desktop'),
            'comfortstart/apps/size': 1,
        },
        'globalkeyshortcuts.conf': {
            'Alt+F1.1/path': None,
            'Alt+F1.1/Exec': str(home / '.local/bin/lxqt-comfort-menu'),
            'Alt+F1.1/Comment': 'DoroShell Start',
            'Alt+F1.1/Enabled': True,
        },
    }


def run(home, apply=False, rollback=False):
    state = home / '.local/state/lxqt-comfort/menu-integration.json'
    safe(state, home)
    config = home / '.config/lxqt'
    changes = desired(home)
    settings = {}
    for filename in changes:
        path = config / filename
        safe(path, home)
        if not path.exists():
            raise RuntimeError(f'Expected LXQt config not found: {path}; log into LXQt first.')
        settings[filename] = QSettings(str(path), QSettings.Format.IniFormat)
    saved = json.loads(state.read_text()) if state.exists() else None
    if rollback:
        if not saved:
            print('No menu integration to roll back.')
            return
        changes = {name: {key: entry['before'] for key, entry in data['keys'].items()} for name, data in saved.items()}
    else:
        shortcuts = settings['globalkeyshortcuts.conf']
        groups = [g for g in shortcuts.childGroups() if g.startswith('Alt+F1.')]
        if groups != ['Alt+F1.1']:
            raise RuntimeError('Nonstandard Alt+F1 action; inspect shortcuts before integrating.')
        if not saved and shortcuts.value('Alt+F1.1/path') != '/panel/fancymenu/show_hide':
            raise RuntimeError('Alt+F1 has a custom action; refusing to replace it.')
        panel = settings['panel.conf']
        plugins = panel.value('panel1/plugins')
        if isinstance(plugins, str):
            plugins = [part.strip() for part in plugins.split(',')]
        if not plugins or not any(x in plugins for x in ('fancymenu', 'comfortstart')):
            raise RuntimeError('Expected Fancy Menu on panel1; inspect this panel before integrating.')
        changes['panel.conf']['panel1/plugins'] = ['comfortstart' if p == 'fancymenu' else p for p in plugins]
    record = saved or {}
    for filename, edits in changes.items():
        cfg = settings[filename]
        if filename not in record:
            record[filename] = {'backup': base64.b64encode((config / filename).read_bytes()).decode(), 'keys': {}}
        for key, value in edits.items():
            current = cfg.value(key)
            old = record[filename]['keys'].get(key)
            # QSettings reloads scalar values as strings; compare normalized values.
            norm = lambda v: str(v).lower() if not isinstance(v, list) else v
            if old and norm(current) != norm(old['after']) and (rollback or norm(current) != norm(old['before'])):
                raise RuntimeError(f'Personal edit detected: {filename}/{key}; no changes applied.')
            if not old:
                record[filename]['keys'][key] = {'before': current, 'after': value}
            print(f'{filename}: {key}: {current!r} -> {value!r}')
    if not apply and not rollback:
        print('Dry run. Use --apply --live in a running LXQt session.')
        return
    if not rollback:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(record, indent=2) + '\n')
        state.chmod(0o600)
    for filename, edits in changes.items():
        cfg = settings[filename]
        for key, value in edits.items():
            if value is None:
                cfg.remove(key)
            else:
                cfg.setValue(key, value)
        cfg.sync()
        if cfg.status() != QSettings.Status.NoError:
            raise RuntimeError(f'Could not sync {filename}; backup retained at {state}')
    if rollback:
        state.unlink()
    print('Saved integration.' if not rollback else 'Restored menu integration keys; unrelated settings retained.')


def live_run(home, rollback=False, operation=None, components=None):
    """Stop config writers before editing; restart only components that were running."""
    if home.resolve() != Path.home().resolve():
        raise RuntimeError('--live is only valid for the current desktop user')
    stopped = []
    try:
        for name in (components if components is not None else ['lxqt-panel', 'lxqt-globalkeysd']):
            pattern = '^/usr/bin/' + name + '$'
            result = subprocess.run(['pgrep', '-u', str(os.getuid()), '-f', pattern], capture_output=True, text=True)
            if result.returncode not in (0, 1):
                raise RuntimeError('Could not inspect running ' + name)
            if result.returncode == 1:
                continue
            stopped.append(name)
            pids = [int(pid) for pid in result.stdout.split()]
            for pid in pids:
                os.kill(pid, signal.SIGTERM)
            for _ in range(50):
                if subprocess.run(['pgrep', '-u', str(os.getuid()), '-f', pattern], stdout=subprocess.DEVNULL).returncode == 1:
                    break
                time.sleep(.1)
            else:
                raise RuntimeError(name + ' did not stop; configuration not changed')
        if operation is None:
            run(home, apply=not rollback, rollback=rollback)
        else:
            operation()
    finally:
        for name in stopped:
            pattern = '^/usr/bin/' + name + '$'
            if subprocess.run(['pgrep', '-u', str(os.getuid()), '-f', pattern], stdout=subprocess.DEVNULL).returncode == 1:
                subprocess.Popen(['/usr/bin/' + name], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--apply', action='store_true')
    actions.add_argument('--rollback', action='store_true')
    parser.add_argument('--live', action='store_true', help='Refresh running LXQt panel/shortcuts safely around the change')
    parser.add_argument('--home', type=Path, default=Path.home())
    args = parser.parse_args()
    if args.live:
        if not (args.apply or args.rollback):
            parser.error('--live requires --apply or --rollback')
        live_run(args.home, args.rollback)
    else:
        if (args.apply or args.rollback) and args.home.resolve() == Path.home().resolve():
            active = subprocess.run(['pgrep', '-u', str(os.getuid()), '-f', '^/usr/bin/(lxqt-panel|lxqt-globalkeysd)$'], stdout=subprocess.DEVNULL)
            if active.returncode == 0:
                parser.error('LXQt components are running. Use --live to prevent them overwriting the change.')
        run(args.home, args.apply, args.rollback)
