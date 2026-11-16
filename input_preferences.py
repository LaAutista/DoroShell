#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Opt-in per-device X11 preferences; no driver switching or system configuration."""
import fcntl
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import time
import uuid

PROFILE = 'Device Accel Profile'
ENABLED = 'Device Enabled'
LIBINPUT_PROFILE = 'libinput Accel Profile Enabled'
LIBINPUT_AVAILABLE = 'libinput Accel Profiles Available'
MARKER = '_DOROSHELL_INPUT_INSTANCE'  # Private device property; a replacement device instance never has it.


def marker_of(device):
    return bytes(device['props'].get(MARKER, {}).get('values', [])).decode('ascii', errors='replace')


def flat(length):
    # libinput profile flags: adaptive, flat[, custom on libinput >= 1.23].
    return [0, 1] + [0] * (length - 2)


def valid_flags(value):
    values = value.get('values') if isinstance(value, dict) else None
    return (isinstance(values, list) and value.get('format') == 8 and type(value.get('type')) is int
            and len(values) in (2, 3) and all(type(v) is int and v in (0, 1) for v in values))


def valid_value(prop, value):
    if not isinstance(value, dict) or type(value.get('type')) is not int or not isinstance(value.get('values'), list):
        return False
    values = value['values']
    if not all(type(v) is int for v in values):
        return False
    if prop == LIBINPUT_PROFILE:
        return valid_flags(value) and sum(values) == 1  # Exactly one selected profile.
    return (value.get('format') == (32 if prop == PROFILE else 8) and len(values) == 1
            and 0 <= values[0] <= (0xffffffff if prop == PROFILE else 1))


def target(prop, value):
    return flat(len(value['values'])) if prop == LIBINPUT_PROFILE else [0xffffffff] if prop == PROFILE else [0]


def property_values(reply):
    fmt, values = reply.value
    return dict(type=reply.type, format=fmt, values=list(values))


class XInput:
    def __init__(self):
        if os.environ.get('XDG_SESSION_TYPE') != 'x11' or not os.environ.get('DISPLAY'):
            raise RuntimeError('Requires an X11 session; Wayland is unsupported.')
        from Xlib import display
        self.display = display.Display()

    def close(self):
        self.display.close()

    def token(self):
        from Xlib import X
        root = self.display.screen().root
        atom = self.display.intern_atom('_DOROSHELL_INPUT_SESSION')
        prop = root.get_full_property(atom, X.AnyPropertyType)
        if prop is None:
            root.change_property(atom, self.display.intern_atom('STRING'), 8, uuid.uuid4().hex.encode())
            self.display.sync()
            prop = root.get_full_property(atom, X.AnyPropertyType)
        return bytes(prop.value).decode('ascii')

    def devices(self):
        from Xlib.ext import xinput
        result = []
        for dev in self.display.xinput_query_device(xinput.AllDevices).devices:
            if dev.use != xinput.SlavePointer:
                continue
            props = {}
            for atom in self.display.xinput_list_device_properties(dev.deviceid).atoms:
                name = self.display.get_atom_name(atom)
                reply = self.display.xinput_get_device_property(dev.deviceid, atom, 0, 0, 1024, False)
                props[name] = property_values(reply)
            node = bytes(props.get('Device Node', {}).get('values', [])).decode('utf-8', errors='replace').rstrip('\0')
            if not re.fullmatch(r'/dev/input/event[0-9]+', node):
                continue
            proc = subprocess.run(['udevadm', 'info', '--query=property', '--name='+node],
                                  capture_output=True, text=True, timeout=3, check=True)
            udev = dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)
            kind = ('touchpad' if udev.get('ID_INPUT_TOUCHPAD') == '1' else
                    'mouse' if udev.get('ID_INPUT_MOUSE') == '1' and
                    udev.get('ID_INPUT_KEYBOARD') != '1' and udev.get('ID_INPUT_TOUCHSCREEN') != '1' else 'other')
            identity = [dev.name, udev.get('ID_SERIAL', ''), udev.get('ID_PATH', ''),
                        udev.get('ID_VENDOR_ID', ''), udev.get('ID_MODEL_ID', '')]
            # Refuse a weak identity rather than persist an unstable numerical XInput ID.
            if not identity[1] and not identity[2]:
                kind = 'other'
            key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            driver = ('evdev' if any(p.startswith('Evdev ') for p in props) else
                      'libinput' if any(p.startswith('libinput ') for p in props) else
                      'synaptics' if any(p.startswith('Synaptics ') for p in props) else 'unknown')
            result.append(dict(key=key, name=dev.name, id=dev.deviceid, node=node,
                               kind=kind, driver=driver, props=props, enabled=bool(dev.enabled),
                               usable_mouse=kind=='mouse' and udev.get('ID_BUS') in ('usb','bluetooth') and '/virtual/' not in udev.get('DEVPATH','') and 'libinput Calibration Matrix' not in props))
        return result

    def write(self, device, name, value):
        from Xlib import X
        # Re-resolve identity immediately before writing; IDs are never trusted from disk.
        devices = self.devices()
        matches = [d for d in devices if d['key'] == device['key']]
        if len(matches) != 1 or matches[0]['id'] != device['id']:
            raise RuntimeError('Device changed before apply; refresh and retry.')
        fresh = matches[0]['props']
        if marker_of(matches[0]) != marker_of(device):
            raise RuntimeError('Device instance was replaced before apply; refresh and retry.')
        if fresh.get(name) != device['props'].get(name):
            raise RuntimeError('Property changed elsewhere before apply; refresh and retry.')
        if name == LIBINPUT_PROFILE and not fresh.get(LIBINPUT_AVAILABLE, {}).get('values', [0] * 3)[value['values'].index(1)]:
            raise RuntimeError('Requested profile is no longer offered by the driver; not written.')
        if name == ENABLED and value['values'] == [0] and device['kind'] == 'touchpad':
            if not any(d.get('usable_mouse',False) and d['enabled'] and d['props'].get(ENABLED,{}).get('values')==[1] for d in devices):
                raise RuntimeError('The other mouse disappeared; touchpad disable refused.')
        self.display.xinput_change_device_property(device['id'], self.display.intern_atom(name),
            value['type'], X.PropModeReplace, (value['format'], value['values']))
        self.display.sync()
        reply = self.display.xinput_get_device_property(device['id'], self.display.intern_atom(name), 0, 0, 1024, False)
        if property_values(reply) != value:
            raise RuntimeError('Driver did not accept the requested property; preference remains configured.')

    def mark(self, device, marker):
        from Xlib import X
        atom = self.display.intern_atom(MARKER)
        self.display.xinput_change_device_property(device['id'], atom, self.display.intern_atom('STRING'),
            X.PropModeReplace, (8, marker.encode('ascii')))
        self.display.sync()
        reply = self.display.xinput_get_device_property(device['id'], atom, 0, 0, 64, False)
        if bytes(property_values(reply)['values']).decode('ascii', errors='replace') != marker:
            raise RuntimeError('Driver did not accept the DoroShell instance marker; not applied.')


def capability(device):
    enabled = device['props'].get(ENABLED, {})
    profile = device['props'].get(PROFILE, {})
    if device['kind'] == 'touchpad' and enabled.get('format') == 8 and enabled.get('values') in ([0], [1]):
        return 'touchpad', ENABLED, [0]
    if device['kind'] == 'mouse' and device['driver'] == 'evdev' and profile.get('format') == 32 and len(profile.get('values', [])) == 1:
        return 'acceleration', PROFILE, [0xffffffff]  # Xorg profile -1: no velocity-dependent acceleration.
    current = device['props'].get(LIBINPUT_PROFILE, {})
    available = device['props'].get(LIBINPUT_AVAILABLE, {})
    if (device['kind'] == 'mouse' and device['driver'] == 'libinput' and valid_value(LIBINPUT_PROFILE, current)
            and valid_flags(available) and len(available['values']) == len(current['values'])
            and available['values'][1] == 1 and available['values'][current['values'].index(1)] == 1):
        return 'acceleration', LIBINPUT_PROFILE, flat(len(current['values']))
    return None


def safe(path, home):
    if not path.is_relative_to(home):
        raise ValueError('Preference path escapes HOME.')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('Refusing symlinked preference path.')
        if part == home:
            break


class Preferences:
    def __init__(self, home):
        self.home = Path(home).absolute()
        self.path = self.home/'.config/doroshell/input-preferences.json'
        self.startup = self.home/'.config/autostart/doroshell-input.desktop'
        self.helper = self.home/'.local/share/doroshell/toolkit/input_preferences.py'

    def read(self):
        safe(self.path, self.home)
        raw = self.path.read_bytes() if self.path.exists() else None
        data = json.loads(raw) if raw is not None else dict(version=1, rules={}, receipts={})
        if (not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1
                or not isinstance(data.get('rules'), dict) or not isinstance(data.get('receipts'), dict)
                or data.get('startup') not in (None, 'pending', 'installed', 'removing')
                or ('all_mice' in data and type(data['all_mice']) is not bool)):
            raise ValueError('Unsupported input preferences; existing file preserved.')
        for key, rule in data['rules'].items():
            if (not re.fullmatch('[0-9a-f]{64}', key) or not isinstance(rule, dict)
                    or not isinstance(rule.get('name'), str) or rule.get('action') not in ('acceleration','touchpad')
                    or type(rule.get('enabled')) is not bool
                    or ('auto' in rule and (rule['auto'] is not True or rule['action'] != 'acceleration'))):
                raise ValueError('Invalid saved input preference.')
        for key, receipt in data['receipts'].items():
            if key not in data['rules'] or not isinstance(receipt, dict):
                raise ValueError('Invalid input restoration record.')
            prop = receipt.get('property')
            allowed = (PROFILE, LIBINPUT_PROFILE) if data['rules'][key]['action']=='acceleration' else (ENABLED,)
            if (prop not in allowed or not isinstance(receipt.get('token'), str) or type(receipt.get('id')) is not int or not isinstance(receipt.get('node'), str)
                    or ('marker' in receipt and not (isinstance(receipt['marker'], str) and re.fullmatch('[0-9a-f]{32}', receipt['marker'])))):
                raise ValueError('Invalid input restoration identity.')
            for field in ('before','after'):
                if not valid_value(prop, receipt.get(field)):
                    raise ValueError('Invalid saved input property.')
            if (receipt['after']['values'] != target(prop, receipt['after'])
                    or len(receipt['before']['values']) != len(receipt['after']['values'])
                    or receipt['before']['type'] != receipt['after']['type']):
                raise ValueError('Invalid input restoration target.')
        return raw, data

    def write(self, path, data):
        safe(path, self.home)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name+'.'+uuid.uuid4().hex)
        try:
            with temp.open('xb') as stream:
                os.chmod(temp, 0o600); stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    @contextmanager
    def locked(self):
        lock = self.path.with_suffix('.lock'); safe(lock, self.home)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def startup_payload(self):
        def quote(value):
            return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
        return ('[Desktop Entry]\nType=Application\nName=DoroShell input preferences\nExec="/usr/bin/python" '+quote(self.helper)+' --login\nOnlyShowIn=LXQt;\n').encode()

    def check_startup(self, data):
        safe(self.startup, self.home)
        if self.startup.exists():
            if (not data.get('startup') or self.startup.read_bytes() != self.startup_payload()
                    or self.startup.stat().st_mode & 0o777 != 0o600):
                raise RuntimeError('Input autostart entry is unowned or changed; preserve it before retrying.')
        elif data.get('startup') == 'installed':
            raise RuntimeError('Input autostart entry was removed elsewhere; restore it before retrying.')

    def autostart(self, data, needed):
        self.check_startup(data)
        if needed:
            safe(self.helper, self.home)
            if not self.helper.is_file():
                raise RuntimeError('Install/update the DoroShell menu toolkit before saving input preferences.')
            if data.get('startup') == 'installed': return
            data['startup'] = 'pending'; self.write(self.path, json.dumps(data).encode())
            self.write(self.startup, self.startup_payload())
            data['startup'] = 'installed'; self.write(self.path, json.dumps(data).encode())
        elif data.get('startup'):
            data['startup'] = 'removing'; self.write(self.path, json.dumps(data).encode())
            self.check_startup(data); self.startup.unlink(missing_ok=True)
            data['startup'] = None; self.write(self.path, json.dumps(data).encode())

    def require_inactive(self):
        """Installer preflight only: never connect to X11 or change devices."""
        _, data = self.read(); self.check_startup(data)
        if any(r['enabled'] for r in data['rules'].values()) or data['receipts'] or data.get('startup'):
            raise RuntimeError('Input preferences still need their helper. Use Mouse & Touchpad → Stop managing and restore; '
                               'absent/unsupported devices or conflicts retain receipts and block removal. No device was changed.')

    def archive_receipt(self, key, rule, receipt, reason='previous-x-server-session'):
        payload = json.dumps(dict(reason=reason, key=key, rule=rule, receipt=receipt), sort_keys=True).encode()
        path = self.home/'.local/state/doroshell/input-restoration'/(hashlib.sha256(payload).hexdigest()+'.json')
        safe(path, self.home)
        if path.exists():
            if path.read_bytes() != payload or path.stat().st_mode & 0o777 != 0o600:
                raise RuntimeError('Archived input restoration evidence changed; preserve it before retrying.')
        else: self.write(path, payload)

    @staticmethod
    def needed(data):
        return bool(data.get('all_mice')) or any(r['enabled'] for r in data['rules'].values()) or bool(data['receipts'])

    def run(self, backend, change=None, expected=None, stop=False, all_mice=None):
        with self.locked():
            raw, data = self.read()
            self.check_startup(data)
            if change is not None or stop or all_mice is not None:
                if raw != expected:
                    raise RuntimeError('Preferences changed elsewhere; refresh before saving.')
                if stop:
                    for rule in data['rules'].values(): rule['enabled'] = False
                    data['all_mice'] = False
                elif all_mice is not None:
                    if type(all_mice) is not bool:
                        raise ValueError('Invalid input request.')
                    data['all_mice'] = all_mice
                else:
                    key, rule = change
                    if (not isinstance(key, str) or not re.fullmatch('[0-9a-f]{64}', key) or not isinstance(rule, dict)
                            or not isinstance(rule.get('name'), str) or rule.get('action') not in ('acceleration','touchpad')
                            or type(rule.get('enabled')) is not bool):
                        raise ValueError('Invalid input request.')
                    if key in data['receipts'] and rule['action'] != data['rules'][key]['action']:
                        raise ValueError('Restore the saved action before changing it.')
                    data['rules'][key] = dict(name=rule['name'], action=rule['action'], enabled=rule['enabled'])  # Explicit choice overrides all-mice.
            # Automatic all-mice rules follow the switch; explicit per-device rules are left alone.
            for rule in data['rules'].values():
                if rule.get('auto'): rule['enabled'] = bool(data.get('all_mice'))
            needed = self.needed(data)
            self.autostart(data, needed)
            if change is not None or stop or all_mice is not None: self.write(self.path, json.dumps(data).encode())
            if not needed:
                return ['No managed input changes remain. Saved choices and archived evidence are retained.']
            devices = backend.devices()
            token = backend.token()
            messages = []
            if data.get('all_mice'):
                for dev in devices:
                    cap = capability(dev)
                    if cap and cap[0] == 'acceleration' and dev['key'] not in data['rules'] and sum(d['key'] == dev['key'] for d in devices) == 1:
                        data['rules'][dev['key']] = dict(name=dev['name'], action='acceleration', enabled=True, auto=True)
            for key, rule in data['rules'].items():
                receipt = data['receipts'].get(key)
                if receipt and receipt['token'] != token:
                    self.archive_receipt(key, rule, receipt)
                    receipt = None; data['receipts'].pop(key)
                    messages.append(rule['name']+': previous-session restoration evidence archived; no old value forced onto this session.')
                if not rule['enabled'] and not receipt:
                    messages.append(rule['name']+': unmanaged; no current-session change to restore.'); continue
                matches = [d for d in devices if d['key'] == key]
                if len(matches) != 1:
                    messages.append(rule['name']+': configured; absent or ambiguous, not applied.'); continue
                dev = matches[0]; cap = capability(dev)
                if not cap or cap[0] != rule['action']:
                    messages.append(dev['name']+': configured; unsupported current driver/property, not applied.'); continue
                action, prop, values = cap
                current = dev['props'][prop]
                if action == 'touchpad' and rule['enabled'] and not any(d.get('usable_mouse',False) and d['enabled'] and d['props'].get(ENABLED,{}).get('values')==[1] for d in devices):
                    messages.append(dev['name']+': not applied; another enabled identified mouse is required.'); continue
                desired = dict(current, values=values)
                if receipt:
                    # IDs and nodes can be reused, so the instance marker decides when the receipt has one.
                    if (receipt.get('id') != dev['id'] or receipt.get('node') != dev['node']
                            or ('marker' in receipt and marker_of(dev) != receipt['marker'])):
                        # The receipt's instance is gone; the new instance starts from its own driver defaults.
                        self.archive_receipt(key, rule, receipt, 'device-reconnected')
                        receipt = None; data['receipts'].pop(key); self.write(self.path, json.dumps(data).encode())
                        messages.append(dev['name']+': reconnected; previous-instance restoration evidence archived.')
                        if not rule['enabled']: continue
                    elif receipt.get('property') != prop:
                        messages.append(dev['name']+': driver property changed; restoration refused.'); continue
                if receipt:
                    if current not in (receipt['before'], receipt['after']):
                        messages.append(dev['name']+': property changed elsewhere; restore/apply refused.'); continue
                if rule['enabled']:
                    if receipt is None:
                        marker = uuid.uuid4().hex
                        try:
                            backend.mark(dev, marker)  # Before the receipt: a stray marker is harmless, a receipt without one is not.
                        except Exception as exc:
                            messages.append(dev['name']+': configured, apply failed: '+str(exc)); continue
                        # The device may have been swapped before marking: take the baseline only from the marked instance.
                        marked = [d for d in backend.devices() if d['key'] == key]
                        if (len(marked) != 1 or marked[0]['id'] != dev['id'] or marked[0]['node'] != dev['node']
                                or marker_of(marked[0]) != marker or capability(marked[0]) != cap):
                            messages.append(dev['name']+': device changed during apply; not applied.'); continue
                        dev = marked[0]; current = dev['props'][prop]; desired = dict(current, values=values)
                        receipt = dict(token=token, id=dev['id'], node=dev['node'], marker=marker, property=prop, before=current, after=desired)
                        data['receipts'][key] = receipt
                        self.write(self.path, json.dumps(data).encode())  # Before modifying input.
                    target = receipt['after']
                else:
                    target = receipt['before']
                if (prop == LIBINPUT_PROFILE and current != target
                        and not dev['props'][LIBINPUT_AVAILABLE]['values'][target['values'].index(1)]):
                    messages.append(dev['name']+': saved profile is no longer offered by the driver; not written.'); continue
                try:
                    if current != target:
                        backend.write(dev, prop, target)
                    if not rule['enabled']:
                        data['receipts'].pop(key)
                    messages.append(dev['name']+(': applied and read back.' if rule['enabled'] else ': prior property restored.'))
                except Exception as exc:
                    messages.append(dev['name']+': configured, apply failed: '+str(exc))
                self.write(self.path, json.dumps(data).encode())
            self.write(self.path, json.dumps(data).encode())
            if not self.needed(data):
                self.autostart(data, False)
            return messages

    def watch(self, backend, tick=5.0, settle=0.5):
        """Apply now, then reapply on XInput device changes until nothing needs managing."""
        lock = self.home/'.local/state/doroshell/input-watch.lock'; safe(lock, self.home)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open('a') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return  # Another watcher owns this session.
            from Xlib.ext import ge, xinput
            display = backend.display
            opcode = display.query_extension(xinput.extname).major_opcode
            display.screen().root.xinput_select_events([(xinput.AllDevices, xinput.HierarchyChangedMask)])
            display.sync()
            pending = True
            def collect():
                changed = False
                while display.pending_events():
                    event = display.next_event()
                    if (event.type == ge.GenericEventCode and getattr(event, 'extension', None) == opcode
                            and event.evtype == xinput.HierarchyChanged):
                        changed |= bool(event.data.flags & (xinput.SlaveAdded | xinput.DeviceEnabled))
                return changed
            while True:
                if pending:
                    try:
                        print('\n'.join(self.run(backend)), flush=True)
                        pending = False
                    except BlockingIOError:
                        pass  # Settings page is saving; this pass stays pending for the next tick.
                if not pending and not self.needed(self.read()[1]):
                    return  # Opted out (possibly by the page while idle); releases the lock.
                if not display.pending_events() and not select.select([display.fileno()], [], [], tick)[0]:
                    continue
                if collect():
                    time.sleep(settle)  # Let the driver finish initializing the new device.
                    collect(); pending = True

    def start_watcher(self):
        safe(self.helper, self.home)
        if self.helper.is_file():
            subprocess.Popen([sys.executable, str(self.helper), '--login'], start_new_session=True,
                             env=dict(os.environ, HOME=str(self.home)),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def page(home):
    import input_diagnostics
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QCheckBox
    widget = QWidget(); layout = QVBoxLayout(widget)
    note = QLabel('Mouse & Touchpad (X11)\nDisable acceleration on supported mice (evdev profile -1 or libinput flat), or disable a selected touchpad.\nSaved choices are reapplied at LXQt login and when a device is connected. No drivers or system rules are changed.')
    note.setWordWrap(True); layout.addWidget(note)
    all_mice = QCheckBox('No acceleration on all mice')
    all_mice.setToolTip('Applies to every supported mouse, including mice connected later. A choice saved for one mouse below overrides this.')
    all_mice.setEnabled(False); layout.addWidget(all_mice)
    devices = QComboBox(); devices.setAccessibleName('Input device'); layout.addWidget(devices)
    enabled = QCheckBox('Disable selected option'); layout.addWidget(enabled)
    status = QLabel('Choose Refresh to inspect devices. No input changes occur while inspecting.'); status.setWordWrap(True); layout.addWidget(status)
    evidence = QLabel(); evidence.setWordWrap(True); evidence.setAccessibleName('Read-only input capability evidence')
    evidence.hide(); layout.addWidget(evidence)
    refresh = QPushButton('Refresh devices'); apply = QPushButton('Save and apply'); apply.setEnabled(False)
    layout.addWidget(refresh); layout.addWidget(apply)
    restore = QPushButton('Stop managing and restore')
    restore.setToolTip('Opt out of all saved choices and restore owned current-session values. Unresolved receipts keep the helper installed.')
    layout.addWidget(restore)
    from gi.repository import Gio
    native_entry = Gio.DesktopAppInfo.new('lxqt-config-input.desktop')
    native_button = QPushButton('Native mouse settings…'); native_button.setEnabled(native_entry is not None)
    def open_native():
        try:
            native_entry.launch([], None)
        except Exception as exc:
            status.setText(str(exc))
    native_button.clicked.connect(open_native)
    layout.addWidget(native_button); layout.addStretch()
    store = Preferences(home); context = {}
    def selected():
        dev = devices.currentData(); cap = capability(dev) if dev else None
        apply.setEnabled(bool(cap))
        enabled.setEnabled(bool(cap))
        if not dev:
            evidence.clear(); evidence.hide(); return
        rule = context['data']['rules'].get(dev['key'], {})
        enabled.setChecked(rule.get('enabled',False))
        enabled.setText('Disable touchpad' if dev['kind']=='touchpad' else 'Disable acceleration')
        value = dev['props'].get(cap[1],{}).get('values') if cap else None
        observed = ('touchpad disabled' if dev['kind']=='touchpad' and value == [0] else
                    'profile -1 (no velocity-dependent acceleration)' if value == [0xffffffff] else
                    'libinput flat profile (no acceleration)' if cap and cap[1] == LIBINPUT_PROFILE and value == cap[2] else
                    'enabled / other profile' if value is not None else 'not exposed')
        status.setText('User preference: '+('disable' if rule.get('enabled',False) else 'unmanaged')+'; observed property: '+observed+'; driver properties: '+dev['driver']+'. '+('Uncheck to restore the saved current-session property.' if cap else 'Unsupported property or device.'))
        if dev['kind'] == 'mouse':
            evidence.setText(input_diagnostics.describe(dev, context['configuration'], bool(cap and cap[0]=='acceleration')))
            evidence.show()
        else: evidence.clear(); evidence.hide()
    def inspect_devices():
        backend = None
        try:
            context['raw'], context['data'] = store.read()
            all_mice.blockSignals(True); all_mice.setChecked(bool(context['data'].get('all_mice'))); all_mice.blockSignals(False)
            all_mice.setEnabled(True)
            backend = XInput(); values = backend.devices()
            context['configuration'] = input_diagnostics.read_configuration()
            devices.blockSignals(True); devices.clear()
            for dev in values:
                devices.addItem(dev['name']+' — '+dev['kind'], dev)
            devices.blockSignals(False); selected()
            if not values: status.setText('No identified input devices available. No changes made.')
            elif not any(d['kind']=='touchpad' for d in values): status.setText(status.text()+' No touchpad detected.')
        except Exception as exc:
            apply.setEnabled(False); enabled.setEnabled(False); evidence.clear(); evidence.hide(); status.setText(str(exc))
        finally:
            if backend: backend.close()
    def save(stop=False, everything=None):
        backend = None
        try:
            backend = XInput()
            if everything is not None:
                messages = store.run(backend, expected=context['raw'], all_mice=everything)
            elif stop:
                raw, _ = store.read()
                messages = store.run(backend, expected=raw, stop=True)
            else:
                dev = devices.currentData(); cap = capability(dev)
                messages = store.run(backend, (dev['key'], dict(name=dev['name'],action=cap[0],enabled=enabled.isChecked())), context['raw'])
            if store.needed(store.read()[1]):
                store.start_watcher()  # Covers devices connected before the next login.
            inspect_devices(); status.setText('\n'.join(messages))
        except Exception as exc: status.setText(str(exc))
        finally:
            if backend: backend.close()
    refresh.clicked.connect(inspect_devices); apply.clicked.connect(save); devices.currentIndexChanged.connect(selected)
    restore.clicked.connect(lambda: save(True))
    all_mice.toggled.connect(lambda checked: save(everything=checked))
    return widget


if __name__ == '__main__':
    if sys.argv[1:] != ['--login']:
        raise SystemExit('Use DoroShell Settings to configure input preferences.')
    backend = None
    try:
        backend = XInput()
        Preferences(Path.home()).watch(backend)
    except Exception as exc:
        raise SystemExit('Input preferences not applied: '+str(exc))
    finally:
        if backend: backend.close()
