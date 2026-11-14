"""No actual authentication, package commands, network or personal configuration."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class PrerequisiteTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.home=Path(temporary.name);self.bin=self.home/'bin';self.bin.mkdir()
        self.env={'HOME':str(self.home),'PATH':str(self.bin),'PYTHONDONTWRITEBYTECODE':'1'}

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.read_bytes(),p.stat().st_mode&0o777)
                for p in self.home.rglob('*') if p.is_file()}

    def cli(self,*args):
        return subprocess.run([sys.executable,'-S','-B',str(ROOT/'deploy.py'),*args],
                              env=self.env,capture_output=True,text=True)

    def readme(self,plan=False,no_packages=False,args=None):
        command=(ROOT/'README.md').read_text().split('```sh\n',1)[1].split('\n```',1)[0]
        if args is not None:command=command.removesuffix('doroshell --apply')+'doroshell '+shlex.join(args)
        if plan:command=command.removesuffix('doroshell --apply')+'doroshell --plan'
        if no_packages:command+=' --no-packages'
        return subprocess.run(['/usr/bin/bash','-c',command],env=self.env,capture_output=True,text=True)

    def test_scoped_guidance_needs_no_bindings_or_user_state(self):
        pointer=self.home/'.local/state/doroshell/deployment.json';pointer.parent.mkdir(parents=True)
        pointer.write_text('invalid private state; guidance must not read this')
        before=self.snapshot()
        result=self.cli('--prerequisites','--modules','menu')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('sudo pacman -Syu --needed curl git python',result.stdout)
        self.assertIn('sudo pacman -Syu --needed pyside6 python-gobject',result.stdout)
        self.assertIn('Selected modules: menu\n',result.stdout)
        self.assertNotIn('qt6-multimedia',result.stdout)
        self.assertNotIn('base-devel',result.stdout)
        self.assertIn('not an install/readiness check',result.stdout)
        self.assertEqual(self.snapshot(),before)
        result=self.cli('--prerequisites','--modules','menu','--with','display')
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('qt6-multimedia',result.stdout)
        self.assertEqual(self.snapshot(),before)

    def test_guidance_cannot_be_combined_with_actions_or_invalid_selection(self):
        before=self.snapshot()
        for args in [('--apply',),('--remove',),('--recover',),('--undo','invalid'),
                     ('--panel','../panel2'),('--panel','panel2','--modules','menu')]:
            result=self.cli('--prerequisites',*args)
            self.assertNotEqual(result.returncode,0);self.assertNotIn('Traceback',result.stderr)
            self.assertEqual(self.snapshot(),before)

    def test_expected_dependency_import_failures_are_actionable_but_runtime_errors_escape(self):
        fake=self.home/'imports';(fake/'PySide6').mkdir(parents=True);(fake/'gi/repository').mkdir(parents=True)
        (fake/'PySide6/__init__.py').write_text('');(fake/'gi/__init__.py').write_text('')
        self.env['PYTHONPATH']=str(fake)+':'+str(ROOT)
        program='''import compatibility,source_release,runpy,sys
compatibility.inspect=lambda *a: {'issues': []}
compatibility.package_versions=lambda p: dict.fromkeys(p,'fixture')
source_release.check=lambda *a: None
source_release.source_files=lambda *a: []
sys.argv=['deploy.py','--modules','native-panel','--panel','panel2','--apply','--no-packages']
runpy.run_module('deploy',run_name='__main__')
'''
        for qt,gio,expected in [('raise ImportError("fixture missing Qt library")','Gio=object()','diagnostic'),
                                 ('class QSettings: pass','','diagnostic'),
                                 ('raise TypeError("unexpected fixture failure")','Gio=object()','traceback')]:
            (fake/'PySide6/QtCore.py').write_text(qt);(fake/'gi/repository/__init__.py').write_text(gio)
            before=self.snapshot()
            result=subprocess.run([sys.executable,'-S','-B','-c',program],env=self.env,cwd=ROOT,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            if expected=='diagnostic':
                self.assertNotIn('Traceback',result.stderr)
                self.assertIn('sudo pacman -Syu --needed pyside6 python-gobject',result.stderr)
                self.assertIn('system Python',result.stderr)
            else:self.assertIn('unexpected fixture failure',result.stderr);self.assertIn('Traceback',result.stderr)
            self.assertEqual(self.snapshot(),before)

    def test_missing_curl_plan_and_missing_admin_tools_stop_before_download(self):
        (self.bin/'bash').symlink_to('/usr/bin/bash')
        before=self.snapshot()
        result=self.readme(plan=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('Plan only',result.stderr)
        self.assertIn('sudo pacman -Syu --needed curl',result.stderr)
        result=self.readme(no_packages=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('--no-packages',result.stderr)
        result=self.readme()
        self.assertNotEqual(result.returncode,0);self.assertIn('require sudo and Arch pacman',result.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_readme_rejects_invalid_arguments_before_curl_or_package_actions(self):
        (self.bin/'bash').symlink_to('/usr/bin/bash')
        for name in ('sudo','pacman'):
            p=self.bin/name;p.write_text('#!/usr/bin/python3\nimport os,pathlib\npathlib.Path(os.environ["HOME"],"unexpected-command").write_text("called")\nraise SystemExit(1)\n');p.chmod(0o755)
        invalid=[['--apply','--prerequisites'],['--apply','--unknown'],['--apply','--panel','../panel2'],
                 ['--apply','--panel','panel2\n'],['--apply','--panel'],['--apply','--plan'],
                 ['--apply','--modules','menu'],['--apply','--panel=panel2'],['--apply','positional']]
        for curl_available in (False,True):
            if curl_available:(self.bin/'curl').symlink_to(self.bin/'sudo')
            for args in invalid:
                with self.subTest(curl=curl_available,args=args):
                    before=self.snapshot();result=self.readme(args=args)
                    self.assertEqual(result.returncode,2,result.stderr)
                    self.assertIn('No prerequisites requested',result.stderr)
                    self.assertFalse((self.home/'unexpected-command').exists())
                    self.assertEqual(self.snapshot(),before)

    def test_missing_curl_apply_cancel_failure_or_no_effect_cannot_download(self):
        (self.bin/'bash').symlink_to('/usr/bin/bash')
        for name in ('sudo','pacman'):
            p=self.bin/name
            p.write_text('#!/usr/bin/python3\nimport json,os,pathlib,sys\npathlib.Path(os.environ["HOME"],"package-argv").write_text(json.dumps(sys.argv[1:]))\nsys.exit(int(os.environ["PACKAGE_EXIT"]))\n');p.chmod(0o755)
        for code in ('1','127','0'):
            self.env['PACKAGE_EXIT']=code
            result=self.readme();self.assertNotEqual(result.returncode,0)
            self.assertEqual(json.loads((self.home/'package-argv').read_text()),['pacman','-Syu','--needed','curl'])
            self.assertNotIn('EXECUTED-BOOTSTRAP',result.stdout)
            if code=='0':self.assertIn('curl is still unavailable',result.stderr)

    def test_missing_curl_apply_rechecks_then_downloads_complete_script(self):
        for name in ('bash','mktemp','rm'):(self.bin/name).symlink_to('/usr/bin/'+name)
        curl_script='''#!/usr/bin/python3
import pathlib,sys
assert '--fail' in sys.argv
pathlib.Path(sys.argv[sys.argv.index('--output')+1]).write_text('echo EXECUTED-BOOTSTRAP "$@"')
'''
        sudo=self.bin/'sudo'
        sudo.write_text('#!/usr/bin/python3\nimport os,pathlib,sys\nassert sys.argv[1:]==["pacman","-Syu","--needed","curl"]\np=pathlib.Path(os.environ["HOME"],"bin/curl")\np.write_text('+repr(curl_script)+')\np.chmod(0o755)\n');sudo.chmod(0o755)
        (self.bin/'pacman').symlink_to('/usr/bin/false')
        temp=self.home/'downloads';temp.mkdir();self.env['TMPDIR']=str(temp)
        result=self.readme(args=['--apply','--panel','panel2']);self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('EXECUTED-BOOTSTRAP --apply --panel panel2',result.stdout);self.assertEqual(list(temp.iterdir()),[])
