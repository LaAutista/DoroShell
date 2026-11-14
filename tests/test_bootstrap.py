"""Download/cleanup/argument boundaries with a fake Git transport; no network."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name);bin_dir=self.home/'bin';bin_dir.mkdir()
        self.env=dict(os.environ,HOME=str(self.home),PATH=str(bin_dir)+':'+os.environ['PATH'])
        gh=bin_dir/'gh';gh.write_text('#!/bin/sh\ntouch "$HOME/gh-invoked"\nexit 1\n');gh.chmod(0o755)
        git=bin_dir/'git'
        git.write_text('''#!/usr/bin/python3
import json,os,pathlib,sys
a=sys.argv[1:];root=pathlib.Path(a[1]);a=a[2:]
if 'fetch' in a:
 assert a[:2]==['-c','credential.helper='], a
 assert os.environ.get('GIT_TERMINAL_PROMPT')=='0'
while a and a[0]=='-c':a=a[2:]
if a[0]=='init':(root/'.git').mkdir()
elif a[0]=='fetch':
 if os.environ.get('FAIL_FETCH'):sys.exit(1)
 (root/'deploy.py').write_text('import json,sys;print("DEPLOY "+json.dumps(sys.argv[1:]))')
 (root/'source_release.py').write_text('print("INVENTORY VERIFIED (fixture)")')
 (root/'release.json').write_text(json.dumps({'channel':'development'}))
elif a[0]=='rev-parse':print('f'*40)
elif a[0]=='status':print(os.environ.get('DIRTY',''))
''');git.chmod(0o755)

    def run_bootstrap(self,*args,ok=True):
        result=subprocess.run(['/usr/bin/bash',str(ROOT/'bootstrap.sh'),*args],env=self.env,capture_output=True,text=True)
        if ok:self.assertEqual(result.returncode,0,result.stderr)
        else:self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.home/"gh-invoked").exists())
        return result

    def test_complete_download_plan_and_apply_forwarding_and_repeat(self):
        result=self.run_bootstrap('--plan','--modules','menu')
        self.assertIn('DEPLOY ["--modules", "menu"]',result.stdout)
        root=self.home/'.local/share/doroshell/sources'
        self.assertEqual([p.name for p in root.iterdir()],['f'*40])
        result=self.run_bootstrap('--apply','--modules','menu')
        self.assertIn('DEPLOY ["--apply", "--modules", "menu"]',result.stdout)
        self.assertEqual([p.name for p in root.iterdir()],['f'*40])

    def test_failed_fetch_never_invokes_install_and_cleans_download(self):
        self.env['FAIL_FETCH']='1'
        result=self.run_bootstrap('--apply',ok=False)
        self.assertNotIn('DEPLOY',result.stdout)
        self.assertEqual(list((self.home/'.local/share/doroshell/sources').iterdir()),[])

    def test_panel_selection_is_forwarded_as_one_argument(self):
        args=['--apply','--modules','native-panel','--panel','panel2','--home',str(self.home/'a space')]
        result=self.run_bootstrap(*args)
        forwarded=json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith('DEPLOY ')))
        self.assertEqual(forwarded,args)
        result=self.run_bootstrap('--apply','--panel','panel2; touch '+str(self.home/'should-not-run'),ok=False)
        self.assertIn('Choose an existing panelN',result.stderr);self.assertNotIn('DEPLOY',result.stdout)
        self.assertFalse((self.home/'should-not-run').exists())

    def test_invalid_arguments_never_reach_acquisition_or_authentication(self):
        self.env['PATH']=str(self.home/'bin')
        for name in ('git','sudo','pacman'):
            path=self.home/'bin'/name
            path.write_text('#!/usr/bin/python3\nimport os,pathlib\npathlib.Path(os.environ["HOME"],"unexpected-command").write_text("called")\nraise SystemExit(1)\n');path.chmod(0o755)
        invalid=[['--apply','--prerequisites'],['--apply','--unknown'],['--apply','--panel','../panel2'],
                 ['--apply','--panel','panel2\n'],['--apply','--panel'],['--apply','--plan'],
                 ['--apply','--modules','unknown'],['--apply','--modules'],['--apply','--with','menu'],
                 ['--apply','--theme','unknown'],['--apply','--home'],['--apply','--channel','unknown'],
                 ['--apply','--ref','../main'],['--apply','--undo','invalid'],['--apply','--panel=panel2'],
                 ['--apply','--panel','panel2','--modules','menu'],['--prerequisites','--remove'],
                 ['--apply','--help'],['--apply','positional'],
                 ['--apply','--undo','20261114T120000-0123456789ab','--recover']]
        for args in invalid:
            with self.subTest(args=args):
                result=self.run_bootstrap(*args,ok=False)
                self.assertEqual(result.returncode,2,result.stderr)
                self.assertIn('No prerequisites requested',result.stderr)
                self.assertFalse((self.home/'unexpected-command').exists())
                self.assertFalse((self.home/'.local').exists())
        result=self.run_bootstrap('--prerequisites',ok=False)
        self.assertEqual(result.returncode,1);self.assertIn('without --prerequisites/--no-packages',result.stderr)
        self.assertFalse((self.home/'unexpected-command').exists());self.assertFalse((self.home/'.local').exists())

    def test_shell_option_catalog_accepts_current_modules_and_optional_choices(self):
        import deploy
        # Keep the small pre-acquisition allowlist aligned with the real parser.
        for module in ['core',*deploy.ORDER]:
            result=self.run_bootstrap('--plan','--modules',module)
            self.assertIn('DEPLOY',result.stdout)
        for extra in deploy.OPTIONAL:
            result=self.run_bootstrap('--plan','--modules','menu','--with',extra)
            self.assertIn('DEPLOY',result.stdout)
        self.run_bootstrap('--plan','--modules','menu','--with','clipboard','--panel','panel2')
        self.run_bootstrap('--recover','--apply','--panel','panel2','--modules','menu')

    def test_help_needs_no_tools_or_writes(self):
        self.env['PATH']='/empty'
        result=self.run_bootstrap('--help')
        self.assertIn('Usage:',result.stdout);self.assertFalse((self.home/'.local').exists())

    def test_missing_acquisition_tools_plan_never_prompts_or_writes(self):
        self.env['PATH']=str(self.home/'bin')  # Fake Git exists, Python is unavailable by PATH.
        for name in ('sudo','pacman'):
            path=self.home/'bin'/name
            path.write_text('#!/bin/sh\necho invoked > "$HOME/package-invoked"\nexit 1\n');path.chmod(0o755)
        result=self.run_bootstrap('--plan','--panel','panel2',ok=False)
        self.assertIn('before layout validation',result.stderr)
        self.assertFalse((self.home/'package-invoked').exists())
        self.assertFalse((self.home/'.local').exists())

    def test_missing_tool_names_and_no_packages_are_accurate(self):
        self.env['PATH']=str(self.home/'bin')
        git=self.home/'bin/git';fake_git=git.read_bytes()
        for missing in (('git',),('python3',),('git','python3')):
            git.unlink(missing_ok=True);(self.home/'bin/python3').unlink(missing_ok=True)
            if 'git' not in missing:git.write_bytes(fake_git);git.chmod(0o755)
            if 'python3' not in missing:(self.home/'bin/python3').symlink_to('/usr/bin/python3')
            result=self.run_bootstrap('--apply','--no-packages',ok=False)
            self.assertIn('Missing acquisition commands: '+' '.join(missing)+'\n',result.stderr)
            self.assertIn('no packages changed',result.stderr)
            self.assertFalse((self.home/'.local').exists())

    def test_missing_acquisition_tools_apply_cancel_failure_or_unavailable_stops(self):
        self.env['PATH']=str(self.home/'bin')
        for name in ('sudo','pacman'):
            path=self.home/'bin'/name
            path.write_text('#!/usr/bin/python3\nimport os,pathlib,sys\npathlib.Path(os.environ["HOME"],"package-argv").write_text(repr(sys.argv[1:]))\nsys.exit(int(os.environ.get("PACKAGE_EXIT","1")))\n');path.chmod(0o755)
        for code in ('1','127','0'):
            self.env['PACKAGE_EXIT']=code
            result=self.run_bootstrap('--apply',ok=False)
            self.assertIn('Missing acquisition commands: python3',result.stderr)
            self.assertIn('pacman -Syu --needed git python',result.stderr)
            self.assertEqual((self.home/'package-argv').read_text(),repr(['pacman','-Syu','--needed','git','python']))
            self.assertFalse((self.home/'.local').exists())
            if code=='0':self.assertIn('still unavailable',result.stderr)

    def test_missing_acquisition_tools_apply_continues_only_after_recheck(self):
        self.env['PATH']=str(self.home/'bin')
        for name in ('mkdir','mktemp','rm','mv'):(self.home/'bin'/name).symlink_to('/usr/bin/'+name)
        (self.home/'bin/pacman').write_text('fixture; never executed directly')
        (self.home/'bin/pacman').chmod(0o755)
        sudo=self.home/'bin/sudo'
        sudo.write_text('''#!/usr/bin/python3
import os,pathlib,sys
assert sys.argv[1:]==['pacman','-Syu','--needed','git','python']
pathlib.Path(os.environ['HOME'],'bin/python3').symlink_to('/usr/bin/python3')
''');sudo.chmod(0o755)
        result=self.run_bootstrap('--apply','--modules','menu')
        self.assertIn('Prerequisite plan:',result.stderr)
        self.assertIn('DEPLOY ["--apply", "--modules", "menu"]',result.stdout)

    def test_dirty_sources_stable_mislabel_and_bad_ref_refuse(self):
        self.run_bootstrap('--plan');self.env['DIRTY']=' M custom.py'
        self.assertIn('local edits',self.run_bootstrap('--apply',ok=False).stderr)
        self.env.pop('DIRTY')
        self.assertIn('not declared stable',self.run_bootstrap('--channel','stable',ok=False).stderr)
        self.assertIn('Invalid revision',self.run_bootstrap('--ref','../main',ok=False).stderr)

    def test_source_parent_symlink_is_not_followed(self):
        target=self.home/'elsewhere';target.mkdir()
        (self.home/'.local').symlink_to(target)
        result=self.run_bootstrap('--plan',ok=False)
        self.assertIn('symlink',result.stderr)
        self.assertEqual(list(target.iterdir()),[])

    def test_exact_readme_one_liner_does_not_execute_partial_download(self):
        # Exercise the exact documented shell quoting, substituting curl only.
        command=(ROOT/'README.md').read_text().split('```sh\n',1)[1].split('\n```',1)[0]
        curl=self.home/'bin/curl'
        curl.write_text('''#!/usr/bin/python3
import os,pathlib,sys
args=sys.argv[1:]
assert '--fail' in args and '--location' in args
assert 'https://raw.githubusercontent.com/LaAutista/DoroShell/main/bootstrap.sh' in args
pathlib.Path(args[args.index('--output')+1]).write_text('echo EXECUTED-BOOTSTRAP "$@"')
sys.exit(22 if os.environ.get('FAIL_FETCH') else 0)
''');curl.chmod(0o755)
        result=subprocess.run(['/usr/bin/bash','-c',command],env=self.env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('EXECUTED-BOOTSTRAP --apply',result.stdout)
        self.env['FAIL_FETCH']='1'
        result=subprocess.run(['/usr/bin/bash','-c',command],env=self.env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertNotIn('EXECUTED-BOOTSTRAP',result.stdout)
