"""Read-only app details with synthetic metadata; no personal catalog or clipboard."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import shiboken6
from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtGui import QAccessible, QContextMenuEvent
from PySide6.QtTest import QTest
from test_menu import menu
import test_start_keyboard as keyboard


def metadata(ident='fixture.desktop', name='Same & <label>'):
    app=Mock()
    app.get_id.return_value=ident;app.get_display_name.return_value=name
    app.get_description.return_value='Éditeur 日本語';app.get_filename.return_value='/fixture/'+ident
    app.list_actions.return_value=[]
    app.get_executable.side_effect=AssertionError('No Exec getter')
    app.get_commandline.side_effect=AssertionError('No command line getter')
    app.launch.side_effect=AssertionError('No launch');app.launch_action.side_effect=AssertionError('No task launch')
    return app


class PropertiesMetadataTests(unittest.TestCase):
    def test_unicode_controls_plain_text_bounds_and_no_file_probes(self):
        app=metadata();app.get_display_name.return_value='Éditeur & <b>日本語</b>\n\u202e'
        app.get_description.return_value='x'*10000
        with patch.object(Path,'stat',side_effect=AssertionError('No stat')),patch.object(Path,'read_bytes',side_effect=AssertionError('No file read')):
            fields,status=menu.application_properties(app,'fixture.desktop')
        self.assertEqual(fields['Display name'],'Éditeur & <b>日本語</b>\\u000A\\u202E')
        self.assertEqual(len(fields['Description']),4096+len('… [truncated]'))
        self.assertIn('not re-read',status);self.assertEqual(fields['Source desktop entry'],'/fixture/fixture.desktop')
        self.assertEqual(menu.property_text(None,20),'Not provided by GIO.')

    def test_missing_nonfile_relative_and_failed_metadata_are_honest(self):
        fields,status=menu.application_properties(None,'gone.desktop')
        self.assertEqual(fields['Desktop ID'],'gone.desktop');self.assertIn('no longer',status)
        app=metadata();app.get_filename.return_value='relative.desktop';app.get_id.return_value=None
        app.get_description.side_effect=RuntimeError('private error not displayed')
        fields,status=menu.application_properties(app,None)
        self.assertEqual(fields['Desktop ID'],'Not provided by GIO.')
        self.assertEqual(fields['Source desktop entry'],'Not provided by GIO.')
        self.assertNotIn('private error',status)
        app=Mock(spec=['get_display_name','get_id','get_description'])
        app.get_display_name.return_value='Non-file';app.get_id.return_value=None;app.get_description.return_value=None
        self.assertEqual(menu.application_properties(app,None)[0]['Source desktop entry'],'Not provided by GIO.')

    def test_real_gio_duplicate_names_deleted_file_and_keyfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);exe=root/'never-run';exe.write_text('#!/bin/sh\nexit 97\n');exe.chmod(0o755)
            text='[Desktop Entry]\nType=Application\nName=Same & 日本語\nComment=Fixture description\nExec='+str(exe)+'\n'
            apps=[]
            for name in ('one.desktop','two.desktop'):
                path=root/name;path.write_text(text);app=menu.Gio.DesktopAppInfo.new_from_filename(str(path));self.assertIsNotNone(app)
                path.unlink();apps.append(menu.application_properties(app,name)[0])
            self.assertEqual(apps[0]['Display name'],apps[1]['Display name'])
            self.assertNotEqual(apps[0]['Desktop ID'],apps[1]['Desktop ID'])
            self.assertNotEqual(apps[0]['Source desktop entry'],apps[1]['Source desktop entry'])
            key=menu.GLib.KeyFile();key.load_from_data(text,len(text.encode()),0)
            app=menu.Gio.DesktopAppInfo.new_from_keyfile(key)
            fields,_=menu.application_properties(app,None)
            self.assertEqual(fields['Source desktop entry'],'Not provided by GIO.')
            self.assertEqual(fields['Desktop ID'],'Not provided by GIO.')


class PropertiesUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):keyboard.StartKeyboardTests.setUpClass()
    def setUp(self):
        self.fixture=keyboard.StartKeyboardTests(methodName='runTest');self.fixture.setUp()
        self.window=self.fixture.window();self.app=self.fixture.app
        self.errors=[]
        import sys
        self.enterContext(patch.object(sys,'excepthook',side_effect=lambda *error:self.errors.append(error)))
        def cleanup():
            self.fixture.doCleanups();self.app.processEvents();self.assertEqual(self.errors,[])
        self.addCleanup(cleanup)
        for app in self.fixture.catalog:
            app.list_actions.return_value=[];app.get_filename.return_value=None

    def modal(self,inspect,invoke=None):
        checked=[]
        def visit():
            dialog=self.app.activeModalWidget()
            try:
                self.assertIsInstance(dialog,menu.ApplicationProperties)
                inspect(dialog);checked.append(True)
            except BaseException as error:self.errors.append(error)
            finally:
                if dialog is not None:dialog.reject()
        QTimer.singleShot(0,visit)
        (invoke or (lambda:self.window.show_application_properties('Alpha.desktop')))()
        self.assertEqual(checked,[True]);self.assertEqual(self.errors,[])

    def test_selectable_read_only_accessible_fields_and_focus_state(self):
        w=self.window;w.search.setText('Alpha');w.list.setCurrentRow(0);w.list.setFocus();self.app.processEvents()
        w.by_id['Alpha.desktop']=metadata('Alpha.desktop')
        before=(w.search.text(),w.category.currentText(),w.favorites.copy(),w.state.read_bytes(),w.list.currentRow())
        def inspect(dialog):
            self.assertFalse(w.column_navigation_allowed());self.assertFalse(w.isVisible())
            self.assertGreaterEqual(dialog.notice.height(),dialog.notice.heightForWidth(dialog.notice.width()))
            self.assertEqual(dialog.fields['Display name'].text(),'Same & <label>')
            for label,field in dialog.fields.items():
                self.assertTrue(field.isReadOnly())
                self.assertEqual(QAccessible.queryAccessibleInterface(field).text(QAccessible.Text.Name),label)
                field.setFocus();QTest.keyClick(field,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
                self.assertTrue(field.textCursor().hasSelection() if isinstance(field,menu.QPlainTextEdit) else field.hasSelectedText())
            QTest.keyClick(dialog,Qt.Key.Key_Escape)
        with patch.object(menu,'save_json',side_effect=AssertionError('No preference write')):
            self.modal(inspect)
        self.assertEqual((w.search.text(),w.category.currentText(),w.favorites,w.state.read_bytes(),w.list.currentRow()),before)
        self.assertTrue(w.list.hasFocus());self.assertTrue(w.isVisible());self.fixture.no_launch()

    def test_context_properties_before_pin_validation_and_stale_catalog(self):
        w=self.window;w.list.setCurrentRow(1);w.state_error='invalid pins'
        def choose(popup,position):
            w.by_id.pop('Beta.desktop')
            return next(a for a in popup.actions() if a.text()=='Properties…')
        class Popup(menu.QMenu):exec=choose
        def inspect(dialog):
            self.assertIn('no longer',dialog.notice.text())
            self.assertEqual(dialog.fields['Desktop ID'].text(),'Beta.desktop')
        with patch.object(menu,'QMenu',Popup),patch.object(w,'error',side_effect=AssertionError('Pin state must not block details')):
            self.modal(inspect,lambda:w.context_menu(w.list.visualItemRect(w.list.currentItem()).center()))

    def test_native_keyboard_context_event_uses_selected_row_not_event_position(self):
        w=self.window;w.list.setCurrentRow(2);w.list.setFocus();self.app.processEvents()
        for modifier in (Qt.KeyboardModifier.NoModifier,Qt.KeyboardModifier.ShiftModifier):
            visited=[]
            def inspect():
                dialog=self.app.activeModalWidget()
                try:
                    self.assertIsInstance(dialog,menu.ApplicationProperties)
                    self.assertEqual(dialog.fields['Desktop ID'].text(),'Gamma.desktop');visited.append(True)
                except BaseException as error:self.errors.append(error)
                finally:
                    if dialog:dialog.reject()
            def choose():
                popup=self.app.activePopupWidget()
                try:
                    self.assertIsInstance(popup,menu.QMenu)
                    self.assertFalse(w.column_navigation_allowed())
                    with patch.object(w,'context_menu') as nested:
                        self.app.sendEvent(w.list.viewport(),QContextMenuEvent(QContextMenuEvent.Reason.Keyboard,QPoint(),QPoint()))
                        nested.assert_not_called()
                    action=next(a for a in popup.actions() if a.text()=='Properties…')
                    popup.setActiveAction(action);QTimer.singleShot(0,inspect)
                    QTest.keyClick(popup,Qt.Key.Key_Return)
                except BaseException as error:
                    self.errors.append(error)
                    if popup and popup is not w:popup.close()
            QTimer.singleShot(0,choose)
            event=QContextMenuEvent(QContextMenuEvent.Reason.Keyboard,QPoint(),w.list.viewport().mapToGlobal(QPoint()),modifier)
            self.app.sendEvent(w.list.viewport(),event)
            self.assertEqual(visited,[True]);self.assertEqual(self.errors,[])
            self.assertTrue(w.list.hasFocus());self.assertEqual(w.list.currentRow(),2)

    def test_key_followed_by_native_context_event_opens_only_once(self):
        w=self.window;w.list.setCurrentRow(2);w.list.setFocus();self.app.processEvents()
        position=w.list.visualItemRect(w.list.currentItem()).center()
        opened=[]
        class Popup(menu.QMenu):
            def exec(self,position):opened.append(position);return None
        with patch.object(menu,'QMenu',Popup):
            self.fixture.key(w.list,Qt.Key.Key_Menu)
            event=QContextMenuEvent(QContextMenuEvent.Reason.Keyboard,position,w.list.viewport().mapToGlobal(position))
            self.app.sendEvent(w.list.viewport(),event)
        self.assertEqual(len(opened),1)
        class ChooseProperties(menu.QMenu):
            def exec(self,position):return next(a for a in self.actions() if a.text()=='Properties…')
        position=w.list.visualItemRect(w.list.item(1)).center()
        with patch.object(menu,'QMenu',ChooseProperties),patch.object(w,'show_application_properties') as show:
            self.app.sendEvent(w.list.viewport(),QContextMenuEvent(QContextMenuEvent.Reason.Mouse,position,w.list.viewport().mapToGlobal(position)))
            show.assert_called_once_with('Beta.desktop')

    def test_empty_disabled_modified_keys_drag_popup_and_modal_ownership(self):
        w=self.window
        def native():self.app.sendEvent(w.list.viewport(),QContextMenuEvent(QContextMenuEvent.Reason.Keyboard,QPoint(),QPoint()))
        with patch.object(w,'context_menu') as context:
            w.list.clear();native();context.assert_not_called()
            w.refresh();w.list.currentItem().setFlags(Qt.ItemFlag.NoItemFlags)
            native();context.assert_not_called()
            w.refresh();w.list.dragging=True
            native();context.assert_not_called();w.list.dragging=False
            self.fixture.key(w.search,Qt.Key.Key_F10,Qt.KeyboardModifier.ShiftModifier);context.assert_not_called()
        w.search.setText('missing');self.modal(lambda d:self.assertFalse(w.column_navigation_allowed()))
        self.assertTrue(w.search.hasFocus())

    def test_modal_failure_restores_lifetime_and_repeated_close(self):
        w=self.window;w.exit_on_hide=True;self.app.setQuitOnLastWindowClosed(True)
        with patch.object(menu,'ApplicationProperties',side_effect=RuntimeError('fixture constructor')):
            with self.assertRaises(RuntimeError):w.show_application_properties('Alpha.desktop')
        self.assertTrue(w.isVisible());self.assertTrue(w.exit_on_hide);self.assertTrue(self.app.quitOnLastWindowClosed())
        w.exit_on_hide=False;self.app.setQuitOnLastWindowClosed(False)
        for _ in range(3):self.modal(lambda d:d.buttons.button(menu.QDialogButtonBox.StandardButton.Close).click())
        self.fixture.no_launch()
