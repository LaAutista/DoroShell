import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
import shiboken6
from PySide6.QtCore import QRect, QPoint, Qt
from PySide6.QtGui import QImage, QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from runtime.menu_capture import FrozenCapture, publish

class MenuCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def image(self):
        image=QImage(400,300,QImage.Format.Format_RGB32);image.fill(QColor('#e9a4cd'));return image

    def select(self,dialog):
        dialog.show();self.app.processEvents()
        QTest.mousePress(dialog,Qt.MouseButton.LeftButton,pos=QPoint(20,80))
        QTest.mouseMove(dialog,QPoint(80,130))
        QTest.mouseRelease(dialog,Qt.MouseButton.LeftButton,pos=QPoint(80,130))

    def test_cancel_and_empty_capture_never_publish(self):
        sink=Mock()
        dialog=FrozenCapture(self.image(),QRect(0,0,400,300))
        dialog.accept();self.assertIsNone(dialog.selected_image())
        self.select(dialog);QTest.keyClick(dialog,Qt.Key.Key_Escape)
        self.assertFalse(publish(dialog.selected_image(),sink))
        sink.clipboard.assert_not_called();shiboken6.delete(dialog)

    def test_confirmed_crop_uses_frozen_pixels_and_scales(self):
        image=self.image();dialog=FrozenCapture(image,QRect(0,0,200,150))
        self.select(dialog)
        # Mutation of the caller's QImage must not alter the frozen snapshot.
        image.fill(QColor('red'))
        QTest.keyClick(dialog,Qt.Key.Key_Return)
        result=dialog.selected_image()
        self.assertIsNotNone(result)
        self.assertEqual(result.width(),round(dialog.selection.width()*image.width()/dialog.width()))
        self.assertEqual(result.pixelColor(0,0),QColor('#e9a4cd'))
        sink=Mock();self.assertTrue(publish(result,sink));sink.clipboard().setImage.assert_called_once()
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'capture.png';self.assertTrue(publish(result,sink,output))
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):publish(result,sink,output)
        shiboken6.delete(dialog)
