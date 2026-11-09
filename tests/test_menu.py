import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import shiboken6
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
menu = load('start_menu', ROOT / 'menu/start_menu.py')
installer = load('installer', ROOT / 'install.py')
import sys
sys.path.insert(0, str(ROOT))
integration = load('integration', ROOT / 'integrate.py')

class MenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = menu.QApplication.instance() or menu.QApplication([])

    def test_application_tasks_use_gio_and_reject_unknown_action(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = menu.StartMenu()
            app = Mock()
            app.list_actions.return_value = ['new-window']
            app.launch_action.return_value = None
            window.by_id['test.desktop'] = app
            with patch.object(window, 'error') as error, patch.object(window, 'close') as close:
                window.launch_app_action('test.desktop', 'unknown')
                app.launch_action.assert_not_called()
                error.assert_called_once()
                window.launch_app_action('test.desktop', 'new-window')
                app.launch_action.assert_called_once_with('new-window', None)
                close.assert_called_once()
                window.launch_app_action('test.desktop', 'new-window')
                self.assertEqual(app.launch_action.call_count, 1)
            window.close()
            shiboken6.delete(window)

    def test_application_task_context_menu_keeps_favorites_unchanged(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = menu.StartMenu()
            app = Mock()
            app.list_actions.return_value = ['new-window']
            app.get_action_name.return_value = 'New & Window'
            window.show()
            self.app.processEvents()
            window.by_id['test.desktop'] = app
            window.list.clear()
            item = menu.QListWidgetItem('Test')
            item.setData(menu.Qt.ItemDataRole.UserRole, 'test.desktop')
            window.list.addItem(item)
            self.app.processEvents()
            before = window.favorites.copy()
            # Corrupt favorites must not block unrelated application tasks.
            window.state_error = 'invalid favorites'
            def choose_task(popup, position):
                action = popup.actions()[-1]
                self.assertEqual(action.text(), 'New && Window')
                return action
            class TestMenu(menu.QMenu):
                exec = choose_task
            with patch.object(menu, 'QMenu', TestMenu), patch.object(window, 'launch_app_action') as launch, patch.object(window, 'error') as error:
                window.context_menu(window.list.visualItemRect(item).center())
                launch.assert_called_once_with('test.desktop', 'new-window')
            self.assertEqual(window.favorites, before)
            window.close()
            shiboken6.delete(window)

    def test_pin_drag_order_preserves_unavailable_pins_and_refuses_conflicts(self):
        import json
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            state=Path(directory)/'lxqt-comfort/favorites.json'
            state.parent.mkdir(parents=True)
            original=['a.desktop','unavailable.desktop','b.desktop','c.desktop']
            state.write_text(json.dumps(original))
            window=menu.StartMenu()
            self.assertTrue(window.reorder_pin('c.desktop','a.desktop'))
            expected=['c.desktop','a.desktop','unavailable.desktop','b.desktop']
            self.assertEqual(json.loads(state.read_text()),expected)
            self.assertEqual(json.loads(next(state.parent.glob('favorites.json.backup-*')).read_text()),original)
            state.write_text('["personal-edit.desktop"]')
            with patch.object(window,'error') as error:
                self.assertFalse(window.reorder_pin('a.desktop','b.desktop',True))
                error.assert_called_once()
            self.assertEqual(window.favorites,expected)
            self.assertEqual(json.loads(state.read_text()),['personal-edit.desktop'])
            shiboken6.delete(window)

    def test_pin_drag_restricted_to_unfiltered_pin_views_and_never_launches(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window=menu.StartMenu()
            window.favorites=['a.desktop','b.desktop']
            window.category.setCurrentText('All applications')
            self.assertFalse(window.reorder_pin('b.desktop','a.desktop'))
            window.category.setCurrentText('Pinned');window.search.setText('a')
            self.assertFalse(window.reorder_pin('b.desktop','a.desktop'))
            window.search.clear()
            self.assertFalse(window.reorder_pin('b.desktop','recent.desktop'))
            item=menu.QListWidgetItem('A');item.setData(menu.Qt.ItemDataRole.UserRole,'a.desktop')
            fake=Mock();window.by_id['a.desktop']=fake
            window.list.dragging=True
            window.launch_item(item)
            fake.launch.assert_not_called()
            self.assertFalse(window.state.exists())
            shiboken6.delete(window)

    def test_programs_button_and_escape_return_without_launching(self):
        from PySide6.QtTest import QTest
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = menu.StartMenu()
            window.show()
            window.activateWindow()
            self.app.processEvents()
            with patch.object(window, 'launch_item') as launch:
                self.assertEqual(window.programs.text(), 'All Programs')
                QTest.mouseClick(window.programs, menu.Qt.MouseButton.LeftButton)
                self.assertEqual(window.category.currentText(), 'All applications')
                self.assertEqual(window.programs.text(), 'Back')
                window.search.setText('test')
                QTest.keyClick(window.search, menu.Qt.Key.Key_Escape)
                self.app.processEvents()
                self.assertEqual(window.search.text(), '')
                self.assertEqual(window.category.currentText(), 'All applications')
                self.assertTrue(window.isVisible())
                QTest.keyClick(window.search, menu.Qt.Key.Key_Escape)
                self.app.processEvents()
                self.assertEqual(window.category.currentText(), 'Home')
                self.assertTrue(window.isVisible())
                window.category.setCurrentText('Utility')
                window.search.setText('test')
                QTest.mouseClick(window.programs, menu.Qt.MouseButton.LeftButton)
                self.assertEqual(window.search.text(), '')
                self.assertEqual(window.category.currentText(), 'Home')
                self.assertTrue(window.search.hasFocus())
                QTest.keyClick(window.search, menu.Qt.Key.Key_Escape)
                self.app.processEvents()
                self.assertFalse(window.isVisible())
                launch.assert_not_called()
            shiboken6.delete(window)

    def test_session_actions_require_confirmation_and_skip_recent_history(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = menu.StartMenu()
            window.exit_on_hide = True
            fixture = Mock(); fixture.launch.return_value = True
            with patch.object(menu.Gio.DesktopAppInfo, 'new', return_value=fixture) as lookup, patch.object(menu.QMessageBox, 'question', return_value=menu.QMessageBox.StandardButton.Cancel) as question, patch.object(window.recent, 'save') as recent, patch.object(window, 'close') as close:
                window.session_action('shutdown')
                question.assert_called_once()
                self.assertEqual(question.call_args.args[-1], menu.QMessageBox.StandardButton.Cancel)
                fixture.launch.assert_not_called(); close.assert_not_called()
                self.assertTrue(window.exit_on_hide); self.assertFalse(window.launching)
                question.return_value = menu.QMessageBox.StandardButton.Yes
                for action_id in menu.SESSION_ACTIONS:
                    window.launching = False
                    window.session_action(action_id)
                    lookup.assert_called_with('lxqt-' + action_id + '.desktop')
                self.assertEqual(fixture.launch.call_count, len(menu.SESSION_ACTIONS))
                recent.assert_not_called()
                window.session_action('shutdown')
                self.assertEqual(fixture.launch.call_count, len(menu.SESSION_ACTIONS))
            window.exit_on_hide = False; window.close(); shiboken6.delete(window)

    def test_session_action_missing_or_invalid_never_dispatches(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = menu.StartMenu()
            with patch.object(menu.Gio.DesktopAppInfo, 'new', return_value=None) as lookup, patch.object(window, 'error') as error, patch.object(menu.QMessageBox, 'question') as question:
                window.session_action('unexpected')
                lookup.assert_not_called()
                window.session_action('shutdown')
                question.assert_not_called()
                self.assertEqual(error.call_count, 2)
                self.assertFalse(window.launching)
            window.close(); shiboken6.delete(window)

    def test_search_and_filter(self):
        data = menu.GLib.KeyFile()
        text = '[Desktop Entry]\nType=Application\nName=Test Editor\nExec=/bin/true\nCategories=Utility;\nKeywords=writing;\n'
        data.load_from_data(text, len(text), 0)
        app = menu.Gio.DesktopAppInfo.new_from_keyfile(data)
        self.assertTrue(menu.matches(app, 'EDITOR writing', 'Utility'))
        self.assertFalse(menu.matches(app, 'editor', 'Game'))
        self.assertFalse(menu.matches(app, 'missing', 'All applications'))

    def test_right_column_controls_fit_and_folders_remain_accessible(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = menu.StartMenu()
            window.show()
            self.app.processEvents()
            area = window.findChild(menu.QScrollArea)
            controls = window.findChildren(menu.QPushButton, 'menuControl')
            self.assertEqual(len(controls), 4)
            self.assertEqual(area.verticalScrollBar().maximum(), 0)
            portrait = window.findChild(menu.QLabel, 'personalStartImage')
            places = window.findChild(menu.QWidget, 'placesPanel')
            self.assertFalse(portrait.pixmap().isNull())
            center = portrait.mapTo(window, portrait.rect().center())
            self.assertTrue(places.geometry().left() <= center.x() <= places.geometry().right())
            self.assertLess(portrait.mapTo(window, portrait.rect().bottomLeft()).y(), places.geometry().top())
            for width, height in ((680, 570), (480, 450), (900, 700)):
                window.resize(width, height)
                self.app.processEvents()
                for button in controls:
                    self.assertTrue(window.rect().contains(button.geometry()))
                    self.assertGreaterEqual(button.width(), button.minimumSizeHint().width())
                for first, second in zip(controls, controls[1:]):
                    self.assertLess(first.geometry().bottom(), second.geometry().top())
                self.assertLess(area.geometry().bottom(), controls[0].geometry().top())
            window.close()
            shiboken6.delete(window)

    def test_menu_search_empty_folder_and_launch_error(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = menu.StartMenu()
            self.assertGreater(window.list.count(), 0)
            window.search.setText('zz-no-such-application-zz')
            self.assertEqual(window.list.count(), 0)
            window.launch_item(None)
            with patch.object(window, 'error') as error:
                window.open_folder('/no-such-folder-comfort-test')
                error.assert_called_once()
            window.list.clear()
            window.close()
            shiboken6.delete(window)

    def test_folder_uri_uses_default_handler(self):
        with tempfile.TemporaryDirectory(prefix='folder spaces ') as directory:
            window = menu.StartMenu()
            with patch.object(menu.Gio.AppInfo, 'launch_default_for_uri', return_value=True) as launch:
                window.open_folder(directory)
                launch.assert_called_once_with(Path(directory).as_uri(), None)
            window.list.clear()
            window.close()
            shiboken6.delete(window)

    def test_installer_idempotent_backup_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            old = home / '.local/bin/lxqt-comfort-menu'
            old.parent.mkdir(parents=True)
            old.write_text('previous launcher')
            old.chmod(0o700)
            installer.install(home, False)
            self.assertEqual(old.read_text(), 'previous launcher')
            installer.install(home, True)
            stamp = old.stat().st_mtime_ns
            installer.install(home, True)
            self.assertEqual(stamp, old.stat().st_mtime_ns)
            old.write_text('user edit')
            with self.assertRaises(RuntimeError):
                installer.rollback(home)
            old.write_bytes(installer.targets(home)[old][0])
            installer.rollback(home)
            self.assertEqual(old.read_text(), 'previous launcher')
            self.assertEqual(old.stat().st_mode & 0o777, 0o700)
            self.assertFalse((home / '.local/share/applications/lxqt-comfort.desktop').exists())

    def test_integration_preserves_other_settings_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config = home / '.config/lxqt'
            config.mkdir(parents=True)
            (config / 'panel.conf').write_text('[panel1]\nplugins=fancymenu, dockbarx\n[other]\nkeep=yes\n')
            (config / 'globalkeyshortcuts.conf').write_text('[Alt%2BF1.1]\npath=/panel/fancymenu/show_hide\nEnabled=true\n')
            integration.run(home, apply=True)
            integration.run(home, apply=True)
            cfg = integration.QSettings(str(config / 'panel.conf'), integration.QSettings.Format.IniFormat)
            self.assertEqual(cfg.value('panel1/plugins'), ['comfortstart', 'dockbarx'])
            cfg.setValue('other/keep', 'new personal setting')
            cfg.sync()
            integration.run(home, rollback=True)
            cfg.sync()
            self.assertEqual(cfg.value('panel1/plugins'), ['fancymenu', 'dockbarx'])
            self.assertEqual(cfg.value('other/keep'), 'new personal setting')

    def test_split_session_controls_route_through_guarded_handler(self):
        window = menu.StartMenu()
        with patch.object(window, 'session_action') as launch:
            window.session_button.click()
            launch.assert_called_once_with('shutdown')
            window.power_menu.actions()[-1].trigger()
            launch.assert_called_with('options')
        shiboken6.delete(window)

    def test_duplicate_activation_launches_once_and_recent_history_persists(self):
        from unittest.mock import MagicMock
        fake = MagicMock()
        fake.get_id.return_value='example.desktop'
        fake.get_display_name.return_value='Example'
        fake.get_description.return_value='Example app'
        fake.get_categories.return_value='Utility;'
        fake.get_keywords.return_value=[]
        fake.get_executable.return_value='/bin/true'
        fake.launch.return_value=True
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'XDG_CONFIG_HOME':d}), patch.object(menu,'applications',return_value=[fake]):
            window=menu.StartMenu()
            item=window.list.item(0)
            window.launch_item(item)
            window.launch_item(item)
            fake.launch.assert_called_once_with([],None)
            recent=menu.RecentPrograms(Path(d)/'lxqt-comfort/recent.json')
            self.assertEqual(recent.value['items'],['example.desktop'])
            recent.save(enabled=False)
            self.assertEqual(menu.RecentPrograms(recent.path).value,{'enabled':False,'items':[]})
            shiboken6.delete(window)

    def test_symlink_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / '.local').symlink_to('/tmp', target_is_directory=True)
            with self.assertRaises(RuntimeError):
                installer.install(home, True)

if __name__ == '__main__':
    unittest.main()
