"""Reversible DoroClipboard files and fixed panel button beside the tray chevron."""
import base64
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parents[1]

def plans(home):
    from modules import ini_value
    home = Path(home)
    edits = []
    def file(name, data, mode=0o644):
        edits.append({'file':name,'kind':'file','after':base64.b64encode(data).decode(),'mode':mode})
    def ini(name, section, key, value):
        edits.append({'file':name,'kind':'ini','section':section,'key':key,'after':value})
    panel = '.config/doroshell/panel.conf'
    text = (home/panel).read_text()
    plugins = ini_value(text, 'panel1', 'plugins')
    if not plugins: raise ValueError('Stage the DoroShell native panel before adding DoroClipboard.')
    parts = [p.strip() for p in plugins.split(',')]
    notifier = next((p for p in parts if ini_value(text,p,'type') == 'statusnotifier' or p == 'statusnotifier'), None)
    if notifier is None: raise ValueError('No notification-area widget found; refusing to guess button placement.')
    name = 'doroClipboard'
    if name in parts or ini_value(text,name,'type'):
        if ini_value(text,name,'type') != 'quicklaunch' or ini_value(text,name,'apps\\1\\desktop') != str(home/'.local/share/applications/doroshell-clipboard.desktop'):
            raise ValueError('Existing doroClipboard widget differs; preserve personal settings.')
        parts.remove(name)
    parts.insert(parts.index(notifier), name)
    ini(panel,'panel1','plugins',', '.join(parts))
    ini(panel,name,'type','quicklaunch'); ini(panel,name,'alignment','Right')
    ini(panel,name,'apps\\1\\desktop',str(home/'.local/share/applications/doroshell-clipboard.desktop'))
    ini(panel,name,'apps\\size','1')
    script = home/'.local/share/doroshell/clipboard.py'
    launcher = home/'.local/bin/doroshell-clipboard'
    file(str(script.relative_to(home)), (ROOT/'clipboard/clipboard.py').read_bytes())
    file(str(launcher.relative_to(home)), ('#!/bin/sh\nexec /usr/bin/python3 '+shlex.quote(str(script))+' "$@"\n').encode(), 0o755)
    icon = home/'.local/share/doroshell/clipboard.svg'
    file(str(icon.relative_to(home)), (ROOT/'clipboard/clipboard.svg').read_bytes())
    quoted = str(launcher).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
    file('.local/share/applications/doroshell-clipboard.desktop', ('[Desktop Entry]\nType=Application\nName=DoroClipboard\nComment=Session-only clipboard history\nExec="'+quoted+'" --show\nIcon='+str(icon)+'\nTerminal=false\nCategories=Utility;\n').encode())
    file('.config/autostart/doroshell-clipboard.desktop', ('[Desktop Entry]\nType=Application\nName=DoroClipboard\nExec="'+quoted+'"\nOnlyShowIn=LXQt;\n').encode())
    return edits
