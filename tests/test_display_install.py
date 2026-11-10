"""Temporary-home installation of a three-file display/wallpaper build."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import modules
from wallpaper.build import write_build_record


class DisplayInstallTests(unittest.TestCase):
    def fixture(self,root):
        binary=root/'build/pcmanfm-qt';binary.parent.mkdir()
        binary.write_bytes(b'desktop fixture');binary.chmod(0o755)
        binary.with_name('doroshell-video-worker').write_bytes(b'isolated decoder fixture')
        binary.with_name('doroshell-video-worker').chmod(0o755)
        helper=binary.with_name('doroshell-display-backend.py');helper.write_bytes(b'display fixture')
        write_build_record(binary,display_controls=True)
        return binary,helper

    def test_requires_display_helper_and_keeps_legacy_pair_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary,helper=self.fixture(Path(tmp));helper.unlink()
            with self.assertRaisesRegex(RuntimeError,'display helper'):write_build_record(binary,True)
            write_build_record(binary)
            self.assertEqual(json.loads(binary.with_name('doroshell-wallpaper-build.json').read_text())['format'],2)

    def test_stage_repeat_upgrade_and_exact_rollback_preserves_original_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);binary,helper=self.fixture(home)
            baseline=home/'.config/autostart/lxqt-desktop.desktop';baseline.parent.mkdir(parents=True)
            original=b'[Desktop Entry]\nName=Existing renderer\nExec=/unchanged/isolated-renderer --desktop\nX-Personal=keep\n'
            baseline.write_bytes(original);baseline.chmod(0o640)
            wallpaper=home/'.config/doroshell/wallpaper.json';wallpaper.parent.mkdir();wallpaper.write_bytes(b'{"enabled":false,"muted":true}')
            before={p:p.read_bytes() for p in binary.parent.iterdir()}
            for _ in range(2):modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
            manifest=(home/'.local/state/doroshell/wallpaper.json').read_bytes()
            # A newer helper/build record can be staged without replacing the first baseline.
            helper.write_bytes(b'new display fixture');write_build_record(binary,True)
            modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
            new=json.loads((home/'.local/state/doroshell/wallpaper.json').read_text())
            self.assertEqual(new['backup'],json.loads(manifest)['backup'])
            modules.run(home,'wallpaper',rollback=True)
            self.assertEqual(baseline.read_bytes(),original)
            self.assertEqual(baseline.stat().st_mode & 0o777,0o640)
            self.assertEqual(wallpaper.read_bytes(),b'{"enabled":false,"muted":true}')
            self.assertEqual(binary.read_bytes(),before[binary])
            self.assertEqual(binary.with_name('doroshell-video-worker').read_bytes(),before[binary.with_name('doroshell-video-worker')])
            self.assertFalse((home/'.local/bin/doroshell-wallpaper-desktop').exists())

    def test_tampered_missing_helper_refuses_staging_and_startup_falls_back(self):
        for kind in ('changed','missing'):
            with tempfile.TemporaryDirectory() as tmp:
                home=Path(tmp);binary,helper=self.fixture(home)
                modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
                launcher=(home/'.local/bin/doroshell-wallpaper-desktop').read_text()
                metadata=json.loads(binary.with_name('doroshell-wallpaper-build.json').read_text())
                self.assertEqual(metadata['format'],3)
                self.assertEqual(metadata['display_helper_sha256'],hashlib.sha256(helper.read_bytes()).hexdigest())
                with patch('subprocess.run',return_value=subprocess.CompletedProcess([],0)) as run,patch('os.execv') as fallback:
                    exec(compile(launcher,'fixture','exec'),{})
                    run.assert_called_once();fallback.assert_not_called()
                if kind=='changed':helper.write_bytes(b'changed')
                else:helper.unlink()
                baseline=(home/'.config/autostart/lxqt-desktop.desktop').read_bytes()
                with self.assertRaisesRegex(ValueError,'Display helper'):modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
                self.assertEqual((home/'.config/autostart/lxqt-desktop.desktop').read_bytes(),baseline)
                with patch('subprocess.run') as run,patch('os.execv') as fallback:
                    exec(compile(launcher,'fixture','exec'),{})
                    run.assert_not_called();fallback.assert_called_once()
                modules.run(home,'wallpaper',rollback=True)

    def test_conflicting_launcher_rollback_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);binary,helper=self.fixture(home)
            modules.run(home,'wallpaper',apply=True,wallpaper_binary=binary)
            launcher=home/'.local/bin/doroshell-wallpaper-desktop';launcher.write_text('# personal edit\n')
            with self.assertRaisesRegex(RuntimeError,'Personal edit'):modules.run(home,'wallpaper',rollback=True)
            self.assertEqual(launcher.read_text(),'# personal edit\n')
