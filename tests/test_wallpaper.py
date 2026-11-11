import json
import hashlib
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from pathlib import Path
from wallpaper.control import validate, deployment_status
import modules


class WallpaperTests(unittest.TestCase):
    def test_volume_bounds(self):
        self.assertEqual(validate({})['volume'], 100)
        for value in (0, 25, 100):
            self.assertEqual(validate({'volume': value})['volume'], value)
        for value in (-1, 101, True, '25', 1.5):
            with self.assertRaises(ValueError):
                validate({'volume': value})

    def test_options_and_local_file_validation(self):
        self.assertFalse(validate({})['enabled'])
        self.assertTrue(validate({})['muted'])
        for values in ({'fit':'tile'},{'fps':0},{'enabled':True,'file':'https://example.com/a.mp4'},{'paused':'false'}):
            with self.assertRaises(ValueError): validate(values)

    def test_stage_repeat_conflict_and_restore(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);binary=home/'build/pcmanfm-qt';binary.parent.mkdir();binary.write_bytes(b'fake native build fixture');binary.chmod(0o755)
            binary.with_name('doroshell-wallpaper-build.json').write_text(json.dumps({'sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}))
            original=home/'.config/autostart/lxqt-desktop.desktop';original.parent.mkdir(parents=True)
            original.write_text('[Desktop Entry]\nExec=personal-desktop\n');before=original.read_bytes()
            for _ in range(2):modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
            launcher=(home/'.local/bin/doroshell-wallpaper-desktop').read_text()
            for code in (0,1):
                with patch('subprocess.run',return_value=subprocess.CompletedProcess([],code)), patch('os.execv') as fallback:
                    exec(compile(launcher,'test-launcher','exec'),{})
                    self.assertEqual(fallback.call_count,int(code!=0))
            installed=original.read_bytes();original.write_bytes(installed+b'# custom\n')
            with self.assertRaisesRegex(RuntimeError,'Personal edit'):modules.run(home,'wallpaper',rollback=True)
            original.write_bytes(installed);modules.run(home,'wallpaper',rollback=True)
            self.assertEqual(original.read_bytes(),before)
            self.assertFalse((home/'.local/bin/doroshell-wallpaper-desktop').exists())

    def test_status_distinguishes_uninstalled_staged_changed_and_stale_reports(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);runtime=home/'run';runtime.mkdir()
            self.assertIn('not installed',deployment_status(home,runtime))
            binary=home/'desktop';binary.write_bytes(b'fixture');binary.chmod(0o755)
            binary.with_name('doroshell-wallpaper-build.json').write_text(json.dumps({'sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}))
            modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
            self.assertIn('Staged for next desktop startup',deployment_status(home,runtime))
            (runtime/'doroshell-wallpaper-test.json').write_text(json.dumps({'pid':999999999,'display':'','binary':str(binary),'playing':True,'reasons':[],'error':''}))
            self.assertIn('Staged for next desktop startup',deployment_status(home,runtime))
            (home/'.local/bin/doroshell-wallpaper').write_text('edited')
            self.assertIn('installation changed',deployment_status(home,runtime))

    def test_existing_desktop_metadata_and_dolphin_hook_survive_repeat_restore(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);binary=home/'desktop';binary.write_bytes(b'fixture');binary.chmod(0o755)
            binary.with_name('doroshell-wallpaper-build.json').write_text(json.dumps({'sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}))
            autostart=home/'.config/autostart/lxqt-desktop.desktop';autostart.parent.mkdir(parents=True)
            before=b'[Desktop Entry]\nType=Application\nName=My desktop\nExec=sh -c "systemctl --user start plasma-dolphin.service; exec pcmanfm-qt --desktop --profile=lxqt"\nX-Personal=keep\n'
            autostart.write_bytes(before)
            for _ in range(2):
                modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
                self.assertIn('Name=My desktop',autostart.read_text())
                self.assertIn('X-Personal=keep',autostart.read_text())
                script=(home/'.local/bin/doroshell-wallpaper-desktop').read_text()
                self.assertIn("['systemctl', '--user', 'start', 'plasma-dolphin.service']",script)
                self.assertNotIn('sh -c',script)
            modules.run(home,'wallpaper',rollback=True)
            self.assertEqual(autostart.read_bytes(),before)

    def test_changed_binary_refused_without_writes(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);binary=home/'desktop';binary.write_bytes(b'changed');binary.chmod(0o755)
            binary.with_name('doroshell-wallpaper-build.json').write_text('{"sha256":"old"}')
            with self.assertRaises(ValueError):modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
            self.assertFalse((home/'.config').exists())

    def test_isolated_build_pair_validation_and_startup_fallback(self):
        from wallpaper.build import write_build_record
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);binary=home/'build/pcmanfm-qt';binary.parent.mkdir()
            helper=binary.with_name('doroshell-video-worker')
            binary.write_bytes(b'desktop');binary.chmod(0o755)
            with self.assertRaises(RuntimeError):write_build_record(binary)
            helper.write_bytes(b'decoder');helper.chmod(0o755);write_build_record(binary)
            proof=json.loads(binary.with_name('doroshell-wallpaper-build.json').read_text())
            self.assertEqual(proof['format'],2)
            modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
            launcher=(home/'.local/bin/doroshell-wallpaper-desktop').read_text()
            with patch('subprocess.run',return_value=subprocess.CompletedProcess([],0)) as run, patch('os.execv') as fallback:
                exec(compile(launcher,'test-launcher','exec'),{})
                run.assert_called_once();fallback.assert_not_called()
            for bad in ('changed','missing','not-executable'):
                helper.write_bytes(b'changed' if bad=='changed' else b'decoder');helper.chmod(0o755)
                if bad=='missing':helper.unlink()
                if bad=='not-executable':helper.chmod(0o644)
                with self.assertRaisesRegex(ValueError,'Decoder helper'):
                    modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
                with patch('subprocess.run') as run, patch('os.execv') as fallback:
                    exec(compile(launcher,'test-launcher','exec'),{})
                    run.assert_not_called();fallback.assert_called_once()
            modules.run(home,'wallpaper',rollback=True)
            self.assertFalse((home/'.config/autostart/lxqt-desktop.desktop').exists())
