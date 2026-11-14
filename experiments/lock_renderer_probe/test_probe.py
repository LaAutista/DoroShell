# SPDX-License-Identifier: GPL-2.0-or-later
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import probe


class ProbeContract(unittest.TestCase):
    def test_personal_display_refused_before_connection(self):
        with patch.dict(os.environ, {'DISPLAY': ':0', 'DOROSHELL_TEST_DISPLAY': ':120'}):
            with self.assertRaises(ValueError):
                probe.fixture_home()

    def test_media_bounds_and_type(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            media = home/'fixture.gif'
            media.write_bytes(b'GIF89a123')
            self.assertEqual(probe.validate_media(str(media), home), media)
            for payload in (b'', b'#EXTM3U', b'GIF89a'+b'x'*1024*1024):
                media.write_bytes(payload)
                with self.assertRaises(ValueError):
                    probe.validate_media(str(media), home)
            media.unlink()
            media.mkdir()
            with self.assertRaises(ValueError):
                probe.validate_media(str(media), home)

    def test_refresh_override_is_fixture_specific_and_reproducible(self):
        default = probe.command('/usr/bin/mpv', 42, '/fixture/a.gif')
        baseline = probe.command('/usr/bin/mpv', 42, '/fixture/a.gif', comparison='baseline')
        self.assertEqual([x for x in default if x not in baseline], ['--display-fps-override=60'])
        self.assertEqual(default[-2:], baseline[-2:])

    def test_no_shell_and_control_options(self):
        media = '/fixture/$(touch sentinel); name.gif'
        argv = probe.command('/usr/bin/mpv', 42, media)
        self.assertEqual(argv[-2:], ['--', media])
        for option in ('--wid=42', '--vo=x11', '--load-scripts=no',
                       '--no-config', '--stop-screensaver=no', '--no-audio',
                       '--input-vo-keyboard=no', '--input-builtin-bindings=no'):
            self.assertIn(option, argv)


if __name__ == '__main__':
    unittest.main()
