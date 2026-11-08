#!/usr/bin/env python3
"""An optional two-column LXQt launcher. Desktop files launch through GIO."""
import argparse
import json
import os
from pathlib import Path
import sys

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib
from PySide6.QtCore import Qt, QStandardPaths, QTimer, QSize
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QCursor
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QComboBox,
    QMessageBox, QMenu)

FOLDERS = [('Home', 'HomeLocation', 'user-home'),
           ('Documents', 'DocumentsLocation', 'folder-documents'),
           ('Downloads', 'DownloadLocation', 'folder-download'),
           ('Pictures', 'PicturesLocation', 'folder-pictures'),
           ('Music', 'MusicLocation', 'folder-music'),
           ('Videos', 'MoviesLocation', 'folder-videos')]
CATEGORIES = ['AudioVideo', 'Development', 'Education', 'Game', 'Graphics',
              'Network', 'Office', 'Science', 'Settings', 'System', 'Utility']


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
        self.resize(680, 570)
        self.apps = applications()
        self.by_id = {app.get_id(): app for app in self.apps}
        self.state = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'lxqt-comfort/favorites.json'
        self.favorites = []
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
        self.category.addItems(['All applications', 'Pinned'] + CATEGORIES)
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
        body.addLayout(left, 3)
        right = QVBoxLayout()
        places = QLabel('YOUR FOLDERS')
        places.setObjectName('section')
        right.addWidget(places)
        self.folder_paths = {}
        for label, location, icon in FOLDERS:
            path = QStandardPaths.writableLocation(getattr(QStandardPaths.StandardLocation, location))
            self.folder_paths[label] = path
            button = QPushButton(QIcon.fromTheme(icon), label)
            button.setToolTip(path or 'Folder location is not configured')
            button.clicked.connect(lambda checked=False, p=path: self.open_folder(p))
            right.addWidget(button)
        right.addStretch()
        settings = QPushButton(QIcon.fromTheme('preferences-system'), 'LXQt settings')
        settings.clicked.connect(lambda: self.run_desktop('lxqt-config.desktop'))
        right.addWidget(settings)
        self.session_button = QPushButton(QIcon.fromTheme('system-shutdown'), 'Log out / power…')
        self.session_button.setToolTip('Open session options. Logging out returns to the login screen. Escape closes this menu.')
        self.session_button.clicked.connect(lambda: self.run_desktop('lxqt-leave.desktop'))
        right.addWidget(self.session_button)
        body.addLayout(right, 2)
        root.addLayout(body)
        self.status = QLabel('Right-click an application to pin it • Tab to move between columns')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.setStyleSheet('''
            QWidget { background: #192938; color: #edf3f8; font-size: 14px; }
            QLabel#heading { font-size: 27px; font-weight: 600; padding-bottom: 10px; }
            QLabel#section { color: #9fb5c8; font-size: 12px; padding: 8px; }
            QListWidget, QLineEdit, QComboBox { background: #101d29; border: 1px solid #40596d; border-radius: 5px; }
            QListWidget::item { padding: 7px; }
            QListWidget::item:selected { background: #326a97; }
            QPushButton { text-align: left; padding: 12px; border: 1px solid transparent; border-radius: 5px; }
            QPushButton:hover, QPushButton:focus { background: #29475e; border: 1px solid #78acd1; }
            QLineEdit { padding: 12px; } QComboBox { padding: 8px; }
            QMenu::item:selected { background: #326a97; }
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

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.exit_on_hide:
            QTimer.singleShot(0, QApplication.instance().quit)

    def focus_results(self):
        self.list.setFocus()

    def refresh(self):
        self.list.clear()
        category = self.category.currentText()
        for app in self.apps:
            if category == 'Pinned' and app.get_id() not in self.favorites:
                continue
            if not matches(app, self.search.text(), 'All applications' if category == 'Pinned' else category):
                continue
            item = QListWidgetItem(icon_for(app), app.get_display_name())
            item.setData(Qt.ItemDataRole.UserRole, app.get_id())
            item.setToolTip(app.get_description() or app.get_display_name())
            self.list.addItem(item)
        self.list.setCurrentRow(0)
        self.status.setText(f'{self.list.count()} applications • Right-click to pin • Tab changes column')

    def error(self, message):
        QMessageBox.warning(self, 'DoroShell Start', message)

    def launch_item(self, item):
        if item is None:
            return
        try:
            if not self.by_id[item.data(Qt.ItemDataRole.UserRole)].launch([], None):
                raise RuntimeError('The application could not be launched.')
            self.close()
        except (GLib.Error, RuntimeError) as error:
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

    def context_menu(self, position):
        item = self.list.itemAt(position)
        if not item:
            return
        desktop_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        action = menu.addAction('Unpin' if desktop_id in self.favorites else 'Pin application')
        if menu.exec(self.list.mapToGlobal(position)) != action:
            return
        if self.state_error:
            self.error('Favorites were not changed because the existing file could not be read: ' + self.state_error)
            return
        updated = [x for x in self.favorites if x != desktop_id] if desktop_id in self.favorites else self.favorites + [desktop_id]
        try:
            self.state.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state.with_suffix('.tmp')
            temporary.write_text(json.dumps(updated, indent=2) + '\n')
            temporary.replace(self.state)
        except OSError as error:
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
