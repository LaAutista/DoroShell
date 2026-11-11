#!/usr/bin/env python3
"""Session-only X11 display transactions. No configuration files are written."""
import copy
from contextvars import ContextVar
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time


class DisplayError(RuntimeError):
    def __init__(self, message, differences=None):
        self.differences = (differences or [])[:32]
        detail = ', '.join(f"{d['field']} (output {d['output']})" for d in self.differences)
        super().__init__(message + (': ' + detail if detail else ''))


def differences(expected, actual):
    """Bounded field labels only: never output property values, EDID or identifiers."""
    result = []
    def add(index, field):
        if len(result) < 32:
            result.append(dict(output=index, field=field))
    if expected['framebuffer'] != actual['framebuffer']:
        add(-1, 'framebuffer geometry')
    before, after = expected['outputs'], actual['outputs']
    for index, output in enumerate(before):
        found = next((o for o in after if o['name'] == output['name']), None)
        if found is None:
            add(index, 'output disappeared')
            continue
        if output.get('connection') != found.get('connection'):
            add(index, 'connection status changed')
        for field in ('current', 'crtc', 'modes'):
            if output[field] != found[field]:
                add(index, {'current': 'current mode mismatch', 'crtc': 'CRTC assignment', 'modes': 'advertised mode timings/flags'}[field])
    if any(o['name'] not in [b['name'] for b in before] for o in after):
        add(-1, 'output added')
    if [o['name'] for o in before] != [o['name'] for o in after]:
        add(-1, 'output enumeration changed')
    if expected.get('vsync') != actual.get('vsync'):
        add(-1, 'NVIDIA OpenGL VSync')
    a, b = expected.get('layout_fields', {}), actual.get('layout_fields', {})
    for key in sorted(a.keys() | b.keys()):
        if a.get(key) != b.get(key):
            index, field = key.split(':', 1)
            add(int(index), field)
    if expected['layout'] != actual['layout'] and a == b:
        add(-1, 'protected layout fingerprint')
    return result


class DeadlineExpired(DisplayError):
    pass


command_deadline = ContextVar('command_deadline', default=None)


def run(args):
    deadline = command_deadline.get()
    timeout = min(4, deadline - time.monotonic()) if deadline is not None else 4
    if timeout <= 0:
        raise DeadlineExpired('Confirmation deadline reached')
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                                env=dict(os.environ, LC_ALL='C'))
    except (OSError, subprocess.TimeoutExpired) as error:
        if deadline is not None and time.monotonic() >= deadline:
            raise DeadlineExpired('Confirmation deadline reached') from error
        raise DisplayError(f'{args[0]} unavailable or timed out') from error
    if result.returncode or 'ERROR:' in result.stderr:
        raise DisplayError(f'{args[0]}: {result.stderr.strip() or "operation failed"}')
    return result.stdout


def parse(text):
    """Retain exact RandR mode IDs; rounded Hz strings are labels only."""
    framebuffer = re.search(r'^Screen \d+:.* current (\d+) x (\d+),', text)
    if not framebuffer:
        raise DisplayError('No X11 RandR screen found')
    outputs = []
    output = mode = None
    signature = []
    layout_fields = {}
    category = "screen geometry"
    for line in text.splitlines():
        head = re.match(r'^(\S+) (connected|disconnected|unknown connection)(.*)$', line)
        if head:
            name, status, tail = head.groups()
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', name) or name.startswith('XWAYLAND'):
                raise DisplayError('Unsupported output name or Xwayland display')
            active = re.search(r'\b\d+x\d+[+-]\d+[+-]\d+ \((0x[0-9a-f]+)\)', tail)
            output = dict(name=name, connection=status, current=active[1] if active else None, crtc=None, modes=[])
            outputs.append(output)
            mode = None
        crtc = re.match(r'\s+CRTC:\s+(\d+)$', line)
        if crtc and output:
            output['crtc'] = int(crtc[1])
        entry = re.match(r'^  (\S+) \((0x[0-9a-f]+)\) .*MHz(.*)$', line)
        if entry and output:
            mode = dict(id=entry[2], name=entry[1], flags=' '.join(entry[3].replace('*current', '').split()))
            output['modes'].append(mode)
        if mode:
            horizontal = re.search(r'h: width\s+(\d+)', line)
            vertical = re.search(r'v: height\s+(\d+).*clock\s+([\d.]+)Hz', line)
            if horizontal:
                mode['width'] = int(horizontal[1])
            if vertical:
                mode.update(height=int(vertical[1]), hz=vertical[2])
        # Current mode is separately compared. Ignore server-generated timestamps only.
        if not re.match(r'\s*Timestamp:', line):
            if head:
                line = re.sub(r' \(0x[0-9a-f]+\)', '', line)
            normalized = line.replace(' *current', '').rstrip()
            signature.append(normalized)
            # Only fixed labels escape the process. Unknown properties (including
            # EDID/serial data) stay in an opaque fingerprint, never in diagnostics.
            if head:
                category = 'connection/geometry/rotation'
            elif entry:
                category = 'mode timings/flags'
            elif ':' in line:
                label = line.strip().split(':', 1)[0]
                category = {'Gamma': 'gamma', 'Brightness': 'brightness',
                    'CRTC': 'CRTC assignment', 'Transform': 'transform',
                    'Border': 'border', '_KDE_SCREEN_INDEX': 'screen index',
                    'CTM': 'color transform', 'CscMatrix': 'color matrix'}.get(label, 'other protected properties')
                if label in ('h', 'v'):
                    category = 'mode timings/flags'
            key = f'{len(outputs)-1}:{category}'
            layout_fields.setdefault(key, []).append(normalized)
    for output in outputs:
        for mode in output['modes']:
            if not {'width', 'height', 'hz'} <= mode.keys():
                raise DisplayError('Incomplete RandR mode timings')
        if output['current'] and not any(m['id'] == output['current'] for m in output['modes']):
            raise DisplayError('Current RandR mode missing')
    return dict(framebuffer='x'.join(framebuffer.groups()), outputs=outputs,
                layout_fields={k: hashlib.sha256('\n'.join(v).encode()).hexdigest() for k, v in layout_fields.items()},
                layout=hashlib.sha256('\n'.join(signature).encode()).hexdigest())


def nv_query():
    value = run(['nvidia-settings', '-t', '-q', '[screen:0]/SyncToVBlank']).strip()
    if value not in ('0', '1'):
        raise DisplayError('NVIDIA OpenGL SyncToVBlank unavailable on X screen 0')
    return int(value)


def snapshot():
    if os.environ.get('XDG_SESSION_TYPE', 'x11') != 'x11':
        raise DisplayError('These controls require an X11 session')
    state = parse(run(['xrandr', '--current', '--verbose']))
    try:
        state['vsync'] = nv_query()
        state['vsync_reason'] = ''
    except DeadlineExpired:
        raise
    except DisplayError:
        state['vsync'] = None
        state['vsync_reason'] = 'NVIDIA OpenGL control unavailable. Intel/AMD: use application VSync settings.'
    return state


def token(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def public(state):
    result = dict(token=token(state), vsync=state['vsync'], vsync_reason=state['vsync_reason'], outputs=[])
    for output in state['outputs']:
        current = next((m for m in output['modes'] if m['id'] == output['current']), None)
        if current and output['crtc'] is not None and not any(flag in current['flags'] for flag in ('Interlace', 'DoubleScan')):
            if sum(o['current'] is not None and o['crtc'] == output['crtc'] for o in state['outputs']) != 1:
                continue  # Shared CRTCs need a coordinated clone-mode transaction.
            # Preferred is metadata, not a timing flag; don't use it to exclude rates.
            modes = [m for m in output['modes'] if (m['width'], m['height']) == (current['width'], current['height'])
                     and float(m['hz']) > 0 and not any(flag in m['flags'] for flag in ('Interlace', 'DoubleScan'))]
            if modes:
                result['outputs'].append(dict(name=output['name'], current=output['current'], modes=modes))
    return result


class Transaction:
    def __init__(self, request, query=snapshot, execute=run):
        self.query, self.execute = query, execute
        if not isinstance(request, dict) or set(request) - {'token', 'output', 'mode', 'vsync'}:
            raise DisplayError('Invalid display request')
        self.before = query()
        if request.get('token') != token(self.before):
            raise DisplayError('Display settings changed. Reload before applying.')
        self.expected = copy.deepcopy(self.before)
        self.output = None
        self.mode_attempted = self.nv_attempted = False
        output_name, mode_id = request.get('output'), request.get('mode')
        if output_name is not None or mode_id is not None:
            allowed = next((o for o in public(self.before)['outputs'] if o['name'] == output_name), None)
            if not allowed or mode_id not in [m['id'] for m in allowed['modes']]:
                raise DisplayError('Choose an advertised refresh mode at the current resolution')
            self.output = next(o for o in self.expected['outputs'] if o['name'] == output_name)
            self.old_mode = self.output['current']
            self.output['current'] = mode_id
        self.new_vsync = request.get('vsync', self.before['vsync'])
        if 'vsync' in request and (self.before['vsync'] is None or type(self.new_vsync) is not int or self.new_vsync not in (0, 1)):
            raise DisplayError('NVIDIA OpenGL VSync is unsupported or the value is invalid')
        self.expected['vsync'] = self.new_vsync

    def mode_command(self, mode):
        return ['xrandr', '--output', self.output['name'], '--mode', mode]

    def apply(self):
        if self.query() != self.before:
            raise DisplayError('Concurrent display edit; reload before applying')
        if self.output and self.output['current'] != self.old_mode:
            self.mode_attempted = True
            self.execute(self.mode_command(self.output['current']))
        if self.new_vsync != self.before['vsync']:
            self.nv_attempted = True
            self.execute(['nvidia-settings', '-a', f'[screen:0]/SyncToVBlank={self.new_vsync}'])
        actual = self.query()
        if actual != self.expected:
            raise DisplayError('Driver did not apply the requested state exactly', differences(self.expected, actual))

    def verify(self):
        actual = self.query()
        if actual != self.expected:
            raise DisplayError('Display state changed; refusing Keep', differences(self.expected, actual))

    def revert(self):
        current = self.query()
        errors = []
        if self.nv_attempted and current['vsync'] != self.before['vsync']:
            if current['vsync'] == self.new_vsync:
                try:
                    self.execute(['nvidia-settings', '-a', f"[screen:0]/SyncToVBlank={self.before['vsync']}"])
                except DisplayError as error:
                    errors.append(str(error))
            else:
                errors.append('NVIDIA setting changed elsewhere; left untouched')
        if self.mode_attempted:
            old_output = next((o for o in current['outputs'] if o['name'] == self.output['name']), None)
            if not old_output or old_output['current'] != self.old_mode:
                others_unchanged = all(o == b for o, b in zip(current['outputs'], self.expected['outputs']) if o['name'] != self.output['name'])
                if current['layout'] == self.before['layout'] and others_unchanged and old_output and old_output['current'] == self.output['current']:
                    try:
                        self.execute(self.mode_command(self.old_mode))
                    except DisplayError as error:
                        errors.append(str(error))
                else:
                    errors.append('Display disconnected or layout changed; no forced reconnect or overwrite')
        if not errors and self.query() != self.before:
            errors.append('Original state not restored exactly; reload and inspect display settings')
        if errors:
            raise DisplayError('; '.join(errors), differences(self.before, current))


def emit(**message):
    try:
        print(json.dumps(message), flush=True)
    except BrokenPipeError:
        pass  # Closing the UI must not interrupt rollback.


def guard(transaction, stream=sys.stdin, timeout=15, cancelled=lambda: False):
    """Own rollback independently of the UI event loop, including EOF and termination."""
    kept = False
    deadline_token = None
    failure = None
    try:
        transaction.apply()
        emit(pending=True, seconds=timeout)
        deadline = time.monotonic() + timeout
        deadline_token = command_deadline.set(deadline)
        while time.monotonic() < deadline and not cancelled():
            ready, _, _ = select.select([stream], [], [], min(.25, max(0, deadline-time.monotonic())))
            if ready:
                # Read bytes, not readline(): an incomplete command cannot stall the deadline.
                command = os.read(stream.fileno(), 64)
                if command == b'keep\n' and time.monotonic() < deadline:
                    transaction.verify()
                    kept = time.monotonic() < deadline and not cancelled()
                break
            transaction.verify()
    except DeadlineExpired:
        pass
    except DisplayError as error:
        failure = error
    finally:
        if deadline_token is not None:
            command_deadline.reset(deadline_token)
        if not kept:
            try:
                transaction.revert()
            except DisplayError as error:
                if failure:
                    raise DisplayError(f'{failure}; recovery failed: {error}',
                                       failure.differences + error.differences) from error
                raise
    if failure:
        raise failure
    emit(done=True, kept=kept)


def main():
    try:
        if sys.argv[1:] == ['query']:
            emit(**public(snapshot()))
            return
        if len(sys.argv) != 3 or sys.argv[1] != 'apply':
            raise DisplayError('Expected query or apply JSON')
        runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
        if runtime.stat().st_uid != os.getuid() or runtime.stat().st_mode & 0o077:
            raise DisplayError('A private user runtime directory is required')
        # All instances share a lock; originals remain in this process until Keep/Revert.
        fd = os.open(runtime/'doroshell-display.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise DisplayError('Another display confirmation is pending') from error
            stopped = False
            def interrupted(signum, frame):
                nonlocal stopped
                stopped = True
            signal.signal(signal.SIGTERM, interrupted)
            signal.signal(signal.SIGINT, interrupted)
            guard(Transaction(json.loads(sys.argv[2])), cancelled=lambda: stopped)
    except (DisplayError, OSError, ValueError) as error:
        emit(error=str(error), differences=getattr(error, 'differences', []))
        sys.exit(1)


if __name__ == '__main__':
    main()
