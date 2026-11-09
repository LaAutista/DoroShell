import importlib.util
from pathlib import Path
import tempfile
import unittest
from PySide6.QtCore import QSettings

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_profile',ROOT/'panel/profile.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)

class NativePanelTests(unittest.TestCase):
    def fixture(self,tmp):
        home=Path(tmp);panel=home/'.config/lxqt/panel.conf';panel.parent.mkdir(parents=True)
        panel.write_text('panels=panel1\n[panel1]\nplugins=comfortstart, dockbarx, statusnotifier, worldclock\nposition=Top\n[dockbarx]\ntype=dockbarx\nPersonal=value\n[statusnotifier]\ntype=statusnotifier\nhideList=Old hidden icon\n[worldclock]\ntype=worldclock\ncustomFormat=HH:mm\n')
        launcher=home/'test.desktop';launcher.write_text('[Desktop Entry]\nType=Application\nName=Test\nExec=/bin/true\n')
        return home,panel,launcher

    def test_profile_preserves_widgets_pins_and_hidden_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            home,panel,launcher=self.fixture(tmp);original=panel.read_bytes()
            result=profile.profile(original.decode(),home,[str(launcher)],None)
            out=home/'candidate.conf';out.write_bytes(result);cfg=QSettings(str(out),QSettings.Format.IniFormat)
            self.assertEqual(cfg.value('panel1/plugins'),['comfortstart','doroshellTasks','statusnotifier','worldclock','doroshellShowDesktop'])
            self.assertEqual(cfg.value('worldclock/customFormat'),'HH:mm')
            self.assertEqual(cfg.value('statusnotifier/hideList'),'Old hidden icon')
            self.assertEqual(cfg.value('doroshellTasks/doroshellPinned'),str(launcher))
            self.assertEqual(panel.read_bytes(),original)

    def test_next_login_enable_restore_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            home,panel,launcher=self.fixture(tmp);before=panel.read_bytes();prepared=home/'prepared'
            profile.prepare(home,prepared,Path('/usr/bin/true'),['Test icon'],[str(launcher)])
            target=home/'.config/autostart/lxqt-panel.desktop';target.parent.mkdir(parents=True);target.write_text('personal override\n')
            profile.switch(home,prepared)
            self.assertEqual(panel.read_bytes(),before)
            self.assertIn('doroshell-native-panel',target.read_text())
            with self.assertRaises(RuntimeError):profile.switch(home,prepared)
            installed=target.read_bytes();target.write_text('changed after enable')
            with self.assertRaises(RuntimeError):profile.switch(home,rollback=True)
            self.assertEqual(target.read_text(),'changed after enable')
            target.write_bytes(installed);profile.switch(home,rollback=True)
            self.assertEqual(target.read_text(),'personal override\n')
            self.assertFalse((home/'.config/doroshell/panel.conf').exists())

    def test_changed_source_and_missing_launcher_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            home,panel,launcher=self.fixture(tmp);prepared=home/'prepared'
            profile.prepare(home,prepared,Path('/usr/bin/true'),None,[str(launcher)])
            panel.write_text(panel.read_text()+'\n# user edit\n')
            with self.assertRaises(RuntimeError):profile.switch(home,prepared)
            launcher.unlink()
            with self.assertRaises(ValueError):profile.profile(panel.read_text(),home,[str(launcher)],None)

    def test_symlink_override_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            home,panel,launcher=self.fixture(tmp);prepared=home/'prepared'
            profile.prepare(home,prepared,Path('/usr/bin/true'),None,[str(launcher)])
            target=home/'.config/autostart/lxqt-panel.desktop';target.parent.mkdir(parents=True);target.symlink_to(launcher)
            with self.assertRaises(RuntimeError):profile.switch(home,prepared)
            self.assertTrue(target.is_symlink())
            self.assertFalse((home/'.config/doroshell/panel.conf').exists())

    def test_duplicate_pins_and_ambiguous_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            home,panel,launcher=self.fixture(tmp)
            result=profile.profile(panel.read_text(),home,[str(launcher),str(launcher)],None)
            out=home/'candidate.conf';out.write_bytes(result)
            cfg=QSettings(str(out),QSettings.Format.IniFormat)
            self.assertEqual(cfg.value('doroshellTasks/doroshellPinned'),str(launcher))
            other=home/'other.desktop';other.write_text(launcher.read_text()+'StartupWMClass=test\n')
            with self.assertRaisesRegex(ValueError,'Ambiguous'):
                profile.profile(panel.read_text(),home,[str(launcher),str(other)],None)

    def test_show_desktop_reuses_existing_widget_at_far_right(self):
        with tempfile.TemporaryDirectory() as tmp:
            home,panel,launcher=self.fixture(tmp)
            cfg=QSettings(str(panel),QSettings.Format.IniFormat)
            cfg.setValue('panel1/plugins',['comfortstart','oldDesktop','dockbarx','statusnotifier','worldclock'])
            cfg.setValue('oldDesktop/type','showdesktop');cfg.setValue('oldDesktop/customValue','keep');cfg.sync()
            original=panel.read_bytes()
            out=home/'candidate.conf';out.write_bytes(profile.profile(original.decode(),home,[str(launcher)],None))
            result=QSettings(str(out),QSettings.Format.IniFormat)
            self.assertEqual(result.value('panel1/plugins')[-1],'oldDesktop')
            self.assertEqual(result.value('oldDesktop/customValue'),'keep')
            self.assertEqual(result.value('oldDesktop/alignment'),'Right')
            self.assertTrue(result.value('oldDesktop/doroshellEdge',type=bool))
            self.assertNotIn('doroshellShowDesktop',result.value('panel1/plugins'))
            self.assertEqual(panel.read_bytes(),original)

    def test_show_desktop_name_conflict_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            home,panel,launcher=self.fixture(tmp)
            cfg=QSettings(str(panel),QSettings.Format.IniFormat)
            cfg.setValue('doroshellShowDesktop/type','customcommand');cfg.sync()
            original=panel.read_bytes()
            with self.assertRaisesRegex(ValueError,'widget name conflict'):
                profile.profile(original.decode(),home,[str(launcher)],None)
            self.assertEqual(panel.read_bytes(),original)
