#!/usr/bin/env python3
"""Local animated wallpaper controls. Does not start/stop the desktop or change locking."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time
import base64

DEFAULT = dict(enabled=False, file='', fit='crop', monitor='all', fps=30,
               muted=True, volume=100, paused=False, pause_fullscreen=True, generation=0)


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'doroshell/wallpaper.json'


def validate(values):
    result = dict(DEFAULT, **values)
    if result['fit'] not in ('fit', 'crop', 'stretch') or result['fps'] not in (15, 30, 60):
        raise ValueError('Choose fit/crop/stretch and 15, 30 or 60 repaint fps')
    if type(result['volume']) is not int or not 0 <= result['volume'] <= 100:
        raise ValueError('Volume must be an integer from 0 to 100')
    if not isinstance(result['monitor'], str) or not isinstance(result['generation'], int):
        raise ValueError('Invalid monitor or generation')
    for key in ('enabled', 'muted', 'paused', 'pause_fullscreen'):
        if not isinstance(result[key], bool): raise ValueError('Invalid '+key)
    if not isinstance(result['file'], str): raise ValueError('Invalid media path')
    if result['enabled'] and (not Path(result['file']).is_absolute() or not Path(result['file']).is_file()):
        raise ValueError('Choose an existing local video or GIF')
    return result


def read():
    path = config_path()
    return dict(DEFAULT, **json.loads(path.read_text())) if path.exists() else dict(DEFAULT)


def save(values):
    values = validate(values)
    path = config_path()
    if path.is_symlink(): raise ValueError('Refusing a symlinked wallpaper configuration')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.wallpaper-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(values, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def deployment_status(home=None, runtime=None):
    home = home or Path.home()
    runtime = runtime or Path(os.environ.get('XDG_RUNTIME_DIR', '/nonexistent'))
    active = []
    for path in runtime.glob('doroshell-wallpaper-*.json'):
        try:
            state = json.loads(path.read_text())
            if time.time() - path.stat().st_mtime > 5 or state.get('display') != os.environ.get('DISPLAY', ''):
                continue
            pid = state['pid']
            if type(pid) is not int or pid <= 0: continue
            if Path(f'/proc/{pid}/exe').resolve(strict=True) != Path(state['binary']).resolve(strict=True): continue
            active.append(path.stem + ': ' + ('playing' if state['playing'] else ', '.join(state['reasons'])) +
                          (' — ' + state['error'] if state['error'] else ''))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if active:
        return 'Native wallpaper renderer active\n' + '\n'.join(active)
    manifest = home/'.local/state/doroshell/wallpaper.json'
    if not manifest.exists():
        return 'Native wallpaper desktop not installed. Stage it with setup.py wallpaper before enabling desktop animation.'
    try:
        record = json.loads(manifest.read_text())
        for edit in record['edits']:
            path = home/edit['file']
            if edit['kind'] != 'file' or path.read_bytes() != base64.b64decode(edit['after'], validate=True):
                return 'Wallpaper installation changed. Review and reapply setup before desktop startup.'
        return 'Staged for next desktop startup. Current desktop animation is not active.'
    except (OSError, ValueError, KeyError, TypeError):
        return 'Wallpaper installation is incomplete. Review and reapply setup.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=('gui', 'off', 'pause', 'resume', 'status'), default='gui')
    args = parser.parse_args()
    if args.action != 'gui':
        values = read()
        if args.action == 'off': values['enabled'] = False
        elif args.action in ('pause', 'resume'): values['paused'] = args.action == 'pause'
        if args.action == 'status':
            print(deployment_status())
        else: save(values)
        return
    from PySide6.QtCore import QTimer, QProcess
    from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QLineEdit, QPushButton,
                                    QCheckBox, QComboBox, QFileDialog, QLabel, QMessageBox)
    app = QApplication([]); window = QDialog(); window.setWindowTitle('DoroShell animated wallpaper')
    form = QFormLayout(window); values = read()
    enabled = QCheckBox('Enable animated background'); enabled.setChecked(values['enabled']); form.addRow(enabled)
    path = QLineEdit(values['file']); form.addRow('Local video or GIF', path)
    choose = QPushButton('Choose media…'); form.addRow(choose)
    def browse():
        selected, _ = QFileDialog.getOpenFileName(window, 'Choose local wallpaper', '', 'Media (*.mp4 *.webm *.mkv *.mov *.gif);;All files (*)')
        if selected: path.setText(selected)
    choose.clicked.connect(browse)
    preview = QProcess(window)
    preview_button = QPushButton('Preview in a separate window'); form.addRow(preview_button)
    def preview_media():
        import shutil
        try:
            validate(dict(enabled=True, file=path.text()))
            if not shutil.which('mpv'): raise ValueError('Install mpv to preview media in a separate window')
            if preview.state() != QProcess.ProcessState.NotRunning: return
            preview.start('mpv', ['--no-config', '--mute=yes', '--loop-file=inf', '--title=DoroShell wallpaper preview', '--', path.text()])
        except (OSError,ValueError) as error: QMessageBox.warning(window, 'Wallpaper preview', str(error))
    preview_button.clicked.connect(preview_media)
    app.aboutToQuit.connect(lambda: preview.terminate() if preview.state()!=QProcess.ProcessState.NotRunning else None)
    fit = QComboBox(); fit.addItems(['fit','crop','stretch']); fit.setCurrentText(values['fit']); form.addRow('Scaling',fit)
    monitor = QComboBox(); monitor.addItem('All monitors','all')
    for screen in app.screens(): monitor.addItem(screen.name(),screen.name())
    index = monitor.findData(values['monitor'])
    if index < 0: monitor.addItem(values['monitor']+' (disconnected)',values['monitor']); index=monitor.count()-1
    monitor.setCurrentIndex(index); form.addRow('Monitor',monitor)
    fps = QComboBox(); fps.addItems(['15','30','60']); fps.setCurrentText(str(values['fps'])); form.addRow('Maximum video repaint fps',fps)
    boxes={}
    for key,label in [('muted','Mute sound'),('paused','Pause manually'),('pause_fullscreen','Pause for fullscreen apps on this monitor')]:
        box=QCheckBox(label);box.setChecked(values[key]);boxes[key]=box;form.addRow(box)
    note=QLabel('Requires the optional native desktop build at a normal login.\nLock, screen saver and display-off pauses always remain active.\nLower repaint fps reduces painting; source decoding may still run at its original rate.');note.setWordWrap(True);form.addRow(note)
    status=QLabel();status.setWordWrap(True);form.addRow(status)
    def refresh():
        status.setText(deployment_status())
    timer=QTimer(window);timer.timeout.connect(refresh);timer.start(1000);refresh()
    apply=QPushButton('Apply / retry');form.addRow(apply)
    def commit():
        try:
            current=read();current.update(enabled=enabled.isChecked(),file=path.text(),fit=fit.currentText(),
                monitor=monitor.currentData(),fps=int(fps.currentText()),generation=current['generation']+1,
                **{k:v.isChecked() for k,v in boxes.items()});save(current)
        except (OSError,ValueError) as error: QMessageBox.warning(window,'Wallpaper settings',str(error))
    apply.clicked.connect(commit)
    off=QPushButton('Off — restore static wallpaper now');form.addRow(off)
    off.clicked.connect(lambda: (enabled.setChecked(False),commit()))
    window.resize(560,480);window.show();app.exec()


if __name__ == '__main__': main()
