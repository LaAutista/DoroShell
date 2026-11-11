import importlib.util
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile, unittest, socket, threading, subprocess, sys
from pathlib import Path
from unittest.mock import patch
import shiboken6
from PySide6.QtCore import QObject, Signal, QTimer, QEventLoop
from PySide6.QtWidgets import QApplication, QDialog
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('resident_test_menu',ROOT/'menu/start_menu.py')
menu=importlib.util.module_from_spec(spec);spec.loader.exec_module(menu)

class Server(QObject):
    newConnection=Signal()

class ResidentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.home=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.home/'config'),'XDG_DATA_HOME':str(self.home/'data')});self.env.start()
        self.server=Server();self.resident=menu.ResidentMenu(self.app,self.server)
    def tearDown(self):
        window=self.resident.window
        if window:
            if window.wallpaper_glass and window.wallpaper_glass.controller:window.wallpaper_glass.controller.stop()
            shiboken6.delete(window)
        self.env.stop();self.tmp.cleanup()
    def test_reopen_resets_launch_search_category_and_keeps_one_window(self):
        r=self.resident;r.toggle();w=r.window
        w.launching=True;w.search.setText('terminal');w.category.setCurrentText('System')
        r.toggle();self.assertFalse(w.isVisible());r.toggle()
        self.assertIs(r.window,w);self.assertFalse(w.launching)
        self.assertEqual(w.search.text(),'');self.assertEqual(w.category.currentText(),'Home')
        for _ in range(10):r.toggle();r.toggle();self.assertIs(r.window,w)
    def test_successful_launch_reopens_without_rebuild_or_stuck_launching(self):
        from unittest.mock import Mock
        r=self.resident;r.toggle();w=r.window
        ident='fixture.desktop';w.by_id[ident]=Mock();w.by_id[ident].launch.return_value=True
        item=menu.QListWidgetItem();item.setData(menu.Qt.ItemDataRole.UserRole,ident)
        w.launch_item(item);self.assertFalse(w.isVisible());self.assertTrue(w.launching)
        r.toggle();self.assertIs(r.window,w);self.assertFalse(w.launching)
        self.assertIn(ident,w.recent.value['items'])
        r.toggle();w.recent.path.write_text('{"enabled":false,"items":[]}');r.toggle()
        self.assertIsNot(r.window,w);self.assertFalse(r.window.remember.isChecked())

    def test_own_pin_and_primary_edits_keep_window(self):
        r=self.resident;r.toggle();w=r.window
        self.assertTrue(w.save_favorites(list(reversed(w.favorites))))
        w.set_primary_action('lockscreen')
        r.toggle();r.toggle();self.assertIs(r.window,w)
        self.assertEqual(w.primary_action,'lockscreen')

    def test_preferences_theme_portrait_and_primary_action_rebuild(self):
        r=self.resident;r.toggle()
        for filename,text in [('doroshell/theme.conf','[Theme]\nname=heretic\n'),
                              ('lxqt-comfort/session-button.json','{"version":1,"action":"lockscreen"}')]:
            old=r.window;r.toggle();path=self.home/'config'/filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            r.toggle();self.assertIsNot(r.window,old);self.assertFalse(shiboken6.isValid(old))
        self.assertEqual(r.window.primary_action,'lockscreen')
        r.toggle();portrait=self.home/'portrait.png'
        from PIL import Image
        Image.new('RGB',(50,50),'red').save(portrait)
        cfg=self.home/'config/lxqt-comfort/folders.json'
        import json
        cfg.write_text(json.dumps({'version':1,'folders':menu.default_links(),'portrait':str(portrait),'portraitCrop':{'x':.5,'y':.5,'zoom':2}}))
        r.toggle();old=r.window;self.assertEqual(old.folder_settings.portrait_crop['zoom'],2)
        r.toggle();Image.new('RGB',(50,50),'blue').save(portrait);r.toggle()
        self.assertIsNot(r.window,old)
    def test_modal_and_drag_are_not_toggled_away(self):
        r=self.resident;r.toggle();w=r.window
        dialog=QDialog(w);dialog.setModal(True);dialog.show()
        r.toggle();self.assertTrue(dialog.isVisible());dialog.close();w.show()
        w.list.dragging=True;r.toggle();self.assertTrue(w.isVisible());w.list.dragging=False
    def test_cancel_pending_decode_and_retry_failed_open(self):
        from PIL import Image
        wall=self.home/'wall.png';Image.new('RGB',(40,40),'red').save(wall)
        config=self.home/'config/doroshell';config.mkdir(parents=True);(config/'wallpaper-glass.json').write_text('{"version":1,"enabled":true}')
        pc=self.home/'config/pcmanfm-qt/lxqt';pc.mkdir(parents=True);(pc/'settings.conf').write_text('[Desktop]\nWallpaper='+str(wall)+'\nWallpaperMode=stretch\n')
        import wallpaper_glass
        original=wallpaper_glass.WallpaperGlass
        gate=threading.Event()
        def delayed(*args,**kwargs):gate.wait(2);return original(*args,**kwargs)
        with patch('wallpaper_glass.WallpaperGlass',side_effect=delayed):
            r=self.resident;r.toggle();c=r.window.wallpaper_glass.controller
            self.assertTrue(c.show_pending);r.toggle();self.assertFalse(c.show_pending)
            gate.set();loop=QEventLoop();QTimer.singleShot(80,loop.quit);loop.exec()
            self.assertFalse(r.window.isVisible())
        c.suspend();r.toggle()
        loop=QEventLoop();QTimer.singleShot(100,loop.quit);loop.exec()
        self.assertTrue(c.active);self.assertTrue(r.window.isVisible())
    def test_slow_fallback_retries_on_next_open(self):
        from PIL import Image
        wall=self.home/'wall.png';Image.new('RGB',(40,40),'red').save(wall)
        cfg=self.home/'config/doroshell';cfg.mkdir(parents=True);(cfg/'wallpaper-glass.json').write_text('{"version":1,"enabled":true}')
        pc=self.home/'config/pcmanfm-qt/lxqt';pc.mkdir(parents=True);(pc/'settings.conf').write_text('[Desktop]\nWallpaper='+str(wall)+'\nWallpaperMode=stretch\n')
        import wallpaper_glass
        original=wallpaper_glass.WallpaperGlass;gate=threading.Event()
        def delayed(*args,**kwargs):gate.wait(2);return original(*args,**kwargs)
        with patch('wallpaper_glass.WallpaperGlass',side_effect=delayed):
            r=self.resident;r.toggle();c=r.window.wallpaper_glass.controller
            loop=QEventLoop();QTimer.singleShot(320,loop.quit);loop.exec()
            self.assertTrue(r.window.isVisible());self.assertFalse(c.active);self.assertFalse(c.enabled)
            r.toggle();gate.set();r.toggle()
            loop=QEventLoop();QTimer.singleShot(120,loop.quit);loop.exec()
            self.assertTrue(r.window.isVisible());self.assertTrue(c.active);self.assertTrue(c.enabled)

    def test_lightweight_client_does_not_import_qt_or_gio(self):
        code = """
import socket,runpy,sys
from unittest.mock import MagicMock
client=MagicMock();client.recv.return_value=b'OK'
socket.socket=MagicMock();socket.socket.return_value.__enter__.return_value=client
sys.argv=[sys.argv[1]]
try:runpy.run_path(sys.argv[0],run_name='__main__')
except SystemExit as error:assert error.code==0
assert 'PySide6' not in sys.modules and 'gi' not in sys.modules
assert client.sendall.call_args[0][0].endswith(b'\\n')
"""
        result=subprocess.run([sys.executable,'-c',code,str(ROOT/'menu/start_menu.py')],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
