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

    def test_search_and_filter(self):
        data = menu.GLib.KeyFile()
        text = '[Desktop Entry]\nType=Application\nName=Test Editor\nExec=/bin/true\nCategories=Utility;\nKeywords=writing;\n'
        data.load_from_data(text, len(text), 0)
        app = menu.Gio.DesktopAppInfo.new_from_keyfile(data)
        self.assertTrue(menu.matches(app, 'EDITOR writing', 'Utility'))
        self.assertFalse(menu.matches(app, 'editor', 'Game'))
        self.assertFalse(menu.matches(app, 'missing', 'All applications'))

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

    def test_session_button_opens_dialog_only(self):
        window = menu.StartMenu()
        with patch.object(window, 'run_desktop') as launch:
            window.session_button.click()
            launch.assert_called_once_with('lxqt-leave.desktop')
        shiboken6.delete(window)

    def test_symlink_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / '.local').symlink_to('/tmp', target_is_directory=True)
            with self.assertRaises(RuntimeError):
                installer.install(home, True)

if __name__ == '__main__':
    unittest.main()
