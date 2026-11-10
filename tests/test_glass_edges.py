import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile
from pathlib import Path
import unittest
from PIL import Image
from menu.wallpaper_glass import WallpaperGlass


class GlassEdgeTests(unittest.TestCase):
    def test_edge_tiles_bounded_without_full_resolution_retention(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'wall.png';Image.new('RGB',(128,128),'purple').save(path)
            for dpr in (1,1.5):
                atlas=WallpaperGlass(path,(int(1024*dpr),int(768*dpr)),'stretch',edge_geometry=(0,0,int(508*dpr),int(634*dpr),dpr))
                self.assertEqual(len(atlas.edge_tiles),8)
                self.assertLessEqual(sum(image.sizeInBytes() for _,_,image in atlas.edge_tiles),256*1024)
                self.assertFalse(hasattr(atlas,'raw'))
    def test_unsupported_layouts_and_outside_geometry_skip_edge_not_glass(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'wall.png';Image.new('RGB',(64,64),'red').save(path)
            for mode,size,geometry in [('fit',(100,100),(0,0,80,80,1)),('stretch',(10000,1000),(0,0,80,80,1)),('stretch',(100,100),(-10,0,80,80,1))]:
                atlas=WallpaperGlass(path,size,mode,edge_geometry=geometry)
                self.assertFalse(atlas.edge_tiles)
                self.assertFalse(atlas.blurred.isNull())
    def test_transparent_edge_uses_opaque_configured_background(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'alpha.png';Image.new('RGBA',(64,64),(255,0,0,128)).save(path)
            atlas=WallpaperGlass(path,(100,100),'stretch',background='#0000ff',edge_geometry=(0,0,80,80,1))
            color=atlas.edge_tiles[0][2].pixelColor(0,0)
            self.assertEqual(color.alpha(),255);self.assertGreater(color.red(),100);self.assertGreater(color.blue(),100)
    def test_jpeg_rotation_applies_to_raw_edge(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'rotated.jpg';im=Image.new('RGB',(80,40),'red');im.paste('blue',(40,0,80,40));exif=Image.Exif();exif[274]=6;im.save(path,exif=exif,quality=100)
            atlas=WallpaperGlass(path,(100,100),'stretch',transform=True,edge_geometry=(0,0,100,100,1))
            top=atlas.edge_tiles[0][2].pixelColor(0,0);bottom=atlas.edge_tiles[2][2].pixelColor(0,0)
            self.assertGreater(top.red(),240);self.assertGreater(bottom.blue(),240)
