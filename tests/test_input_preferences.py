import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import input_preferences as ip


def device(kind='mouse', driver='evdev', key='a'*64):
    props={ip.ENABLED:dict(type=19,format=8,values=[1])}
    if kind=='mouse':props[ip.PROFILE]=dict(type=19,format=32,values=[0])
    return dict(key=key,name='Synthetic '+kind,id=7 if kind=='mouse' else 8,node='/dev/input/event7' if kind=='mouse' else '/dev/input/event8',kind=kind,driver=driver,props=props,enabled=True,usable_mouse=kind=='mouse')


class Backend:
    def __init__(self, devices):self.items=devices;self.writes=[];self.session='session-one';self.fail=False
    def devices(self):return copy.deepcopy(self.items)
    def token(self):return self.session
    def close(self):pass
    def write(self,dev,prop,value):
        self.writes.append((dev['key'],prop,value))
        if self.fail:raise RuntimeError('synthetic apply failure')
        target=next(d for d in self.items if d['key']==dev['key']);target['props'][prop]=copy.deepcopy(value)
        if prop==ip.ENABLED:target['enabled']=bool(value['values'][0])


class InputPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=ip.Preferences(Path(self.temp.name));self.mouse=device();self.pad=device('touchpad','libinput','b'*64)
        self.store.helper.parent.mkdir(parents=True)
        self.store.helper.write_bytes(Path(ip.__file__).read_bytes())
        self.backend=Backend([self.mouse,self.pad])
    def change(self,dev,enabled=True):
        raw,_=self.store.read()
        return self.store.run(self.backend,(dev['key'],dict(name=dev['name'],action='touchpad' if dev['kind']=='touchpad' else 'acceleration',enabled=enabled)),raw)
    def test_persistence_reapply_and_exact_opt_out(self):
        self.change(self.mouse)
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0xffffffff])
        again=ip.Preferences(self.store.home);again.run(self.backend)
        self.assertEqual(len(self.backend.writes),1)
        self.assertTrue(self.store.startup.exists())
        self.change(self.mouse,False)
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0])
        self.assertFalse(self.store.read()[1]['rules'][self.mouse['key']]['enabled'])
        self.assertEqual(self.store.read()[1]['receipts'],{})
        self.assertFalse(self.store.startup.exists())
    def test_new_session_restores_its_own_baseline(self):
        self.change(self.mouse);self.backend.session='session-two'
        self.mouse['props'][ip.PROFILE]['values']=[4]
        self.store.run(self.backend);self.change(self.mouse,False)
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[4])
    def test_touchpad_guard_and_external_mouse_unchanged(self):
        before=copy.deepcopy(self.mouse)
        self.change(self.pad)
        self.assertEqual(self.pad['props'][ip.ENABLED]['values'],[0]);self.assertEqual(self.mouse,before)
        self.change(self.pad,False)
        self.backend.items=[self.pad]
        self.assertIn('another enabled',self.change(self.pad)[0]);self.assertEqual(self.pad['props'][ip.ENABLED]['values'],[1])
    def test_virtual_or_disabled_mouse_does_not_satisfy_touchpad_guard(self):
        self.mouse['usable_mouse']=False
        self.assertIn('another enabled',self.change(self.pad)[0])
        self.assertEqual(self.pad['props'][ip.ENABLED]['values'],[1])
        self.mouse['usable_mouse']=True;self.mouse['enabled']=False
        self.assertIn('another enabled',self.change(self.pad)[0])

    def test_absent_ambiguous_unsupported_and_missing_property(self):
        self.change(self.mouse);self.backend.items=[]
        self.assertIn('absent',self.store.run(self.backend)[0])
        self.backend.items=[self.mouse,copy.deepcopy(self.mouse)]
        self.assertIn('ambiguous',self.store.run(self.backend)[0])
        self.backend.items=[self.mouse];self.mouse['driver']='libinput'
        self.assertIn('unsupported',self.store.run(self.backend)[0])
        self.mouse['driver']='evdev';self.mouse['props'].pop(ip.PROFILE)
        self.assertIsNone(ip.capability(self.mouse))
    def test_failure_preserves_config_and_receipt_for_safe_retry(self):
        self.backend.fail=True;self.assertIn('apply failed',self.change(self.mouse)[0])
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0])
        self.assertTrue(self.store.read()[1]['receipts'])
        self.backend.fail=False;self.store.run(self.backend)
        self.change(self.mouse,False);self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0])
    def test_external_property_edit_is_not_overwritten(self):
        self.change(self.mouse);self.mouse['props'][ip.PROFILE]['values']=[5]
        self.assertIn('changed elsewhere',self.change(self.mouse,False)[0])
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[5])
    def test_device_instance_change_refuses_restore(self):
        self.change(self.mouse);self.mouse['id']=90
        self.assertIn('instance changed',self.change(self.mouse,False)[0])
    def test_file_conflicts_and_invalid_receipts_refused(self):
        self.change(self.mouse);raw,data=self.store.read();data['version']=99
        self.store.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.store.run(self.backend)
        data['version']=1;data['receipts'][self.mouse['key']]['before']['values']=[-1]
        self.store.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.store.run(self.backend)
    def test_cas_autostart_and_symlink_conflicts(self):
        self.change(self.mouse)
        with self.assertRaisesRegex(RuntimeError,'Preferences changed'):
            self.store.run(self.backend,(self.mouse['key'],dict(name='mouse',action='acceleration',enabled=False)),None)
        self.store.startup.write_text('unrelated entry')
        with self.assertRaisesRegex(RuntimeError,'autostart'):self.change(self.mouse,False)
        self.store.path.unlink();self.store.path.symlink_to(self.store.home/'outside')
        with self.assertRaises(ValueError):self.store.read()
    def test_wayland_refused_before_connect(self):
        with patch.dict(os.environ,{'XDG_SESSION_TYPE':'wayland'}):
            with self.assertRaisesRegex(RuntimeError,'Wayland'):ip.XInput()
    def test_ui_render_and_apply_mock_only(self):
        from PySide6.QtWidgets import QApplication,QPushButton,QComboBox,QCheckBox,QLabel
        app=QApplication.instance() or QApplication([])
        with patch.object(ip,'XInput',return_value=self.backend):
            widget=ip.page(self.store.home);widget.resize(650,500);widget.show();app.processEvents()
            buttons=widget.findChildren(QPushButton)
            next(b for b in buttons if b.text()=='Refresh devices').click()
            widget.findChild(QCheckBox).setChecked(True)
            next(b for b in buttons if b.text().startswith('Save')).click()
            self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0xffffffff])
            self.assertTrue(any('applied and read back' in l.text() for l in widget.findChildren(QLabel)))
            widget.close()
