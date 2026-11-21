"""A fresh LXQt/Openbox login runs from system defaults; the installer must see that layout."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import compatibility
import deploy
import install

SYSTEM_PANEL = ('[General]\n__userfile__=false\n\n[panel1]\nplugins=fancymenu, quicklaunch, taskbar, worldclock\nposition=Bottom\n\n'
                '[fancymenu]\ntype=fancymenu\n\n[taskbar]\ntype=taskbar\n\n[worldclock]\ntype=worldclock\n')
# What the reported profile held: one Fancy Menu favorite and per-plugin alignment, no [panel1].
USER_PANEL = ('[General]\n__userfile__=true\n\n[fancymenu]\nfavorites\\1\\desktopFile=/usr/share/applications/firefox.desktop\n'
              'favorites\\size=1\n\n[worldclock]\nalignment=Right\n')
SYSTEM_OPENBOX = b'<?xml version="1.0"?>\n<openbox_config><desktops><number>4</number></desktops><keyboard></keyboard></openbox_config>\n'


class EffectiveDefaultsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)/'home'; self.system = Path(temporary.name)/'xdg'
        (self.system/'lxqt').mkdir(parents=True); (self.system/'openbox').mkdir()
        (self.system/'lxqt/panel.conf').write_text(SYSTEM_PANEL); (self.system/'openbox/rc.xml').write_bytes(SYSTEM_OPENBOX)
        self.panel = self.home/compatibility.PANEL; self.panel.parent.mkdir(parents=True)
        self.panel.write_text(USER_PANEL); self.panel.chmod(0o640)
        self.openbox = self.home/compatibility.OPENBOX
        self.env = dict(XDG_CURRENT_DESKTOP='LXQt', XDG_SESSION_TYPE='x11', XDG_CONFIG_DIRS=str(self.system))
        self.enterContext(patch.object(compatibility.shutil, 'which', return_value='/usr/bin/pacman'))

    def inspect(self, modules=('native-panel', 'snapping')):
        return compatibility.inspect(self.home, list(modules), self.env, dict(ID='cachyos', ID_LIKE='arch'))

    def test_override_only_profile_resolves_both_effective_configs_without_writing(self):
        report = self.inspect()
        self.assertEqual(report['issues'], [])
        self.assertEqual(report['effective_defaults'], [compatibility.PANEL, compatibility.OPENBOX])
        self.assertEqual(self.panel.read_text(), USER_PANEL); self.assertFalse(self.openbox.exists())
        merged = compatibility.effective_defaults(self.home, ['native-panel', 'snapping'], self.env)
        panel = merged[compatibility.PANEL].decode()
        self.assertTrue(compatibility.single_panel1(panel))
        self.assertIn('plugins=fancymenu, quicklaunch, taskbar, worldclock', panel)
        self.assertIn('favorites\\1\\desktopFile=/usr/share/applications/firefox.desktop', panel)   # the favorite survives
        self.assertIn('__userfile__=true', panel); self.assertNotIn('__userfile__=false', panel)     # user keys win
        self.assertIn('[worldclock]\ntype=worldclock\nalignment=Right\n', panel)
        self.assertEqual(merged[compatibility.OPENBOX], SYSTEM_OPENBOX)

    def test_ambiguous_or_absent_layouts_still_stop_and_name_the_missing_file(self):
        (self.system/'lxqt/panel.conf').write_text(SYSTEM_PANEL+'\n[panel2]\nplugins=tray\n')   # two system panels
        self.assertIn('defines no panel', self.inspect(['native-panel'])['issues'][0])
        (self.system/'lxqt/panel.conf').write_text(SYSTEM_PANEL)
        self.panel.write_text('[General]\npanels=panel1, panel2\n[panel1]\n[panel2]\n')            # the user's own two panels
        report = self.inspect(['native-panel'])
        self.assertIn('single panel1 layout', report['issues'][0]); self.assertEqual(report['effective_defaults'], [])
        (self.system/'openbox/rc.xml').unlink(); (self.system/'lxqt/panel.conf').unlink(); self.panel.write_text(USER_PANEL)
        issues = self.inspect()['issues']
        self.assertEqual(len(issues), 2)
        self.assertIn('~/.config/lxqt/panel.conf', issues[0]); self.assertIn(str(self.system/'lxqt/panel.conf'), issues[0])
        self.assertIn('~/.config/openbox/rc.xml', issues[1]); self.assertIn('install -Dm644', issues[1])

    def test_existing_user_files_are_never_replaced(self):
        self.panel.write_text('[General]\n[panel1]\nplugins=mine\n'); self.openbox.parent.mkdir(parents=True); self.openbox.write_bytes(b'<mine/>')
        self.assertEqual(compatibility.effective_defaults(self.home, ['native-panel', 'snapping', 'theme'], self.env), {})

    def test_apply_writes_the_effective_panel_and_undo_restores_the_original(self):
        menu = self.home/'synthetic-menu'
        output = io.StringIO(); self.enterContext(contextlib.redirect_stdout(output))
        self.enterContext(patch.dict(os.environ, self.env, clear=True))
        self.enterContext(patch.object(compatibility, 'os_release', return_value={'ID': 'arch'}))
        self.enterContext(patch.object(compatibility, 'package_versions', return_value={'python': 'fixture'}))
        self.enterContext(patch.object(deploy, 'build_native', return_value={'native-panel': Path('/usr/bin/true')}))
        self.enterContext(patch.object(deploy, 'run')); self.enterContext(patch('source_release.check'))
        self.enterContext(patch.object(deploy.os, 'geteuid', return_value=1000))
        self.enterContext(patch.object(install, 'targets', return_value={menu: (b'installed menu', 0o644)}))
        cli = lambda *args: deploy.main(['--home', str(self.home), '--modules', 'native-panel', 'maintenance', *args])
        self.assertEqual(cli(), 0)
        self.assertNotIn('Plan blocked', output.getvalue()); self.assertIn('Would write the effective system default', output.getvalue())
        self.assertEqual(self.panel.read_text(), USER_PANEL)                                       # a plan writes nothing
        self.assertIn('Status: plan only', output.getvalue())
        (self.system/'lxqt/panel.conf').rename(self.system/'lxqt/aside'); cli()
        self.assertIn('Status: blocked. Nothing was installed', output.getvalue()); self.assertIn('  - Native taskbar: ~/.config/lxqt/panel.conf', output.getvalue())
        with self.assertRaisesRegex(ValueError, 'Status: blocked'): cli('--apply')
        (self.system/'lxqt/aside').rename(self.system/'lxqt/panel.conf')
        self.assertEqual(cli('--apply'), 0)
        self.assertIn('Status: deployed, waiting for your next normal login', output.getvalue())
        written = self.panel.read_text()
        self.assertTrue(compatibility.single_panel1(written)); self.assertIn('favorites\\1\\desktopFile', written)
        self.assertEqual(self.panel.stat().st_mode & 0o777, 0o640)
        staged = (self.home/'.config/doroshell/panel.conf').read_text()
        self.assertIn('favorites', staged); self.assertIn('[panel1]', staged)
        pointer = json.loads((self.home/deploy.POINTER).read_text())
        self.assertEqual(cli('--apply'), 0)                                                        # repeat install: nothing left to write down
        self.assertEqual(self.panel.read_text(), written)
        latest = json.loads((self.home/deploy.POINTER).read_text())['transaction']
        cli('--apply', '--undo', latest); cli('--apply', '--undo', pointer['transaction'])
        self.assertEqual(self.panel.read_text(), USER_PANEL); self.assertEqual(self.panel.stat().st_mode & 0o777, 0o640)


if __name__ == '__main__':
    unittest.main()
