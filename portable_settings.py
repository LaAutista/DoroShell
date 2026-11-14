"""Path-free Start preferences with explicit previews and exact local rollback."""
import base64
import copy
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile

LIMIT = 128 * 1024
ACTIONS = ('shutdown', 'reboot', 'logout', 'suspend', 'hibernate', 'lockscreen')
FOLDERS = [('Home','HomeLocation','user-home'), ('Documents','DocumentsLocation','folder-documents'),
           ('Downloads','DownloadLocation','folder-download'), ('Pictures','PicturesLocation','folder-pictures'),
           ('Music','MusicLocation','folder-music'), ('Videos','MoviesLocation','folder-videos')]
FILES = ('session-button.json', 'recent.json', 'folders.json')
NOTICE = ('Only portable Start preferences are included. Version 2 replaces folder separators as well as standard-link order/visibility. Legacy version 1 imports leave separators unchanged. Pins, history entries/timestamps, custom folder names/paths, '
          'portrait/crop, wallpapers, clipboard, credentials, panel and machine settings are excluded and left unchanged. '
          'Import does not launch apps or perform session/power actions. Reopen Start to apply history expiry; untimed entries expire when age limiting is enabled.')


def decode(data, limit=LIMIT):
    if len(data) > limit: raise ValueError('Settings file is too large.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate settings key.')
            result[key] = value
        return result
    try: return json.loads(data, object_pairs_hook=pairs)
    except (RecursionError, UnicodeError) as error: raise ValueError('Invalid settings file.') from error


def encode(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode()


def validate(value):
    if not isinstance(value, dict) or set(value) != {'format', 'version', 'preferences'} or value['format'] != 'DoroShell portable Start settings' or type(value['version']) is not int or value['version'] not in (1, 2):
        raise ValueError('Unsupported portable settings format.')
    prefs = value['preferences']
    if not isinstance(prefs, dict) or set(prefs) != {'primary', 'recent', 'folders'}: raise ValueError('Invalid preferences.')
    if prefs['primary'] not in ACTIONS: raise ValueError('Invalid primary button.')
    recent = prefs['recent']
    if not isinstance(recent, dict) or set(recent) not in ({'enabled', 'limit'}, {'enabled', 'limit', 'retention_days'}) or type(recent['enabled']) is not bool or type(recent['limit']) is not int or not 1 <= recent['limit'] <= 50:
        raise ValueError('Invalid recent-program preferences.')
    if type(recent.get('retention_days', 0)) is not int or not 0 <= recent.get('retention_days', 0) <= 365:
        raise ValueError('Invalid recent-program retention period.')
    folders = prefs['folders']
    if not isinstance(folders, list) or len(folders) > 100 + len(FOLDERS) or (value['version'] == 1 and len(folders) != len(FOLDERS)): raise ValueError('Invalid standard folders.')
    seen = set()
    for item in folders:
        if value['version'] == 2 and item == {'type': 'separator'}:
            continue
        if not isinstance(item, dict) or set(item) != {'standard', 'visible'} or not isinstance(item['standard'], str) or item['standard'] not in {x[1] for x in FOLDERS} or item['standard'] in seen or type(item['visible']) is not bool:
            raise ValueError('Invalid standard folders.')
        seen.add(item['standard'])
    if seen != {x[1] for x in FOLDERS}: raise ValueError('Missing standard folders.')
    return value


class Store:
    def __init__(self, home, config=None):
        self.home = Path(home).absolute()
        self.config = Path(config or self.home/'.config').absolute()
        self.base = self.config/'lxqt-comfort'
        self.undo = self.base/'portable-settings-undo.json'

    def safe(self, path):
        # Reject linked ancestors too; no import may redirect writes elsewhere.
        for part in [path, *path.parents]:
            if part.is_symlink(): raise ValueError('Linked settings paths are not supported.')

    def read(self, path, limit=LIMIT):
        self.safe(path)
        try:
            with path.open('rb') as stream: data = stream.read(limit + 1)
        except FileNotFoundError: return None
        if len(data) > limit: raise ValueError('Local settings file is too large.')
        return data

    def snapshot(self):
        raw = {name: self.read(self.base/name) for name in FILES}
        values = {name: decode(data) if data is not None else {} for name, data in raw.items()}
        if any(not isinstance(value, dict) for value in values.values()): raise ValueError('Invalid local preferences; not overwriting.')
        from menu.start_menu import validate_links, validate_recent
        from menu.portrait_crop import validate_crop
        for name, value in values.items():
            if raw[name] is None: continue
            if name == 'session-button.json':
                if type(value.get('version')) is not int or value['version'] != 1 or value.get('action') not in ACTIONS: raise ValueError('Invalid local session preferences.')
            elif name == 'recent.json':
                validate_recent(value)
            else:
                if type(value.get('version')) is not int: raise ValueError('Invalid folder settings version.')
                validate_links(value); validate_crop(value.get('portraitCrop'))
                if not isinstance(value.get('hiddenSystemLinks',[]),list) or not all(isinstance(x,str) for x in value.get('hiddenSystemLinks',[])) or not isinstance(value.get('portrait',''),str) or (value.get('portrait') and not Path(value['portrait']).is_absolute()): raise ValueError('Invalid local folder preferences.')
                keys=[x['standard'] for x in value['folders'] if 'standard' in x]
                if len(keys)!=len(set(keys)): raise ValueError('Duplicate standard shortcuts are preserved. Resolve duplicates in Start before portable import/export.')
        return raw, values

    def export(self):
        raw, values = self.snapshot()
        recent = values['recent.json']; folder_data = values['folders.json'].get('folders', [])
        if not isinstance(folder_data, list): raise ValueError('Invalid local folder preferences.')
        order = []; visible = {}
        for item in folder_data:
            if not isinstance(item, dict): raise ValueError('Invalid local folder preferences.')
            if item.get('type') == 'separator':
                order.append({'type': 'separator'})
                continue
            standard = item.get('standard')
            if standard in {x[1] for x in FOLDERS}:
                if standard in visible: raise ValueError('Duplicate standard folder.')
                order.append({'standard': standard, 'visible': item['visible']}); visible[standard] = item['visible']
        for _, standard, _ in FOLDERS:
            if standard not in visible: order.append({'standard': standard, 'visible': raw['folders.json'] is None})
        # Absent source standard links export as hidden, except in a fresh configuration.
        prefs = {'primary': values['session-button.json'].get('action', 'shutdown'),
                 'recent': {'enabled': recent.get('enabled', True), 'limit': recent.get('limit', 20)},
                 'folders': order}
        if 'retention_days' in recent:
            prefs['recent']['retention_days'] = recent['retention_days']
        return validate({'format': 'DoroShell portable Start settings', 'version': 2, 'preferences': prefs})

    def plan(self, value):
        prefs = validate(value)['preferences']; raw, values = self.snapshot(); after = copy.deepcopy(values)
        after['session-button.json'].update(version=1, action=prefs['primary'])
        recent = after['recent.json']
        if not isinstance(recent.get('items', []), list): raise ValueError('Invalid local recent history.')
        # Importing preferences never removes private history. Start itself applies its normal policy on later use.
        if len(recent.get('items', [])) > prefs['recent']['limit']:
            raise ValueError('The imported recent count is smaller than existing history. Clear history in Start first or use a larger count.')
        recent.update(prefs['recent']); recent.setdefault('items', [])
        folders = after['folders.json']
        links = folders.get('folders', [{'label': label, 'standard': key, 'icon': icon, 'visible': True} for label,key,icon in FOLDERS])
        if not isinstance(links, list) or any(not isinstance(x, dict) for x in links): raise ValueError('Invalid local folder preferences.')
        standards = {x.get('standard'): x for x in links if x.get('standard') in {f[1] for f in FOLDERS}}
        replacements = []
        for item in prefs['folders']:
            if item.get('type') == 'separator':
                replacements.append({'type': 'separator'})
                continue
            key = item['standard']
            if key in standards:
                link = standards[key]; link['visible'] = item['visible']; replacements.append(link)
            elif item['visible']:
                label, _, icon = next(x for x in FOLDERS if x[1] == key)
                replacements.append(dict(label=label, standard=key, icon=icon, visible=True))
        merged = []; remaining = iter(replacements)
        for link in links:
            if link.get('standard') in standards or (value['version'] == 2 and link.get('type') == 'separator'):
                replacement = next(remaining, None)
                if replacement is not None: merged.append(replacement)
            else: merged.append(link)
        merged.extend(remaining)
        from menu.start_menu import links_version
        folders.update(version=links_version(merged), folders=merged)
        folders.setdefault('hiddenSystemLinks', []); folders.setdefault('portrait', '')
        from menu.start_menu import validate_links
        validate_links(folders)
        changes = {name: {'before': raw[name], 'after': encode(after[name])} for name in FILES if values[name] != after[name]}
        if any(len(item['after']) > LIMIT for item in changes.values()): raise ValueError('Updated preferences exceed the safe size limit.')
        return changes

    def atomic(self, path, data):
        self.safe(path); path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.doro-portable-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, path)
        finally: Path(temp).unlink(missing_ok=True)

    @contextmanager
    def locked(self):
        self.safe(self.base); self.base.mkdir(parents=True, exist_ok=True)
        lock = self.base/'.portable-settings.lock'; self.safe(lock)
        with lock.open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def write_or_remove(self, path, data):
        if data is None:
            self.safe(path); path.unlink(missing_ok=True)
        else: self.atomic(path, data)

    def transaction(self, changes):
        written = []
        try:
            for name, item in changes.items():
                if self.read(self.base/name) != item['before']: raise ValueError('Settings changed during update.')
                self.write_or_remove(self.base/name, item['after']); written.append(name)
        except Exception as original:
            failures = []
            for name in reversed(written):
                item = changes[name]
                try:
                    if self.read(self.base/name) != item['after']: raise ValueError('Later edit preserved')
                    self.write_or_remove(self.base/name, item['before'])
                except Exception: failures.append(name)
            if failures: raise ValueError('Update interrupted; could not automatically restore: '+', '.join(failures)+'. Local recovery record retained.') from original
            raise

    def apply(self, changes):
        if not changes: return
        if any(not isinstance(item['after'], bytes) or len(item['after']) > LIMIT for item in changes.values()): raise ValueError('Invalid planned settings size.')
        with self.locked():
            for name, item in changes.items():
                if name not in FILES or self.read(self.base/name) != item['before']: raise ValueError('Settings changed after preview; preview again.')
            record = {name: {key: base64.b64encode(data).decode() if data is not None else None for key, data in item.items()} for name,item in changes.items()}
            previous_undo = self.read(self.undo, LIMIT * 10)
            self.atomic(self.undo, encode(record))
            try: self.transaction(changes)
            except Exception:
                if all(self.read(self.base/name) == item['before'] for name,item in changes.items()):
                    self.write_or_remove(self.undo, previous_undo)
                raise

    def rollback(self):
        with self.locked():
            data = self.read(self.undo, LIMIT * 10)
            if data is None: raise ValueError('No portable import to restore.')
            record = decode(data, LIMIT * 10)
            if not isinstance(record, dict) or not record or not set(record) <= set(FILES): raise ValueError('Invalid rollback record.')
            changes = {}
            for name, item in record.items():
                if not isinstance(item, dict) or set(item) != {'before', 'after'}: raise ValueError('Invalid rollback record.')
                before = base64.b64decode(item['before'], validate=True) if item['before'] is not None else None
                after = base64.b64decode(item['after'], validate=True)
                if len(after)>LIMIT or (before is not None and len(before)>LIMIT): raise ValueError('Invalid rollback size.')
                changes[name] = {'before': after, 'after': before}
            for name, item in changes.items():
                if self.read(self.base/name) != item['before']: raise ValueError('Settings changed since import; rollback refused.')
            self.transaction(changes)
            self.undo.unlink()


def open_dialog(parent, home):
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox
    config = os.environ.get('XDG_CONFIG_HOME') if Path(home) == Path.home() else None
    store = Store(home, config)
    dialog = QDialog(parent); dialog.setWindowTitle('Portable Start preferences')
    layout = QVBoxLayout(dialog); note = QLabel(NOTICE); note.setWordWrap(True); layout.addWidget(note)
    def error(exc): QMessageBox.warning(dialog, 'Portable preferences could not complete', str(exc))
    def export():
        try:
            data = encode(store.export())
            name, _ = QFileDialog.getSaveFileName(dialog, 'Export portable preferences', 'DoroShell-preferences.json', 'JSON (*.json)')
            if name: store.atomic(Path(name).absolute(), data)
        except (OSError, ValueError, TypeError) as exc: error(exc)
    def import_():
        try:
            name, _ = QFileDialog.getOpenFileName(dialog, 'Preview portable preferences', '', 'JSON (*.json)')
            if not name: return
            data = store.read(Path(name).absolute())
            if data is None: raise ValueError('Import file no longer exists.')
            value = validate(decode(data)); changes = store.plan(value)
            if not changes:
                QMessageBox.information(dialog, 'Portable preferences', 'These preferences already match.'); return
            prefs = value['preferences']
            summary = ('Primary button: '+prefs['primary']+'\nRecent recording: '+str(prefs['recent']['enabled'])+
                       '\nRecent count: '+str(prefs['recent']['limit'])+
                       '\nRecent age limit (days; 0 = none): '+str(prefs['recent'].get('retention_days', 'unchanged'))+'\nStandard folders/separators, in order:\n'+
                       '\n'.join(('— Separator —' if item.get('type') == 'separator' else item['standard'].removesuffix('Location')+(': shown' if item['visible'] else ': hidden')) for item in prefs['folders']))
            if QMessageBox.question(dialog, 'Apply this preview?', summary+'\n\n'+NOTICE+'\n\nThe previous import rollback is replaced.', QMessageBox.StandardButton.Apply|QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Apply: return
            store.apply(changes)
            QMessageBox.information(dialog, 'Imported', 'Portable preferences saved. Reopen Start. Restore last import is available here.')
        except (OSError, ValueError, TypeError) as exc: error(exc)
    def restore():
        if QMessageBox.question(dialog, 'Restore last import?', 'Restore the exact local preferences from before the last import? Later edits cause a refusal instead of being overwritten.', QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes: return
        try:
            store.rollback(); QMessageBox.information(dialog, 'Restored', 'Previous preferences restored. Reopen Start.')
        except (OSError, ValueError, TypeError) as exc: error(exc)
    for title, callback in [('Export portable preferences…', export), ('Preview and import…', import_), ('Restore last import', restore), ('Close', dialog.reject)]:
        button = QPushButton(title); button.clicked.connect(callback); layout.addWidget(button)
    dialog.exec()
