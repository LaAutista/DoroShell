import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cursor
from PIL import Image

class CursorTests(unittest.TestCase):
    def test_install_repeat_rollback_conflict_and_inheritance(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)
            gif=home/'test.gif'
            Image.new('RGBA',(10,10),'red').save(gif,save_all=True,append_images=[Image.new('RGBA',(10,10),'blue')],duration=[30,50],loop=0)
            config=home/'.config/lxqt/session.conf'; config.parent.mkdir(parents=True)
            original=b'[Mouse]\ncursor_theme=breeze_cursors\ncursor_size=30\n[General]\nwindow_manager=openbox\n'
            config.write_bytes(original)
            cursor.run(home,gif)
            self.assertFalse((home/'.icons').exists())
            cursor.run(home,gif,apply=True)
            cursor.run(home,gif,apply=True)
            root=home/'.icons'/cursor.THEME
            self.assertFalse((root/'cursors/default').exists())
            self.assertIn(b'Inherits=breeze_cursors',(root/'index.theme').read_bytes())
            im,hot=cursor.decode_cursor(root/'cursors/wait',30)
            self.assertEqual(im.size,(30,30)); self.assertEqual(hot,(15,15))
            installed=config.read_bytes(); config.write_bytes(installed+b'# personal edit\n')
            with self.assertRaises(RuntimeError): cursor.run(home,rollback=True)
            config.write_bytes(installed)
            cursor.run(home,rollback=True)
            self.assertEqual(config.read_bytes(),original)
            self.assertFalse((root/'cursors/wait').exists())
    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp); (home/'.local').symlink_to('/tmp')
            with self.assertRaises(RuntimeError): cursor.run(home,rollback=True)

    def test_pink_pointer_is_optional_and_switches_back_with_timing_preserved(self):
        import struct
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); gif=home/'spin.gif'
            Image.new('RGBA',(12,12),'red').save(gif,save_all=True,append_images=[Image.new('RGBA',(12,12),'blue')],duration=[40,80],loop=0)
            cursor.run(home,gif,apply=True,pink=True)
            path=home/'.icons'/cursor.THEME/'cursors'
            self.assertTrue((path/'default').exists())
            data=(path/'wait').read_bytes(); count=struct.unpack_from('<I',data,12)[0]
            delays=[]
            for i in range(count):
                _,_,offset=struct.unpack_from('<3I',data,16+i*12)
                delays.append(struct.unpack_from('<I',data,offset+32)[0])
            self.assertEqual(delays,[40,80]*len(cursor.SIZES))
            cursor.run(home,gif,apply=True,pink=False)
            self.assertFalse((path/'default').exists())
            self.assertFalse((path/'left_ptr').exists())
            cursor.run(home,rollback=True)

    def test_disabling_pink_restores_preexisting_theme_arrow(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            gif=home/'spin.gif'
            Image.new('RGBA',(8,8),'red').save(gif,save_all=True,append_images=[Image.new('RGBA',(8,8),'blue')],duration=50,loop=0)
            arrow=home/'.icons'/cursor.THEME/'cursors/left_ptr'
            arrow.parent.mkdir(parents=True)
            original=Path('/usr/share/icons/breeze_cursors/cursors/default').read_bytes()
            arrow.write_bytes(original)
            arrow.chmod(0o600)
            cursor.run(home,gif,apply=True,pink=True)
            self.assertNotEqual(arrow.read_bytes(), original)
            cursor.run(home,gif,apply=True,pink=False)
            self.assertEqual(arrow.read_bytes(),original)
            self.assertEqual(arrow.stat().st_mode & 0o777,0o600)
            cursor.run(home,rollback=True)
            self.assertEqual(arrow.read_bytes(),original)

    def test_apng_preserves_canvas_timing_and_skips_poster(self):
        import struct
        with tempfile.TemporaryDirectory() as tmp:
            animation=Path(tmp)/'busy.apng'
            poster=Image.new('RGBA',(30,30),'blue')
            frames=[]
            for x in (4,18):
                frame=Image.new('RGBA',(30,30))
                frame.paste('red',(x,6,x+4,10))
                frames.append(frame)
            poster.save(animation,format='PNG',save_all=True,default_image=True,
                        append_images=frames,duration=[30,40],loop=0)
            data=cursor.build(animation,Path('/usr/share/icons/breeze_cursors'))['wait']
            found=[]
            for i in range(struct.unpack_from('<I',data,12)[0]):
                _,size,pos=struct.unpack_from('<3I',data,16+i*12)
                if size==30:
                    w,h,xhot,yhot,delay=struct.unpack_from('<5I',data,pos+16)
                    pixels=struct.unpack_from('<900I',data,pos+36)
                    found.append((w,h,xhot,yhot,delay,pixels.index(0xffff0000)))
            self.assertEqual(found,[(30,30,15,15,30,6*30+4),(30,30,15,15,40,6*30+18)])
