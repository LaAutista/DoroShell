"""Regression coverage for opaque simulated glass and bounded first presentation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import shiboken6
import tempfile
import threading
import time
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from menu.wallpaper_glass import WallpaperGlass, MenuGlassController
from themes import PALETTES


class GlassEdgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def wait(self, predicate, seconds=2):
        end = time.monotonic() + seconds
        while not predicate() and time.monotonic() < end:
            loop = QEventLoop(); QTimer.singleShot(5, loop.quit); loop.exec()
        self.assertTrue(predicate())

    def test_atlas_retains_only_blurred_wallpaper_for_all_modes(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'wall.png'; Image.new('RGBA', (64, 64), (255, 0, 0, 128)).save(path)
            for mode in ('stretch', 'fit', 'crop'):
                atlas = WallpaperGlass(path, (100, 100), mode, '#0000ff')
                color = atlas.blurred.pixelColor(0, 0)
                self.assertEqual(color.alpha(), 255)
                self.assertGreater(color.red(), 100); self.assertGreater(color.blue(), 100)
                self.assertFalse(hasattr(atlas, 'edge_tiles'))
                self.assertFalse(hasattr(atlas, 'raw'))

    def test_gif_is_frozen_first_frame_and_jpeg_orientation_retained(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'wall.gif'
            Image.new('RGB', (80, 40), 'red').save(path, save_all=True,
                append_images=[Image.new('RGB', (80, 40), 'blue')], duration=20, loop=0)
            atlas = WallpaperGlass(path, (100, 100))
            self.assertGreater(atlas.blurred.pixelColor(5, 5).red(), 240)
            path = Path(d)/'wall.jpg'
            im = Image.new('RGB', (80, 40), 'red'); im.paste('blue', (40, 0, 80, 40))
            exif = Image.Exif(); exif[274] = 6; im.save(path, exif=exif, quality=100)
            atlas = WallpaperGlass(path, (100, 100), 'stretch', transform=True)
            self.assertGreater(atlas.blurred.pixelColor(5, 0).red(), 240)
            self.assertGreater(atlas.blurred.pixelColor(5, 11).blue(), 240)

    def exercise_presentation(self, outcome):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'wall.png'; Image.new('RGB', (64, 64), 'red').save(path)
            menu = QWidget(); menu.frame = QWidget(menu)
            QVBoxLayout(menu).addWidget(menu.frame); menu.resize(300, 300)
            gate = threading.Event()
            def decode(*args):
                gate.wait(2)
                if outcome == 'error': raise ValueError('broken image')
                return WallpaperGlass(*args)
            with patch('menu.wallpaper_glass.WallpaperGlass', side_effect=decode) as build:
                c = MenuGlassController(menu, path, PALETTES['windows'])
                try:
                    c.present(); self.assertFalse(menu.isVisible())
                    heartbeat = []; QTimer.singleShot(0, lambda: heartbeat.append(True))
                    if outcome != 'slow': gate.set()
                    self.wait(menu.isVisible)
                    self.assertTrue(heartbeat)
                    self.assertEqual(c.active, outcome == 'ready')
                    if outcome == 'slow':
                        gate.set(); self.wait(lambda: not c.busy)
                        self.assertFalse(c.active)  # Late result cannot flash into view.
                    if outcome == 'ready':
                        atlas = c.atlas; generation = c.generation
                        menu.move(20, 30); menu.resize(320, 310)
                        self.app.processEvents()
                        self.assertIs(c.atlas, atlas); self.assertEqual(c.generation, generation)
                        self.assertEqual(build.call_count, 1)
                        menu.hide(); c.present(); self.assertTrue(c.active)
                        self.assertEqual(build.call_count, 1)
                finally:
                    gate.set(); c.stop(); c.pool.shutdown(wait=True); menu.close(); shiboken6.delete(menu)

    def test_first_show_ready_without_geometry_redecode(self): self.exercise_presentation('ready')
    def test_first_show_error_uses_opaque_fallback(self): self.exercise_presentation('error')
    def test_first_show_deadline_keeps_late_result_opaque(self): self.exercise_presentation('slow')
