import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QLabel
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

    def test_theme_caption_and_wallpaper_controls_keep_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            window = settings.Settings(Path(d))
            choice = window.choices['theme']
            caption = next(label for label in window.findChildren(QLabel) if label.buddy() is choice)
            self.assertEqual(caption.text(), 'Coordinated Doro theme')
            self.assertEqual(choice.currentData(), 'keep')
            self.assertEqual(window.commands(True), [])
            with patch('settings.QProcess') as process:
                window.wallpaper_controls.click()
                process.return_value.startDetached.assert_called_once()
            self.assertFalse((Path(d)/'.config/doroshell/wallpaper.json').exists())
            shiboken6.delete(window)

    def test_live_refresh_never_stops_desktop_components(self):
        from unittest.mock import Mock
        import integrate
        operation = Mock()
        with patch('integrate.os.kill') as kill:
            with self.assertRaisesRegex(RuntimeError, 'output pipes'):
                integrate.live_run(Path.home(), operation=operation)
            operation.assert_not_called()
            kill.assert_not_called()
        integrate.live_run(Path.home(), operation=operation, components=[])
        operation.assert_called_once()

    def test_settings_start_unchanged_and_keyboard_selects_only_opt_in(self):
        with tempfile.TemporaryDirectory() as d:
            window = settings.Settings(Path(d))
            window.show(); self.app.processEvents()
            self.assertEqual(window.commands(True), [])
            window.categories.setCurrentRow(3); self.app.processEvents()
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

    def test_category_pages_preserve_selections_and_cover_every_module(self):
        with tempfile.TemporaryDirectory() as d:
            window = settings.Settings(Path(d))
            window.show(); self.app.processEvents()
            self.assertEqual(set(window.choices), {module for module, _ in settings.OPTIONS})
            window.other_taskbars.click()
            for index, (_, modules_on_page) in enumerate(settings.PAGES):
                window.categories.setCurrentRow(index); self.app.processEvents()
                self.assertEqual(window.pages.currentIndex(), index)
                for module, choice in window.choices.items():
                    self.assertEqual(choice.isVisible(), module in modules_on_page)
            self.assertEqual(window.commands(True), [])
            window.choices['menu'].setCurrentIndex(1)
            window.choices['kate'].setCurrentIndex(1)
            window.categories.setCurrentRow(0)
            self.assertEqual([command[1] for command in window.commands(True)], ['menu', 'kate'])
            self.assertEqual(window.selection_summary.text(), '2 selected changes across all pages')
            window.choices['menu'].setCurrentIndex(0)
            window.choices['kate'].setCurrentIndex(0)
            self.assertEqual(window.selection_summary.text(), 'No changes selected')
            window.close(); shiboken6.delete(window)

    def test_settings_pages_fit_and_results_use_space_only_when_needed(self):
        from PySide6.QtGui import QFont
        with tempfile.TemporaryDirectory() as tmp:
            original=self.app.font()
            try:
                for width,height,points in [(880,650,11),(600,480,16)]:
                    font=QFont(original)
                    font.setPointSize(points)
                    self.app.setFont(font)
                    window=settings.Settings(Path(tmp))
                    try:
                        window.resize(width,height)
                        window.show()
                        for i in range(window.pages.count()):
                            window.categories.setCurrentRow(i)
                            self.app.processEvents()
                            page=window.pages.currentWidget()
                            self.assertEqual(page.horizontalScrollBar().maximum(),0)
                            if width==880:
                                self.assertEqual(page.verticalScrollBar().maximum(),0)
                        self.assertTrue(window.output.isHidden())
                        window.preview.click()
                        self.assertTrue(window.output.isVisible())
                        self.assertIn('No changes selected',window.output.toPlainText())
                        window.output.clear()
                        self.assertTrue(window.output.isHidden())
                    finally:
                        shiboken6.delete(window)
            finally:
                self.app.setFont(original)

    def test_taskbar_sizes_preview_apply_and_restore(self):
        import subprocess, sys
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home/'.local/state/doroshell').mkdir(parents=True)
            (home/'.local/state/doroshell/native-panel.json').write_text('{}')
            panel = home/'.config/doroshell/panel.conf'
            panel.parent.mkdir(parents=True)
            original = '[panel1]\niconSize=25\n[doroshellTasks]\ntype=taskbar\nbuttonWidth=43\n[worldclock]\nshowDate=true\n'
            panel.write_text(original)
            window = settings.Settings(home)
            try:
                choice = window.choices['taskbar-size']
                for size, pixels, width in [('small',20,36), ('medium',28,48), ('large',36,56)]:
                    choice.setCurrentIndex(choice.findData(size))
                    before = panel.read_bytes()
                    subprocess.run([sys.executable, *window.commands(False)[0]], check=True)
                    self.assertEqual(panel.read_bytes(), before)
                    subprocess.run([sys.executable, *window.commands(True)[0]], check=True)
                    text = panel.read_text()
                    self.assertEqual(modules.ini_value(text,'panel1','iconSize'), str(pixels))
                    self.assertEqual(modules.ini_value(text,'doroshellTasks','buttonWidth'), str(width))
                panel.write_text(panel.read_text().replace('buttonWidth=56','buttonWidth=52'))
                with self.assertRaises(RuntimeError):
                    modules.run(home,'taskbar-size',rollback=True)
                panel.write_text(panel.read_text().replace('buttonWidth=52','buttonWidth=56'))
                choice.setCurrentIndex(choice.findData('restore'))
                subprocess.run([sys.executable, *window.commands(True)[0]], check=True)
                self.assertEqual(panel.read_text(), original)
            finally:
                shiboken6.delete(window)

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
            framed = target.with_name('framed-start-icon.png')
            self.assertEqual(QImage(str(framed)).width(),96)
            self.assertEqual(QImage(str(target)).pixelColor(0,0),QColor('pink'))
            self.assertIn('framed-start-icon.png',(home/'.local/share/applications/lxqt-comfort.desktop').read_text())
            install.rollback(home)
            self.assertTrue(icon.exists()); self.assertFalse(target.exists()); self.assertFalse(framed.exists())
