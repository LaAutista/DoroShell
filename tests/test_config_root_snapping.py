"""Config relocation and shared XML ownership; no server, input or package actions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

import config_root
import deploy
import install
import modules
import setup
import test_config_root as fixtures


class SnappingRootTests(unittest.TestCase):
    snapshot=fixtures.ConfigRootTests.snapshot
    cli=fixtures.ConfigRootTests.cli
    job=fixtures.ConfigRootTests.job

    def setUp(self):
        fixtures.ConfigRootTests.setUp(self)
        self.xml=self.xml.replace(b'<desktops>',b'<keyboard><!--keep binding--><keybind key="C-A-t"><action name="Execute"><command>fixture-terminal</command></action></keybind></keyboard><desktops>')
        self.file.write_bytes(self.xml);self.default.write_bytes(self.xml)
        self.snap=self.home/'.local/state/doroshell/snapping.json'
        self.autostart=self.root/'autostart/doroshell-snap.desktop'

    def opt(self,*args,combined=False):
        return self.cli('--modules','snapping',*(['single-desktop'] if combined else []),'--config-root',str(self.root),*args)

    def test_single_lifecycle_restores_preexisting_programs_autostart_and_modes(self):
        paths=[self.home/'.local/share/doroshell/snap.py',self.home/'.local/bin/doroshell-snap',self.autostart]
        for p in paths:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'previous fixture');p.chmod(0o700)
        before=self.snapshot();self.opt();self.assertEqual(self.snapshot(),before)
        self.opt('--apply');installed=self.file.read_bytes();saved=self.snap.read_bytes()
        self.assertIn(b'W-Left',installed);self.assertIn(b'<number>4</number>',installed)
        self.assertIn(b'C-A-t',installed);self.assertTrue(self.autostart.exists())
        self.assertFalse((self.home/'.config/autostart/doroshell-snap.desktop').exists())
        self.assertEqual(json.loads(saved)['config_root'],'Config with spaces')
        self.cli('--modules','snapping','--apply');self.assertEqual(self.snap.read_bytes(),saved)
        _,identifier=self.job();self.cli('--apply','--undo',identifier)
        self.assertEqual(self.file.read_bytes(),installed);self.assertEqual(self.snap.read_bytes(),saved)
        self.cli('--modules','snapping','--remove','--apply')
        for name,value in before.items():self.assertEqual(self.snapshot()[name],value)
        self.assertFalse(self.snap.exists());self.commands.assert_not_called();self.build.assert_called()

    def test_combined_plan_repeat_undo_remove_and_individual_restoration(self):
        before=self.snapshot();self.opt(combined=True);self.assertEqual(self.snapshot(),before)
        self.opt('--apply',combined=True)
        installed=self.file.read_bytes();records=[self.snap.read_bytes(),self.record.read_bytes()]
        self.assertIn(b'W-Left',installed);self.assertIn(b'<number>1</number>',installed)
        self.cli('--modules','snapping','single-desktop','--apply');_,upgrade=self.job()
        self.cli('--apply','--undo',upgrade)
        self.assertEqual(self.file.read_bytes(),installed)
        self.assertEqual([self.snap.read_bytes(),self.record.read_bytes()],records)
        self.cli('--modules','snapping','single-desktop','--remove','--apply')
        self.assertEqual(self.file.read_bytes(),self.xml)
        self.assertFalse(self.snap.exists());self.assertFalse(self.record.exists())
        self.opt('--apply',combined=True)
        self.cli('--modules','snapping','--remove','--apply')
        self.assertNotIn(b'W-Left',self.file.read_bytes());self.assertIn(b'<number>1</number>',self.file.read_bytes())
        self.cli('--modules','single-desktop','--remove','--apply');self.assertEqual(self.file.read_bytes(),self.xml)
        self.opt('--apply',combined=True);_,identifier=self.job();self.cli('--apply','--undo',identifier)
        self.assertEqual(self.file.read_bytes(),self.xml);self.assertFalse(self.snap.exists())
        self.assertEqual(self.default.read_bytes(),self.xml);self.assertEqual(self.other.read_bytes(),b'private fixture untouched')

    def test_existing_other_adapter_and_unrelated_xml_edit_are_preserved(self):
        modules.run(self.home,'single-desktop',apply=True,config_root=self.root)
        self.opt('--apply')
        self.file.write_bytes(self.file.read_bytes().replace(b'untouched',b'personal later edit'))
        modules.run(self.home,'single-desktop',rollback=True)
        self.assertIn(b'W-Left',self.file.read_bytes());self.assertIn(b'<number>4</number>',self.file.read_bytes())
        modules.run(self.home,'snapping',rollback=True)
        self.assertEqual(self.file.read_bytes(),self.xml.replace(b'untouched',b'personal later edit'))

    def test_wrong_root_legacy_ownership_and_shared_root_disagreement_refuse(self):
        modules.run(self.home,'snapping',apply=True)
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'recorded ownership'):self.opt('--apply')
        self.assertEqual(self.snapshot(),before)
        modules.run(self.home,'single-desktop',apply=True)
        legacy=self.home/'.local/state/doroshell/single-desktop.json'
        record=json.loads(legacy.read_text());record['edits']=record['edits'][:1];legacy.write_text(json.dumps(record))
        modules.run(self.home,'single-desktop',apply=True);modules.run(self.home,'single-desktop',rollback=True)
        modules.run(self.home,'single-desktop',apply=True,config_root=self.root);before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'different recorded'):self.cli('--modules','snapping','single-desktop','--apply')
        self.assertEqual(self.snapshot(),before)

    def test_missing_malformed_conflicting_and_ambiguous_keyboard_refuse_without_writes(self):
        bad=[b'<bad',self.xml.replace(b'</keyboard>',b'</keyboard><keyboard></keyboard>'),self.xml.replace(b'</keyboard>',b'<keybind other="x" key="W-Left"/></keyboard>'),self.xml.replace(b'</keyboard>',b'<!-- DoroShell snapping begin --></keyboard>')]
        for data in bad:
            self.file.write_bytes(data);before=self.snapshot()
            with self.assertRaises((ValueError,RuntimeError,ET.ParseError)):self.opt('--apply',combined=True)
            self.assertEqual(self.snapshot(),before)
        self.file.unlink();before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'initialized Openbox'):self.opt('--apply')
        self.assertEqual(self.snapshot(),before);self.commands.assert_not_called();self.build.assert_not_called()

    def test_target_symlinks_and_unsafe_record_refuse_before_metadata(self):
        for rel in ['autostart','.local/bin','.local/share/doroshell','.local/state/doroshell']:
            with tempfile.TemporaryDirectory() as tmp:
                home=Path(tmp);root=home/'config';rc=root/'openbox/rc.xml';rc.parent.mkdir(parents=True);rc.write_bytes(self.xml)
                foreign=home/'foreign';foreign.mkdir();alias=(root if rel=='autostart' else home)/rel
                alias.parent.mkdir(parents=True,exist_ok=True);alias.symlink_to(foreign,target_is_directory=True)
                with self.assertRaisesRegex(RuntimeError,'symlink'):modules.run(home,'snapping',apply=True,config_root=root)
                self.assertEqual(list(foreign.iterdir()),[]);self.assertEqual(rc.read_bytes(),self.xml)
        self.opt('--apply');original=self.snap.read_bytes()
        for mutate in [lambda r:r.pop('config_root'),lambda r:r['edits'][0].update(after='bad base64!'),lambda r:r['edits'][0].update(file='somewhere'),lambda r:r.update(config_root='../outside')]:
            record=json.loads(original);mutate(record);self.snap.write_text(json.dumps(record));before=self.snapshot()
            with self.assertRaises((RuntimeError,ValueError)):self.cli('--modules','snapping','--apply')
            self.assertEqual(self.snapshot(),before)
        self.snap.write_bytes(original)

    def test_managed_content_mode_and_environment_edits_refuse(self):
        self.opt('--apply')
        for path in (self.file,self.autostart,self.home/'.local/share/doroshell/snap.py'):
            original=path.read_bytes();path.write_bytes(original.replace(b'left',b'right') if path==self.file else b'edited')
            before=self.snapshot()
            for action in ('--apply','--remove'):
                with self.assertRaises(RuntimeError):self.cli('--modules','snapping',action,'--apply')
                self.assertEqual(self.snapshot(),before)
            path.write_bytes(original)
        self.file.chmod(0o600);before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'mode edit'):self.opt('--apply')
        self.assertEqual(self.snapshot(),before);self.file.chmod(0o640)
        with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.home/'.config')}),self.assertRaisesRegex(ValueError,'differs'):self.opt('--apply')

    def test_partial_multifile_apply_and_restoration_recover_without_adopting_edits(self):
        real=modules.atomic
        for target in (self.home/'.local/bin/doroshell-snap',self.file):
            def crash(path,*args):
                real(path,*args)
                if path==target:raise fixtures.Crash()
            with patch.object(modules,'atomic',crash),self.assertRaises(fixtures.Crash):self.opt('--apply')
            self.cli('--apply','--recover')
            self.assertEqual(json.loads(self.snap.read_text())['phase'],'complete')
            self.cli('--modules','snapping','--remove','--apply');self.assertEqual(self.file.read_bytes(),self.xml)
        self.opt('--apply')
        unlink=Path.unlink
        def crash_unlink(path,*args,**kwargs):
            unlink(path,*args,**kwargs)
            if path==self.autostart:raise fixtures.Crash()
        with patch.object(Path,'unlink',crash_unlink),self.assertRaises(fixtures.Crash):self.cli('--modules','snapping','--remove','--apply')
        self.cli('--apply','--recover');self.assertFalse(self.snap.exists());self.assertEqual(self.file.read_bytes(),self.xml)

    def test_write_failure_restores_all_originals(self):
        before=self.snapshot();real=modules.atomic
        def fail(path,*args):
            if path==self.file:raise OSError('fixture write failure')
            return real(path,*args)
        with patch.object(modules,'atomic',fail),self.assertRaises(OSError):self.opt('--apply')
        self.assertEqual(self.file.read_bytes(),self.xml);self.assertFalse(self.autostart.exists());self.assertFalse(self.snap.exists())
        self.cli('--apply','--recover');self.cli('--modules','snapping','--remove','--apply')
        for name,value in before.items():self.assertEqual(self.snapshot()[name],value)

    def test_combined_interruption_between_steps_recovers_and_edit_is_not_adopted(self):
        real=deploy.step
        def stop(home,name,*args,**kwargs):
            if name=='single-desktop':raise fixtures.Crash()
            return real(home,name,*args,**kwargs)
        with patch.object(deploy,'step',stop),self.assertRaises(fixtures.Crash):self.opt('--apply',combined=True)
        installed=self.file.read_bytes();self.file.write_bytes(installed+b'<!-- external -->')
        before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Edited completed'):self.cli('--apply','--recover')
        self.assertEqual(self.snapshot(),before);self.file.write_bytes(installed)
        self.cli('--apply','--recover');self.assertIn(b'<number>1</number>',self.file.read_bytes())
        self.cli('--modules','snapping','single-desktop','--remove','--apply');self.assertEqual(self.file.read_bytes(),self.xml)

    def test_ambiguous_overlapping_interruption_remains_refused(self):
        real=modules.atomic
        def crash(path,data,*args):
            real(path,data,*args)
            if path==self.file and b'<number>1</number>' in data:raise fixtures.Crash()
        with patch.object(modules,'atomic',crash),self.assertRaises(fixtures.Crash):self.opt('--apply',combined=True)
        before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Edited completed'):self.cli('--apply','--recover')
        self.assertEqual(self.snapshot(),before)

    def test_installed_toolkit_cli_and_setup_preflight(self):
        install.install(self.home,True)
        toolkit=self.home/'.local/share/doroshell/toolkit'
        env=dict(os.environ,HOME=str(self.home),PATH='',XDG_CONFIG_HOME=str(self.root))
        for args in ([],['--apply'],['--apply'],['--rollback']):
            result=subprocess.run([sys.executable,'-S','-B',str(toolkit/'modules.py'),'snapping','--config-root',str(self.root),*args],env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.file.read_bytes(),self.xml)
        args=['setup.py','snapping','single-desktop','--config-root',str(self.root),'--home',str(self.home),'--apply']
        with patch.object(sys,'argv',args),patch.object(setup.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as command:setup.main()
        programs=[call.args[0] for call in command.call_args_list if '--config-root' in call.args[0]]
        self.assertEqual([cmd[2] for cmd in programs],['snapping','single-desktop'])
        self.assertTrue(all(cmd[cmd.index('--config-root')+1]==str(self.root) for cmd in programs))
        self.file.write_bytes(b'<bad');before=self.snapshot()
        with patch.object(sys,'argv',args),patch.object(setup.subprocess,'run') as command,self.assertRaises((ValueError,RuntimeError,ET.ParseError)):setup.main()
        command.assert_not_called();self.assertEqual(self.snapshot(),before)


if __name__=='__main__':unittest.main()
