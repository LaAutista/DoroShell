"""Permission-edit regression checks on ordinary disposable fixture files only."""
import json
from unittest.mock import patch
import unittest
import test_transaction_faults as fixtures
import install
import modules

class ModeConflictTests(unittest.TestCase):
    setUp = fixtures.TransactionFaultTests.setUp
    snapshot = fixtures.TransactionFaultTests.snapshot
    payloads = fixtures.TransactionFaultTests.payloads
    edits = fixtures.TransactionFaultTests.edits
    menu = fixtures.TransactionFaultTests.menu
    optional = fixtures.TransactionFaultTests.optional
    def test_menu_chmod_refuses_update_repeat_and_rollback_legacy_and_new(self):
        with self.menu(b'v1'):install.install(self.home,True)
        manifest=self.home/'.local/state/lxqt-comfort/menu-install.json'
        self.paths[0].chmod(0o600)
        for legacy in (False,True):
            if legacy:
                record=json.loads(manifest.read_text())
                for entry in record.values():entry.pop('installed_mode',None)
                manifest.write_text(json.dumps(record))
            before=self.snapshot()
            for version in (b'v1',b'v2'):
                with self.menu(version):
                    with self.assertRaises(RuntimeError):install.install(self.home,True)
                    with self.assertRaises(RuntimeError):install.rollback(self.home)
                self.assertEqual(before,self.snapshot())

    def test_optional_chmod_refuses_update_and_rollback(self):
        with self.optional(b'v1'):modules.run(self.home,'theme',apply=True)
        self.paths[0].chmod(0o600);before=self.snapshot()
        with self.optional(b'v2'):
            for kwargs in ({'apply':True},{'rollback':True}):
                with self.assertRaises(RuntimeError):modules.run(self.home,'theme',**kwargs)
                self.assertEqual(before,self.snapshot())

    def test_optional_chmod_during_failed_apply_preserves_edit(self):
        with self.optional(b'v1'):modules.run(self.home,'theme',apply=True)
        atomic=modules.atomic
        def fail(path,data,mode=0o600):
            if path==self.paths[1]:
                self.paths[0].chmod(0o600)
                raise OSError('injected write failure with chmod')
            return atomic(path,data,mode)
        with self.optional(b'v2'),patch.object(modules,'atomic',side_effect=fail):
            with self.assertRaises(RuntimeError):modules.run(self.home,'theme',apply=True)
        self.assertEqual(self.paths[0].stat().st_mode&0o777,0o600)
        before=self.snapshot()
        with self.optional(b'v2'):
            with self.assertRaises(RuntimeError):modules.run(self.home,'theme',rollback=True)
        self.assertEqual(before,self.snapshot())

    def test_symlink_substitution_refused(self):
        with self.menu(b'v1'):install.install(self.home,True)
        target=self.home/'unmanaged';target.write_bytes(b'personal');target.chmod(0o600)
        self.paths[0].unlink();self.paths[0].symlink_to(target)
        with self.menu(b'v2'):
            with self.assertRaises(RuntimeError):install.install(self.home,True)
            with self.assertRaises(RuntimeError):install.rollback(self.home)
        self.assertEqual(target.read_bytes(),b'personal');self.assertEqual(target.stat().st_mode&0o777,0o600)

    def test_interrupted_menu_chmod_refuses_then_recovery_resumes(self):
        with self.menu(b'v1'):install.install(self.home,True)
        with self.menu(b'v2'),patch.object(install,'atomic',side_effect=fixtures.TransactionFaultTests.fail_second(self,install.atomic)):
            with self.assertRaises(OSError):install.install(self.home,True)
        self.paths[1].chmod(0o600);before=self.snapshot()
        with self.menu(b'v2'):
            with self.assertRaises(RuntimeError):install.install(self.home,True)
            with self.assertRaises(RuntimeError):install.rollback(self.home)
        self.assertEqual(before,self.snapshot())
        self.paths[1].chmod(0o644)
        with self.menu(b'v2'):install.install(self.home,True);install.rollback(self.home)
        for path in self.paths:
            self.assertEqual(path.read_bytes(),b'original')
            self.assertEqual(path.stat().st_mode&0o777,0o640)

    def test_clean_legacy_menu_and_optional_symlink(self):
        with self.menu(b'v1'):install.install(self.home,True)
        manifest=self.home/'.local/state/lxqt-comfort/menu-install.json'
        record=json.loads(manifest.read_text())
        for entry in record.values():entry.pop('installed_mode',None)
        manifest.write_text(json.dumps(record))
        with self.menu(b'v2'):install.install(self.home,True);install.rollback(self.home)
        with self.optional(b'v1'):modules.run(self.home,'theme',apply=True)
        target=self.home/'unmanaged';target.write_bytes(b'personal');target.chmod(0o600)
        self.paths[0].unlink();self.paths[0].symlink_to(target)
        with self.optional(b'v2'):
            for kwargs in ({'apply':True},{'rollback':True}):
                with self.assertRaises(RuntimeError):modules.run(self.home,'theme',**kwargs)
        self.assertEqual(target.read_bytes(),b'personal');self.assertEqual(target.stat().st_mode&0o777,0o600)
