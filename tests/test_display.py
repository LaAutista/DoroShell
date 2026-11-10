"""Display transactions with synthetic RandR/NV-CONTROL state; no live writes."""
import copy
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from display import backend as b


def randr(current='0x11', connected=True):
    header = f'DP-0 connected primary 1920x1080+0+0 ({current}) normal (normal left inverted right x axis y axis) 500mm x 300mm' if connected else 'DP-0 disconnected (normal left inverted right x axis y axis)'
    text = 'Screen 0: minimum 8 x 8, current 1920 x 1080, maximum 32767 x 32767\n'+header+'\n\tCRTC: 0\n\tTimestamp: 12\n'
    if connected:
        for ident, rate in [('0x11','60.00'),('0x12','144.00')]:
            text += f'  1920x1080 ({ident}) 148.500MHz +HSync +VSync'+(' *current' if ident == current else '')+'\n'
            text += f'        h: width 1920 start 2008 end 2052 total 2200 skew 0 clock 67.50KHz\n        v: height 1080 start 1084 end 1089 total 1125 clock {rate}Hz\n'
    return text


class Driver:
    def __init__(self, nv=1):
        self.state = dict(b.parse(randr()), vsync=nv, vsync_reason='' if nv is not None else 'unsupported')
        self.calls = []
        self.fail = None
    def query(self):
        return copy.deepcopy(self.state)
    def run(self, args):
        self.calls.append(args)
        if self.fail == len(self.calls):
            raise b.DisplayError('fake driver failure')
        if args[0] == 'xrandr':
            self.state['outputs'][0]['current'] = args[-1]
        else:
            self.state['vsync'] = int(args[-1].split('=')[-1])
        return ''
    def transaction(self, **changes):
        return b.Transaction(dict(token=b.token(self.state), output='DP-0', mode='0x12', **changes), self.query, self.run)


class DisplayTests(unittest.TestCase):
    def test_parser_modes_and_layout_stable(self):
        old, new = b.parse(randr()), b.parse(randr('0x12'))
        self.assertEqual(old['layout'], new['layout'])
        self.assertEqual(old['outputs'][0]['modes'], new['outputs'][0]['modes'])
        self.assertEqual(new['outputs'][0]['current'], '0x12')
        self.assertEqual(old['outputs'][0]['modes'][1]['hz'], '144.00')

    def test_invalid_parse(self):
        for text in ('', randr().replace('DP-0','--bad'), randr().replace('DP-0','XWAYLAND0'), randr().replace('height 1080','height invalid')):
            with self.assertRaises(b.DisplayError): b.parse(text)

    def test_validation_no_commands(self):
        d = Driver()
        for changes in ({'mode':'--auto'}, {'output':'DP-0; echo bad'}, {'token':'stale'}, {'vsync':2}, {'vsync':True}, {'vsync':'0'}, {'extra':1}):
            request = dict(token=b.token(d.state), output='DP-0', mode='0x12'); request.update(changes)
            with self.assertRaises(b.DisplayError): b.Transaction(request, d.query, d.run)
        self.assertEqual(d.calls, [])

    def test_apply_and_exact_revert(self):
        d=Driver(); original=d.query(); t=d.transaction(vsync=0)
        t.apply(); t.verify(); self.assertEqual(d.state['vsync'],0)
        t.revert(); self.assertEqual(d.state,original)
        self.assertEqual(d.calls[0],['xrandr','--output','DP-0','--mode','0x12'])
        self.assertEqual(d.calls[-1][-1],'0x11')

    def test_repeated_apply_no_extra_writes(self):
        d=Driver(); t=d.transaction(); t.apply()
        second=d.transaction(); second.apply()
        self.assertEqual(len(d.calls),1)
        second.revert(); self.assertEqual(len(d.calls),1)

    def test_concurrent_change_refused(self):
        d=Driver(); t=d.transaction(); d.state['layout']='changed'
        with self.assertRaises(b.DisplayError): t.apply()
        self.assertEqual(d.calls,[])

    def test_disconnect_does_not_force_reconnect(self):
        d=Driver(); t=d.transaction(vsync=0); t.apply()
        d.state.update(b.parse(randr(connected=False)))
        with self.assertRaises(b.DisplayError): t.verify()
        with self.assertRaisesRegex(b.DisplayError,'disconnected'): t.revert()
        self.assertEqual(d.state['vsync'],1)
        self.assertEqual(len([c for c in d.calls if c[0]=='xrandr']),1)

    def test_external_mode_or_layout_not_overwritten(self):
        for key in ('mode','layout'):
            d=Driver(); t=d.transaction(); t.apply()
            if key=='mode': d.state['outputs'][0]['current']='0x99'
            else: d.state['layout']='changed'
            with self.assertRaises(b.DisplayError): t.revert()
            self.assertEqual(len(d.calls),1)

    def test_unsupported_nv_refresh_works(self):
        d=Driver(None); t=d.transaction(); t.apply(); t.revert()
        self.assertTrue(all(c[0]=='xrandr' for c in d.calls))
        with self.assertRaises(b.DisplayError): d.transaction(vsync=0)

    def test_clone_outputs_disabled(self):
        d=Driver(); second=copy.deepcopy(d.state['outputs'][0]);second['name']='DP-1';d.state['outputs'].append(second)
        self.assertEqual(b.public(d.state)['outputs'],[])

    def test_timeout_cancel_eof_and_partial_command(self):
        for command in (None,b'revert\n',b'',b'k'):
            d=Driver(); original=d.query(); t=d.transaction(vsync=0)
            read,write=os.pipe()
            try:
                if command is not None:
                    if command: os.write(write,command)
                    os.close(write);write=None
                with os.fdopen(read) as stream, patch('sys.stdout',io.StringIO()): b.guard(t,stream,timeout=.02)
                self.assertEqual(d.state,original)
            finally:
                if write is not None: os.close(write)

    def test_keep_and_failed_apply_recovery(self):
        for fail in (None,1,2):
            d=Driver(); original=d.query(); d.fail=fail; t=d.transaction(vsync=0)
            read,write=os.pipe();os.write(write,b'keep\n');os.close(write)
            with os.fdopen(read) as stream, patch('sys.stdout',io.StringIO()):
                if fail:
                    with self.assertRaises(b.DisplayError): b.guard(t,stream)
                    self.assertEqual(d.state,original)
                else:
                    b.guard(t,stream);self.assertEqual(d.state,t.expected)

    def test_slow_keep_verification_cannot_extend_deadline(self):
        import time
        d=Driver(); original=d.query(); t=d.transaction()
        verify=t.verify
        def slow():
            time.sleep(.04);verify()
        t.verify=slow
        read,write=os.pipe();os.write(write,b'keep\n');os.close(write)
        with os.fdopen(read) as stream, patch('sys.stdout',io.StringIO()): b.guard(t,stream,timeout=.01)
        self.assertEqual(d.state,original)

    def test_stalled_command_is_bounded_by_remaining_deadline(self):
        import time
        context=b.command_deadline.set(time.monotonic()+.04)
        start=time.monotonic()
        try:
            with self.assertRaises(b.DeadlineExpired):
                b.run([sys.executable,'-c','import time; time.sleep(10)'])
        finally:b.command_deadline.reset(context)
        self.assertLess(time.monotonic()-start,.8)

    def test_deadline_during_poll_restores_original(self):
        d=Driver(); original=d.query(); t=d.transaction(vsync=0)
        t.verify=lambda: (_ for _ in ()).throw(b.DeadlineExpired('expired'))
        read,write=os.pipe()
        try:
            with os.fdopen(read) as stream, patch('sys.stdout',io.StringIO()): b.guard(t,stream,timeout=.4)
        finally:os.close(write)
        self.assertEqual(d.state,original)

    def test_guard_process_lock_and_sigterm_restore(self):
        import json, select, subprocess
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'fixture.json';original=Driver().state
            state.write_text(json.dumps({'state':original,'calls':[]}))
            env=dict(os.environ,XDG_RUNTIME_DIR=tmp,DOROSHELL_DISPLAY_FIXTURE=str(state))
            request=json.dumps(dict(token=b.token(original),output='DP-0',mode='0x12',vsync=0))
            command=[sys.executable,str(Path(__file__).with_name('display_driver_fixture.py')),'apply',request]
            first=subprocess.Popen(command,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            try:
                self.assertTrue(select.select([first.stdout],[],[],5)[0])
                self.assertTrue(json.loads(first.stdout.readline())['pending'])
                second=subprocess.run(command,env=env,input='',capture_output=True,text=True,timeout=5)
                self.assertEqual(second.returncode,1)
                self.assertIn('Another display confirmation',second.stdout)
                first.terminate();first.communicate(timeout=5)
                self.assertEqual(json.loads(state.read_text())['state'],original)
            finally:
                if first.poll() is None:first.kill();first.wait()
                first.stdout.close();first.stdin.close()

    def test_command_timeout_and_missing_tools(self):
        import subprocess
        for failure in (FileNotFoundError(),subprocess.TimeoutExpired('xrandr',4)):
            with patch.object(b.subprocess,'run',side_effect=failure), self.assertRaises(b.DisplayError): b.run(['xrandr'])

    def test_wayland_disabled(self):
        with patch.dict(os.environ,XDG_SESSION_TYPE='wayland'), self.assertRaises(b.DisplayError): b.snapshot()


if __name__=='__main__':unittest.main()
