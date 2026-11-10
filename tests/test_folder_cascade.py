import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
import shiboken6
from menu import folder_cascade as fc


class FolderCascadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def wait(self,condition,ms=3000):
        for _ in range(ms//10):
            if condition():return
            QTest.qWait(10)
        self.fail('Timed out waiting for folder helper')
    def test_listing_is_one_level_sorted_and_skips_hidden_links_and_special_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'Z folder').mkdir();(root/'Z folder/private.txt').write_text('not read')
            (root/'alpha & beta.txt').write_text('data');(root/'.hidden').touch();(root/'link').symlink_to(root/'Z folder');os.mkfifo(root/'pipe')
            result=fc.list_folder(root)
            self.assertEqual([x['name'] for x in result['items']],['Z folder','alpha & beta.txt'])
            self.assertFalse(result['limited']);self.assertEqual(result['error'],'')
    def test_scan_and_output_limits_are_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i in range(12):(root/str(i)).touch()
            with patch.object(fc,'MAX_SCAN',8),patch.object(fc,'MAX_ITEMS',3):result=fc.list_folder(root)
            self.assertTrue(result['limited']);self.assertEqual(len(result['items']),3)
    def test_missing_folder_and_protocol_validation(self):
        self.assertTrue(fc.list_folder('/not/a/real/folder')['error'])
        for name in ['../bad','/root','.','..','bad\0name']:
            with self.assertRaises(ValueError):fc.validate_result(dict(items=[dict(name=name,directory=False)],limited=False,error=''))
        self.assertEqual(fc.label('A&B\nName'),'A&&B�Name')
    def test_async_menu_lazy_child_and_uri_path_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);child=root/'nested';child.mkdir();(child/'inside.txt').touch();file=root/'space & snow ☃.txt';file.touch();opened=Mock()
            menu=fc.FolderCascadeMenu(root,opened);self.assertIsNone(menu.job['process']);menu.load()
            self.wait(lambda:menu.job['process'] is None)
            actions={a.data():a for a in menu.actions() if a.data()}
            nested=actions[child.as_uri()].menu();self.assertIsNone(nested.job['process'])
            actions[file.as_uri()].trigger();opened.assert_called_once_with(str(file))
            nested.load();self.wait(lambda:nested.job['process'] is None)
            self.assertIn((child/'inside.txt').as_uri(),[a.data() for a in nested.actions()]);menu.cancel();shiboken6.delete(menu)
    def test_non_utf8_filename_keeps_exact_path_and_safe_action_data(self):
        with tempfile.TemporaryDirectory() as d:
            raw=os.fsencode(d)+b'/invalid-\xff.txt'
            fd=os.open(raw,os.O_CREAT|os.O_WRONLY,0o600);os.close(fd)
            path=Path(os.fsdecode(raw));opened=Mock();menu=fc.FolderCascadeMenu(d,opened)
            menu.load();self.wait(lambda:menu.job['process'] is None)
            action=next(a for a in menu.actions() if a.data())
            self.assertEqual(action.data(),path.as_uri());action.trigger()
            opened.assert_called_once_with(str(path));shiboken6.delete(menu)
            directory=Path(os.fsdecode(os.fsencode(d)+b'/folder-\xff'))
            directory.mkdir();(directory/'child.txt').touch()
            menu=fc.FolderCascadeMenu(directory,opened);menu.load()
            self.wait(lambda:menu.job['process'] is None)
            self.assertIn((directory/'child.txt').as_uri(),[a.data() for a in menu.actions()])
            shiboken6.delete(menu)
    def test_timeout_keeps_gui_responsive_and_kills_only_own_helper(self):
        with tempfile.TemporaryDirectory() as d:
            script=Path(d)/'slow';script.write_text('#!/usr/bin/python\nimport time\ntime.sleep(30)\n');script.chmod(0o755)
            with patch.object(fc,'TIMEOUT_MS',200):menu=fc.FolderCascadeMenu(d,Mock())
            ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(1));timer.start(10)
            with patch.object(fc.sys,'executable',str(script)):menu.load()
            self.wait(lambda:menu.failed)
            self.assertGreater(len(ticks),5);self.assertIsNone(menu.job['process']);self.assertIn('too long',menu.actions()[-1].text())
            timer.stop();shiboken6.delete(menu)
    def test_destroy_cancels_pending_worker_without_blocking(self):
        with tempfile.TemporaryDirectory() as d:
            script=Path(d)/'slow';script.write_text('#!/usr/bin/python\nimport time\ntime.sleep(30)\n');script.chmod(0o755)
            menu=fc.FolderCascadeMenu(d,Mock())
            with patch.object(fc.sys,'executable',str(script)):menu.load()
            self.wait(lambda:menu.job['process'].processId()>0);pid=menu.job['process'].processId()
            shiboken6.delete(menu);self.wait(lambda:not Path('/proc',str(pid),'exe').exists())
    def test_depth_limit_and_reopen_refresh(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);menu=fc.FolderCascadeMenu(root,Mock(),depth=fc.MAX_DEPTH);menu.load()
            self.assertIsNone(menu.job['process']);self.assertIn('deeper',menu.actions()[-1].text());shiboken6.delete(menu)
            menu=fc.FolderCascadeMenu(root,Mock());menu.load();self.wait(lambda:menu.job['process'] is None)
            (root/'new.txt').touch();menu.load();self.wait(lambda:menu.job['process'] is None)
            self.assertIn((root/'new.txt').as_uri(),[a.data() for a in menu.actions()]);shiboken6.delete(menu)
