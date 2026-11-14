"""Legacy cursor schema compatibility and interrupted-write recovery in fixtures."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cursor


class CursorRecoveryTests(unittest.TestCase):
    def test_partial_update_retry_original_baseline_and_mode_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);a=home/'a';b=home/'b'
            for p in (a,b):p.write_bytes(b'original');p.chmod(0o640)
            with patch.object(cursor,'targets',return_value={a:b'v1',b:b'v1'}):cursor.run(home,home/'fake.gif',apply=True)
            real=cursor.atomic
            def fail(path,*args):
                if path==b:raise OSError('injected')
                real(path,*args)
            with patch.object(cursor,'targets',return_value={a:b'v2',b:b'v2'}),patch.object(cursor,'atomic',side_effect=fail),self.assertRaises(OSError):
                cursor.run(home,home/'fake.gif',apply=True)
            self.assertEqual(a.read_bytes(),b'v2');self.assertEqual(b.read_bytes(),b'v1')
            a.chmod(0o600)
            with patch.object(cursor,'targets',return_value={a:b'v2',b:b'v2'}),self.assertRaises(RuntimeError):cursor.run(home,home/'fake.gif',apply=True)
            a.chmod(0o640)
            with patch.object(cursor,'targets',return_value={a:b'v2',b:b'v2'}):cursor.run(home,home/'fake.gif',apply=True)
            cursor.run(home,rollback=True)
            for p in (a,b):self.assertEqual(p.read_bytes(),b'original');self.assertEqual(p.stat().st_mode&0o777,0o640)

    def test_malformed_pending_record_and_interrupted_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);a=home/'a';b=home/'b'
            for p in (a,b):p.write_bytes(b'original')
            with patch.object(cursor,'targets',return_value={a:b'new',b:b'new'}):cursor.run(home,home/'fake.gif',apply=True)
            manifest=home/'.local/state/lxqt-comfort/cursor-install.json';original=manifest.read_bytes()
            record=json.loads(original);record['b']['pending_mode']=-1;manifest.write_text(json.dumps(record))
            with self.assertRaises(ValueError):cursor.run(home,rollback=True)
            self.assertEqual(a.read_bytes(),b'new');manifest.write_bytes(original)
            real=cursor.atomic
            def fail(path,*args):
                if path==b:raise OSError('injected')
                real(path,*args)
            with patch.object(cursor,'atomic',side_effect=fail),self.assertRaises(OSError):cursor.run(home,rollback=True)
            cursor.run(home,rollback=True)
            for p in (a,b):self.assertEqual(p.read_bytes(),b'original')
