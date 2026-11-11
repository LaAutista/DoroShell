import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import shiboken6
from PySide6.QtCore import QRect, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QImage, QColor, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLineEdit, QFontComboBox, QCheckBox, QDoubleSpinBox, QSpinBox
from runtime.menu_capture import FrozenCapture, publish, compose_screens, monitor_geometry

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

    def test_edit_marks_hit_order_hollow_shapes_and_history(self):
        dialog = FrozenCapture(self.image(), QRect(0, 0, 400, 300))
        self.addCleanup(shiboken6.delete, dialog)
        self.select(dialog)
        crop = QRect(dialog.pixel_rect())
        def drag(start, end):
            QTest.mousePress(dialog, Qt.MouseButton.LeftButton, pos=start)
            QTest.mouseMove(dialog, end)
            QTest.mouseRelease(dialog, Qt.MouseButton.LeftButton, pos=end)
        a, b = QPoint(30, 90), QPoint(70, 125)
        for tool in ('Redact', 'Rectangle'):
            dialog.set_tool(tool)
            drag(a, b)
        dialog.set_tool('Edit marks')
        def pick(p):
            QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, pos=p)
        pick(a)
        self.assertEqual(dialog.selected_mark, 1)
        pick(QPoint(50, 104))
        self.assertEqual(dialog.selected_mark, 0)
        pick(QPoint(95, 104))
        self.assertIsNone(dialog.selected_mark)
        old = dialog.rendered_image()
        drag(QPoint(50, 104), QPoint(85, 104))
        moved = dialog.rendered_image()
        self.assertNotEqual(moved, old)
        self.assertEqual(dialog.pixel_rect(), crop)
        QTest.keyClick(dialog, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(dialog.pixel_rect(), crop)
        QTest.keyClick(dialog, Qt.Key.Key_Delete)
        deleted = dialog.rendered_image()
        self.assertNotEqual(deleted, moved)
        for operation, expected in ((dialog.undo, moved), (dialog.undo, old),
                                    (dialog.redo, moved), (dialog.redo, deleted)):
            operation()
            self.assertEqual(dialog.rendered_image(), expected)
        dialog.undo()
        pick(QPoint(75, 108))
        self.assertTrue(dialog.redo_stack)  # Selection alone keeps the redo branch.
        drag(QPoint(75, 108), QPoint(64, 108))
        self.assertFalse(dialog.redo_stack)

    def test_text_edits_preserve_one_pixel_crop_and_style(self):
        dialog = FrozenCapture(self.image(), QRect(-30, -20, 200, 150))
        self.addCleanup(shiboken6.delete, dialog)
        dialog.raw_selection = QRect(100, 100, 1, 1)
        dialog.selection = dialog.view_rect(dialog.raw_selection)
        dialog.set_tool('Text')
        anchor = QPoint(46, 55)
        def text_input(answer):
            value, accepted = answer
            result = (value, dialog.font(), dialog.colors['ink']) if accepted else None
            return patch('runtime.menu_capture.text_editor', return_value=result)
        with text_input(('old', True)):
            QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, pos=anchor)
        original = dialog.strokes[0]
        dialog.set_tool('Edit marks')
        hit = dialog.mark_bounds(original).center()
        QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, pos=hit)
        with text_input(('ignored', False)):
            QTest.keyClick(dialog, Qt.Key.Key_F2)
        self.assertEqual(len(dialog.undo_stack), 1)
        with text_input(('replacement', True)):
            QTest.mouseDClick(dialog, Qt.MouseButton.LeftButton, pos=hit)
        changed = dialog.strokes[0]
        self.assertEqual(changed, (*original[:2], 'replacement', *original[3:]))
        self.assertEqual(dialog.pixel_rect(), QRect(100, 100, 1, 1))
        dialog.undo()
        self.assertEqual(dialog.strokes, [original])
        dialog.redo()
        self.assertEqual(dialog.strokes, [changed])

    def test_mark_picker_matches_linework_and_filled_regions(self):
        dialog = FrozenCapture(self.image(), QRect(0, 0, 400, 300))
        self.addCleanup(shiboken6.delete, dialog)
        # All checks are in view coordinates, including the tip of an arrowhead.
        for tool, points, hit, miss in (
            ('Pen', [(40, 50), (80, 90), (120, 50)], (60, 70), (80, 55)),
            ('Highlight', [(40, 50), (120, 50)], (80, 56), (80, 80)),
            ('Arrow', [(40, 50), (120, 50)], (108, 56), (80, 70)),
            ('Ellipse', [(40, 50), (120, 90)], (80, 50), (80, 70)),
            ('Rectangle', [(40, 50), (120, 90)], (80, 90), (80, 70)),
            ('Redact', [(40, 50), (120, 90)], (80, 70), (130, 70)),
        ):
            with self.subTest(tool=tool):
                dialog.strokes = [(tool, [QPoint(*p) for p in points], '', QColor('red'),
                                   15 if tool == 'Highlight' else 3)]
                self.assertEqual(dialog.mark_at(QPoint(*hit)), 0)
                self.assertIsNone(dialog.mark_at(QPoint(*miss)))

    def test_line_octants_free_drag_zero_length_and_endpoint_history(self):
        dialog = FrozenCapture(self.image(), QRect(0, 0, 400, 300))
        self.addCleanup(shiboken6.delete, dialog)
        dialog.set_tool('Line')
        origin = QPoint(140, 150)
        shift = Qt.KeyboardModifier.ShiftModifier
        left = Qt.MouseButton.LeftButton
        for dx, dy, sx, sy in ((40, 4, 40, 0), (29, 27, 28, 28), (-4, 40, 0, 40),
                               (-27, 29, -28, 28), (-40, 4, -40, 0), (-29, -27, -28, -28),
                               (4, -40, 0, -40), (27, -29, 28, -28)):
            QTest.mousePress(dialog, left, pos=origin)
            QTest.mouseRelease(dialog, left, shift, origin+QPoint(dx, dy))
            self.assertEqual(dialog.strokes[-1][1], [origin, origin+QPoint(sx, sy)])
            dialog.undo()
        QTest.mouseClick(dialog, left, pos=origin)
        self.assertEqual(dialog.strokes, [])
        self.assertTrue(dialog.redo_stack)
        end = origin + QPoint(70, 10)
        QTest.mousePress(dialog, left, pos=origin)
        QTest.mouseRelease(dialog, left, pos=end)
        self.assertEqual(dialog.strokes[0][1], [origin, end])
        self.assertIsNone(dialog.mark_at(origin+QPoint(35, 15)))
        dialog.set_tool('Edit marks')
        QTest.mouseClick(dialog, left, pos=origin+QPoint(35, 5))
        QTest.mouseClick(dialog, left, pos=end+QPoint(2, 1))
        self.assertEqual(dialog.strokes[0][1], [origin, end])
        self.assertEqual(len(dialog.undo_stack), 1)
        QTest.mousePress(dialog, left, pos=end)
        QTest.mouseRelease(dialog, left, shift, origin+QPoint(29, 27))
        self.assertEqual(dialog.strokes[0][1], [origin, origin+QPoint(28, 28)])
        dialog.undo()
        self.assertEqual(dialog.strokes[0][1], [origin, end])

    def test_number_reuse_after_delete_undo_redo_and_label_edit(self):
        dialog = FrozenCapture(self.image(), QRect(0, 0, 400, 300))
        self.addCleanup(shiboken6.delete, dialog)
        def click(x):
            QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, pos=QPoint(x, 150))
        def labels():
            return [mark[2] for mark in dialog.strokes]
        dialog.set_tool('Number')
        for x in (40, 100, 160):
            click(x)
        self.assertEqual(labels(), ['1', '2', '3'])
        dialog.undo()
        dialog.redo()
        self.assertEqual(labels(), ['1', '2', '3'])
        dialog.set_tool('Edit marks')
        click(100)
        QTest.keyClick(dialog, Qt.Key.Key_Delete)
        dialog.undo()
        self.assertEqual(labels(), ['1', '2', '3'])
        dialog.redo()
        dialog.set_tool('Number')
        click(220)
        self.assertEqual(labels(), ['1', '3', '2'])
        dialog.set_tool('Edit marks')
        click(220)
        with patch('runtime.menu_capture.QInputDialog.getInt', return_value=(12345, True)):
            QTest.keyClick(dialog, Qt.Key.Key_F2)
        self.assertEqual(labels(), ['1', '3', '12345'])
        box = dialog.mark_bounds(dialog.strokes[-1])
        self.assertIsNone(dialog.mark_at(box.topLeft()))
        self.assertEqual(dialog.mark_at(box.center()), 2)
        dialog.undo()
        self.assertEqual(labels(), ['1', '3', '2'])
        dialog.redo()
        self.assertEqual(labels(), ['1', '3', '12345'])

    def test_toolbars_fit_narrow_selection_display(self):
        for width in (320, 400, 600):
            dialog = FrozenCapture(self.image(), QRect(0, 0, width, 480))
            self.addCleanup(shiboken6.delete, dialog)
            dialog.show()
            self.app.processEvents()
            font = QFont(dialog.font())
            dialog.set_tool('Edit marks')
            dialog.strokes.append(('Text', [QPoint(50, 50)], 'label', QColor('black'), 3))
            dialog.selected_mark = 0
            dialog.updated()
            for extra_points in (0, 3):
                if extra_points:
                    font.setPointSizeF(font.pointSizeF() + extra_points)
                    dialog.setFont(font)
                    self.app.processEvents()
                for bar in (dialog.tools, dialog.controls):
                    self.assertTrue(dialog.rect().contains(bar.geometry()), (width, bar.geometry()))
                for button in (*dialog.tool_buttons.values(), *dialog.actions.values(),
                               dialog.color_button, dialog.stroke_width, dialog.help):
                    self.assertTrue(button.isVisibleTo(dialog))
                    self.assertTrue(button.parentWidget().rect().contains(button.geometry()))

                for y in (0, 470):
                    dialog.selection = QRect(width//2, y, 8, 8)
                    dialog.updated()
                    self.assertFalse(dialog.tools.geometry().intersects(dialog.controls.geometry()))
                    self.assertTrue(dialog.rect().contains(dialog.tools.geometry()))
                    self.assertTrue(dialog.rect().contains(dialog.controls.geometry()))

    def test_region_effects_exact_scaled_edge_crop_and_history(self):
        image = QImage(60, 45, QImage.Format.Format_RGB32)
        for y in range(image.height()):
            for x in range(image.width()):
                v = 32 + 128*(x % 2)
                image.setPixelColor(x, y, QColor(v, v, v))
        image.setDevicePixelRatio(1.5)
        for tool in ('Blur', 'Pixelate'):
            with self.subTest(tool=tool):
                dialog = FrozenCapture(image, QRect(-15, -10, 40, 30))
                self.addCleanup(shiboken6.delete, dialog)
                dialog.set_tool(tool)
                left = Qt.MouseButton.LeftButton
                def drag(a, b):
                    QTest.mousePress(dialog, left, pos=a)
                    QTest.mouseRelease(dialog, left, pos=b)
                drag(QPoint(39, 29), QPoint(35, 25))
                original = QRect(52, 37, 8, 8)
                moved = QRect(0, 0, 8, 8)
                def expected(rect):
                    result = image.copy()
                    result.setDevicePixelRatio(1)
                    for y in range(rect.y(), rect.y()+rect.height()):
                        for x in range(rect.x(), rect.x()+rect.width()):
                            result.setPixelColor(x, y, QColor(96, 96, 96))
                    return result
                unchanged = expected(QRect())
                self.assertEqual(dialog.rendered_image(), expected(original))
                dialog.set_tool('Edit marks')
                drag(QPoint(35, 25), QPoint(-8, -5))
                self.assertEqual(dialog.mark_bounds(dialog.strokes[0]), QRect(0, 0, 5, 5))
                self.assertEqual(dialog.rendered_image(), expected(moved))
                dialog.raw_selection = QRect(3, 5, 24, 12)
                dialog.selection = dialog.view_rect(dialog.raw_selection)
                crop = dialog.pixel_rect()
                self.assertEqual(dialog.rendered_image(), expected(moved).copy(crop))
                QTest.keyClick(dialog, Qt.Key.Key_Delete)
                self.assertEqual(dialog.rendered_image(), unchanged.copy(crop))
                for action, rect in ((dialog.undo, moved), (dialog.undo, original),
                                     (dialog.redo, moved), (dialog.redo, QRect())):
                    action()
                    self.assertEqual(dialog.rendered_image(), expected(rect).copy(crop))

    def test_effect_interpolation_stacking_and_tiny_regions(self):
        image = QImage(40, 20, QImage.Format.Format_RGB32)
        image.fill(QColor('magenta'))
        for y in range(12):
            for x in range(24):
                v = 40 if x < 12 else 200
                image.setPixelColor(x, y, QColor(v, v, v))
        dialog = FrozenCapture(image, image.rect())
        self.addCleanup(shiboken6.delete, dialog)
        def mark(tool, a, b):
            dialog.set_tool(tool)
            QTest.mousePress(dialog, Qt.MouseButton.LeftButton, pos=a)
            QTest.mouseRelease(dialog, Qt.MouseButton.LeftButton, pos=b)
        # One native pixel at the corner cannot draw in samples from outside it.
        mark('Blur', QPoint(39, 19), QPoint(39, 19))
        mark('Pixelate', QPoint(39, 19), QPoint(45, 25))
        self.assertEqual(dialog.rendered_image(), image)
        a, b = QPoint(2, 2), QPoint(23, 11)
        mark('Redact', QPoint(4, 3), QPoint(7, 7))
        mark('Blur', a, b)
        blurred = dialog.rendered_image()
        self.assertEqual(blurred.pixelColor(5, 5), QColor('black'))
        self.assertEqual(dialog.mark_at(QPoint(5, 5)), 2)
        self.assertTrue(40 < blurred.pixelColor(12, 5).red() < 200)
        mark('Pixelate', a, b)
        pixelated = dialog.rendered_image()
        self.assertEqual(dialog.mark_at(QPoint(16, 5)), 4)
        self.assertEqual(pixelated.pixelColor(13, 5), QColor(200, 200, 200))
        self.assertEqual(pixelated.pixelColor(8, 5), pixelated.pixelColor(11, 5))
        self.assertNotEqual(pixelated, blurred)
        self.assertEqual(pixelated.pixelColor(24, 5), image.pixelColor(24, 5))
        dialog.undo()
        self.assertEqual(dialog.rendered_image(), blurred)
        mark('Redact', QPoint(15, 5), QPoint(16, 6))
        self.assertEqual(dialog.rendered_image().pixelColor(15, 5), QColor('black'))

    def test_styled_labels_keep_font_color_position_and_legacy_undo(self):
        source = self.image()
        dialog = FrozenCapture(source, QRect(0, 0, 200, 150))
        self.addCleanup(shiboken6.delete, dialog)
        left = Qt.MouseButton.LeftButton
        a, b = QPoint(14, 38), QPoint(36, 95)
        serif = QFont('DejaVu Serif', 18)
        mono = QFont('DejaVu Sans Mono', 12)
        mono.setBold(True)
        mono.setItalic(True)
        red, blue = QColor('firebrick'), QColor('navy')
        dialog.set_tool('Text')
        for point, value in ((a, ('old', serif, red)), (b, ('new', mono, blue))):
            with patch('runtime.menu_capture.text_editor', return_value=value):
                QTest.mouseClick(dialog, left, pos=point)
        original = dialog.strokes[0]
        self.assertEqual([m[5] for m in dialog.strokes], [serif, mono])
        dialog.set_tool('Edit marks')
        QTest.mouseClick(dialog, left, pos=dialog.mark_bounds(original).center())
        self.assertEqual(dialog.color_button.text(), 'Edit text…')
        with patch('runtime.menu_capture.text_editor', return_value=('old', mono, blue)):
            dialog.color_button.click()
        changed = dialog.strokes[0]
        self.assertEqual((changed[3], changed[5]), (blue, mono))
        self.assertEqual(dialog.strokes[1][5], mono)
        dialog.undo()
        self.assertEqual(dialog.strokes[0], original)
        dialog.redo()
        hit = dialog.mark_bounds(changed).center()
        QTest.mousePress(dialog, left, pos=hit)
        QTest.mouseRelease(dialog, left, pos=hit+QPoint(7, 4))
        self.assertEqual(dialog.strokes[0][5], mono)
        expected = source.copy()
        with QPainter(expected) as paint:
            paint.scale(2, 2)
            paint.setRenderHint(QPainter.RenderHint.Antialiasing)
            font = QFont(mono)
            font.setPixelSize(round(12*dialog.logicalDpiY()/72))
            paint.setFont(font)
            paint.setPen(blue)
            paint.drawText(a+QPoint(7, 4), 'old')
            paint.drawText(b, 'new')
        self.assertEqual(dialog.rendered_image(), expected)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'styled.png'
            self.assertTrue(publish(dialog.rendered_image(), self.app, path))
            self.assertEqual(QImage(str(path)), expected)

        legacy = original[:5]
        dialog.strokes[:] = [legacy]
        dialog.selected_mark = 0
        with patch('runtime.menu_capture.text_editor', return_value=('old', mono, blue)):
            dialog.edit_label()
        dialog.undo()
        self.assertEqual(dialog.strokes, [legacy])
        self.assertEqual(dialog.mark_bounds(legacy), dialog.fontMetrics().boundingRect('old').translated(a))

    def test_cancel_new_styled_label_in_narrow_large_font_dialog(self):
        dialog = FrozenCapture(self.image(), QRect(0, 0, 320, 480))
        self.addCleanup(shiboken6.delete, dialog)
        larger = QFont(dialog.font())
        larger.setPointSizeF(larger.pointSizeF()+3)
        dialog.setFont(larger)
        dialog.set_tool('Text')
        observed = []
        def cancel_form():
            form = self.app.activeModalWidget()
            try:
                ok = form.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
                observed.append(not ok.isEnabled())
                observed.append(form.width() <= 320 and form.height() <= 480)
                field = form.findChild(QLineEdit)
                field.setText('temporary')
                form.findChild(QFontComboBox).setCurrentFont(QFont('DejaVu Serif'))
                form.findChild(QDoubleSpinBox).setValue(24)
                form.findChild(QCheckBox).setChecked(True)
                observed.append(ok.isEnabled())
            finally:
                form.reject()
        QTimer.singleShot(0, cancel_form)
        QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, pos=QPoint(80, 80))
        self.assertEqual(observed, [True, True, True])
        self.assertEqual(dialog.strokes, [])
        self.assertEqual(dialog.undo_stack, [])

    def test_native_monitor_edges_map_into_negative_logical_desktop(self):
        desktop = QRect(-1280, -100, 2560, 720)
        root = QSize(3840, 1080)
        self.assertEqual(monitor_geometry(QRect(0, 0, 1920, 1080), root, desktop),
                         QRect(-1280, -100, 1280, 720))
        self.assertEqual(monitor_geometry(QRect(1920, 0, 1920, 1080), root, desktop),
                         QRect(0, -100, 1280, 720))

    def test_new_capture_options_cancel_preserves_old_edit(self):
        dialog = FrozenCapture(self.image(), QRect(0, 0, 400, 300))
        self.addCleanup(shiboken6.delete, dialog)
        self.select(dialog)
        before = dialog.rendered_image()
        def cancel_options():
            form = self.app.activeModalWidget()
            form.findChild(QSpinBox).setValue(7)
            QTest.keyClick(form, Qt.Key.Key_Escape)
        QTimer.singleShot(0, cancel_options)
        dialog.actions['New capture…'].click()
        self.assertTrue(dialog.isVisible())
        self.assertFalse(hasattr(dialog, 'capture_request'))
        self.assertEqual(dialog.rendered_image(), before)

    def test_window_border_control_fits_narrow_picker(self):
        dialog = FrozenCapture(self.image(), QRect(0, 0, 320, 480), [self.image().rect()])
        self.addCleanup(shiboken6.delete, dialog)
        font = QFont(dialog.font())
        font.setPointSizeF(font.pointSizeF()+3)
        dialog.setFont(font)
        dialog.show()
        dialog.pick_window()
        self.app.processEvents()
        self.assertTrue(dialog.window_borders.isVisibleTo(dialog))
        self.assertTrue(dialog.controls.rect().contains(dialog.window_borders.geometry()))
        self.assertTrue(dialog.rect().contains(dialog.controls.geometry()))

    def test_window_picker_hits_frame_even_if_client_is_outside_capture(self):
        image = self.image()
        lower = image.rect()
        top = (QRect(-40, 20, 40, 100), QRect(-45, 10, 50, 115))
        dialog = FrozenCapture(image, QRect(-200, -50, 200, 150), [top, (lower, lower)])
        self.addCleanup(shiboken6.delete, dialog)
        dialog.show()
        dialog.actions['Window'].click()
        border = QPoint(1, 40)
        self.assertTrue(dialog.window_borders.isVisible())
        self.assertEqual(dialog.window_at(border), QRect(0, 10, 5, 115))
        dialog.window_borders.click()
        self.assertTrue(dialog.window_at(border).isEmpty())
        QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, pos=border)
        self.assertEqual(dialog.active_tool, 'Window')
        QTest.keyClick(dialog, Qt.Key.Key_B)
        QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, pos=border)
        self.assertEqual(dialog.pixel_rect(), QRect(0, 10, 5, 115))
        self.assertFalse(dialog.window_borders.isVisible())
