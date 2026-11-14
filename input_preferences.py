#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Opt-in per-device X11 preferences; no driver switching or system configuration."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

PROFILE = 'Device Accel Profile'
ENABLED = 'Device Enabled'


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
        if name == ENABLED and value['values'] == [0] and device['kind'] == 'touchpad':
            if not any(d.get('usable_mouse',False) and d['enabled'] and d['props'].get(ENABLED,{}).get('values')==[1] for d in devices):
                raise RuntimeError('The other mouse disappeared; touchpad disable refused.')
        self.display.xinput_change_device_property(device['id'], self.display.intern_atom(name),
            value['type'], X.PropModeReplace, (value['format'], value['values']))
        self.display.sync()
        reply = self.display.xinput_get_device_property(device['id'], self.display.intern_atom(name), 0, 0, 1024, False)
        if property_values(reply) != value:
            raise RuntimeError('Driver did not accept the requested property; preference remains configured.')


def capability(device):
    enabled = device['props'].get(ENABLED, {})
    profile = device['props'].get(PROFILE, {})
    if device['kind'] == 'touchpad' and enabled.get('format') == 8 and enabled.get('values') in ([0], [1]):
        return 'touchpad', ENABLED, [0]
    if device['kind'] == 'mouse' and device['driver'] == 'evdev' and profile.get('format') == 32 and len(profile.get('values', [])) == 1:
        return 'acceleration', PROFILE, [0xffffffff]  # Xorg profile -1: no velocity-dependent acceleration.
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

    def read(self):
        safe(self.path, self.home)
        raw = self.path.read_bytes() if self.path.exists() else None
        data = json.loads(raw) if raw else dict(version=1, rules={}, receipts={})
        if data.get('version') != 1 or not isinstance(data.get('rules'), dict) or not isinstance(data.get('receipts'), dict):
            raise ValueError('Unsupported input preferences; existing file preserved.')
        for key, rule in data['rules'].items():
            if not re.fullmatch('[0-9a-f]{64}', key) or rule.get('action') not in ('acceleration','touchpad') or type(rule.get('enabled')) is not bool:
                raise ValueError('Invalid saved input preference.')
        for key, receipt in data['receipts'].items():
            if key not in data['rules'] or not isinstance(receipt, dict):
                raise ValueError('Invalid input restoration record.')
            prop = PROFILE if data['rules'][key]['action']=='acceleration' else ENABLED
            wanted = [0xffffffff] if prop == PROFILE else [0]
            if receipt.get('property') != prop or not isinstance(receipt.get('token'), str) or type(receipt.get('id')) is not int or not isinstance(receipt.get('node'), str):
                raise ValueError('Invalid input restoration identity.')
            for field in ('before','after'):
                value = receipt.get(field, {})
                if not isinstance(value, dict) or value.get('format') != (32 if prop == PROFILE else 8) or type(value.get('type')) is not int or not isinstance(value.get('values'), list) or len(value['values']) != 1 or type(value['values'][0]) is not int or not 0 <= value['values'][0] <= (0xffffffff if prop == PROFILE else 1):
                    raise ValueError('Invalid saved input property.')
            if receipt['after']['values'] != wanted or receipt['before']['type'] != receipt['after']['type']:
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

    def autostart(self):
        def quote(value):
            return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
        payload = ('[Desktop Entry]\nType=Application\nName=DoroShell input preferences\nExec='+quote(sys.executable)+' '+quote(Path(__file__).resolve())+' --login\nOnlyShowIn=LXQt;\n').encode()
        safe(self.startup, self.home)
        if self.startup.exists() and self.startup.read_bytes() != payload:
            raise RuntimeError('Input autostart entry changed elsewhere; it was not replaced.')
        if not self.startup.exists():
            self.write(self.startup, payload)

    def run(self, backend, change=None, expected=None):
        lock = self.path.with_suffix('.lock'); safe(lock, self.home)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            raw, data = self.read()
            if change is not None:
                if raw != expected:
                    raise RuntimeError('Preferences changed elsewhere; refresh before saving.')
                key, rule = change
                # Validate request with the same reader schema before any device write.
                if not re.fullmatch('[0-9a-f]{64}', key) or rule['action'] not in ('acceleration','touchpad') or type(rule['enabled']) is not bool:
                    raise ValueError('Invalid input request.')
                self.autostart()
                data['rules'][key] = rule
                self.write(self.path, json.dumps(data).encode())
            if not data['rules']:
                return []
            devices = backend.devices()
            token = backend.token()
            messages = []
            for key, rule in data['rules'].items():
                matches = [d for d in devices if d['key'] == key]
                if len(matches) != 1:
                    messages.append(rule['name']+': configured; absent or ambiguous, not applied.'); continue
                dev = matches[0]; cap = capability(dev)
                receipt = data['receipts'].get(key)
                if receipt and receipt.get('token') != token:
                    receipt = None; data['receipts'].pop(key)
                if not rule['enabled'] and not receipt:
                    messages.append(dev['name']+': unmanaged; no current-session change to restore.'); continue
                if not cap or cap[0] != rule['action']:
                    messages.append(dev['name']+': configured; unsupported current driver/property, not applied.'); continue
                action, prop, values = cap
                current = dev['props'][prop]
                if action == 'touchpad' and rule['enabled'] and not any(d.get('usable_mouse',False) and d['enabled'] and d['props'].get(ENABLED,{}).get('values')==[1] for d in devices):
                    messages.append(dev['name']+': not applied; another enabled identified mouse is required.'); continue
                desired = dict(current, values=values)
                if receipt:
                    if receipt.get('property') != prop or receipt.get('id') != dev['id'] or receipt.get('node') != dev['node']:
                        messages.append(dev['name']+': device instance changed; restoration refused.'); continue
                    if current not in (receipt['before'], receipt['after']):
                        messages.append(dev['name']+': property changed elsewhere; restore/apply refused.'); continue
                if rule['enabled']:
                    if receipt is None:
                        receipt = dict(token=token, id=dev['id'], node=dev['node'], property=prop, before=current, after=desired)
                        data['receipts'][key] = receipt
                        self.write(self.path, json.dumps(data).encode())  # Before modifying input.
                    target = receipt['after']
                else:
                    target = receipt['before']
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
            if not any(r['enabled'] for r in data['rules'].values()) and not data['receipts']:
                self.autostart()  # Verify ownership before removing our login entry.
                self.startup.unlink()
            return messages


def page(home):
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QCheckBox
    widget = QWidget(); layout = QVBoxLayout(widget)
    note = QLabel('Mouse & Touchpad (X11)\nDisable velocity-dependent acceleration on supported evdev mice, or disable a selected touchpad.\nSaved choices are retried once at LXQt login. Reconnects require Refresh / Reapply. No drivers or system rules are changed.')
    note.setWordWrap(True); layout.addWidget(note)
    devices = QComboBox(); devices.setAccessibleName('Input device'); layout.addWidget(devices)
    enabled = QCheckBox('Disable selected option'); layout.addWidget(enabled)
    status = QLabel('Choose Refresh to inspect devices. No input changes occur while inspecting.'); status.setWordWrap(True); layout.addWidget(status)
    refresh = QPushButton('Refresh devices'); apply = QPushButton('Save and apply'); apply.setEnabled(False)
    layout.addWidget(refresh); layout.addWidget(apply)
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
        if not dev: return
        rule = context['data']['rules'].get(dev['key'], {})
        enabled.setChecked(rule.get('enabled',False))
        enabled.setText('Disable touchpad' if dev['kind']=='touchpad' else 'Disable acceleration')
        value = dev['props'].get(cap[1],{}).get('values') if cap else None
        observed = ('disabled' if value == ([0] if dev['kind']=='touchpad' else [0xffffffff]) else 'enabled / other profile' if value is not None else 'not exposed')
        status.setText('Configured: '+('disable' if rule.get('enabled',False) else 'unmanaged')+'; observed now: '+observed+'; driver properties: '+dev['driver']+'. '+('Uncheck to restore the saved current-session property.' if cap else 'Unsupported property or device. An existing system AccelerationScheme none rule may remove the profile property; its absence does not verify the scheme.'))
    def inspect_devices():
        backend = None
        try:
            context['raw'], context['data'] = store.read()
            backend = XInput(); values = backend.devices()
            devices.blockSignals(True); devices.clear()
            for dev in values:
                devices.addItem(dev['name']+' — '+dev['kind'], dev)
            devices.blockSignals(False); selected()
            if not values: status.setText('No identified input devices available. No changes made.')
            elif not any(d['kind']=='touchpad' for d in values): status.setText(status.text()+' No touchpad detected.')
        except Exception as exc:
            apply.setEnabled(False); enabled.setEnabled(False); status.setText(str(exc))
        finally:
            if backend: backend.close()
    def save():
        backend = None
        try:
            dev = devices.currentData(); cap = capability(dev)
            backend = XInput()
            messages = store.run(backend, (dev['key'], dict(name=dev['name'],action=cap[0],enabled=enabled.isChecked())), context['raw'])
            inspect_devices(); status.setText('\n'.join(messages))
        except Exception as exc: status.setText(str(exc))
        finally:
            if backend: backend.close()
    refresh.clicked.connect(inspect_devices); apply.clicked.connect(save); devices.currentIndexChanged.connect(selected)
    return widget


if __name__ == '__main__':
    if sys.argv[1:] != ['--login']:
        raise SystemExit('Use DoroShell Settings to configure input preferences.')
    backend = None
    try:
        backend = XInput()
        print('\n'.join(Preferences(Path.home()).run(backend)))
    except Exception as exc:
        raise SystemExit('Input preferences not applied: '+str(exc))
    finally:
        if backend: backend.close()
