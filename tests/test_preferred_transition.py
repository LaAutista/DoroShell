"""Synthetic topology based on read-only dimensions/rates, excluding EDID/private data."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from display import backend as b


def topology(current='0x1bf'):
    text = ('Screen 0: minimum 8 x 8, current 2560 x 1440, maximum 32767 x 32767\n'
            'HDMI-0 disconnected (normal left inverted right x axis y axis)\n'
            f'DP-0 connected primary 2560x1440+0+0 ({current}) normal (normal left inverted right x axis y axis) 590mm x 330mm\n'
            '\tTimestamp: 123\n\tGamma: 1.0:1.0:1.0\n\tBrightness: 1.0\n\tCRTC: 0\n'
            '\tTransform: 1.000000 0.000000 0.000000\n\t           0.000000 1.000000 0.000000\n\t           0.000000 0.000000 1.000000\n'
            '\t_KDE_SCREEN_INDEX: 1\n\tBorder: 0 0 0 0\n')
    for ident,clock,hz,vertical in [('0x1be','241.500','59.95',1481),('0x1bf','2414.000','479.99',1849)]:
        text += f'  2560x1440 ({ident}) {clock}MHz +HSync -VSync'+(' *current' if ident==current else '')+(' +preferred' if ident=='0x1be' else '')+'\n'
        text += f'        h: width 2560 start 2608 end 2640 total 2720 skew 0 clock 88.79KHz\n        v: height 1440 start 1443 end 1448 total {vertical} clock {hz}Hz\n'
    for name in ('DP-1','DP-2','DP-3','DP-4','DP-5','HDMI-A-1-0','DisplayPort-1-0','DisplayPort-1-1','DisplayPort-1-2'):
        text+=name+' disconnected (normal left inverted right x axis y axis)\n'
    return text

class PreferredTransitionTests(unittest.TestCase):
    def state(self,text):return dict(b.parse(text),vsync=1,vsync_reason='')
    def test_marker_changes_only_current_mode(self):
        before=self.state(topology());after=self.state(topology('0x1be'))
        expected=copy.deepcopy(before);expected['outputs'][1]['current']='0x1be'
        self.assertEqual(after,expected)
        self.assertEqual(after['outputs'][1]['modes'][0]['flags'],'+HSync -VSync +preferred')

    def test_preferred_roundtrip(self):
        for original,target in [('0x1bf','0x1be'),('0x1be','0x1bf')]:
            with self.subTest(original=original):
                current=original;calls=[]
                def query():return self.state(topology(current))
                def execute(args):
                    nonlocal current
                    calls.append(args);current=args[-1]
                transaction=b.Transaction(dict(token=b.token(query()),output='DP-0',mode=target),query,execute)
                transaction.apply();transaction.verify();transaction.revert()
                self.assertEqual(current,original)
                self.assertEqual(calls,[['xrandr','--output','DP-0','--mode',target],['xrandr','--output','DP-0','--mode',original]])

    def test_external_layout_properties_still_refuse(self):
        for old,new in [('Brightness: 1.0','Brightness: 0.8'),('Gamma: 1.0:1.0:1.0','Gamma: 0.9:1.0:1.0'),
                        ('2560x1440+0+0','2560x1440+100+0'),('Transform: 1.000000','Transform: 1.100000'),
                        ('_KDE_SCREEN_INDEX: 1','_KDE_SCREEN_INDEX: 2'),('Border: 0 0 0 0','Border: 1 0 0 0')]:
            with self.subTest(property=old):
                current='0x1bf';changed=False;calls=[]
                def query():return self.state(topology(current).replace(old,new) if changed else topology(current))
                def execute(args):
                    nonlocal current
                    calls.append(args);current=args[-1]
                t=b.Transaction(dict(token=b.token(query()),output='DP-0',mode='0x1be'),query,execute);t.apply();changed=True
                with self.assertRaises(b.DisplayError):t.verify()
                with self.assertRaisesRegex(b.DisplayError,'layout changed'):t.revert()
                self.assertEqual(len(calls),1,'External changes must not be overwritten')

    def test_differences_redact_identifiers_and_classify(self):
        original = topology() + '\tEDID:\n\t\tPRIVATE-MONITOR-SERIAL\n'
        before = self.state(original)
        for old, new, label in [
            ('Brightness: 1.0', 'Brightness: 0.8', 'brightness'),
            ('Gamma: 1.0:1.0:1.0', 'Gamma: 0.9:1.0:1.0', 'gamma'),
            ('2560x1440+0+0', '2560x1440+100+0', 'connection/geometry/rotation'),
            ('PRIVATE-MONITOR-SERIAL', 'ANOTHER-PRIVATE-SERIAL', 'other protected properties'),
        ]:
            with self.subTest(label=label):
                actual = self.state(original.replace(old, new))
                detail = b.differences(before, actual)
                self.assertIn(label, [d['field'] for d in detail])
                self.assertNotIn('PRIVATE', str(detail))
                self.assertNotIn('DP-0', str(detail))
                self.assertLessEqual(len(detail), 32)
        actual = copy.deepcopy(before)
        actual['outputs'][1]['connection'] = 'disconnected'
        self.assertIn('connection status changed', [d['field'] for d in b.differences(before, actual)])
        actual['outputs'].pop(1)
        self.assertIn('output disappeared', [d['field'] for d in b.differences(before, actual)])

    def test_guard_preserves_verification_and_recovery_evidence(self):
        current = '0x1bf'
        calls = []
        def query():
            text = topology(current)
            if current == '0x1be':
                text = text.replace('Brightness: 1.0', 'Brightness: 0.8')
            return self.state(text)
        def execute(args):
            nonlocal current
            calls.append(args)
            current = args[-1]
        t = b.Transaction(dict(token=b.token(query()), output='DP-0', mode='0x1be'), query, execute)
        with self.assertRaises(b.DisplayError) as raised:
            b.guard(t)
        self.assertIn('Driver did not apply', str(raised.exception))
        self.assertIn('recovery failed', str(raised.exception))
        self.assertIn('brightness', str(raised.exception))
        self.assertTrue(raised.exception.differences)
        self.assertEqual(current, '0x1be')
        self.assertEqual(len(calls), 1, 'external changes must never trigger forced restore/retry')
        self.assertEqual(b.public(query())['outputs'][0]['current'], '0x1be')
        self.assertEqual(len(calls), 1, 'read-only refresh cannot write')
