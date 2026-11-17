#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Prepare a native LXQt profile; enable/restore only at a future normal login."""
import argparse
import ast
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
from PySide6.QtCore import QSettings
from gi.repository import Gio
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from install import PlanError, safe, validate_backup
from modules import atomic
from panel.layout import installed_panel, preserve_sections, sections, select_panel


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def profile(original, home, launchers, hidden, panel=None):
    """Keep unknown widgets and settings; replace DockBarX in its original slot."""
    with tempfile.TemporaryDirectory() as tmp:
        config_path=Path(tmp)/'panel.conf';config_path.write_text(original)
        cfg=QSettings(str(config_path),QSettings.Format.IniFormat)
        selected=select_panel(cfg,panel)
        bounded = panel is not None
        if bounded: sections(original)
        before={key:cfg.value(key) for key in cfg.allKeys()}
        plugins=cfg.value(selected+'/plugins',[])
        if isinstance(plugins,str):plugins=[plugins]
        if not plugins:raise ValueError('Missing panel1 plugin list')
        if launchers is None:
            dockbarx = any(cfg.value(name+'/type', name) == 'dockbarx' for name in plugins)
            if dockbarx and home.resolve() != Path.home().resolve():
                raise ValueError('Alternate-home DockBarX migration requires explicit launcher data')
            launchers = launchers_from_dockbarx() if dockbarx else []
        result=[];inserted=False
        for name in plugins:
            kind=cfg.value(name+'/type',name)
            if kind in ('dockbarx','taskbar'):
                if not inserted:
                    result.append('doroshellTasks');inserted=True
            else:result.append(name)
        if not inserted:
            result[1:1]=['doroshellTasks']
        start = home/'.local/share/applications/lxqt-comfort.desktop'
        if start.is_file() and not any(
            cfg.value(key) == str(start) for name in result for key in cfg.allKeys()
            if key.startswith(name+'/apps/') and key.endswith('/desktop')
        ):
            name = 'doroshellStart'
            if name in cfg.childGroups() or name in result:
                raise ValueError('Panel widget name conflict: '+name)
            cfg.setValue(name+'/type', 'quicklaunch')
            cfg.setValue(name+'/apps/1/desktop', str(start))
            cfg.setValue(name+'/apps/size', 1)
            result.insert(0, name)
        if cfg.contains('doroshellTasks/type') and cfg.value('doroshellTasks/type')!='taskbar':
            raise ValueError('Panel widget name conflict: doroshellTasks')
        cfg.setValue('doroshellTasks/type','taskbar')
        pins=[];identities=set()
        for path in launchers:
            path=Path(path)
            if not path.is_absolute() or path.suffix!='.desktop' or not path.is_file():
                raise ValueError('Unavailable desktop launcher: '+str(path))
            if str(path) in pins:continue
            app=Gio.DesktopAppInfo.new_from_filename(str(path))
            if app is None:raise ValueError('Invalid application desktop entry: '+str(path))
            identity=(app.get_startup_wm_class() or path.stem).casefold()
            if identity in identities:raise ValueError('Ambiguous pinned application identity: '+identity)
            identities.add(identity);pins.append(str(path))
        result=merge_quicklaunch(cfg,result,pins,identities,home)
        cfg.setValue('doroshellTasks/doroshellPinned',pins)
        for key,value in {'buttonStyle':'Icon','buttonWidth':48,'groupingEnabled':True,'iconByClass':True,'showOnlyOneDesktopTasks':False}.items():
            cfg.setValue('doroshellTasks/'+key,value)
        notifier=next((n for n in result if cfg.value(n+'/type',n)=='statusnotifier'),None)
        if notifier is None:
            notifier='doroshellNotifier'
            if cfg.contains(notifier+'/type') and cfg.value(notifier+'/type') != 'statusnotifier':
                raise ValueError('Panel widget name conflict: '+notifier)
            result.append(notifier);cfg.setValue(notifier+'/type','statusnotifier')
        # A standalone --config file does not inherit the stock panel's plugin types.
        for name in result:
            if not cfg.contains(name+'/type'):
                cfg.setValue(name+'/type', name)
        cfg.setValue(notifier+'/doroshellCollapseNew', hidden is None and
                     not any(cfg.contains(notifier+'/'+key) for key in ('hideList','autoHideList')))
        cfg.setValue(notifier+'/alignment','Right');cfg.setValue(notifier+'/doroshellPopup',True)
        if hidden is not None:cfg.setValue(notifier+'/hideList',hidden)
        clock=next((name for name in result if cfg.value(name+'/type')=='worldclock'), None)
        if clock is None:
            clock='doroshellClock'
            if clock in cfg.childGroups():
                raise ValueError('Panel widget name conflict: '+clock)
            cfg.setValue(clock+'/type','worldclock')
        else:
            result.remove(clock)
        result.append(clock)
        cfg.setValue(clock+'/alignment','Right')
        cfg.setValue(clock+'/doroshellTwoLine',True)
        cfg.setValue(clock+'/formatType','short-timeonly')
        cfg.setValue(clock+'/dateFormatType','short')
        cfg.setValue(clock+'/showDate',True)
        cfg.setValue(clock+'/datePosition','below')
        if not cfg.contains(clock+'/customFormat'):
            cfg.setValue(clock+'/useAdvancedManualFormat',True)
            cfg.setValue(clock+'/customFormat',"h:mm AP'<br/>'ddd, MMM d")
        desktop=next((name for name in result if cfg.value(name+'/type',name)=='showdesktop'),None)
        if desktop is None:
            desktop='doroshellShowDesktop'
            if cfg.contains(desktop+'/type') and cfg.value(desktop+'/type')!='showdesktop':
                raise ValueError('Panel widget name conflict: '+desktop)
            cfg.setValue(desktop+'/type','showdesktop')
        else:
            result.remove(desktop)
        result.append(desktop)
        cfg.setValue(desktop+'/alignment','Right')
        cfg.setValue(desktop+'/doroshellEdge',True)
        cfg.setValue(selected+'/plugins',result)
        style={'doroshellTheme':True,'position':'Bottom','panelSize':40,'iconSize':cfg.value(selected+'/iconSize', 28),'lineCount':1}
        # Explicit selection keeps the chosen panel's geometry; only its DoroShell widgets/theme change.
        if bounded: style={'doroshellTheme':True}
        for key,value in style.items():cfg.setValue(selected+'/'+key,value)
        cfg.sync()
        if cfg.status()!=QSettings.Status.NoError:raise RuntimeError('Profile serialization failed')
        if bounded:
            after={key:cfg.value(key) for key in cfg.allKeys()}
            changed={key.split('/',1)[0] for key in before.keys()|after.keys() if before.get(key)!=after.get(key)}
            content=preserve_sections(original,config_path.read_text(),changed)
            return content.encode()
        return config_path.read_bytes()


def app_info(path):
    """Desktop application for a launcher path, or None (missing file, Type=Link, invalid entry)."""
    if not Path(path).is_absolute() or not Path(path).is_file():return None
    try:return Gio.DesktopAppInfo.new_from_filename(str(path))
    except TypeError:return None  # PyGObject raises when the constructor returns NULL


def merge_quicklaunch(cfg, plugins, pins, identities, home=None):
    """Move stock Quick Launch applications into taskbar pins so each app is one button.

    Only plain application launchers move. The DoroShell Start launcher, folder links,
    custom commands, missing files and ambiguous window identities stay in Quick Launch.
    A widget with unrecognised keys or non-text values is left untouched, a widget from
    which nothing moves is not rewritten, and a widget is removed only when every entry
    moved. `pins` and `identities` are extended in place; the new plugin list is returned.
    """
    start=str((home or Path.home())/'.local/share/applications/lxqt-comfort.desktop')
    result=[]
    for name in plugins:
        if name=='doroshellStart' or cfg.value(name+'/type',name)!='quicklaunch':
            result.append(name);continue
        prefix=name+'/apps/'
        size=cfg.value(prefix+'size')
        size=int(size) if isinstance(size,str) and size.isdigit() else None
        entries={};unknown=size is None
        for key in cfg.allKeys():
            if unknown:break
            if not key.startswith(prefix) or key==prefix+'size':continue
            index,_,field=key[len(prefix):].partition('/')
            value=cfg.value(key)
            if not index.isdigit() or not field or '/' in field or not isinstance(value,str):
                unknown=True;break
            if 1<=int(index)<=size:  # QSettings arrays may keep stale entries past apps/size
                entries.setdefault(int(index),{})[field]=value
        if unknown or not entries:
            result.append(name);continue
        moved=[];leftover=[]
        for index in sorted(entries):
            entry=entries[index]
            path=entry.get('desktop')
            if set(entry)!={'desktop'} or path==start:
                leftover.append(entry);continue
            if path in pins:
                moved.append(path);continue  # already pinned: this was the duplicate
            app=app_info(path)
            identity=(app.get_startup_wm_class() or Path(path).stem).casefold() if app is not None else None
            if identity is None or identity in identities:
                leftover.append(entry);continue
            identities.add(identity);pins.append(path);moved.append(path)
        if not moved:
            result.append(name);continue
        cfg.remove(name+'/apps')
        if leftover:
            for number,entry in enumerate(leftover,1):
                for field,value in entry.items():
                    cfg.setValue(f'{prefix}{number}/{field}',value)
            cfg.setValue(prefix+'size',len(leftover))
            result.append(name)
        else:
            cfg.remove(name)
    return result


def merge_existing(home, preview=False):
    """Apply merge_quicklaunch to an already installed DoroShell panel profile (next login).

    When the profile is still exactly as DoroShell installed it, the native-panel manifest
    is updated too (two-phase, like upgrade()), so restore/removal keep working. A profile
    the user already edited keeps its manifest; restoring it needs --keep-panel-edits as before.
    """
    with panel_lock(home):  # The manifest read-modify-write must not interleave with upgrade/switch.
        return locked_merge_existing(home, preview)


def locked_merge_existing(home, preview):
    state=home/'.local/state/doroshell'
    config=home/'.config/doroshell/panel.conf';manifest=state/'native-panel.json'
    for path in (state,config,manifest):safe(path,home)
    if not config.is_file():raise ValueError('DoroShell panel profile is not installed')
    original=config.read_bytes()
    selected=installed_panel(original.decode())
    with tempfile.TemporaryDirectory() as tmp:
        work=Path(tmp)/'panel.conf';work.write_bytes(original)
        cfg=QSettings(str(work),QSettings.Format.IniFormat)
        plugins=cfg.value(selected+'/plugins',[])
        if isinstance(plugins,str):plugins=[plugins]
        if 'doroshellTasks' not in plugins:raise ValueError('DoroShell taskbar is not in '+selected)
        pins=cfg.value('doroshellTasks/doroshellPinned',[])
        if isinstance(pins,str):pins=[pins]
        pins=[p for p in (pins or []) if isinstance(p,str)]
        identities=set()
        for path in pins:
            app=app_info(path)
            identities.add(((app.get_startup_wm_class() if app else None) or Path(path).stem).casefold())
        before=list(pins)
        snapshot={k:cfg.value(k) for k in cfg.allKeys()}
        result=merge_quicklaunch(cfg,plugins,pins,identities,home)
        if result==plugins and pins==before and {k:cfg.value(k) for k in cfg.allKeys()}==snapshot:
            print('Nothing to merge: no Quick Launch applications next to the taskbar');return
        for path in pins[len(before):]:print('Pin in taskbar:',path)
        if preview:return
        cfg.setValue(selected+'/plugins',result);cfg.setValue('doroshellTasks/doroshellPinned',pins)
        cfg.sync()
        if cfg.status()!=QSettings.Status.NoError:raise RuntimeError('Profile serialization failed')
        after={k:cfg.value(k) for k in cfg.allKeys()}
        changed={key.split('/',1)[0] for key in snapshot.keys()|after.keys() if snapshot.get(key)!=after.get(key)}
        content=preserve_sections(original.decode(),work.read_text(),changed).encode()
    record=entry=None
    if manifest.is_file():
        record=json.loads(manifest.read_text());validate_record(record)
        entry=record['.config/doroshell/panel.conf']
        if digest(original) not in (entry['after'],entry.get('pending_after')):entry=None  # already a personal edit
    state.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='panel-before-merge-',suffix='.conf',dir=state,delete=False) as backup:
        backup.write(original);backup.flush();os.fsync(backup.fileno())
    os.chmod(backup.name,0o600)
    if entry is not None:
        entry['pending_after']=digest(content);atomic(manifest,json.dumps(record,indent=2).encode())
    atomic(config,content,config.stat().st_mode&0o777)
    if entry is not None:
        entry['after']=entry.pop('pending_after');atomic(manifest,json.dumps(record,indent=2).encode())
    print('Saved previous panel settings:',backup.name)
    if record is not None and entry is None:
        print('Note: this profile already had personal edits; restoring the stock panel needs --keep-panel-edits.')
    print('Takes effect at your next normal login. No process stopped or started.')

def launchers_from_dockbarx():
    raw=subprocess.check_output(['gsettings','get','org.dockbarx.dockbarx','launchers'],text=True)
    if raw.strip()=='@as []':return []
    result=[]
    for value in ast.literal_eval(raw):
        path=value.split(';',1)[-1]
        if path not in result:result.append(path)
    return result


def prepare(home, output, binary, hidden=None, launchers=None, panel=None):
    binary=binary.resolve()
    if not binary.is_file() or not os.access(binary,os.X_OK):raise ValueError('Build the native panel first')
    if output.exists() and any(output.iterdir()):raise ValueError('Preparation directory must be empty')
    source=home/'.config/lxqt/panel.conf'
    original=source.read_bytes()
    content=profile(original.decode(),home,launchers,hidden,panel)
    print('Prepare DoroShell widgets on:', panel or 'panel1')
    output.mkdir(parents=True,exist_ok=True);output.chmod(0o700)
    atomic(output/'panel.conf',content)
    atomic(output/'plan.json',json.dumps({'binary':str(binary),'binary_hash':digest(binary.read_bytes()),'source_hash':digest(original),'profile_hash':digest(content),'panel':panel or 'panel1'},indent=2).encode())
    print('Prepared:',output,'— current panel and autostart unchanged')


def launcher(binary, config):
    script = '#!/usr/bin/python3\nimport os\nfrom pathlib import Path\np=Path.home()/".local/state/doroshell/native-panel.log"\np.parent.mkdir(parents=True,exist_ok=True)\nfd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)\nos.dup2(fd,1);os.dup2(fd,2);os.close(fd)\n'
    recipe = Path(binary).parents[2]/'recipe/native_rebuild.py' if len(Path(binary).parents) > 2 else None
    if recipe and recipe.is_file():
        # Missing libraries after a system update: rebuild in the background and use the
        # stock panel with its own LXQt profile, leaving DoroShell's panel.conf untouched.
        script += ('import subprocess\nif os.access("/usr/bin/lxqt-panel",os.X_OK) and subprocess.run(["/usr/bin/python3",'
                   +repr(str(recipe))+',"login","panel","--current",'+repr(str(binary))+']).returncode:\n'
                   '    os.execv("/usr/bin/lxqt-panel",["/usr/bin/lxqt-panel"])\n')
    return script+'os.execv('+repr(str(binary))+','+repr([str(binary),'--config',str(config)])+')\n'


def validate_record(record):
    targets = {'.config/doroshell/panel.conf', '.local/bin/doroshell-native-panel', '.config/autostart/lxqt-panel.desktop'}
    if not isinstance(record, dict) or set(record) != targets:
        raise ValueError('Unexpected native panel manifest targets')
    for entry in record.values():
        validate_backup(entry, 'before')
        for field in ('after', 'pending_after'):
            if field == 'pending_after' and field not in entry: continue
            if not isinstance(entry.get(field), str) or not re.fullmatch('[0-9a-f]{64}', entry[field]):
                raise ValueError('Invalid native panel recovery hash')


@contextmanager
def panel_lock(home):
    """Serialize every panel staging change: upgrade, switch, rollback and background rebuilds."""
    lock = home/'.local/state/doroshell/native-panel.lock'
    safe(lock, home)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def upgrade(home, binary, preview=False, require=None):
    """Replace only the staged executable reference; retain the user's panel profile.

    With ``require``, upgrade only while the launcher still runs that executable and
    return False otherwise, checked under the same lock as the change."""
    with panel_lock(home):
        return locked_upgrade(home, binary, preview, require)


def locked_upgrade(home, binary, preview, require):
    manifest = home/'.local/state/doroshell/native-panel.json'
    wrapper = home/'.local/bin/doroshell-native-panel'
    for path in (manifest, wrapper): safe(path, home)
    if require is not None and not (manifest.is_file() and wrapper.is_file()
                                    and repr(str(require)) in wrapper.read_text()):
        return False
    binary = binary.resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError('Build the native panel before upgrading')
    record = json.loads(manifest.read_text())
    validate_record(record)
    key = str(wrapper.relative_to(home))
    entry = record[key]
    current = wrapper.read_bytes()
    if wrapper.stat().st_mode & 0o777 != 0o755 or digest(current) not in (entry['after'], entry.get('pending_after')):
        raise RuntimeError('Edited panel launcher; refusing upgrade')
    desired = launcher(binary, home/'.config/doroshell/panel.conf').encode()
    print('Update native panel executable for next login; retain panel settings')
    if preview: return True
    entry['pending_after'] = digest(desired)
    atomic(manifest, json.dumps(record, indent=2).encode())
    atomic(wrapper, desired, 0o755)
    entry['after'] = entry.pop('pending_after')
    atomic(manifest, json.dumps(record, indent=2).encode())
    return True


def switch(home, prepared=None, rollback=False, preview=False, keep_panel_edits=False):
    with panel_lock(home):
        return locked_switch(home, prepared, rollback, preview, keep_panel_edits)


def locked_switch(home, prepared, rollback, preview, keep_panel_edits):
    manifest=home/'.local/state/doroshell/native-panel.json'
    safe(manifest,home)
    saved = json.loads(manifest.read_text()) if manifest.exists() else None
    if saved is not None: validate_record(saved)
    if rollback:
        if saved is None:return
        record=saved
        files={home/k:base64.b64decode(v['before']) if v['before'] is not None else None for k,v in record.items()}
    else:
        plan=json.loads((prepared/'plan.json').read_text());binary=Path(plan['binary'])
        content=(prepared/'panel.conf').read_bytes()
        if digest((home/'.config/lxqt/panel.conf').read_bytes())!=plan['source_hash'] or digest(content)!=plan['profile_hash']:
            raise RuntimeError('Panel or prepared profile changed; prepare again')
        if not binary.is_file() or not os.access(binary,os.X_OK):raise ValueError('Prepared panel binary is unavailable')
        if digest(binary.read_bytes())!=plan['binary_hash']:raise RuntimeError('Panel binary changed; prepare again')
        print('Prepared DoroShell panel:', installed_panel(content.decode()))
        config=home/'.config/doroshell/panel.conf';wrapper=home/'.local/bin/doroshell-native-panel'
        # File-backed output avoids breaking launched applications when a parent exits.
        script=launcher(binary, config)
        quoted=str(wrapper).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
        desktop='[Desktop Entry]\nType=Application\nName=DoroShell Panel\nExec="'+quoted+'"\nOnlyShowIn=LXQt;\nX-LXQt-Module=true\n'
        files={config:content,wrapper:script.encode(),home/'.config/autostart/lxqt-panel.desktop':desktop.encode()}
        record=saved if saved is not None else {}
    edited_config = None
    for path,data in files.items():
        safe(path,home);key=str(path.relative_to(home));current=path.read_bytes() if path.exists() else None
        if saved is not None:
            before = base64.b64decode(record[key]['before'], validate=True) if record[key]['before'] is not None else None
            if current is not None:
                current_mode = path.stat().st_mode & 0o777
                installed_mode = 0o755 if path.name == 'doroshell-native-panel' else 0o600
                if current_mode != installed_mode and not (current == before and current_mode == record[key]['mode']):
                    raise RuntimeError('Personal mode edit; refusing to change: '+key)
            if current != before and digest(current) not in (record[key]['after'], record[key].get('pending_after')):
                if rollback and key == '.config/doroshell/panel.conf' and current is not None:
                    if not keep_panel_edits:
                        raise RuntimeError('Panel settings changed. Restore with --keep-panel-edits to save a private copy before switching back.')
                    edited_config = current
                else:
                    raise RuntimeError('Personal edit; refusing to change: '+key)
            if not rollback and digest(data) != record[key]['after']:
                raise RuntimeError('Another switch is staged; restore it before changing profiles')
        else:record[key]={'before':base64.b64encode(current).decode() if current is not None else None,'mode':path.stat().st_mode&0o777 if path.exists() else 0o600,'after':digest(data)}
    if preview:
        for path in files:
            print('Would configure for next login:', path.relative_to(home))
        return
    if edited_config is not None:
        with tempfile.NamedTemporaryFile(prefix='panel-edited-', suffix='.conf', dir=manifest.parent, delete=False) as backup:
            backup.write(edited_config)
            backup.flush()
            os.fsync(backup.fileno())
        print('Saved edited panel settings:', backup.name)
    if saved is None:atomic(manifest,json.dumps(record,indent=2).encode())
    for path,data in files.items():
        if data is None:path.unlink(missing_ok=True)
        else:atomic(path,data,record[str(path.relative_to(home))]['mode'] if rollback else (0o755 if path.name=='doroshell-native-panel' else 0o600))
    if rollback:
        # Keep sizing history with the backups when its panel is removed.
        size_record = manifest.with_name('taskbar-size.json')
        if size_record.exists():
            safe(size_record, home)
            with tempfile.NamedTemporaryFile(prefix='taskbar-size-before-restore-', suffix='.json',
                                             dir=manifest.parent, delete=False) as backup:
                backup_name = backup.name
            size_record.replace(backup_name)
        manifest.unlink()
    print('Saved for your next normal login. No process stopped or started.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','preview-next-login','enable-next-login','restore-next-login','merge-quicklaunch','preview-merge-quicklaunch'])
    p.add_argument('--home',type=Path,default=Path.home());p.add_argument('--prepared',type=Path);p.add_argument('--binary',type=Path);p.add_argument('--hide',action='append',default=None)
    p.add_argument('--panel',help='Explicit panel ID to adapt during prepare; other panels are preserved')
    p.add_argument('--keep-panel-edits', action='store_true', help='Save changed panel settings privately before restoring the previous panel')
    a=p.parse_args()
    if a.panel is not None and a.action!='prepare':p.error('--panel is only valid for prepare; later actions use the prepared profile')
    if a.action=='prepare':
        if not a.prepared or not a.binary:p.error('prepare needs --prepared and --binary')
        prepare(a.home,a.prepared,a.binary,a.hide,panel=a.panel)
    elif a.action in ('preview-next-login', 'enable-next-login'):
        if not a.prepared:p.error('enable-next-login needs --prepared')
        switch(a.home,a.prepared,preview=a.action=='preview-next-login')
    elif a.action in ('merge-quicklaunch','preview-merge-quicklaunch'):
        merge_existing(a.home,preview=a.action.startswith('preview'))
    else:switch(a.home,rollback=True,keep_panel_edits=a.keep_panel_edits)


if __name__=='__main__':
    try:main()
    except PlanError as error:sys.exit('profile.py: '+str(error))
