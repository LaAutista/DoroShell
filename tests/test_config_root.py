"""Explicit config-root lifecycle: ordinary disposable directories, no live actions."""
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
import config_root
import deploy
import install
import modules
import setup


inspect_platform=compatibility.inspect


class Crash(BaseException):pass


class ConfigRootTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.home=Path(temp.name);self.root=self.home/'Config with spaces'
        self.file=self.root/'openbox/rc.xml';self.file.parent.mkdir(parents=True)
        self.xml=b'<openbox_config><!--keep--><desktops><number>4</number><firstdesk>3</firstdesk></desktops><other>untouched</other></openbox_config>\n'
        self.file.write_bytes(self.xml);self.file.chmod(0o640)
        self.other=self.root/'unrelated';self.other.write_bytes(b'private fixture untouched')
        self.default=self.home/'.config/openbox/rc.xml';self.default.parent.mkdir(parents=True);self.default.write_bytes(self.xml)
        self.record=self.home/'.local/state/doroshell/single-desktop.json'
        self.enterContext(patch.dict(os.environ,{'HOME':str(self.home)},clear=True))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(patch.object(compatibility,'inspect',side_effect=lambda *a,**kw:{'issues':[]}))
        self.enterContext(patch.object(compatibility,'package_versions',return_value={'openbox':'fixture'}))
        self.enterContext(patch('source_release.check'))
        self.enterContext(patch.object(deploy.os,'geteuid',return_value=1000))
        self.commands=self.enterContext(patch.object(deploy,'run'))
        self.build=self.enterContext(patch.object(deploy,'build_native',return_value={}))

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.read_bytes(),p.stat().st_mode&0o777) for p in self.home.rglob('*') if p.is_file()}
    def cli(self,*args):return deploy.main(['--home',str(self.home),*args])
    def opt(self,*args):return self.cli('--modules','single-desktop','--config-root',str(self.root),*args)
    def job(self):
        identifier=json.loads((self.home/deploy.POINTER).read_text())['transaction']
        return self.home/'.local/state/doroshell/deployments'/identifier/'journal.json',identifier

    def test_explicit_space_root_plan_apply_repeat_remove_exact(self):
        before=self.snapshot();self.opt();self.assertEqual(self.snapshot(),before)
        with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.root)}):self.opt('--apply')
        self.assertIn(b'<number>1</number><firstdesk>1</firstdesk>',self.file.read_bytes())
        saved=self.record.read_bytes();self.assertEqual(json.loads(saved)['config_root'],'Config with spaces')
        self.cli('--modules','single-desktop','--apply');self.assertEqual(self.record.read_bytes(),saved)
        self.cli('--modules','single-desktop','--remove','--apply')
        self.assertEqual(self.file.read_bytes(),self.xml);self.assertEqual(self.file.stat().st_mode&0o777,0o640)
        self.assertFalse(self.record.exists());self.assertEqual(self.default.read_bytes(),self.xml)
        self.assertEqual(self.other.read_bytes(),b'private fixture untouched');self.commands.assert_not_called()

    def test_root_change_environment_unsupported_modules_and_missing_path_refuse_before_work(self):
        before=self.snapshot()
        invalid=[['--modules','menu'],['--modules','single-desktop','menu'],['--modules','core'],['--modules','single-desktop','--with','start-shortcut']]
        for args in invalid:
            with self.assertRaises(ValueError):self.cli(*args,'--config-root',str(self.root),'--apply')
            self.assertEqual(self.snapshot(),before)
        missing=self.home/'missing config'
        with self.assertRaisesRegex(ValueError,'initialized Openbox'):self.cli('--modules','single-desktop','--config-root',str(missing),'--apply')
        self.assertFalse(missing.exists());self.assertEqual(self.snapshot(),before)
        with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.root)}),self.assertRaisesRegex(ValueError,'no implicit relocation'):
            self.cli('--modules','single-desktop','--apply')
        self.commands.assert_not_called();self.build.assert_not_called()
        self.opt('--apply');before=self.snapshot()
        for chosen in (self.home/'.config',self.home/'elsewhere'):
            with self.assertRaisesRegex(ValueError,'recorded ownership'):self.cli('--modules','single-desktop','--config-root',str(chosen),'--apply')
            self.assertEqual(self.snapshot(),before)
        with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.home/'.config')}),self.assertRaisesRegex(ValueError,'differs'):
            self.cli('--modules','single-desktop','--remove','--apply')
        self.assertEqual(self.snapshot(),before)

    def test_legacy_default_ownership_cannot_move_root(self):
        modules.run(self.home,'single-desktop',apply=True);before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'recorded ownership'):self.opt('--apply')
        self.assertEqual(self.snapshot(),before)
        modules.run(self.home,'single-desktop',rollback=True);self.opt('--apply')
        self.assertEqual(self.default.read_bytes(),self.xml)

    def test_paths_overlap_escape_symlink_and_data_state_roots_refuse(self):
        for root in (self.home,self.home/'.local',self.home/'.local/state/other',self.home/'.cache/new',self.home/'.icons/x',self.home/'.config/nested',self.home/'../escape',Path('/tmp/outside'),Path('relative')):
            before=self.snapshot()
            with self.assertRaises((ValueError,RuntimeError)):self.cli('--modules','single-desktop','--config-root',str(root),'--apply')
            self.assertEqual(self.snapshot(),before)
        alias=self.home/'link';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises((ValueError,RuntimeError)):self.cli('--modules','single-desktop','--config-root',str(alias),'--apply')
        for name in ('XDG_DATA_HOME','XDG_STATE_HOME'):
            with patch.dict(os.environ,{name:str(self.home/'foreign')}),self.assertRaisesRegex(ValueError,name):self.opt('--apply')
        for name in ('XDG_CACHE_HOME','XDG_RUNTIME_DIR'):
            with patch.dict(os.environ,{name:str(self.root/'nested')}),self.assertRaisesRegex(ValueError,'overlaps'):self.opt('--apply')
        self.commands.assert_not_called();self.build.assert_not_called()

    def test_exact_upgrade_undo_and_completed_edit_conflicts(self):
        self.opt('--apply');record=self.record.read_bytes();installed=self.file.read_bytes()
        self.cli('--modules','single-desktop','--apply');_,identifier=self.job()
        self.cli('--apply','--undo',identifier);self.assertEqual(self.file.read_bytes(),installed);self.assertEqual(self.record.read_bytes(),record)
        for data in (self.xml,installed.replace(b'<number>1',b'<number>3')):
            self.file.write_bytes(data);before=self.snapshot()
            for action in ('--apply','--remove'):
                with self.assertRaises(RuntimeError):self.cli('--modules','single-desktop',action,'--apply')
                self.assertEqual(self.snapshot(),before)
        self.file.write_bytes(installed);self.file.chmod(0o600);before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'mode edit'):self.cli('--modules','single-desktop','--apply')
        self.assertEqual(self.snapshot(),before)

    def test_unrelated_xml_edit_survives_restoration(self):
        self.opt('--apply');self.file.write_bytes(self.file.read_bytes().replace(b'untouched',b'new preference'))
        modules.run(self.home,'single-desktop',rollback=True)
        self.assertEqual(self.file.read_bytes(),self.xml.replace(b'untouched',b'new preference'))

    def test_interrupted_apply_before_and_after_write_recovers_root(self):
        real=modules.atomic
        for after in (False,True):
            def crash(path,data,*args):
                if (not after and path==self.file) or (after and path==self.record and json.loads(data).get('phase')=='complete'):raise Crash()
                return real(path,data,*args)
            with patch.object(modules,'atomic',side_effect=crash),self.assertRaises(Crash):self.opt('--apply')
            path,_=self.job();journal=json.loads(path.read_text());self.assertEqual(journal['format'],5)
            self.assertEqual(journal['request']['config_root'],'Config with spaces')
            self.cli('--apply','--recover');self.assertEqual(json.loads(self.record.read_text())['phase'],'complete')
            self.cli('--modules','single-desktop','--remove','--apply');self.assertEqual(self.file.read_bytes(),self.xml)

    def test_interrupted_before_module_ownership_and_root_override_refusal(self):
        with patch.object(deploy,'step',side_effect=Crash()),self.assertRaises(Crash):self.opt('--apply')
        self.assertFalse(self.record.exists());before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'recorded configuration root'):
            self.cli('--apply','--recover','--config-root',str(self.home/'.config'))
        self.assertEqual(self.snapshot(),before)
        self.file.write_bytes(self.xml.replace(b'<number>4',b'<number>7'));before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'changed before ownership'):self.cli('--apply','--recover')
        self.assertEqual(self.snapshot(),before)
        self.file.write_bytes(self.xml)
        self.cli('--apply','--recover');self.assertTrue(self.record.exists())

    def test_interrupted_restoration_resumes_and_pending_edits_refuse(self):
        self.opt('--apply');real=Path.unlink
        def crash(path,*a,**kw):
            if path==self.record:raise Crash()
            return real(path,*a,**kw)
        with patch.object(Path,'unlink',crash),self.assertRaises(Crash):self.cli('--modules','single-desktop','--remove','--apply')
        self.assertEqual(self.file.read_bytes(),self.xml)
        self.cli('--apply','--recover');self.assertFalse(self.record.exists())
        real=modules.atomic
        def crashwrite(path,*args):
            if path==self.file:raise Crash()
            return real(path,*args)
        with patch.object(modules,'atomic',side_effect=crashwrite),self.assertRaises(Crash):self.opt('--apply')
        self.file.write_bytes(self.xml.replace(b'<number>4',b'<number>7'));before=self.snapshot()
        with self.assertRaises(RuntimeError):self.cli('--apply','--recover')
        self.assertEqual(self.snapshot(),before)

    def test_write_failure_restores_baseline_and_keeps_recoverable_deployment(self):
        real=modules.atomic
        def fail(path,*args):
            if path==self.file:raise OSError('fixture failure')
            return real(path,*args)
        with patch.object(modules,'atomic',side_effect=fail),self.assertRaises(OSError):self.opt('--apply')
        self.assertEqual(self.file.read_bytes(),self.xml);self.assertFalse(self.record.exists())
        self.cli('--apply','--recover');self.assertTrue(self.record.exists())

    def test_malformed_root_records_and_retargeting_refuse_without_writes(self):
        self.opt('--apply');raw=self.record.read_bytes()
        for change in (lambda r:r.update(config_root='../escape'),lambda r:r.update(config_root=None),lambda r:r.pop('config_root'),lambda r:r.update(phase='unknown'),lambda r:r['edits'][0].update(file='.config/openbox/rc.xml')):
            data=json.loads(raw);change(data);self.record.write_text(json.dumps(data));before=self.snapshot()
            with self.assertRaises((ValueError,RuntimeError)):self.cli('--modules','single-desktop','--apply')
            self.assertEqual(self.snapshot(),before)
        self.record.write_bytes(raw)
        path,identifier=self.job();journal=json.loads(path.read_text());journal['request']['config_root']='../escape';path.write_text(json.dumps(journal));before=self.snapshot()
        with self.assertRaises((ValueError,RuntimeError)):deploy.undo(self.home,identifier)
        self.assertEqual(self.snapshot(),before)

    def test_installed_cli_and_setup_forwarding_use_root_as_single_argument(self):
        install.install(self.home,True);toolkit=self.home/'.local/share/doroshell/toolkit'
        self.assertTrue((toolkit/'config_root.py').is_file())
        env={'HOME':str(self.home),'PATH':'/empty','PYTHONDONTWRITEBYTECODE':'1'}
        for flags in ([],['--apply'],['--rollback']):
            r=subprocess.run([sys.executable,'-S','-B',str(toolkit/'modules.py'),'single-desktop','--config-root',str(self.root),*flags],env=env,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(self.file.read_bytes(),self.xml)
        argv=['setup.py','single-desktop','--config-root',str(self.root),'--home',str(self.home),'--apply']
        with patch.object(sys,'argv',argv),patch.object(setup.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as command:setup.main()
        target=command.call_args_list[-1].args[0];self.assertEqual(target[target.index('--config-root')+1],str(self.root))
        with patch.object(sys,'argv',argv+['--live']),patch.object(setup.subprocess,'run') as command,self.assertRaises(SystemExit):setup.main()
        command.assert_not_called()

    def test_real_capability_probe_allows_only_bound_config_root(self):
        env={'XDG_CURRENT_DESKTOP':'LXQt','XDG_SESSION_TYPE':'x11','XDG_CONFIG_HOME':str(self.root)}
        with patch.object(compatibility.shutil,'which',return_value='/fixture/pacman'):
            rejected=inspect_platform(self.home,['single-desktop'],env,{'ID':'arch'})
            self.assertTrue(any('XDG_CONFIG_HOME' in issue for issue in rejected['issues']))
            accepted=inspect_platform(self.home,['single-desktop'],env,{'ID':'arch'},config_root=self.root)
            self.assertEqual(accepted['issues'],[])
            with self.assertRaises(ValueError):inspect_platform(self.home,['menu'],env,{'ID':'arch'},config_root=self.root)
            env['XDG_STATE_HOME']=str(self.home/'different state')
            self.assertTrue(any('XDG_STATE_HOME' in issue for issue in inspect_platform(self.home,['single-desktop'],env,{'ID':'arch'},config_root=self.root)['issues']))

    def test_target_symlink_and_build_time_change_cannot_be_adopted(self):
        original=self.file.read_bytes()
        def change(*args):
            self.file.write_bytes(original.replace(b'<number>4',b'<number>7'))
            return {}
        self.build.side_effect=change
        with self.assertRaisesRegex(RuntimeError,'changed during prerequisite/build'):self.opt('--apply')
        self.assertFalse(self.record.exists());self.assertFalse((self.home/deploy.POINTER).exists())
        self.build.side_effect=None;self.file.write_bytes(original);self.opt('--apply')
        owned=self.file.read_bytes();self.file.unlink();target=self.home/'other.xml';target.write_bytes(owned);self.file.symlink_to(target)
        before=self.snapshot()
        with self.assertRaises((RuntimeError,ValueError)):self.cli('--modules','single-desktop','--remove','--apply')
        self.assertEqual(self.snapshot(),before);self.assertTrue(self.file.is_symlink())

    def test_completed_apply_and_remove_finalize_from_recorded_root(self):
        real=deploy.atomic
        for remove in (False,True):
            def crash(path,data,*args):
                if path==self.home/deploy.POINTER and json.loads(data)['status']=='complete':raise Crash()
                return real(path,data,*args)
            args=['--remove','--apply'] if remove else ['--apply']
            with patch.object(deploy,'atomic',side_effect=crash),self.assertRaises(Crash):self.opt(*args)
            journal,_=self.job();self.assertEqual(json.loads(journal.read_text())['status'],'complete')
            self.cli('--apply','--recover')
            self.assertEqual(json.loads((self.home/deploy.POINTER).read_text())['status'],'complete')
        self.assertEqual(self.file.read_bytes(),self.xml);self.assertFalse(self.record.exists())
