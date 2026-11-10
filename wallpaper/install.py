"""Use the existing module backup engine for next-login desktop selection."""
import base64
import hashlib
import json
import os
from pathlib import Path
from install import set_ini


def plans(home, binary):
    if binary is None: raise ValueError('Build the optional native desktop and pass --wallpaper-binary')
    binary = Path(binary).resolve()
    proof = binary.with_name('doroshell-wallpaper-build.json')
    if not binary.is_file() or not os.access(binary, os.X_OK) or not proof.is_file(): raise ValueError('Expected a verified DoroShell wallpaper build')
    metadata = json.loads(proof.read_text())
    if metadata['sha256'] != hashlib.sha256(binary.read_bytes()).hexdigest():
        raise ValueError('Native desktop changed since its build record')
    helper = binary.with_name('doroshell-video-worker')
    if metadata.get('format', 1) not in (1, 2):
        raise ValueError('Unsupported wallpaper build record')
    if metadata.get('format') == 2:
        if (not helper.is_file() or not os.access(helper, os.X_OK) or
                hashlib.sha256(helper.read_bytes()).hexdigest() != metadata.get('helper_sha256')):
            raise ValueError('Decoder helper missing or changed since its build record')
    autostart = home/'.config/autostart/lxqt-desktop.desktop'
    original = autostart.read_bytes() if autostart.exists() else None
    manifest = home/'.local/state/doroshell/wallpaper.json'
    if manifest.exists():
        baseline = json.loads(manifest.read_text())['backup']['.config/autostart/lxqt-desktop.desktop']['data']
        original = base64.b64decode(baseline) if baseline is not None else None
    previous = original.decode() if original is not None else '[Desktop Entry]\nType=Application\nName=DoroShell desktop\nOnlyShowIn=LXQt;\nX-LXQt-Module=true\n'
    # Retain the existing local Dolphin startup hook as an explicit argv command.
    dolphin_hook = 'Exec=sh -c "systemctl --user start plasma-dolphin.service; exec pcmanfm-qt --desktop --profile=lxqt"' in previous.splitlines()
    launcher = home/'.local/bin/doroshell-wallpaper-desktop'
    check = ''
    if metadata.get('format') == 2:
        # Recheck the pinned pair at startup; missing/tampered files fall back to stock.
        check = ('    import hashlib\n'
                 '    for path, expected in '+repr([(str(binary),metadata['sha256']),
                                                    (str(helper),metadata['helper_sha256'])])+':\n'
                 '        if not os.access(path, os.X_OK): raise OSError("Wallpaper build is not executable")\n'
                 '        with open(path, "rb") as stream:\n'
                 '            if hashlib.sha256(stream.read()).hexdigest() != expected:\n'
                 '                raise OSError("Wallpaper build changed")\n')
    script = ('#!/usr/bin/python\nimport os, subprocess\n' 
              + ("subprocess.run(['systemctl', '--user', 'start', 'plasma-dolphin.service'])\n" if dolphin_hook else '') +
              'try:\n'+check+'    result = subprocess.run(['+repr(str(binary))+", '--desktop', '--profile=lxqt'])\n"
              'except OSError:\n    result = None\n'
              'if result is None or result.returncode != 0:\n'
              "    os.execv('/usr/bin/pcmanfm-qt', ['pcmanfm-qt', '--desktop', '--profile=lxqt'])\n").encode()
    def file(name,data,mode=0o644):
        return dict(file=name,kind='file',after=base64.b64encode(data).decode(),mode=mode)
    # Quote Exec as a desktop-entry argument, never as a shell command.
    quoted = '"'+str(launcher).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
    desktop = set_ini(set_ini(previous, 'Desktop Entry', 'Exec', quoted), 'Desktop Entry', 'TryExec', '/usr/bin/python').encode()
    control=(Path(__file__).with_name('control.py')).read_bytes()
    control_exec = quoted.replace('doroshell-wallpaper-desktop', 'doroshell-wallpaper')
    app = ('[Desktop Entry]\nType=Application\nName=DoroShell animated wallpaper\nExec='+control_exec+'\nIcon=preferences-desktop-wallpaper\nCategories=Settings;DesktopSettings;\n').encode()
    return [file('.local/share/applications/doroshell-wallpaper.desktop',app),file('.local/bin/doroshell-wallpaper-desktop',script,0o755),
            file('.local/bin/doroshell-wallpaper',control,0o755),
            file('.config/autostart/lxqt-desktop.desktop',desktop)]
