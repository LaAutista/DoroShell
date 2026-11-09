"""Interactive-widget smoke test; temporary settings only, no global input."""
import importlib.util
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QTimer
import shiboken6
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('menu', root / 'menu/start_menu.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
app = m.QApplication([])
errors = []
with tempfile.TemporaryDirectory(prefix='doroshell-links-') as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
    folder = Path(directory) / 'Folder with spaces'
    folder.mkdir()
    window = m.StartMenu()
    window.exit_on_hide = True
    window.show()
    def edit():
        try:
            editor = app.activeModalWidget()
            assert isinstance(editor, m.FolderEditor)
            with patch.object(m.QFileDialog, 'getExistingDirectory', return_value=str(folder)):
                QTest.mouseClick(editor.buttons['Add folder…'], Qt.MouseButton.LeftButton)
            editor.table.setCurrentCell(6, 0)
            editor.table.setFocus()
            QTest.keyClick(editor.table, Qt.Key.Key_F2)
            QTest.qWait(20)
            QTest.keyClick(app.focusWidget(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClicks(app.focusWidget(), 'Test project')
            QTest.keyClick(app.focusWidget(), Qt.Key.Key_Return)
            QTest.mouseClick(editor.buttons['Move up'], Qt.MouseButton.LeftButton)
            QTest.mouseClick(editor.actions.button(m.QDialogButtonBox.StandardButton.Save), Qt.MouseButton.LeftButton)
        except Exception as error:
            errors.append(str(error))
            if app.activeModalWidget(): app.activeModalWidget().reject()
    def start():
        QTimer.singleShot(250, edit)
        QTest.mouseClick(window.edit_links_button, Qt.MouseButton.LeftButton)
        try:
            assert window.isVisible(), 'Menu did not return after editor'
            saved = m.FolderSettings(Path(directory) / 'lxqt-comfort/folders.json')
            assert saved.links[5]['label'] == 'Test project'
            assert window.folder_paths['Test project'] == str(folder)
        except Exception as error:
            errors.append(str(error))
        app.quit()
    QTimer.singleShot(100, start)
    app.exec()
    shiboken6.delete(window)
assert not errors, errors
print('PASS: X11 editor mouse/keyboard, save, persisted order, menu lifecycle; temporary config only')
