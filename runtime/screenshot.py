#!/usr/bin/env python3
"""ScreenGrab selection UI; publish only a completed capture to the clipboard."""
import os
from pathlib import Path
import sys
import tempfile
from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def capture_config(root):
    out = root / 'captures'
    out.mkdir()
    config = root / 'screengrab/screengrab.conf'
    config.parent.mkdir()
    cfg = QSettings(str(config), QSettings.Format.IniFormat)
    for key, value in {'Base/defDir': str(out), 'Base/defFilename': 'capture',
                       'Base/defImgFormat': 'png', 'Base/insDateTimeInFilename': False,
                       'Base/CopyFilenameToClipboard': 0, 'Base/includeCursor': False,
                       'Display/showNotification': False, 'Display/showTrayIcon': False,
                       'System/AllowCopies': True, 'System/closeInTray': False}.items():
        cfg.setValue(key, value)
    cfg.sync()
    return out


def completed_image(directory, exit_code):
    if exit_code != 0:
        return None
    files = list(directory.glob('*.png'))
    if len(files) != 1:
        return None
    image = QImage(str(files[0]))
    return None if image.isNull() else image


class Capture:
    def __init__(self, app):
        self.app = app
        self.process = None
        self.temp = None

    def start(self):
        # Ignore repeated Print while the current selection owns input.
        if self.process is not None:
            return
        self.temp = tempfile.TemporaryDirectory(prefix='doroshell-capture-')
        self.out = capture_config(Path(self.temp.name))
        self.process = QProcess()
        env = QProcessEnvironment.systemEnvironment()
        env.insert('XDG_CONFIG_HOME', self.temp.name)
        self.process.setProcessEnvironment(env)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.failed)
        self.process.start('screengrab', ['--region', '--no-win'])

    def failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            QMessageBox.warning(None, 'DoroShell screenshot', 'ScreenGrab could not start. Install the screengrab package.')
            self.cleanup()

    def finished(self, code, status):
        if status == QProcess.ExitStatus.NormalExit:
            image = completed_image(self.out, code)
            if image is not None:
                self.app.clipboard().setImage(image)
        else:
            print('DoroShell: ScreenGrab crashed; clipboard unchanged.', file=sys.stderr)
        # Cancel/crash/no file never replaces existing clipboard contents.
        self.cleanup()

    def cleanup(self):
        if self.process:
            self.process.deleteLater()
        self.process = None
        if self.temp:
            self.temp.cleanup()
            self.temp = None


def main():
    if os.environ.get('XDG_SESSION_TYPE', 'x11') != 'x11':
        raise SystemExit('This screenshot integration is validated for X11 only.')
    if '--native-region' not in sys.argv:
        helper = Path(__file__).with_name('menu_capture.py')
        os.execv(sys.executable,[sys.executable,str(helper)])
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    name = 'doroshell-capture-' + str(os.getuid())
    socket = QLocalSocket()
    socket.connectToServer(name)
    if socket.waitForConnected(200):
        socket.disconnectFromServer()
        return 0
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    QLocalServer.removeServer(name)
    if not server.listen(name):
        raise SystemExit(server.errorString())
    capture = Capture(app)
    def request():
        while server.hasPendingConnections():
            client = server.nextPendingConnection()
            client.close()
            client.deleteLater()
        capture.start()
    server.newConnection.connect(request)
    QTimer.singleShot(0, capture.start)
    # Keep one owner alive so image paste works without a clipboard manager.
    return app.exec()

if __name__ == '__main__':
    sys.exit(main())
