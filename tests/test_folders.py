import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_menu import menu
import shiboken6
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QTimer


class FolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = menu.QApplication.instance() or menu.QApplication([])

    def test_mouse_add_keyboard_rename_reorder_hide_save_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'folders.json'
            folder = Path(directory) / '資料 with spaces'
            folder.mkdir()
            settings = menu.FolderSettings(path)
            editor = menu.FolderEditor(settings)
            editor.show()
            QTest.qWait(20)
            with patch.object(menu.QFileDialog, 'getExistingDirectory', return_value=str(folder)):
                QTest.mouseClick(editor.buttons['Add folder…'], Qt.MouseButton.LeftButton)
            row = editor.table.rowCount() - 1
            editor.table.setCurrentCell(row, 0)
            editor.table.setFocus()
            QTest.keyClick(editor.table, Qt.Key.Key_F2)
            QTest.qWait(20)
            self.assertIsNotNone(self.app.focusWidget())
            QTest.keyClick(self.app.focusWidget(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClicks(self.app.focusWidget(), 'Project files')
            QTest.keyClick(self.app.focusWidget(), Qt.Key.Key_Return)
            QTest.mouseClick(editor.buttons['Move up'], Qt.MouseButton.LeftButton)
            self.assertEqual(editor.table.item(row - 1, 0).text(), 'Project files')
            editor.table.setCurrentCell(0, 2)
            editor.table.setFocus()
            QTest.keyClick(editor.table, Qt.Key.Key_Space)
            QTest.mouseClick(editor.actions.button(menu.QDialogButtonBox.StandardButton.Save), Qt.MouseButton.LeftButton)
            self.assertEqual(editor.result(), menu.QDialog.DialogCode.Accepted)
            reloaded = menu.FolderSettings(path)
            self.assertFalse(reloaded.links[0]['visible'])
            self.assertEqual(reloaded.links[row - 1]['label'], 'Project files')
            self.assertEqual(menu.link_path(reloaded.links[row - 1]), str(folder))
            shiboken6.delete(editor)

    def test_change_destination_portrait_and_hidden_system_links(self):
        from PySide6.QtGui import QImage, QColor
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory, 'XDG_DATA_HOME': directory}):
            home = Path(directory)
            art = home / 'lxqt-comfort'
            art.mkdir()
            icon = art / 'start-icon.png'
            picture = home / 'portrait.png'
            img = QImage(24, 24, QImage.Format.Format_RGB32)
            img.fill(QColor('blue'))
            img.save(str(icon))
            original = icon.read_bytes()
            img.fill(QColor('red'))
            img.save(str(picture))
            editor = menu.FolderEditor(menu.FolderSettings(art / 'folders.json'))
            with patch.object(menu.QFileDialog, 'getExistingDirectory', return_value=directory):
                editor.change_folder()
            editor.set_picture(str(picture))
            editor.system_checks['Printers'].setChecked(False)
            editor.save()
            window = menu.StartMenu()
            self.assertEqual(window.folder_paths['Home'], directory)
            self.assertEqual(window.mascot.pixmap().toImage().pixelColor(10, 10).name(), '#ff0000')
            self.assertNotIn('Printers', [b.text() for b in window.findChildren(menu.QPushButton, 'folderLink')])
            picture.unlink()
            window.refresh_portrait()
            self.assertEqual(window.mascot.pixmap().toImage().pixelColor(10, 10).name(), '#0000ff')
            self.assertEqual(icon.read_bytes(), original)
            shiboken6.delete(editor)
            shiboken6.delete(window)

    def test_cancel_defaults_backup_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'folders.json'
            settings = menu.FolderSettings(path)
            custom = menu.default_links()
            custom[0]['label'] = 'My home'
            settings.save(custom)
            original = path.read_bytes()
            editor = menu.FolderEditor(settings)
            editor.show()
            QTest.qWait(20)
            QTest.mouseClick(editor.buttons['Restore defaults'], Qt.MouseButton.LeftButton)
            QTest.keyClick(editor, Qt.Key.Key_Escape)
            self.assertEqual(path.read_bytes(), original)
            shiboken6.delete(editor)
            editor = menu.FolderEditor(settings)
            editor.buttons['Restore defaults'].click()
            editor.save()
            self.assertEqual(menu.FolderSettings(path).links, menu.default_links())
            self.assertEqual(list(path.parent.glob('folders.json.backup-*'))[0].read_bytes(), original)
            shiboken6.delete(editor)

    def test_invalid_concurrent_and_failed_save_preserve_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'folders.json'
            path.write_text('{broken')
            settings = menu.FolderSettings(path)
            self.assertIsNotNone(settings.error)
            with self.assertRaises(ValueError): settings.save(menu.default_links())
            self.assertEqual(path.read_text(), '{broken')
            path.unlink()
            settings = menu.FolderSettings(path)
            settings.save(menu.default_links())
            original = path.read_bytes()
            invalid = menu.default_links()
            invalid[0]['standard'] = []
            with self.assertRaises(ValueError): settings.save(invalid)
            invalid = menu.default_links()
            invalid[0]['label'] = ''
            with self.assertRaises(ValueError): settings.save(invalid)
            changed = menu.default_links()
            changed[0]['label'] = 'Changed'
            with patch.object(Path, 'replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError): settings.save(changed)
            self.assertEqual(path.read_bytes(), original)
            path.write_text('{}')
            with self.assertRaises(ValueError): settings.save(menu.default_links())
            self.assertEqual(path.read_text(), '{}')

    def test_editor_modal_returns_to_menu_and_folder_click_dispatch(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = menu.StartMenu()
            window.exit_on_hide = True
            window.show()
            def cancel_editor():
                editor = self.app.activeModalWidget()
                self.assertIsInstance(editor, menu.FolderEditor)
                QTest.keyClick(editor, Qt.Key.Key_Escape)
            QTimer.singleShot(50, cancel_editor)
            QTest.mouseClick(window.edit_links_button, Qt.MouseButton.LeftButton)
            self.assertTrue(window.isVisible())
            self.assertTrue(window.exit_on_hide)
            window.exit_on_hide = False
            with patch.object(menu.Gio.AppInfo, 'launch_default_for_uri', return_value=True) as launch:
                QTest.mouseClick(window.folder_layout.itemAt(0).widget().findChild(menu.QPushButton, 'folderLink'), Qt.MouseButton.LeftButton)
                launch.assert_called_once_with(Path.home().as_uri(), None)
            shiboken6.delete(window)

    def test_empty_hidden_and_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'folders.json'
            editor = menu.FolderEditor(menu.FolderSettings(path))
            for _ in menu.FOLDERS:
                editor.table.selectRow(0)
                editor.buttons['Remove'].click()
            editor.save()
            self.assertEqual(menu.FolderSettings(path).links, [])
            shiboken6.delete(editor)

if __name__ == '__main__': unittest.main()
