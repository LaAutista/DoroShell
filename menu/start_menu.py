#!/usr/bin/env python3
"""An optional two-column LXQt launcher. Desktop files launch through GIO."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sys
import copy
import tempfile
import time
import subprocess
import shutil

def runtime_signature():
    """Detect helper upgrades before reusing a loaded resident."""
    import hashlib
    root = Path(__file__).resolve().parent
    paths = [root / name for name in ('start_menu.py', 'wallpaper_glass.py', 'app_search.py',
                                     'folder_cascade.py', 'portrait_crop.py', 'themes.py')]
    paths.append(root.parent / 'themes.py')
    return hashlib.sha256(repr([(str(p), file_stamp(p)) for p in paths]).encode()).hexdigest()


def file_stamp(path):
    try:
        stat = path.stat()
        return stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
    except OSError:
        return None


def toggle_existing():
    # This path must stay above Qt/GIO imports: ordinary repeated clicks cost only IPC.
    import socket
    address = str(Path(tempfile.gettempdir()) / ('lxqt-comfort-' + str(os.getuid())))
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1)
        try:
            client.connect(address)
        except OSError:
            return False
        try:
            client.sendall((runtime_signature() + '\n').encode())
            return client.recv(16) == b'OK'
        except TimeoutError:
            return True  # A busy/startup-pending resident still owns the queued toggle.
        except OSError:
            return False


if __name__ == '__main__' and len(sys.argv) == 1 and toggle_existing():
    sys.exit(0)


sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app_search import AppSearchIndex, is_visible
from portrait_crop import PortraitCropDialog, validate_crop, load_image, render_crop
from folder_cascade import FolderCascadeMenu

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib
from PySide6.QtCore import Qt, QStandardPaths, QTimer, QSize, QRectF, Signal, QUrl
from PySide6.QtNetwork import QLocalServer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QCursor, QDrag, QActionGroup, QPainterPath, QRegion, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QToolButton, QComboBox,
    QMessageBox, QMenu, QDialog, QDialogButtonBox, QTableWidget,
    QTableWidgetItem, QFileDialog, QCheckBox, QAbstractItemView, QScrollArea, QStyledItemDelegate)

SESSION_ACTIONS = {
    'shutdown': ('Shut down', 'system-shutdown'),
    'reboot': ('Restart', 'system-reboot'),
    'logout': ('Log out', 'system-log-out'),
    'suspend': ('Sleep', 'system-suspend'),
    'hibernate': ('Hibernate', 'system-suspend-hibernate'),
    'lockscreen': ('Lock screen', 'system-lock-screen'),
}

FOLDERS = [('Home', 'HomeLocation', 'user-home'),
           ('Documents', 'DocumentsLocation', 'folder-documents'),
           ('Downloads', 'DownloadLocation', 'folder-download'),
           ('Pictures', 'PicturesLocation', 'folder-pictures'),
           ('Music', 'MusicLocation', 'folder-music'),
           ('Videos', 'MoviesLocation', 'folder-videos')]
CATEGORIES = ['AudioVideo', 'Development', 'Education', 'Game', 'Graphics',
              'Network', 'Office', 'Science', 'Settings', 'System', 'Utility']


SYSTEM_GROUPS = (
    (('Games', ()), ('Computer', ())),
    (('Control Panel', ('lxqt-config.desktop',)),
     ('Network connections', ('nm-connection-editor.desktop',)),
     ('Printers', ('kcm_printer_manager.desktop', 'system-config-printer.desktop')),
     ('Default programs', ('lxqt-config-file-associations.desktop',))),
)


def desktop_entry(desktop_id):
    try:
        return Gio.DesktopAppInfo.new(desktop_id)
    except TypeError:
        # PyGObject raises this when g_desktop_app_info_new returns NULL.
        return None


def available_entry(ids):
    for entry in ids:
        app = desktop_entry(entry)
        if app and (app.get_boolean('DBusActivatable') or shutil.which(app.get_executable())):
            return entry
    return None


def default_pins(by_id):
    slots = (
        (('qterminal.desktop', 'org.kde.konsole.desktop', 'org.gnome.Terminal.desktop', 'xfce4-terminal.desktop', 'xterm.desktop'), ('x-scheme-handler/terminal',)),
        (('firefox.desktop', 'org.mozilla.firefox.desktop'), ('x-scheme-handler/https',)),
        (('org.kde.dolphin.desktop',), ('inode/directory',)),
        (('org.kde.kate.desktop',), ('text/plain',)),
        (('vlc.desktop', 'org.videolan.VLC.desktop'), ('video/mp4', 'audio/mpeg')),
        (('lxqt-config.desktop',), ()),
    )
    pins = []
    for ids, types in slots:
        entry = available_entry([key for key in ids if key in by_id])
        if not entry:
            for mime in types:
                app = Gio.AppInfo.get_default_for_type(mime, False)
                if app and app.get_id() in by_id:
                    entry = available_entry([app.get_id()])
                    if entry:
                        break
        if entry and entry not in pins:
            pins.append(entry)
    return pins


def has_compositor():
    if QApplication.platformName() != 'xcb':
        return QApplication.platformName().startswith('wayland')
    try:
        from Xlib import display, error
    except ImportError:
        return False
    try:
        with closing(display.Display()) as server:
            atom = server.intern_atom(f'_NET_WM_CM_S{server.get_default_screen()}')
            return bool(server.get_selection_owner(atom))
    except (error.DisplayError, OSError):
        return False


def default_links():
    return [{'label': label, 'standard': location, 'icon': icon, 'visible': True}
            for label, location, icon in FOLDERS]


def validate_links(value):
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ValueError('Unsupported folder settings version')
    links = value.get('folders')
    if not isinstance(links, list) or len(links) > 100:
        raise ValueError('Folder settings must contain at most 100 links')
    standards = {location for _, location, _ in FOLDERS}
    for link in links:
        if not isinstance(link, dict) or not isinstance(link.get('label'), str) or not link['label'].strip() or len(link['label']) > 100:
            raise ValueError('Every folder needs a name of 1–100 characters')
        if type(link.get('visible')) is not bool or not isinstance(link.get('icon', 'folder'), str):
            raise ValueError('Invalid folder visibility or icon')
        if 'standard' in link:
            if not isinstance(link['standard'], str) or link['standard'] not in standards or 'path' in link:
                raise ValueError('Invalid standard folder')
        elif not isinstance(link.get('path'), str) or not Path(link['path']).is_absolute() or '\x00' in link['path']:
            raise ValueError('Custom folders require an absolute path')
    return links


def link_path(link):
    if 'standard' in link:
        return QStandardPaths.writableLocation(getattr(QStandardPaths.StandardLocation, link['standard']))
    return link['path']


class FolderSettings:
    def __init__(self, path):
        self.path = path
        self.original = None
        self.error = None
        self.links = default_links()
        self.hidden = []
        self.portrait = ''
        self.portrait_crop = None
        try:
            self.original = path.read_bytes()
            value = json.loads(self.original)
            self.links = validate_links(value)
            hidden = value.get('hiddenSystemLinks', [])
            portrait = value.get('portrait', '')
            if not isinstance(hidden, list) or not all(isinstance(item, str) for item in hidden):
                raise ValueError('Invalid system link preferences')
            if not isinstance(portrait, str) or (portrait and not Path(portrait).is_absolute()):
                raise ValueError('Invalid portrait path')
            self.hidden = hidden
            self.portrait = portrait
            self.portrait_crop = validate_crop(value.get('portraitCrop'))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            self.error = str(error)

    def save(self, links, *, hidden=None, portrait=None, crop=None):
        if self.error:
            raise ValueError('Existing folder settings could not be read; they will not be overwritten: ' + self.error)
        hidden = self.hidden if hidden is None else hidden
        crop = validate_crop(self.portrait_crop if portrait is None and crop is None else crop)
        portrait = self.portrait if portrait is None else portrait
        data = json.dumps({'version': 1, 'folders': links, 'hiddenSystemLinks': hidden, 'portrait': portrait, 'portraitCrop': crop}, ensure_ascii=False, indent=2).encode() + b'\n'
        validate_links(json.loads(data))
        if self.path.is_symlink():
            raise ValueError('Refusing to replace a symlinked settings file')
        current = self.path.read_bytes() if self.path.exists() else None
        if current != self.original:
            raise ValueError('Folder settings changed elsewhere. Close and reopen the editor.')
        if current == data:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if current is not None:
            backup = self.path.with_name(self.path.name + '.backup-' + str(time.time_ns()))
            with backup.open('xb') as stream:
                stream.write(current)
            backup.chmod(0o600)
        fd, name = tempfile.mkstemp(prefix='.folders-', dir=self.path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.original = data
        self.links = copy.deepcopy(links)
        self.hidden = list(hidden)
        self.portrait = portrait
        self.portrait_crop = crop


def save_json(path, value, original):
    """Refuse external edits and preserve the previous valid state."""
    if path.is_symlink():
        raise ValueError('Refusing symlinked preferences')
    current = path.read_bytes() if path.exists() else None
    if current != original:
        raise ValueError('Preferences changed elsewhere; reopen the menu.')
    data = (json.dumps(value, indent=2) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if current is not None and current != data:
        backup = path.with_name(path.name + '.backup-' + str(time.time_ns()))
        backup.write_bytes(current)
        backup.chmod(0o600)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.menu-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if original is None:
            os.link(name, path)
        else:
            os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
    return data


class RecentPrograms:
    def __init__(self, path):
        self.path = path
        self.original = None
        self.value = {'enabled': True, 'items': []}
        self.error = None
        try:
            self.original = path.read_bytes() if path.exists() else None
            if self.original is not None:
                value = json.loads(self.original)
                if (not isinstance(value, dict) or type(value.get('enabled')) is not bool
                        or not isinstance(value.get('items'), list)
                        or type(value.get('limit', 20)) is not int
                        or not 1 <= value.get('limit', 20) <= 50
                        or len(value['items']) > value.get('limit', 20)
                        or not all(isinstance(x, str) for x in value['items'])):
                    raise ValueError('Invalid recent-program preferences')
                self.value = value
        except (ValueError, OSError) as error:
            self.error = str(error)

    def save(self, enabled=None, launched=None, clear=False, limit=None):
        if self.error:
            raise ValueError(self.error)
        value = copy.deepcopy(self.value)
        if limit is not None:
            if type(limit) is not int or not 1 <= limit <= 50:
                raise ValueError('Recent-program count must be between 1 and 50.')
            value['limit'] = limit
        if enabled is not None:
            value['enabled'] = enabled
        if clear or not value['enabled']:
            value['items'] = []
        if launched and value['enabled']:
            value['items'] = [launched] + [x for x in value['items'] if x != launched]
        value['items'] = value['items'][:value.get('limit', 20)]
        self.original = save_json(self.path, value, self.original)
        self.value = value


class FolderEditor(QDialog):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle('Folder links — DoroShell')
        self.resize(660, 460)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Rename a link in the Name column. Uncheck Show to hide it.'))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Name', 'Folder', 'Show'])
        self.table.setAccessibleName('Folder links')
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 350)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        self.buttons = {}
        for text, callback in [('Add folder…', self.add_folder), ('Change folder…', self.change_folder), ('Move up', lambda: self.move(-1)),
                               ('Move down', lambda: self.move(1)), ('Remove', self.remove),
                               ('Restore defaults', lambda: self.populate(default_links()))]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
            self.buttons[text] = button
        layout.addLayout(row)
        self.system_checks = {}
        for group in SYSTEM_GROUPS:
            choices = QHBoxLayout()
            for label, _ in group:
                check = QCheckBox(label)
                check.setChecked(label not in settings.hidden)
                self.system_checks[label] = check
                choices.addWidget(check)
            layout.addLayout(choices)
        self.portrait = settings.portrait
        self.portrait_crop = copy.deepcopy(settings.portrait_crop)
        portrait_row = QHBoxLayout()
        self.picture_label = QLabel()
        self.update_picture_label()
        portrait_row.addWidget(self.picture_label, 1)
        choose = QPushButton('Choose portrait…')
        choose.clicked.connect(self.choose_picture)
        portrait_row.addWidget(choose)
        reset = QPushButton('Use Start icon')
        reset.clicked.connect(lambda: self.set_picture(''))
        portrait_row.addWidget(reset)
        layout.addLayout(portrait_row)
        self.notice = QLabel(settings.error or 'Changes are saved only when you choose Save. Escape cancels.')
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.actions.accepted.connect(self.save)
        self.actions.rejected.connect(self.reject)
        self.actions.button(QDialogButtonBox.StandardButton.Save).setEnabled(not settings.error)
        layout.addWidget(self.actions)
        self.populate(settings.links)

    def populate(self, links):
        self.table.setRowCount(0)
        for link in links:
            row = self.table.rowCount()
            self.table.insertRow(row)
            label = QTableWidgetItem(link['label'])
            label.setData(Qt.ItemDataRole.UserRole, copy.deepcopy(link))
            self.table.setItem(row, 0, label)
            path = QTableWidgetItem(link_path(link))
            path.setFlags(path.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, path)
            show = QTableWidgetItem()
            show.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            show.setCheckState(Qt.CheckState.Checked if link['visible'] else Qt.CheckState.Unchecked)
            self.table.setItem(row, 2, show)
        if links:
            self.table.selectRow(0)

    def values(self):
        links = []
        for row in range(self.table.rowCount()):
            link = copy.deepcopy(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
            link['label'] = self.table.item(row, 0).text().strip()
            link['visible'] = self.table.item(row, 2).checkState() == Qt.CheckState.Checked
            links.append(link)
        return links

    def add_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Choose folder')
        if path:
            links = self.values()
            links.append({'label': Path(path).name or path, 'path': path, 'icon': 'folder', 'visible': True})
            self.populate(links)
            self.table.selectRow(len(links) - 1)

    def update_picture_label(self):
        self.picture_label.setText('Portrait · ' + (Path(self.portrait).name if self.portrait else 'Start icon'))
        self.picture_label.setToolTip(self.portrait)

    def set_picture(self, path, crop=None):
        self.portrait_crop = validate_crop(crop)
        self.portrait = path
        self.update_picture_label()

    def choose_picture(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose Start menu portrait', '', 'Pictures (*.png *.jpg *.jpeg *.webp *.svg)')
        if path:
            try:
                dialog = PortraitCropDialog(path, self.portrait_crop if path == self.portrait else None, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self.set_picture(path, dialog.crop())
                dialog.deleteLater()
            except ValueError as error:
                self.notice.setText(str(error))

    def change_folder(self):
        row = self.table.currentRow()
        if row < 0:
            return
        links = self.values()
        path = QFileDialog.getExistingDirectory(self, 'Change folder destination', link_path(links[row]))
        if path:
            links[row].pop('standard', None)
            links[row]['path'] = path
            self.populate(links)
            self.table.selectRow(row)

    def move(self, delta):
        row = self.table.currentRow()
        other = row + delta
        if row < 0 or not 0 <= other < self.table.rowCount():
            return
        links = self.values()
        links[row], links[other] = links[other], links[row]
        self.populate(links)
        self.table.selectRow(other)

    def remove(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def save(self):
        try:
            self.settings.save(self.values(), hidden=[k for k, v in self.system_checks.items() if not v.isChecked()], portrait=self.portrait, crop=self.portrait_crop)
        except (OSError, ValueError) as error:
            self.notice.setText(str(error))
            return
        self.accept()


def applications():
    return sorted([a for a in Gio.AppInfo.get_all() if is_visible(a)],
                  key=lambda a: (a.get_display_name().casefold(), a.get_id() or ''))


def matches(app, query, category):
    categories = (app.get_categories() or '').split(';')
    words = ' '.join([app.get_display_name(), app.get_description() or '',
                      app.get_executable() or '', ' '.join(app.get_keywords() or [])]).casefold()
    return (category == 'All applications' or category in categories) and all(
        word in words for word in query.casefold().split())


def icon_for(app):
    icon = app.get_icon()
    if isinstance(icon, Gio.ThemedIcon):
        for name in icon.get_names():
            if QIcon.hasThemeIcon(name):
                return QIcon.fromTheme(name)
    if isinstance(icon, Gio.FileIcon):
        return QIcon(icon.get_file().get_path())
    return QIcon.fromTheme('application-x-executable')


def control_icon(name, widget):
    """Keep symbolic controls legible when the system icon theme is light-only."""
    widget.ensurePolished()
    pixmap = QIcon.fromTheme(name).pixmap(32, 32)
    if not pixmap.isNull():
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), widget.palette().color(QPalette.ColorRole.WindowText))
        painter.end()
    return QIcon(pixmap)


class ApplicationList(QListWidget):
    """Keep native drop feedback, but persist pins before rebuilding the list."""
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.dragged_id = None
        self.dragging = False
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setDropIndicatorShown(True)

    def startDrag(self, actions):
        item = self.currentItem()
        if item is None:
            return
        desktop_id = item.data(Qt.ItemDataRole.UserRole)
        app = self.owner.by_id.get(desktop_id)
        filename = app.get_filename() if isinstance(app, Gio.DesktopAppInfo) else None
        if not filename or not Path(filename).is_absolute() or not Path(filename).is_file():
            return
        self.dragged_id = desktop_id
        self.internal_drop = False
        self.dragging = True
        drag = QDrag(self)
        data = self.model().mimeData([self.indexFromItem(item)])
        data.setUrls([QUrl.fromLocalFile(filename)])
        drag.setMimeData(data)
        drag.setPixmap(item.icon().pixmap(self.iconSize()))
        exit_on_hide = self.owner.exit_on_hide
        self.owner.exit_on_hide = False
        # Keep the one-shot process alive until Qt finishes the target's URI transfer.
        if exit_on_hide:
            drag.destroyed.connect(lambda: QTimer.singleShot(0, lambda: QApplication.instance().quit()
                if not self.owner.isVisible() else None))
        try:
            # Copy-only outside Start: never move an installed application launcher.
            result = drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
            if result == Qt.DropAction.CopyAction and not self.internal_drop:
                self.owner.hide()
        finally:
            self.owner.exit_on_hide = exit_on_hide
            self.dragged_id = None
            # Qt owns drag cleanup; early deletion loses the target's deferred URI request.
            # Ignore the release that ends the drag; it must not launch an app.
            QTimer.singleShot(0, self.finish_drag)

    def finish_drag(self):
        self.dragging = bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        item = self.itemAt(event.position().toPoint())
        if event.source() is not self or not self.owner.can_reorder_pins() or (item and item.data(Qt.ItemDataRole.UserRole) not in self.owner.favorites):
            event.ignore()

    def dropEvent(self, event):
        if event.source() is not self or not self.owner.can_reorder_pins():
            event.ignore()
            return
        item = self.itemAt(event.position().toPoint())
        target = item.data(Qt.ItemDataRole.UserRole) if item else None
        after = bool(item and event.position().y() > self.visualItemRect(item).center().y())
        if self.owner.reorder_pin(self.dragged_id, target, after):
            self.internal_drop = True
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()


MENU_SIZE = QSize(508, 634)


class Portrait(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


class StartMenu(QWidget):
    catalog_changed = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.Popup)
        self.setWindowTitle('DoroShell Start')
        self.setObjectName('doroShellStart')
        self.exit_on_hide = False
        self.launching = False
        self.resize(MENU_SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.apps = applications()
        self.search_index = AppSearchIndex(self.apps)
        self.by_id = {app.get_id(): app for app in self.apps}
        self.state = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'lxqt-comfort/favorites.json'
        self.favorites = []
        self.state_original = None
        self.recent = RecentPrograms(self.state.with_name('recent.json'))
        self.primary_action = 'shutdown'
        self.primary_path = self.state.with_name('session-button.json')
        self.primary_original = None
        self.primary_error = None
        try:
            if self.primary_path.is_symlink():
                raise ValueError('Refusing symlinked session preferences')
            if self.primary_path.exists():
                self.primary_original = self.primary_path.read_bytes()
                value = json.loads(self.primary_original)
                if not isinstance(value, dict) or value.get('version') != 1 or value.get('action') not in SESSION_ACTIONS:
                    raise ValueError('Invalid session button preferences')
                self.primary_action = value['action']
        except (OSError, ValueError, TypeError) as error:
            self.primary_error = str(error)
        self.state_error = None
        try:
            if not self.state.exists():
                try:
                    save_json(self.state, default_pins(self.by_id), None)
                except (FileExistsError, ValueError):
                    if not self.state.is_file() or self.state.is_symlink():
                        raise
            self.state_original = self.state.read_bytes()
            value = json.loads(self.state_original)
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError('Favorites must be a list of desktop IDs')
            self.favorites = value
        except (OSError, ValueError) as error:
            self.state_error = str(error)
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 58, 2, 2)
        self.frame = frame = QWidget()
        frame.setObjectName('glassFrame')
        root.addWidget(frame)
        body = QHBoxLayout(frame)
        body.setContentsMargins(10, 14, 10, 12)
        body.setSpacing(6)
        self.folder_settings = FolderSettings(self.state.with_name('folders.json'))
        self.mascot = Portrait(self)
        self.mascot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mascot.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.mascot.setToolTip('Choose Start menu portrait')
        self.mascot.clicked.connect(self.choose_portrait)
        self.mascot.setObjectName('personalStartImage')
        self.mascot.setFixedSize(88, 88)
        self.mascot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mascot.setAccessibleName('Start menu portrait')
        self.refresh_portrait()
        apps_panel = QWidget()
        apps_panel.setObjectName('applicationsPanel')
        left = QVBoxLayout(apps_panel)
        left.setContentsMargins(8, 8, 8, 8)
        self.pinned_heading = QLabel('Pinned')
        self.pinned_heading.setObjectName('pinnedHeading')
        left.addWidget(self.pinned_heading)
        self.category = QComboBox()
        self.category.setItemDelegate(QStyledItemDelegate(self.category))
        self.category.addItems(['Home', 'All applications', 'Pinned', 'Recent'] + CATEGORIES)
        self.category.setAccessibleName('Application category')
        left.addWidget(self.category)
        self.list = ApplicationList(self)
        self.list.setIconSize(QSize(32, 32))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.list.setAccessibleName('Applications')
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.context_menu)
        self.list.itemClicked.connect(self.launch_item)
        self.list.itemActivated.connect(self.launch_item)
        left.addWidget(self.list)
        self.search_notice = QLabel()
        self.search_notice.setWordWrap(True)
        self.search_notice.setTextFormat(Qt.TextFormat.PlainText)
        self.search_notice.setAccessibleName('Application search status')
        left.addWidget(self.search_notice)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search programs…')
        self.search_action = self.search.addAction(QIcon(), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setAccessibleName('Search applications')
        self.programs = QPushButton('All Programs')
        self.programs.setObjectName('programsButton')
        self.programs.clicked.connect(self.toggle_programs)
        self.recent_button = QPushButton('Recent programs')
        self.recent_button.clicked.connect(lambda: self.category.setCurrentText('Recent'))
        left.addWidget(self.recent_button)
        left.addWidget(self.programs)
        left.addWidget(self.search)
        body.addWidget(apps_panel, 3)
        places_panel = QWidget()
        places_panel.setObjectName('placesPanel')
        right = QVBoxLayout(places_panel)
        right.setContentsMargins(4, 38, 3, 2)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        contents = QWidget()
        self.folder_layout = QVBoxLayout(contents)
        self.folder_layout.setContentsMargins(0, 0, 0, 0)
        self.folder_layout.setSpacing(2)
        area.setWidget(contents)
        right.addWidget(area, 1)
        self.refresh_folders()
        self.edit_links_button = QPushButton('Edit folder links…')
        self.edit_links_button.setObjectName('menuControl')
        self.edit_links_button.clicked.connect(self.edit_folders)
        right.addWidget(self.edit_links_button)
        options = QPushButton('Menu options…')
        options.setObjectName('menuControl')
        options_menu = QMenu(options)
        self.remember = options_menu.addAction('Remember recent programs')
        self.remember.setCheckable(True)
        self.remember.setChecked(self.recent.value['enabled'])
        self.remember.toggled.connect(self.set_remember)
        count_menu = options_menu.addMenu('Recent program count')
        self.recent_counts = QActionGroup(self)
        for count in sorted({5, 10, 15, 20, 30, 50, self.recent.value.get('limit', 20)}):
            action = count_menu.addAction(str(count))
            action.setCheckable(True)
            action.setData(count)
            self.recent_counts.addAction(action)
            action.setChecked(count == self.recent.value.get('limit', 20))
        self.recent_counts.triggered.connect(lambda action: self.set_recent_limit(action.data()))
        options_menu.addAction('Clear recent programs', self.clear_recent)
        primary_menu = options_menu.addMenu('Primary session button')
        self.primary_choices = QActionGroup(self)
        for action_id, (label, _) in SESSION_ACTIONS.items():
            action = primary_menu.addAction(label)
            action.setCheckable(True); action.setData(action_id)
            self.primary_choices.addAction(action)
            action.setChecked(action_id == self.primary_action)
            action.setEnabled(desktop_entry('lxqt-'+action_id+'.desktop') is not None)
        self.primary_choices.triggered.connect(lambda action: self.set_primary_action(action.data()))
        options_menu.addSeparator()
        options_menu.addAction('DoroShell settings…', lambda: self.run_desktop('doroshell-settings.desktop'))
        options.setMenu(options_menu)
        right.addWidget(options)

        power = QHBoxLayout(); power.setSpacing(0)
        self.session_button = QPushButton('Shut down…')
        self.session_button.setObjectName('menuControl')
        self.session_button.setProperty('sessionPrimary', True)
        self.session_button.setToolTip('Shut down the computer after confirmation. Cancel is selected by default.')
        self.session_button.setEnabled(desktop_entry('lxqt-shutdown.desktop') is not None)
        self.session_button.clicked.connect(lambda: self.session_action(self.primary_action))
        power.addWidget(self.session_button, 1)
        self.power_arrow = QPushButton('▾')
        self.power_arrow.setObjectName('powerMenuArrow')
        self.power_arrow.setAccessibleName('More session and power options')
        self.power_arrow.setToolTip('Lock, log out, sleep, restart and other session options')
        self.power_arrow.setFixedWidth(34)
        self.power_menu = QMenu(self.power_arrow)
        for action_id in ('lockscreen', 'logout', 'suspend', 'hibernate', 'reboot', 'shutdown'):
            label, icon = SESSION_ACTIONS[action_id]
            action = self.power_menu.addAction(QIcon.fromTheme(icon), label + ('' if action_id == 'lockscreen' else '…'))
            action.setData(action_id)
            action.setEnabled(desktop_entry('lxqt-'+action_id+'.desktop') is not None)
            action.triggered.connect(lambda checked=False, action_id=action_id: self.session_action(action_id))
        self.power_menu.addSeparator()
        self.power_menu.addAction('All session options…', lambda: self.session_action('options'))
        self.power_arrow.setMenu(self.power_menu)
        power.addWidget(self.power_arrow)
        right.addLayout(power)
        body.addWidget(places_panel, 2)
        self.list.setToolTip('Drag pins to reorder. Right-click a program for more options.')
        style = '''
            QWidget { color: #351329; background: transparent; }
            QWidget#glassFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0.78,stop:0 #f8b9df,stop:0.12 #993d71,stop:0.28 #e19dc5,stop:0.46 #86345e,stop:0.49 #b54e83,stop:0.68 #713452,stop:0.86 #b85187,stop:1 #f6b2d5);
                border: 1px solid #965474; border-radius: 15px;
            }
            QWidget#applicationsPanel { background: qlineargradient(x1:0,y1:0,x2:1,y2:0.7,stop:0 #fff9fd,stop:0.44 #fbeaf5,stop:0.47 #fff5fc,stop:0.76 #f8d9ed,stop:1 #fff5fb); border: 1px solid #d9acc7; border-radius: 9px; }
            QLabel#personalStartImage { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ffffff,stop:0.52 #ffe0f2,stop:1 #e7aaca); border: 1px solid #883c69; border-radius: 11px; }
            QWidget#placesPanel { background: qlineargradient(x1:0,y1:0,x2:1,y2:0.8,stop:0 #a24877,stop:0.39 #783251,stop:0.43 #9e4672,stop:0.65 #773353,stop:1 #9d4772); border-radius: 7px; }
            QWidget#placesPanel QLabel, QWidget#placesPanel QPushButton { color: #fff5fb; }
            QLabel#pinnedHeading { font-weight: bold; padding: 4px 7px; }
            QListWidget, QLineEdit, QComboBox { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #fff7fc,stop:1 #f8d7e9); border: 1px solid #b75d91; border-radius: 6px; }
            QWidget#applicationsPanel QListWidget { background: transparent; border: none; }
            QListWidget::item { padding: 4px; border: 1px solid transparent; }
            QListWidget::item:selected { background: #edafd2; border: 1px solid #ad5086; color: #351329; border-radius: 4px; }
            QPushButton { text-align: left; padding: 12px; border: 1px solid transparent; border-radius: 5px; }
            QListWidget::item:hover { background: #f5d1e6; border-radius: 4px; }
            QPushButton#folderLink { padding: 3px 8px; }
            QToolButton#folderBrowse { color: #fff5fb; background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 2px; }
            QToolButton#folderBrowse:hover, QToolButton#folderBrowse:focus { background: #783251; border-color: #dca5c5; }
            QToolButton#folderBrowse::menu-indicator { image: none; }
            QToolButton#folderBrowse:disabled { color: #c8bdc4; }
            QPushButton#menuControl { padding: 5px 8px; }
            QPushButton[sessionPrimary="true"] { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #934369,stop:1 #6f294c); border: 1px solid #dca5c5; border-top-right-radius: 0; border-bottom-right-radius: 0; }
            QPushButton#powerMenuArrow { text-align: center; padding: 5px 2px; background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #934369,stop:1 #6f294c); border: 1px solid #dca5c5; border-top-left-radius: 0; border-bottom-left-radius: 0; }
            QPushButton#powerMenuArrow::menu-indicator { image: none; width: 0px; height: 0px; }
            QWidget#placesPanel QPushButton:disabled { color: #fff5fb; }
            QPushButton:hover, QPushButton:focus { background: #f3c6e0; border: 1px solid #914069; }
            QWidget#placesPanel QPushButton:hover, QWidget#placesPanel QPushButton:focus { background: #642644; border: 1px solid #fff0f8; }
            QPushButton#programsButton { border-top: 1px solid #c48caa; border-radius: 0; font-weight: 600; padding: 6px; }
            QLineEdit { padding: 6px; placeholder-text-color: #795369; } QComboBox { padding: 8px; }
            QComboBox QAbstractItemView { background: #fff7fc; color: #351329; selection-background-color: #edafd2; selection-color: #351329; }
            QComboBox QAbstractItemView::item:selected { background: #edafd2; color: #351329; }
            QMessageBox { background: #fff2f9; color: #351329; }
            QMessageBox QLabel { color: #351329; }
            QMessageBox QPushButton { background: #fff7fc; color: #351329; border: 1px solid #914069; min-width: 70px; }
            QMenu { background: #fff2f9; color: #351329; border: 1px solid #aa4a7c; }
            QMenu::item:selected { background: #eaa6c8; }
            QMenu::item:disabled { color: #684b5c; }
        '''
        composited = has_compositor()
        if composited:
            for color in ('#f8b9df', '#993d71', '#e19dc5', '#86345e', '#b54e83', '#713452', '#b85187', '#f6b2d5'):
                style = style.replace(color, '#d8' + color[1:])
            for color in ('#a24877', '#783251', '#9e4672', '#773353', '#9d4772'):
                style = style.replace(color, '#ed' + color[1:])
        custom_style = self.state.parents[1] / 'doroshell/start-theme.qss'
        glass_style = custom_style.with_name('start-theme-glass.qss')
        if composited and glass_style.is_file():
            custom_style = glass_style
        try:
            style += custom_style.read_text()
        except OSError:
            pass
        self.setStyleSheet(style)
        self.search_action.setIcon(control_icon('edit-find', self.search))
        self.refresh_primary_action()
        for action, action_id in zip(self.power_menu.actions(), ('lockscreen', 'logout', 'suspend', 'hibernate', 'reboot', 'shutdown')):
            action.setIcon(control_icon(SESSION_ACTIONS[action_id][1], self.power_menu))
        self.search.textChanged.connect(self.refresh)
        self.category.currentTextChanged.connect(self.refresh)
        self.search.returnPressed.connect(lambda: self.launch_item(self.list.currentItem()))
        QShortcut(QKeySequence('Print'), self, activated=self.capture_menu)
        QShortcut(QKeySequence('Escape'), self, activated=self.navigate_back)
        QShortcut(QKeySequence('Alt+F1'), self, activated=self.close)
        QShortcut(QKeySequence('Ctrl+F'), self, activated=self.search.setFocus)
        self.results_shortcut = QShortcut(QKeySequence('Down'), self.search, activated=self.focus_results)
        self.results_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.refresh()
        self.search.setFocus()
        self.catalog_timer = QTimer(self)
        self.catalog_timer.setSingleShot(True)
        self.catalog_timer.setInterval(150)
        self.catalog_timer.timeout.connect(self.refresh_catalog)
        self.catalog_changed.connect(self.catalog_timer.start, Qt.ConnectionType.QueuedConnection)
        from wallpaper_glass import maybe_attach
        self.wallpaper_glass = maybe_attach(self)
        monitor = Gio.AppInfoMonitor.get()
        handler = monitor.connect('changed', lambda *_: self.catalog_changed.emit())
        self.destroyed.connect(lambda: monitor.disconnect(handler))

    def refresh_catalog(self):
        if self.list.dragging:
            self.catalog_timer.start()
            return
        selected = self.list.currentItem()
        desktop_id = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        row = self.list.currentRow()
        scroll = self.list.verticalScrollBar().value()
        self.apps = applications()
        self.search_index = AppSearchIndex(self.apps)
        self.by_id = {app.get_id(): app for app in self.apps}
        self.refresh()
        for index in range(self.list.count()):
            if self.list.item(index).data(Qt.ItemDataRole.UserRole) == desktop_id:
                row = index
                break
        self.list.setCurrentRow(min(max(0, row), self.list.count() - 1))
        self.list.verticalScrollBar().setValue(scroll)

    def refresh_folders(self):
        while self.folder_layout.count():
            item = self.folder_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.folder_paths = {}
        for link in self.folder_settings.links:
            if not link['visible']:
                continue
            path = link_path(link)
            self.folder_paths[link['label']] = path
            button = QPushButton(link['label'])
            button.setObjectName('folderLink')
            button.setToolTip(path or 'Folder location is not configured')
            button.clicked.connect(lambda checked=False, p=path: self.open_folder(p))
            row=QWidget();line=QHBoxLayout(row);line.setContentsMargins(0,0,0,0);line.setSpacing(0)
            line.addWidget(button,1)
            browse=QToolButton();browse.setText('›');browse.setObjectName('folderBrowse')
            browse.setAccessibleName('Browse '+link['label']+' contents');browse.setToolTip('Browse folder contents')
            browse.setFixedWidth(22);browse.setEnabled(bool(path));browse.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            if path:browse.setMenu(FolderCascadeMenu(path,self.open_browsed_path,browse))
            line.addWidget(browse);self.folder_layout.addWidget(row)
        for group in SYSTEM_GROUPS:
            entries = [(label, ids) for label, ids in group if label not in self.folder_settings.hidden]
            if entries and self.folder_layout.count():
                divider = QWidget()
                divider.setFixedHeight(1)
                divider.setStyleSheet('background: rgba(255,225,244,80);')
                self.folder_layout.addWidget(divider)
            for label, ids in entries:
                button = QPushButton(label)
                button.setObjectName('folderLink')
                if label == 'Games':
                    button.clicked.connect(self.show_games)
                elif label == 'Printers':
                    button.setToolTip('Open printer management')
                    button.clicked.connect(self.open_printers)
                elif label == 'Computer':
                    button.clicked.connect(lambda: self.open_folder('/'))
                else:
                    desktop = available_entry(ids)
                    button.setEnabled(desktop is not None)
                    button.setToolTip(desktop or f'{label} is not installed')
                    button.clicked.connect(lambda checked=False, entry=desktop: self.run_desktop(entry))
                self.folder_layout.addWidget(button)
        self.folder_layout.addStretch()

    def show_games(self):
        self.search.clear()
        self.category.setCurrentText('Game')

    def refresh_portrait(self):
        art = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)) / 'lxqt-comfort'
        framed = art / 'framed-start-icon.png'
        for path in (Path(self.folder_settings.portrait), framed, art / 'start-icon.png', Path(__file__).with_name('start.svg')):
            if path.is_file():
                size = 88 if path == framed else 76
                try:
                    pixmap = (QPixmap.fromImage(render_crop(load_image(path), self.folder_settings.portrait_crop, size))
                              if str(path) == self.folder_settings.portrait and self.folder_settings.portrait_crop is not None
                              else QIcon(str(path)).pixmap(size, size))
                except ValueError:
                    continue
                if not pixmap.isNull():
                    self.mascot.setStyleSheet('background: transparent; border: none;' if path == framed else '')
                    self.mascot.setPixmap(pixmap)
                    return

    def choose_portrait(self):
        app = QApplication.instance()
        quit_on_close, exit_on_hide = app.quitOnLastWindowClosed(), self.exit_on_hide
        self.exit_on_hide = False
        app.setQuitOnLastWindowClosed(False)
        self.hide()
        try:
            settings = FolderSettings(self.state.with_name('folders.json'))
            path, _ = QFileDialog.getOpenFileName(None, 'Choose Start menu portrait', '', 'Pictures (*.png *.jpg *.jpeg *.webp *.svg)')
            if path:
                dialog = PortraitCropDialog(path, settings.portrait_crop if path == settings.portrait else None)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    settings.save(settings.links, portrait=path, crop=dialog.crop())
                    self.folder_settings = settings
                    self.refresh_portrait()
                dialog.deleteLater()
        except (OSError, ValueError) as error:
            self.error(str(error))
        finally:
            self.show()
            self.mascot.setFocus()
            self.exit_on_hide = exit_on_hide
            app.setQuitOnLastWindowClosed(quit_on_close)

    def edit_folders(self):
        app = QApplication.instance()
        quit_on_close = app.quitOnLastWindowClosed()
        exit_on_hide = self.exit_on_hide
        self.exit_on_hide = False
        app.setQuitOnLastWindowClosed(False)
        self.hide()
        self.folder_settings = FolderSettings(self.state.with_name('folders.json'))
        editor = FolderEditor(self.folder_settings)
        try:
            editor.exec()
            self.refresh_folders()
            self.refresh_portrait()
        finally:
            import shiboken6
            shiboken6.delete(editor)
            self.show()
            self.search.setFocus()
            self.exit_on_hide = exit_on_hide
            app.setQuitOnLastWindowClosed(quit_on_close)

    def capture_menu(self):
        if self.launching:
            return
        helper = Path(__file__).resolve().parents[1] / 'runtime/menu_capture.py'
        if not helper.is_file():
            helper = Path.home() / '.local/share/doroshell/toolkit/runtime/menu_capture.py'
        try:
            process = subprocess.Popen([sys.executable, str(helper), '--notify'], stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
            with process.stdout as reply:
                status = reply.readline()
            if status == b'BUSY\n':
                return
            if status != b'FROZEN\n':
                raise RuntimeError('The desktop could not be frozen.')
        except (OSError, RuntimeError) as error:
            self.error('Capture could not start. Clipboard unchanged: ' + str(error))
            return
        self.launching = True
        self.close()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.exit_on_hide:
            QTimer.singleShot(0, QApplication.instance().quit)

    def toggle_programs(self):
        if self.search.text() or self.category.currentText() != 'Home':
            self.search.clear()
            self.category.setCurrentText('Home')
        else:
            self.category.setCurrentText('All applications')
        self.search.setFocus()

    def navigate_back(self):
        if self.search.text():
            self.search.clear()
            self.search.setFocus()
        elif self.category.currentText() != 'Home':
            self.category.setCurrentText('Home')
            self.search.setFocus()
        else:
            self.close()

    def focus_results(self):
        if self.list.count():
            self.list.setFocus()

    def set_remember(self, enabled):
        try:
            self.recent.save(enabled=enabled)
        except (OSError, ValueError) as error:
            self.remember.blockSignals(True)
            self.remember.setChecked(self.recent.value['enabled'])
            self.remember.blockSignals(False)
            self.error(str(error))
        self.refresh()

    def set_recent_limit(self, limit):
        try:
            self.recent.save(limit=limit)
        except (OSError, ValueError) as error:
            self.error(str(error))
        for action in self.recent_counts.actions():
            action.setChecked(action.data() == self.recent.value.get('limit', 20))
        self.refresh()

    def refresh_primary_action(self):
        label, icon = SESSION_ACTIONS[self.primary_action]
        self.session_button.setText(label + ('' if self.primary_action == 'lockscreen' else '…'))
        self.session_button.setIcon(control_icon(icon, self.session_button))
        self.session_button.setEnabled(desktop_entry('lxqt-'+self.primary_action+'.desktop') is not None)
        self.session_button.setToolTip('Lock the screen.' if self.primary_action == 'lockscreen' else
                                      label + ' after confirmation. Cancel is selected by default.')
        for action in self.primary_choices.actions():
            action.setChecked(action.data() == self.primary_action)
        for action in self.power_menu.actions():
            if action.data() in SESSION_ACTIONS:
                action.setVisible(action.data() != self.primary_action)

    def set_primary_action(self, action_id):
        try:
            if self.primary_error:
                raise ValueError(self.primary_error)
            if action_id not in SESSION_ACTIONS:
                raise ValueError('Unknown session button action')
            self.primary_original = save_json(self.primary_path, {'version': 1, 'action': action_id}, self.primary_original)
            self.primary_action = action_id
        except (OSError, ValueError, TypeError) as error:
            self.error('Session button was not changed: ' + str(error))
        self.refresh_primary_action()

    def clear_recent(self):
        try:
            self.recent.save(clear=True)
        except (OSError, ValueError) as error:
            self.error(str(error))
        self.refresh()

    def refresh(self):
        self.list.clear()
        category = self.category.currentText()
        query = self.search.text().strip()
        back = bool(query) or category != 'Home'
        self.programs.setText('Back' if back else 'All Programs')
        self.programs.setIcon(control_icon('go-previous' if back else 'go-next', self.programs))
        self.programs.setAccessibleName('Back to pinned applications' if back else 'All Programs')
        self.pinned_heading.setVisible(not back)
        self.category.setVisible(category != 'Home')
        self.list.setAccessibleName('Pinned applications' if not back else 'Applications')
        pinned = [self.by_id[x] for x in self.favorites if x in self.by_id]
        recent = [self.by_id[x] for x in self.recent.value['items'] if x in self.by_id] if self.recent.value['enabled'] else []
        self.recent_button.setVisible(not back and bool(recent))
        if query:
            apps = self.apps
        elif category in ('Home', 'Pinned'):
            apps = pinned
        elif category == 'Recent':
            apps = recent
        else:
            apps = self.apps
        if query:
            results = self.search_index.search(query)
            filtered = results[:100]
            notice = ('No matching applications. Try a name, command or keyword.' if not results else
                      f'Showing 100 of {len(results)} matches. Refine your search.' if len(results) > 100 else '')
        else:
            filtered = [a for a in apps if matches(a, '', 'All applications' if category in ('Home', 'Pinned', 'Recent') else category)]
            notice = ('' if filtered else 'No pinned applications. Open All Programs or search.' if category in ('Home', 'Pinned') else
                      'No recent applications.' if category == 'Recent' else 'No applications in this category.')
        self.search_notice.setText(notice)
        self.search_notice.setVisible(bool(notice))
        for app in filtered:
            item = QListWidgetItem(icon_for(app), app.get_display_name())
            item.setData(Qt.ItemDataRole.UserRole, app.get_id())
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
            if not isinstance(app, Gio.DesktopAppInfo) or not app.get_filename():
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            item.setToolTip(app.get_description() or app.get_display_name())
            self.list.addItem(item)
        self.list.setDragEnabled(True)
        self.list.setCurrentRow(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, 'mascot', None):
            self.mascot.move(round(self.width() * 0.80 - self.mascot.width() / 2), 2)
            self.mascot.raise_()
        # An X11 server without a compositor paints transparent popup margins black.
        if QApplication.platformName() == 'xcb':
            outline = QPainterPath()
            outline.setFillRule(Qt.FillRule.WindingFill)
            outline.addRoundedRect(QRectF(self.frame.geometry()), 15, 15)
            if self.mascot:
                portrait = QRectF(self.mascot.geometry())
                if self.mascot.styleSheet():
                    portrait.adjust(2, 2, -2, -2)
                outline.addRoundedRect(portrait, 11, 11)
            self.setMask(QRegion(outline.toFillPolygon().toPolygon(), Qt.FillRule.WindingFill))

    def can_reorder_pins(self):
        return not self.search.text() and self.category.currentText() in ('Home', 'Pinned') and not self.state_error

    def save_favorites(self, updated):
        if self.state_error:
            self.error('Favorites were not changed: ' + self.state_error)
            return False
        try:
            self.state_original = save_json(self.state, updated, self.state_original)
        except (OSError, ValueError) as error:
            self.error(str(error))
            return False
        self.favorites = updated
        self.refresh()
        return True

    def reorder_pin(self, desktop_id, target_id, after=False):
        if not self.can_reorder_pins() or desktop_id not in self.favorites or (target_id is not None and target_id not in self.favorites):
            return False
        if desktop_id == target_id:
            return True
        updated = self.favorites.copy()
        updated.remove(desktop_id)
        position = len(updated) if target_id is None else updated.index(target_id) + int(after)
        updated.insert(position, desktop_id)
        if updated == self.favorites:
            return True
        return self.save_favorites(updated)

    def error(self, message):
        QMessageBox.warning(self, 'DoroShell Start', message)

    def launch_item(self, item):
        if item is None or self.launching or self.list.dragging:
            return
        self.launching = True
        try:
            if not self.by_id[item.data(Qt.ItemDataRole.UserRole)].launch([], None):
                raise RuntimeError('The application could not be launched.')
            try:
                self.recent.save(launched=item.data(Qt.ItemDataRole.UserRole))
            except (OSError, ValueError) as error:
                self.error('Application opened, but recent history was not saved: ' + str(error))
            self.close()
        except (GLib.Error, RuntimeError) as error:
            self.launching = False
            self.error(str(error))

    def session_action(self, action_id):
        if self.launching:
            return
        if action_id not in SESSION_ACTIONS and action_id != 'options':
            self.error('Unknown session action.')
            return
        desktop_id = 'lxqt-leave.desktop' if action_id == 'options' else 'lxqt-' + action_id + '.desktop'
        app = desktop_entry(desktop_id)
        if app is None:
            self.error(f'{desktop_id} is not installed.')
            return
        self.launching = True
        if action_id not in ('lockscreen', 'options'):
            label = SESSION_ACTIONS[action_id][0]
            exit_on_hide = self.exit_on_hide
            self.exit_on_hide = False
            try:
                prompt = {'shutdown': 'Shut down this computer? Save your work first.',
                          'reboot': 'Restart this computer? Save your work first.',
                          'logout': 'Log out of this session? Save your work first.',
                          'suspend': 'Put this computer to sleep?',
                          'hibernate': 'Hibernate this computer?'}[action_id]
                answer = QMessageBox.question(self, label + '?', prompt,
                                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                              QMessageBox.StandardButton.Cancel)
            finally:
                self.exit_on_hide = exit_on_hide
            if answer != QMessageBox.StandardButton.Yes:
                self.launching = False
                self.show()
                self.search.setFocus()
                return
        try:
            # GIO owns the installed LXQt desktop entry; session actions never enter recent-app history.
            if not app.launch([], None):
                raise RuntimeError('The session action could not be started.')
            was_visible = self.isVisible()
            self.close()
            # A modal confirmation can already have hidden the popup while exit-on-hide was suspended.
            if self.exit_on_hide and not was_visible:
                QTimer.singleShot(0, QApplication.instance().quit)
        except (GLib.Error, RuntimeError) as error:
            self.launching = False
            self.show()
            self.search.setFocus()
            self.error(str(error))

    def open_printers(self):
        try:
            # The ConfigurePrinter desktop entry is a per-device helper, not a manager.
            if shutil.which('kcmshell6') and QStandardPaths.locate(
                    QStandardPaths.StandardLocation.GenericDataLocation, 'applications/kcm_printer_manager.desktop'):
                app = Gio.AppInfo.create_from_commandline(
                    'kcmshell6 kcm_printer_manager', 'Printers', Gio.AppInfoCreateFlags.NONE)
                if not app.launch([], None):
                    raise RuntimeError('Printer management could not be started.')
                self.close()
                return
            entry = available_entry(('kcm_printer_manager.desktop', 'system-config-printer.desktop'))
            if entry:
                self.run_desktop(entry)
            else:
                self.error('Printer management is unavailable. Install KDE print-manager with kcmshell6, or system-config-printer.')
        except (GLib.Error, RuntimeError) as error:
            self.error(str(error))

    def run_desktop(self, desktop_id):
        app = desktop_entry(desktop_id)
        if app is None:
            self.error(f'{desktop_id} is not installed.')
            return
        self.by_id[app.get_id()] = app
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, app.get_id())
        self.launch_item(item)

    def open_browsed_path(self, path):
        # Native URI dispatch, never interpret filenames or desktop Exec as shell text.
        try:
            if not Gio.AppInfo.launch_default_for_uri(Path(path).as_uri(), None):
                raise RuntimeError('The selected item could not be opened.')
            self.close()
        except (GLib.Error, RuntimeError, ValueError) as error:
            self.error(str(error))

    def open_folder(self, path):
        if not path or not Path(path).is_dir():
            self.error(f'This folder does not exist yet:\n{path or "Not configured"}')
            return
        try:
            Gio.AppInfo.launch_default_for_uri(Path(path).as_uri(), None)
            self.close()
        except GLib.Error as error:
            self.error(str(error))

    def launch_app_action(self, desktop_id, action_id):
        if self.launching:
            return
        app = self.by_id.get(desktop_id)
        if app is None or action_id not in app.list_actions():
            self.error('This application task is no longer available.')
            return
        self.launching = True
        try:
            # GIO owns desktop-entry interpretation; never execute Exec via a shell.
            # launch_action returns void, not an application-success result.
            app.launch_action(action_id, None)
            self.close()
        except (GLib.Error, RuntimeError) as error:
            self.launching = False
            self.error(str(error))

    def context_menu(self, position):
        item = self.list.itemAt(position)
        if not item:
            return
        desktop_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        action = menu.addAction('Unpin' if desktop_id in self.favorites else 'Pin application')
        up = menu.addAction('Move pin up') if desktop_id in self.favorites else None
        down = menu.addAction('Move pin down') if desktop_id in self.favorites else None
        tasks = {}
        app = self.by_id[desktop_id]
        action_ids = app.list_actions()
        if action_ids:
            menu.addSeparator()
            for action_id in action_ids:
                label = app.get_action_name(action_id) or action_id
                tasks[menu.addAction(label.replace('&', '&&'))] = action_id
        chosen = menu.exec(self.list.mapToGlobal(position))
        if chosen is None:
            return
        if chosen in tasks:
            self.launch_app_action(desktop_id, tasks[chosen])
            return
        if self.state_error:
            self.error('Favorites were not changed: ' + self.state_error)
            return
        updated = self.favorites.copy()
        if chosen == action:
            updated = [x for x in updated if x != desktop_id] if desktop_id in updated else updated + [desktop_id]
        else:
            i = updated.index(desktop_id)
            j = i + (-1 if chosen == up else 1)
            if 0 <= j < len(updated):
                updated[i], updated[j] = updated[j], updated[i]
        self.save_favorites(updated)


class ResidentMenu:
    """Created on first demand only; hidden windows have no polling timer."""
    def __init__(self, app, server):
        self.app, self.server = app, server
        self.version = runtime_signature()
        self.window = None
        self.preferences = None
        server.newConnection.connect(self.accept)
        app.setQuitOnLastWindowClosed(False)

    def snapshot(self):
        root = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        paths = [root / 'lxqt-comfort' / name for name in
                 ('folders.json',)]
        paths += [root / 'doroshell' / name for name in
                  ('start-theme.qss', 'start-theme-glass.qss', 'theme.conf', 'wallpaper-glass.json')]
        art = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)) / 'lxqt-comfort'
        paths += [art / name for name in ('framed-start-icon.png', 'start-icon.png')]
        if self.window and self.window.folder_settings.portrait:
            paths.append(Path(self.window.folder_settings.portrait))
        # Saved bytes distinguish our own edits from external preference changes.
        changed = []
        for path, original in ((self.window.state, self.window.state_original),
                               (self.window.recent.path, self.window.recent.original),
                               (self.window.primary_path, self.window.primary_original)):
            try:
                different = (path.read_bytes() if path.exists() else None) != original
            except OSError:
                different = True
            changed.append((str(path), different))
        return [(str(p), file_stamp(p)) for p in paths] + changed

    def accept(self):
        while self.server.hasPendingConnections():
            client = self.server.nextPendingConnection()
            def read(client=client):
                if not client.canReadLine():
                    if client.bytesAvailable() > 256: client.abort()
                    return
                version = bytes(client.readLine(256)).strip().decode('ascii', errors='replace')
                if version != self.version:
                    self.server.close()
                    client.write(b'RELOAD'); client.flush(); client.disconnectFromServer()
                    self.app.quit()
                    return
                self.toggle()
                client.write(b'OK'); client.flush(); client.disconnectFromServer()
            client.readyRead.connect(read)
            client.disconnected.connect(client.deleteLater)
            read()

    def toggle(self):
        window = self.window
        if QApplication.activeModalWidget() or (window and window.list.dragging):
            return
        controller = window.wallpaper_glass.controller if window and window.wallpaper_glass else None
        if window and (window.isVisible() or (controller and controller.show_pending)):
            if controller:
                controller.show_pending = False
                controller.presentation.stop()
            window.hide()
            return
        if window is None or self.snapshot() != self.preferences:
            if window:
                if controller: controller.stop()
                import shiboken6
                shiboken6.delete(window)
            self.window = window = StartMenu()
            self.preferences = self.snapshot()
        if window.wallpaper_glass:
            managed = window.wallpaper_glass
            managed.reload()
            if managed.last and managed.controller and not managed.controller.enabled:
                managed.controller.configure(**managed.last)
        window.launching = False
        window.search.clear()
        window.category.setCurrentText('Home')
        window.refresh()
        present_menu(window)


def present_menu(window):
    screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
    area = screen.availableGeometry()
    window.resize(min(MENU_SIZE.width(), area.width()), min(MENU_SIZE.height(), area.height()))
    window.move(area.left(), area.bottom() - window.height() + 1)
    controller = window.wallpaper_glass.controller if window.wallpaper_glass else None
    if controller:
        controller.present()
    else:
        window.show()
    window.search.setFocus()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot', type=Path, help='Render this menu to a PNG and exit without launching anything')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    server = None
    resident = None
    if not args.screenshot:
        name = 'lxqt-comfort-' + str(os.getuid())
        server = QLocalServer()
        if not server.listen(name):
            if toggle_existing(): return 0
            QLocalServer.removeServer(name)
            if not server.listen(name):
                raise RuntimeError('Could not create menu toggle socket: ' + server.errorString())
        resident = ResidentMenu(app, server)
        resident.toggle()
    else:
        window = StartMenu()
        window.exit_on_hide = True
        present_menu(window)
        def capture():
            window.grab().save(str(args.screenshot))
            app.quit()
        QTimer.singleShot(250, capture)
    result = app.exec()
    import shiboken6
    shiboken6.delete(resident.window if resident else window)
    return result


if __name__ == '__main__':
    sys.exit(main())
