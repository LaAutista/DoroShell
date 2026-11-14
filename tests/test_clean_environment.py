"""Disposable-home boundaries; no host display, bus, package mutation or login."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CleanEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = {'HOME': str(self.home), 'PATH': str(self.home/'empty-bin'),
                    'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
                    'QT_QPA_PLATFORM': 'offscreen'}

    def run_cli(self, *args, no_site=True, cwd=ROOT, ok=True):
        result = subprocess.run([sys.executable, *(['-S'] if no_site else []), *map(str,args)],
                                cwd=cwd, env=self.env, capture_output=True, text=True, timeout=30)
        if ok: self.assertEqual(result.returncode, 0, result.stderr)
        else: self.assertNotEqual(result.returncode, 0)
        return result

    def files(self):
        return {str(p.relative_to(self.home)): (p.read_bytes(),p.stat().st_mode & 0o777)
                for p in self.home.rglob('*') if p.is_file()}

    def test_stdlib_help_preview_packages_do_not_write(self):
        for script in ('setup.py','install.py','modules.py','wallpaper/build.py','display/build_candidate.py','panel/build.py','screengrab/build.py'):
            self.run_cli(ROOT/script, '--help')
        self.run_cli('setup.py','menu','--home',self.home)
        self.run_cli('setup.py','menu','--packages')
        self.assertEqual(self.files(), {})

    def test_missing_package_manager_is_actionable_without_writes(self):
        result=self.run_cli('setup.py','menu','--apply','--home',self.home,ok=False)
        self.assertIn('Cannot query pacman',result.stderr)
        self.assertNotIn('Traceback',result.stderr)
        self.assertEqual(self.files(), {})

    def test_missing_python_bindings_refuses_before_writes(self):
        result=self.run_cli('install.py','menu','--apply','--home',self.home,ok=False)
        self.assertIn('Install missing dependencies',result.stderr)
        self.assertNotIn('Traceback',result.stderr)
        self.assertEqual(self.files(), {})

    def test_missing_package_refuses_before_module_dispatch(self):
        bin_dir=self.home/'empty-bin';bin_dir.mkdir()
        fake=bin_dir/'pacman';fake.write_text('#!/bin/sh\nexit 1\n');fake.chmod(0o755)
        before=self.files()
        result=self.run_cli('setup.py','menu','--apply','--home',self.home,ok=False)
        self.assertIn('Missing packages:',result.stderr)
        self.assertEqual(self.files(), before)

    def test_installed_toolkit_repeat_and_exact_rollback_without_source_cwd(self):
        sentinel=self.home/'.config/unrelated';sentinel.parent.mkdir(parents=True)
        sentinel.write_bytes(b'keep\x00exact');sentinel.chmod(0o640)
        old=self.home/'.local/share/lxqt-comfort/start.svg';old.parent.mkdir(parents=True)
        old.write_bytes(b'prior icon');old.chmod(0o600)
        # Package availability is simulated; this never installs or queries OS packages.
        bin_dir=self.home/'empty-bin';bin_dir.mkdir()
        fake=bin_dir/'pacman';fake.write_text('#!/bin/sh\nexit 0\n');fake.chmod(0o755)
        before=self.files()
        self.run_cli('setup.py','menu','--apply','--home',self.home,no_site=False)
        installed=self.files()
        toolkit=self.home/'.local/share/doroshell/toolkit'
        self.run_cli(toolkit/'install.py','menu','--apply','--home',self.home,no_site=False,cwd=self.home)
        self.assertEqual(installed,self.files())
        code="import sys; sys.path.insert(0,sys.argv[1]); import menu.start_menu, menu.app_search, menu.folder_cascade, portable_settings, input_preferences, settings, modules, wallpaper.install; print('imports passed')"
        self.run_cli('-c',code,toolkit,no_site=False,cwd=self.home)
        manifest=json.loads((self.home/'.local/state/lxqt-comfort/menu-install.json').read_text())
        self.assertTrue(any(n.endswith('/app_search.py') for n in manifest))
        self.assertTrue(any(n.endswith('/folder_cascade.py') for n in manifest))
        self.assertTrue(any(n.endswith('/portable_settings.py') for n in manifest))
        self.assertTrue(any(n.endswith('/input_preferences.py') for n in manifest))
        # Rollback needs no GUI bindings on this no-native-panel baseline.
        self.run_cli(toolkit/'install.py','menu','--rollback','--home',self.home,cwd=self.home)
        restored=self.files()
        # The input writer/removal lock must retain its inode for waiting clients.
        self.assertEqual(restored.pop('.config/doroshell/input-preferences.lock'),(b'',0o644))
        self.assertEqual(before,restored)

    def test_scoped_stdlib_module_and_rollback_preserve_unrelated_file(self):
        p=self.home/'.config/mimeapps.list';p.parent.mkdir(parents=True)
        p.write_text('[Default Applications]\ntext/plain=old.desktop;\n');p.chmod(0o640)
        missing=self.run_cli('modules.py','kate','--home',self.home,'--apply',ok=False)
        self.assertIn('Install kate before opting in',missing.stderr)
        bin_dir=self.home/'empty-bin';bin_dir.mkdir()
        fake=bin_dir/'kate';fake.write_text('#!/bin/sh\nexit 99\n');fake.chmod(0o755)
        before=self.files()
        self.run_cli('modules.py','kate','--home',self.home)
        self.assertEqual(before,self.files())
        self.run_cli('modules.py','kate','--home',self.home,'--apply')
        self.run_cli('modules.py','kate','--home',self.home,'--apply')
        self.run_cli('modules.py','kate','--home',self.home,'--rollback')
        self.assertEqual(before,self.files())

    def test_display_query_without_capabilities_is_structured(self):
        result=self.run_cli('display/backend.py','query',ok=False)
        self.assertIn('error',json.loads(result.stdout))
        self.assertNotIn('Traceback',result.stderr)
        self.assertEqual(self.files(), {})

    def test_optional_previews_do_not_create_lock_or_state(self):
        self.run_cli('modules.py','wallpaper-glass','--home',self.home)
        self.assertEqual(self.files(), {})
        self.run_cli('modules.py','clipboard','--home',self.home,ok=False)
        self.assertEqual(self.files(), {})
        self.run_cli('modules.py','wallpaper','--home',self.home,ok=False)
        self.assertEqual(self.files(), {})

    def test_builders_refuse_nonempty_work_before_external_tools(self):
        work=self.home/'build';work.mkdir()
        marker=work/'keep';marker.write_text('existing source')
        before=self.files()
        for script in ('wallpaper/build.py','panel/build.py','screengrab/build.py'):
            result=self.run_cli(script,'--work',work,ok=False)
            self.assertIn('empty',result.stderr.lower())
            self.assertEqual(self.files(),before)

    def test_optional_prerequisite_diagnostics_through_both_clis(self):
        for script in ('modules.py', 'setup.py'):
            for module, message in (('clipboard','Stage the DoroShell native panel'),
                                    ('wallpaper','pass --wallpaper-binary')):
                with self.subTest(script=script,module=module):
                    result=self.run_cli(script,module,'--home',self.home,ok=False)
                    self.assertIn(message,result.stderr)
                    self.assertNotIn('Traceback',result.stderr)
                    self.assertEqual(self.files(),{})
        panel=self.home/'.config/doroshell/panel.conf';panel.parent.mkdir(parents=True)
        for content, message in (('[panel1]\nplugins=clock\n','No notification-area widget'),
                                 ('[panel1]\nplugins=doroClipboard,statusnotifier\n[doroClipboard]\ntype=taskbar\n','Existing doroClipboard widget differs')):
            panel.write_text(content);before=self.files()
            result=self.run_cli('modules.py','clipboard','--home',self.home,ok=False)
            self.assertIn(message,result.stderr)
            self.assertNotIn('Traceback',result.stderr)
            self.assertEqual(self.files(),before)

    def test_wallpaper_invalid_build_diagnostics_without_writes(self):
        import hashlib
        binary=self.home/'candidate';binary.write_bytes(b'not executed');binary.chmod(0o755)
        proof=self.home/'doroshell-wallpaper-build.json'
        digest=hashlib.sha256(binary.read_bytes()).hexdigest()
        cases=[('{','Invalid wallpaper build record'),('[]','Invalid wallpaper build record'),
               ('{}','Invalid wallpaper build record'),
               (json.dumps({'sha256':'changed'}),'Native desktop changed'),
               (json.dumps({'sha256':digest,'format':99}),'Unsupported wallpaper build record'),
               (json.dumps({'sha256':digest,'format':3}),'Decoder helper missing')]
        for data,message in cases:
            with self.subTest(data=data):
                proof.write_text(data);before=self.files()
                result=self.run_cli('setup.py','wallpaper','--home',self.home,'--wallpaper-binary',binary,ok=False)
                self.assertIn(message,result.stderr)
                self.assertNotIn('Traceback',result.stderr)
                self.assertEqual(self.files(),before)

    def test_unexpected_programming_errors_keep_traceback(self):
        code="""import sys,runpy
sys.path.insert(0,sys.argv[1])
import clipboard.install
def broken(home): raise ValueError('unexpected programming failure')
clipboard.install.plans=broken
sys.argv=['modules.py','clipboard','--home',sys.argv[2]]
runpy.run_path('modules.py',run_name='__main__')
"""
        result=self.run_cli('-c',code,ROOT,self.home,ok=False)
        self.assertIn('Traceback',result.stderr)
        self.assertIn('unexpected programming failure',result.stderr)
        self.assertEqual(self.files(),{})
