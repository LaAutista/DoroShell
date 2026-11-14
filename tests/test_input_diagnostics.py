"""Bounded configuration fixtures never establish effective acceleration or log provenance."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import input_diagnostics as diagnostics
from test_input_preferences import device, Backend


def rule(scheme='none', matches='MatchProduct "Synthetic mouse"\nMatchIsPointer "on"\nMatchDevicePath "/dev/input/event*"'):
    return 'Section "InputClass"\nIdentifier "fixture"\n'+matches+'\nOption "AccelerationScheme" "'+scheme+'"\nEndSection\n'


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.config=self.root/'xorg.conf'
        self.directory=self.root/'xorg.conf.d'; self.directory.mkdir()
        self.mouse=device()

    def read(self):
        return diagnostics.read_configuration(self.config,(self.directory,))

    def text(self, content, available=False):
        return diagnostics.describe(self.mouse,diagnostics.parse_configuration(content),available)

    def test_none_intent_and_missing_profile_never_mean_effective_disabled(self):
        text=self.text(rule())
        self.assertIn('control: unavailable',text); self.assertIn('requests none (intent only)',text)
        self.assertIn('initialization: unverified',text)
        self.assertIn('missing profile do not prove acceleration is disabled',text)
        self.assertIn('cannot change the system scheme',text)
        self.assertIn('control: available',self.text(rule(),True))

    def test_absent_configuration_is_unknown_not_disabled(self):
        text=diagnostics.describe(self.mouse,self.read())
        self.assertIn('no matching scheme request established',text)
        self.assertIn('initialization: unverified',text)

    def test_product_path_boolean_and_negative_matches(self):
        for matches, expected in [
            ('MatchProduct "No match|Synthetic"',True),
            ('MatchProduct "Synthetic"\nMatchProduct "mouse"',True),
            ('MatchProduct "synthetic"',False),
            ('MatchDevicePath "/dev/input/event[0-9]"',True),
            ('MatchDevicePath "/dev/input/mouse*"',False),
            ('MatchIsPointer "off"',False),('MatchIsTouchpad "off"',True),
            ('NoMatchProduct "touchpad"',True),('NoMatchDevicePath "/dev/input/event*"',False),
        ]:
            with self.subTest(matches=matches):
                self.assertEqual('requests none (intent only)' in self.text(rule(matches=matches)),expected)

    def test_conflicting_requests_are_not_resolved_by_guessed_precedence(self):
        self.config.write_text(rule('none'))
        (self.directory/'99-fixture.conf').write_text(rule('predictable'))
        text=diagnostics.describe(self.mouse,self.read())
        self.assertIn('conflicting matching scheme requests',text)
        self.assertNotIn('requests none (intent only)',text)

    def test_unknown_selectors_or_inputdevice_do_not_establish_a_match(self):
        for content in (rule(matches='MatchTag "private-tag"'), rule().replace('InputClass','InputDevice')):
            with self.subTest(content=content):
                text=self.text(content)
                self.assertNotIn('requests none (intent only)',text); self.assertIn('unsupported',text)
        self.assertNotIn('unsupported',self.text(rule(matches='MatchProduct "Other device"\nMatchTag "unknown"')))

    def test_malformed_and_truncated_files_are_not_positive_evidence(self):
        for content in (rule().replace('EndSection',''),rule().replace('Identifier "fixture"\n',''),
                        rule().replace('"none"','"none'),rule().replace('"none"','"none" "extra"'),rule('typo'),
                        rule().replace('EndSection','Option\nEndSection'),rule().replace('Identifier "fixture"','Identifier "fixture" "extra"')):
            with self.subTest(content=content):
                text=self.text(content)
                self.assertIn('malformed',text); self.assertNotIn('requests none (intent only)',text)

    def test_unreadable_or_changed_evidence_keeps_status_incomplete(self):
        self.config.write_text(rule())
        with patch.object(diagnostics.os,'open',side_effect=PermissionError):
            text=diagnostics.describe(self.mouse,self.read())
        self.assertIn('incomplete: unreadable',text)
        with patch.object(diagnostics.os,'read',return_value=b''):
            text=diagnostics.describe(self.mouse,self.read())
        self.assertIn('incomplete: changed',text); self.assertNotIn('requests none (intent only)',text)

    def test_file_count_and_byte_limits_are_enforced(self):
        self.config.write_bytes(b'#'*(diagnostics.MAX_FILE+1))
        self.assertIn('bounded',self.read()[1])
        self.config.unlink()
        for n in range(3): (self.directory/f'{n}.conf').write_text(rule())
        with patch.object(diagnostics,'MAX_FILES',2):
            rules,issues=self.read(); self.assertEqual(len(rules),2); self.assertIn('bounded',issues)
        with patch.object(diagnostics,'MAX_TOTAL',len(rule().encode())):
            rules,issues=self.read(); self.assertEqual(len(rules),1); self.assertIn('bounded',issues)

    def test_symlinks_and_nonregular_files_are_not_followed(self):
        target=self.root/'fixture'; target.write_text(rule()); self.config.symlink_to(target)
        self.assertIn('unreadable',self.read()[1]); self.assertEqual(self.read()[0],[])
        self.config.unlink(); os.mkfifo(self.config)
        self.assertIn('unreadable',self.read()[1]); self.assertEqual(self.read()[0],[])

    def test_stale_or_matching_logs_are_not_read_or_promoted(self):
        self.config.write_text(rule()); os.utime(self.config,(1,1))
        # A convincing name-only log cannot bind this snapshot to a current device instance.
        log=self.directory/'Xorg.0.log'
        log.write_text('Synthetic mouse: (accel) selected scheme none/0\n')
        os.utime(log,(1,1)); original=diagnostics.os.open
        def opened(path,*args,**kwargs):
            self.assertNotEqual(Path(path),log)
            return original(path,*args,**kwargs)
        with patch.object(diagnostics.os,'open',side_effect=opened):
            text=diagnostics.describe(self.mouse,self.read())
        self.assertIn('requests none (intent only)',text); self.assertIn('initialization: unverified',text)
        self.assertNotIn('fixture',text); self.assertNotIn('Synthetic',text)

    def test_refresh_does_not_write_preferences_devices_or_session_marker(self):
        import input_preferences as ip
        from PySide6.QtWidgets import QApplication,QPushButton,QLabel
        app=QApplication.instance() or QApplication([]); backend=Backend([self.mouse])
        with patch.object(ip,'XInput',return_value=backend),patch.object(backend,'token',side_effect=AssertionError('session write')),patch.object(diagnostics,'read_configuration',return_value=diagnostics.parse_configuration(rule())):
            widget=ip.page(self.root)
            next(b for b in widget.findChildren(QPushButton) if b.text()=='Refresh devices').click()
            label=next(l for l in widget.findChildren(QLabel) if l.accessibleName()=='Read-only input capability evidence')
            self.assertIn('requests none (intent only)',label.text())
            self.assertFalse(backend.writes); self.assertFalse(ip.Preferences(self.root).path.exists())
            widget.close()
