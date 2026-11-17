"""Use the existing module backup engine for next-login desktop selection."""
import base64
import hashlib
import json
import os
from pathlib import Path
from install import PlanError, set_ini


def plans(home, binary):
    if binary is None: raise PlanError('Build the optional native desktop and pass --wallpaper-binary')
    binary = Path(binary).resolve()
    proof = binary.with_name('doroshell-wallpaper-build.json')
    if not binary.is_file() or not os.access(binary, os.X_OK) or not proof.is_file(): raise PlanError('Expected a verified DoroShell wallpaper build')
    try:
        metadata = json.loads(proof.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise PlanError('Invalid wallpaper build record; rebuild the candidate before staging.') from error
    if not isinstance(metadata, dict) or not isinstance(metadata.get('sha256'), str):
        raise PlanError('Invalid wallpaper build record; rebuild the candidate before staging.')
    if metadata['sha256'] != hashlib.sha256(binary.read_bytes()).hexdigest():
        raise PlanError('Native desktop changed since its build record')
    helper = binary.with_name('doroshell-video-worker')
    if metadata.get('format', 1) not in (1, 2, 3):
        raise PlanError('Unsupported wallpaper build record')
    if metadata.get('format') in (2, 3):
        if (not helper.is_file() or not os.access(helper, os.X_OK) or
                hashlib.sha256(helper.read_bytes()).hexdigest() != metadata.get('helper_sha256')):
            raise PlanError('Decoder helper missing or changed since its build record')
    display_helper = binary.with_name('doroshell-display-backend.py')
    if metadata.get('format') == 3:
        if (not display_helper.is_file() or not os.access(display_helper, os.R_OK) or
                hashlib.sha256(display_helper.read_bytes()).hexdigest() != metadata.get('display_helper_sha256')):
            raise PlanError('Display helper missing or changed since its build record')
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
    if metadata.get('format') in (2, 3):
        # Recheck the complete build at startup; any mismatch falls back to stock.
        files = [(str(binary),metadata['sha256'],os.X_OK), (str(helper),metadata['helper_sha256'],os.X_OK)]
        if metadata.get('format') == 3:
            files.append((str(display_helper),metadata['display_helper_sha256'],os.R_OK))
        check = ('    import hashlib\n'
                 '    for path, expected, access in '+repr(files)+':\n'
                 '        if not os.access(path, access): raise OSError("Wallpaper build is unavailable")\n'
                 '        with open(path, "rb") as stream:\n'
                 '            if hashlib.sha256(stream.read()).hexdigest() != expected:\n'
                 '                raise OSError("Wallpaper build changed")\n')
    recipe = binary.parents[2]/'recipe/native_rebuild.py' if len(binary.parents) > 2 else None
    if recipe and recipe.is_file():
        # Missing libraries after a system update: rebuild in the background, use stock PCManFM now.
        check += ('    if subprocess.run(["/usr/bin/python", '+repr(str(recipe))+', "login", "desktop", "--current", '
                  +repr(str(binary))+']).returncode: raise OSError("Desktop rebuild pending")\n')
    script =('#!/usr/bin/python\nimport os, subprocess\n' 
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
