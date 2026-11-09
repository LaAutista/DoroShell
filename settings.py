#!/usr/bin/env python3
"""Small opt-in settings front end for DoroShell's reversible modules."""
from pathlib import Path
import json
import sys
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QCheckBox, QLineEdit, QFileDialog,
    QPlainTextEdit, QFormLayout, QScrollArea)

ROOT = Path(__file__).resolve().parent
OPTIONS = [
    ('menu', 'Pink Start menu'),
    ('panel', 'Start button and Alt+F1'),
    ('taskbar', 'Taskbar'),
    ('snapping', 'Drag windows to screen edges'),
    ('screenshots', 'Print Screen → clipboard'),
    ('single-desktop', 'One desktop (next login)'),
    ('kate', 'Kate for plain text'),
    ('dolphin', 'Dolphin for folders'),
    ('kate-dark', 'Kate: Breeze Dark'),
    ('dolphin-dark', 'Dolphin: Breeze Dark'),
    ('cursor', 'Animated loading cursor'),
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
        self.setWindowTitle('DoroShell settings')
        self.resize(760, 760)
        self.process = None
        self.queue = []
        layout = QVBoxLayout(self)
        title = QLabel('Make LXQt feel like home')
        title.setStyleSheet('font-size: 24px; font-weight: 600; color: #743b59; background: #f7d6e4; padding: 10px;')
        layout.addWidget(title)
        intro = QLabel('Choose only what you want to change. Restore uses the saved settings from before DoroShell.\n'
                       'Packages are never installed here. One desktop takes effect at your next login.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        area = QScrollArea(); area.setWidgetResizable(True)
        content = QWidget(); form = QFormLayout(content)
        self.choices = {}
        for module, label in OPTIONS:
            choice = QComboBox()
            choice.setAccessibleName(label)
            choice.addItem('Keep unchanged', 'keep')
            if module == 'taskbar':
                choice.addItem('Grouped application icons', 'icons')
                choice.addItem('LXQt icons and labels', 'standard')
            else:
                choice.addItem('Enable / update', 'enable')
            choice.addItem('Restore previous settings', 'restore')
            choice.model().item(choice.count()-1).setEnabled(managed(self.home, module))
            form.addRow(label, choice)
            self.choices[module] = choice
        self.icon = self.file_row(form, 'Personal Start image', 'Images (*.png *.jpg *.webp *.svg)')
        self.gif = self.file_row(form, 'Spinning animation', 'Animations (*.gif *.webp)')
        self.pink = QCheckBox('Pink ordinary pointer (off keeps the normal pointer)')
        form.addRow(self.pink)
        area.setWidget(content); layout.addWidget(area, 2)
        self.live = QCheckBox('Refresh panel / shortcuts now; start edge snapping')
        self.live.setToolTip('Briefly refreshes only the selected LXQt components. No logout or application closure.')
        layout.addWidget(self.live)
        self.output = QPlainTextEdit(); self.output.setReadOnly(True)
        self.output.setAccessibleName('Change preview and results')
        layout.addWidget(self.output, 1)
        row = QHBoxLayout()
        self.preview = QPushButton('Preview changes')
        self.preview.clicked.connect(lambda: self.start(False))
        self.apply = QPushButton('Apply selected changes')
        self.apply.clicked.connect(lambda: self.start(True))
        row.addWidget(self.preview); row.addWidget(self.apply)
        layout.addLayout(row)
        self.setStyleSheet('QComboBox, QLineEdit { min-height: 26px; } QPushButton { padding: 8px; }')

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
            if self.live.isChecked() and apply: cmd.append('--live')
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
