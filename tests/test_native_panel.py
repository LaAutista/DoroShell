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

    def test_stock_panel_needs_no_dockbarx_and_keeps_notifier_name_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, panel, launcher = self.fixture(tmp)
            stock = '[panel1]\nplugins=fancymenu, taskbar, worldclock\n'
            panel.write_text(stock)
            start = home/'.local/share/applications/lxqt-comfort.desktop'
            start.parent.mkdir(parents=True)
            start.write_bytes(launcher.read_bytes())
            profile.prepare(home, home/'stock', Path('/usr/bin/true'))
            cfg = QSettings(str(home/'stock/panel.conf'), QSettings.Format.IniFormat)
            self.assertEqual(cfg.value('panel1/plugins')[:2], ['doroshellStart', 'fancymenu'])
            self.assertEqual(cfg.value('doroshellStart/apps/1/desktop'), str(start))
            self.assertIn('doroshellNotifier', cfg.value('panel1/plugins'))
            self.assertEqual(panel.read_text(), stock)
            panel.write_text(stock + '[doroshellNotifier]\ntype=quicklaunch\n')
            with self.assertRaisesRegex(ValueError, 'widget name conflict'):
                profile.prepare(home, home/'conflict', Path('/usr/bin/true'))
            self.assertFalse((home/'conflict').exists())

    def quicklaunch_fixture(self, home):
        apps = home/'apps'; apps.mkdir()
        for name in ('alpha', 'beta'):
            (apps/(name+'.desktop')).write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec=/bin/true\n')
        (apps/'folder.desktop').write_text('[Desktop Entry]\nType=Link\nName=Folder\nURL=file:///tmp\n')
        return apps

    def test_stock_quicklaunch_apps_become_taskbar_pins(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp); apps = self.quicklaunch_fixture(home)
            raw = ('[panel1]\nplugins=fancymenu, quicklaunch, taskbar, worldclock\n[quicklaunch]\n'
                   'apps\\1\\desktop='+str(apps/'alpha.desktop')+'\napps\\2\\desktop='+str(apps/'folder.desktop')+
                   '\napps\\3\\desktop='+str(apps/'beta.desktop')+'\napps\\4\\desktop='+str(apps/'alpha.desktop')+
                   '\napps\\5\\desktop='+str(apps/'missing.desktop')+'\napps\\size=5\n')
            out = home/'out.conf'; out.write_bytes(profile.profile(raw, home, [], None))
            cfg = QSettings(str(out), QSettings.Format.IniFormat)
            self.assertEqual(cfg.value('doroshellTasks/doroshellPinned'), [str(apps/'alpha.desktop'), str(apps/'beta.desktop')])
            # Non-application and unavailable launchers stay where the user put them.
            self.assertIn('quicklaunch', cfg.value('panel1/plugins'))
            self.assertEqual(cfg.value('quicklaunch/apps/size', type=int), 2)
            self.assertEqual(cfg.value('quicklaunch/apps/1/desktop'), str(apps/'folder.desktop'))
            self.assertEqual(cfg.value('quicklaunch/apps/2/desktop'), str(apps/'missing.desktop'))
            # An all-application Quick Launch disappears entirely.
            raw = '[panel1]\nplugins=quicklaunch, taskbar\n[quicklaunch]\napps\\1\\desktop='+str(apps/'beta.desktop')+'\napps\\size=1\n'
            out.write_bytes(profile.profile(raw, home, [], None))
            cfg = QSettings(str(out), QSettings.Format.IniFormat)
            self.assertNotIn('quicklaunch', cfg.value('panel1/plugins'))
            self.assertNotIn('quicklaunch', cfg.childGroups())
            self.assertEqual(cfg.value('doroshellTasks/doroshellPinned'), str(apps/'beta.desktop'))

    def test_merge_existing_profile_backs_up_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp); apps = self.quicklaunch_fixture(home)
            config = home/'.config/doroshell/panel.conf'; config.parent.mkdir(parents=True)
            original = ('[panel1]\nplugins=doroshellStart, quicklaunch, doroshellTasks\n[doroshellStart]\ntype=quicklaunch\n'
                        'apps\\1\\desktop='+str(apps/'folder.desktop')+'\napps\\size=1\n[quicklaunch]\ntype=quicklaunch\n'
                        'apps\\1\\desktop='+str(apps/'alpha.desktop')+'\napps\\2\\desktop='+str(apps/'beta.desktop')+
                        '\napps\\size=2\n[doroshellTasks]\ntype=taskbar\ndoroshellPinned='+str(apps/'beta.desktop')+'\n')
            config.write_text(original); config.chmod(0o600)
            profile.merge_existing(home, preview=True)
            self.assertEqual(config.read_text(), original)
            profile.merge_existing(home)
            cfg = QSettings(str(config), QSettings.Format.IniFormat)
            self.assertEqual(cfg.value('panel1/plugins'), ['doroshellStart', 'doroshellTasks'])
            self.assertEqual(cfg.value('doroshellTasks/doroshellPinned'), [str(apps/'beta.desktop'), str(apps/'alpha.desktop')])
            self.assertEqual(cfg.value('doroshellStart/apps/1/desktop'), str(apps/'folder.desktop'))
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            backups = list((home/'.local/state/doroshell').glob('panel-before-merge-*.conf'))
            self.assertEqual(len(backups), 1); self.assertEqual(backups[0].read_text(), original)
            merged = config.read_bytes(); profile.merge_existing(home)
            self.assertEqual(config.read_bytes(), merged)
            self.assertEqual(len(list((home/'.local/state/doroshell').glob('panel-before-merge-*.conf'))), 1)

    def test_merge_keeps_start_launcher_and_restore_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp); apps = self.quicklaunch_fixture(home)
            start = home/'.local/share/applications/lxqt-comfort.desktop'; start.parent.mkdir(parents=True)
            start.write_text('[Desktop Entry]\nType=Application\nName=DoroShell Start\nExec=/bin/true\n')
            panel = home/'.config/lxqt/panel.conf'; panel.parent.mkdir(parents=True)
            # integrate.py layout: Start lives in its own quicklaunch; apps in the stock one.
            panel.write_text('[panel1]\nplugins=comfortstart, quicklaunch, taskbar\n[comfortstart]\ntype=quicklaunch\n'
                             'apps\\1\\desktop='+str(start)+'\napps\\size=1\n[quicklaunch]\napps\\1\\desktop='+str(start)+
                             '\napps\\2\\desktop='+str(apps/'alpha.desktop')+'\napps\\size=2\n')
            original = panel.read_bytes()
            profile.prepare(home, home/'prepared', Path('/usr/bin/true'))
            cfg = QSettings(str(home/'prepared/panel.conf'), QSettings.Format.IniFormat)
            self.assertEqual(cfg.value('doroshellTasks/doroshellPinned'), str(apps/'alpha.desktop'))
            self.assertIn('comfortstart', cfg.value('panel1/plugins'))
            self.assertEqual(cfg.value('comfortstart/apps/1/desktop'), str(start))
            self.assertEqual(cfg.value('quicklaunch/apps/1/desktop'), str(start))  # Start never becomes a pin
            profile.switch(home, home/'prepared')
            # A merge of a DoroShell-owned profile keeps the manifest consistent.
            config = home/'.config/doroshell/panel.conf'
            cfg = QSettings(str(config), QSettings.Format.IniFormat)
            cfg.setValue('quicklaunch/apps/2/desktop', str(apps/'beta.desktop')); cfg.setValue('quicklaunch/apps/size', 2); cfg.sync()
            import json, hashlib
            manifest = home/'.local/state/doroshell/native-panel.json'; record = json.loads(manifest.read_text())
            record['.config/doroshell/panel.conf']['after'] = hashlib.sha256(config.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(record))
            profile.merge_existing(home)
            record = json.loads(manifest.read_text())
            self.assertEqual(record['.config/doroshell/panel.conf']['after'], hashlib.sha256(config.read_bytes()).hexdigest())
            self.assertNotIn('pending_after', record['.config/doroshell/panel.conf'])
            profile.switch(home, rollback=True)  # no --keep-panel-edits needed
            self.assertEqual(panel.read_bytes(), original)
            self.assertFalse(config.exists())

    def test_merge_leaves_empty_unknown_and_unmoved_widgets_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp); apps = self.quicklaunch_fixture(home)
            for body in ('apps\\size=0\n',
                         'apps\\1\\desktop='+str(apps/'alpha.desktop')+'\napps\\extra=1\napps\\size=1\n',
                         'apps\\1\\desktop='+str(apps/'folder.desktop')+'\napps\\size=1\n'):
                raw = '[panel1]\nplugins=quicklaunch, taskbar\n[quicklaunch]\n'+body
                out = home/'out.conf'; out.write_bytes(profile.profile(raw, home, [], None))
                cfg = QSettings(str(out), QSettings.Format.IniFormat)
                self.assertIn('quicklaunch', cfg.value('panel1/plugins'))
                original = QSettings(str(home/'raw.conf'), QSettings.Format.IniFormat)
                (home/'raw.conf').write_text(raw); original = QSettings(str(home/'raw.conf'), QSettings.Format.IniFormat)
                self.assertEqual({k: cfg.value(k) for k in cfg.allKeys() if k.startswith('quicklaunch/apps')},
                                 {k: original.value(k) for k in original.allKeys() if k.startswith('quicklaunch/apps')})

    def test_merge_refuses_symlinked_state(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            home = Path(tmp)
            config = home/'.config/doroshell/panel.conf'; config.parent.mkdir(parents=True)
            config.write_text('[panel1]\nplugins=doroshellTasks\n[doroshellTasks]\ntype=taskbar\n')
            (home/'.local/state').mkdir(parents=True); (home/'.local/state/doroshell').symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError, 'symlink'):
                profile.merge_existing(home)

    def test_standalone_profile_loads_inherited_clock_and_tray_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for clock in ('', ', worldclock'):
                raw = '[panel1]\nplugins=taskbar, statusnotifier, volume'+clock+'\n'
                path = home/('existing.conf' if clock else 'new.conf')
                path.write_bytes(profile.profile(raw, home, [], None))
                cfg = QSettings(str(path), QSettings.Format.IniFormat)
                widgets = cfg.value('panel1/plugins')
                self.assertTrue(all(cfg.value(name+'/type') for name in widgets))
                clock_name = widgets[-2]
                self.assertEqual(cfg.value(clock_name+'/type'), 'worldclock')
                self.assertEqual(cfg.value(clock_name+'/alignment'), 'Right')
                self.assertTrue(cfg.value(clock_name+'/showDate', type=bool))
                self.assertEqual(cfg.value(clock_name+'/datePosition'), 'below')
                self.assertTrue(cfg.value('statusnotifier/doroshellCollapseNew', type=bool))

    def test_next_login_enable_restore_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            home,panel,launcher=self.fixture(tmp);before=panel.read_bytes();prepared=home/'prepared'
            profile.prepare(home,prepared,Path('/usr/bin/true'),['Test icon'],[str(launcher)])
            target=home/'.config/autostart/lxqt-panel.desktop';target.parent.mkdir(parents=True);target.write_text('personal override\n')
            profile.switch(home,prepared)
            self.assertEqual(panel.read_bytes(),before)
            self.assertIn('doroshell-native-panel',target.read_text())
            original_manifest=(home/'.local/state/doroshell/native-panel.json').read_bytes()
            profile.switch(home,prepared)
            self.assertEqual((home/'.local/state/doroshell/native-panel.json').read_bytes(), original_manifest)
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

    def test_interrupted_switch_can_restore_original_autostart(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            home, panel, launcher = self.fixture(tmp)
            prepared = home/'prepared'
            profile.prepare(home, prepared, Path('/usr/bin/true'), None, [str(launcher)])
            target = home/'.config/autostart/lxqt-panel.desktop'
            target.parent.mkdir(parents=True)
            target.write_text('original')
            real_atomic = profile.atomic
            def fail_wrapper(path, *args):
                if path.name == 'doroshell-native-panel':
                    raise OSError('simulated interrupted write')
                real_atomic(path, *args)
            with patch.object(profile, 'atomic', side_effect=fail_wrapper), self.assertRaises(OSError):
                profile.switch(home, prepared)
            profile.switch(home, rollback=True)
            self.assertEqual(target.read_text(), 'original')
            self.assertFalse((home/'.config/doroshell/panel.conf').exists())
            self.assertFalse((home/'.local/state/doroshell/native-panel.json').exists())

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
