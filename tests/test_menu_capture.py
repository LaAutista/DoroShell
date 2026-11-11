import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import shiboken6
from PySide6.QtCore import QRect, QPoint, Qt
from PySide6.QtGui import QImage, QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from runtime.menu_capture import FrozenCapture, publish, compose_screens

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

    def test_fullscreen_enter_and_cancel_never_publishes(self):
        sink=Mock()
        dialog=FrozenCapture(self.image(),QRect(0,0,400,300))
        QTest.keyClick(dialog,Qt.Key.Key_Return);self.assertEqual(dialog.selected_image(),self.image())
        self.select(dialog);QTest.keyClick(dialog,Qt.Key.Key_Escape)
        self.assertFalse(publish(dialog.selected_image(),sink))
        sink.clipboard.assert_not_called();shiboken6.delete(dialog)

    def test_window_picker_uses_topmost_raw_bounds_and_requires_a_hit(self):
        image = self.image()
        rect = QRect(51, 61, 81, 101)
        dialog = FrozenCapture(image, QRect(0, 0, 200, 150), [rect, QRect(-30, 10, 210, 170)])
        dialog.show()
        dialog.actions['Window'].click()
        QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, pos=QPoint(190, 140))
        QTest.keyClick(dialog, Qt.Key.Key_Return)
        self.assertTrue(dialog.isVisible())
        self.assertFalse(dialog.actions['Copy'].isEnabled())
        QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, pos=QPoint(40, 45))
        self.assertEqual(dialog.pixel_rect(), rect)
        self.assertEqual(dialog.rendered_image(), image.copy(rect))
        dialog.actions['Window'].click()
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.assertIsNone(dialog.selected_image())
        shiboken6.delete(dialog)

    def test_confirmed_crop_uses_frozen_pixels_and_scales(self):
        image=self.image();dialog=FrozenCapture(image,QRect(0,0,200,150))
        self.select(dialog)
        # Mutation of the caller's QImage must not alter the frozen snapshot.
        image.fill(QColor('red'))
        QTest.keyClick(dialog,Qt.Key.Key_Return)
        result=dialog.selected_image()
        self.assertIsNotNone(result)
        self.assertEqual(result.size().toTuple(), (121,101))
        self.assertEqual(result.pixelColor(0,0),QColor('#e9a4cd'))
        sink=Mock();self.assertTrue(publish(result,sink));sink.clipboard().setImage.assert_called_once()
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'capture.png';self.assertTrue(publish(result,sink,output))
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):publish(result,sink,output)
        shiboken6.delete(dialog)


    def test_resize_move_annotate_undo_and_export(self):
        dialog=FrozenCapture(self.image(),QRect(0,0,400,300))
        self.select(dialog)
        def drag(start,end):
            QTest.mousePress(dialog,Qt.MouseButton.LeftButton,pos=start)
            QTest.mouseMove(dialog,end)
            QTest.mouseRelease(dialog,Qt.MouseButton.LeftButton,pos=end)
        drag(QPoint(80,130),QPoint(100,150))
        self.assertEqual(dialog.pixel_rect(),QRect(20,80,81,71))
        drag(QPoint(50,100),QPoint(60,110))
        self.assertEqual(dialog.pixel_rect(),QRect(30,90,81,71))
        dialog.set_tool('Redact')
        drag(QPoint(40,100),QPoint(60,120))
        dialog.undo()
        self.assertFalse(dialog.strokes)
        dialog.redo()
        dialog.accept()
        result=dialog.selected_image()
        self.assertEqual(result.size().toTuple(),(81,71))
        self.assertEqual(result.pixelColor(20,20),QColor('black'))
        self.assertEqual(result.pixelColor(0,0),QColor('#e9a4cd'))
        shiboken6.delete(dialog)

    def test_composite_negative_origin_and_mixed_density(self):
        left=QImage(150,120,QImage.Format.Format_RGB32);left.fill(QColor('red'))
        right=QImage(100,80,QImage.Format.Format_RGB32);right.fill(QColor('blue'))
        image,bounds=compose_screens([(QRect(-100,-20,100,80),left),(QRect(0,0,100,80),right)])
        self.assertEqual(bounds,QRect(-100,-20,200,100))
        self.assertEqual(image.size().toTuple(),(300,150))
        self.assertEqual(image.pixelColor(149,60),QColor('red'))
        self.assertEqual(image.pixelColor(150,60),QColor('blue'))
        self.assertEqual(image.pixelColor(151,0),QColor('black'))


    def test_save_exports_final_annotations_and_cancelled_save_stays_open(self):
        dialog=FrozenCapture(self.image(),QRect(0,0,400,300))
        self.select(dialog)
        dialog.set_tool('Pen')
        QTest.mousePress(dialog,Qt.MouseButton.LeftButton,pos=QPoint(30,95))
        QTest.mouseRelease(dialog,Qt.MouseButton.LeftButton,pos=QPoint(55,95))
        with patch('runtime.menu_capture.QFileDialog.getSaveFileName',return_value=('','')):
            dialog.choose_save()
        self.assertIsNone(dialog.selected_image())
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'marked.png'
            with patch('runtime.menu_capture.QFileDialog.getSaveFileName',return_value=(str(path),'PNG')):
                dialog.choose_save()
            result=dialog.selected_image()
            saved=QImage(str(path))
            self.assertEqual(saved.size(),result.size())
            self.assertEqual(saved.pixelColor(20,15),QColor('#f04761'))
            self.assertEqual(saved.pixelColor(20,15),result.pixelColor(20,15))
        shiboken6.delete(dialog)

    def test_strokes_keep_independent_colors_and_widths(self):
        dialog=FrozenCapture(self.image(),QRect(0,0,400,300))
        dialog.show()
        self.app.processEvents()
        dialog.set_tool('Pen')
        for y,width,color in [(100,3,'#1040d0'),(125,11,'#007830')]:
            with patch('runtime.menu_capture.QColorDialog.getColor',return_value=QColor(color)):
                dialog.choose_color()
            dialog.stroke_width.setValue(width)
            QTest.mousePress(dialog,Qt.MouseButton.LeftButton,pos=QPoint(25,y))
            QTest.mouseRelease(dialog,Qt.MouseButton.LeftButton,pos=QPoint(90,y))
        dialog.set_tool('Highlight')
        self.assertEqual(dialog.stroke_width.value(),15)
        dialog.set_tool('Pen')
        self.assertEqual(dialog.stroke_width.value(),11)
        dialog.accept()
        image=dialog.selected_image()
        self.assertEqual(image.pixelColor(50,100),QColor('#1040d0'))
        self.assertEqual(image.pixelColor(50,104),QColor('#e9a4cd'))
        self.assertEqual(image.pixelColor(50,129),QColor('#007830'))
        shiboken6.delete(dialog)

    def test_precision_keys_use_frozen_pixels_with_negative_origin_and_scale(self):
        image = QImage(900, 600, QImage.Format.Format_RGB32)
        image.fill(QColor('navy'))
        dialog = FrozenCapture(image, QRect(-120, -50, 600, 400))
        self.addCleanup(shiboken6.delete, dialog)
        self.select(dialog)
        crop = QRect(dialog.pixel_rect())
        shift, alt = Qt.KeyboardModifier.ShiftModifier, Qt.KeyboardModifier.AltModifier
        def press(key, modifiers=Qt.KeyboardModifier.NoModifier):
            QTest.keyClick(dialog.actions['Copy'], key, modifiers)
        press(Qt.Key.Key_Right)
        crop.translate(23, 0)
        press(Qt.Key.Key_Up, shift)
        crop.translate(0, -1)
        press(Qt.Key.Key_Left, alt | shift)
        crop.adjust(0, 0, -1, 0)
        self.assertEqual(dialog.pixel_rect(), crop)
        for _ in range(40):
            press(Qt.Key.Key_Left)
            press(Qt.Key.Key_Down)
        self.assertEqual(dialog.pixel_rect().size(), crop.size())
        self.assertEqual(dialog.pixel_rect().bottomLeft(), image.rect().bottomLeft())
        press(Qt.Key.Key_Down, alt)
        self.assertEqual(dialog.pixel_rect().height(), crop.height())
        for _ in range(40):
            press(Qt.Key.Key_Up, alt)
            press(Qt.Key.Key_Left, alt)
        self.assertEqual(dialog.pixel_rect(), QRect(0, 600-crop.height(), 1, 1))
        self.assertEqual(dialog.selection, dialog.view_rect(dialog.pixel_rect()))
        for _ in range(45):
            press(Qt.Key.Key_Right, alt)
        self.assertEqual(dialog.pixel_rect().right(), image.rect().right())
        press(Qt.Key.Key_Right)
        self.assertEqual(dialog.pixel_rect().left(), 0)

    def test_drag_lens_paints_frozen_neighbors_and_excludes_editor_chrome(self):
        image = QImage(960, 720, QImage.Format.Format_RGB32)
        image.fill(QColor('navy'))
        point = QPoint(300, 230)
        raw = point * 1.5
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                image.setPixelColor(raw.x()+dx, raw.y()+dy, QColor(120+dx, 140+dy, 60))
        image.setDevicePixelRatio(1.5)
        dialog = FrozenCapture(image, QRect(-20, -10, 640, 480))
        self.addCleanup(shiboken6.delete, dialog)
        dialog.show()
        QTest.mousePress(dialog, Qt.MouseButton.LeftButton, pos=QPoint(90, 85))
        QTest.mouseMove(dialog, point)
        box = dialog.lens_rect()
        self.assertFalse(box.isEmpty())
        self.assertTrue(any(r.contains(box) for r in dialog.screen_bounds))
        self.assertFalse(any(box.contains(p) for p in dialog.handles().values()))
        self.assertFalse(any(box.intersects(bar.geometry()) for bar in (dialog.tools, dialog.controls)))
        preview = dialog.grab().toImage()
        for dx, dy in ((0, 0), (-4, 3), (4, -3)):
            sample = (box.center() + QPoint(dx*7, dy*7)) * preview.devicePixelRatio()
            self.assertEqual(preview.pixelColor(sample), image.pixelColor(raw + QPoint(dx, dy)))
        expected = image.copy(dialog.pixel_rect())
        expected.setDevicePixelRatio(1)
        self.assertEqual(dialog.rendered_image(), expected)
        QTest.mouseRelease(dialog, Qt.MouseButton.LeftButton, pos=point)
        self.assertTrue(dialog.lens_rect().isEmpty())
        dialog.set_tool('Pen')
        QTest.mousePress(dialog, Qt.MouseButton.LeftButton, pos=point)
        self.assertTrue(dialog.lens_rect().isEmpty())
        QTest.mouseRelease(dialog, Qt.MouseButton.LeftButton, pos=point)
