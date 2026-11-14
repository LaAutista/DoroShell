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
        command=next(line for line in (ROOT/'README.md').read_text().splitlines() if line.startswith('bash -c '))
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
