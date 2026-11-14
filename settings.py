#!/usr/bin/env python3
"""Small opt-in settings front end for DoroShell's reversible modules."""
from pathlib import Path
import json
import sys
from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QCheckBox, QLineEdit, QFileDialog,
    QPlainTextEdit, QFormLayout, QScrollArea, QStyledItemDelegate, QListWidget, QStackedWidget, QToolButton, QStyle)

ROOT = Path(__file__).resolve().parent
OPTIONS = [
    ('clipboard', 'DoroClipboard history button'),
    ('menu', 'Start menu'),
    ('theme', 'Coordinated Doro theme'),
    ('wallpaper-glass', 'Wallpaper glass (no compositor)'),
    ('panel', 'Start button and Alt+F1'),
    ('native-panel', 'Enable at next login'),
    ('taskbar-size', 'Taskbar icon and button size'),
    ('taskbar', 'LXQt taskbar style'),
    ('taskbar-drag', 'DockBarX icon dragging'),
    ('snapping', 'Drag windows to screen edges'),
    ('screenshots', 'Print Screen capture overlay'),
    ('single-desktop', 'One desktop (next login)'),
    ('kate', 'Kate for plain text'),
    ('dolphin', 'Dolphin for folders'),
    ('kate-dark', 'Kate: Breeze Dark'),
    ('dolphin-dark', 'Dolphin: Breeze Dark'),
    ('cursor', 'Animated loading cursor'),
]

PAGES = [
    ('Start Menu', ('menu', 'panel')),
    ('Taskbar & Windows', ('native-panel', 'clipboard', 'taskbar-size', 'snapping', 'single-desktop', 'taskbar', 'taskbar-drag')),
    ('Screenshots', ('screenshots',)),
    ('Apps & Themes', ('theme', 'wallpaper-glass', 'kate', 'dolphin', 'kate-dark', 'dolphin-dark')),
    ('Cursor', ('cursor',)),
]


def managed(home, module):
    if module in ('menu', 'panel', 'cursor'):
        name = {'menu':'menu-install','panel':'menu-integration','cursor':'cursor-install'}[module]
        path = home/'.local/state/lxqt-comfort'/f'{name}.json'
    else:
        path = home/'.local/state/doroshell'/f'{module}.json'
    return path.exists()


class Settings(QWidget):
    def __init__(self, home=None):
        super().__init__()
        self.home = home or Path.home()
        self.setWindowTitle('DoroShell Settings')
        self.setObjectName('doroShellSettings')
        self.resize(880, 650)
        self.process = None
        self.queue = []
        layout = QVBoxLayout(self)
        title = QLabel('DoroShell Settings')
        title_font = title.font()
        if title_font.pointSizeF() > 0: title_font.setPointSizeF(title_font.pointSizeF() * 1.6)
        elif title_font.pixelSize() > 0: title_font.setPixelSize(round(title_font.pixelSize() * 1.6))
        title.setFont(title_font)
        title.setStyleSheet(' font-weight: 600; color: #743b59; background: #f7d6e4; padding: 10px;')
        layout.addWidget(title)
        intro = QLabel('Choose a change to preview or apply. Restore uses your saved settings.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        body = QHBoxLayout()
        self.categories = QListWidget()
        self.categories.setAccessibleName('Settings categories')
        self.categories.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.categories.setMinimumWidth(self.categories.fontMetrics().horizontalAdvance('Taskbar & Windows') + 30
                                        + self.categories.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent))
        self.pages = QStackedWidget()
        self.pages.setAccessibleName('Settings page')
        body.addWidget(self.categories, 1); body.addWidget(self.pages, 3)
        layout.addLayout(body, 3)
        self.choices = {}
        forms = {}
        for title, modules in PAGES:
            self.categories.addItem(title)
            area = QScrollArea(); area.setWidgetResizable(True)
            content = QWidget(); form = QFormLayout(content)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            heading = QLabel(title); heading.setStyleSheet('font-weight: 600; padding: 8px 0;')
            form.addRow(heading)
            for module in modules:
                group = {'native-panel':'DoroShell taskbar', 'snapping':'Windows'}.get(module)
                if group:
                    section = QLabel(group)
                    section.setStyleSheet('font-weight: 600; color: #743b59;')
                    form.addRow(section)
                if module=='taskbar':
                    self.other_taskbars = QToolButton()
                    self.other_taskbars.setText('Other taskbars')
                    self.other_taskbars.setToolTip('Stock LXQt taskbar and DockBarX options')
                    self.other_taskbars.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                    self.other_taskbars.setArrowType(Qt.ArrowType.RightArrow)
                    self.other_taskbars.setCheckable(True)
                    form.addRow(self.other_taskbars)
                    alternative = QWidget()
                    form.addRow(alternative)
                    form = QFormLayout(alternative)
                    form.setContentsMargins(8,0,0,0)
                    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
                    alternative.hide()
                    self.other_taskbars.toggled.connect(alternative.setVisible)
                    self.other_taskbars.toggled.connect(lambda open_: self.other_taskbars.setArrowType(
                        Qt.ArrowType.DownArrow if open_ else Qt.ArrowType.RightArrow))
                    self.note(form,'Use LXQt taskbar style for the stock taskbar. Icon dragging applies to the DockBarX applet.')
                if module=='screenshots':
                    self.note(form,'Print freezes the desktop, including Start. Drag an area, choose Window and click an app, or press Enter for the full desktop. Annotate, then choose Copy or Save. Open in ScreenGrab sends the finished image to the native window when the importer is installed.')
                label = dict(OPTIONS)[module]
                choice = QComboBox()
                choice.setItemDelegate(QStyledItemDelegate(choice))
                choice.setAccessibleName(label)
                choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                choice.setMinimumContentsLength(12)
                choice.addItem('Keep unchanged', 'keep')
                if module == 'theme':
                    for key,theme_label in [('windows','Windows Doro'),('polar','Polar Doro'),('heretic','Heretic Doro'),('spring','Spring Doro')]:
                        choice.addItem(theme_label,key)
                    choice.setToolTip('Styles Start, the theme-capable DoroShell panel, LXQt, Dolphin, Kate and Openbox at normal startup. GTK apps are unaffected. Restore overlapping app themes in reverse order.')
                elif module == 'wallpaper-glass':
                    choice.addItem('Enable wallpaper glass', 'enable')
                    choice.setToolTip('Frozen blur/tint from the standard PCManFM-Qt wallpaper, not moving-window transparency. Start updates on its next open; taskbar needs a glass-capable DoroShell panel. Animated wallpaper stays frozen. Restore returns the previous setting.')
                elif module == 'clipboard':
                    choice.addItem('Enable at next login', 'enable')
                    choice.setToolTip('A visible history button beside the hidden-icons arrow. Up to 50 text/image copies in memory only; no PRIMARY selection or disk history. Pause before copying secrets. Does not replace another running clipboard manager.')
                elif module == 'taskbar-size':
                    for name, pixels in [('Small', 20), ('Medium', 28), ('Large', 36)]:
                        choice.addItem(f'{name} ({pixels} px icons)', name.lower())
                    choice.setToolTip('Applies to the DoroShell panel at its next startup.')
                elif module == 'taskbar':
                    choice.addItem('Grouped application icons', 'icons')
                    choice.addItem('LXQt icons and labels', 'standard')
                else:
                    choice.addItem('Enable / update', 'enable')
                choice.addItem('Restore previous panel' if module == 'native-panel' else 'Restore previous settings', 'restore')
                if module == 'native-panel':
                    choice.setItemData(choice.count()-1,'Backs up edited panel settings before restoring the previous panel.',Qt.ItemDataRole.ToolTipRole)
                choice.model().item(choice.count()-1).setEnabled(managed(self.home, module))
                caption = QLabel(label); caption.setWordWrap(True); caption.setBuddy(choice)
                form.addRow(caption, choice)
                self.choices[module] = choice
                if module=='taskbar-size':
                    self.panel_plan = self.file_row(form,'Prepared taskbar plan','Panel plan (plan.json)')
                    self.panel_plan.setPlaceholderText('Default prepared profile')
                if module=='single-desktop':
                    self.live = QCheckBox('Start edge snapping now')
                    self.live.setToolTip('Start the snapping helper in this session when applying the snapping module.')
                    form.addRow(self.live)
            area.setWidget(content); self.pages.addWidget(area); forms[title] = content.layout()
        self.icon = self.file_row(forms['Start Menu'], 'Personal Start image', 'Images (*.png *.jpg *.webp *.svg)')
        self.note(forms['Start Menu'],'In Start, right-click an app to pin it and drag pins to reorder them. Menu options controls recent programs, history and the primary session button. Edit folder links changes the shortcuts in the right column.')
        self.start_link = QPushButton('Open Start menu')
        self.start_link.clicked.connect(self.open_start)
        self.start_link.setEnabled(self.start_entry().is_file())
        forms['Start Menu'].addRow(self.start_link)
        self.portable = QPushButton('Portable Start preferences…')
        self.portable.clicked.connect(self.open_portable)
        forms['Start Menu'].addRow(self.portable)
        self.wallpaper_controls = QPushButton('Wallpaper controls…')
        self.wallpaper_controls.setToolTip('Prepare local media choices; does not enable or replace the running desktop.')
        self.wallpaper_controls.clicked.connect(self.open_wallpaper)
        forms['Apps & Themes'].addRow(self.wallpaper_controls)
        self.gif = self.file_row(forms['Cursor'], 'Spinning animation', 'Animations (*.gif *.webp *.apng *.png)')
        self.pink = QCheckBox('Use pink ordinary pointer')
        self.pink.setToolTip('Off keeps your normal inherited pointer; only the loading cursor changes.')
        forms['Cursor'].addRow(self.pink)
        self.categories.addItem('Mouse & Touchpad')
        input_area = QScrollArea(); input_area.setWidgetResizable(True)
        try:
            from input_preferences import page as input_page
            input_area.setWidget(input_page(self.home))
        except ImportError:
            missing = QLabel('Input preferences component is not installed. Update the toolkit before using these controls.')
            missing.setWordWrap(True); input_area.setWidget(missing)
        self.pages.addWidget(input_area)
        self.categories.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.categories.setCurrentRow(0)
        self.selection_summary = QLabel('No changes selected')
        self.selection_summary.setAccessibleName('Selected changes across all pages')
        layout.addWidget(self.selection_summary)
        for choice in self.choices.values():
            choice.currentIndexChanged.connect(self.update_summary)
        self.output = QPlainTextEdit(); self.output.setReadOnly(True)
        self.output.setAccessibleName('Change preview and results')
        self.output.hide()
        self.output.textChanged.connect(lambda: self.output.setVisible(bool(self.output.toPlainText())))
        layout.addWidget(self.output, 1)
        row = QHBoxLayout()
        self.preview = QPushButton('Preview changes')
        self.preview.clicked.connect(lambda: self.start(False))
        self.apply = QPushButton('Apply selected changes')
        self.apply.clicked.connect(lambda: self.start(True))
        row.addWidget(self.preview); row.addWidget(self.apply)
        layout.addLayout(row)
        self.setStyleSheet('''
            QWidget { color: #351329; }
            QWidget#doroShellSettings { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #fff1fa,stop:1 #e7a3c9); }
            QScrollArea, QScrollArea > QWidget > QWidget { background: #fff4fa; border: 0; }
            QComboBox, QLineEdit { min-height: 26px; background: #fff9fc; border: 1px solid #b66a93; border-radius: 5px; padding: 3px; }
            QComboBox QAbstractItemView { background: #fff9fc; color: #351329; selection-background-color: #edafd2; selection-color: #351329; }
            QComboBox QAbstractItemView::item:disabled { color: #684b5c; }
            QComboBox QAbstractItemView::item:selected { background: #edafd2; color: #351329; }
            QLineEdit { placeholder-text-color: #795369; }
            QListWidget { background: #fff4fa; border: 1px solid #b66a93; border-radius: 5px; }
            QListWidget::item { padding: 10px 6px; color: #351329; }
            QListWidget::item:selected { background: #edafd2; color: #351329; }
            QListWidget::item:hover { background: #f3c6e0; color: #351329; }
            QPlainTextEdit { background: #fff9fc; border: 1px solid #b66a93; border-radius: 5px; }
            QPushButton { padding: 8px; background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffebf7,stop:0.49 #f3b6d7,stop:0.5 #e899c2,stop:1 #f5c4df); border: 1px solid #a75b83; border-radius: 5px; }
            QPushButton:hover, QPushButton:focus { border: 1px solid #672044; background: #ffd9ee; }
            QPushButton:disabled { color: #684b5c; background: #eadce4; }
        ''')

    def open_portable(self):
        from portable_settings import open_dialog
        open_dialog(self, self.home)

    @staticmethod
    def note(form,text):
        label = QLabel(text)
        label.setWordWrap(True)
        form.addRow(label)

    def start_entry(self):
        return self.home/'.local/share/applications/lxqt-comfort.desktop'

    def open_start(self):
        from gi.repository import Gio, GLib
        try:
            entry = Gio.DesktopAppInfo.new_from_filename(str(self.start_entry()))
            if entry is None or not entry.launch([],None):
                raise RuntimeError('The Start menu launcher is unavailable.')
        except (GLib.Error, RuntimeError) as error:
            self.output.setPlainText(str(error))

    def open_wallpaper(self):
        process = QProcess()
        from PySide6.QtCore import QProcessEnvironment
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert('XDG_CONFIG_HOME', str(self.home/'.config'))
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        process.setArguments([str(ROOT/'wallpaper/control.py')])
        if not process.startDetached():
            self.output.setPlainText('Could not open animated wallpaper controls.')

    def update_summary(self):
        count = sum(choice.currentData() != 'keep' for choice in self.choices.values())
        self.selection_summary.setText('No changes selected' if not count else f'{count} selected change' + ('s' if count != 1 else '') + ' across all pages')

    def file_row(self, form, label, pattern):
        container = QWidget(); row = QHBoxLayout(container); row.setContentsMargins(0,0,0,0)
        field = QLineEdit(); field.setAccessibleName(label)
        button = QPushButton('Browse…')
        def choose():
            path, _ = QFileDialog.getOpenFileName(self, label, '', pattern)
            if path: field.setText(path)
        button.clicked.connect(choose)
        row.addWidget(field); row.addWidget(button)
        form.addRow(label, container)
        return field

    def commands(self, apply):
        commands = []
        selections = [(module, self.choices[module].currentData()) for module, _ in OPTIONS]
        # Restore integrations before removing their menu launcher.
        selections.sort(key=lambda pair: pair[0]=='menu' and pair[1]=='restore')
        for module, action in selections:
            if action == 'keep': continue
            if action == 'restore' and not apply:
                self.output.appendPlainText(module+': restore saved settings (conflicts checked on Apply)')
                continue
            cmd = [str(ROOT/'setup.py'), module, '--home', str(self.home)]
            if action == 'restore': cmd.append('--rollback')
            elif apply: cmd.append('--apply')
            if self.live.isChecked() and apply and module=='snapping': cmd.append('--live')
            if module=='native-panel' and action=='restore': cmd.append('--keep-panel-edits')
            if module=='native-panel' and action!='restore' and self.panel_plan.text().strip():
                plan = Path(self.panel_plan.text().strip())
                if plan.name != 'plan.json' or not plan.is_file():
                    raise ValueError('Choose the plan.json created by panel/profile.py prepare.')
                cmd += ['--prepared', str(plan.parent)]
            if module=='theme' and action!='restore': cmd += ['--theme',action]
            if module=='taskbar-size' and action!='restore': cmd += ['--taskbar-size', action]
            if module=='taskbar' and action in ('icons','standard'):
                cmd += ['--taskbar-style', action]
            if module=='cursor' and action!='restore':
                if not self.gif.text().strip(): raise ValueError('Choose your animated GIF before enabling the loading cursor.')
                cmd += ['--gif', self.gif.text().strip()]
                if self.pink.isChecked(): cmd.append('--pink-pointer')
            if module=='menu' and action!='restore' and self.icon.text().strip():
                cmd += ['--icon', self.icon.text().strip()]
            commands.append(cmd)
        return commands

    def start(self, apply):
        if self.process is not None: return
        self.output.clear()
        try: self.queue = self.commands(apply)
        except ValueError as error:
            self.output.setPlainText(str(error)); return
        if not self.queue:
            if not self.output.toPlainText(): self.output.setPlainText('No changes selected.')
            return
        self.preview.setEnabled(False); self.apply.setEnabled(False)
        self.next_command()

    def next_command(self):
        if not self.queue:
            self.process = None
            self.start_link.setEnabled(self.start_entry().is_file())
            self.preview.setEnabled(True); self.apply.setEnabled(True)
            for module, choice in self.choices.items():
                choice.model().item(choice.count()-1).setEnabled(managed(self.home, module))
            return
        command = self.queue.pop(0)
        self.output.appendPlainText('\n'+command[1]+':')
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.failed)
        self.process.start(sys.executable, command)

    def read_output(self):
        self.output.appendPlainText(bytes(self.process.readAllStandardOutput()).decode(errors='replace').rstrip())

    def failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.output.appendPlainText(self.process.errorString())
            self.finished(1, QProcess.ExitStatus.CrashExit)

    def finished(self, code, status):
        self.read_output()
        self.process.deleteLater()
        self.process = None
        if code or status != QProcess.ExitStatus.NormalExit:
            self.output.appendPlainText('Stopped. Earlier successful modules remain applied; each can be restored separately.')
            self.queue.clear()
        self.next_command()

    def closeEvent(self, event):
        if self.process is not None:
            self.output.appendPlainText('Wait for the current operation to finish before closing settings.')
            event.ignore()
        else: event.accept()


def main(home=None):
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = Settings(home); window.show()
    return app.exec()


if __name__=='__main__':
    sys.exit(main())
