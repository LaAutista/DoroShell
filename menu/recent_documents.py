"""Opt-in, read-only desktop XBEL view. Never inspect the referenced targets."""
import json
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata
from datetime import datetime
from urllib.parse import quote, unquote_to_bytes, urlsplit
from xml.parsers import expat

MAX_BYTES = 1024 * 1024
MAX_BOOKMARKS = 2048
MAX_ITEMS = 20
BOOKMARK_NS = 'http://www.freedesktop.org/standards/desktop-bookmarks'
NOTICE = 'Shared desktop history; local file URIs only. Availability is not checked.'


def local_uri(value):
    if not isinstance(value, str) or len(value) > 4096 or not value.lower().startswith('file:') or any(unicodedata.category(c).startswith('C') or unicodedata.category(c) in ('Zl', 'Zp') for c in value):
        raise ValueError('Unsupported document URI')
    if re.search(r'%(?![0-9a-fA-F]{2})', value):
        raise ValueError('Unsupported document URI')
    parts = urlsplit(value)
    if parts.scheme != 'file' or parts.netloc.lower() not in ('', 'localhost') or '?' in value or '#' in value:
        raise ValueError('Unsupported document URI')
    path = unquote_to_bytes(parts.path).decode('utf-8', 'strict')
    if (not path.startswith('/') or path.startswith('//') or path.endswith('/') or
            any(p in ('.', '..', '') for p in path.split('/')[1:]) or
            any(unicodedata.category(c).startswith('C') or unicodedata.category(c) in ('Zl', 'Zp') for c in path)):
        raise ValueError('Unsupported document URI')
    uri = 'file://' + quote(path, safe='/')
    if len(uri) > 4096: raise ValueError('Unsupported document URI')
    return uri, path.rsplit('/', 1)[-1]


def parse(data):
    if len(data) > MAX_BYTES:
        raise ValueError('Desktop history exceeds the 1 MiB limit')
    parser = expat.ParserCreate(namespace_separator='|')
    stack, records, private = [], {}, set()
    current = None
    count = 0

    def forbidden(*args):
        raise ValueError('Desktop history declarations/entities are unsupported')

    def start(name, attrs):
        nonlocal current, count
        stack.append(name)
        if len(stack) > 16 or len(attrs) > 32 or (len(stack) == 1 and name != 'xbel'):
            raise ValueError('Unsupported desktop history structure')
        if name == 'bookmark':
            count += 1
            if count > MAX_BOOKMARKS or stack != ['xbel', 'bookmark']:
                raise ValueError('Desktop history has too many or nested bookmarks')
            current = None
            try:
                uri, label = local_uri(attrs.get('href'))
                stamps = []
                for key in ('visited', 'modified', 'added'):
                    try:
                        stamp = datetime.fromisoformat(attrs.get(key, '').replace('Z', '+00:00'))
                        if stamp.tzinfo is not None: stamps.append(stamp.timestamp())
                    except (ValueError, OverflowError):
                        pass
                current = {'uri': uri, 'label': label[:128], 'stamp': max(stamps, default=-float('inf')), 'private': False}
            except (ValueError, UnicodeError):
                pass
        elif current is not None and name == BOOKMARK_NS + '|private':
            current['private'] = True

    def end(name):
        nonlocal current
        if name == 'bookmark' and current is not None:
            uri = current['uri']
            if current['private']: private.add(uri)
            if uri not in records or current['stamp'] > records[uri]['stamp']: records[uri] = current
            current = None
        stack.pop()

    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    try:
        parser.Parse(data, True)
    except expat.ExpatError as error:
        raise ValueError('Desktop history XML is malformed') from error
    ordered = sorted((r for uri, r in records.items() if uri not in private), key=lambda r: (-r['stamp'], r['uri']))
    return [{'uri': r['uri'], 'label': r['label']} for r in ordered[:MAX_ITEMS]]


def bounded_read(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('File exceeds the limit or is not a regular file')
        data = stream.read(limit + 1)
        if len(data) > limit: raise ValueError('File exceeds the limit')
        return data


def read_shared():
    base = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))
    if not base.is_absolute(): raise ValueError('Desktop data directory must be absolute')
    try:
        return parse(bounded_read(base/'recently-used.xbel', MAX_BYTES))
    except FileNotFoundError:
        return []


def preference(path):
    """Return default-off state; preserve invalid/future bytes rather than migrate."""
    try:
        data = bounded_read(path, 4096)
    except FileNotFoundError:
        return False, None, None
    except (OSError, ValueError):
        return False, None, 'Recent-document preferences are unreadable; preserved unchanged.'
    try:
        def unique(pairs):
            if len(dict(pairs)) != len(pairs): raise ValueError('Duplicate preference key')
            return dict(pairs)
        value = json.loads(data, object_pairs_hook=unique)
        if not isinstance(value, dict) or set(value) != {'version', 'enabled'} or type(value['version']) is not int or value['version'] != 1 or type(value['enabled']) is not bool:
            raise ValueError()
        return value['enabled'], data, None
    except (ValueError, UnicodeError):
        return False, data, 'Recent-document preferences are invalid; preserved unchanged.'


def make_menu(parent, enabled, activate):
    from PySide6.QtCore import QProcess, QTimer
    from PySide6.QtWidgets import QMenu

    class DocumentsMenu(QMenu):
        def __init__(self):
            super().__init__('Recent documents', parent)
            self.setToolTipsVisible(True)
            self.process = None
            self.buffer = bytearray()
            self.timer = QTimer(self); self.timer.setSingleShot(True)
            self.timer.timeout.connect(lambda: self.fail('Desktop history timed out; try reopening.'))
            self.erase_timer = QTimer(self); self.erase_timer.setSingleShot(True)
            self.erase_timer.timeout.connect(self.erase_hidden)
            self.aboutToShow.connect(self.load)
            self.aboutToHide.connect(self.cancel)

        def stop(self):
            self.timer.stop()
            process, self.process = self.process, None
            if process is not None:
                process.kill()
                process.finished.connect(process.deleteLater)
                if process.state() == QProcess.ProcessState.NotRunning: process.deleteLater()
            self.buffer.clear()

        def cancel(self):
            self.stop()
            self.erase_timer.start(0)

        def erase_hidden(self):
            if not self.isVisible(): self.clear()

        def message(self, text):
            self.clear(); self.addAction(text).setEnabled(False)

        def fail(self, text):
            self.stop(); self.message(text)

        def load(self):
            self.stop()
            self.erase_timer.stop()
            if not enabled():
                self.message('Recent documents are disabled.'); return
            self.message('Reading shared desktop history…')
            process = self.process = QProcess(self)
            process.setStandardErrorFile(os.devnull)
            process.readyReadStandardOutput.connect(lambda: self.receive(process))
            process.finished.connect(lambda code, status: self.complete(process, code, status))
            process.errorOccurred.connect(lambda *_: self.fail('Desktop history reader unavailable.') if process is self.process else None)
            process.start(sys.executable, ['-B', str(Path(__file__).resolve()), '--read'])
            self.timer.start(1500)

        def receive(self, process):
            if process is not self.process: return
            self.buffer.extend(bytes(process.readAllStandardOutput()))
            if len(self.buffer) > 128 * 1024: self.fail('Desktop history response exceeds the limit.')

        def complete(self, process, code, status):
            if process is not self.process: return
            self.receive(process)
            if process is not self.process: return
            try:
                if code or status != QProcess.ExitStatus.NormalExit or not enabled(): raise ValueError()
                rows = json.loads(self.buffer)
                if not isinstance(rows, list) or len(rows) > MAX_ITEMS: raise ValueError()
                for row in rows:
                    uri, label = local_uri(row['uri'])
                    if set(row) != {'uri', 'label'} or uri != row['uri'] or row['label'] != label[:128]: raise ValueError()
            except (ValueError, TypeError, UnicodeError, KeyError):
                self.fail('Desktop history unavailable or unsupported; it was not changed.'); return
            self.stop(); self.message(NOTICE)
            if not rows: self.addAction('No supported recent documents.').setEnabled(False)
            for row in rows:
                action = self.addAction(row['label'].replace('&', '&&'))
                action.setToolTip(row['uri']+'\nAvailability unverified; opens with the default application.')
                action.triggered.connect(lambda checked=False, uri=row['uri']: activate(uri))
    return DocumentsMenu()


if __name__ == '__main__':
    if sys.argv[1:] != ['--read']: raise SystemExit(2)
    try:
        print(json.dumps(read_shared()))
    except (OSError, ValueError):
        raise SystemExit(1)  # No paths or arbitrary parser/driver errors in diagnostics.
