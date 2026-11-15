"""Widget-local column navigation; synthetic apps/folders, no real dispatch."""
import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPoint
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QLineEdit
import test_start_keyboard as keyboard


class StartColumnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): keyboard.StartKeyboardTests.setUpClass()
    def setUp(self):
        self.fixture = keyboard.StartKeyboardTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.menu = keyboard.menu; self.app = self.fixture.app
        self.window = self.fixture.window()
        self.addCleanup(self.fixture.no_launch)
    def key(self, widget, key, modifiers=None):
        self.fixture.key(widget, key, modifiers or self.menu.Qt.KeyboardModifier.NoModifier)
    def folder_buttons(self):
        return [b for b in self.window.findChildren(self.menu.QPushButton, 'folderLink') if b.isVisible()]
    def test_right_enters_places_left_restores_selected_result(self):
        w=self.window;w.list.setCurrentRow(2);w.list.setFocus();self.app.processEvents()
        self.key(w.list,self.menu.Qt.Key.Key_Right)
        self.assertIs(self.app.focusWidget(),self.folder_buttons()[0])
        self.key(self.app.focusWidget(),self.menu.Qt.Key.Key_Left)
        self.assertTrue(w.list.hasFocus());self.assertEqual(w.list.currentRow(),2)
    def test_options_session_and_arrow_are_return_targets_without_dispatch(self):
        w=self.window;controls=[w.edit_links_button,w.findChildren(self.menu.QPushButton,'menuControl')[1],w.session_button,w.power_arrow]
        w.session_button.setEnabled(True)
        for control in controls:
            with self.subTest(control=control.text()):
                control.setFocus();self.app.processEvents()
                self.key(control,self.menu.Qt.Key.Key_Left);self.assertTrue(w.list.hasFocus())
                self.key(w.list,self.menu.Qt.Key.Key_Right);self.assertIs(self.app.focusWidget(),control)
    def test_hidden_disabled_separators_and_no_usable_target(self):
        w=self.window;buttons=self.folder_buttons();buttons[0].setFocus();self.app.processEvents()
        self.key(buttons[0],self.menu.Qt.Key.Key_Left)
        buttons[0].hide();w.findChildren(self.menu.QToolButton,'folderBrowse')[0].setEnabled(False)
        self.key(w.list,self.menu.Qt.Key.Key_Right)
        self.assertIs(self.app.focusWidget(),buttons[1])
        self.key(buttons[1],self.menu.Qt.Key.Key_Left)
        panel=w.findChild(self.menu.QWidget,'placesPanel')
        for button in panel.findChildren(self.menu.QPushButton)+panel.findChildren(self.menu.QToolButton):button.setEnabled(False)
        self.key(w.list,self.menu.Qt.Key.Key_Right);self.assertTrue(w.list.hasFocus())
        for divider in w.findChildren(self.menu.QFrame,'folderSeparator'):
            self.assertEqual(divider.focusPolicy(),self.menu.Qt.FocusPolicy.NoFocus)
    def test_empty_and_disabled_results_return_to_search(self):
        w=self.window
        for empty in (False,True):
            if empty:w.search.setText('no-synthetic-match')
            else:
                for i in range(w.list.count()):w.list.item(i).setFlags(self.menu.Qt.ItemFlag.NoItemFlags)
            w.list.setFocus();self.key(w.list,self.menu.Qt.Key.Key_Right)
            right=self.app.focusWidget();self.assertIsNot(right,w.list)
            self.key(right,self.menu.Qt.Key.Key_Left);self.assertTrue(w.search.hasFocus())
    def test_rebuild_retains_folder_identity_and_removal_falls_back(self):
        w=self.window;target=self.folder_buttons()[1];label=target.text()
        target.setFocus();self.app.processEvents();w.refresh_folders();self.app.processEvents()
        self.assertEqual(self.app.focusWidget().text(),label)
        self.assertIsNot(self.app.focusWidget(),target)
        self.key(self.app.focusWidget(),self.menu.Qt.Key.Key_Left);self.assertTrue(w.list.hasFocus())
        self.key(w.list,self.menu.Qt.Key.Key_Right);self.assertEqual(self.app.focusWidget().text(),label)
        w.folder_settings.links=[row for row in w.folder_settings.links if row.get('label')!=label]
        w.refresh_folders();self.app.processEvents()
        self.assertIs(self.app.focusWidget(),self.folder_buttons()[0])
    def test_catalog_rebuild_keeps_places_focus_and_returns_to_usable_result(self):
        w=self.window;w.list.setCurrentRow(2);w.edit_links_button.setFocus();self.app.processEvents()
        self.fixture.catalog_provider.return_value=[self.fixture.catalog[1]]
        w.refresh_catalog();self.app.processEvents();self.assertTrue(w.edit_links_button.hasFocus())
        self.key(w.edit_links_button,self.menu.Qt.Key.Key_Left);self.assertTrue(w.list.hasFocus())
        self.assertEqual(self.fixture.current_id(w),'Beta.desktop')
        self.fixture.catalog_provider.return_value=[];w.power_arrow.setFocus();w.refresh_catalog()
        self.key(w.power_arrow,self.menu.Qt.Key.Key_Left);self.assertTrue(w.search.hasFocus())
    def test_duplicate_folder_roles_reordering_and_scroll_reveal(self):
        w=self.window;folder=self.fixture.home/'folder';folder.mkdir()
        link={'label':'Duplicate','path':str(folder),'visible':True}
        w.folder_settings.links=[link.copy(),{'type':'separator'},link.copy()]
        w.refresh_folders();self.app.processEvents()
        browsers=[b for b in w.findChildren(self.menu.QToolButton,'folderBrowse') if b.isVisible()]
        browsers[1].setFocus();self.app.processEvents();self.key(browsers[1],self.menu.Qt.Key.Key_Left)
        w.folder_settings.links.insert(0,{'label':'Before','path':str(folder),'visible':True})
        w.refresh_folders();self.app.processEvents();self.assertTrue(w.list.hasFocus())
        self.key(w.list,self.menu.Qt.Key.Key_Right)
        current=[b for b in w.findChildren(self.menu.QToolButton,'folderBrowse') if b.isVisible()]
        self.assertIs(self.app.focusWidget(),current[2])
        for i in range(30):w.folder_settings.links.append({'label':f'Fixture {i}','path':str(folder),'visible':True})
        w.refresh_folders();self.app.processEvents()
        last=next(button for button in self.folder_buttons() if button.text()=='Fixture 29')
        last.setFocus();self.app.processEvents()
        self.key(last,self.menu.Qt.Key.Key_Left);w.places_area.verticalScrollBar().setValue(0)
        self.key(w.list,self.menu.Qt.Key.Key_Right)
        self.assertIs(self.app.focusWidget(),last);self.assertGreater(w.places_area.verticalScrollBar().value(),0)
    def test_search_modifiers_tab_and_reopens_preserve_existing_behavior(self):
        w=self.window;w.search.setText('Alpha Beta');w.search.setCursorPosition(5);w.search.setFocus()
        self.key(w.search,self.menu.Qt.Key.Key_Left);self.assertEqual(w.search.cursorPosition(),4)
        self.key(w.search,self.menu.Qt.Key.Key_Right,self.menu.Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(w.search.selectedText(),'a');self.assertTrue(w.search.hasFocus())
        w.search.clear();self.key(w.search,self.menu.Qt.Key.Key_Tab);self.assertTrue(w.list.hasFocus())
        self.key(w.list,self.menu.Qt.Key.Key_Right,self.menu.Qt.KeyboardModifier.ControlModifier);self.assertTrue(w.list.hasFocus())
        self.key(w.list,self.menu.Qt.Key.Key_Tab);self.assertTrue(w.programs.hasFocus())
        self.key(w.programs,self.menu.Qt.Key.Key_Backtab);self.assertTrue(w.list.hasFocus())
        for _ in range(3):
            self.key(w.list,self.menu.Qt.Key.Key_Right);self.assertIsNot(self.app.focusWidget(),w.list)
            self.key(self.app.focusWidget(),self.menu.Qt.Key.Key_Left);self.assertTrue(w.list.hasFocus())
            w.hide();w.show();self.app.processEvents();w.list.setFocus()
    def test_modal_popup_and_drag_ownership_block_column_handling(self):
        w=self.window;w.list.setFocus();w.list.dragging=True
        self.key(w.list,self.menu.Qt.Key.Key_Right);self.assertTrue(w.list.hasFocus());w.list.dragging=False
        dialog=QDialog(w);edit=QLineEdit(dialog);dialog.setModal(True);dialog.show();edit.setFocus();self.app.processEvents()
        try:
            with patch.object(w,'focus_results') as focus:
                self.key(w.power_arrow,self.menu.Qt.Key.Key_Left);focus.assert_not_called()
            self.assertTrue(dialog.isVisible());self.assertIs(self.app.activeModalWidget(),dialog)
        finally:dialog.close();dialog.deleteLater();self.app.processEvents()
        w.show();w.list.setFocus();popup=w.power_menu;popup.popup(w.mapToGlobal(QPoint(10,20)));self.app.processEvents()
        try:
            with patch.object(w,'focus_results') as focus:
                self.key(w.power_arrow,self.menu.Qt.Key.Key_Left);focus.assert_not_called()
            self.assertTrue(popup.isVisible())
        finally:popup.hide();self.app.processEvents()
        w.hide();other=QLineEdit();other.show();other.activateWindow();other.setFocus();self.app.processEvents()
        try:
            w.refresh_folders();self.key(w.list,self.menu.Qt.Key.Key_Right)
            self.assertFalse(w.isVisible());self.assertTrue(other.hasFocus())
        finally:other.close();other.deleteLater()
    def test_native_folder_submenu_right_left_escape_and_accessible_names(self):
        w=self.window;folder=self.fixture.home/'fixture folder';(folder/'child').mkdir(parents=True)
        (folder/'child/item.txt').write_text('fixture')
        w.folder_settings.links=[{'label':'Fixture','path':str(folder),'visible':True}]
        w.refresh_folders();self.app.processEvents()
        browse=next(b for b in w.findChildren(self.menu.QToolButton,'folderBrowse') if b.isVisible());cascade=browse.menu()
        cascade.popup(w.mapToGlobal(QPoint(10,20)))
        end=time.monotonic()+3
        while not cascade.submenus and time.monotonic()<end:QTest.qWait(10)
        self.assertTrue(cascade.submenus);child=cascade.submenus[0]
        cascade.setActiveAction(next(a for a in cascade.actions() if a.menu() is child))
        self.key(cascade,self.menu.Qt.Key.Key_Right);self.assertTrue(child.isVisible())
        self.key(child,self.menu.Qt.Key.Key_Left);self.assertFalse(child.isVisible());self.assertTrue(cascade.isVisible())
        self.key(cascade,self.menu.Qt.Key.Key_Escape);self.assertFalse(cascade.isVisible());self.assertTrue(w.isVisible())
        panel=w.findChild(self.menu.QWidget,'placesPanel')
        for button in panel.findChildren(self.menu.QPushButton)+panel.findChildren(self.menu.QToolButton):
            if button.isVisible() and button.isEnabled():
                self.assertTrue(QAccessible.queryAccessibleInterface(button).text(QAccessible.Text.Name),button.objectName())
