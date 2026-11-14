"""Explicit multi-panel preparation and reversible staging; no panel is launched."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings

import deploy
import install
import modules
from panel import layout, profile


class PanelSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.stock = self.home/'.config/lxqt/panel.conf'; self.stock.parent.mkdir(parents=True)
        self.original = ('; fixture global comment\n[General]\npanels=panel1, panel2\ncustom=keep\n\n'
                         '[panel1]\n; preserve this exact spacing\nplugins=taskOne, trayOne, clockOne\n'
                         'position=Top\npanelSize=31\niconSize=19\n\n'
                         '[taskOne]\ntype=taskbar\nbuttonWidth=77\n\n'
                         '[trayOne]\ntype=statusnotifier\nhideList=untouched\n\n'
                         '[clockOne]\ntype=worldclock\ncustomFormat=HH:mm\n\n'
                         '[panel2]\nplugins=taskTwo, trayTwo, clockTwo\nposition=Left\n'
                         'panelSize=47\niconSize=23\nlineCount=2\n\n'
                         '[taskTwo]\ntype=taskbar\n\n[trayTwo]\ntype=statusnotifier\n\n'
                         '[clockTwo]\ntype=worldclock\ncustomFormat=hh:mm:ss\n\n'
                         '[UnknownWidget]\ncustom = keep spaces\n')
        self.stock.write_bytes(self.original.encode()); self.stock.chmod(0o640)
        self.prepared = self.home/'prepared'
        self.config = self.home/'.config/doroshell/panel.conf'
        self.wrapper = self.home/'.local/bin/doroshell-native-panel'
        self.autostart = self.home/'.config/autostart/lxqt-panel.desktop'
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def prepare(self, selected='panel2'):
        profile.prepare(self.home, self.prepared, Path('/usr/bin/true'), panel=selected)

    def snapshot(self):
        return {str(p.relative_to(self.home)): (p.read_bytes(), p.stat().st_mode & 0o777)
                for p in self.home.rglob('*') if p.is_file()}

    def test_explicit_selection_preserves_other_sections_and_chosen_geometry(self):
        for selected, untouched in [('panel2', ['panel1', 'taskOne', 'trayOne', 'clockOne']),
                                    ('panel1', ['panel2', 'taskTwo', 'trayTwo', 'clockTwo'])]:
            with self.subTest(selected=selected):
                content = profile.profile(self.original, self.home, [], None, panel=selected)
                before = layout.sections(self.original)[1]; after = layout.sections(content.decode())[1]
                for name in [*untouched, 'General', 'UnknownWidget']:
                    self.assertEqual(after[name], before[name], name)
                path = self.home/'candidate.conf'; path.write_bytes(content)
                cfg = QSettings(str(path), QSettings.Format.IniFormat)
                self.assertIn('doroshellTasks', cfg.value(selected+'/plugins'))
                self.assertEqual(cfg.value(selected+'/position'), 'Left' if selected == 'panel2' else 'Top')
                self.assertEqual(cfg.value(selected+'/panelSize'), '47' if selected == 'panel2' else '31')
                self.assertEqual(layout.installed_panel(content.decode()), selected)
                self.assertEqual(self.stock.read_bytes(), self.original.encode())

    def test_missing_wrong_shared_or_ambiguous_selection_refuses_without_output(self):
        cases = [(self.original, None), (self.original, 'panel9'), (self.original, '../panel2'),
                 (self.original, 'panel2\n[other]'),
                 (self.original.replace('plugins=taskTwo,', 'plugins=taskOne,'), 'panel2'),
                 (self.original.replace('[taskOne]\ntype=taskbar', '[taskOne]\ncustom=unknown'), 'panel2'),
                 (self.original+'\n[panel2]\nplugins=taskTwo\n', 'panel2'),
                 (self.original.replace('taskOne', 'doroshellTasks'), 'panel2'),
                 (self.original+'\n[doroshellTasks]\ntype=taskbar\n', 'panel2'),
                 (self.original.replace('[UnknownWidget]', '[Unknown%20Widget]'), 'panel2'),
                 (self.original.replace('[UnknownWidget]', ' [UnknownWidget]'), 'panel2'),
                 (self.original.replace('panels=panel1, panel2', 'panels=panel2'), 'panel2')]
        for text, selected in cases:
            with self.subTest(selected=selected, text=text):
                self.stock.write_text(text); before = self.snapshot()
                with self.assertRaises(ValueError): self.prepare(selected)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(self.prepared.exists())

    def test_changed_source_or_different_prepared_selection_cannot_replace_staged_profile(self):
        self.prepare(); profile.switch(self.home, self.prepared)
        other = self.home/'other-plan'
        profile.prepare(self.home, other, Path('/usr/bin/true'), panel='panel1')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'Another switch'): profile.switch(self.home, other)
        self.assertEqual(self.snapshot(), before)
        self.stock.write_bytes(self.original.encode()+b'\n; later unrelated panel edit\n'); before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'prepare again'): profile.switch(self.home, self.prepared)
        self.assertEqual(self.snapshot(), before)

    def test_ambiguous_installed_owner_blocks_companion_writes(self):
        self.prepare(); profile.switch(self.home, self.prepared)
        text = self.config.read_text().replace('plugins=taskOne,', 'plugins=doroshellTasks,')
        self.config.write_text(text); before = self.snapshot()
        for module in ('clipboard', 'taskbar-size'):
            with self.assertRaises(ValueError): modules.run(self.home, module, apply=True)
            self.assertEqual(self.snapshot(), before)

    def test_repeated_staging_preview_and_exact_baseline_restore(self):
        self.config.parent.mkdir(parents=True); self.config.write_bytes(b'original private profile'); self.config.chmod(0o640)
        self.autostart.parent.mkdir(parents=True); self.autostart.write_bytes(b'original override'); self.autostart.chmod(0o644)
        originals = self.snapshot(); self.prepare()
        before = self.snapshot(); profile.switch(self.home, self.prepared, preview=True)
        self.assertEqual(self.snapshot(), before)
        profile.switch(self.home, self.prepared); installed = self.snapshot()
        profile.switch(self.home, self.prepared); self.assertEqual(self.snapshot(), installed)
        profile.switch(self.home, rollback=True)
        for name, value in originals.items(): self.assertEqual(self.snapshot()[name], value)
        self.assertFalse(self.wrapper.exists())

    def test_interruption_retry_and_later_edit_refusal_preserve_originals(self):
        self.prepare(); real = profile.atomic
        def fail(path, *args):
            if path == self.wrapper: raise OSError('fixture interruption')
            return real(path, *args)
        with patch.object(profile, 'atomic', side_effect=fail), self.assertRaises(OSError):
            profile.switch(self.home, self.prepared)
        manifest = self.home/'.local/state/doroshell/native-panel.json'; saved = manifest.read_bytes()
        original = self.config.read_bytes(); self.config.write_bytes(original+b'\n# later edit\n'); before = self.snapshot()
        with self.assertRaises(RuntimeError): profile.switch(self.home, self.prepared)
        self.assertEqual(self.snapshot(), before)
        self.config.write_bytes(original); profile.switch(self.home, self.prepared)
        self.assertEqual(manifest.read_bytes(), saved)
        profile.switch(self.home, rollback=True)
        self.assertFalse(self.config.exists()); self.assertFalse(self.wrapper.exists())
        self.assertEqual(self.stock.read_bytes(), self.original.encode())

    def test_exact_upgrade_undo_retains_selected_profile_and_other_panels(self):
        self.prepare(); profile.switch(self.home, self.prepared)
        before = (self.config.read_bytes(), self.wrapper.read_bytes())
        job = deploy.deploy(self.home, ['native-panel'], {'native-panel': Path('/usr/bin/false')})
        self.assertNotEqual(self.wrapper.read_bytes(), before[1])
        deploy.undo(self.home, job)
        self.assertEqual((self.config.read_bytes(), self.wrapper.read_bytes()), before)
        self.assertEqual(self.stock.read_bytes(), self.original.encode())

    def test_size_and_clipboard_target_selected_panel_and_restore_exactly(self):
        self.prepare(); profile.switch(self.home, self.prepared); before = self.config.read_bytes()
        unrelated = layout.sections(before.decode())[1]['panel1']
        for module in ('taskbar-size', 'clipboard'):
            with self.subTest(module=module):
                modules.run(self.home, module, apply=True); modules.run(self.home, module, apply=True)
                self.assertEqual(layout.sections(self.config.read_text())[1]['panel1'], unrelated)
                cfg = QSettings(str(self.config), QSettings.Format.IniFormat)
                if module == 'taskbar-size': self.assertEqual(cfg.value('panel2/iconSize'), '28')
                else: self.assertIn('doroClipboard', cfg.value('panel2/plugins'))
                modules.run(self.home, module, rollback=True)
                self.assertEqual(self.config.read_bytes(), before)

    def test_later_quicklaunch_merge_keeps_other_panel_and_private_original(self):
        self.prepare(); profile.switch(self.home, self.prepared)
        launcher = self.home/'fixture.desktop'
        launcher.write_text('[Desktop Entry]\nType=Application\nName=Fixture\nExec=/usr/bin/true\nStartupWMClass=fixture\n')
        text = self.config.read_text()
        text = modules.ini_set(text, 'panel2', 'plugins', modules.ini_value(text, 'panel2', 'plugins')+', lateLaunch')
        text += '\n[lateLaunch]\ntype=quicklaunch\napps\\1\\desktop='+str(launcher)+'\napps\\size=1\n'
        self.config.write_text(text)
        manifest = self.home/'.local/state/doroshell/native-panel.json'; evidence = manifest.read_bytes()
        profile.merge_existing(self.home)
        self.assertEqual(layout.sections(self.config.read_text())[1]['panel1'], layout.sections(text)[1]['panel1'])
        cfg = QSettings(str(self.config), QSettings.Format.IniFormat)
        self.assertNotIn('lateLaunch', cfg.value('panel2/plugins'))
        self.assertEqual(cfg.value('doroshellTasks/doroshellPinned'), str(launcher))
        backups = list(manifest.parent.glob('panel-before-merge-*.conf'))
        self.assertEqual(len(backups), 1); self.assertEqual(backups[0].read_bytes(), text.encode())
        self.assertEqual(manifest.read_bytes(), evidence)  # Do not adopt the earlier personal edit.

    def test_installed_toolkit_import_and_cli_selection(self):
        install.install(self.home, apply=True)
        toolkit = self.home/'.local/share/doroshell/toolkit'
        self.assertEqual((toolkit/'panel/layout.py').read_bytes(), (Path(__file__).resolve().parents[1]/'panel/layout.py').read_bytes())
        env = dict(os.environ, HOME=str(self.home), QT_QPA_PLATFORM='offscreen', DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent')
        for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY'): env.pop(key, None)
        args = [sys.executable, str(toolkit/'panel/profile.py'), 'prepare', '--home', str(self.home),
                '--prepared', str(self.prepared), '--binary', '/usr/bin/true']
        refused = subprocess.run(args, env=env, capture_output=True, text=True)
        self.assertNotEqual(refused.returncode, 0); self.assertIn('--panel', refused.stderr)
        self.assertNotIn('Traceback', refused.stderr); self.assertFalse(self.prepared.exists())
        result = subprocess.run([*args, '--panel', 'panel2'], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.prepared/'plan.json').read_text())['panel'], 'panel2')
