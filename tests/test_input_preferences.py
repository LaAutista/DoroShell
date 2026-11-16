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


def libinput_mouse(flags=(1,0,0), available=(1,1,1), key='c'*64):
    dev=device(key=key);dev['driver']='libinput';dev['props'].pop(ip.PROFILE)
    dev['props'][ip.LIBINPUT_PROFILE]=dict(type=19,format=8,values=list(flags))
    dev['props'][ip.LIBINPUT_AVAILABLE]=dict(type=19,format=8,values=list(available))
    return dev


class InputPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=ip.Preferences(Path(self.temp.name));self.mouse=device();self.pad=device('touchpad','libinput','b'*64)
        self.store.helper.parent.mkdir(parents=True)
        self.store.helper.write_bytes(Path(ip.__file__).read_bytes())
        self.backend=Backend([self.mouse,self.pad])
        # Never spawn a real watcher from tests.
        spawn=patch.object(ip.Preferences,'start_watcher');self.spawned=spawn.start();self.addCleanup(spawn.stop)
        popen=patch.object(ip.subprocess,'Popen',side_effect=AssertionError('test spawned a process'));popen.start();self.addCleanup(popen.stop)
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
    def test_reconnected_instance_archives_receipt_and_reapplies(self):
        self.change(self.mouse);old=self.store.read()[1]['receipts'][self.mouse['key']]
        self.mouse['id']=90;self.mouse['props'][ip.PROFILE]['values']=[0]  # New instance at driver default.
        self.assertIn('reconnected',self.store.run(self.backend)[0])
        receipt=self.store.read()[1]['receipts'][self.mouse['key']]
        self.assertEqual((receipt['id'],receipt['before']['values']),(90,[0]))
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0xffffffff])
        archived=[json.loads(f.read_text()) for f in (self.store.home/'.local/state/doroshell/input-restoration').iterdir()]
        self.assertEqual([(a['reason'],a['receipt']) for a in archived],[('device-reconnected',old)])
        self.mouse['id']=91;self.mouse['props'][ip.PROFILE]['values']=[0];writes=len(self.backend.writes)
        self.assertIn('reconnected',self.change(self.mouse,False)[0])
        self.assertEqual(len(self.backend.writes),writes);self.assertEqual(self.store.read()[1]['receipts'],{})
    def test_all_mice_switch_covers_current_and_later_mice_and_restores(self):
        lib=libinput_mouse();self.backend.items=[self.mouse,self.pad]
        raw,_=self.store.read();self.store.run(self.backend,expected=raw,all_mice=True)
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0xffffffff])
        self.assertEqual(self.pad['props'][ip.ENABLED]['values'],[1])  # Touchpads untouched.
        self.assertTrue(self.store.startup.exists())
        self.backend.items.append(lib);self.store.run(self.backend)  # Hotplug pass.
        self.assertEqual(lib['props'][ip.LIBINPUT_PROFILE]['values'],[0,1,0])
        rules=self.store.read()[1]['rules'];self.assertTrue(rules[lib['key']]['auto'])
        raw,_=self.store.read();self.store.run(self.backend,expected=raw,all_mice=False)
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0])
        self.assertEqual(lib['props'][ip.LIBINPUT_PROFILE]['values'],[1,0,0])
        self.assertEqual(self.store.read()[1]['receipts'],{});self.assertFalse(self.store.startup.exists())
    def test_explicit_device_choice_overrides_all_mice(self):
        raw,_=self.store.read();self.store.run(self.backend,expected=raw,all_mice=True)
        self.change(self.mouse,False)  # Explicit opt-out for this mouse.
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0])
        self.store.run(self.backend);self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0])
        self.assertNotIn('auto',self.store.read()[1]['rules'][self.mouse['key']])
        raw,_=self.store.read();self.store.run(self.backend,expected=raw,all_mice=False);self.store.run(self.backend,expected=self.store.read()[0],all_mice=True)
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0])
    def test_all_mice_skips_ambiguous_and_stop_clears_switch(self):
        twin=copy.deepcopy(self.mouse);twin['id']=70;self.backend.items=[self.mouse,twin,self.pad]
        raw,_=self.store.read();self.store.run(self.backend,expected=raw,all_mice=True)
        self.assertNotIn(self.mouse['key'],self.store.read()[1]['rules'])
        self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0])
        raw,_=self.store.read();self.store.run(self.backend,expected=raw,stop=True)
        self.assertFalse(self.store.read()[1]['all_mice']);self.assertFalse(self.store.startup.exists())
    def test_invalid_all_mice_and_auto_values_refused(self):
        raw,data=self.store.read();data['all_mice']='yes';self.store.write(self.store.path,json.dumps(data).encode())
        with self.assertRaises(ValueError):self.store.read()
        data['all_mice']=True;data['rules']['d'*64]=dict(name='x',action='touchpad',enabled=True,auto=True)
        self.store.write(self.store.path,json.dumps(data).encode())
        with self.assertRaises(ValueError):self.store.read()
        raw,_=self.store.read() if False else (self.store.path.read_bytes(),None)
        with self.assertRaises(ValueError):self.store.run(self.backend,expected=raw,all_mice='on')
    @staticmethod
    def event(flags,info=(),kind=None,extension=131):
        from Xlib.ext import ge, xinput
        class Info:
            def __init__(self,deviceid,flags):self.deviceid=deviceid;self.flags=flags
        return type('Event',(),{'type':ge.GenericEventCode if kind is None else kind,'extension':extension,'evtype':xinput.HierarchyChanged,
                                'data':type('D',(),{'flags':flags,'info':[Info(*i) for i in info]})()})()
    def fake_display(self,script):
        """script: list of steps; each step is a list of events delivered together, or a callable run at that tick."""
        from Xlib.ext import xinput
        test=self
        class Display:
            def __init__(self):self.queue=[];self.script=list(script);self.selected=None;self.ticks=0
            def query_extension(self,name):
                test.assertEqual(name,xinput.extname);return type('E',(),{'major_opcode':131})()
            def screen(self):
                d=self;return type('S',(),{'root':type('R',(),{'xinput_select_events':lambda _,m:setattr(d,'selected',m)})()})()
            def sync(self):pass
            def fileno(self):return -1
            def pending_events(self):return len(self.queue)
            def next_event(self):return self.queue.pop(0)
            def tick(self,*args):
                self.ticks+=1
                if self.ticks>50:raise AssertionError('watcher did not exit')
                if self.script:
                    step=self.script.pop(0)
                    if callable(step):step()
                    else:self.queue.extend(step)
                return ([1] if self.queue else [],[],[])
        return Display()
    def watch(self,display):
        self.backend.display=display
        with patch.object(ip.select,'select',side_effect=display.tick),patch.object(ip.time,'sleep'):
            self.store.watch(self.backend)
    def opt_out(self):
        raw,_=self.store.read();ip.Preferences.run(self.store,self.backend,expected=raw,stop=True)
    def assert_watch_lock_released(self):
        import fcntl
        with (self.store.home/'.local/state/doroshell/input-watch.lock').open('a') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def test_watcher_reapplies_on_device_added_and_exits_when_unmanaged(self):
        from Xlib import X
        from Xlib.ext import xinput
        lib=libinput_mouse()
        raw,_=self.store.read();self.store.run(self.backend,expected=raw,all_mice=True)
        Event=self.event
        display=self.fake_display([
            [Event(xinput.SlaveAdded,kind=X.KeyPress),Event(xinput.SlaveAdded,extension=99),Event(xinput.SlaveAdded)],
            lambda:None, self.opt_out])
        self.backend.items.append(lib)  # Present for the pass the SlaveAdded event triggers.
        self.watch(display)
        self.assertEqual(display.selected,[(xinput.AllDevices,xinput.HierarchyChangedMask)])
        self.assertEqual(self.store.read()[1]['receipts'],{})
        self.assertEqual(lib['props'][ip.LIBINPUT_PROFILE]['values'],[1,0,0])  # Applied, then restored on opt-out.
        self.assertTrue(any(w[0]==lib['key'] and w[2]['values']==[0,1,0] for w in self.backend.writes))
        self.assert_watch_lock_released()
    def test_watcher_exits_after_idle_opt_out_without_events(self):
        raw,_=self.store.read();self.store.run(self.backend,expected=raw,all_mice=True)
        display=self.fake_display([lambda:None,self.opt_out])
        self.watch(display)
        self.assertLessEqual(display.ticks,3)
        self.assert_watch_lock_released()
    def test_watcher_retries_pending_pass_after_lock_contention(self):
        raw,_=self.store.read();self.store.run(self.backend,expected=raw,all_mice=True)
        lib=libinput_mouse();self.backend.items.append(lib)
        original=ip.Preferences.run;calls=[]
        def busy(*a,**k):
            calls.append(1)
            if len(calls)<=12:raise BlockingIOError
            return original(self.store,*a,**k)
        display=self.fake_display([lambda:None]*14+[self.opt_out])
        with patch.object(self.store,'run',side_effect=busy):
            self.watch(display)
        self.assertGreater(len(calls),12)
        self.assertTrue(any(w[0]==lib['key'] and w[2]['values']==[0,1,0] for w in self.backend.writes))
    def test_removed_instance_with_reused_id_and_node_keeps_replacement_baseline(self):
        from Xlib.ext import xinput
        lib=libinput_mouse((0,0,1));self.backend.items=[lib,self.pad];self.change(lib)
        self.assertEqual(lib['props'][ip.LIBINPUT_PROFILE]['values'],[0,1,0])
        # Replacement reuses key, XInput ID and event node, and starts already flat.
        def replace():
            lib['props'][ip.LIBINPUT_PROFILE]['values']=[0,1,0]
        Event=self.event
        display=self.fake_display([[Event(xinput.SlaveRemoved,[(lib['id'],xinput.SlaveRemoved)]),Event(xinput.SlaveAdded,[(lib['id'],xinput.SlaveAdded)])],
                                         lambda:None,self.opt_out])
        writes=len(self.backend.writes);replace();self.watch(display)
        self.assertEqual(lib['props'][ip.LIBINPUT_PROFILE]['values'],[0,1,0])  # Never restored to the old custom.
        self.assertEqual(len(self.backend.writes),writes)
        archived=[json.loads(f.read_text())['reason'] for f in (self.store.home/'.local/state/doroshell/input-restoration').iterdir()]
        self.assertEqual(archived,['device-removed'])
    def test_strict_boolean_schema_for_all_mice_and_auto(self):
        _,data=self.store.read()
        for value in (1,0,None,'true'):
            bad=copy.deepcopy(data);bad['all_mice']=value;self.store.write(self.store.path,json.dumps(bad).encode())
            with self.assertRaises(ValueError,msg=value):self.store.read()
        for value in (1,None,False):
            bad=copy.deepcopy(data);bad['rules']['d'*64]=dict(name='x',action='acceleration',enabled=True,auto=value)
            self.store.write(self.store.path,json.dumps(bad).encode())
            with self.assertRaises(ValueError,msg=value):self.store.read()
    def test_second_watcher_exits_without_touching_devices(self):
        import fcntl
        lock=self.store.home/'.local/state/doroshell/input-watch.lock';lock.parent.mkdir(parents=True,exist_ok=True)
        with lock.open('a') as held:
            fcntl.flock(held,fcntl.LOCK_EX)
            self.backend.display=None
            self.assertIsNone(self.store.watch(self.backend))
        self.assertEqual(self.backend.writes,[])
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
    def test_libinput_flat_apply_and_exact_restore(self):
        for flags,available,flat in (((1,0,0),(1,1,1),[0,1,0]),((1,0),(1,1),[0,1])):
            mouse=libinput_mouse(flags,available);self.backend.items=[mouse,self.pad]
            self.assertEqual(ip.capability(mouse),('acceleration',ip.LIBINPUT_PROFILE,flat))
            self.assertIn('applied and read back',self.change(mouse)[0])
            self.assertEqual(mouse['props'][ip.LIBINPUT_PROFILE]['values'],flat)
            receipt=self.store.read()[1]['receipts'][mouse['key']]
            self.assertEqual((receipt['property'],receipt['before']['values']),(ip.LIBINPUT_PROFILE,list(flags)))
            self.assertIn('prior property restored',self.change(mouse,False)[0])
            self.assertEqual(mouse['props'][ip.LIBINPUT_PROFILE]['values'],list(flags))
            self.assertEqual(self.store.read()[1]['receipts'],{})
    def test_libinput_without_flat_or_malformed_is_unsupported(self):
        self.assertIsNone(ip.capability(libinput_mouse(available=(1,0,1))))
        self.assertIsNone(ip.capability(libinput_mouse(flags=(1,0,0),available=(1,1))))
        self.assertIsNone(ip.capability(libinput_mouse(flags=(2,0,0))))
        pad=libinput_mouse();pad['kind']='touchpad'
        self.assertEqual(ip.capability(pad)[0],'touchpad')
        evdev=libinput_mouse();evdev['driver']='evdev'
        self.assertIsNone(ip.capability(evdev))
    def test_libinput_tampered_receipts_refused(self):
        mouse=libinput_mouse();self.backend.items=[mouse,self.pad];self.change(mouse)
        _,data=self.store.read();good=copy.deepcopy(data);r=data['receipts'][mouse['key']]
        for field,values in (('after',[1,0,0]),('after',[0,1]),('before',[1,0]),('before',[2,0,0])):
            data=copy.deepcopy(good);data['receipts'][mouse['key']][field]['values']=values
            self.store.path.write_text(json.dumps(data))
            with self.assertRaises(ValueError,msg=(field,values)):self.store.read()
        data=copy.deepcopy(good);data['rules'][mouse['key']]['action']='touchpad'
        self.store.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.store.read()
        self.store.path.write_text(json.dumps(good));self.store.read()
    def test_libinput_restore_refuses_withdrawn_baseline_profile(self):
        mouse=libinput_mouse((0,0,1));self.backend.items=[mouse,self.pad];self.change(mouse)
        self.assertEqual(mouse['props'][ip.LIBINPUT_PROFILE]['values'],[0,1,0])
        mouse['props'][ip.LIBINPUT_AVAILABLE]['values']=[1,1,0];writes=len(self.backend.writes)
        self.assertIn('no longer offered',self.change(mouse,False)[0])
        self.assertEqual(len(self.backend.writes),writes)
        self.assertEqual(mouse['props'][ip.LIBINPUT_PROFILE]['values'],[0,1,0])
        self.assertTrue(self.store.read()[1]['receipts'])
    def test_libinput_enabled_must_select_one_advertised_profile(self):
        self.assertIsNone(ip.capability(libinput_mouse(flags=(1,1,0))))
        self.assertIsNone(ip.capability(libinput_mouse(flags=(0,0,0))))
        self.assertIsNone(ip.capability(libinput_mouse(flags=(0,0,1),available=(1,1,0))))
        mouse=libinput_mouse();self.backend.items=[mouse,self.pad];self.change(mouse)
        _,data=self.store.read()
        data['receipts'][mouse['key']]['before']['values']=[1,1,0]
        self.store.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.store.read()
    def test_xinput_write_rechecks_fresh_device_before_request(self):
        class Display:
            def __init__(self):self.changes=[]
            def intern_atom(self,name):return name
            def xinput_change_device_property(self,*args):self.changes.append(args)
            def sync(self):pass
        snapshot=libinput_mouse((0,0,1))
        for fresh_flags,fresh_available,message in (((0,1,0),(1,1,0),'no longer offered'),((1,0,0),(1,1,1),'changed elsewhere')):
            backend=object.__new__(ip.XInput);backend.display=Display()
            fresh=copy.deepcopy(snapshot);fresh['props'][ip.LIBINPUT_PROFILE]['values']=list(fresh_flags)
            fresh['props'][ip.LIBINPUT_AVAILABLE]['values']=list(fresh_available)
            stale=copy.deepcopy(snapshot);stale['props'][ip.LIBINPUT_PROFILE]['values']=list(fresh_flags) if message=='no longer offered' else [0,1,0]
            backend.devices=lambda f=fresh:[copy.deepcopy(f)]
            with self.assertRaisesRegex(RuntimeError,message):
                backend.write(stale,ip.LIBINPUT_PROFILE,dict(type=19,format=8,values=[0,0,1]))
            self.assertEqual(backend.display.changes,[])
    def test_libinput_flat_withdrawn_after_apply_is_not_forced(self):
        mouse=libinput_mouse();self.backend.items=[mouse,self.pad];self.change(mouse)
        mouse['props'][ip.LIBINPUT_AVAILABLE]['values']=[1,0,1]
        self.assertIn('unsupported',self.store.run(self.backend)[0])
        self.assertTrue(self.store.read()[1]['receipts'])
    def test_wayland_refused_before_connect(self):
        with patch.dict(os.environ,{'XDG_SESSION_TYPE':'wayland'}):
            with self.assertRaisesRegex(RuntimeError,'Wayland'):ip.XInput()
    def test_ui_render_and_apply_mock_only(self):
        from PySide6.QtWidgets import QApplication,QPushButton,QComboBox,QCheckBox,QLabel
        app=QApplication.instance() or QApplication([])
        with patch.object(ip,'XInput',return_value=self.backend), patch('input_diagnostics.read_configuration',return_value=([],set())):
            widget=ip.page(self.store.home);widget.resize(650,500);widget.show();app.processEvents()
            buttons=widget.findChildren(QPushButton)
            next(b for b in buttons if b.text()=='Refresh devices').click()
            widget.findChild(QCheckBox).setChecked(True)
            next(b for b in buttons if b.text().startswith('Save')).click()
            self.assertEqual(self.mouse['props'][ip.PROFILE]['values'],[0xffffffff])
            self.assertTrue(any('applied and read back' in l.text() for l in widget.findChildren(QLabel)))
            widget.close()
