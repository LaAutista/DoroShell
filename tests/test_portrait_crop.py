import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtGui import QImage,QColor
from menu.portrait_crop import source_rect,render_crop,validate_crop,PortraitCropDialog,load_image
from menu.start_menu import StartMenu,FolderEditor,FolderSettings
import shiboken6


class PortraitCropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def image(self,path):
        image=QImage(600,300,QImage.Format.Format_RGB32);image.fill(QColor('red'))
        for y in range(300):
            for x in range(300,600):image.setPixelColor(x,y,QColor('blue'))
        image.save(str(path));return image
    def test_geometry_zoom_edges_and_validation(self):
        image=QImage(600,300,QImage.Format.Format_RGB32)
        self.assertEqual(source_rect(image,None).getRect(),(150.,0.,300.,300.))
        rect=source_rect(image,dict(x=1,y=0,zoom=2));self.assertEqual(rect.getRect(),(450.,0.,150.,150.))
        for bad in ({},dict(x=10**400,y=.5,zoom=1),dict(x=float('inf'),y=.5,zoom=1),dict(x=float('nan'),y=.5,zoom=1),dict(x=True,y=.5,zoom=1),dict(x=.5,y=.5,zoom=5)):
            with self.assertRaises(ValueError):validate_crop(bad)
    def test_crop_apply_persistence_and_original_unchanged(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_CONFIG_HOME':d,'XDG_DATA_HOME':d}):
            path=Path(d)/'original.png';image=self.image(path);before=path.read_bytes()
            window=StartMenu();crop=dict(x=.85,y=.5,zoom=2)
            with patch('menu.start_menu.QFileDialog.getOpenFileName',return_value=(str(path),'')),patch('menu.start_menu.PortraitCropDialog.exec',return_value=QDialog.DialogCode.Accepted),patch('menu.start_menu.PortraitCropDialog.crop',return_value=crop):window.choose_portrait()
            value=json.loads(window.folder_settings.path.read_text());self.assertEqual(value['portraitCrop'],crop)
            self.assertEqual(window.mascot.pixmap().toImage().pixelColor(38,38),QColor('blue'))
            settings=FolderSettings(window.folder_settings.path);settings.save(settings.links,hidden=['Printers'])
            self.assertEqual(FolderSettings(settings.path).portrait_crop,crop)
            self.assertEqual(path.read_bytes(),before);shiboken6.delete(window)
    def test_cancel_crop_and_folder_editor_leave_settings_and_original_untouched(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_CONFIG_HOME':d,'XDG_DATA_HOME':d}):
            path=Path(d)/'original.png';self.image(path);before=path.read_bytes()
            window=StartMenu();window.folder_settings.save(window.folder_settings.links)
            settings_before=window.folder_settings.path.read_bytes()
            with patch('menu.start_menu.QFileDialog.getOpenFileName',return_value=(str(path),'')),patch('menu.start_menu.PortraitCropDialog.exec',return_value=QDialog.DialogCode.Rejected):window.choose_portrait()
            self.assertEqual(window.folder_settings.path.read_bytes(),settings_before)
            editor=FolderEditor(window.folder_settings)
            with patch('menu.start_menu.QFileDialog.getOpenFileName',return_value=(str(path),'')),patch('menu.start_menu.PortraitCropDialog.exec',return_value=QDialog.DialogCode.Accepted):editor.choose_picture()
            editor.reject();self.assertEqual(window.folder_settings.path.read_bytes(),settings_before)
            self.assertEqual(path.read_bytes(),before)
            shiboken6.delete(editor);shiboken6.delete(window)
    def test_preview_drag_zoom_and_reset_are_non_destructive(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'original.png';self.image(path);before=path.read_bytes();dialog=PortraitCropDialog(path)
            dialog.zoom.setValue(200);dialog.preview.move_image(-200,0)
            self.assertEqual(dialog.crop()['zoom'],2)
            self.assertGreater(dialog.crop()['x'],.5)
            self.assertEqual(render_crop(dialog.preview.image,dialog.crop()).pixelColor(128,128),QColor('blue'))
            dialog.reset();self.assertEqual(dialog.crop(),dict(x=.5,y=.5,zoom=1))
            dialog.reject();self.assertEqual(path.read_bytes(),before);shiboken6.delete(dialog)

    def test_large_preview_is_bounded_and_jpeg_orientation_is_applied(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'wide.png';Image.new('RGB',(6000,40),'red').save(path)
            preview=load_image(path);self.assertLessEqual(max(preview.width(),preview.height()),4096)
            path=Path(d)/'rotated.jpg';image=Image.new('RGB',(200,100),'blue');exif=Image.Exif();exif[274]=6
            image.save(path,exif=exif)
            preview=load_image(path);self.assertEqual((preview.width(),preview.height()),(100,200))
