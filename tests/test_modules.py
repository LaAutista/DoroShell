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

    def test_single_desktop_plan_repeat_restore_and_conflict(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'XDG_CONFIG_HOME':str(Path(d)/'.config')}):
            home=self.home(d)
            path=home/'.config/openbox/rc.xml'
            original='<openbox_config><desktops><number>4</number><firstdesk>3</firstdesk></desktops><other><number>7</number></other></openbox_config>'
            path.write_text(original); path.chmod(0o600)
            with patch.object(modules.subprocess,'run',side_effect=AssertionError('No live commands')), patch.object(modules.subprocess,'Popen',side_effect=AssertionError('No live processes')):
                modules.run(home,'single-desktop')
                self.assertEqual(path.read_text(),original)
                self.assertFalse((home/'.local/state/doroshell/single-desktop.json').exists())
                modules.run(home,'single-desktop',apply=True)
                applied=path.read_bytes()
                self.assertIn(b'<desktops><number>1</number><firstdesk>1</firstdesk>',applied)
                self.assertIn(b'<other><number>7</number></other>',applied)
                modules.run(home,'single-desktop',apply=True)
                self.assertEqual(path.read_bytes(),applied)
                path.write_bytes(applied.replace(b'<number>1</number>',b'<number>2</number>'))
                edited=path.read_bytes()
                with self.assertRaisesRegex(RuntimeError,'Personal edit'):
                    modules.run(home,'single-desktop',rollback=True)
                self.assertEqual(path.read_bytes(),edited)
                path.write_bytes(applied)
                modules.run(home,'single-desktop',rollback=True)
                self.assertEqual(path.read_text(),original)
                self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_all_modules_repeat_and_independent_rollback(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'XDG_CONFIG_HOME':str(Path(d)/'.config')}):
            home=self.home(d)
            (home/'.config/doroshell').mkdir()
            (home/'.config/doroshell/panel.conf').write_text('[panel1]\niconSize=24\n[doroshellTasks]\ntype=taskbar\nbuttonWidth=40\n')
            (home/'.local/state/doroshell').mkdir(parents=True)
            (home/'.local/state/doroshell/native-panel.json').write_text('{}')
            before={p.relative_to(home):p.read_bytes() for p in home.rglob('*') if p.is_file()}
            # Coordinated themes/Start shortcut have separate dependency/ordering tests.
            for m in (m for m in modules.MODULES if m not in ('theme','wallpaper','clipboard','start-shortcut')):
                modules.run(home,m,apply=True)
                modules.run(home,m,apply=True)
            # Same XML shared by two modules: roll back out of order.
            # Coordinated themes/Start shortcut have separate dependency/ordering tests.
            for m in (m for m in modules.MODULES if m not in ('theme','wallpaper','clipboard','start-shortcut')):
                modules.run(home,m,rollback=True)
            for p,data in before.items():
                self.assertEqual((home/p).read_bytes(),data,p)
            self.assertFalse((home/'.local/bin/doroshell-screenshot').exists())

    def test_personal_changes_conflicts_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            home=self.home(d)
            self.enterContext(patch.dict(os.environ,{'XDG_CONFIG_HOME':str(home/'.config')}))
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

    def test_renumbered_print_shortcut_keeps_backup_and_refuses_command_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=self.home(tmp)
            path=home/'.config/lxqt/globalkeyshortcuts.conf'
            original=path.read_text().replace('[Print.30]', '[Print.42]')
            modules.run(home,'screenshots',apply=True)
            moved=path.read_text().replace('[Print.30]', '[Print.42]')
            edited=moved.replace('doroshell-screenshot','another-command')
            path.write_text(edited)
            with self.assertRaisesRegex(RuntimeError,'renumbered'):
                modules.run(home,'screenshots',apply=True)
            self.assertEqual(path.read_text(),edited)
            path.write_text(moved)
            modules.run(home,'screenshots',apply=True)
            modules.run(home,'screenshots',rollback=True)
            self.assertEqual(path.read_text(),original)

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
