#!/usr/bin/env python3
"""Select from a frozen menu screenshot; publish only after explicit confirmation."""
import argparse
import sys
from pathlib import Path
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QWidget


class FrozenCapture(QDialog):
    def __init__(self, image, geometry):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        if image.isNull() or geometry.width() <= 0 or geometry.height() <= 0:
            raise ValueError('No completed screen image was supplied')
        self.image = QImage(image)
        self.selection = QRect()
        self.origin = None
        self.setWindowTitle('DoroShell menu capture')
        self.setGeometry(geometry)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.controls = QWidget(self)
        self.controls.setCursor(Qt.CursorShape.ArrowCursor)
        self.controls.setStyleSheet('QWidget { background: #fff7fc; color: #351329; } QPushButton { padding: 8px; }')
        row = QHBoxLayout(self.controls)
        self.help = QLabel('Drag to select • Enter to copy • Escape to cancel')
        row.addWidget(self.help)
        self.copy = QPushButton('Copy'); self.copy.setEnabled(False)
        row.addWidget(self.copy)
        cancel = QPushButton('Cancel'); row.addWidget(cancel)
        self.copy.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        self.controls.adjustSize()
        self.controls.move(max(0, (geometry.width()-self.controls.width())//2), 12)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(self.rect(), self.image)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        if not self.selection.isEmpty():
            painter.setClipRect(self.selection)
            painter.drawImage(self.rect(), self.image)
            painter.setClipping(False)
            painter.setPen(QColor('#5b143d'))
            painter.drawRect(self.selection.adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.selection = QRect()
            self.copy.setEnabled(False)
            self.update()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.selection = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.rect())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.origin is not None:
            self.selection = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.rect())
            self.origin = None
            self.copy.setEnabled(self.selection.width() >= 2 and self.selection.height() >= 2)
            self.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def accept(self):
        if self.copy.isEnabled():
            super().accept()

    def selected_image(self):
        if self.result() != QDialog.DialogCode.Accepted or self.selection.width() < 2 or self.selection.height() < 2:
            return None
        sx, sy = self.image.width()/self.width(), self.image.height()/self.height()
        rect = QRect(round(self.selection.x()*sx), round(self.selection.y()*sy),
                     round(self.selection.width()*sx), round(self.selection.height()*sy))
        result = self.image.copy(rect.intersected(self.image.rect()))
        result.setDevicePixelRatio(1)
        return None if result.isNull() else result


def publish(image, app, output=None):
    if image is None or image.isNull():
        return False
    if output is not None:
        data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, 'PNG'):raise RuntimeError('Could not encode capture')
        with open(output, 'xb') as stream:
            import os
            os.fchmod(stream.fileno(), 0o600)
            stream.write(bytes(data))
    else:
        app.clipboard().setImage(image)
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry',type=int,nargs=4,required=True,metavar=('X','Y','WIDTH','HEIGHT'))
    parser.add_argument('--output',type=Path,help='Save a new PNG instead of changing the clipboard')
    args=parser.parse_args()
    data=sys.stdin.buffer.read(64*1024*1024+1)
    if len(data)>64*1024*1024:raise SystemExit('Capture exceeds the input limit')
    image=QImage.fromData(data,'PNG')
    if image.isNull():raise SystemExit('Incomplete capture; clipboard unchanged')
    app=QApplication(sys.argv[:1]);app.setQuitOnLastWindowClosed(False)
    dialog=FrozenCapture(image,QRect(*args.geometry))
    dialog.exec()
    if not publish(dialog.selected_image(),app,args.output):return 0
    if args.output:return 0
    # Stay alive as the clipboard owner, even without a clipboard manager.
    def release_if_replaced():
        if not app.clipboard().ownsClipboard():app.quit()
    app.clipboard().dataChanged.connect(release_if_replaced)
    QTimer.singleShot(0,release_if_replaced)
    return app.exec()


if __name__=='__main__':
    sys.exit(main())
