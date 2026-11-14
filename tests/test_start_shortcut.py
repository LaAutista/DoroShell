"""Opt-in Alt+F1 file ownership, using disposable homes and no shortcut daemon."""
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

import compatibility
import deploy
import install
import integrate
import modules
import setup


class Crash(BaseException):pass


class StartShortcutTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.home=Path(temporary.name)
        self.output=io.StringIO();self.enterContext(contextlib.redirect_stdout(self.output))
        install.install(self.home,True)
        self.path=self.home/'.config/lxqt/globalkeyshortcuts.conf';self.path.parent.mkdir(parents=True,exist_ok=True)
        self.unrelated='; untouched\n[Print.1]\nExec=custom-shot\nEnabled=true\n\n'
        self.path.write_text(self.unrelated);self.path.chmod(0o640)
        self.record=self.home/'.local/state/doroshell/start-shortcut.json'
        self.enterContext(patch.dict(os.environ,{'HOME':str(self.home)},clear=True))
        self.enterContext(patch.object(compatibility,'inspect',side_effect=lambda *args:{'issues':[]}))
        self.enterContext(patch.object(compatibility,'package_versions',return_value={'python':'fixture'}))
        self.enterContext(patch('source_release.check'))
        self.enterContext(patch.object(deploy.os,'geteuid',return_value=1000))
        self.build=self.enterContext(patch.object(deploy,'build_native',return_value={}))
        self.commands=self.enterContext(patch.object(deploy,'run'))

    def cli(self,*args):return deploy.main(['--home',str(self.home),*args])
    def opt(self,*args):return self.cli('--modules','start-shortcut',*args)
    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.read_bytes(),p.stat().st_mode&0o777) for p in self.home.rglob('*') if p.is_file()}
    def custom(self):
        self.path.write_text(self.unrelated+'[Alt%2BF1.7]\nExec=personal-start --flag\nEnabled=true\nComment=Keep me\n')

    def test_optional_plan_shows_binding_and_no_default_takeover(self):
        self.assertNotIn('start-shortcut',deploy.CORE)
        self.custom();before=self.snapshot();self.opt()
        self.assertIn('personal-start --flag',self.output.getvalue());self.assertIn('Plan blocked',self.output.getvalue())
        with self.assertRaisesRegex(ValueError,'replace-start-shortcut'):self.opt('--apply')
        self.assertEqual(self.snapshot(),before);self.commands.assert_not_called();self.build.assert_not_called()

    def test_no_binding_repeat_and_remove_restore_exact_bytes_and_mode(self):
        before=self.path.read_bytes();self.opt('--apply');record=self.record.read_bytes();installed=self.path.read_bytes()
        self.assertTrue(installed.startswith(before));self.assertIn(b'Alt%2BF1.1',installed)
        self.opt('--apply');self.assertEqual(self.record.read_bytes(),record);self.assertEqual(self.path.read_bytes(),installed)
        self.opt('--remove','--apply');self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.path.stat().st_mode&0o777,0o640)
        self.assertFalse(self.record.exists())

    def test_missing_file_is_created_then_removed_and_legacy_default_is_reversible(self):
        self.path.unlink();modules.run(self.home,'start-shortcut',apply=True);modules.run(self.home,'start-shortcut',rollback=True)
        self.assertFalse(self.path.exists())
        before=self.unrelated+'[Alt+F1.1]\npath=/panel/fancymenu/show_hide\nEnabled=true\n'
        self.path.write_text(before);modules.run(self.home,'start-shortcut',apply=True)
        self.assertTrue(self.path.read_text().startswith(self.unrelated))
        modules.run(self.home,'start-shortcut',rollback=True);self.assertEqual(self.path.read_text(),before)

    def test_explicit_replacement_durable_choice_and_exact_upgrade_undo(self):
        self.custom();before=self.path.read_bytes();self.opt('--replace-start-shortcut')
        self.assertEqual(self.path.read_bytes(),before)
        self.opt('--apply','--replace-start-shortcut');first=self.path.read_bytes();record=self.record.read_bytes()
        pointer=json.loads((self.home/deploy.POINTER).read_text())
        job=self.home/'.local/state/doroshell/deployments'/pointer['transaction']/'journal.json'
        journal=json.loads(job.read_text());self.assertEqual(journal['format'],4);self.assertTrue(journal['request']['replace_start_shortcut'])
        self.opt('--apply');latest=json.loads((self.home/deploy.POINTER).read_text())['transaction']
        self.cli('--apply','--undo',latest);self.assertEqual(self.path.read_bytes(),first);self.assertEqual(self.record.read_bytes(),record)
        self.opt('--remove','--apply');self.assertEqual(self.path.read_bytes(),before)

    def test_installed_edits_including_reverting_to_baseline_refuse_without_overwrite(self):
        baseline=self.path.read_bytes();modules.run(self.home,'start-shortcut',apply=True);owned=self.path.read_bytes()
        for data in (baseline,owned+b'; another shortcut edit\n',owned.replace(b'Enabled=true',b'Enabled=false')):
            self.path.write_bytes(data);before=self.snapshot()
            for kwargs in ({'apply':True},{'rollback':True},{'replace_start_shortcut':True}):
                with self.assertRaisesRegex(RuntimeError,'Edited shortcut'):modules.run(self.home,'start-shortcut',**kwargs)
                self.assertEqual(self.snapshot(),before)
        self.path.write_bytes(owned);self.path.chmod(0o600);before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'mode edit'):modules.run(self.home,'start-shortcut',rollback=True)
        self.assertEqual(self.snapshot(),before)

    def test_duplicate_alias_malformed_and_legacy_ownership_refuse(self):
        for text in ('[Alt%2BF1.1]\nExec=a\n[Alt+F1.2]\nExec=b\n',
                     '[Alt%2BF1.1]bad\nExec=a\n','[ALT%2bF1.1]\nExec=a\n',
                     '[Alt%2BF1.1]\nExec=a\nExec=b\n','[Alt%2BF1.1]\n Exec=a\n'):
            self.path.write_text(text);before=self.snapshot()
            with self.assertRaises(RuntimeError):modules.run(self.home,'start-shortcut',apply=True,replace_start_shortcut=True)
            self.assertEqual(self.snapshot(),before)
        self.path.write_text(self.unrelated)
        legacy=self.home/'.local/state/lxqt-comfort/menu-integration.json';legacy.write_text('{}');before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'legacy'):modules.run(self.home,'start-shortcut',apply=True)
        self.assertEqual(self.snapshot(),before)

    def test_io_failure_restores_original_file_and_manifest(self):
        before=self.snapshot();real=modules.atomic
        def fail(path,*args):
            if path==self.path:raise OSError('fixture write failure')
            return real(path,*args)
        with patch.object(modules,'atomic',side_effect=fail),self.assertRaises(OSError):modules.run(self.home,'start-shortcut',apply=True)
        self.assertEqual(self.snapshot(),before)

    def test_crash_before_or_after_write_recovers_recorded_custom_replacement(self):
        self.custom();baseline=self.path.read_bytes();real=modules.atomic
        for after in (False,True):
            def crash(path,data,*args):
                if (not after and path==self.path) or (after and path==self.record and json.loads(data)['phase']=='complete'):raise Crash()
                return real(path,data,*args)
            with patch.object(modules,'atomic',side_effect=crash),self.assertRaises(Crash):self.opt('--apply','--replace-start-shortcut')
            saved=json.loads(self.record.read_text());self.assertEqual(saved['phase'],'pending')
            self.cli('--apply','--recover');self.assertEqual(json.loads(self.record.read_text())['phase'],'complete')
            self.opt('--remove','--apply');self.assertEqual(self.path.read_bytes(),baseline)

    def test_failed_recovery_retains_originals_and_refuses_user_edits(self):
        self.custom();real=modules.atomic
        def crash(path,*args):
            if path==self.path:raise Crash()
            return real(path,*args)
        with patch.object(modules,'atomic',side_effect=crash),self.assertRaises(Crash):self.opt('--apply','--replace-start-shortcut')
        self.path.write_bytes(self.path.read_bytes()+b'; later edit\n');before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Edited shortcut'):self.cli('--apply','--recover')
        self.assertEqual(self.snapshot(),before);self.commands.assert_not_called()

    def test_interrupted_restoration_can_resume(self):
        before=self.path.read_bytes();modules.run(self.home,'start-shortcut',apply=True)
        unlink=Path.unlink
        def crash(path,*args,**kwargs):
            if path==self.record:raise Crash()
            return unlink(path,*args,**kwargs)
        with patch.object(Path,'unlink',crash),self.assertRaises(Crash):modules.run(self.home,'start-shortcut',rollback=True)
        self.assertEqual(self.path.read_bytes(),before)
        with self.assertRaisesRegex(RuntimeError,'Finish'):modules.run(self.home,'start-shortcut',apply=True)
        modules.run(self.home,'start-shortcut',rollback=True);self.assertFalse(self.record.exists())

    def test_corrupt_record_symlink_and_launcher_removal_refuse(self):
        modules.run(self.home,'start-shortcut',apply=True);raw=self.record.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'shortcut'):install.rollback(self.home)
        for mutate in (lambda r:r.update(phase='unknown'),lambda r:r['edits'][0].update(file='elsewhere'),
                       lambda r:r.update(phase='pending',pending_from='!!')):
            data=json.loads(raw);mutate(data);self.record.write_text(json.dumps(data));before=self.snapshot()
            with self.assertRaises(ValueError):modules.run(self.home,'start-shortcut',apply=True)
            self.assertEqual(self.snapshot(),before)
        self.record.write_bytes(raw);data=self.path.read_bytes();self.path.unlink();other=self.home/'other';other.write_bytes(data);self.path.symlink_to(other)
        with self.assertRaises((ValueError,RuntimeError)):modules.run(self.home,'start-shortcut',rollback=True)
        self.assertEqual(other.read_bytes(),data)

    def test_installed_toolkit_preview_and_restore_without_qt_or_live_commands(self):
        toolkit=self.home/'.local/share/doroshell/toolkit';program=toolkit/'modules.py'
        env={'HOME':str(self.home),'PATH':'/empty','PYTHONDONTWRITEBYTECODE':'1'}
        before=self.path.read_bytes()
        for flags in ([],['--apply'],['--rollback']):
            r=subprocess.run([sys.executable,'-S','-B',str(program),'start-shortcut',*flags],env=env,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(self.path.read_bytes(),before)

    def test_invalid_replacement_scope_has_no_writes(self):
        before=self.snapshot()
        for args in (['--modules','menu','--replace-start-shortcut','--apply'],
                     ['--modules','start-shortcut','--remove','--replace-start-shortcut','--apply']):
            with self.assertRaises(ValueError):self.cli(*args)
            self.assertEqual(self.snapshot(),before)

    def test_stale_review_before_ownership_refuses_recovery_without_packages(self):
        self.custom();original=self.path.read_bytes();real=deploy.step
        def crash(home,name,*args,**kwargs):
            if name=='start-shortcut':raise Crash()
            return real(home,name,*args,**kwargs)
        with patch.object(deploy,'step',side_effect=crash),self.assertRaises(Crash):self.opt('--apply','--replace-start-shortcut')
        self.assertFalse(self.record.exists())
        self.path.write_bytes(original.replace(b'personal-start',b'later-start'));before=self.snapshot();self.build.reset_mock()
        with self.assertRaisesRegex(ValueError,'changed since review'):self.cli('--apply','--recover')
        self.assertEqual(self.snapshot(),before);self.commands.assert_not_called();self.build.assert_not_called()
        self.path.write_bytes(original);self.cli('--apply','--recover')
        self.opt('--remove','--apply');self.assertEqual(self.path.read_bytes(),original)

    def test_print_adapter_overlap_repeat_and_reverse_remove(self):
        before=self.path.read_bytes()
        self.cli('--modules','screenshots','start-shortcut','--apply')
        installed=self.path.read_bytes();self.assertIn(b'DoroShell Start',installed);self.assertIn(b'doroshell-screenshot',installed)
        self.cli('--modules','screenshots','start-shortcut','--apply');self.assertEqual(self.path.read_bytes(),installed)
        state=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Restore start-shortcut'):modules.run(self.home,'screenshots',rollback=True)
        self.assertEqual(self.snapshot(),state)
        self.cli('--modules','screenshots','start-shortcut','--remove','--apply');self.assertEqual(self.path.read_bytes(),before)

    def test_corrupt_journal_review_and_changed_recovery_consent_refuse(self):
        real=deploy.step
        def crash(home,name,*args,**kwargs):
            if name=='start-shortcut':raise Crash()
            return real(home,name,*args,**kwargs)
        with patch.object(deploy,'step',side_effect=crash),self.assertRaises(Crash):self.opt('--apply')
        pointer=json.loads((self.home/deploy.POINTER).read_text())
        path=self.home/'.local/state/doroshell/deployments'/pointer['transaction']/'journal.json';raw=path.read_bytes()
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'recorded shortcut'):self.cli('--apply','--recover','--replace-start-shortcut')
        self.assertEqual(self.snapshot(),before)
        for key,value in (('shortcut_before',None),('shortcut_before','bad'),('replace_start_shortcut','true')):
            data=json.loads(raw);data['request'][key]=value;path.write_text(json.dumps(data));before=self.snapshot()
            with self.assertRaises(ValueError):self.cli('--apply','--recover')
            self.assertEqual(self.snapshot(),before)
        data=json.loads(raw);data['format']=2
        for key in ('shortcut_before','replace_start_shortcut','panel'):data['request'].pop(key)
        path.write_text(json.dumps(data));before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'journal schema'):self.cli('--apply','--recover')
        self.assertEqual(self.snapshot(),before);self.commands.assert_not_called()

    def test_initial_combined_undo_and_separate_menu_undo_guard(self):
        install.rollback(self.home);before=self.path.read_bytes()
        self.opt('--apply');identifier=json.loads((self.home/deploy.POINTER).read_text())['transaction']
        self.cli('--apply','--undo',identifier);self.assertFalse(self.record.exists());self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse((self.home/'.local/bin/lxqt-comfort-menu').exists())
        self.cli('--modules','menu','--apply');identifier=json.loads((self.home/deploy.POINTER).read_text())['transaction']
        modules.run(self.home,'start-shortcut',apply=True);before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'shortcut'):deploy.undo(self.home,identifier)
        self.assertEqual(self.snapshot(),before)

    def test_setup_forwarding_order_and_live_refusal_before_writes(self):
        self.custom();before=self.snapshot()
        args=['setup.py','start-shortcut','menu','--home',str(self.home),'--apply','--replace-start-shortcut']
        with patch.object(sys,'argv',args),patch.object(setup.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as command:
            setup.main()
        calls=[c.args[0] for c in command.call_args_list if 'pacman' not in c.args[0]]
        self.assertEqual(Path(calls[0][1]).name,'install.py');self.assertEqual(calls[1][2],'start-shortcut');self.assertIn('--replace-start-shortcut',calls[1])
        with patch.object(sys,'argv',args+['--live']),patch.object(setup.subprocess,'run') as command,self.assertRaises(SystemExit):setup.main()
        command.assert_not_called();self.assertEqual(self.snapshot(),before)

    def test_unsupported_launcher_path_refuses_instead_of_guessing_exec_quoting(self):
        home=self.home/'space here';home.mkdir();before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'launcher path'):integrate.shortcut_plan(home)
        self.assertEqual(self.snapshot(),before)

    def test_binding_change_during_build_does_not_adopt_stale_replacement(self):
        self.custom();original=self.path.read_bytes()
        def change(*args):
            self.path.write_bytes(original.replace(b'personal-start',b'later-start'))
            return {}
        self.build.side_effect=change
        with self.assertRaisesRegex(RuntimeError,'changed during prerequisite/build'):self.opt('--apply','--replace-start-shortcut')
        self.assertFalse(self.record.exists());self.assertFalse((self.home/deploy.POINTER).exists())
        self.assertIn(b'later-start',self.path.read_bytes())

    def test_qsettings_reads_supported_binding_and_unrelated_trailing_bytes_survive(self):
        from PySide6.QtCore import QSettings
        for suffix in ('\n\n\n; tail  \n\n\n','\n; no final newline'):
            before=(self.unrelated+suffix).encode();self.path.write_bytes(before)
            modules.run(self.home,'start-shortcut',apply=True)
            self.assertTrue(self.path.read_bytes().startswith(before))
            cfg=QSettings(str(self.path),QSettings.Format.IniFormat)
            self.assertEqual(cfg.value('Alt+F1.1/Exec'),str(self.home/'.local/bin/lxqt-comfort-menu'))
            self.assertEqual(cfg.value('Alt+F1.1/Enabled'),'true');del cfg
            modules.run(self.home,'start-shortcut',rollback=True);self.assertEqual(self.path.read_bytes(),before)
        for section in ('Alt+F1.3','Alt%2BF1.7','Alt%2bF1.9'):
            before=(self.unrelated+'['+section+']').encode();self.path.write_bytes(before)
            modules.run(self.home,'start-shortcut',apply=True,replace_start_shortcut=True)
            cfg=QSettings(str(self.path),QSettings.Format.IniFormat)
            groups=[g for g in cfg.childGroups() if g.startswith('Alt+F1.')]
            self.assertEqual(len(groups),1)
            self.assertEqual(cfg.value(groups[0]+'/Exec'),str(self.home/'.local/bin/lxqt-comfort-menu'));del cfg
            modules.run(self.home,'start-shortcut',rollback=True);self.assertEqual(self.path.read_bytes(),before)
