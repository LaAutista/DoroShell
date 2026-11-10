#!/usr/bin/env python3
"""DoroClipboard: bounded, memory-only X11 clipboard history. Never logs contents."""
import argparse
import base64
import json
import hashlib
import os
import signal
from pathlib import Path
import sys
from dataclasses import dataclass
from functools import cached_property
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMimeData, Qt, QTimer, QProcess
from PySide6.QtGui import QClipboard, QImage, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QCheckBox)

MAX_ENTRY = 4 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
MAX_ITEMS = 50
SENSITIVE = ('x-kde-passwordmanagerhint', 'application/x-keepassxc',
             'application/x-keepass', 'application/x-qt-windows-mime;value="excludeclipboardcontentfrommonitorprocessing"')

@dataclass
class Entry:
    formats: dict
    text: str
    image: QImage | None = None

    @property
    def size(self):
        return sum(len(data) for data in self.formats.values()) + (self.image.sizeInBytes() if self.image is not None else 0)

    @cached_property
    def identity(self):
        digest = hashlib.sha256()
        for name, data in sorted(self.formats.items()):
            digest.update(name.encode()); digest.update(b'\0'); digest.update(data)
        if self.image is not None:
            digest.update(bytes(self.image.constBits()))
            digest.update(f'{self.image.width()}x{self.image.height()}'.encode())
        return digest.digest()

    @cached_property
    def thumbnail(self):
        from PySide6.QtGui import QPixmap
        return QIcon(QPixmap.fromImage(self.image.scaled(64,64,Qt.AspectRatioMode.KeepAspectRatio))) if self.image is not None else QIcon()

    def mime(self, replay=False):
        mime = QMimeData()
        for name, data in self.formats.items():
            if replay and name == 'application/x-kde-cutselection': data = b'0'
            if replay and name == 'x-special/gnome-copied-files' and data.startswith(b'cut\n'): data = b'copy\n'+data[4:]
            mime.setData(name, QByteArray(data))
        if self.image is not None: mime.setImageData(self.image)
        return mime


def snapshot(mime):
    """Preserve supported formats; reject sensitive, oversized and unknown payloads."""
    if mime is None: return None
    formats = mime.formats()
    if any(any(marker in name.lower() for marker in SENSITIVE) for name in formats): return None
    data = {}; total = 0
    # Only known passive content targets. Never request X11 DELETE/INSERT_*
    # or arbitrary application conversion targets, which can have side effects.
    allowed = {'text/plain', 'text/html', 'text/uri-list', 'text/rtf', 'application/rtf',
               'x-special/gnome-copied-files', 'application/x-kde-cutselection',
               'UTF8_STRING', 'STRING', 'TEXT', 'COMPOUND_TEXT'}
    if len(formats) > 32: return None
    for name in formats:
        if name not in allowed and not name.startswith('text/plain;charset='): continue
        value = bytes(mime.data(name))
        total += len(value)
        if total > MAX_ENTRY: return None
        data[name] = value
    text = mime.text() if mime.hasText() else ''
    if len(text) > 262144: return None
    image = None
    if mime.hasImage():
        image = QImage(mime.imageData())
        if image.isNull() or image.sizeInBytes() + total > MAX_ENTRY: return None
        image = image.convertToFormat(QImage.Format.Format_ARGB32).copy()
        if image.sizeInBytes() + total > MAX_ENTRY: return None
    if not text and image is None: return None
    return Entry(data, text, image)


def encode_entry(entry):
    if entry is None: return b'null'
    image = None
    if entry.image is not None:
        array = QByteArray(); buffer = QBuffer(array); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not entry.image.save(buffer, 'PNG'): return b'null'
        image = base64.b64encode(bytes(array)).decode('ascii')
    return json.dumps({'formats':{key:base64.b64encode(value).decode('ascii') for key,value in entry.formats.items()},
                       'text':entry.text,'image':image}, ensure_ascii=True).encode('ascii')


def decode_entry(payload):
    if len(payload) > 8 * 1024 * 1024: return None
    try:
        obj = json.loads(payload)
        if obj is None: return None
        formats = {key:base64.b64decode(value,validate=True) for key,value in obj['formats'].items()}
        text = obj['text']
        if not isinstance(text,str) or len(text)>262144: return None
        image = QImage.fromData(base64.b64decode(obj['image'],validate=True)) if obj['image'] else None
        if image is not None and image.isNull(): return None
        entry = Entry(formats,text,image)
        return entry if entry.size <= MAX_ENTRY else None
    except (ValueError,TypeError,KeyError,AttributeError): return None


def capture_worker(app):
    # X11 owners can stall or allocate excessively during Qt selection transfers.
    # Acquisition runs only here, isolated from the history UI and timed out by it.
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    current = int(Path('/proc/self/statm').read_text().split()[0]) * os.sysconf('SC_PAGE_SIZE')
    resource.setrlimit(resource.RLIMIT_AS,(current+128*1024*1024,current+128*1024*1024))
    from PySide6.QtGui import QImageReader
    QImageReader.setAllocationLimit(16)
    try: payload = encode_entry(snapshot(app.clipboard().mimeData(QClipboard.Mode.Clipboard)))
    except (MemoryError,RuntimeError): payload = b'null'
    sys.stdout.buffer.write(payload); sys.stdout.buffer.flush()
    return 0


class History:
    def __init__(self): self.entries = []
    def add(self, entry):
        if entry is None or entry.size > MAX_ENTRY: return
        self.entries = [old for old in self.entries if old.identity != entry.identity]
        self.entries.insert(0, entry)
        while len(self.entries) > MAX_ITEMS or sum(e.size for e in self.entries) > MAX_TOTAL:
            self.entries.pop()


class ClipboardWindow(QWidget):
    def __init__(self, app):
        super().__init__()
        self.clipboard = app.clipboard(); self.history = History(); self.writing = False
        self.generation = 0; self.capture = None
        app.aboutToQuit.connect(self.cancel_capture)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowTitle('DoroClipboard'); self.resize(440, 500)
        self.setWindowIcon(QIcon.fromTheme('edit-paste'))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('DoroClipboard'))
        note = QLabel('Session-only history • up to 50 copies\nPasswords may be copied as plain text. Pause before copying secrets.')
        note.setWordWrap(True); layout.addWidget(note)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search copied text'); self.search.setAccessibleName('Search clipboard history')
        layout.addWidget(self.search)
        self.items = QListWidget(); self.items.setAccessibleName('Clipboard history'); layout.addWidget(self.items)
        self.empty = QLabel('Copy text or an image to begin. Nothing is saved to disk.'); self.empty.setWordWrap(True); layout.addWidget(self.empty)
        row = QHBoxLayout(); layout.addLayout(row)
        self.copy = QPushButton('Copy selected'); row.addWidget(self.copy)
        self.delete = QPushButton('Delete'); row.addWidget(self.delete)
        self.clear = QPushButton('Clear history'); row.addWidget(self.clear)
        self.pause = QCheckBox('Pause collection'); layout.addWidget(self.pause)
        self.quit = QPushButton('Quit and forget history'); layout.addWidget(self.quit)
        self.quit.clicked.connect(app.quit)
        self.copy.clicked.connect(self.activate); self.items.itemDoubleClicked.connect(self.activate)
        self.delete.clicked.connect(self.remove); self.clear.clicked.connect(self.clear_history)
        self.search.textChanged.connect(self.refresh)
        self.pause.toggled.connect(lambda _: self.cancel_capture())
        self.clipboard.changed.connect(self.changed)
        self.refresh()
        # Deliberately do not import the clipboard that predates service startup.

    def cancel_capture(self):
        self.generation += 1
        if self.capture is not None:
            self.capture.kill()
            self.capture = None

    def changed(self, mode):
        if mode != QClipboard.Mode.Clipboard or self.writing: return
        self.cancel_capture()
        if self.pause.isChecked(): return
        generation = self.generation
        process = QProcess(self); self.capture = process
        output = bytearray()
        timer = QTimer(process); timer.setSingleShot(True)
        timer.timeout.connect(process.kill)
        def drain():
            output.extend(bytes(process.readAllStandardOutput()))
            if len(output) > 8*1024*1024:
                output.clear(); process.kill()
        process.readyReadStandardOutput.connect(drain)
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        def finished(code, status):
            timer.stop(); drain()
            if self.capture is process: self.capture = None
            if generation == self.generation and code == 0 and status == QProcess.ExitStatus.NormalExit and not self.pause.isChecked():
                entry = decode_entry(output)
                if entry is not None:
                    self.history.add(entry)
                    self.writing = True
                    try: self.clipboard.setMimeData(entry.mime(),QClipboard.Mode.Clipboard)
                    finally: self.writing = False
                    self.refresh()
            process.deleteLater()
        process.finished.connect(finished)
        def failed(error):
            if error == QProcess.ProcessError.FailedToStart:
                timer.stop()
                if self.capture is process: self.capture = None
                process.deleteLater()
        process.errorOccurred.connect(failed)
        process.start(sys.executable,[str(Path(__file__).resolve()),'--capture'])
        timer.start(1500)

    def refresh(self):
        selected = self.selected()
        identity = selected.identity if selected else None
        self.items.clear(); query = self.search.text().casefold()
        for entry in self.history.entries:
            if query and query not in entry.text.casefold(): continue
            label = ' '.join(entry.text.split())[:160] or f'Image {entry.image.width()} × {entry.image.height()}'
            item = QListWidgetItem(label); item.setData(Qt.ItemDataRole.UserRole, entry)
            if entry.image is not None:
                item.setIcon(entry.thumbnail)
            self.items.addItem(item)
            if entry.identity == identity: self.items.setCurrentItem(item)
        if self.items.currentRow() < 0 and self.items.count(): self.items.setCurrentRow(0)
        self.empty.setVisible(not self.items.count())
        self.copy.setEnabled(bool(self.items.count())); self.delete.setEnabled(bool(self.items.count()))

    def selected(self):
        item = self.items.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def activate(self, *_):
        self.cancel_capture()
        entry = self.selected()
        if entry is None: return
        self.writing = True
        try: self.clipboard.setMimeData(entry.mime(replay=True), QClipboard.Mode.Clipboard)
        finally: self.writing = False
        self.history.add(entry); self.refresh(); self.hide()
        # Never synthesize Ctrl+V into another application.

    def remove(self):
        entry = self.selected()
        if entry:
            self.history.entries = [e for e in self.history.entries if e.identity != entry.identity]
            self.refresh()

    def clear_history(self):
        self.cancel_capture()
        self.history.entries.clear(); self.refresh()
        # Clearing stored history does not overwrite the user's current clipboard.

    def open(self):
        self.refresh(); self.show(); self.raise_(); self.activateWindow(); self.search.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.hide(); return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter): self.activate(); return
        super().keyPressEvent(event)

    def closeEvent(self, event): event.ignore(); self.hide()


def manager_conflicts():
    """Only inspect process names, never another manager's history."""
    names = {'copyq', 'qlipper', 'klipper', 'clipit', 'parcellite', 'xfce4-clipman'}
    found = set()
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit(): continue
        try:
            if directory.stat().st_uid == os.getuid():
                name = (directory/'comm').read_text().strip()
                if name in names: found.add(name)
        except (OSError, ValueError): pass
    return sorted(found)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--show', action='store_true'); parser.add_argument('--stop',action='store_true'); parser.add_argument('--capture',action='store_true',help=argparse.SUPPRESS); args = parser.parse_args()
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    if args.capture:
        # Also self-terminate if the UI is killed before its timeout can run.
        signal.alarm(2)
    app = QApplication(sys.argv[:1]); app.setQuitOnLastWindowClosed(False)
    if app.platformName() != 'xcb':
        print('DoroClipboard currently requires X11.', file=sys.stderr); return 1
    if args.capture: return capture_worker(app)
    # Separate singleton per display and user runtime; no global stale-socket deletion.
    key = hashlib.sha256(os.environ.get('DISPLAY','').encode()).hexdigest()[:16]
    name = f'doroshell-clipboard-{os.getuid()}-{key}'
    probe = QLocalSocket(); probe.connectToServer(name)
    if probe.waitForConnected(300):
        probe.write(b'stop\n' if args.stop else b'show\n' if args.show else b'ping\n'); probe.waitForBytesWritten(300); probe.disconnectFromServer(); return 0
    if args.stop: return 0
    conflicts = manager_conflicts()
    if conflicts:
        print('DoroClipboard not started: another clipboard manager is running: '+', '.join(conflicts), file=sys.stderr); return 2
    from PySide6.QtCore import QLockFile, QStandardPaths
    runtime = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    lock = QLockFile(str(Path(runtime)/(name+'.lock')))
    if not lock.tryLock(0): return 0
    QLocalServer.removeServer(name)
    server = QLocalServer(); server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(name): return 1
    window = ClipboardWindow(app)
    sockets = set()
    def accept():
        while server.hasPendingConnections():
            socket = server.nextPendingConnection(); sockets.add(socket)
            def read(s=socket):
                data = bytes(s.readAll())
                if b'stop' in data[:16]: app.quit()
                elif b'show' in data[:16]: window.open()
                s.disconnectFromServer()
            socket.readyRead.connect(read)
            socket.disconnected.connect(lambda s=socket: (sockets.discard(s), s.deleteLater()))
            if socket.bytesAvailable(): read()
    server.newConnection.connect(accept)
    if args.show: QTimer.singleShot(0, window.open)
    return app.exec()

if __name__ == '__main__': sys.exit(main())
