"""Completed native-panel recovery with later stock-layout edits, in disposable homes."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import compatibility
import deploy
import install


class PanelLayoutRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.stock = self.home/'.config/lxqt/panel.conf'
        self.stock.parent.mkdir(parents=True)
        self.stock.write_text('[panel1]\nplugins=taskbar,statusnotifier\n')
        self.menu = self.home/'synthetic-menu-file'
        self.menu.write_bytes(b'original menu'); self.menu.chmod(0o640)
        self.selected = ['menu', 'native-panel', 'maintenance']
        self.binaries = {'native-panel': Path('/usr/bin/true')}  # Recorded, never executed.
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(patch.object(install, 'targets', return_value={self.menu: (b'installed menu', 0o644)}))
        # Exercise real capability/layout checks; package/build boundaries are synthetic.
        self.enterContext(patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'LXQt', 'XDG_SESSION_TYPE': 'x11'}, clear=True))
        self.enterContext(patch.object(compatibility, 'os_release', return_value={'ID': 'arch'}))
        self.enterContext(patch.object(compatibility.shutil, 'which', return_value='/usr/bin/pacman'))
        self.enterContext(patch.object(compatibility, 'package_versions', return_value={'python': 'fixture'}))
        self.enterContext(patch.object(deploy.os, 'geteuid', return_value=1000))

    def snapshot(self):
        return {str(p.relative_to(self.home)): (p.read_bytes(), p.stat().st_mode & 0o777)
                for p in self.home.rglob('*') if p.is_file()}

    def interrupt(self, at='maintenance'):
        real = deploy.step
        def step(*args, **kwargs):
            names, operation = real(*args, **kwargs)
            if args[1] == at:
                def operation():
                    raise OSError('fixture interrupted before '+at)
            return names, operation
        with patch.object(deploy, 'step', side_effect=step), self.assertRaisesRegex(OSError, 'fixture interrupted'):
            deploy.deploy(self.home, self.selected, self.binaries)
        pointer = self.home/deploy.POINTER
        self.identifier = json.loads(pointer.read_text())['transaction']
        self.journal = pointer.parent/'deployments'/self.identifier/'journal.json'

    def add_stock_panel(self):
        self.stock.write_text('panels=panel1,panel2\n[panel1]\nplugins=taskbar,statusnotifier\n'
                              '[panel2]\nplugins=customclock\nposition=Left\n[customclock]\ntype=worldclock\n')
        self.stock.chmod(0o640)

    def recover(self):
        return deploy.main(['--home', str(self.home), '--apply', '--recover', '--no-packages'])

    def test_completed_panel_recovers_without_adopting_new_stock_layout_then_exact_undo(self):
        self.interrupt()
        completed = json.loads(self.journal.read_text())['after']
        self.add_stock_panel(); stock = (self.stock.read_bytes(), self.stock.stat().st_mode & 0o777)
        with patch.object(deploy, 'build_native', return_value=self.binaries), patch('source_release.check'):
            self.assertEqual(self.recover(), 0)
        after = json.loads(self.journal.read_text())['after']
        for name, evidence in completed.items():
            self.assertEqual(after[name], evidence)
            self.assertEqual(deploy.file_state(self.home, name), evidence)
        self.assertNotIn(str(self.stock.relative_to(self.home)), after)
        self.assertEqual((self.stock.read_bytes(), self.stock.stat().st_mode & 0o777), stock)
        deploy.undo(self.home, self.identifier)
        self.assertEqual((self.menu.read_bytes(), self.menu.stat().st_mode & 0o777), (b'original menu', 0o640))
        self.assertFalse((self.home/'.config/doroshell/panel.conf').exists())
        self.assertEqual((self.stock.read_bytes(), self.stock.stat().st_mode & 0o777), stock)

    def test_completed_panel_edits_still_refused_before_prerequisites_or_writes(self):
        self.interrupt(); self.add_stock_panel()
        target = self.home/'.config/doroshell/panel.conf'; original = target.read_bytes()
        for kind in ('content', 'mode', 'symlink'):
            with self.subTest(kind=kind):
                if kind == 'content': target.write_bytes(original+b'\n# personal edit\n')
                elif kind == 'mode': target.chmod(0o640)
                else:
                    target.unlink(); target.symlink_to(self.stock)
                before = self.snapshot()
                with patch.object(compatibility, 'inspect') as inspect, patch.object(deploy, 'build_native') as build:
                    with self.assertRaises((ValueError, RuntimeError)): self.recover()
                    inspect.assert_not_called(); build.assert_not_called()
                self.assertEqual(self.snapshot(), before)
                if target.is_symlink(): target.unlink()
                target.write_bytes(original); target.chmod(0o600)

    def test_unfinished_panel_keeps_single_panel_gate(self):
        self.interrupt(at='native-panel'); self.add_stock_panel(); before = self.snapshot()
        with patch.object(deploy, 'build_native') as build:
            with self.assertRaisesRegex(ValueError, 'single panel1'): self.recover()
            build.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_completed_panel_does_not_bypass_custom_xdg_refusal(self):
        self.interrupt(); self.add_stock_panel(); before = self.snapshot()
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.home/'custom-config')}), patch.object(deploy, 'build_native') as build:
            with self.assertRaisesRegex(ValueError, 'XDG_CONFIG_HOME'): self.recover()
            build.assert_not_called()
        self.assertEqual(self.snapshot(), before)
