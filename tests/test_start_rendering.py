"""First mapped glass frame with synthetic wallpaper; no personal display or bus."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import shiboken6
from PIL import Image
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage
from test_menu import menu
import wallpaper_glass as glass


class StartRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = menu.QApplication.instance() or menu.QApplication([])

    def test_glass_curve_retains_fractional_alpha_and_texture_scale(self):
        backdrop = glass.Backdrop(None)
        backdrop.setAttribute(menu.Qt.WidgetAttribute.WA_TranslucentBackground)
        backdrop.resize(80, 80)
        try:
            for dpr in (1, 1.25, 1.5, 2):
                with self.subTest(dpr=dpr):
                    size = round(80*dpr)
                    texture = QImage(size, size, QImage.Format.Format_RGB32)
                    texture.fill(QColor('red')); texture.setDevicePixelRatio(dpr)
                    for y in range(size):
                        for x in range(size//2, size): texture.setPixelColor(x, y, QColor('blue'))
                    backdrop.image = texture
                    target = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
                    target.fill(menu.Qt.GlobalColor.transparent); target.setDevicePixelRatio(dpr)
                    backdrop.render(target)
                    curve = [target.pixelColor(x,y).alpha() for y in range(round(15*dpr))
                             for x in range(round(15*dpr))]
                    self.assertTrue(any(0 < alpha < 255 for alpha in curve), 'Rounded glass clipping is binary')
                    self.assertEqual(target.pixelColor(0,0).alpha(), 0)
                    self.assertEqual(target.pixelColor(round(20*dpr), round(40*dpr)), QColor('red'))
                    self.assertEqual(target.pixelColor(round(60*dpr), round(40*dpr)), QColor('blue'))
        finally:
            backdrop.close(); shiboken6.delete(backdrop)

    def test_first_paint_samples_final_mapped_position(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary); config = home/'.config'
            (config/'doroshell').mkdir(parents=True)
            (config/'pcmanfm-qt/lxqt').mkdir(parents=True)
            (config/'lxqt-comfort').mkdir()
            (config/'lxqt-comfort/favorites.json').write_text('[]')
            (config/'doroshell/wallpaper-glass.json').write_text('{"version":1,"enabled":true}')
            wallpaper = home/'synthetic.png'
            Image.new('RGB', (64, 64), 'purple').save(wallpaper)
            (config/'pcmanfm-qt/lxqt/settings.conf').write_text(
                '[Desktop]\nWallpaper='+str(wallpaper)+'\nWallpaperMode=stretch\n')
            with patch.dict(os.environ, {'HOME':str(home), 'XDG_CONFIG_HOME':str(config),
                                         'XDG_DATA_HOME':str(home/'data')}, clear=True), \
                    patch.object(menu, 'applications', return_value=[]), \
                    patch.object(menu, 'desktop_entry', return_value=None), \
                    patch.object(menu, 'has_compositor', return_value=False):
                window = menu.StartMenu(); controller = window.wallpaper_glass.controller
                paints = []; original = glass.Backdrop.paintEvent
                def paint(backdrop, event):
                    if backdrop is controller.backdrop and not paints:
                        _, dpr, origin = controller.screen_spec()
                        point = window.frame.mapToGlobal(QPoint())-origin
                        rect = window.frame.rect()
                        expected = (round(point.x()*dpr), round(point.y()*dpr),
                                    round(rect.width()*dpr), round(rect.height()*dpr))
                        # The last requested surface is the one assigned to the backdrop.
                        paints.append((next(reversed(controller.atlas.cache))[0], expected))
                    original(backdrop, event)
                try:
                    with patch.object(glass.Backdrop, 'paintEvent', paint):
                        for opening in range(3):
                            with self.subTest(opening=opening):
                                paints.clear(); menu.present_menu(window)
                                end = time.monotonic()+2
                                while not paints and time.monotonic()<end:
                                    self.app.processEvents(); time.sleep(.002)
                                self.assertTrue(paints, 'No glass paint before deadline')
                                self.assertEqual(*paints[0], 'First glass paint sampled the pre-map position')
                                window.hide(); self.app.processEvents()
                finally:
                    controller.stop(); controller.pool.shutdown(wait=True)
                    window.close(); shiboken6.delete(window)
