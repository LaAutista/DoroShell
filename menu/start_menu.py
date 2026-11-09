#!/usr/bin/env python3
"""An optional two-column LXQt launcher. Desktop files launch through GIO."""
import argparse
import json
import os
from pathlib import Path
import sys
import copy
import tempfile
import time

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib
from PySide6.QtCore import Qt, QStandardPaths, QTimer, QSize
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QCursor
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QComboBox,
    QMessageBox, QMenu, QDialog, QDialogButtonBox, QTableWidget,
    QTableWidgetItem, QFileDialog, QAbstractItemView, QScrollArea)

FOLDERS = [('Home', 'HomeLocation', 'user-home'),
           ('Documents', 'DocumentsLocation', 'folder-documents'),
           ('Downloads', 'DownloadLocation', 'folder-download'),
           ('Pictures', 'PicturesLocation', 'folder-pictures'),
           ('Music', 'MusicLocation', 'folder-music'),
           ('Videos', 'MoviesLocation', 'folder-videos')]
CATEGORIES = ['AudioVideo', 'Development', 'Education', 'Game', 'Graphics',
              'Network', 'Office', 'Science', 'Settings', 'System', 'Utility']


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
        try:
            self.original = path.read_bytes()
            self.links = validate_links(json.loads(self.original))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            self.error = str(error)

    def save(self, links):
        if self.error:
            raise ValueError('Existing folder settings could not be read; they will not be overwritten: ' + self.error)
        data = json.dumps({'version': 1, 'folders': links}, ensure_ascii=False, indent=2).encode() + b'\n'
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
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
    return data


class RecentPrograms:
    def __init__(self, path):
        self.path = path
        self.original = path.read_bytes() if path.exists() else None
        self.value = {'enabled': True, 'items': []}
        self.error = None
        try:
            if self.original is not None:
                value = json.loads(self.original)
                if (not isinstance(value, dict) or type(value.get('enabled')) is not bool
                        or not isinstance(value.get('items'), list)
                        or len(value['items']) > 20 or not all(isinstance(x, str) for x in value['items'])):
                    raise ValueError('Invalid recent-program preferences')
                self.value = value
        except (ValueError, OSError) as error:
            self.error = str(error)

    def save(self, enabled=None, launched=None, clear=False):
        if self.error:
            raise ValueError(self.error)
        value = copy.deepcopy(self.value)
        if enabled is not None:
            value['enabled'] = enabled
        if clear or not value['enabled']:
            value['items'] = []
        if launched and value['enabled']:
            value['items'] = ([launched] + [x for x in value['items'] if x != launched])[:20]
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
        for text, callback in [('Add folder…', self.add_folder), ('Move up', lambda: self.move(-1)),
                               ('Move down', lambda: self.move(1)), ('Remove', self.remove),
                               ('Restore defaults', lambda: self.populate(default_links()))]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
            self.buttons[text] = button
        layout.addLayout(row)
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
            self.settings.save(self.values())
        except (OSError, ValueError) as error:
            self.notice.setText(str(error))
            return
        self.accept()


def applications():
    return sorted([a for a in Gio.AppInfo.get_all() if a.should_show()
                   and a.get_id() != 'lxqt-comfort.desktop'],
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


class StartMenu(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Popup)
        self.setWindowTitle('DoroShell Start')
        self.exit_on_hide = False
        self.launching = False
        self.resize(680, 570)
        self.apps = applications()
        self.by_id = {app.get_id(): app for app in self.apps}
        self.state = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'lxqt-comfort/favorites.json'
        self.favorites = []
        self.state_original = self.state.read_bytes() if self.state.exists() else None
        self.recent = RecentPrograms(self.state.with_name('recent.json'))
        self.state_error = None
        try:
            value = json.loads(self.state.read_text())
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError('Favorites must be a list of desktop IDs')
            self.favorites = value
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            self.state_error = str(error)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        heading = QLabel('Start')
        heading.setObjectName('heading')
        root.addWidget(heading)
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.category = QComboBox()
        self.category.addItems(['Home', 'All applications', 'Pinned', 'Recent'] + CATEGORIES)
        self.category.setAccessibleName('Application category')
        left.addWidget(self.category)
        self.list = QListWidget()
        self.list.setIconSize(QSize(28, 28))
        self.list.setAccessibleName('Applications')
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.context_menu)
        self.list.itemClicked.connect(self.launch_item)
        self.list.itemActivated.connect(self.launch_item)
        left.addWidget(self.list)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search applications…')
        self.search.setAccessibleName('Search applications')
        left.addWidget(self.search)
        programs = QPushButton('All programs / Home')
        programs.clicked.connect(lambda: self.category.setCurrentText('Home' if self.category.currentText() == 'All applications' else 'All applications'))
        left.addWidget(programs)
        body.addLayout(left, 3)
        right = QVBoxLayout()
        places = QLabel('YOUR FOLDERS')
        places.setObjectName('section')
        right.addWidget(places)
        self.folder_settings = FolderSettings(self.state.with_name('folders.json'))
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        contents = QWidget()
        self.folder_layout = QVBoxLayout(contents)
        self.folder_layout.setContentsMargins(0, 0, 0, 0)
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
        options_menu.addAction('Clear recent programs', self.clear_recent)
        options_menu.addSeparator()
        options_menu.addAction('DoroShell settings…', lambda: self.run_desktop('doroshell-settings.desktop'))
        options.setMenu(options_menu)
        right.addWidget(options)
        right.addStretch()
        settings = QPushButton(QIcon.fromTheme('preferences-system'), 'LXQt settings')
        settings.setObjectName('menuControl')
        settings.clicked.connect(lambda: self.run_desktop('lxqt-config.desktop'))
        right.addWidget(settings)
        self.session_button = QPushButton(QIcon.fromTheme('system-shutdown'), 'Log out / power…')
        self.session_button.setObjectName('menuControl')
        self.session_button.setToolTip('Open session options. Logging out returns to the login screen. Escape closes this menu.')
        self.session_button.clicked.connect(lambda: self.run_desktop('lxqt-leave.desktop'))
        right.addWidget(self.session_button)
        body.addLayout(right, 2)
        root.addLayout(body)
        self.status = QLabel('Right-click an application to pin it • Tab to move between columns')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.setStyleSheet('''
            QWidget { background: #f7d6e4; color: #3b1730; font-size: 14px; }
            QLabel#heading { font-size: 27px; font-weight: 600; padding-bottom: 10px; }
            QLabel#section { color: #743b59; font-size: 12px; padding: 8px; }
            QListWidget, QLineEdit, QComboBox { background: #fff4f8; border: 1px solid #bc7898; border-radius: 5px; }
            QListWidget::item { padding: 7px; }
            QListWidget::item:selected { background: #eaa6c8; color: #3b1730; }
            QPushButton { text-align: left; padding: 12px; border: 1px solid transparent; border-radius: 5px; }
            QPushButton#folderLink { padding: 8px; }
            QPushButton#menuControl { padding: 5px 8px; }
            QPushButton:hover, QPushButton:focus { background: #efb5d0; border: 1px solid #8f355f; }
            QLineEdit { padding: 12px; } QComboBox { padding: 8px; }
            QMenu::item:selected { background: #eaa6c8; }
        ''')
        self.search.textChanged.connect(self.refresh)
        self.category.currentTextChanged.connect(self.refresh)
        self.search.returnPressed.connect(lambda: self.launch_item(self.list.currentItem()))
        QShortcut(QKeySequence('Escape'), self, activated=self.close)
        QShortcut(QKeySequence('Alt+F1'), self, activated=self.close)
        QShortcut(QKeySequence('Ctrl+F'), self, activated=self.search.setFocus)
        QShortcut(QKeySequence('Down'), self.search, activated=self.focus_results)
        self.refresh()
        self.search.setFocus()

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
            button = QPushButton(QIcon.fromTheme(link.get('icon', 'folder')), link['label'])
            button.setObjectName('folderLink')
            button.setToolTip(path or 'Folder location is not configured')
            button.clicked.connect(lambda checked=False, p=path: self.open_folder(p))
            self.folder_layout.addWidget(button)
        self.folder_layout.addStretch()

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
        finally:
            import shiboken6
            shiboken6.delete(editor)
            self.show()
            self.search.setFocus()
            self.exit_on_hide = exit_on_hide
            app.setQuitOnLastWindowClosed(quit_on_close)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.exit_on_hide:
            QTimer.singleShot(0, QApplication.instance().quit)

    def focus_results(self):
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

    def clear_recent(self):
        try:
            self.recent.save(clear=True)
        except (OSError, ValueError) as error:
            self.error(str(error))
        self.refresh()

    def refresh(self):
        self.list.clear()
        category = self.category.currentText()
        query = self.search.text()
        pinned = [self.by_id[x] for x in self.favorites if x in self.by_id]
        recent = [self.by_id[x] for x in self.recent.value['items'] if x in self.by_id] if self.recent.value['enabled'] else []
        if query:
            apps = self.apps
        elif category == 'Home':
            apps = pinned + [x for x in recent if x.get_id() not in self.favorites]
            if not apps:
                apps = self.apps[:12]
        elif category == 'Pinned':
            apps = pinned
        elif category == 'Recent':
            apps = recent
        else:
            apps = self.apps
        filtered = [a for a in apps if matches(a, query, 'All applications' if query or category in ('Home', 'Pinned', 'Recent') else category)]
        if query:
            filtered.sort(key=lambda a: (not a.get_display_name().casefold().startswith(query.casefold()), a.get_display_name().casefold()))
        for app in filtered:
            label = app.get_display_name()
            if category == 'Home' and not query and app.get_id() in self.favorites:
                label = '★ ' + label
            item = QListWidgetItem(icon_for(app), label)
            item.setData(Qt.ItemDataRole.UserRole, app.get_id())
            item.setToolTip(app.get_description() or app.get_display_name())
            self.list.addItem(item)
        self.list.setCurrentRow(0)
        self.status.setText('Pinned first, then recent • Choose All applications to browse' if category == 'Home' and not query else f'{self.list.count()} applications • Right-click to pin or reorder')

    def error(self, message):
        QMessageBox.warning(self, 'DoroShell Start', message)

    def launch_item(self, item):
        if item is None or self.launching:
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

    def run_desktop(self, desktop_id):
        app = Gio.DesktopAppInfo.new(desktop_id)
        if app is None:
            self.error(f'{desktop_id} is not installed.')
            return
        self.by_id[app.get_id()] = app
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, app.get_id())
        self.launch_item(item)

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
        try:
            self.state_original = save_json(self.state, updated, self.state_original)
        except (OSError, ValueError) as error:
            self.error(str(error))
            return
        self.favorites = updated
        self.refresh()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot', type=Path, help='Render this menu to a PNG and exit without launching anything')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    server = None
    if not args.screenshot:
        name = 'lxqt-comfort-' + str(os.getuid())
        socket = QLocalSocket()
        socket.connectToServer(name)
        if socket.waitForConnected(150):
            socket.disconnectFromServer()
            return 0
        server = QLocalServer()
        QLocalServer.removeServer(name)
        if not server.listen(name):
            raise RuntimeError('Could not create menu toggle socket: ' + server.errorString())
        server.newConnection.connect(app.quit)
    window = StartMenu()
    window.exit_on_hide = True
    screen = QApplication.screenAt(QCursor.pos()) or app.primaryScreen()
    area = screen.availableGeometry()
    window.resize(min(680, area.width()), min(570, area.height()))
    window.move(area.left(), area.bottom() - window.height() + 1)
    window.show()
    if args.screenshot:
        def capture():
            window.grab().save(str(args.screenshot))
            app.quit()
        QTimer.singleShot(250, capture)
    result = app.exec()
    # Destroy Qt callbacks before Python tears down imported modules.
    import shiboken6
    shiboken6.delete(window)
    return result


if __name__ == '__main__':
    sys.exit(main())
