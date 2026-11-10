import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PIL import Image
import modules,install,settings
from menu.wallpaper_glass import resolve_wallpaper,WallpaperGlass
from themes import PALETTES

class WallpaperGlassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def seed(self,home):
        wall=home/'wall paper.png';Image.new('RGB',(100,50),'red').save(wall)
        pc=home/'.config/pcmanfm-qt/lxqt/settings.conf';pc.parent.mkdir(parents=True)
        pc.write_text('[Desktop]\nWallpaper='+str(wall)+'\nWallpaperMode=stretch\nBgColor=#123456\nPerScreenWallpaper=false\nSlideShowInterval=0\nTransformWallpaper=false\n')
        return wall,pc
    def test_optin_auto_resolve_repeat_exact_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);wall,pc=self.seed(home);before=pc.read_bytes()
            self.assertIsNone(resolve_wallpaper(home))
            modules.run(home,'wallpaper-glass',apply=True)
            spec=resolve_wallpaper(home);self.assertEqual(spec,dict(path=wall,mode='stretch',background='#123456',transform=False))
            manifest=home/'.local/state/doroshell/wallpaper-glass.json';saved=manifest.read_bytes()
            modules.run(home,'wallpaper-glass',apply=True);self.assertEqual(manifest.read_bytes(),saved)
            modules.run(home,'wallpaper-glass',rollback=True)
            self.assertIsNone(resolve_wallpaper(home));self.assertEqual(pc.read_bytes(),before)
            self.assertFalse((home/'.config/doroshell/wallpaper-glass.json').exists())
    def test_restore_existing_bytes_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);self.seed(home);cfg=home/'.config/doroshell/wallpaper-glass.json';cfg.parent.mkdir();original=b'{"version":1,"enabled":false,"personal":"keep"}\n';cfg.write_bytes(original);cfg.chmod(0o640)
            modules.run(home,'wallpaper-glass',apply=True);modules.run(home,'wallpaper-glass',rollback=True)
            self.assertEqual(cfg.read_bytes(),original);self.assertEqual(cfg.stat().st_mode&0o777,0o640)
            modules.run(home,'wallpaper-glass',apply=True);cfg.write_text('{"version":1,"enabled":false}')
            with self.assertRaises(RuntimeError):modules.run(home,'wallpaper-glass',rollback=True)
    def test_unsupported_layouts_and_qt_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);wall,pc=self.seed(home);modules.run(home,'wallpaper-glass',apply=True);original=pc.read_text()
            for replacement in [('WallpaperMode=stretch','WallpaperMode=tile'),('PerScreenWallpaper=false','PerScreenWallpaper=true'),('SlideShowInterval=0','SlideShowInterval=10')]:
                pc.write_text(original.replace(*replacement));self.assertIsNone(resolve_wallpaper(home))
            pc.write_text(original.replace('WallpaperMode=stretch','WallpaperMode=zoom').replace('#123456','#ff123456'))
            spec=resolve_wallpaper(home);self.assertEqual(spec['mode'],'crop');self.assertEqual(spec['background'],'#123456')
    def test_installer_settings_and_no_default_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);files=install.targets(home)
            self.assertIn(home/'.local/share/lxqt-comfort/wallpaper_glass.py',files)
            self.assertIn(home/'.local/share/lxqt-comfort/themes.py',files)
            widget=settings.Settings(home);choice=widget.choices['wallpaper-glass'];self.assertEqual(choice.currentData(),'keep');self.assertEqual(widget.commands(True),[])
            choice.setCurrentIndex(choice.findData('enable'));self.assertIn('wallpaper-glass',widget.commands(True)[0]);widget.close()
    def test_custom_config_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_CONFIG_HOME': '/tmp/custom-doro-config'}):
            with patch('modules.Path.home', return_value=Path(tmp)), self.assertRaisesRegex(ValueError, 'custom XDG_CONFIG_HOME'):
                modules.plans(Path(tmp),'wallpaper-glass')

    def test_alpha_cache_bounds_and_transform(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'alpha.png';Image.new('RGBA',(100,100),(255,0,0,0)).save(path)
            a=WallpaperGlass(path,(2560,1440),'stretch','#00ff00');self.assertEqual(a.blurred.pixelColor(0,0).name(),'#00ff00')
            one=a.surface((0,0,500,500),PALETTES['windows']);self.assertEqual(one.cacheKey(),a.surface((0,0,500,500),PALETTES['windows']).cacheKey())
            for i in range(20):a.surface((i,0,500,500),PALETTES['windows'])
            self.assertLessEqual(len(a.cache),8);self.assertLessEqual(sum(v.sizeInBytes() for v in a.cache.values()),16*1024*1024)
