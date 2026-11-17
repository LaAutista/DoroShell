"""Login check and background rebuild of native builds after a system update."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import modules
import native_rebuild
from panel.profile import launcher as panel_launcher


class NativeRebuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        notify = patch('native_rebuild.notify')
        self.notify = notify.start()
        self.addCleanup(notify.stop)
        self.addCleanup(self.temp.cleanup)
        self.current = self.home/'old/build/pcmanfm/pcmanfm-qt'

    def test_missing_libraries_parses_ldd(self):
        out = '\tlibfm-qt6.so.17 => not found\n\tlibQt6Core.so.6 => /usr/lib/libQt6Core.so.6 (0x1)\n'
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, out, '')):
            self.assertEqual(native_rebuild.missing_libraries('x'), ['libfm-qt6.so.17'])
        with patch('subprocess.run', side_effect=FileNotFoundError):
            self.assertEqual(native_rebuild.missing_libraries('x'), [])

    def test_login_starts_rebuild_only_when_libraries_are_missing(self):
        self.current.parent.mkdir(parents=True); self.current.write_bytes(b'x')
        with patch('native_rebuild.missing_libraries', return_value=[]), patch('subprocess.Popen') as popen:
            self.assertEqual(native_rebuild.login('desktop', self.current), 0)
            popen.assert_not_called()
        with patch('native_rebuild.missing_libraries', return_value=['libfm-qt6.so.17']), patch('subprocess.Popen') as popen:
            self.assertEqual(native_rebuild.login('desktop', self.current), 1)
            args, kwargs = popen.call_args
            self.assertEqual(args[0][2:5], ['rebuild', 'desktop', '--current'])
            self.assertTrue(kwargs['start_new_session'])

    def rebuild(self, **kwargs):
        return native_rebuild.rebuild('desktop', self.current, self.home, **kwargs)

    def status(self):
        return json.loads((self.home/'.local/state/doroshell/native-rebuild.json').read_text())['desktop']

    def test_success_and_failure_are_recorded_and_failure_is_not_retried_at_once(self):
        with patch('native_rebuild.system_version', return_value='2.5.0'), \
             patch('native_rebuild.build_and_stage', side_effect=RuntimeError('patch does not apply')) as build:
            self.assertEqual(self.rebuild(), 1)
            self.assertEqual(self.status()['result'], 'failed')
            self.assertIn('patch does not apply', self.notify.call_args.args[1])
            self.assertEqual(self.rebuild(), 1)  # Same version, failed recently: notify only.
            self.assertEqual(build.call_count, 1)
            self.assertEqual(self.rebuild(force=True), 1)
            self.assertEqual(build.call_count, 2)
        with patch('native_rebuild.system_version', return_value='2.5.1'), patch('native_rebuild.build_and_stage', return_value=(None, True)) as build:
            self.assertEqual(self.rebuild(), 0)
            work = build.call_args.args[2]
            self.assertTrue(work.name.startswith('desktop-2.5.1-'))
            self.assertEqual(self.status()['result'], 'ready')
            self.assertIn('next login', self.notify.call_args.args[1])

    def test_second_rebuild_waits_on_the_lock(self):
        state = self.home/'.local/state/doroshell'; state.mkdir(parents=True)
        with (state/'native-rebuild-desktop.lock').open('a') as held, patch('native_rebuild.build_and_stage') as build:
            fcntl.flock(held, fcntl.LOCK_EX)
            self.assertEqual(self.rebuild(), 0)
            build.assert_not_called()

    def test_unreadable_version_notifies(self):
        with patch('native_rebuild.system_version', side_effect=RuntimeError('Could not read')), \
             patch('native_rebuild.build_and_stage') as build:
            self.assertEqual(self.rebuild(), 1)
            build.assert_not_called()
            self.assertTrue(self.notify.call_args.kwargs['urgent'])

    def test_snapshot_copies_tracked_sources_only(self):
        root = Path(native_rebuild.ROOT)
        private = root/'local-private-notes.env'
        private.write_text('secret')
        self.addCleanup(private.unlink)
        inside = root/'build-in-checkout'  # A build directory inside the checkout must not copy itself.
        self.addCleanup(lambda: __import__('shutil').rmtree(inside, ignore_errors=True))
        for work in (self.home, inside):
            native_rebuild.snapshot(work)
            recipe = work/'recipe'
            for name in ('native_rebuild.py', 'modules.py', 'wallpaper/build.py', 'wallpaper/desktop-video.patch',
                         'display/pcmanfm-advanced.patch', 'panel/build.py', 'panel/patches/0012-calendar-holidays-dst.patch'):
                self.assertTrue((recipe/name).is_file(), name)
            for name in ('assets', 'tests', '.git', 'local-private-notes.env', 'build-in-checkout', 'SHA256SUMS'):
                self.assertFalse((recipe/name).exists(), name)
        # A recipe snapshots itself from its own inventory.
        listed = json.loads((self.home/'recipe/RECIPE-FILES.json').read_text())
        with patch('native_rebuild.ROOT', self.home/'recipe'):
            native_rebuild.snapshot(self.home/'again')
        self.assertEqual(json.loads((self.home/'again/recipe/RECIPE-FILES.json').read_text()), listed)

    def test_new_build_with_missing_libraries_is_never_staged(self):
        self.current.parent.mkdir(parents=True)
        self.current.with_name('doroshell-wallpaper-build.json').write_text('{"format": 3}')
        # Either the desktop or only its video worker may lack a library.
        for results in ([['libfm-qt6.so.19'], []], [[], ['libQt6Multimedia.so.7']]):
            answers = iter(results)
            with patch('subprocess.run'), patch('native_rebuild.stage') as stage, \
                 patch('native_rebuild.missing_libraries', side_effect=lambda path: next(answers)), \
                 open(os.devnull, 'w') as log:
                with self.assertRaisesRegex(RuntimeError, 'missing libraries'):
                    native_rebuild.build_and_stage('desktop', '2.5.0', self.home/'new', self.current, self.home, log)
                stage.assert_not_called()

    def test_staging_skips_after_rollback_or_newer_selection(self):
        script, work = self.staged_desktop_launcher(True)
        current = work/'build/pcmanfm/pcmanfm-qt'
        self.assertTrue(native_rebuild.still_selected('desktop', current, self.home))
        self.assertFalse(native_rebuild.still_selected('desktop', self.home/'other/pcmanfm-qt', self.home))
        with patch('modules.run') as run:  # Owner chose another build while this one compiled.
            self.assertFalse(native_rebuild.stage('desktop', self.home/'new/pcmanfm-qt', self.home/'other/pcmanfm-qt', self.home))
            run.assert_not_called()
        modules.run(self.home, 'wallpaper', rollback=True)  # Owner rolled back while it compiled.
        self.assertFalse(native_rebuild.still_selected('desktop', current, self.home))
        with patch('modules.run') as run:
            self.assertFalse(native_rebuild.stage('desktop', self.home/'new/pcmanfm-qt', current, self.home))
            run.assert_not_called()
        self.assertFalse(native_rebuild.still_selected('panel', self.home/'p/runtime/bin/lxqt-panel', self.home))
        with patch('panel.profile.upgrade') as upgrade:
            self.assertFalse(native_rebuild.stage('panel', self.home/'n', self.home/'p/runtime/bin/lxqt-panel', self.home))
            upgrade.assert_not_called()

    def test_not_staged_build_is_reported(self):
        with patch('native_rebuild.system_version', return_value='2.5.0'), \
             patch('native_rebuild.build_and_stage', return_value=(None, False)):
            self.assertEqual(self.rebuild(), 0)
        self.assertEqual(self.status()['result'], 'built-not-staged')
        self.assertIn('left as you set it', self.notify.call_args.args[1])

    def test_build_record_marks_unreviewed_tags(self):
        from wallpaper.build import write_build_record, REVISIONS
        binary = self.home/'pcmanfm-qt'; binary.write_bytes(b'b')
        binary.with_name('doroshell-video-worker').write_bytes(b'w')
        write_build_record(binary, tag='2.5.0', revision=REVISIONS['2.5.0'])
        self.assertTrue(json.loads(binary.with_name('doroshell-wallpaper-build.json').read_text())['reviewed'])
        write_build_record(binary, tag='2.6.0', revision='0'*40)
        record = json.loads(binary.with_name('doroshell-wallpaper-build.json').read_text())
        self.assertEqual((record['tag'], record['reviewed']), ('2.6.0', False))

    def staged_desktop_launcher(self, with_recipe):
        work = self.home/'build-dir'
        binary = work/'build/pcmanfm/pcmanfm-qt'; binary.parent.mkdir(parents=True)
        binary.write_bytes(b'fake native build'); binary.chmod(0o755)
        helper = binary.with_name('doroshell-video-worker'); helper.write_bytes(b'w'); helper.chmod(0o755)
        binary.with_name('doroshell-wallpaper-build.json').write_text(json.dumps(dict(
            format=2, sha256=hashlib.sha256(b'fake native build').hexdigest(), helper_sha256=hashlib.sha256(b'w').hexdigest())))
        if with_recipe:
            (work/'recipe').mkdir(); (work/'recipe/native_rebuild.py').write_text('')
        modules.run(self.home, 'wallpaper', apply=True, wallpaper_binary=binary)
        return (self.home/'.local/bin/doroshell-wallpaper-desktop').read_text(), work

    def test_desktop_launcher_falls_back_when_login_check_fails(self):
        script, work = self.staged_desktop_launcher(True)
        self.assertIn(str(work/'recipe/native_rebuild.py'), script)
        for check, expected in ((0, 0), (1, 1)):
            calls = []
            def run(args, **kwargs):
                calls.append(args)
                return subprocess.CompletedProcess(args, check if 'login' in args else 0)
            with patch('subprocess.run', side_effect=run), patch('os.execv') as stock:
                exec(compile(script, 'launcher', 'exec'), {})
            self.assertEqual(stock.call_count, expected)
            self.assertEqual(any(str(work/'build/pcmanfm/pcmanfm-qt') == c[0] for c in calls), not expected)

    def test_desktop_launcher_without_recipe_is_unchanged(self):
        script, _ = self.staged_desktop_launcher(False)
        self.assertNotIn('native_rebuild', script)

    def test_panel_launcher_uses_stock_panel_on_failed_check(self):
        binary = self.home/'p/runtime/bin/lxqt-panel'
        self.assertNotIn('native_rebuild', panel_launcher(binary, self.home/'panel.conf'))
        (self.home/'p/recipe').mkdir(parents=True); (self.home/'p/recipe/native_rebuild.py').write_text('')
        script = panel_launcher(binary, self.home/'panel.conf')
        for check, target in ((0, str(binary)), (1, '/usr/bin/lxqt-panel')):
            with patch('subprocess.run', return_value=subprocess.CompletedProcess([], check)), \
                 patch('os.access', return_value=True), patch('os.open', return_value=99), \
                 patch('os.dup2'), patch('os.close'), patch('os.execv', side_effect=SystemExit) as execv:
                with self.assertRaises(SystemExit):
                    exec(compile(script, 'panel-launcher', 'exec'), {})
            self.assertEqual(execv.call_args.args[0], target)
            if check:
                self.assertEqual(execv.call_args.args[1], ['/usr/bin/lxqt-panel'])


if __name__ == '__main__':
    unittest.main()
