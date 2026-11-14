"""Installed input lifecycle in disposable homes; all devices are synthetic."""
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
import input_preferences as ip
from test_input_preferences import Backend, device


class InputLifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.home=Path(tmp.name); self.store=ip.Preferences(self.home)
        self.backend=Backend([device()])
        output=contextlib.redirect_stdout(io.StringIO()); output.__enter__()
        self.addCleanup(output.__exit__,None,None,None)

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.read_bytes(),p.stat().st_mode&0o777)
                for p in self.home.rglob('*') if p.is_file()}

    def opt_in(self):
        dev=self.backend.items[0]; raw,_=self.store.read()
        return self.store.run(self.backend,(dev['key'],dict(name=dev['name'],action='acceleration',enabled=True)),raw)

    def stop(self):
        return self.store.run(self.backend,expected=self.store.read()[0],stop=True)

    def test_install_repeat_update_and_remove_preserve_choices_and_first_baseline(self):
        install.install(self.home,True); self.assertEqual(self.store.helper.read_bytes(),Path(ip.__file__).read_bytes())
        self.opt_in(); saved=self.store.path.read_bytes(); startup=self.store.startup.read_bytes()
        manifest=self.home/'.local/state/lxqt-comfort/menu-install.json'
        baseline=manifest.read_bytes(); install.install(self.home,True)
        self.assertEqual(manifest.read_bytes(),baseline)
        self.assertEqual(self.store.path.read_bytes(),saved); self.assertEqual(self.store.startup.read_bytes(),startup)
        before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'still need their helper'): install.rollback(self.home)
        self.assertEqual(self.snapshot(),before)
        self.stop(); saved=self.store.path.read_bytes(); install.rollback(self.home)
        self.assertFalse(self.store.helper.exists()); self.assertFalse(self.store.startup.exists())
        self.assertEqual(self.store.path.read_bytes(),saved)

    def test_upgrade_from_older_toolkit_and_exact_undo_are_guarded(self):
        real=install.targets
        def old(home,icon=None):
            files=real(home,icon); files.pop(self.store.helper)
            files[home/'.local/share/doroshell/toolkit/settings.py']=(b'# older settings fixture\n',0o644)
            return files
        with patch.object(install,'targets',side_effect=old): old_id=deploy.deploy(self.home,['menu'],{})
        old_manifest=(self.home/'.local/state/lxqt-comfort/menu-install.json').read_bytes()
        upgrade=deploy.deploy(self.home,['menu'],{}); self.opt_in(); before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'still need their helper'): deploy.undo(self.home,upgrade)
        self.assertEqual(self.snapshot(),before)
        self.stop(); saved=self.store.path.read_bytes(); deploy.undo(self.home,upgrade)
        self.assertFalse(self.store.helper.exists()); self.assertFalse(self.store.startup.exists())
        self.assertEqual(self.store.path.read_bytes(),saved)
        self.assertEqual((self.home/'.local/state/lxqt-comfort/menu-install.json').read_bytes(),old_manifest)
        self.assertEqual(json.loads((self.home/deploy.POINTER).read_text())['transaction'],old_id)

    def test_repeat_deployment_undo_keeps_active_choices_if_helper_identical(self):
        deploy.deploy(self.home,['menu'],{}); self.opt_in()
        saved=self.store.path.read_bytes(); startup=self.store.startup.read_bytes()
        identifier=deploy.deploy(self.home,['menu'],{}); deploy.undo(self.home,identifier)
        self.assertEqual(self.store.path.read_bytes(),saved); self.assertEqual(self.store.startup.read_bytes(),startup)

    def test_full_removal_preflight_refuses_before_removing_any_module(self):
        deploy.deploy(self.home,['menu','maintenance'],{}); self.opt_in(); before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'still need their helper'):
            deploy.deploy(self.home,['menu','maintenance'],{},remove=True)
        self.assertEqual(self.snapshot(),before)
        with patch.object(deploy.compatibility,'inspect') as inspect:
            with self.assertRaises(RuntimeError):
                deploy.main(['--home',str(self.home),'--modules','menu','maintenance','--remove','--apply'])
            inspect.assert_not_called()
        self.assertEqual(self.snapshot(),before)
        self.stop(); identifier=deploy.deploy(self.home,['menu','maintenance'],{},remove=True)
        self.assertFalse(self.store.helper.exists()); deploy.undo(self.home,identifier)
        self.assertTrue(self.store.helper.exists()); self.assertFalse(self.store.startup.exists())

    def test_installer_and_preferences_share_retained_lock(self):
        install.install(self.home,True); self.opt_in(); self.stop()
        lock=self.store.path.with_suffix('.lock'); inode=lock.stat().st_ino
        with self.store.locked(), self.assertRaises(BlockingIOError): install.rollback(self.home)
        self.assertTrue(self.store.helper.exists()); install.rollback(self.home)
        self.assertEqual(lock.stat().st_ino,inode)

    def test_absent_and_unsupported_restoration_keep_helper_and_evidence(self):
        install.install(self.home,True); self.opt_in(); receipt=copy.deepcopy(self.store.read()[1]['receipts'])
        dev=self.backend.items[0]; self.backend.items=[]
        self.assertIn('absent',' '.join(self.stop()))
        self.assertEqual(self.store.read()[1]['receipts'],receipt)
        with self.assertRaises(RuntimeError): install.rollback(self.home)
        self.backend.items=[dev]; dev['driver']='libinput'
        self.assertIn('unsupported',' '.join(self.stop()))
        self.assertEqual(self.store.read()[1]['receipts'],receipt)
        with self.assertRaises(RuntimeError): install.rollback(self.home)
        dev['driver']='evdev'; self.stop(); install.rollback(self.home)
        self.assertEqual(dev['props'][ip.PROFILE]['values'],[0])

    def test_expired_receipt_is_archived_before_absent_device_is_retired(self):
        install.install(self.home,True); self.opt_in()
        receipt=copy.deepcopy(self.store.read()[1]['receipts']); self.backend.items=[]
        self.stop(); self.backend.session='next-session'
        messages=self.store.run(self.backend)
        self.assertIn('evidence archived',' '.join(messages))
        archives=list((self.home/'.local/state/doroshell/input-restoration').glob('*.json'))
        self.assertEqual(len(archives),1)
        self.assertEqual(json.loads(archives[0].read_text())['receipt'],receipt['a'*64])
        self.assertEqual(archives[0].stat().st_mode&0o777,0o600)
        install.rollback(self.home); self.assertTrue(archives[0].exists())

    def test_archive_failure_preserves_receipt_and_does_not_write_device(self):
        install.install(self.home,True); self.opt_in(); self.backend.session='next-session'
        before=self.store.path.read_bytes(); count=len(self.backend.writes)
        with patch.object(self.store,'archive_receipt',side_effect=OSError('fixture archive failure')):
            with self.assertRaises(OSError): self.store.run(self.backend)
        self.assertEqual(self.store.path.read_bytes(),before); self.assertEqual(len(self.backend.writes),count)

    def test_autostart_conflicts_and_unknown_ownership_block_without_device_writes(self):
        install.install(self.home,True)
        self.store.startup.parent.mkdir(parents=True)
        self.store.startup.write_bytes(self.store.startup_payload()); self.store.startup.chmod(0o600)
        with self.assertRaisesRegex(RuntimeError,'unowned'): self.opt_in()
        self.assertFalse(self.backend.writes); self.assertFalse(self.store.path.exists())
        self.store.startup.unlink(); self.opt_in()
        for content,mode in ((b'personal entry',0o600),(self.store.startup_payload(),0o644)):
            self.store.startup.write_bytes(content); self.store.startup.chmod(mode)
            before=self.snapshot(); count=len(self.backend.writes)
            with self.assertRaises(RuntimeError): self.stop()
            with self.assertRaises(RuntimeError): install.rollback(self.home)
            self.assertEqual(self.snapshot(),before); self.assertEqual(len(self.backend.writes),count)

    def test_interrupted_autostart_creation_and_removal_retry_safely(self):
        install.install(self.home,True); real=self.store.write
        def fail_creation(path,data):
            if path==self.store.startup: raise OSError('fixture startup failure')
            real(path,data)
        with patch.object(self.store,'write',side_effect=fail_creation),self.assertRaises(OSError): self.opt_in()
        self.assertEqual(self.store.read()[1]['startup'],'pending'); self.assertFalse(self.backend.writes)
        self.store.run(self.backend); self.assertEqual(self.store.read()[1]['startup'],'installed')
        def fail_final(path,data):
            if path==self.store.path and json.loads(data).get('startup') is None: raise OSError('fixture final record failure')
            real(path,data)
        with patch.object(self.store,'write',side_effect=fail_final),self.assertRaises(OSError): self.stop()
        self.assertFalse(self.store.startup.exists()); self.assertEqual(self.store.read()[1]['startup'],'removing')
        self.store.run(self.backend); self.store.require_inactive()

    def test_missing_helper_and_invalid_saved_fields_do_not_mutate_device(self):
        with self.assertRaisesRegex(RuntimeError,'Install/update'): self.opt_in()
        self.assertFalse(self.backend.writes); self.assertFalse(self.store.path.exists())
        install.install(self.home,True); self.opt_in(); pristine=self.store.read()[1]
        for changed in ({'startup':'unknown'},{'rules':{'a'*64:[]}}, {'rules':{'a'*64:dict(action='acceleration',enabled=True)}}):
            self.store.path.write_text(json.dumps({**pristine,**changed})); before=self.snapshot()
            with self.assertRaises(ValueError): self.store.run(self.backend)
            with self.assertRaises(ValueError): install.rollback(self.home)
            self.assertEqual(self.snapshot(),before)

    def test_helper_byte_and_mode_edits_are_not_overwritten_by_update_or_removal(self):
        install.install(self.home,True); self.opt_in(); self.stop()
        original=self.store.helper.read_bytes()
        for data,mode in ((original+b'\n# personal fixture edit\n',0o644),(original,0o600)):
            self.store.helper.write_bytes(data); self.store.helper.chmod(mode); before=self.snapshot()
            with self.assertRaises(RuntimeError): install.install(self.home,True)
            with self.assertRaises(RuntimeError): install.rollback(self.home)
            self.assertEqual(self.snapshot(),before)
