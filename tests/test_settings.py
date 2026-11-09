import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import shiboken6
import settings
import modules
import install


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_start_unchanged_and_keyboard_selects_only_opt_in(self):
        with tempfile.TemporaryDirectory() as d:
            window = settings.Settings(Path(d))
            window.show(); self.app.processEvents()
            self.assertEqual(window.commands(True), [])
            choice=window.choices['kate']; choice.setFocus()
            QTest.keyClick(choice, Qt.Key.Key_Down)
            commands=window.commands(True)
            self.assertEqual(len(commands),1)
            self.assertEqual(commands[0][1],'kate')
            self.assertIn('--apply',commands[0])
            window.choices['taskbar'].setCurrentIndex(2)
            self.assertIn('standard',window.commands(True)[0])
            self.assertFalse(window.live.isChecked())
            window.close(); shiboken6.delete(window)

    def test_defaults_and_dark_repeat_restore_preserve_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); conf=home/'.config'; conf.mkdir()
            mime=conf/'mimeapps.list'; mime.write_text('[Default Applications]\ntext/plain=old.desktop;\ninode/directory=files.desktop;\n')
            kate=conf/'katerc'; kate.write_text('[UiSettings]\nColorScheme=Light\n[Other]\nKeep=yes\n')
            original=mime.read_bytes(); original_kate=kate.read_bytes()
            for module in ('kate','dolphin','kate-dark','dolphin-dark'):
                modules.run(home,module,apply=True); modules.run(home,module,apply=True)
            self.assertIn('ColorScheme=BreezeDark',kate.read_text())
            self.assertIn('text/plain=org.kde.kate.desktop;',mime.read_text())
            for module in ('dolphin-dark','kate-dark','dolphin','kate'):
                modules.run(home,module,rollback=True)
            self.assertEqual(mime.read_bytes(),original)
            self.assertEqual(kate.read_bytes(),original_kate)

    def test_taskbar_switch_and_repeat_restore_created_plugin(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); panel=home/'.config/lxqt/panel.conf';panel.parent.mkdir(parents=True)
            original='[panel1]\nplugins=fancymenu, dockbarx, tray\n[dockbarx]\ntype=dockbarx\ncustom=keep\n'
            panel.write_text(original)
            modules.run(home,'taskbar',apply=True)
            self.assertIn('buttonStyle=Icon\n',panel.read_text())
            modules.run(home,'taskbar',apply=True,taskbar_style='standard')
            self.assertIn('buttonStyle=IconText',panel.read_text())
            modules.run(home,'taskbar',apply=True,taskbar_style='standard')
            modules.run(home,'taskbar',rollback=True)
            self.assertEqual(panel.read_text(),original)

    def test_desktop_count_scoped_and_firstdesk_restored(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); path=home/'.config/openbox/rc.xml';path.parent.mkdir(parents=True)
            original='<openbox_config><desktops><number>4</number><firstdesk>3</firstdesk></desktops><other><number>7</number></other></openbox_config>'
            path.write_text(original)
            modules.run(home,'single-desktop',apply=True)
            self.assertIn('<firstdesk>1</firstdesk>',path.read_text())
            self.assertIn('<other><number>7</number></other>',path.read_text())
            modules.run(home,'single-desktop',rollback=True)
            self.assertEqual(path.read_text(),original)

    def test_personal_icon_retained_and_rollback_restores_original(self):
        from PySide6.QtGui import QImage, QColor
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); icon=home/'personal.png'
            image=QImage(32,32,QImage.Format.Format_ARGB32);image.fill(QColor('pink'));image.save(str(icon))
            install.install(home,True,icon)
            target=home/'.local/share/lxqt-comfort/start-icon.png'
            self.assertTrue(target.exists())
            install.install(home,True)
            self.assertIn('start-icon.png',(home/'.local/share/applications/lxqt-comfort.desktop').read_text())
            install.rollback(home)
            self.assertTrue(icon.exists()); self.assertFalse(target.exists())
