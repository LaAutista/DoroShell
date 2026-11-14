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

    def test_primary_session_choice_persists_and_routes_without_executing(self):
        import json
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window=menu.StartMenu()
            with patch.object(menu,'desktop_entry',return_value=Mock()), patch.object(window,'session_action') as launch:
                for action_id,(label,_) in menu.SESSION_ACTIONS.items():
                    window.set_primary_action(action_id)
                    self.assertEqual(window.primary_action,action_id)
                    self.assertEqual(window.session_button.text(),label+('' if action_id=='lockscreen' else '…'))
                    window.session_button.click();launch.assert_called_with(action_id)
                    visible={a.data() for a in window.power_menu.actions() if a.isVisible() and a.data()}
                    self.assertEqual(visible,set(menu.SESSION_ACTIONS)-{action_id})
            self.assertEqual(json.loads(window.primary_path.read_text())['action'],'lockscreen')
            shiboken6.delete(window)
            reopened=menu.StartMenu();self.assertEqual(reopened.primary_action,'lockscreen');shiboken6.delete(reopened)

    def test_primary_session_choice_rejects_corruption_external_edits_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window=menu.StartMenu();window.set_primary_action('reboot')
            window.primary_path.write_text('personal edit')
            with patch.object(window,'error') as error:
                window.set_primary_action('logout');error.assert_called_once()
            self.assertEqual(window.primary_action,'reboot');self.assertEqual(window.primary_path.read_text(),'personal edit')
            path=window.primary_path;shiboken6.delete(window)
            for content in ('{}','{"version":1,"action":[]}','{"version":1,"action":"unknown"}'):
                path.write_text(content);window=menu.StartMenu()
                self.assertEqual(window.primary_action,'shutdown')
                with patch.object(window,'error') as error:window.set_primary_action('logout');error.assert_called_once()
                self.assertEqual(path.read_text(),content);shiboken6.delete(window)
            target=Path(directory)/'keep';target.write_text('original');path.unlink();path.symlink_to(target)
            window=menu.StartMenu()
            with patch.object(window,'error') as error:window.set_primary_action('logout');error.assert_called_once()
            self.assertEqual(target.read_text(),'original');shiboken6.delete(window)

    def test_primary_session_missing_action_is_disabled_and_selection_never_launches(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window=menu.StartMenu();fixture=Mock()
            with patch.object(menu,'desktop_entry',return_value=fixture):
                window.set_primary_action('reboot');fixture.launch.assert_not_called()
            with patch.object(menu,'desktop_entry',return_value=None),patch.object(window,'session_action') as launch:
                window.refresh_primary_action();self.assertFalse(window.session_button.isEnabled())
                window.session_button.click();launch.assert_not_called()
            shiboken6.delete(window)

    def test_catalog_refresh_retains_view_and_missing_pin_records(self):
        import json
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            folder=Path(directory)
            apps=[]
            for name in ('Alpha','Beta'):
                path=folder/(name+'.desktop')
                path.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec=/usr/bin/true\nCategories=System;\n')
                apps.append(menu.Gio.DesktopAppInfo.new_from_filename(str(path)))
            with patch.object(menu,'applications',return_value=apps):
                window=menu.StartMenu()
            window.save_favorites([apps[0].get_id(),'missing.desktop'])
            before=window.state.read_bytes()
            window.category.setCurrentText('System');window.search.setText('Beta')
            with patch.object(menu,'applications',return_value=[apps[1]]):window.refresh_catalog()
            self.assertEqual(window.category.currentText(),'System')
            self.assertEqual(window.search.text(),'Beta')
            self.assertEqual(window.list.currentItem().data(menu.Qt.ItemDataRole.UserRole),apps[1].get_id())
            self.assertEqual(window.state.read_bytes(),before)
            self.assertIn('missing.desktop',window.favorites)
            shiboken6.delete(window)

    def test_default_pin_order_missing_apps_and_configured_handler(self):
        from unittest.mock import Mock
        ids = ['qterminal.desktop', 'firefox.desktop', 'org.kde.dolphin.desktop',
               'org.kde.kate.desktop', 'vlc.desktop', 'lxqt-config.desktop']
        apps = {key: Mock() for key in ids + ['editor.desktop']}
        for key, app in apps.items():
            app.get_id.return_value = key
            app.get_executable.return_value = '/bin/true'
            app.get_boolean.return_value = False
        with patch.object(menu, 'desktop_entry', side_effect=apps.get), patch.object(
                menu.Gio.AppInfo, 'get_default_for_type',
                side_effect=lambda mime, _: apps['editor.desktop'] if mime == 'text/plain' else None):
            self.assertEqual(menu.default_pins(apps), ids)
            del apps['org.kde.kate.desktop']
            apps['vlc.desktop'].get_executable.return_value = '/no/such/player'
            self.assertEqual(menu.default_pins(apps), ids[:3] + ['editor.desktop', ids[-1]])

    def test_only_new_pin_file_is_seeded(self):
        import json
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            for expected in (['new.desktop'], ['custom.desktop', 'other.desktop'], []):
                with patch.object(menu, 'default_pins', return_value=['new.desktop']) as seed:
                    window = menu.StartMenu()
                    self.assertEqual(window.favorites, expected)
                    self.assertEqual(seed.call_count, int(expected == ['new.desktop']))
                    path = window.state
                    shiboken6.delete(window)
                if expected:
                    path.write_text(json.dumps(['custom.desktop', 'other.desktop'] if expected == ['new.desktop'] else []))

    def test_system_links_dispatch_and_disable_missing_tools(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}), patch.object(
                menu, 'available_entry', side_effect=lambda ids: next(iter(ids), None) if 'nm-connection-editor.desktop' in ids else None):
            window = menu.StartMenu()
            buttons = {button.text(): button for button in window.findChildren(menu.QPushButton, 'folderLink')}
            buttons['Games'].click()
            self.assertEqual(window.category.currentText(), 'Game')
            with patch.object(window, 'run_desktop') as run, patch.object(window, 'open_folder') as folder:
                buttons['Network connections'].click()
                run.assert_called_once_with('nm-connection-editor.desktop')
                buttons['Computer'].click()
                folder.assert_called_once_with('/')
            with patch.object(menu, 'desktop_entry', return_value=None), patch.object(menu.shutil, 'which', return_value=None), patch.object(window, 'error') as error:
                buttons['Printers'].click()
                error.assert_called_once()
            shiboken6.delete(window)

    def test_printers_without_systemsettings_uses_kcm_host(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = menu.StartMenu()
            with patch.object(menu, 'desktop_entry', side_effect=lambda key: Mock() if key in (
                    'org.kde.ConfigurePrinter.desktop',) else None), patch.object(
                    menu.shutil, 'which', side_effect=lambda exe: '/usr/bin/kcmshell6' if exe == 'kcmshell6' else None), patch.object(
                    menu.Gio.AppInfo, 'create_from_commandline') as create, patch.object(
                    menu.QStandardPaths, 'locate', return_value='/usr/share/applications/kcm_printer_manager.desktop'), patch.object(window, 'error') as error:
                create.return_value.launch.return_value = True
                window.open_printers()
                create.assert_called_once_with('kcmshell6 kcm_printer_manager', 'Printers', menu.Gio.AppInfoCreateFlags.NONE)
                create.return_value.launch.assert_called_once_with([], None)
                error.assert_not_called()
                create.return_value.launch.return_value = False
                window.open_printers()
                error.assert_called_once()
            shiboken6.delete(window)

    def test_app_export_uses_copy_only_file_urls_and_preserves_pins(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            path = Path(directory)/"App space & 'quote' %.desktop"
            path.write_text('[Desktop Entry]\nType=Application\nName=Export fixture\nExec=/usr/bin/true %F\n')
            entry = menu.Gio.DesktopAppInfo.new_from_filename(str(path))
            with patch.object(menu, 'applications', return_value=[entry]):
                window = menu.StartMenu()
            window.save_favorites([entry.get_id()])
            saved = window.state.read_bytes()
            for category in ('Home', 'All applications'):
                window.category.setCurrentText(category)
                window.list.setCurrentRow(0)
                with patch.object(menu, 'QDrag') as drag:
                    window.list.startDrag(menu.Qt.DropAction.CopyAction)
                    data = drag.return_value.setMimeData.call_args.args[0]
                    self.assertEqual([url.toLocalFile() for url in data.urls()], [str(path)])
                    drag.return_value.exec.assert_called_once_with(menu.Qt.DropAction.CopyAction, menu.Qt.DropAction.CopyAction)
                self.assertEqual(window.state.read_bytes(), saved)
                self.assertTrue(path.is_file())
            shiboken6.delete(window)

    def test_power_arrow_is_centered_at_small_and_large_fonts(self):
        from PySide6.QtGui import QFont
        original = self.app.font()
        try:
            with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
                for size in (10, 16, 20):
                    self.app.setFont(QFont('Sans Serif', size))
                    window = menu.StartMenu()
                    window.show()
                    self.app.processEvents()
                    image = window.power_arrow.grab().toImage()
                    points = [(x,y) for x in range(5,image.width()-5) for y in range(5,image.height()-5)
                              if min(image.pixelColor(x,y).red(), image.pixelColor(x,y).green(), image.pixelColor(x,y).blue()) > 210]
                    self.assertTrue(points)
                    center = sum(x for x,y in points)/len(points)
                    self.assertAlmostEqual(center, (image.width()-1)/2, delta=1, msg=str(size))
                    window.close()
                    shiboken6.delete(window)
        finally:
            self.app.setFont(original)

    def test_recent_limit_migrates_trims_and_preserves_disabled_privacy(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recent.json'
            original = {'enabled': True, 'items': [f'{i}.desktop' for i in range(20)]}
            path.write_text(json.dumps(original))
            recent = menu.RecentPrograms(path)
            recent.save(limit=5)
            self.assertEqual(recent.value['items'], original['items'][:5])
            self.assertEqual(json.loads(next(path.parent.glob('recent.json.backup-*')).read_text()), original)
            recent = menu.RecentPrograms(path)
            recent.save(launched='new.desktop')
            self.assertEqual(recent.value['items'], ['new.desktop'] + original['items'][:4])
            recent.save(limit=30)
            for i in range(40):
                recent.save(launched=f'app-{i}.desktop')
            self.assertEqual(len(menu.RecentPrograms(path).value['items']), 30)
            recent.save(enabled=False)
            recent.save(launched='private.desktop', limit=10)
            self.assertEqual(recent.value['items'], [])
            self.assertFalse(recent.value['enabled'])
            recent.save(clear=True)
            self.assertEqual(recent.value['limit'], 10)

    def test_recent_limit_validation_and_conflicts_preserve_file(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recent.json'
            recent = menu.RecentPrograms(path)
            for invalid in (0, 51, True, 4.5, '10'):
                with self.assertRaises(ValueError):
                    recent.save(limit=invalid)
                self.assertFalse(path.exists())
            for invalid in (0, 51, True, '10'):
                raw = json.dumps({'enabled': True, 'items': [], 'limit': invalid})
                path.write_text(raw)
                corrupt = menu.RecentPrograms(path)
                self.assertIsNotNone(corrupt.error)
                with self.assertRaises(ValueError):
                    corrupt.save(limit=5)
                self.assertEqual(path.read_text(), raw)
            path.write_text('null')
            with self.assertRaises(ValueError):
                recent.save(limit=5)
            self.assertEqual(path.read_text(), 'null')

    def test_unreadable_recent_preferences_do_not_prevent_menu_startup(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            path = Path(directory) / 'lxqt-comfort' / 'recent.json'
            path.mkdir(parents=True)
            window = menu.StartMenu()
            with self.assertRaises(ValueError):
                window.recent.save(limit=5)
            self.assertTrue(path.is_dir())
            window.close()
            shiboken6.delete(window)

    def test_home_shows_ordered_pins_and_opens_recent_separately(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            catalog = []
            for name in ('Alpha', 'Beta', 'Gamma'):
                path = Path(directory) / (name + '.desktop')
                path.write_text(f'[Desktop Entry]\nType=Application\nName={name}\nExec=/bin/true\n')
                catalog.append(menu.Gio.DesktopAppInfo.new_from_filename(str(path)))
            with patch.object(menu, 'applications', return_value=catalog):
                window = menu.StartMenu()
            window.show()
            try:
                window.save_favorites(['Beta.desktop', 'missing.desktop', 'Alpha.desktop'])
                window.recent.save(launched='Gamma.desktop')
                window.refresh()
                self.app.processEvents()
                def rows():
                    return [window.list.item(i).text() for i in range(window.list.count())]
                self.assertTrue(window.pinned_heading.isVisible())
                self.assertEqual(window.pinned_heading.text(), 'Pinned')
                self.assertTrue(window.category.isHidden())
                self.assertEqual(rows(), ['Beta', 'Alpha'])
                self.assertLess(window.list.geometry().bottom(), window.programs.y())
                self.assertLess(window.programs.geometry().bottom(), window.search.y())
                window.recent_button.click()
                self.assertEqual(rows(), ['Gamma'])
                self.assertFalse(window.can_reorder_pins())
                window.programs.click()
                self.assertEqual(rows(), ['Beta', 'Alpha'])
                window.search.setText('Gamma')
                self.assertEqual(rows(), ['Gamma'])
                window.navigate_back()
                window.set_remember(False)
                self.assertTrue(window.recent_button.isHidden())
                self.assertEqual(rows(), ['Beta', 'Alpha'])
            finally:
                window.close()
                shiboken6.delete(window)

    def test_recent_limit_menu_persists_and_restores_check_on_conflict(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = menu.StartMenu()
            choices = {a.data(): a for a in window.recent_counts.actions()}
            choices[5].trigger()
            self.assertEqual(window.recent.value['limit'], 5)
            self.assertEqual(menu.RecentPrograms(window.recent.path).value['limit'], 5)
            window.recent.path.write_text('{"enabled": false, "items": []}')
            with patch.object(window, 'error') as error:
                choices[30].trigger()
                error.assert_called_once()
            self.assertTrue(choices[5].isChecked())
            self.assertFalse(choices[30].isChecked())
            window.close()
            shiboken6.delete(window)

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
            original = window.state.read_bytes()
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
            self.assertEqual(window.state.read_bytes(), original)
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
            self.assertEqual(len(controls), 3)
            self.assertEqual(area.verticalScrollBar().maximum(), 0)
            portrait = window.findChild(menu.QLabel, 'personalStartImage')
            places = window.findChild(menu.QWidget, 'placesPanel')
            self.assertFalse(portrait.pixmap().isNull())
            center = portrait.mapTo(window, portrait.rect().center())
            self.assertTrue(places.mapTo(window, places.rect().topLeft()).x() <= center.x() <= places.mapTo(window, places.rect().topRight()).x())
            frame = window.findChild(menu.QWidget, 'glassFrame')
            self.assertLess(portrait.y(), frame.y())
            self.assertGreater(portrait.y() + portrait.height(), frame.y())
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
            self.assertEqual(window.list.count(), len(window.favorites))
            window.programs.click()
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
            integration_state = home / '.local/state/lxqt-comfort/menu-integration.json'
            integration_state.write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'integration'):
                installer.rollback(home)
            self.assertEqual(old.stat().st_mtime_ns, stamp)
            integration_state.unlink()
            old.write_text('user edit')
            with self.assertRaises(RuntimeError):
                installer.rollback(home)
            old.write_bytes(installer.targets(home)[old][0])
            installer.rollback(home)
            self.assertEqual(old.read_text(), 'previous launcher')
            self.assertEqual(old.stat().st_mode & 0o777, 0o700)
            self.assertFalse((home / '.local/share/applications/lxqt-comfort.desktop').exists())

    def test_interrupted_menu_upgrade_can_retry_or_restore(self):
        for retry in (False, True):
            with self.subTest(retry=retry), tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                installer.install(home, True)
                launcher = home/'.local/bin/lxqt-comfort-menu'
                files = installer.targets(home)
                files[launcher] = (b'updated launcher', 0o755)
                write = installer.atomic
                def fail_launcher(path, *args):
                    if path == launcher:
                        raise OSError('simulated interruption')
                    write(path, *args)
                with patch.object(installer, 'targets', return_value=files):
                    with patch.object(installer, 'atomic', side_effect=fail_launcher), self.assertRaises(OSError):
                        installer.install(home, True)
                    if retry:
                        installer.install(home, True)
                        self.assertEqual(launcher.read_bytes(), files[launcher][0])
                    installer.rollback(home)
                self.assertFalse(launcher.exists())

    def test_integration_preserves_other_settings_and_rolls_back(self):
        from PySide6.QtCore import QSettings
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config = home / '.config/lxqt'
            config.mkdir(parents=True)
            (config / 'panel.conf').write_text('[panel1]\nplugins=fancymenu, dockbarx\n[other]\nkeep=yes\n')
            (config / 'globalkeyshortcuts.conf').write_text('[Alt%2BF1.1]\npath=/panel/fancymenu/show_hide\nEnabled=true\n')
            with self.assertRaisesRegex(RuntimeError, 'Install the Start menu'):
                integration.run(home, apply=True)
            installer.install(home, True)
            integration.run(home, apply=True)
            integration.run(home, apply=True)
            cfg = QSettings(str(config / 'panel.conf'), QSettings.Format.IniFormat)
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
            window.programs.click()
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
