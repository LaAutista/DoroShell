"""Synthetic XBEL/offscreen tests only; no personal history or document dispatch."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'menu'))
import recent_documents as docs


def xbel(body):
    return ('<xbel xmlns:b="'+docs.BOOKMARK_NS+'">'+body+'</xbel>').encode()


def bookmark(uri='file:///fixture/report.txt', extra='', stamp='2026-01-01T00:00:00Z'):
    return '<bookmark href="'+uri+'" visited="'+stamp+'">'+extra+'</bookmark>'


class DocumentReaderTests(unittest.TestCase):
    def test_local_uri_validation_and_unicode(self):
        self.assertEqual(docs.local_uri('file://localhost/fixture/caf%C3%A9%20%E6%96%87.txt'), ('file:///fixture/caf%C3%A9%20%E6%96%87.txt','café 文.txt'))
        for uri in ('https://example.test/a','smb://host/a','file://remote/a','file://user@localhost/a','file://localhost:22/a','file:relative','file:////server/a','file:///a/../b','file:///a//b','file:///a/','file:///','file:///a?query','file:///a#fragment','file:///bad%xx','file:///bad%FF','file:///a%00b','file:///a%0Ab','file:///a%E2%80%AEb',' file:///a','file:///a\n'):
            with self.subTest(uri=uri),self.assertRaises(ValueError):docs.local_uri(uri)

    def test_oversized_malformed_dtd_entity_and_encoding_refusal(self):
        attack='<!DOCTYPE xbel [<!ENTITY file SYSTEM "file:///fixture/private">]><xbel>&file;</xbel>'
        for data in (b'x'*(docs.MAX_BYTES+1), b'<xbel>', b'<other/>', attack.encode(), attack.encode('utf-16'), b'<!DOCTYPE xbel SYSTEM "https://example.test/x"><xbel/>'):
            with self.subTest(size=len(data)),self.assertRaises(ValueError):docs.parse(data)
        for uri in ('file:///a?', 'file:///a#', 'file:///a%E2%80%A8b', 'file:///'+('文'*600)):
            with self.subTest(uri=uri[:30]),self.assertRaises(ValueError):docs.local_uri(uri)

    def test_structure_count_depth_bounds_and_item_limit(self):
        with self.assertRaises(ValueError):docs.parse(xbel(bookmark()* (docs.MAX_BOOKMARKS+1)))
        with self.assertRaises(ValueError):docs.parse(xbel('<a>'*17+'</a>'*17))
        with self.assertRaises(ValueError):docs.parse(xbel(bookmark(extra=bookmark())))
        self.assertEqual(len(docs.parse(xbel(''.join(bookmark(f'file:///fixture/{i:03}.txt') for i in range(40))))),20)

    def test_duplicate_canonical_uri_private_suppression_order_and_titles(self):
        data=xbel(bookmark('file:///fixture/old.txt',stamp='invalid')+
                  bookmark('file:///fixture/new.txt',extra='<title>ignored malicious title</title>')+
                  bookmark('file://localhost/fixture/new.txt')+
                  bookmark('file:///fixture/private.txt')+
                  bookmark('file:///fixture/private.txt',extra='<info><metadata owner="http://freedesktop.org"><b:private/></metadata></info>'))
        self.assertEqual(docs.parse(data),[{'uri':'file:///fixture/new.txt','label':'new.txt'},{'uri':'file:///fixture/old.txt','label':'old.txt'}])
        ordered=docs.parse(xbel(bookmark('file:///invalid.txt',stamp='invalid')+bookmark('file:///before-epoch.txt',stamp='1960-01-01T00:00:00Z')))
        self.assertEqual(ordered[-1]['uri'],'file:///invalid.txt')

    def test_missing_and_network_mounted_paths_never_inspected(self):
        with patch.object(Path,'stat',side_effect=AssertionError('target probe')),patch.object(Path,'exists',side_effect=AssertionError('target probe')),patch.object(os,'open',side_effect=AssertionError('target open')):
            rows=docs.parse(xbel(bookmark('file:///network-mount/offline.txt')+bookmark('file:///missing.txt')+bookmark('https://example.test/file')))
        self.assertEqual(len(rows),2)

    def test_shared_regular_file_symlink_fifo_size_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_DATA_HOME':tmp}):
            path=Path(tmp)/'recently-used.xbel';self.assertEqual(docs.read_shared(),[])
            data=xbel(bookmark());path.write_bytes(data);self.assertEqual(len(docs.read_shared()),1);self.assertEqual(path.read_bytes(),data)
            path.unlink();path.symlink_to('missing')
            with self.assertRaises(OSError):docs.read_shared()
            path.unlink();os.mkfifo(path)
            with self.assertRaises(ValueError):docs.read_shared()
            path.unlink();path.write_bytes(b'x'*(docs.MAX_BYTES+1))
            with self.assertRaises(ValueError):docs.read_shared()

    def test_preferences_default_schema_errors_and_no_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'recent-documents.json';self.assertEqual(docs.preference(path),(False,None,None))
            for data in (b'{}',b'{"version":2,"enabled":true}',b'{"version":1,"enabled":1}',b'{"version":1,"enabled":true,"enabled":false}',b'{"version":1,"enabled":true,"items":[]}',b'x'*4097):
                path.write_bytes(data);enabled,_,error=docs.preference(path)
                self.assertFalse(enabled);self.assertTrue(error);self.assertEqual(path.read_bytes(),data)
            path.unlink();os.mkfifo(path);self.assertFalse(docs.preference(path)[0]);self.assertTrue(docs.preference(path)[2])


class DocumentUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_start_keyboard import StartKeyboardTests
        StartKeyboardTests.setUpClass()
        cls.fixture_class=StartKeyboardTests

    def setUp(self):
        self.fixture=self.fixture_class(methodName='runTest');self.fixture.setUp()
        self.qt_errors=[]
        self.enterContext(patch.object(sys,'excepthook',side_effect=lambda *error:self.qt_errors.append(error)))
        def cleanup():
            self.fixture.doCleanups();self.fixture.app.processEvents();self.assertEqual(self.qt_errors,[])
        self.addCleanup(cleanup)
        self.window=self.fixture.window();self.app=self.fixture.app;self.home=self.fixture.home
        self.store=self.home/'data/recently-used.xbel';self.store.parent.mkdir(parents=True,exist_ok=True)
        self.original=xbel(bookmark());self.store.write_bytes(self.original)

    def wait(self,predicate):
        deadline=time.monotonic()+4
        while not predicate() and time.monotonic()<deadline:self.app.processEvents();time.sleep(.01)
        self.assertTrue(predicate())

    def show_documents(self):
        self.window.set_documents_enabled(True)
        popup=self.window.documents_menu;popup.popup(self.window.documents_button.mapToGlobal(self.window.documents_button.rect().bottomLeft()))
        self.wait(lambda:popup.process is None)
        return popup

    def test_default_off_zero_store_reads_and_policy_only_portability(self):
        from PySide6.QtCore import QProcess
        import portable_settings
        self.assertFalse(self.window.documents_enabled);self.assertTrue(self.window.documents_button.isHidden())
        with patch.object(QProcess,'start',side_effect=AssertionError('disabled reader started')):
            self.window.documents_menu.load();self.window.refresh();self.window.show()
        self.window.set_documents_enabled(True)
        config=self.window.documents_path
        self.assertEqual(json.loads(config.read_bytes()),{'version':1,'enabled':True})
        self.assertEqual(list(config.parent.glob('recent-documents.json.backup-*')),[])
        export=portable_settings.Store(self.home).export()
        self.assertNotIn('fixture',json.dumps(export));self.assertNotIn('documents',json.dumps(export))
        self.window.set_documents_enabled(False);self.assertEqual(self.store.read_bytes(),self.original)

    def test_actual_worker_native_keys_and_cross_column_focus(self):
        from PySide6.QtCore import Qt
        popup=self.show_documents();actions=[a for a in popup.actions() if a.isEnabled()]
        self.assertEqual([a.text() for a in actions],['report.txt'])
        self.assertFalse(self.window.column_navigation_allowed())
        self.fixture.key(popup,Qt.Key.Key_Down);self.assertIs(popup.activeAction(),actions[0])
        self.fixture.key(popup,Qt.Key.Key_Escape);self.assertFalse(popup.isVisible())
        self.window.documents_button.setFocus();self.app.processEvents()
        self.fixture.key(self.window.documents_button,Qt.Key.Key_Left);self.assertTrue(self.window.list.hasFocus())
        self.fixture.key(self.window.list,Qt.Key.Key_Right);self.assertTrue(self.window.documents_button.hasFocus())
        self.assertEqual(self.store.read_bytes(),self.original)

    def test_mocked_dispatch_failure_preserves_history_and_success_uses_gio(self):
        from test_menu import menu
        self.window.set_documents_enabled(True)
        with patch.object(self.window,'error') as error,patch.object(menu.Gio.AppInfo,'launch_default_for_uri',return_value=False) as launch:
            self.window.open_document('file:///fixture/missing.txt');launch.assert_called_once_with('file:///fixture/missing.txt',None)
            self.assertIn('missing',error.call_args.args[0]);self.assertTrue(self.window.isVisible())
        with patch.object(menu.Gio.AppInfo,'launch_default_for_uri',return_value=True) as launch:
            self.window.open_document('file:///fixture/report.txt');self.window.open_document('file:///fixture/report.txt')
            launch.assert_called_once();self.assertFalse(self.window.isVisible())
        self.assertEqual(self.store.read_bytes(),self.original)

    def test_native_enter_dispatch_and_disable_without_reading_again(self):
        from test_menu import menu
        popup=self.show_documents();action=next(a for a in popup.actions() if a.isEnabled())
        popup.setActiveAction(action)
        with patch.object(menu.Gio.AppInfo,'launch_default_for_uri',return_value=True) as launch:
            self.fixture.key(popup,menu.Qt.Key.Key_Return)
            launch.assert_called_once_with('file:///fixture/report.txt',None)
        self.app.processEvents();self.assertEqual(popup.actions(),[])
        self.window.set_documents_enabled(False)
        with patch.object(menu.Gio.AppInfo,'launch_default_for_uri') as launch:
            self.window.open_document('file:///fixture/report.txt');launch.assert_not_called()

    def test_reopen_reflects_edits_empty_malformed_and_no_raw_errors(self):
        popup=self.show_documents();popup.close();self.app.processEvents()
        self.assertEqual(popup.actions(),[])
        self.store.write_bytes(xbel(''));popup=self.show_documents();self.assertIn('No supported',popup.actions()[-1].text())
        popup.close();self.app.processEvents();self.store.write_bytes(b'<fixture-private-error')
        popup=self.show_documents();self.assertIn('unsupported',popup.actions()[0].text());self.assertNotIn('fixture-private',popup.actions()[0].text())

    def test_timeout_cancel_disable_and_late_completion(self):
        from PySide6.QtCore import QProcess
        self.window.set_documents_enabled(True);popup=self.window.documents_menu
        original_start=QProcess.start
        def stalled(process,*args):original_start(process,sys.executable,['-c','import time;time.sleep(5)'])
        with patch.object(QProcess,'start',stalled):
            popup.load();process=popup.process;popup.timer.timeout.emit()
            self.assertIsNone(popup.process);self.assertIn('timed out',popup.actions()[0].text())
            self.wait(lambda:process.state()==QProcess.ProcessState.NotRunning)
            self.window.set_documents_enabled(True);popup.load();process=popup.process
            self.window.close();self.assertIsNone(popup.process)
            self.wait(lambda:process.state()==QProcess.ProcessState.NotRunning)
            popup.load();process=popup.process;self.window.set_documents_enabled(False)
            self.assertIsNone(popup.process);self.assertEqual(popup.actions(),[])
            self.wait(lambda:process.state()==QProcess.ProcessState.NotRunning)

    def test_future_and_external_preferences_and_save_failure_preserved(self):
        from test_menu import menu
        from PySide6.QtCore import QProcess
        original=b'{"version":99,"enabled":true}'
        self.window.documents_path.write_bytes(original)
        with patch.object(self.window,'error') as error:
            self.window.set_documents_enabled(True);self.assertTrue(error.called)
        self.assertFalse(self.window.documents_enabled);self.assertEqual(self.window.documents_path.read_bytes(),original)
        new=self.fixture.window();self.assertTrue(new.documents_error)
        with patch.object(new,'error'),patch.object(QProcess,'start',side_effect=AssertionError('future prefs read history')):
            new.set_documents_enabled(True);new.documents_menu.load()
        self.assertFalse(new.documents_enabled)
        self.window.documents_path.unlink()
        with patch.object(menu,'save_json',side_effect=OSError('fixture disk full')),patch.object(self.window,'error'):
            self.window.set_documents_enabled(True)
        self.assertFalse(self.window.show_documents.isChecked())

    def test_resident_detects_external_preference_changes_with_bounded_read(self):
        from test_menu import menu
        from test_start_keyboard import Server
        resident=menu.ResidentMenu(self.app,Server());resident.window=self.window
        before=resident.snapshot();self.window.documents_path.write_bytes(b'x'*8192)
        read=Path.read_bytes
        def bounded(path):
            if path==self.window.documents_path:raise AssertionError('Unbounded document preference read')
            return read(path)
        with patch.object(Path,'read_bytes',bounded):after=resident.snapshot()
        self.assertNotEqual(before,after)


class DocumentInstallTests(unittest.TestCase):
    def test_installed_worker_import_repeat_conflict_rollback_and_privacy(self):
        import install
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            home=Path(tmp);runtime=home/'.local/share/lxqt-comfort';runtime.mkdir(parents=True)
            helper=runtime/'recent_documents.py';helper.write_bytes(b'# previous helper\n');helper.chmod(0o640)
            config=home/'.config/lxqt-comfort/recent-documents.json';config.parent.mkdir(parents=True)
            config.write_text('{"version":1,"enabled":true}')
            store=home/'.local/share/recently-used.xbel';data=xbel(bookmark());store.write_bytes(data)
            env=dict(HOME=tmp,PATH='/usr/bin:/bin',XDG_DATA_HOME=str(home/'.local/share'),XDG_CONFIG_HOME=str(home/'.config'),QT_QPA_PLATFORM='offscreen',DBUS_SESSION_BUS_ADDRESS='unix:path='+tmp+'/no-bus',DBUS_SYSTEM_BUS_ADDRESS='unix:path='+tmp+'/no-system')
            with patch.dict(os.environ,env,clear=True):
                install.install(home,True)
                record=home/'.local/state/lxqt-comfort/menu-install.json';first=record.read_bytes()
                install.install(home,True);self.assertEqual(record.read_bytes(),first)
                self.assertEqual(helper.read_bytes(),(home/'.local/share/doroshell/toolkit/menu/recent_documents.py').read_bytes())
                result=subprocess.run([sys.executable,'-B',str(helper),'--read'],env=env,cwd=home,capture_output=True,text=True,timeout=4)
                self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout),docs.parse(data))
                self.assertNotIn(b'fixture/report',first)
                installed=helper.read_bytes();helper.write_bytes(b'# external edit\n')
                with self.assertRaises(RuntimeError):install.rollback(home)
                helper.write_bytes(installed);install.rollback(home)
                self.assertEqual(helper.read_bytes(),b'# previous helper\n');self.assertEqual(helper.stat().st_mode&0o777,0o640)
                self.assertTrue(config.exists());self.assertEqual(store.read_bytes(),data)
