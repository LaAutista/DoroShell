"""Diagnostic-only phases: mocked commands and pipes, never a real display."""
import copy
import io
import json
import os
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_display import randr
from display import backend as b

class DiagnosticTests(unittest.TestCase):
    def state(self, text):
        result=b.parse(text);result.update(vsync=1,vsync_reason='');return result

    def test_metadata_cannot_change_tokens_or_acceptance(self):
        current=self.state(randr());calls=[]
        original=copy.deepcopy(current);original_token=b.token(current)
        current.diagnostic_fields={'0:Colorspace':'synthetic metadata only'}
        self.assertEqual(current,original);self.assertEqual(b.token(current),original_token)
        self.assertEqual(json.dumps(current,sort_keys=True),json.dumps(original,sort_keys=True))
        def query(): return copy.deepcopy(current)
        def execute(args):
            calls.append(args);current['outputs'][0]['current']=args[-1]
            current.diagnostic_fields={'0:BorderDimensions':'different metadata'}
        t=b.Transaction(dict(token=b.token(current),output='DP-0',mode='0x12'),query,execute)
        t.apply();t.verify();t.revert()
        self.assertEqual(current,original);self.assertEqual(len(calls),2)

    def test_fixed_property_labels_and_unchanged_refusal(self):
        for field in b.PROPERTY_FIELDS:
            with self.subTest(field=field):
                before=randr().replace('\tTimestamp:',f'\t{field}: 0\n\tTimestamp:')
                current=self.state(before);calls=[]
                def query():return copy.deepcopy(current)
                def execute(args):
                    nonlocal current
                    calls.append(args);current=self.state(before.replace('(0x11) normal','(0x12) normal').replace(f'{field}: 0',f'{field}: 1'))
                t=b.Transaction(dict(token=b.token(current),output='DP-0',mode='0x12'),query,execute)
                with self.assertRaises(b.DisplayError) as error:t.apply()
                self.assertIn(field,error.exception.diagnostics[0]['fields'])
                self.assertEqual(error.exception.diagnostics[0]['phase'],'apply_verification')
                with self.assertRaises(b.DisplayError):t.revert()
                self.assertEqual(len(calls),1)

    def test_apply_and_recovery_events_remain_separate(self):
        current=self.state(randr()+'\tColorspace: Default\n');calls=[]
        def query():return copy.deepcopy(current)
        def execute(args):
            nonlocal current
            calls.append(args);current=self.state(randr('0x12')+'\tColorspace: Changed\n')
        t=b.Transaction(dict(token=b.token(current),output='DP-0',mode='0x12'),query,execute)
        with self.assertRaises(b.DisplayError) as error:b.guard(t)
        events=error.exception.diagnostics
        self.assertEqual([(e['phase'],e['reason']) for e in events],[('apply_verification','state_mismatch'),('recovery','external_change')])
        self.assertTrue(all('Colorspace' in e['fields'] for e in events))
        self.assertNotIn('Changed',json.dumps(events));self.assertEqual(len(calls),1)

    def test_keep_periodic_and_deadline_recovery_phases(self):
        for action in ('keep','periodic','deadline'):
            with self.subTest(action=action):
                calls=[]
                class Transaction:
                    def apply(self):calls.append('apply')
                    def verify(self):
                        calls.append('verify')
                        if action=='deadline':raise b.DeadlineExpired('raw',reason='deadline')
                        raise b.DisplayError('raw PRIVATE',reason='state_mismatch')
                    def revert(self):calls.append('revert');raise b.DisplayError('raw RECOVERY',reason='command_failed')
                read,write=os.pipe()
                try:
                    if action=='keep':os.write(write,b'keep\n')
                    with os.fdopen(read,'rb') as stream,patch.object(b,'emit'):
                        with self.assertRaises(b.DisplayError) as error:b.guard(Transaction(),stream,timeout=1)
                    events=error.exception.diagnostics
                    expected='keep_verification' if action=='keep' else 'periodic_verification'
                    self.assertEqual([e['phase'] for e in events],[expected,'recovery'])
                    self.assertEqual(events[-1]['reason'],'command_failed')
                    if action=='deadline':self.assertEqual(events[0]['reason'],'deadline')
                    self.assertEqual(calls,['apply','verify','revert']);self.assertNotIn('PRIVATE',json.dumps(events))
                finally:os.close(write)

    def test_command_reasons(self):
        cases=[(subprocess.TimeoutExpired(['fake'],1),'command_timeout'),(OSError('PRIVATE'),'command_unavailable'),
               (SimpleNamespace(returncode=1,stderr='PRIVATE raw output',stdout=''),'command_failed')]
        for response,reason in cases:
            with self.subTest(reason=reason):
                options={'side_effect':response} if isinstance(response,Exception) else {'return_value':response}
                with patch.object(b.subprocess,'run',**options):
                    with self.assertRaises(b.DisplayError) as error:
                        with b.diagnostic_phase('apply'):b.run(['fake'])
                self.assertEqual(error.exception.diagnostics,[dict(phase='apply',reason=reason,fields=[])])

    def test_recovery_command_failure_not_lost(self):
        current=self.state(randr());calls=[]
        def query():return copy.deepcopy(current)
        def execute(args):
            calls.append(args)
            if len(calls)==2:raise b.DisplayError('SECRET',reason='command_timeout')
            current['outputs'][0]['current']=args[-1]
        t=b.Transaction(dict(token=b.token(current),output='DP-0',mode='0x12'),query,execute);t.apply()
        with self.assertRaises(b.DisplayError) as error:t.revert()
        self.assertEqual(error.exception.diagnostics[0]['reason'],'command_timeout')
        self.assertEqual(error.exception.diagnostics[0]['phase'],'recovery');self.assertEqual(len(calls),2)

    def test_sanitizer_bounds_and_unknown_values(self):
        changes=[dict(field='PRIVATE')] + [dict(field=k,output='SECRET') for k in sorted(b.FIELDS)]*100
        event=b.diagnostic('PRIVATE','SECRET',changes)
        self.assertEqual(event['phase'],'preflight');self.assertEqual(event['reason'],'operation_failed')
        self.assertEqual(len(event['fields']),6);self.assertNotIn('PRIVATE',json.dumps(event));self.assertNotIn('SECRET',json.dumps(event))
        error=b.DisplayError('raw',diagnostics=[event]*100);self.assertEqual(len(error.diagnostics),3)
