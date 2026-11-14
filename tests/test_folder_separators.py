"""Separator editor/rendering and path-free imports; disposable data/fake dispatch."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from PySide6.QtTest import QTest
from PySide6.QtCore import QPoint
import portable_settings as ps
import test_start_keyboard as keyboard
from test_menu import menu

SEP = {'type': 'separator'}

class SeparatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): keyboard.StartKeyboardTests.setUpClass()
    def setUp(self):
        self.fixture = keyboard.StartKeyboardTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.home = self.fixture.home
        self.store = ps.Store(self.home, self.home/'config')
        self.path = self.store.base/'folders.json'
        self.settings = menu.FolderSettings(self.path)
    def editor(self):
        editor = menu.FolderEditor(self.settings); self.fixture.windows.append(editor)
        editor.show(); self.fixture.app.processEvents(); return editor
    def save(self, links):
        self.settings.save(copy.deepcopy(links))
    def write(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True); self.path.write_bytes(ps.encode(value))
    def window(self, links):
        self.settings.save(copy.deepcopy(links), hidden=[label for group in menu.SYSTEM_GROUPS for label, _ in group])
        return self.fixture.window()
    def widgets(self, window):
        return [window.folder_layout.itemAt(i).widget() for i in range(window.folder_layout.count()) if window.folder_layout.itemAt(i).widget()]
    def snapshots(self):
        return {p.name: p.read_bytes() for p in self.store.base.iterdir() if p.is_file()} if self.store.base.exists() else {}

    def test_editor_add_move_remove_save_reopen_keeps_folder_data(self):
        links = menu.default_links(); links[0]['label'] = 'My home'
        links[1]['visible'] = False; links[0]['extra'] = 'preserved'
        self.save(links); before = self.path.read_bytes(); editor = self.editor()
        QTest.mouseClick(editor.buttons['Add separator'], menu.Qt.MouseButton.LeftButton)
        for _ in range(5): editor.buttons['Move up'].click()
        self.assertEqual(editor.values(), links[:1]+[SEP]+links[1:])
        editor.buttons['Move down'].click(); editor.buttons['Move up'].click()
        editor.save(); self.assertEqual(editor.result(), menu.QDialog.DialogCode.Accepted)
        self.assertEqual(menu.FolderSettings(self.path).links, links[:1]+[SEP]+links[1:])
        self.assertEqual(json.loads(self.path.read_bytes())['version'], 2)
        self.assertIn(before, [p.read_bytes() for p in self.path.parent.glob('folders.json.backup-*')])
        self.settings = menu.FolderSettings(self.path); reopened = self.editor()
        reopened.table.selectRow(1); reopened.buttons['Remove'].click(); reopened.save()
        self.assertEqual(menu.FolderSettings(self.path).links, links)
        self.assertEqual(json.loads(self.path.read_bytes())['version'], 1)

    def test_separator_editor_no_rename_visibility_destination_or_cancel_write(self):
        self.save([SEP]); before = self.path.read_bytes(); editor = self.editor()
        self.assertFalse(editor.table.item(0, 0).flags() & menu.Qt.ItemFlag.ItemIsEditable)
        self.assertFalse(editor.table.item(0, 2).flags() & menu.Qt.ItemFlag.ItemIsUserCheckable)
        self.assertFalse(editor.buttons['Change folder…'].isEnabled())
        with patch.object(menu.QFileDialog, 'getExistingDirectory') as choose:
            editor.change_folder(); choose.assert_not_called()
        editor.buttons['Add separator'].click(); QTest.keyClick(editor, menu.Qt.Key.Key_Escape)
        self.assertEqual(self.path.read_bytes(), before)
        reopened = self.editor(); reopened.buttons['Remove'].click(); reopened.save()
        self.assertEqual(menu.FolderSettings(self.path).links, [])

    def test_legacy_default_and_custom_rows_are_not_automatically_migrated(self):
        self.assertFalse(self.path.exists()); self.assertEqual(self.settings.links, menu.default_links())
        links = menu.default_links()+[{'label':'Fixture','path':str(self.home/'folder'),'visible':True,'opaque':'keep'}]
        self.save(links); before = self.path.read_bytes(); self.settings = menu.FolderSettings(self.path)
        self.assertEqual(json.loads(before)['version'], 1); self.settings.save(links)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(list(self.path.parent.glob('folders.json.backup-*')))
        editor = self.editor(); self.assertEqual(self.path.read_bytes(), before); editor.save()
        self.assertEqual(json.loads(self.path.read_bytes()), json.loads(before))
        # Qt table mappings may reorder JSON keys; the existing editor keeps exact backup bytes.
        for backup in self.path.parent.glob('folders.json.backup-*'): self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(self.store.export()['version'], 2)

    def test_invalid_local_separator_schema_is_preserved_and_editor_save_disabled(self):
        invalid = [dict(SEP, path='/private'), dict(SEP, visible=True), {'type':'command'}, {'type':[]}, {}]
        for item in invalid:
            for version in (1, 2):
                with self.subTest(item=item, version=version):
                    self.write({'version':version,'folders':[item]}); before=self.path.read_bytes()
                    self.settings=menu.FolderSettings(self.path); self.assertIsNotNone(self.settings.error)
                    with self.assertRaises(ValueError): self.settings.save([])
                    editor=self.editor(); self.assertFalse(editor.actions.button(menu.QDialogButtonBox.StandardButton.Save).isEnabled())
                    self.assertEqual(self.path.read_bytes(),before)
        for version in (True, 3, '2'):
            with self.assertRaises(ValueError): menu.validate_links({'version':version,'folders':[]})
        with self.assertRaises(ValueError): menu.validate_links({'version':1,'folders':[SEP]})

    def test_failed_save_and_external_edit_preserved_with_retry(self):
        self.save(menu.default_links()); before=self.path.read_bytes(); editor=self.editor(); editor.add_separator()
        with patch.object(Path,'replace',side_effect=OSError('fixture full disk')): editor.save()
        self.assertIn('fixture full disk',editor.notice.text()); self.assertNotEqual(editor.result(),menu.QDialog.DialogCode.Accepted)
        self.assertEqual(self.path.read_bytes(),before); self.assertEqual(self.settings.links,menu.default_links())
        self.assertFalse(list(self.path.parent.glob('.folders-*')))
        editor.save(); self.assertEqual(menu.FolderSettings(self.path).links[-1],SEP)
        other=self.editor(); changed=self.path.read_bytes()+b' '; self.path.write_bytes(changed)
        other.add_separator(); other.save(); self.assertIn('changed elsewhere',other.notice.text()); self.assertEqual(self.path.read_bytes(),changed)

    def test_render_edges_consecutive_hidden_rows_and_refresh_preserve_stored_items(self):
        home,docs,downloads=menu.default_links()[:3]; docs['visible']=False
        links=[SEP,SEP,home,SEP,docs,SEP,SEP,downloads,SEP]
        window=self.window(links); before=self.path.read_bytes()
        for _ in range(3):
            widgets=self.widgets(window); self.assertEqual(len(widgets),3)
            self.assertEqual(widgets[1].objectName(),'folderSeparator')
            self.assertEqual([w.findChild(menu.QPushButton,'folderLink').text() for w in (widgets[0],widgets[2])],['Home','Downloads'])
            self.assertEqual(set(window.folder_paths),{'Home','Downloads'})
            window.refresh_folders(); self.fixture.app.processEvents()
        self.assertEqual(self.path.read_bytes(),before); self.fixture.no_launch()

    def test_only_separators_empty_and_all_hidden_have_no_lines(self):
        hidden=menu.default_links()[0];hidden['visible']=False
        for links in ([],[SEP],[SEP,SEP],[SEP,hidden,SEP]):
            window=self.window(links);self.assertEqual(self.widgets(window),[]);self.assertEqual(window.folder_paths,{})
            self.assertEqual(menu.FolderSettings(self.path).links,links);window.close()

    def test_tab_skips_separator_and_nested_browse_still_works(self):
        folder=self.home/'fixture folder';(folder/'child').mkdir(parents=True);(folder/'child'/'item.txt').write_text('fixture')
        links=[menu.default_links()[0],SEP,{'label':'Fixture','path':str(folder),'visible':True}]
        window=self.window(links); widgets=self.widgets(window); divider=widgets[1]
        self.assertEqual(divider.focusPolicy(),menu.Qt.FocusPolicy.NoFocus)
        self.assertTrue(divider.testAttribute(menu.Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        self.assertEqual(divider.actions(),[]); window.search.setFocus();visited=set()
        for _ in range(80):
            focus=self.fixture.app.focusWidget();visited.add(focus);self.fixture.key(focus,menu.Qt.Key.Key_Tab)
            if window.search.hasFocus():break
        else:self.fail('Tab did not return to search')
        self.assertNotIn(divider,visited)
        browse=widgets[2].findChild(menu.QToolButton,'folderBrowse');self.assertIn(browse,visited)
        cascade=browse.menu();cascade.popup(window.mapToGlobal(QPoint(10,20)))
        for _ in range(100):
            if cascade.submenus:break
            QTest.qWait(10)
        self.assertTrue(cascade.submenus)
        action=next(a for a in cascade.actions() if a.menu());cascade.setActiveAction(action)
        self.fixture.key(cascade,menu.Qt.Key.Key_Right);child=action.menu()
        self.assertTrue(child.isVisible()); self.fixture.key(child,menu.Qt.Key.Key_Escape)
        self.fixture.key(cascade,menu.Qt.Key.Key_Escape); self.assertTrue(window.isVisible());self.fixture.no_launch()

    def test_portable_export_projects_separators_without_private_data(self):
        links=[SEP,menu.default_links()[1],{'label':'secret label','path':'/private/secret','visible':True},SEP,menu.default_links()[0],SEP]
        self.save(links);value=self.store.export();blob=ps.encode(value)
        for secret in (b'secret',b'private',b'label',b'path',b'icon'):self.assertNotIn(secret,blob)
        items=value['preferences']['folders'];self.assertEqual(value['version'],2)
        self.assertEqual(items[:5],[SEP,{'standard':'DocumentsLocation','visible':True},SEP,{'standard':'HomeLocation','visible':True},SEP])
        self.assertEqual(sum(item==SEP for item in items),3);self.assertEqual(len(items),9)
        self.assertEqual(self.path.read_bytes(),self.settings.original)

    def test_portable_import_preserves_customs_idempotence_and_exact_undo(self):
        private={'label':'Private label','path':'/private/fixture','visible':True,'extra':'keep'}
        self.settings.save([private,menu.default_links()[0],SEP,menu.default_links()[1]],hidden=['Games'],portrait='/private/picture')
        before=self.path.read_bytes();value=self.store.export();value['preferences']['folders'].insert(0,copy.deepcopy(SEP))
        plan=self.store.plan(value);self.assertEqual(self.path.read_bytes(),before)
        self.store.apply(plan);after=json.loads(self.path.read_bytes())
        self.assertEqual(after['folders'][0],private);self.assertEqual(after['portrait'],'/private/picture');self.assertEqual(after['hiddenSystemLinks'],['Games'])
        self.assertEqual(sum(item==SEP for item in after['folders']),2)
        self.assertEqual(self.store.export(),value);self.assertEqual(self.store.plan(value),{})
        self.store.rollback();self.assertEqual(self.path.read_bytes(),before)

    def test_legacy_portable_import_preserves_separators_new_import_can_remove(self):
        self.save([menu.default_links()[0],SEP,menu.default_links()[1]])
        value=self.store.export();value['preferences']['folders']=[x for x in value['preferences']['folders'] if x!=SEP];value['version']=1
        self.store.apply(self.store.plan(value));self.assertIn(SEP,json.loads(self.path.read_bytes())['folders'])
        value['version']=2;self.store.apply(self.store.plan(value))
        local=json.loads(self.path.read_bytes());self.assertNotIn(SEP,local['folders']);self.assertEqual(local['version'],1)

    def test_malformed_portable_import_refuses_before_any_writes(self):
        self.save([menu.default_links()[0],SEP]);value=self.store.export();before=self.snapshots()
        mutations=[lambda v:v.update(version=True),lambda v:v.update(version=3),lambda v:v.update(version=1),
                   lambda v:v['preferences']['folders'].append(dict(SEP,path='/private')),
                   lambda v:v['preferences']['folders'].append(dict(SEP,label='secret')),
                   lambda v:v['preferences']['folders'].append({'type':'command'}),
                   lambda v:v['preferences']['folders'].pop(0),
                   lambda v:v['preferences']['folders'].extend([SEP]*107),
                   lambda v:v['preferences']['folders'].append({'standard':'HomeLocation','visible':True})]
        for mutate in mutations:
            candidate=copy.deepcopy(value);mutate(candidate)
            with self.assertRaises(ValueError):self.store.plan(candidate)
            self.assertEqual(self.snapshots(),before)
        with self.assertRaises(ValueError):ps.decode(b'{"version":2,"version":1}')

    def test_portable_failed_save_stale_preview_and_rollback_conflict(self):
        self.save(menu.default_links());before=self.path.read_bytes();value=self.store.export();value['preferences']['folders'].insert(1,copy.deepcopy(SEP));plan=self.store.plan(value)
        atomic=self.store.atomic
        def fail(path,data):
            if path.name=='folders.json':raise OSError('fixture disk failure')
            atomic(path,data)
        with patch.object(self.store,'atomic',side_effect=fail),self.assertRaises(OSError):self.store.apply(plan)
        self.assertEqual(self.path.read_bytes(),before);self.assertFalse(self.store.undo.exists());self.assertFalse((self.store.base/'session-button.json').exists())
        self.path.write_bytes(before+b' ')
        with self.assertRaises(ValueError):self.store.apply(plan)
        self.assertEqual(self.path.read_bytes(),before+b' ')
        self.store.apply(self.store.plan(value));changed=self.path.read_bytes()+b' ';self.path.write_bytes(changed)
        snapshot=self.snapshots()
        with self.assertRaises(ValueError):self.store.rollback()
        self.assertEqual(self.snapshots(),snapshot)

    def test_local_and_portable_size_boundaries(self):
        self.save([SEP]*100);before=self.path.read_bytes()
        with self.assertRaises(ValueError):self.settings.save([SEP]*101)
        self.assertEqual(self.path.read_bytes(),before)
        value=self.store.export();self.assertEqual(len(value['preferences']['folders']),106)
        self.store.apply(self.store.plan(value));self.assertEqual(menu.FolderSettings(self.path).links,[SEP]*100)
        empty=ps.Store(self.home/'other')
        with self.assertRaises(ValueError):empty.plan(value) # Existing default standard slots would exceed the local bound.
        self.assertFalse(empty.base.exists())

if __name__=='__main__': unittest.main()
