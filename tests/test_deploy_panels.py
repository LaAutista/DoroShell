"""Portable panel selection with real file adapters and synthetic package/build boundaries."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import compatibility
import deploy
import install
from panel import layout, profile


class DeployPanelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.stock = self.home/'.config/lxqt/panel.conf'; self.stock.parent.mkdir(parents=True)
        self.original = ('[General]\npanels=panel1,panel2\n[panel1]\nplugins=clockOne\n'
                         'position=Top\n[clockOne]\ntype=worldclock\ncustomFormat=HH:mm\n'
                         '[panel2]\nplugins=taskTwo,trayTwo\nposition=Left\npanelSize=47\n'
                         '[taskTwo]\ntype=taskbar\n[trayTwo]\ntype=statusnotifier\n')
        self.stock.write_text(self.original); self.stock.chmod(0o640)
        self.menu = self.home/'synthetic-menu'; self.menu.write_bytes(b'original menu'); self.menu.chmod(0o640)
        self.config = self.home/'.config/doroshell/panel.conf'
        self.wrapper = self.home/'.local/bin/doroshell-native-panel'
        self.pointer = self.home/deploy.POINTER
        self.output = io.StringIO(); self.enterContext(contextlib.redirect_stdout(self.output))
        self.enterContext(patch.dict(os.environ, {'XDG_CURRENT_DESKTOP':'LXQt', 'XDG_SESSION_TYPE':'x11'}, clear=True))
        self.enterContext(patch.object(compatibility, 'os_release', return_value={'ID':'arch'}))
        self.enterContext(patch.object(compatibility.shutil, 'which', return_value='/usr/bin/pacman'))
        self.packages = self.enterContext(patch.object(compatibility, 'package_versions', return_value={'python':'fixture'}))
        self.build = self.enterContext(patch.object(deploy, 'build_native', return_value={'native-panel':Path('/usr/bin/true')}))
        self.run = self.enterContext(patch.object(deploy, 'run'))
        self.enterContext(patch('source_release.check'))
        self.enterContext(patch.object(deploy.os, 'geteuid', return_value=1000))
        self.enterContext(patch.object(install, 'targets', return_value={self.menu:(b'installed menu',0o644)}))

    def cli(self, *args):
        return deploy.main(['--home',str(self.home),*args])

    def initial(self, *args):
        return self.cli('--modules','native-panel','maintenance','--panel','panel2',*args)

    def snapshot(self, journals=True):
        return {str(p.relative_to(self.home)):(p.read_bytes(),p.stat().st_mode&0o777)
                for p in self.home.rglob('*') if p.is_file() and (journals or 'deployments' not in p.parts)}

    def journal(self):
        pointer = json.loads(self.pointer.read_text())
        path = self.pointer.parent/'deployments'/pointer['transaction']/'journal.json'
        return path, json.loads(path.read_text())

    def interrupt(self, legacy=False):
        real = profile.atomic
        def fail(path, *args):
            if path == self.wrapper: raise OSError('fixture native interruption')
            return real(path,*args)
        with patch.object(profile,'atomic',side_effect=fail), self.assertRaisesRegex(OSError,'fixture native interruption'):
            if legacy: self.cli('--modules','native-panel','maintenance','--apply')
            else: self.initial('--apply')
        return self.journal()

    def test_plan_no_writes_apply_repeat_scoped_update_remove_and_exact_undo(self):
        before = self.snapshot(); self.assertEqual(self.initial(),0); self.assertEqual(self.snapshot(),before)
        self.assertIn('"panel": "panel2"',self.output.getvalue()); self.build.assert_not_called(); self.run.assert_not_called()
        self.initial('--apply'); staged = self.snapshot(journals=False)
        record = json.loads(self.pointer.read_text()); self.assertEqual((record['format'],record['panel']),(2,'panel2'))
        path, journal = self.journal(); self.assertEqual((journal['format'],journal['request']['panel']),(3,'panel2'))
        self.assertEqual(layout.sections(self.config.read_text())[1]['panel1'],layout.sections(self.original)[1]['panel1'])
        baseline = (self.home/'.local/state/doroshell/native-panel.json').read_bytes()
        self.build.return_value={'native-panel':Path('/usr/bin/false')}; self.cli('--apply')
        self.assertIn('/usr/bin/false',self.wrapper.read_text())
        upgrade = json.loads(self.pointer.read_text())['transaction']; self.cli('--apply','--undo',upgrade)
        restored = self.snapshot(journals=False)
        for name,value in staged.items(): self.assertEqual(restored[name],value)
        self.assertEqual(set(restored)-set(staged), {'.local/state/doroshell/'+name+'.lock' for name in ('theme','wallpaper','clipboard')})
        self.cli('--modules','menu','--apply')
        self.assertEqual(json.loads(self.pointer.read_text())['panel'],'panel2')
        self.assertEqual((self.home/'.local/state/doroshell/native-panel.json').read_bytes(),baseline)
        self.cli('--apply','--remove')
        self.assertFalse(self.config.exists()); self.assertFalse(self.wrapper.exists())
        self.assertNotIn('panel',json.loads(self.pointer.read_text()))
        for name,value in before.items(): self.assertEqual(self.snapshot()[name],value)

    def test_wrong_missing_and_shared_selection_refuse_before_package_or_install_writes(self):
        self.packages.return_value={'python':None}
        for selection, text in [(None,self.original), ('panel9',self.original),
                                ('panel2',self.original.replace('plugins=taskTwo,trayTwo','plugins=clockOne,trayTwo')),
                                (None,self.original.replace('panels=panel1,panel2\n',''))]:
            with self.subTest(selection=selection):
                self.stock.write_text(text); before=self.snapshot()
                args=['--modules','native-panel','--apply']+(['--panel',selection] if selection else [])
                with self.assertRaises(ValueError): self.cli(*args)
                self.run.assert_not_called(); self.build.assert_not_called(); self.assertEqual(self.snapshot(),before)

    def test_bad_id_or_scoped_selection_refuses_before_probes(self):
        for args in [('--panel','../panel2'),('--panel','panel2\n'),('--panel','panel2','--modules','menu')]:
            before=self.snapshot()
            with patch.object(compatibility,'inspect') as inspect, self.assertRaises(ValueError):self.cli(*args,'--apply')
            inspect.assert_not_called();self.assertEqual(self.snapshot(),before)

    def test_missing_validation_bindings_fail_without_package_or_home_writes(self):
        before=self.snapshot()
        result=subprocess.run([sys.executable,'-S',str(deploy.ROOT/'deploy.py'),'--home',str(self.home),
                               '--modules','native-panel','--panel','panel2','--apply'],
                              env={'HOME':str(self.home),'PATH':'/empty','XDG_CURRENT_DESKTOP':'LXQt','XDG_SESSION_TYPE':'x11'},
                              capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('Panel validation needs PySide6 and GIO',result.stderr)
        self.assertNotIn('Traceback',result.stderr);self.assertEqual(self.snapshot(),before)

    def test_recorded_choice_cannot_be_changed_by_repeat_or_recovery(self):
        self.interrupt(); before=self.snapshot()
        self.packages.reset_mock();self.build.reset_mock()
        with self.assertRaisesRegex(ValueError,'recorded panel'):self.cli('--apply','--recover','--panel','panel1')
        self.packages.assert_not_called();self.build.assert_not_called();self.assertEqual(self.snapshot(),before)
        self.cli('--apply','--recover'); before=self.snapshot();self.packages.reset_mock()
        with self.assertRaisesRegex(ValueError,'recorded choice'):self.cli('--apply','--panel','panel1')
        self.packages.assert_not_called();self.assertEqual(self.snapshot(),before)

    def test_first_stage_recovery_uses_saved_plan_and_first_originals(self):
        path,journal=self.interrupt();before=copy.deepcopy(journal['before'])
        native_record=(self.home/'.local/state/doroshell/native-panel.json').read_bytes()
        self.assertTrue(self.config.exists());self.assertFalse(self.wrapper.exists())
        self.cli('--apply','--recover')
        recovered = json.loads(path.read_text())['before']
        for name,value in before.items(): self.assertEqual(recovered[name],value)
        self.assertEqual((self.home/'.local/state/doroshell/native-panel.json').read_bytes(),native_record)
        self.assertEqual(layout.installed_panel(self.config.read_text()),'panel2')
        self.cli('--apply','--undo',path.parent.name)
        self.assertEqual(self.stock.read_text(),self.original);self.assertFalse(self.config.exists())

    def test_legacy_single_panel_first_stage_recovery_keeps_legacy_schema(self):
        self.stock.write_text('[panel1]\nplugins=taskbar,statusnotifier\n')
        path,record=self.interrupt(legacy=True);self.assertEqual(record['format'],2)
        self.cli('--apply','--recover')
        self.assertEqual(json.loads(self.pointer.read_text())['format'],1)
        self.assertNotIn('panel',json.loads(path.read_text())['request'])
        self.cli('--apply','--remove');self.assertFalse(self.config.exists())

    def test_changed_source_or_active_output_blocks_recovery_before_packages(self):
        self.interrupt(); self.packages.return_value={'python':None}
        original=self.config.read_bytes()
        for target,data in [(self.stock,self.original.encode()+b'\n; later layout edit\n'),
                            (self.config,original+b'\n; later native edit\n')]:
            previous=target.read_bytes();target.write_bytes(data);before=self.snapshot()
            self.run.reset_mock();self.build.reset_mock()
            with self.assertRaises(ValueError):self.cli('--apply','--recover')
            self.run.assert_not_called();self.build.assert_not_called();self.assertEqual(self.snapshot(),before)
            target.write_bytes(previous)

    def test_schema_and_pointer_choice_mismatch_are_refused_without_writes(self):
        path,original=self.interrupt();pointer=self.pointer.read_bytes()
        for mutate in (lambda r:r['request'].update(panel=None),lambda r:r['request'].update(panel='../panel2'),
                       lambda r:r.update(format=2),lambda r:r['request'].pop('panel')):
            record=copy.deepcopy(original);mutate(record);path.write_text(json.dumps(record));before=self.snapshot()
            with patch.object(compatibility,'inspect') as inspect,self.assertRaises(ValueError):self.cli('--apply','--recover')
            inspect.assert_not_called();self.assertEqual(self.snapshot(),before)
        path.write_text(json.dumps(original));record=json.loads(pointer);record['panel']='panel1';self.pointer.write_text(json.dumps(record))
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Mismatched pending panel'):self.cli('--apply','--recover')
        self.assertEqual(self.snapshot(),before)

    def test_completed_native_recovery_still_preserves_later_stock_layout(self):
        real=deploy.step
        def fail(*args,**kwargs):
            names,operation=real(*args,**kwargs)
            if args[1]=='maintenance':
                def operation():raise OSError('fixture maintenance interruption')
            return names,operation
        with patch.object(deploy,'step',side_effect=fail),self.assertRaises(OSError):self.initial('--apply')
        self.stock.write_text(self.original.replace('panel1,panel2','panel1,panel2,panel3')+'\n[panel3]\nplugins=custom\n')
        changed=self.stock.read_bytes();self.cli('--apply','--recover');self.assertEqual(self.stock.read_bytes(),changed)

    def test_later_native_edits_are_preserved_and_block_removal(self):
        self.initial('--apply');self.config.write_bytes(self.config.read_bytes()+b'\n; personal change\n')
        changed=self.config.read_bytes();self.cli('--apply');self.assertEqual(self.config.read_bytes(),changed)
        with self.assertRaises(RuntimeError):self.cli('--apply','--remove')
        self.assertEqual(self.config.read_bytes(),changed)

    def test_validation_prerequisites_apply_then_revalidate_before_config(self):
        real=deploy.panel_preflight; calls=[]; before=self.snapshot()
        def preflight(*args):
            calls.append(True)
            if len(calls)==1:raise deploy.PanelPrerequisitesUnavailable('fixture missing bindings')
            return real(*args)
        def package(argv):
            self.assertEqual(argv,['sudo','pacman','-Syu','--needed','pyside6','python-gobject'])
            self.assertEqual(self.snapshot(),before)
        self.run.side_effect=package
        with patch.object(deploy,'panel_preflight',side_effect=preflight):self.initial('--apply')
        self.assertGreaterEqual(len(calls),3)  # Initial check, post-package check, final adapter check.
        self.run.assert_called_once();self.assertEqual(layout.installed_panel(self.config.read_text()),'panel2')
        self.assertIn('The panel may still be refused afterward',self.output.getvalue())

    def test_validation_prerequisite_cancel_or_failure_stops_without_writes(self):
        before=self.snapshot()
        for code in (1,127):
            self.run.reset_mock();self.run.side_effect=subprocess.CalledProcessError(code,['fixture-pacman'])
            with patch.object(deploy,'panel_preflight',side_effect=deploy.PanelPrerequisitesUnavailable('fixture missing')):
                with self.assertRaises(subprocess.CalledProcessError):self.initial('--apply')
            self.run.assert_called_once();self.build.assert_not_called();self.assertEqual(self.snapshot(),before)

    def test_unavailable_bindings_after_success_never_retry_or_write(self):
        before=self.snapshot()
        with patch.object(deploy,'panel_preflight',side_effect=deploy.PanelPrerequisitesUnavailable('fixture missing')):
            with self.assertRaisesRegex(ValueError,'still unavailable after pacman'):self.initial('--apply')
        self.run.assert_called_once();self.build.assert_not_called();self.assertEqual(self.snapshot(),before)

    def test_post_prerequisite_panel_refusal_prevents_module_packages_and_config(self):
        self.packages.return_value={'python':None}
        real=deploy.panel_preflight
        for text in (self.original.replace('panel2','panel9'),
                     self.original.replace('plugins=taskTwo,trayTwo','plugins=clockOne,trayTwo')):
            self.stock.write_text(text);before=self.snapshot();calls=[];self.run.reset_mock()
            def preflight(*args):
                calls.append(True)
                if len(calls)==1:raise deploy.PanelPrerequisitesUnavailable('fixture missing')
                return real(*args)
            with patch.object(deploy,'panel_preflight',side_effect=preflight),self.assertRaises(ValueError):self.initial('--apply')
            self.run.assert_called_once_with(['sudo','pacman','-Syu','--needed','pyside6','python-gobject'])
            self.build.assert_not_called();self.assertEqual(self.snapshot(),before)

    def test_plan_no_packages_and_platform_refusal_never_offer_validation_packages(self):
        before=self.snapshot()
        with patch.object(deploy,'panel_preflight',side_effect=deploy.PanelPrerequisitesUnavailable('fixture missing')):
            self.initial();self.assertIn('Plan blocked',self.output.getvalue())
            with self.assertRaises(deploy.PanelPrerequisitesUnavailable):self.initial('--apply','--no-packages')
            with patch.object(compatibility,'inspect',return_value={'issues':['fixture unsupported platform']}):
                with self.assertRaisesRegex(ValueError,'unsupported platform'):self.initial('--apply')
        self.run.assert_not_called();self.build.assert_not_called();self.assertEqual(self.snapshot(),before)
