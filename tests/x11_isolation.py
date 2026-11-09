"""Run an opt-in acceptance command on an authenticated disposable X11 server."""
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time


def isolated(xvfb, command):
    with tempfile.TemporaryDirectory(prefix='doroshell-private-display-') as tmp:
        base=Path(tmp);auth=base/'Xauthority';auth.touch(mode=0o600)
        number=next(n for n in range(120,220) if not Path(f'/tmp/.X11-unix/X{n}').exists() and not Path(f'/tmp/.X{n}-lock').exists())
        screen=f':{number}'
        subprocess.run(['xauth','-f',str(auth),'add',screen,'MIT-MAGIC-COOKIE-1',secrets.token_hex(16)],check=True,stdout=subprocess.DEVNULL)
        env=dict(os.environ,DISPLAY=screen,XAUTHORITY=str(auth),HOME=tmp,XDG_CONFIG_HOME=tmp+'/.config',XDG_DATA_HOME=tmp+'/.local/share',XDG_CACHE_HOME=tmp+'/.cache',QT_QPA_PLATFORM='xcb',DOROSHELL_TEST_DISPLAY=screen)
        for key, leaf in [('XDG_RUNTIME_DIR', 'run'), ('TMPDIR', 'tmp')]:
            directory = base/leaf
            directory.mkdir(mode=0o700)
            env[key] = str(directory)
        env['XDG_STATE_HOME'] = str(base/'.local/state')
        env['XDG_SESSION_TYPE'] = 'x11'
        # No inherited Wayland socket or session bus can route a test to personal applications.
        env.pop('WAYLAND_DISPLAY',None);env.pop('DBUS_SESSION_BUS_ADDRESS',None)
        with open(base/'xvfb.log','w') as log:
            server=subprocess.Popen([str(xvfb),screen,'-screen','0','1024x768x24','-nolisten','tcp','-auth',str(auth)],stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+5
                while not Path(f'/tmp/.X11-unix/X{number}').exists():
                    if server.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Private Xvfb did not start: '+(base/'xvfb.log').read_text())
                    time.sleep(.05)
                subprocess.run(['dbus-run-session','--',*command],env=env,check=True,timeout=90)
            finally:
                server.terminate();server.wait(timeout=5)

