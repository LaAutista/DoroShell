"""Fault injection on real persistence engines, using only disposable homes."""
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import install
import modules

class TransactionFaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.paths=[self.home/'a',self.home/'b']
        for p in self.paths:p.write_bytes(b'original');p.chmod(0o640)

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.read_bytes(),p.stat().st_mode&0o777)
                for p in self.home.rglob('*') if p.is_file()}

    def payloads(self,version):return {p:(version,0o644) for p in self.paths}
    def edits(self,version):
        return [dict(file=p.name,kind='file',after=base64.b64encode(version).decode(),mode=0o644) for p in self.paths]
    def menu(self,version):return patch.object(install,'targets',return_value=self.payloads(version))
    def optional(self,version):return patch.object(modules,'plans',return_value=self.edits(version))
    def fail_second(self,atomic,conflict=False):
        fired=False
        def write(path,data,mode=0o600):
            nonlocal fired
            if path==self.paths[1] and not fired:
                fired=True
                if conflict:self.paths[0].write_bytes(b'user edit')
                raise OSError('injected second-file failure')
            return atomic(path,data,mode)
        return write

    def test_menu_interrupted_upgrade_retry_preserves_first_baseline(self):
        with self.menu(b'v1'):install.install(self.home,True)
        manifest=self.home/'.local/state/lxqt-comfort/menu-install.json'
        first=json.loads(manifest.read_text())
        with self.menu(b'v2'),patch.object(install,'atomic',side_effect=self.fail_second(install.atomic)):
            with self.assertRaises(OSError):install.install(self.home,True)
        interrupted=json.loads(manifest.read_text())
        self.assertEqual([p.read_bytes() for p in self.paths],[b'v2',b'v1'])
        self.assertTrue(all('pending_from' in x for x in interrupted.values()))
        with self.menu(b'v2'):install.install(self.home,True);install.rollback(self.home)
        for p in self.paths:self.assertEqual(p.read_bytes(),b'original');self.assertEqual(p.stat().st_mode&0o777,0o640)
        self.assertEqual(first['a']['original'],interrupted['a']['original'])

    def test_menu_interrupted_upgrade_user_edit_refuses_retry_and_rollback(self):
        with self.menu(b'v1'):install.install(self.home,True)
        with self.menu(b'v2'),patch.object(install,'atomic',side_effect=self.fail_second(install.atomic)):
            with self.assertRaises(OSError):install.install(self.home,True)
        self.paths[0].write_bytes(b'user edit');before=self.snapshot()
        with self.menu(b'v2'):
            for action in (lambda:install.install(self.home,True),lambda:install.rollback(self.home)):
                with self.assertRaises(RuntimeError):action()
                self.assertEqual(self.snapshot(),before)

    def test_menu_interrupted_rollback_can_resume(self):
        with self.menu(b'v1'):install.install(self.home,True)
        with self.menu(b'v1'),patch.object(install,'atomic',side_effect=self.fail_second(install.atomic)):
            with self.assertRaises(OSError):install.rollback(self.home)
        self.assertEqual([p.read_bytes() for p in self.paths],[b'original',b'v1'])
        with self.menu(b'v1'):install.rollback(self.home)
        self.assertEqual([p.read_bytes() for p in self.paths],[b'original',b'original'])

    def test_malformed_menu_backup_refused_before_any_write(self):
        with self.menu(b'v1'):install.install(self.home,True)
        manifest=self.home/'.local/state/lxqt-comfort/menu-install.json'
        pristine=json.loads(manifest.read_text())
        for field,value in (('mode',None),('mode',-1),('original','invalid!')):
            data=json.loads(json.dumps(pristine))
            if field=='mode' and value is None:del data['b']['mode']
            else:data['b'][field]=value
            manifest.write_text(json.dumps(data));before=self.snapshot()
            with self.menu(b'v2'):
                for action in (lambda:install.install(self.home,True),lambda:install.rollback(self.home)):
                    with self.assertRaises(ValueError):action()
                    self.assertEqual(self.snapshot(),before)

    def test_optional_failed_upgrade_restores_previous_version_and_manifest(self):
        with self.optional(b'v1'):modules.run(self.home,'theme',apply=True)
        before=self.snapshot()
        with self.optional(b'v2'),patch.object(modules,'atomic',side_effect=self.fail_second(modules.atomic)):
            with self.assertRaises(OSError):modules.run(self.home,'theme',apply=True)
        self.assertEqual(self.snapshot(),before)
        with self.optional(b'v2'):modules.run(self.home,'theme',apply=True);modules.run(self.home,'theme',rollback=True)
        self.assertEqual([p.read_bytes() for p in self.paths],[b'original',b'original'])

    def test_optional_recovery_preserves_concurrent_user_edit(self):
        with self.optional(b'v1'):modules.run(self.home,'theme',apply=True)
        with self.optional(b'v2'),patch.object(modules,'atomic',side_effect=self.fail_second(modules.atomic,True)):
            with self.assertRaisesRegex(RuntimeError,'recovery manifest'):modules.run(self.home,'theme',apply=True)
        self.assertEqual(self.paths[0].read_bytes(),b'user edit');before=self.snapshot()
        with self.optional(b'v2'):
            for kwargs in ({'apply':True},{'rollback':True}):
                with self.assertRaises(RuntimeError):modules.run(self.home,'theme',**kwargs)
                self.assertEqual(self.snapshot(),before)

    def test_malformed_optional_backup_refused_before_any_write(self):
        with self.optional(b'v1'):modules.run(self.home,'theme',apply=True)
        manifest=self.home/'.local/state/doroshell/theme.json'
        pristine=json.loads(manifest.read_text())
        for field,value in (('mode',None),('mode',-1),('data','invalid!')):
            data=json.loads(json.dumps(pristine))
            if field=='mode' and value is None:del data['backup']['b']['mode']
            else:data['backup']['b'][field]=value
            manifest.write_text(json.dumps(data));before=self.snapshot()
            with self.optional(b'v2'):
                for kwargs in ({'apply':True},{'rollback':True}):
                    with self.assertRaises(ValueError):modules.run(self.home,'theme',**kwargs)
                    self.assertEqual(self.snapshot(),before)

    def test_truncated_manifests_leave_all_files_untouched(self):
        for kind in ('menu','theme'):
            with self.subTest(kind=kind):
                manifest=self.home/('.local/state/lxqt-comfort/menu-install.json' if kind=='menu' else '.local/state/doroshell/theme.json')
                manifest.parent.mkdir(parents=True,exist_ok=True);manifest.write_text('{')
                before=self.snapshot()
                with self.menu(b'v2'),self.optional(b'v2'):
                    action=(lambda:install.install(self.home,True)) if kind=='menu' else (lambda:modules.run(self.home,'theme',apply=True))
                    with self.assertRaises(ValueError):action()
                self.assertEqual(self.snapshot(),before)

    def test_optional_failed_rollback_restores_installed_version(self):
        with self.optional(b'v1'):modules.run(self.home,'theme',apply=True)
        before=self.snapshot()
        with self.optional(b'v1'),patch.object(modules,'atomic',side_effect=self.fail_second(modules.atomic)):
            with self.assertRaises(OSError):modules.run(self.home,'theme',rollback=True)
        self.assertEqual(self.snapshot(),before)
        with self.optional(b'v1'):modules.run(self.home,'theme',rollback=True)
        self.assertEqual([p.read_bytes() for p in self.paths],[b'original',b'original'])

    def test_menu_final_manifest_failure_leaves_recoverable_pending_record(self):
        manifest=self.home/'.local/state/lxqt-comfort/menu-install.json'
        atomic=install.atomic;count=0
        def fail_final(path,data,mode=0o600):
            nonlocal count
            if path==manifest:
                count+=1
                if count==2:raise OSError('injected final manifest failure')
            return atomic(path,data,mode)
        with self.menu(b'v1'),patch.object(install,'atomic',side_effect=fail_final):
            with self.assertRaises(OSError):install.install(self.home,True)
        self.assertTrue(all('pending_from' in e for e in json.loads(manifest.read_text()).values()))
        with self.menu(b'v1'):install.rollback(self.home)
        self.assertEqual([p.read_bytes() for p in self.paths],[b'original',b'original'])

    def test_optional_bad_after_payload_cannot_fail_after_first_restore(self):
        with self.optional(b'v1'):modules.run(self.home,'theme',apply=True)
        manifest=self.home/'.local/state/doroshell/theme.json'
        data=json.loads(manifest.read_text());data['edits'][1]['after']='a'
        # A prior interrupted rollback has already restored this second file.
        self.paths[1].write_bytes(b'original');manifest.write_text(json.dumps(data))
        before=self.snapshot()
        with self.optional(b'v1'):
            with self.assertRaises(ValueError):modules.run(self.home,'theme',rollback=True)
        self.assertEqual(self.snapshot(),before)

    def test_optional_invalid_backup_text_preflight_before_first_restore(self):
        edits=self.edits(b'v1')[:1]+[dict(file='b',kind='ini',section='Test',key='key',after='new')]
        self.paths[1].write_bytes(b'[Test]\nkey=old\n')
        with patch.object(modules,'plans',return_value=edits):modules.run(self.home,'theme',apply=True)
        manifest=self.home/'.local/state/doroshell/theme.json'
        data=json.loads(manifest.read_text());data['backup']['b']['data']=base64.b64encode(b'\xff').decode()
        manifest.write_text(json.dumps(data));before=self.snapshot()
        with self.assertRaises(ValueError):modules.run(self.home,'theme',rollback=True)
        self.assertEqual(self.snapshot(),before)

    def test_saved_hash_kind_and_mode_validation(self):
        with self.menu(b'v1'):install.install(self.home,True)
        menu_manifest=self.home/'.local/state/lxqt-comfort/menu-install.json'
        pristine=json.loads(menu_manifest.read_text())
        for field,value in (('installed','not-a-digest'),('pending_from',False)):
            data=json.loads(json.dumps(pristine));data['b'][field]=value
            menu_manifest.write_text(json.dumps(data));before=self.snapshot()
            with self.menu(b'v2'):
                with self.assertRaises(ValueError):install.install(self.home,True)
                with self.assertRaises(ValueError):install.rollback(self.home)
            self.assertEqual(self.snapshot(),before)
        # Independent optional manifest, without changing any personal state.
        with self.optional(b'v2'):modules.run(self.home,'theme',apply=True)
        manifest=self.home/'.local/state/doroshell/theme.json'
        pristine=json.loads(manifest.read_text())
        for field,value in (('kind','unknown'),('mode',True),('after',False)):
            data=json.loads(json.dumps(pristine));data['edits'][1][field]=value
            manifest.write_text(json.dumps(data));before=self.snapshot()
            for kwargs in ({'apply':True},{'rollback':True}):
                with self.assertRaises(ValueError):modules.run(self.home,'theme',**kwargs)
                self.assertEqual(self.snapshot(),before)
