import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import portable_settings as ps


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=ps.Store(self.temp.name);self.store.base.mkdir(parents=True)
    def write(self,name,value):
        (self.store.base/name).write_bytes(ps.encode(value))
    def test_export_excludes_private_fields_and_import_preserves_them(self):
        folders={'version':1,'folders':[{'label':'Private medical','path':'/private/medical','visible':True},{'label':'My docs','standard':'DocumentsLocation','visible':True}], 'portrait':'/private/portrait.png','portraitCrop':{'x':.7,'y':.5,'zoom':2},'hiddenSystemLinks':['computer']}
        self.write('folders.json',folders);self.write('recent.json',{'enabled':True,'limit':20,'items':['private.desktop']})
        value=self.store.export();blob=ps.encode(value)
        for secret in [b'private',b'medical',b'portrait',b'My docs']:self.assertNotIn(secret,blob)
        value['preferences']['primary']='lockscreen';value['preferences']['folders'][0]['visible']=False
        before={p.name:p.read_bytes() for p in self.store.base.iterdir()}
        self.store.apply(self.store.plan(value))
        after=ps.decode((self.store.base/'folders.json').read_bytes())
        self.assertEqual(after['portraitCrop'],folders['portraitCrop']);self.assertEqual(after['portrait'],folders['portrait']);self.assertEqual(after['folders'][0],folders['folders'][0])
        self.assertEqual(ps.decode((self.store.base/'recent.json').read_bytes())['items'],['private.desktop'])
        self.store.rollback()
        for name,data in before.items():self.assertEqual((self.store.base/name).read_bytes(),data)
        self.assertFalse((self.store.base/'session-button.json').exists())
    def test_invalid_schema_bounds_duplicate_keys_and_links(self):
        value=self.store.export();value['preferences']['path']='/etc/passwd'
        with self.assertRaises(ValueError):ps.validate(value)
        with self.assertRaises(ValueError):ps.decode(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):ps.decode(b' '* (ps.LIMIT+1))
        (self.store.base/'recent.json').symlink_to(self.store.base/'missing')
        with self.assertRaises(ValueError):self.store.export()
    def test_preview_is_read_only_and_conflict_safe(self):
        value=self.store.export();changes=self.store.plan(value)
        self.assertFalse((self.store.base/'session-button.json').exists())
        self.write('session-button.json',{'version':1,'action':'logout'})
        with self.assertRaises(ValueError):self.store.apply(changes)
        self.assertFalse(self.store.undo.exists())
    def test_rollback_refuses_later_edits_before_touching_any_files(self):
        self.store.apply(self.store.plan(self.store.export()))
        self.write('recent.json',{'enabled':False,'items':[]})
        before=(self.store.base/'session-button.json').read_bytes()
        with self.assertRaises(ValueError):self.store.rollback()
        self.assertEqual((self.store.base/'session-button.json').read_bytes(),before)
    def test_failed_write_restores_prior_written_files(self):
        plan=self.store.plan(self.store.export());atomic=self.store.atomic
        def failing(path,data):
            if path.name=='recent.json':raise OSError('simulated full disk')
            atomic(path,data)
        with patch.object(self.store,'atomic',side_effect=failing),self.assertRaises(OSError):self.store.apply(plan)
        self.assertFalse((self.store.base/'session-button.json').exists())
    def test_history_is_never_silently_truncated(self):
        self.write('recent.json',{'enabled':True,'items':['one','two'],'limit':20})
        value=self.store.export();value['preferences']['recent']['limit']=1
        with self.assertRaises(ValueError):self.store.plan(value)
        self.assertEqual(ps.decode((self.store.base/'recent.json').read_bytes())['items'],['one','two'])
    def test_fresh_roundtrip_and_repeated_plan(self):
        value=self.store.export();self.store.apply(self.store.plan(value))
        self.assertEqual(self.store.export(),value);self.assertEqual(self.store.plan(value),{})

    def test_empty_folders_remain_hidden_and_duplicates_refused(self):
        self.write('folders.json',{'version':1,'folders':[]})
        self.assertTrue(all(not x['visible'] for x in self.store.export()['preferences']['folders']))
        links=[{'label':label,'standard':'HomeLocation','visible':True} for label in ['First','Second']]
        self.write('folders.json',{'version':1,'folders':links})
        with self.assertRaises(ValueError):self.store.export()
    def test_large_local_fields_have_readable_exact_rollback(self):
        self.write('session-button.json',{'version':1,'action':'shutdown','opaque':'x'*60000})
        before=(self.store.base/'session-button.json').read_bytes()
        value=self.store.export();value['preferences']['primary']='lockscreen'
        self.store.apply(self.store.plan(value));self.store.rollback()
        self.assertEqual((self.store.base/'session-button.json').read_bytes(),before)
    def test_failed_rollback_compensates_and_can_be_retried(self):
        self.store.apply(self.store.plan(self.store.export()))
        before={name:(self.store.base/name).read_bytes() for name in ps.FILES}
        real=self.store.write_or_remove
        def fail(path,data):
            if path.name=='recent.json' and data is None:raise OSError('simulated rollback failure')
            real(path,data)
        with patch.object(self.store,'write_or_remove',side_effect=fail),self.assertRaises(OSError):self.store.rollback()
        for name,data in before.items():self.assertEqual((self.store.base/name).read_bytes(),data)
        self.store.rollback();self.assertTrue(all(not (self.store.base/name).exists() for name in ps.FILES))
    def test_failed_import_keeps_previous_undo(self):
        self.store.apply(self.store.plan(self.store.export()));prior=self.store.undo.read_bytes()
        value=self.store.export();value['preferences']['primary']='lockscreen';plan=self.store.plan(value)
        real=self.store.atomic
        def fail(path,data):
            if path.name=='session-button.json':raise OSError('full disk')
            real(path,data)
        with patch.object(self.store,'atomic',side_effect=fail),self.assertRaises(OSError):self.store.apply(plan)
        self.assertEqual(self.store.undo.read_bytes(),prior)
    def test_invalid_local_known_fields_are_preserved(self):
        for value in [{'version':2,'action':'shutdown'}, {'version':1,'action':[]}]:
            self.write('session-button.json',value)
            with self.assertRaises(ValueError):self.store.export()
            self.assertEqual(ps.decode((self.store.base/'session-button.json').read_bytes()),value)

    def test_resulting_folder_count_and_encoded_size_are_bounded(self):
        value=self.store.export()
        links=[{'label':str(i),'path':'/private/'+str(i),'visible':True} for i in range(100)]
        self.write('folders.json',{'version':1,'folders':links})
        with self.assertRaises(ValueError):self.store.plan(value)
        (self.store.base/'folders.json').unlink()
        import json
        (self.store.base/'session-button.json').write_bytes(json.dumps({'version':1,'action':'shutdown','opaque':'字'*30000},ensure_ascii=False).encode())
        value=self.store.export();value['preferences']['primary']='lockscreen'
        with self.assertRaises(ValueError):self.store.plan(value)
        self.assertFalse(self.store.undo.exists())
