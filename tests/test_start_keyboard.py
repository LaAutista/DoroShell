"""Widget-local keys with synthetic apps/fake dispatch; no personal X11/input."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import shiboken6
from PySide6.QtCore import QObject, Signal, QPoint
from PySide6.QtTest import QTest
from test_menu import menu
from test_app_search import app as fake_app

class Server(QObject):
    newConnection=Signal()

class StartKeyboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=menu.QApplication.instance() or menu.QApplication([])
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.home=Path(tmp.name)
        self.enterContext(patch.dict(os.environ,{'HOME':str(self.home),'XDG_CONFIG_HOME':str(self.home/'config'),'XDG_DATA_HOME':str(self.home/'data')},clear=True))
        self.catalog=[]
        for name in ('Alpha','Beta','Gamma','Delta','Omega'):
            app=fake_app(name);app.get_categories.return_value='Utility;';app.get_icon.return_value=None
            app.get_filename.return_value=None;app.launch.return_value=True;self.catalog.append(app)
        self.catalog_provider=self.enterContext(patch.object(menu,'applications',return_value=self.catalog))
        self.enterContext(patch.object(menu,'desktop_entry',return_value=None))
        self.session=self.enterContext(patch.object(menu.StartMenu,'session_action'))
        self.uri=self.enterContext(patch.object(menu.Gio.AppInfo,'launch_default_for_uri',side_effect=AssertionError('No real URI launch')))
        self.windows=[];self.addCleanup(self.cleanup_windows)
    def cleanup_windows(self):
        for window in reversed(self.windows):
            if shiboken6.isValid(window):window.close();shiboken6.delete(window)
        self.session.assert_not_called();self.uri.assert_not_called()
    def window(self):
        window=menu.StartMenu();self.windows.append(window)
        window.category.setCurrentText('All applications');window.show();window.activateWindow();self.app.processEvents()
        window.search.setFocus();self.app.processEvents();return window
    def key(self,widget,key,modifiers=menu.Qt.KeyboardModifier.NoModifier):
        QTest.keyClick(widget,key,modifiers);self.app.processEvents()
    def current_id(self,window):
        item=window.list.currentItem();return item.data(menu.Qt.ItemDataRole.UserRole) if item else None
    def no_launch(self):
        for app in self.catalog:app.launch.assert_not_called()

    def test_search_arrows_and_result_boundaries_preserve_modified_keys(self):
        window=self.window();self.key(window.search,menu.Qt.Key.Key_Up)
        self.assertTrue(window.list.hasFocus());self.assertEqual(self.current_id(window),'Omega.desktop')
        self.key(window.list,menu.Qt.Key.Key_Down);self.assertTrue(window.search.hasFocus())
        self.key(window.search,menu.Qt.Key.Key_Down);self.assertTrue(window.list.hasFocus())
        self.assertEqual(self.current_id(window),'Omega.desktop')
        window.list.setCurrentRow(0)
        self.key(window.list,menu.Qt.Key.Key_Up,menu.Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(window.list.hasFocus())
        self.key(window.list,menu.Qt.Key.Key_Up);self.assertTrue(window.search.hasFocus())
        self.key(window.search,menu.Qt.Key.Key_Up,menu.Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(window.search.hasFocus());self.no_launch()

    def test_home_end_and_arrows_skip_disabled_hidden_rows(self):
        window=self.window()
        for row in (0,4):window.list.item(row).setFlags(window.list.item(row).flags() & ~menu.Qt.ItemFlag.ItemIsEnabled)
        window.list.item(2).setHidden(True);window.list.setFocus();window.list.setCurrentRow(3);self.app.processEvents()
        self.key(window.list,menu.Qt.Key.Key_Home);self.assertEqual(window.list.currentRow(),1)
        self.key(window.list,menu.Qt.Key.Key_Down);self.assertEqual(window.list.currentRow(),3)
        self.key(window.list,menu.Qt.Key.Key_Up);self.assertEqual(window.list.currentRow(),1)
        self.key(window.list,menu.Qt.Key.Key_End);self.assertEqual(window.list.currentRow(),3)
        self.key(window.list,menu.Qt.Key.Key_Down);self.assertTrue(window.search.hasFocus())
        self.key(window.search,menu.Qt.Key.Key_Up);self.assertEqual(window.list.currentRow(),3);self.no_launch()

    def test_empty_disabled_and_nonselectable_results_do_not_activate_or_trap_search(self):
        window=self.window()
        for row in range(window.list.count()):window.list.item(row).setFlags(window.list.item(row).flags() & ~menu.Qt.ItemFlag.ItemIsEnabled)
        for key in (menu.Qt.Key.Key_Down,menu.Qt.Key.Key_Up,menu.Qt.Key.Key_Return):
            self.key(window.search,key);self.assertTrue(window.search.hasFocus())
        window.list.setFocus();self.key(window.list,menu.Qt.Key.Key_Down);self.assertTrue(window.search.hasFocus())
        item=window.list.item(0);item.setFlags((item.flags() | menu.Qt.ItemFlag.ItemIsEnabled) & ~menu.Qt.ItemFlag.ItemIsSelectable)
        window.launch_item(item);self.assertFalse(window.launching)
        window.search.setText('no-such-fixture');self.assertEqual(window.list.count(),0)
        for key in (menu.Qt.Key.Key_Up,menu.Qt.Key.Key_Down,menu.Qt.Key.Key_Return):self.key(window.search,key)
        self.assertTrue(window.search.hasFocus());self.assertTrue(window.isVisible());self.no_launch()

    def test_search_home_end_left_right_and_selection_remain_text_editing(self):
        window=self.window();window.search.setText('Alpha Beta');window.search.setCursorPosition(5)
        self.key(window.search,menu.Qt.Key.Key_Home);self.assertEqual(window.search.cursorPosition(),0)
        self.key(window.search,menu.Qt.Key.Key_End);self.assertEqual(window.search.cursorPosition(),10)
        self.key(window.search,menu.Qt.Key.Key_Left);self.assertEqual(window.search.cursorPosition(),9)
        self.key(window.search,menu.Qt.Key.Key_Right);self.assertEqual(window.search.cursorPosition(),10)
        self.key(window.search,menu.Qt.Key.Key_Home,menu.Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(window.search.selectedText(),'Alpha Beta');self.assertTrue(window.search.hasFocus());self.no_launch()

    def test_tab_results_and_reverse_tab_keep_native_remaining_chain(self):
        window=self.window();self.key(window.search,menu.Qt.Key.Key_Tab);self.assertTrue(window.list.hasFocus())
        self.key(window.list,menu.Qt.Key.Key_Backtab);self.assertTrue(window.search.hasFocus())
        self.key(window.search,menu.Qt.Key.Key_Tab);self.key(window.list,menu.Qt.Key.Key_Tab);self.assertTrue(window.programs.hasFocus(),repr(self.app.focusWidget()))
        self.key(window.programs,menu.Qt.Key.Key_Backtab);self.assertTrue(window.list.hasFocus())
        self.assertIn('Home and End',window.list.accessibleDescription());self.assertIn('search text',window.search.accessibleDescription())
        window.search.setFocus();visited=set()
        for _ in range(80):
            focus=self.app.focusWidget();visited.add(focus);self.key(focus,menu.Qt.Key.Key_Tab)
            if window.search.hasFocus():break
        else:self.fail('Tab traversal did not return to search')
        self.assertTrue({window.search,window.list,window.programs,window.category,window.mascot,window.edit_links_button,window.power_arrow}.issubset(visited))
        self.no_launch()

    def test_focused_rebuild_preserves_id_then_nearest_row_and_empty_focus(self):
        window=self.window();window.list.setFocus();window.list.setCurrentRow(2)
        window.refresh();self.assertEqual(self.current_id(window),'Gamma.desktop');self.assertTrue(window.list.hasFocus())
        window.search.setText('a');self.assertEqual(self.current_id(window),'Gamma.desktop')
        window.search.setText('Beta');self.assertEqual(self.current_id(window),'Beta.desktop');self.assertTrue(window.list.hasFocus())
        window.search.setText('no-such-fixture');self.assertEqual(window.list.currentRow(),-1);self.assertTrue(window.search.hasFocus())
        window.search.clear();window.list.setCurrentRow(3);window.search.setText('a')
        self.assertTrue(window.search.hasFocus());self.assertEqual(self.current_id(window),'Alpha.desktop');self.no_launch()

    def test_catalog_rebuild_preserves_selection_and_keyboard_focus(self):
        window=self.window();window.list.setFocus();window.list.setCurrentRow(1)
        self.catalog_provider.return_value=[self.catalog[4],self.catalog[2],self.catalog[1]]
        window.refresh_catalog();self.assertEqual(self.current_id(window),'Beta.desktop');self.assertTrue(window.list.hasFocus())
        self.catalog_provider.return_value=[];window.refresh_catalog()
        self.assertEqual(window.list.currentRow(),-1);self.assertTrue(window.search.hasFocus());self.no_launch()

    def test_enter_uses_fake_launch_once_and_stale_rows_do_not_dispatch(self):
        window=self.window();window.search.setText('Beta');self.key(window.search,menu.Qt.Key.Key_Down)
        self.key(window.list,menu.Qt.Key.Key_Return)
        self.catalog[1].launch.assert_called_once_with([],None);self.assertFalse(window.isVisible())
        window.launch_item(window.list.currentItem());self.catalog[1].launch.assert_called_once()
        other=self.window();other.search.setText('Alpha');other.by_id.pop('Alpha.desktop')
        self.key(other.search,menu.Qt.Key.Key_Return);self.assertFalse(other.launching);self.assertTrue(other.isVisible());self.catalog[0].launch.assert_not_called()

    def test_nested_folder_menu_keeps_native_keys_and_staged_escape(self):
        window=self.window();window.search.setText('Alpha')
        folder=self.home/'folder';(folder/'child').mkdir(parents=True);(folder/'child'/'fixture.txt').write_text('fixture')
        opened=Mock();cascade=menu.FolderCascadeMenu(folder,opened,window);self.windows.append(cascade)
        cascade.popup(window.mapToGlobal(QPoint(10,20)))
        def wait(predicate):
            deadline=time.monotonic()+3
            while not predicate() and time.monotonic()<deadline:QTest.qWait(10)
            self.assertTrue(predicate())
        wait(lambda: bool(cascade.submenus));child=cascade.submenus[0]
        action=next(a for a in cascade.actions() if a.menu() is child)
        cascade.setActiveAction(action);self.key(cascade,menu.Qt.Key.Key_Right)
        wait(lambda: child.isVisible() and any(a.text()=='fixture.txt' for a in child.actions()))
        before=self.current_id(window);child.setActiveAction(child.actions()[0]);self.key(child,menu.Qt.Key.Key_Down)
        self.assertEqual(child.activeAction().text(),'fixture.txt');self.assertEqual(self.current_id(window),before)
        self.key(child,menu.Qt.Key.Key_Escape);self.assertFalse(child.isVisible());self.assertEqual(window.search.text(),'Alpha')
        self.key(cascade,menu.Qt.Key.Key_Escape);self.assertFalse(cascade.isVisible());self.assertEqual(window.search.text(),'Alpha')
        window.search.setFocus();self.key(window.search,menu.Qt.Key.Key_Escape);self.assertEqual(window.search.text(),'');self.assertTrue(window.isVisible())
        self.key(window.search,menu.Qt.Key.Key_Escape);self.assertEqual(window.category.currentText(),'Home');self.assertTrue(window.isVisible())
        self.key(window.search,menu.Qt.Key.Key_Escape);self.assertFalse(window.isVisible());opened.assert_not_called();self.no_launch()

    def test_resident_reopens_reset_search_and_cancel_without_dispatch(self):
        server=Server();resident=menu.ResidentMenu(self.app,server);resident.toggle();window=resident.window;self.windows.append(window)
        for _ in range(3):
            self.assertTrue(window.search.hasFocus());window.search.setText('Beta')
            self.key(window.search,menu.Qt.Key.Key_Up);self.assertTrue(window.list.hasFocus())
            self.key(window.list,menu.Qt.Key.Key_Escape);self.assertEqual(window.search.text(),'');self.assertTrue(window.search.hasFocus())
            self.key(window.search,menu.Qt.Key.Key_Escape);self.assertFalse(window.isVisible())
            resident.toggle();self.app.processEvents();self.assertIs(resident.window,window)
            self.assertEqual(window.search.text(),'');self.assertEqual(window.category.currentText(),'Home')
        self.no_launch()

if __name__=='__main__':unittest.main()
