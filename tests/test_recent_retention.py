"""Age-based recent apps in disposable homes/offscreen Qt; never launch an app."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import shiboken6
from PySide6.QtCore import QObject, Signal
from test_menu import menu
import portable_settings as portable


class Server(QObject):
    newConnection=Signal()


class RecentRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=menu.QApplication.instance() or menu.QApplication([])

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.home=Path(temp.name);self.config=self.home/'.config'
        self.path=self.config/'lxqt-comfort/recent.json';self.path.parent.mkdir(parents=True)
        self.enterContext(patch.dict(os.environ,{'HOME':str(self.home),'XDG_CONFIG_HOME':str(self.config),'XDG_DATA_HOME':str(self.home/'.local/share')},clear=True))
        self.clock=self.enterContext(patch.object(menu.time,'time',return_value=2000000))

    def write(self,value):self.path.write_text(json.dumps(value));return self.path.read_bytes()
    def store(self):return menu.RecentPrograms(self.path)
    def timed(self,**updates):
        value={'enabled':True,'items':['fixture.desktop'],'retention_days':1,'launched_at':{'fixture.desktop':2000000}}
        value.update(updates);self.write(value);return self.store()
    def window(self):
        with patch.object(menu,'applications',return_value=[]):window=menu.StartMenu()
        self.addCleanup(lambda: shiboken6.delete(window) if shiboken6.isValid(window) else None)
        return window

    def test_default_legacy_has_no_expiry_timestamp_collection_or_open_writes(self):
        original=self.write({'enabled':True,'items':['old.desktop']})
        with patch.object(menu.time,'time',side_effect=AssertionError('default must not read clock')):
            store=self.store()
            for _ in range(3):store.prune();self.assertEqual(store.items(),['old.desktop'])
            self.assertEqual(self.path.read_bytes(),original)
            store.save(launched='next.desktop')
            self.assertEqual(store.value,{'enabled':True,'items':['next.desktop','old.desktop']})
        self.assertNotIn('launched_at',store.value)
        self.assertNotIn('retention_days',portable.Store(self.home).export()['preferences']['recent'])

    def test_enabling_discards_untimed_entries_without_invented_times(self):
        self.write({'enabled':True,'limit':5,'items':['old.desktop','unknown.desktop']})
        store=self.store();store.save(retention_days=7)
        self.assertEqual(store.value['items'],[]);self.assertEqual(store.value['launched_at'],{})
        self.assertEqual(list(self.path.parent.glob('recent.json.backup-*')),[])
        store.save(launched='new.desktop');self.assertEqual(store.value['launched_at'],{'new.desktop':2000000})
        store.save(retention_days=0);self.assertNotIn('launched_at',store.value)
        self.clock.return_value+=999999;self.assertEqual(store.items(),['new.desktop'])

    def test_expiry_boundary_relaunch_and_no_repeated_writes(self):
        store=self.timed();self.clock.return_value+=86399
        original=self.path.read_bytes();store.prune();self.assertEqual(self.path.read_bytes(),original)
        self.assertEqual(store.items(),['fixture.desktop'])
        self.clock.return_value+=1;self.assertEqual(store.items(),[]);store.prune()
        self.assertEqual(store.value['items'],[])
        stamp=self.path.stat().st_mtime_ns
        with patch.object(menu,'save_json',side_effect=AssertionError('no redundant write')):
            for _ in range(3):self.store().prune()
        self.assertEqual(self.path.stat().st_mtime_ns,stamp)
        store.save(launched='fixture.desktop');self.clock.return_value+=42;store.save(launched='fixture.desktop')
        self.assertEqual(store.value['items'],['fixture.desktop'])
        self.assertEqual(store.value['launched_at']['fixture.desktop'],self.clock.return_value)
        for days in (0,7):
            store=self.timed();self.clock.return_value=2000000+86400
            store.save(retention_days=days);self.assertEqual(store.value['items'],[])

    def test_count_disabled_recording_clear_and_old_backups(self):
        store=self.timed();old_backup=self.path.with_name('recent.json.backup-fixture');old_backup.write_bytes(b'older backup')
        for i in range(8):store.save(launched=f'{i}.desktop')
        store.save(limit=5);self.assertEqual(len(store.value['items']),5)
        self.assertEqual(set(store.value['launched_at']),set(store.value['items']))
        store.save(enabled=False);store.save(launched='private.desktop')
        self.assertEqual(store.value['items'],[]);self.assertEqual(store.value['launched_at'],{})
        store.save(enabled=True);store.save(launched='later.desktop');store.save(clear=True)
        self.assertEqual(store.value['launched_at'],{});self.assertEqual(store.value['retention_days'],1)
        self.assertEqual(list(self.path.parent.glob('recent.json.backup-*')),[old_backup])
        self.assertEqual(old_backup.read_bytes(),b'older backup')

    def test_clock_rollback_future_entries_and_invalid_clock(self):
        store=self.timed();self.clock.return_value-=1
        self.assertEqual(store.items(),[]);store.prune();self.assertEqual(store.value['launched_at'],{})
        store.save(launched='new.desktop');original=self.path.read_bytes()
        self.clock.return_value=float('nan')
        self.assertEqual(store.items(),[])
        with self.assertRaisesRegex(ValueError,'clock'):store.prune()
        self.assertEqual(self.path.read_bytes(),original)
        store.save(clear=True);self.assertEqual(store.value['items'],[])
        store.save(enabled=False);self.assertFalse(store.value['enabled'])
        store.save(retention_days=0);self.assertNotIn('launched_at',store.value)

    def test_invalid_options_records_and_timestamps_preserve_input(self):
        store=self.store()
        for days in (-1,366,True,1.5,'7'):
            with self.assertRaises(ValueError):store.save(retention_days=days)
            self.assertFalse(self.path.exists())
        valid={'enabled':True,'items':['x'],'retention_days':7,'launched_at':{'x':2000000}}
        records=[None,[],{'enabled':True,'items':['x'*4097]},dict(valid,retention_days=True),dict(valid,version=2)]
        records += [dict(valid,launched_at={'x':stamp}) for stamp in (True,-1,253402300800,'yesterday',float('nan'),float('inf'),None)]
        records += [dict(valid,launched_at=['bad']),dict(valid,launched_at={str(i):1 for i in range(51)})]
        for value in records:
            original=self.write(value);bad=self.store();self.assertIsNotNone(bad.error)
            with self.assertRaises(ValueError):bad.save(clear=True)
            self.assertEqual(self.path.read_bytes(),original)
        for raw in (b'{"enabled":true,"enabled":false,"items":[]}',b'x'*(menu.RECENT_LIMIT_BYTES+1)):
            self.path.write_bytes(raw);bad=self.store();self.assertIsNotNone(bad.error)
            with self.assertRaises(ValueError):bad.prune()
            self.assertEqual(self.path.read_bytes(),raw)

    def test_serialized_bound_cannot_write_an_unreadable_record(self):
        # Compact input is within the read bound; pretty output would exceed it.
        value={'enabled':True,'items':[],'opaque':list(range(15000))}
        raw=json.dumps(value,separators=(',',':')).encode();self.assertLess(len(raw),menu.RECENT_LIMIT_BYTES)
        self.path.write_bytes(raw);store=self.store();self.assertIsNone(store.error)
        with self.assertRaisesRegex(ValueError,'large'):store.save(retention_days=7)
        self.assertEqual(self.path.read_bytes(),raw)

    def test_failed_expiry_hides_old_entries_and_preserves_original_for_retry(self):
        store=self.timed();original=self.path.read_bytes();value=copy.deepcopy(store.value)
        self.clock.return_value+=86400
        with patch.object(menu.os,'replace',side_effect=OSError('fixture disk full')),self.assertRaises(OSError):store.prune()
        self.assertEqual(self.path.read_bytes(),original);self.assertEqual(store.original,original);self.assertEqual(store.value,value)
        self.assertEqual(store.items(),[]);self.assertEqual(list(self.path.parent.glob('.menu-*')),[])
        store.prune();self.assertEqual(self.store().value['items'],[])

    def test_external_history_edits_are_not_overwritten_by_expiry(self):
        store=self.timed();self.clock.return_value+=86400
        external=self.write({'enabled':False,'items':[]})
        with self.assertRaisesRegex(ValueError,'changed elsewhere'):store.prune()
        self.assertEqual(self.path.read_bytes(),external)

    def test_portable_policy_exports_without_history_or_times_and_restores_exactly(self):
        self.timed();store=portable.Store(self.home);original=self.path.read_bytes()
        value=store.export();blob=portable.encode(value)
        self.assertEqual(value['preferences']['recent']['retention_days'],1)
        for secret in (b'fixture.desktop',b'launched_at',b'2000000'):self.assertNotIn(secret,blob)
        value['preferences']['recent']['retention_days']=7
        changes=store.plan(value);self.assertEqual(self.path.read_bytes(),original)
        store.apply(changes);local=json.loads(self.path.read_text())
        self.assertEqual(local['launched_at'],{'fixture.desktop':2000000});self.assertEqual(local['items'],['fixture.desktop'])
        self.assertEqual(local['retention_days'],7)
        store.rollback();self.assertEqual(self.path.read_bytes(),original)

    def test_legacy_portable_import_retains_policy_and_rejects_history_fields(self):
        self.timed();store=portable.Store(self.home);value=store.export()
        value['preferences']['recent'].pop('retention_days')
        changes=store.plan(value)
        if 'recent.json' in changes:self.assertEqual(json.loads(changes['recent.json']['after'])['retention_days'],1)
        for field,entry in [('launched_at',{'secret':123}),('items',['secret']),('retention_days',True),('retention_days',366)]:
            invalid=copy.deepcopy(value);invalid['preferences']['recent'][field]=entry
            with self.assertRaises(ValueError):store.plan(invalid)

    def test_menu_age_actions_restore_check_on_conflict_and_show_failure(self):
        window=self.window();choices={a.data():a for a in window.recent_ages.actions()}
        self.assertTrue(choices[0].isChecked());choices[7].trigger()
        self.assertEqual(self.store().value['retention_days'],7)
        self.path.write_text('{"enabled":false,"items":[]}')
        with patch.object(window,'error') as error:choices[30].trigger();error.assert_called_once()
        self.assertTrue(choices[7].isChecked());self.assertFalse(choices[30].isChecked())
        window.recent=self.timed();self.clock.return_value+=86400
        with patch.object(menu.os,'replace',side_effect=OSError('fixture disk full')):window.expire_recent()
        self.assertFalse(window.recent_notice.isHidden());self.assertIn('could not be saved',window.recent_notice.text())
        self.assertEqual(window.recent.items(),[])
        window.expire_recent();self.assertTrue(window.recent_notice.isHidden())

    def test_resident_reopen_prunes_without_background_timer_or_window_rebuild(self):
        self.timed();server=Server();resident=menu.ResidentMenu(self.app,server)
        with patch.object(menu,'applications',return_value=[]):resident.toggle()
        window=resident.window
        self.addCleanup(lambda: shiboken6.delete(resident.window) if shiboken6.isValid(resident.window) else None)
        self.assertEqual(window.recent.items(),['fixture.desktop'])
        resident.toggle();original=self.path.read_bytes();self.clock.return_value+=86400
        self.app.processEvents();self.assertEqual(self.path.read_bytes(),original)
        resident.toggle();self.assertIs(resident.window,window)
        self.assertEqual(window.recent.value['items'],[])
        with patch.object(window.recent,'persist',side_effect=AssertionError('reopen rewrote history')):
            resident.toggle();resident.toggle();window.refresh();window.refresh()
        self.assertIs(resident.window,window)


if __name__=='__main__':unittest.main()
