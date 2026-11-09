#!/usr/bin/env python3
"""Independent, reversible desktop modules. No package installation or session logout."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sysconfig
from install import atomic, safe, set_ini
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
MODULES = ('snapping', 'screenshots', 'dolphin', 'single-desktop', 'taskbar', 'kate', 'kate-dark', 'dolphin-dark', 'taskbar-drag')


def ini_value(text, section, key):
    match = re.search(r'(?m)^\['+re.escape(section)+r'\]\s*\n', text)
    if not match:
        return None
    rest = text[match.end():]
    body = re.split(r'(?m)^\[', rest, maxsplit=1)[0]
    found = re.search(r'(?m)^'+re.escape(key)+r'\s*=(.*)$', body)
    return found.group(1) if found else None


def ini_set(text, section, key, value):
    if value is not None:
        return set_ini(text, section, key, value)
    match = re.search(r'(?m)^\['+re.escape(section)+r'\]\s*\n', text)
    if not match:
        return text
    end = re.search(r'(?m)^\[', text[match.end():])
    stop = match.end()+end.start() if end else len(text)
    body = re.sub(r'(?m)^'+re.escape(key)+r'\s*=.*\n?', '', text[match.end():stop])
    return text[:match.end()]+body+text[stop:]


def plans(home, module, taskbar_style="icons"):
    edits = []
    def file(name, data, mode=0o644):
        edits.append({'file':name,'kind':'file','after':base64.b64encode(data).decode(),'mode':mode})
    def ini(name, section, key, value):
        edits.append({'file':name,'kind':'ini','section':section,'key':key,'after':value})
    if module in ('snapping','screenshots'):
        script = 'snap' if module=='snapping' else 'screenshot'
        file('.local/share/doroshell/'+script+'.py', (ROOT/'runtime'/f'{script}.py').read_bytes())
        target = home/'.local/share/doroshell'/f'{script}.py'
        wrapper = '#!/bin/sh\nexec /usr/bin/python3 '+shlex.quote(str(target))+' "$@"\n'
        file('.local/bin/doroshell-'+script, wrapper.encode(), 0o755)
        if module=='snapping':
            launcher = str(home/'.local/bin/doroshell-snap')
            file('.config/autostart/doroshell-snap.desktop', ('[Desktop Entry]\nType=Application\nName=DoroShell edge snapping\nExec="'+launcher+'"\nOnlyShowIn=LXQt;\n').encode())
            # An explicit Openbox section; preserve every unrelated key binding.
            block = '\n<!-- DoroShell snapping begin -->\n'
            for key,action in [('W-Left','left'),('W-Right','right'),('W-Down','restore')]:
                from xml.sax.saxutils import escape
                block += f'<keybind key="{key}"><action name="Execute"><command>{escape(shlex.quote(launcher))} {action}</command></action></keybind>\n'
            block += '<!-- DoroShell snapping end -->\n'
            edits.append({'file':'.config/openbox/rc.xml','kind':'snapkeys','after':block})
        else:
            conf = home/'.config/lxqt/globalkeyshortcuts.conf'
            text = conf.read_text() if conf.exists() else ''
            groups = re.findall(r'(?m)^\[(Print\.[^\]]+)\]', text)
            if len(groups)>1:
                raise RuntimeError('Multiple Print bindings found; refusing duplicate shortcut')
            section = groups[0] if groups else 'Print.1'
            for key,value in [('Exec', str(home/'.local/bin/doroshell-screenshot')), ('Enabled','true'),('Comment','DoroShell ScreenGrab selection'),('path',None)]:
                ini('.config/lxqt/globalkeyshortcuts.conf',section,key,value)
    elif module=='taskbar-drag':
        if not Path('/usr/share/dockbarx/lxqt-panel-applet.py').is_file():
            raise RuntimeError('This option requires the existing DockBarX LXQt plugin')
        site = Path(sysconfig.get_path('purelib', scheme='posix_user', vars={'userbase': str(home/'.local')}))
        relative = str(site.relative_to(home))
        file(relative+'/doroshell_dockbarx_drag.py', (ROOT/'runtime/dockbarx_drag.py').read_bytes())
        hook = "import sys; __import__('doroshell_dockbarx_drag').activate() if sys.argv[0] == '/usr/share/dockbarx/lxqt-panel-applet.py' else None\n"
        file(relative+'/doroshell_dockbarx_drag.pth', hook.encode())
    elif module in ('kate-dark', 'dolphin-dark'):
        app = module.removesuffix('-dark')
        if not Path('/usr/share/color-schemes/BreezeDark.colors').is_file():
            raise RuntimeError('Install the optional breeze package for Breeze Dark first')
        ini('.config/'+app+'rc', 'UiSettings', 'ColorScheme', 'BreezeDark')
    elif module in ('dolphin', 'kate'):
        # User MIME associations, not application-owned file choosers.
        for name in ['mimeapps.list', 'lxqt-mimeapps.list']:
            ini('.config/'+name, 'Default Applications',
                'inode/directory' if module=='dolphin' else 'text/plain',
                'org.kde.'+module+'.desktop;')
    elif module=='single-desktop':
        edits.append({'file':'.config/openbox/rc.xml','kind':'desktop','after':'1'})
        edits.append({'file':'.config/openbox/rc.xml','kind':'firstdesk','after':'1'})
    elif module=='taskbar':
        name='.config/lxqt/panel.conf'
        text=(home/name).read_text()
        plugins=ini_value(text,'panel1','plugins')
        if not plugins:
            raise RuntimeError('Expected panel1 configuration; log into LXQt first')
        parts=[p.strip() for p in plugins.split(',')]
        # Only detach known DockBarX entries when this option is explicitly applied.
        original_parts = parts[:]
        parts = [p for p in parts if p != 'dockbarx' and ini_value(text,p,'type') != 'dockbarx']
        task=next((p for p in parts if p=='taskbar' or ini_value(text,p,'type')=='taskbar'),None)
        if not task:
            task='doroshelltaskbar'
            parts.append(task)
            ini(name,task,'type','taskbar')
        if parts != original_parts:
            ini(name,'panel1','plugins',', '.join(parts))
        if taskbar_style not in ('icons', 'standard'):
            raise ValueError('Unknown taskbar style')
        ini(name,task,'buttonStyle','Icon' if taskbar_style=='icons' else 'IconText')
        ini(name,task,'groupingEnabled','true')
        ini(name,task,'iconByClass','true')
        ini(name,task,'showOnlyOneDesktopTasks','false')
    return edits


def read_value(edit, data):
    if edit['kind']=='file':
        return base64.b64encode(data).decode() if data is not None else None
    text=(data or b'').decode()
    if edit['kind']=='ini':
        return ini_value(text,edit['section'],edit['key'])
    if edit['kind'] in ('desktop', 'firstdesk'):
        # Validate XML, but edit only the owned element to preserve formatting/comments.
        tree = ET.fromstring(text)
        blocks = re.findall(r'<desktops\b[^>]*>(.*?)</desktops>', text, re.S)
        if len(blocks) != 1:
            raise RuntimeError('Expected one Openbox desktops section')
        tag = 'number' if edit['kind']=='desktop' else 'firstdesk'
        values = re.findall(r'<'+tag+r'>\s*(\d+)\s*</'+tag+r'>', blocks[0])
        if len(values)>1 or (tag=='number' and not values):
            raise RuntimeError('Expected one Openbox '+tag)
        for application in tree.iter():
            if application.tag.rsplit('}',1)[-1] == 'application':
                for child in application:
                    value = (child.text or '').strip()
                    if child.tag.rsplit('}',1)[-1]=='desktop' and value.isdigit() and int(value)>1:
                        raise RuntimeError('Application rules target other desktops; review them first')
        return values[0] if values else None
    found=re.search(r'\n<!-- DoroShell snapping begin -->.*?<!-- DoroShell snapping end -->\n',text,re.S)
    return found.group(0) if found else None


def write_value(edit, data, value):
    kind=edit['kind']
    if kind=='file':
        return base64.b64decode(value) if value is not None else None
    text=(data or b'').decode()
    if kind=='ini':
        return ini_set(text,edit['section'],edit['key'],value).encode()
    if kind in ('desktop', 'firstdesk'):
        read_value(edit, data)
        tag = 'number' if kind=='desktop' else 'firstdesk'
        def update(match):
            body = match[2]
            pattern = r'<'+tag+r'>\s*\d+\s*</'+tag+r'>'
            replacement = '<'+tag+'>'+value+'</'+tag+'>' if value is not None else ''
            body = re.sub(pattern, replacement, body) if re.search(pattern, body) else body+replacement
            return match[1]+body+match[3]
        return re.sub(r'(<desktops\b[^>]*>)(.*?)(</desktops>)', update, text, count=1, flags=re.S).encode()
    old=read_value(edit,data)
    if old:
        text=text.replace(old,'')
    if value:
        for key in ('W-Left','W-Right','W-Down'):
            if re.search(r'<keybind\s+key=[\"\']'+key+r'[\"\']',text):
                raise RuntimeError('Existing Openbox shortcut conflicts: '+key)
        if text.count('</keyboard>')!=1:
            raise RuntimeError('Expected Openbox keyboard section')
        text=text.replace('</keyboard>',value+'</keyboard>')
    return text.encode()


def live_print_change(path, original, desired):
    """Prepare one LXQt daemon edit, checking its command against the on-disk binding."""
    import tempfile
    from gi.repository import Gio, GLib
    from PySide6.QtCore import QSettings
    if Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config')).resolve() != path.parent.parent.resolve():
        raise RuntimeError('The shortcut daemon and target must use the same configuration home')
    service = 'org.lxqt.global_key_shortcuts'
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def call(method, signature, *args):
        return bus.call_sync(service, '/daemon', service+'.daemon', method, GLib.Variant(signature, args),
                             None, Gio.DBusCallFlags.NO_AUTO_START, 3000, None).unpack()

    def binding(data):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'shortcut.conf'
            source.write_bytes(data or b'')
            cfg = QSettings(str(source), QSettings.Format.IniFormat)
            groups = [group for group in cfg.childGroups() if group.startswith('Print.')]
            if len(groups) != 1 or not cfg.value(groups[0]+'/Enabled', False, type=bool):
                raise RuntimeError('Live setup requires one enabled Print command; use offline setup for this layout')
            group = groups[0]
            argv = cfg.value(group+'/Exec')
            if isinstance(argv, str):
                argv = [argv]
            if not argv or not re.fullmatch(r'Print\.\d+', group):
                raise RuntimeError('Unsupported live Print binding')
            return int(group.split('.')[1]), cfg.value(group+'/Comment', ''), argv
    action, description, argv = binding(original)
    target, new_description, new_argv = binding(desired)
    if target != action:
        raise RuntimeError('Print binding changed identity')
    def verify():
        valid, key, label, enabled, command, arguments = call('getCommandActionInfoById', '(t)', action)
        if not valid or key != 'Print' or not enabled or [command, *arguments] != argv or label != description:
            raise RuntimeError('Active Print shortcut differs from its configuration; refusing to change it')
    verify()
    def apply():
        verify()
        if path.read_bytes() != original:
            raise RuntimeError('Shortcut settings changed during setup')
        if not call('modifyCommandAction', '(tsass)', action, new_argv[0], new_argv[1:], new_description)[0]:
            raise RuntimeError('LXQt refused to update its Print shortcut')
        if binding(path.read_bytes()) != (target, new_description, new_argv):
            raise RuntimeError('LXQt did not persist the requested Print shortcut')
    return apply


def run(home, module, apply=False, rollback=False, taskbar_style="icons", active_print=False):
    if module not in MODULES:
        raise ValueError("Unknown module")
    manifest=home/'.local/state/doroshell'/f'{module}.json'
    safe(manifest,home)
    saved=json.loads(manifest.read_text()) if manifest.exists() else None
    if rollback and not saved:
        print(module+': nothing to restore')
        return
    edits=saved['edits'] if rollback else plans(home,module,taskbar_style)
    if not edits:
        print(module+': existing icon taskbar retained')
        return
    original={}
    changed={}
    modes={}
    record=[]
    for index,edit in enumerate(edits):
        path=home/edit['file']
        safe(path,home)
        if path not in changed:
            original[path]=path.read_bytes() if path.exists() else None
            changed[path]=original[path]
            modes[path]=path.stat().st_mode & 0o777 if path.exists() else edit.get('mode',0o644)
        current=read_value(edit,changed[path])
        old=next((e for e in saved['edits'] if all(e.get(k)==edit.get(k) for k in ('file','kind','section','key'))),None) if saved else None
        if old and current not in (old['after'], old['before']):
            raise RuntimeError(f'Personal edit detected; no changes applied: {path}')
        entry=dict(edit)
        entry['before']=old['before'] if old else current
        changed[path]=write_value(edit,changed[path],edit['before'] if rollback else edit['after'])
        record.append(entry)
        print(('Restore ' if rollback else 'Configure ')+edit['file']+(' / '+edit['key'] if 'key' in edit else ''))
    if saved and not rollback:
        for old in saved['edits']:
            if not any(all(e.get(k)==old.get(k) for k in ('file','kind','section','key')) for e in record):
                path=home/old['file']
                safe(path, home)
                if read_value(old, path.read_bytes() if path.exists() else None) != old['after']:
                    raise RuntimeError('Personal edit detected in previously managed setting: '+str(path))
                record.append(old)
        # Keep insertion order stable for byte-exact rollback of newly created sections.
        identity = lambda e: tuple(e.get(k) for k in ('file','kind','section','key'))
        order = [identity(e) for e in saved['edits']]
        record.sort(key=lambda e: order.index(identity(e)) if identity(e) in order else len(order))
    if not apply and not rollback:
        print('Plan only. Add --apply.')
        return
    shortcuts = home/'.config/lxqt/globalkeyshortcuts.conf'
    update_print = None
    if active_print and original[shortcuts] != changed[shortcuts]:
        update_print = live_print_change(shortcuts, original[shortcuts], changed[shortcuts])
    if not rollback:
        backup=dict(saved['backup']) if saved else {}
        for p,v in original.items():
            backup.setdefault(str(p.relative_to(home)), {'data':base64.b64encode(v).decode() if v is not None else None,'mode':modes[p]})
        atomic(manifest,(json.dumps({'edits':record,'backup':backup},indent=2)+'\n').encode())
    if rollback and update_print:
        update_print()
    for path,data in changed.items():
        if path == shortcuts and update_print:
            if not rollback:
                update_print()
            continue
        if rollback:
            before=saved['backup'][str(path.relative_to(home))]
            # Restore exact bytes when no unrelated changes occurred.
            base=base64.b64decode(before['data']) if before['data'] is not None else None
            installed=base
            for edit in saved['edits']:
                if home/edit['file']==path:
                    installed=write_value(edit,installed,edit['after'])
            if original[path]==installed:
                data=base
                modes[path]=before['mode']
        if data==original[path]:
            continue
        if data is None:
            path.unlink(missing_ok=True)
        else:
            atomic(path,data,modes[path])
    if rollback:
        manifest.unlink()


def refresh_dockbarx():
    """Never sever output pipes inherited by already-running applications."""
    raise RuntimeError(
        'Files saved. DockBarX live refresh is disabled: applications can inherit '
        'its output pipes and fail with EPIPE when it exits. Changes take effect '
        'at your next normal login; no running process was stopped.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('module',choices=MODULES)
    parser.add_argument('--home',type=Path,default=Path.home())
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--taskbar-style', choices=('icons','standard'), default='icons')
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--apply',action='store_true')
    actions.add_argument('--rollback',action='store_true')
    args=parser.parse_args()
    if os.geteuid()==0:
        parser.error('Run as your desktop user, not root')
    components={'screenshots':['lxqt-globalkeysd'], 'taskbar':['lxqt-panel']}.get(args.module,[])
    if args.module == 'screenshots' and (args.apply or args.rollback) and args.home.resolve() == Path.home().resolve():
        if subprocess.run(['pgrep', '-u', str(os.getuid()), '-f', '^/usr/bin/lxqt-globalkeysd$'], stdout=subprocess.DEVNULL).returncode == 0:
            run(args.home, args.module, args.apply, args.rollback, active_print=True)
            raise SystemExit(0)
    if args.live and not (args.apply or args.rollback):
        parser.error('--live requires --apply or --rollback')
    if args.live and args.module=='single-desktop':
        parser.error('One-desktop changes are saved for the next login; live workspace migration is not supported')
    if args.module in ('kate','dolphin','kate-dark','dolphin-dark') and (args.apply or args.rollback):
        app=args.module.removesuffix('-dark')
        import shutil
        if args.apply and not shutil.which(app):
            parser.error('Install '+app+' before opting in')
        if args.module.endswith('-dark') and subprocess.run(['pgrep','-u',str(os.getuid()),'-x',app],stdout=subprocess.DEVNULL).returncode==0:
            parser.error('Save your work and close '+app+' yourself before changing its theme')
    if args.live and args.module=='taskbar-drag':
        if args.home.resolve()!=Path.home().resolve():
            parser.error('--live requires the current user home')
        run(args.home,args.module,args.apply,args.rollback)
        refresh_dockbarx()
        raise SystemExit(0)
    if args.live:
        from integrate import live_run
        # Preflight; desktop component restarts are refused by live_run.
        if not args.rollback:
            run(args.home,args.module,taskbar_style=args.taskbar_style)
        live_run(args.home, operation=lambda:run(args.home,args.module,args.apply,args.rollback,args.taskbar_style), components=components)
        if args.module in ('snapping','single-desktop'):
            subprocess.run(['openbox','--reconfigure'],check=True)
        if args.module=='snapping' and args.apply:
            subprocess.Popen([str(args.home/'.local/bin/doroshell-snap')],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if args.module=='snapping' and args.rollback:
            subprocess.run(['/usr/bin/python3',str(ROOT/'runtime/snap.py'),'stop'],check=True)
    else:
        if (args.apply or args.rollback) and args.home.resolve()==Path.home().resolve() and components:
            for name in components:
                if subprocess.run(['pgrep','-u',str(os.getuid()),'-f','^/usr/bin/'+name+'$'],stdout=subprocess.DEVNULL).returncode==0:
                    parser.error('Component is running; live restarts are disabled. Use the native panel next-login workflow or apply while the component is stopped.')
        run(args.home,args.module,args.apply,args.rollback,args.taskbar_style)
