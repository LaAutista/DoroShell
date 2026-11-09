import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import modules

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
snap=load('snap',ROOT/'runtime/snap.py')
shot=load('shot',ROOT/'runtime/screenshot.py')

class ModulesTests(unittest.TestCase):
    def home(self,d):
        home=Path(d)
        (home/'.config/openbox').mkdir(parents=True)
        (home/'.config/lxqt').mkdir(parents=True)
        (home/'.config/openbox/rc.xml').write_text('<openbox_config><desktops><number>4</number></desktops><keyboard></keyboard></openbox_config>')
        (home/'.config/lxqt/panel.conf').write_text('[panel1]\nplugins=fancymenu, taskbar\n[taskbar]\nbuttonStyle=IconText\n')
        (home/'.config/lxqt/globalkeyshortcuts.conf').write_text('[Print.30]\nExec=old-shot\nEnabled=true\n')
        return home

    def test_all_modules_repeat_and_independent_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            home=self.home(d)
            before={p.relative_to(home):p.read_bytes() for p in home.rglob('*') if p.is_file()}
            for m in modules.MODULES:
                modules.run(home,m,apply=True)
                modules.run(home,m,apply=True)
            # Same XML shared by two modules: roll back out of order.
            for m in modules.MODULES:
                modules.run(home,m,rollback=True)
            for p,data in before.items():
                self.assertEqual((home/p).read_bytes(),data,p)
            self.assertFalse((home/'.local/bin/doroshell-screenshot').exists())

    def test_personal_changes_conflicts_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            home=self.home(d)
            modules.run(home,'screenshots',apply=True)
            conf=home/'.config/lxqt/globalkeyshortcuts.conf'
            conf.write_text(conf.read_text()+'\n[Other]\nKeep=yes\n')
            modules.run(home,'screenshots',rollback=True)
            self.assertIn('Keep=yes',conf.read_text())
            modules.run(home,'snapping',apply=True)
            rc=home/'.config/openbox/rc.xml'
            rc.write_text(rc.read_text().replace('doroshell-snap','personal-snap'))
            with self.assertRaises(RuntimeError): modules.run(home,'snapping',rollback=True)
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); (home/'.config').symlink_to('/tmp')
            with self.assertRaises(RuntimeError): modules.run(home,'dolphin',apply=True)

    def test_geometry_odd_width_and_monitor_panel(self):
        self.assertEqual(snap.half((1920,20,1921,1060),'left'),(1920,20,960,1060))
        self.assertEqual(snap.half((1920,20,1921,1060),'right'),(2880,20,961,1060))
        bottom=[0,0,0,30,0,0,0,0,0,0,0,1919]
        self.assertEqual(snap.workarea((0,0,1920,1080),[bottom],3840,1080),(0,0,1920,1050))
        self.assertEqual(snap.workarea((1920,0,1920,1080),[bottom],3840,1080),(1920,0,1920,1080))

    def test_screenshot_only_completed_decodable_file(self):
        from PySide6.QtGui import QImage,QColor
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); out=shot.capture_config(root)
            self.assertIsNone(shot.completed_image(out,0))
            image=QImage(50,30,QImage.Format.Format_ARGB32);image.fill(QColor('pink'))
            image.save(str(out/'capture.png'))
            self.assertEqual(shot.completed_image(out,0).size(),image.size())
            self.assertIsNone(shot.completed_image(out,1))
            (out/'capture.png').write_bytes(b'partial')
            self.assertIsNone(shot.completed_image(out,0))

    def test_duplicate_shortcuts_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as d:
            home=self.home(d)
            cfg=home/'.config/lxqt/globalkeyshortcuts.conf'
            cfg.write_text(cfg.read_text()+'[Print.31]\nExec=another\n')
            with self.assertRaises(RuntimeError): modules.run(home,'screenshots',apply=True)
            self.assertFalse((home/'.local/bin/doroshell-screenshot').exists())
