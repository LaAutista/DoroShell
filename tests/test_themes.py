import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import shiboken6
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap, QIcon
from PySide6.QtTest import QTest
import modules
import themes
from menu.start_menu import StartMenu
from test_readability import contrast


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def seed(self, home):
        configs = {
            '.config/openbox/rc.xml': '<openbox_config><theme><name>Original</name><titleLayout>NLIMC</titleLayout></theme><desktops><number>2</number></desktops></openbox_config>',
            '.config/katerc': '[UiSettings]\nColorScheme=Old\n[Personal]\nRecentFile=example\n',
            '.config/dolphinrc': '[General]\nViewMode=Details\n',
            '.config/lxqt/lxqt.conf': '[General]\nicon_theme=breeze\n[Qt]\nfont=Custom\n',
            '.config/mimeapps.list': '[Default Applications]\ninode/directory=personal.desktop;\n'}
        for name, value in configs.items():
            path = home/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
            path.chmod(0o640)
        return {home/k: (v.encode(), 0o640) for k,v in configs.items()}

    def test_theme_name_targets_direct_child_and_preserves_fonts_comments(self):
        edit = {'kind': 'obtheme'}
        for namespace in ('', ' xmlns="http://openbox.org/3.4/rc"'):
            before = ('<openbox_config'+namespace+'><theme>\n'
                      '<!-- <name>Comment is not a setting</name> -->\n'
                      '<font place="ActiveWindow"><name>Sans</name><size>10</size></font>\n'
                      '<name>Clearlooks</name>\n'
                      '<font place="MenuItem"><name>Déjà Vu</name></font>\n'
                      '</theme></openbox_config>').encode()
            self.assertEqual(modules.read_value(edit, before), 'Clearlooks')
            after = modules.write_value(edit, before, 'DoroShell')
            self.assertEqual(after, before.replace(b'<name>Clearlooks</name>', b'<name>DoroShell</name>'))
            self.assertEqual(modules.write_value(edit, after, 'Clearlooks'), before)
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); self.seed(home)
            path=home/'.config/openbox/rc.xml'; path.write_bytes(before)
            modules.run(home,'theme',apply=True,theme='heretic')
            self.assertEqual(path.read_bytes(), before.replace(b'<name>Clearlooks</name>', b'<name>DoroShell</name>'))
            modules.run(home,'theme',rollback=True)
            self.assertEqual(path.read_bytes(),before)

    def test_theme_duplicate_direct_names_refused_and_empty_name_supported(self):
        edit={'kind':'obtheme'}
        with self.assertRaisesRegex(RuntimeError, 'Expected one Openbox theme name'):
            modules.read_value(edit,b'<openbox_config><theme><name>A</name><name>B</name></theme></openbox_config>')
        data=b'<openbox_config><theme><name/><font><name>Sans</name></font></theme></openbox_config>'
        self.assertEqual(modules.read_value(edit,data),'')
        self.assertEqual(modules.read_value(edit,modules.write_value(edit,data,'DoroShell')),'DoroShell')

    def test_four_theme_switch_repeat_restore_preserve_personal_values(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            baseline = self.seed(home)
            for name in themes.PALETTES:
                modules.run(home,'theme',apply=True,theme=name)
                record = (home/'.local/state/doroshell/theme.json').read_bytes()
                modules.run(home,'theme',apply=True,theme=name)
                self.assertEqual(record,(home/'.local/state/doroshell/theme.json').read_bytes())
                self.assertIn('RecentFile=example',(home/'.config/katerc').read_text())
                self.assertIn('titleLayout>NLIMC',(home/'.config/openbox/rc.xml').read_text())
            modules.run(home,'theme',rollback=True)
            for p,(data,mode) in baseline.items():
                self.assertEqual(p.read_bytes(),data)
                self.assertEqual(p.stat().st_mode&0o777,mode)
            for path in themes.theme_files(themes.PALETTES['spring']):
                self.assertFalse((home/path).exists())

    def test_conflict_preflight_changes_nothing_and_unrelated_edit_survives(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            self.seed(home)
            modules.run(home,'theme',apply=True)
            kate = home/'.config/katerc'
            kate.write_text(kate.read_text().replace('RecentFile=example','RecentFile=new'))
            modules.run(home,'theme',rollback=True)
            self.assertIn('RecentFile=new',kate.read_text())
            modules.run(home,'theme',apply=True)
            kate.write_text(kate.read_text().replace('ColorScheme=DoroShell','ColorScheme=Personal'))
            before = {str(p):p.read_bytes() for p in home.rglob('*') if p.is_file()}
            for kwargs in ({'apply':True,'theme':'polar'},{'rollback':True}):
                with self.assertRaisesRegex(RuntimeError,'Personal edit'):
                    modules.run(home,'theme',**kwargs)
                self.assertEqual(before,{str(p):p.read_bytes() for p in home.rglob('*') if p.is_file()})

    def test_overlapping_app_theme_requires_reverse_restore(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);self.seed(home)
            modules.run(home,'kate-dark',apply=True)
            modules.run(home,'theme',apply=True)
            with self.assertRaisesRegex(RuntimeError,'Personal edit'):
                modules.run(home,'kate-dark',rollback=True)
            modules.run(home,'theme',rollback=True)
            self.assertIn('ColorScheme=BreezeDark',(home/'.config/katerc').read_text())
            modules.run(home,'kate-dark',rollback=True)
            self.assertIn('ColorScheme=Old',(home/'.config/katerc').read_text())

    def test_failed_switch_restores_previous_theme_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);self.seed(home)
            modules.run(home,'theme',apply=True)
            before={str(p):p.read_bytes() for p in home.rglob('*') if p.is_file()}
            write=modules.atomic
            calls=0
            def fail_once(*args,**kwargs):
                nonlocal calls
                calls += 1
                if calls == 5:
                    raise OSError('simulated disk failure')
                return write(*args,**kwargs)
            with patch.object(modules,'atomic',side_effect=fail_once):
                with self.assertRaises(OSError):
                    modules.run(home,'theme',apply=True,theme='heretic')
            self.assertEqual(before,{str(p):p.read_bytes() for p in home.rglob('*') if p.is_file()})
            calls = 3
            with patch.object(modules,'atomic',side_effect=fail_once):
                with self.assertRaises(OSError):
                    modules.run(home,'theme',rollback=True)
            self.assertEqual(before,{str(p):p.read_bytes() for p in home.rglob('*') if p.is_file()})
            modules.run(home,'theme',rollback=True)

    def test_generated_asset_conflict_and_new_config_personal_edit(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            (home/'.config/openbox').mkdir(parents=True)
            (home/'.config/openbox/rc.xml').write_text('<openbox_config></openbox_config>')
            modules.run(home, 'theme', apply=True)
            kate = home/'.config/katerc'
            kate.write_text(kate.read_text() + '\n[Personal]\nKeep=yes\n')
            asset = home/'.config/doroshell/start-theme.qss'
            expected = asset.read_bytes()
            asset.write_bytes(expected + b'/* custom */')
            with self.assertRaisesRegex(RuntimeError, 'Personal edit'):
                modules.run(home, 'theme', rollback=True)
            asset.write_bytes(expected)
            modules.run(home, 'theme', rollback=True)
            self.assertIn('Keep=yes', kate.read_text())
            self.assertNotIn('DoroShell', kate.read_text())

    def test_symbolic_controls_follow_foreground_in_all_palettes(self):
        black = QPixmap(32, 32)
        black.fill(QColor('black'))
        for name, palette in themes.PALETTES.items():
            with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
                path = Path(directory)/'doroshell/start-theme.qss'
                path.parent.mkdir()
                path.write_text(themes.menu_style(palette))
                with patch('menu.start_menu.QIcon.fromTheme', return_value=QIcon(black)):
                    menu = StartMenu()
                    controls = [(menu.search_action.icon(), palette['ink']),
                                (menu.programs.icon(), palette['ink']),
                                (menu.session_button.icon(), '#fff5fb')]
                    controls += [(action.icon(), palette['ink']) for action in menu.power_menu.actions()[:5]]
                    menu.category.setCurrentText('All applications')
                    controls.append((menu.programs.icon(), palette['ink']))
                for icon, expected in controls:
                    self.assertEqual(icon.pixmap(32, 32).toImage().pixelColor(16, 16).name(), expected, name)
                shiboken6.delete(menu)

    def test_palette_contrast(self):
        for p in themes.PALETTES.values():
            decoration = themes.theme_files(p)['.local/share/themes/DoroShell/openbox-3/themerc']
            self.assertIn('window.active.client.color: '+p['window'], decoration)
            self.assertIn('window.inactive.client.color: '+p['window'], decoration)
            for bg in ('base','window','selection'):
                self.assertGreaterEqual(contrast(p['ink'],p[bg]),4.5,(p['name'],bg))
            for bg in ('base','window'):
                self.assertGreaterEqual(contrast(p['muted'],p[bg]),4.5,(p['name'],bg))
            self.assertGreaterEqual(contrast('#fff5fb',p['side']),4.5,p['name'])

    def test_panel_theme_overrides_every_hardcoded_patch_color(self):
        # Patch 0001's built-in sheet uses the light Windows palette; the theme file loads after it and must
        # override every colored selector, or dark presets show light text on light popups.
        import re
        patch=(Path(__file__).resolve().parents[1]/'panel/patches/0001-hidden-tray-popup.patch').read_text()
        def rules(css):
            for selectors,body in re.findall(r'([^{}]+)\{([^{}]*)\}',css):
                yield [x.strip() for x in selectors.split(',')],body
        hardcoded=set()
        for line in re.findall(r'sheet << QStringLiteral\("(.*)"\);',patch):
            for selectors,body in rules(line.replace('\\"','"')):
                colored=re.search(r'(?:^|;)\s*(?:background|color)\s*:\s*(?!transparent)',body)
                if colored and 'background-image' not in body:
                    hardcoded.update(selectors)
        self.assertIn('LXQtGroupPopup',hardcoded)
        for name,p in themes.PALETTES.items():
            for composited in (False,True):
                covered={x for selectors,_ in rules(themes.panel_style(p,composited)) for x in selectors}
                self.assertEqual(hardcoded-covered,set(),(name,composited))
            popup=next(b for s,b in rules(themes.panel_style(p)) if s==['LXQtGroupPopup'])
            self.assertIn(p['base'],popup)
            self.assertGreaterEqual(contrast(p['ink'],p['base']),4.5,name)  # Popup task text.
            self.assertGreaterEqual(contrast(p['ink'],p['selection']),4.5,name)  # Hovered/checked task text.
    def test_portrait_click_opens_picker_cancel_and_save_independent(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'XDG_CONFIG_HOME':d,'XDG_DATA_HOME':d}):
            path = Path(d)/'portrait.png'
            pix=QPixmap(32,32);pix.fill(QColor('green'));pix.save(str(path))
            menu=StartMenu();menu.show();self.app.processEvents()
            settings=menu.folder_settings.path
            with patch('menu.start_menu.QFileDialog.getOpenFileName',return_value=('','')) as picker:
                QTest.mouseClick(menu.mascot,Qt.MouseButton.LeftButton)
                picker.assert_called_once()
            self.assertFalse(settings.exists())
            self.assertTrue(menu.isVisible())
            with patch('menu.start_menu.QFileDialog.getOpenFileName',return_value=(str(path),'')), patch('menu.start_menu.PortraitCropDialog.exec',return_value=1):
                QTest.mouseClick(menu.mascot,Qt.MouseButton.LeftButton)
            self.assertEqual(json.loads(settings.read_text())['portrait'],str(path))
            self.assertTrue(menu.isVisible())
            self.assertEqual(menu.mascot.pixmap().toImage().pixelColor(10,10),QColor('green'))
            shiboken6.delete(menu)
