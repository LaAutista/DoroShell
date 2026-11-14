"""Independent recovery regressions, using only disposable synthetic homes."""
import base64
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import deploy
import install


class RecoveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.target = self.home/'synthetic-menu-file'
        self.target.write_bytes(b'original'); self.target.chmod(0o640)
        self.payloads = patch.object(install, 'targets', return_value={self.target:(b'installed',0o644)})
        self.payloads.start(); self.addCleanup(self.payloads.stop)
        output = contextlib.redirect_stdout(io.StringIO()); output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        self.pointer = self.home/'.local/state/doroshell/deployment.json'

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.read_bytes(),p.stat().st_mode & 0o777)
                for p in self.home.rglob('*') if p.is_file()}

    def interrupt(self, operation=None):
        real = deploy.step
        def step(*args, **kwargs):
            names, action = real(*args, **kwargs)
            if args[1] == 'maintenance':
                def action():
                    if operation: operation()
                    raise OSError('fixture interruption before maintenance completes')
            return names, action
        with patch.object(deploy, 'step', side_effect=step), self.assertRaises(OSError):
            deploy.deploy(self.home, ['menu','maintenance'], {})
        self.identifier = json.loads(self.pointer.read_text())['transaction']
        self.journal_path = self.pointer.parent/'deployments'/self.identifier/'journal.json'
        return json.loads(self.journal_path.read_text())

    def recover(self):
        return deploy.deploy(self.home, ['menu','maintenance'], {}, recover=True)

    def reject_record(self, record):
        self.journal_path.write_text(json.dumps(record))
        before = self.snapshot()
        with self.assertRaises(ValueError): self.recover()
        self.assertEqual(self.snapshot(), before)
        with patch.object(deploy.compatibility, 'inspect') as inspect, patch.object(deploy, 'build_native') as build:
            with self.assertRaises(ValueError):
                deploy.main(['--home',str(self.home),'--apply','--recover','--no-packages'])
            inspect.assert_not_called(); build.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        with self.assertRaises(ValueError): deploy.undo(self.home, self.identifier)
        self.assertEqual(self.snapshot(), before)
        with patch.object(deploy.compatibility, 'inspect') as inspect, patch.object(deploy, 'build_native') as build:
            with self.assertRaises(ValueError):
                deploy.main(['--home',str(self.home),'--apply','--undo',self.identifier,'--no-packages'])
            inspect.assert_not_called(); build.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_completed_content_edit_is_not_adopted_by_recovery_or_undo(self):
        self.interrupt()
        self.target.write_bytes(b'user edit after interruption')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'Edited completed'):
            self.recover()
        self.assertEqual(self.snapshot(), before)
        with patch.object(deploy.compatibility, 'inspect') as inspect:
            with self.assertRaisesRegex(RuntimeError, 'Edited completed'):
                deploy.main(['--home',str(self.home),'--apply','--recover','--no-packages'])
            inspect.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        with self.assertRaises(ValueError): deploy.undo(self.home, self.identifier)
        self.assertEqual(self.snapshot(), before)

    def test_completed_mode_edit_is_not_adopted_by_recovery(self):
        self.interrupt(); self.target.chmod(0o600)
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'Edited completed'): self.recover()
        self.assertEqual(self.snapshot(), before)

    def test_unsupported_schema_is_rejected_by_every_entry_before_writes(self):
        record = self.interrupt(); record['format'] = 999
        self.reject_record(record)

    def test_malformed_journals_are_rejected_before_consuming_requests(self):
        pristine = self.interrupt()
        changes = [
            lambda r:r.update(format=True), lambda r:r.update(status='unknown'),
            lambda r:r.update(request=[]), lambda r:r['request'].update(remove='false'),
            lambda r:r['request'].update(unrecognized=True),
            lambda r:r['request'].update(modules=['unknown']),
            lambda r:r['request'].update(modules=['menu','menu']),
            lambda r:r['request'].update(theme='unknown'),
            lambda r:r['request'].update(source='not a hash'),
            lambda r:r.update(done=['maintenance']), lambda r:r.update(active='unknown'),
            lambda r:r.update(installed_before='menu'), lambda r:r.update(before=[]),
            lambda r:r['before'].update({'../escape':{'data':None,'mode':None}}),
            lambda r:r['before']['synthetic-menu-file'].update(data='invalid!'),
            lambda r:r['before']['synthetic-menu-file'].update(mode=-1),
            lambda r:r.update(after=[]),
            lambda r:r.update(active_files='maintenance'),
            lambda r:r.update(active_files=['unknown']),
            lambda r:r['active_files'].append(r['active_files'][0]),
            lambda r:r['after'].pop('synthetic-menu-file'),
            lambda r:r['after']['synthetic-menu-file'].update(mode=True),
            lambda r:r['before'][deploy.POINTER].update(data=base64.b64encode(b'[]').decode(),mode=0o600),
            lambda r:r['before'][deploy.POINTER].update(mode=0o600),
            lambda r:r['before'].update({'./alias':{'data':None,'mode':None}}),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                record = copy.deepcopy(pristine); change(record); self.reject_record(record)

    def test_invalid_json_or_top_level_is_rejected_without_changes(self):
        self.interrupt()
        for value in (None, [], True, 'record'):
            with self.subTest(value=value): self.reject_record(value)
        self.journal_path.write_text('{"format":2,')
        before=self.snapshot()
        with self.assertRaises(ValueError): self.recover()
        with self.assertRaises(ValueError): deploy.undo(self.home,self.identifier)
        self.assertEqual(self.snapshot(),before)

    def test_recovery_module_override_is_refused_before_prerequisites_or_writes(self):
        self.interrupt(); before=self.snapshot()
        with patch.object(deploy.compatibility,'inspect') as inspect,patch.object(deploy,'build_native') as build:
            with self.assertRaisesRegex(ValueError,'recorded module'):
                deploy.main(['--home',str(self.home),'--apply','--recover','--modules','menu'])
            inspect.assert_not_called(); build.assert_not_called()
        self.assertEqual(self.snapshot(),before)

    def test_invalid_pointer_is_refused_before_request_or_writes(self):
        self.interrupt(); pristine=json.loads(self.pointer.read_text())
        for changes in ({'format':999}, {'status':'unknown'}, {'transaction':'../escape'}, {'modules':['unknown']}):
            record={**pristine,**changes}; self.pointer.write_text(json.dumps(record))
            before=self.snapshot()
            with self.assertRaises(ValueError): self.recover()
            with patch.object(deploy.compatibility,'inspect') as inspect:
                with self.assertRaises(ValueError): deploy.main(['--home',str(self.home),'--apply','--recover'])
                inspect.assert_not_called()
            self.assertEqual(self.snapshot(),before)

    def test_legacy_pending_evidence_is_not_invented(self):
        record = self.interrupt(); record['format'] = 1
        record.pop('active_files', None); record['after'] = {}
        self.reject_record(record)

    def test_completed_step_evidence_survives_recovery_and_exact_undo(self):
        journal = self.interrupt()
        before = journal['before']['synthetic-menu-file']
        self.assertEqual(journal['after']['synthetic-menu-file'], deploy.file_state(self.home,'synthetic-menu-file'))
        self.recover()
        self.assertEqual(json.loads(self.journal_path.read_text())['before']['synthetic-menu-file'], before)
        deploy.undo(self.home,self.identifier)
        self.assertEqual(self.target.read_bytes(), b'original')
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)

    def test_edit_during_later_module_cannot_be_adopted_at_finalization(self):
        real = deploy.step
        def step(*args, **kwargs):
            names, action = real(*args, **kwargs)
            if args[1] == 'maintenance':
                original_action = action
                def action():
                    self.target.write_bytes(b'concurrent user edit')
                    original_action()
            return names, action
        with patch.object(deploy,'step',side_effect=step), self.assertRaisesRegex(RuntimeError,'Edited completed'):
            deploy.deploy(self.home,['menu','maintenance'],{})
        pointer = json.loads(self.pointer.read_text()); self.assertEqual(pointer['status'],'pending')
        journal = json.loads((self.pointer.parent/'deployments'/pointer['transaction']/'journal.json').read_text())
        self.assertEqual(base64.b64decode(journal['after']['synthetic-menu-file']['data']),b'installed')
        self.assertEqual(self.target.read_bytes(),b'concurrent user edit')

    def test_successful_overlapping_step_records_latest_expected_state(self):
        real = deploy.step
        def step(*args, **kwargs):
            names, action = real(*args, **kwargs)
            if args[1] == 'maintenance':
                original_action = action
                def action():
                    original_action(); self.target.write_bytes(b'next module output')
                names.append('synthetic-menu-file')
            return names, action
        with patch.object(deploy,'step',side_effect=step):
            identifier = deploy.deploy(self.home,['menu','maintenance'],{})
        deploy.undo(self.home,identifier)
        self.assertEqual(self.target.read_bytes(),b'original')

    def test_interrupted_overlap_without_success_evidence_refuses_to_guess(self):
        real=deploy.step
        def step(*args,**kwargs):
            names,action=real(*args,**kwargs)
            if args[1]=='maintenance':
                names.append('synthetic-menu-file')
                def action():
                    self.target.write_bytes(b'unverified partial overlapping output')
                    raise OSError('interrupted overlap')
            return names,action
        with patch.object(deploy,'step',side_effect=step),self.assertRaises(OSError):
            deploy.deploy(self.home,['menu','maintenance'],{})
        before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Edited completed'): self.recover()
        self.assertEqual(self.snapshot(),before)

    def test_changed_active_inventory_is_refused_without_adopting_new_targets(self):
        self.interrupt(); before=self.snapshot(); real=deploy.step
        def step(*args,**kwargs):
            names,action=real(*args,**kwargs)
            return [*names,'unexpected-target'],action
        with patch.object(deploy,'step',side_effect=step),self.assertRaisesRegex(ValueError,'Changed pending module inventory'):
            self.recover()
        self.assertEqual(self.snapshot(),before)

    def test_completed_symlink_is_refused_without_following_it(self):
        self.interrupt(); self.target.unlink()
        unrelated=self.home/'unrelated'; unrelated.write_bytes(b'private fixture')
        self.target.symlink_to(unrelated)
        before=self.snapshot()
        with self.assertRaisesRegex((ValueError,RuntimeError),'symlink'): self.recover()
        self.assertTrue(self.target.is_symlink()); self.assertEqual(self.snapshot(),before)

    def test_finalization_validates_terminal_record_before_writes(self):
        real=deploy.atomic
        def fail(path,data,mode=0o600):
            if path==self.pointer and json.loads(data)['status']=='complete': raise OSError('pointer interruption')
            real(path,data,mode)
        with patch.object(deploy,'atomic',side_effect=fail),self.assertRaises(OSError):
            deploy.deploy(self.home,['menu','maintenance'],{})
        self.identifier=json.loads(self.pointer.read_text())['transaction']
        self.journal_path=self.pointer.parent/'deployments'/self.identifier/'journal.json'
        pristine=json.loads(self.journal_path.read_text())
        changes=[lambda r:r.update(format=999),lambda r:r.update(status='unknown'),
                 lambda r:r['after'].pop('synthetic-menu-file'),lambda r:r.update(done=['menu']),
                 lambda r:r['after'][deploy.POINTER].update(data=base64.b64encode(b'{}').decode())]
        for change in changes:
            record=copy.deepcopy(pristine); change(record); self.reject_record(record)
        self.journal_path.write_text(json.dumps(pristine)); self.recover()
        deploy.undo(self.home,self.identifier)
        self.assertEqual(self.target.read_bytes(),b'original')

    def test_legacy_completed_journal_retains_exact_undo(self):
        identifier = deploy.deploy(self.home,['menu','maintenance'],{})
        path = self.pointer.parent/'deployments'/identifier/'journal.json'
        record=json.loads(path.read_text()); record['format']=1; record.pop('active_files',None)
        path.write_text(json.dumps(record))
        deploy.undo(self.home,identifier)
        self.assertEqual(self.target.read_bytes(),b'original')

    def test_interrupted_undo_remains_resumable_for_both_formats(self):
        for version in (1,2):
            with self.subTest(version=version):
                identifier=deploy.deploy(self.home,['menu','maintenance'],{})
                path=self.pointer.parent/'deployments'/identifier/'journal.json'
                record=json.loads(path.read_text()); record['format']=version
                if version==1: record.pop('active_files')
                path.write_text(json.dumps(record)); real=deploy.atomic
                def fail(path,data,mode=0o600):
                    if path==self.target and data==b'original': raise OSError('undo interruption')
                    real(path,data,mode)
                with patch.object(deploy,'atomic',side_effect=fail),self.assertRaises(OSError):
                    deploy.undo(self.home,identifier)
                self.assertEqual(json.loads(path.read_text())['status'],'undoing')
                deploy.undo(self.home,identifier); deploy.undo(self.home,identifier)
                self.assertEqual(json.loads(path.read_text())['status'],'undone')
                self.assertEqual(self.target.read_bytes(),b'original')
                self.assertEqual(self.target.stat().st_mode&0o777,0o640)
