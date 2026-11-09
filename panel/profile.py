#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Prepare a native LXQt profile; enable/restore only at a future normal login."""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from PySide6.QtCore import QSettings
from gi.repository import Gio
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from install import safe
from modules import atomic


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def profile(original, home, launchers, hidden):
    """Keep unknown widgets and settings; replace DockBarX in its original slot."""
    with tempfile.TemporaryDirectory() as tmp:
        config_path=Path(tmp)/'panel.conf';config_path.write_text(original)
        cfg=QSettings(str(config_path),QSettings.Format.IniFormat)
        panels=cfg.value('panels',['panel1'])
        if isinstance(panels,str):panels=[panels]
        if panels!=['panel1']:raise ValueError('Only a single panel1 layout is supported')
        plugins=cfg.value('panel1/plugins',[])
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
        cfg.setValue('panel1/plugins',result)
        for key,value in {'doroshellTheme':True,'position':'Bottom','panelSize':40,'iconSize':cfg.value('panel1/iconSize', 28),'lineCount':1}.items():cfg.setValue('panel1/'+key,value)
        cfg.sync()
        if cfg.status()!=QSettings.Status.NoError:raise RuntimeError('Profile serialization failed')
        return config_path.read_bytes()


def launchers_from_dockbarx():
    raw=subprocess.check_output(['gsettings','get','org.dockbarx.dockbarx','launchers'],text=True)
    if raw.strip()=='@as []':return []
    result=[]
    for value in ast.literal_eval(raw):
        path=value.split(';',1)[-1]
        if path not in result:result.append(path)
    return result


def prepare(home, output, binary, hidden=None, launchers=None):
    binary=binary.resolve()
    if not binary.is_file() or not os.access(binary,os.X_OK):raise ValueError('Build the native panel first')
    if output.exists() and any(output.iterdir()):raise ValueError('Preparation directory must be empty')
    source=home/'.config/lxqt/panel.conf'
    original=source.read_bytes()
    content=profile(original.decode(),home,launchers,hidden)
    output.mkdir(parents=True,exist_ok=True);output.chmod(0o700)
    atomic(output/'panel.conf',content)
    atomic(output/'plan.json',json.dumps({'binary':str(binary),'binary_hash':digest(binary.read_bytes()),'source_hash':digest(original),'profile_hash':digest(content)},indent=2).encode())
    print('Prepared:',output,'— current panel and autostart unchanged')


def switch(home, prepared=None, rollback=False, preview=False, keep_panel_edits=False):
    manifest=home/'.local/state/doroshell/native-panel.json'
    safe(manifest,home)
    saved = json.loads(manifest.read_text()) if manifest.exists() else None
    targets = {'.config/doroshell/panel.conf', '.local/bin/doroshell-native-panel', '.config/autostart/lxqt-panel.desktop'}
    if saved is not None and set(saved) != targets:
        raise RuntimeError('Unexpected native panel manifest targets')
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
        config=home/'.config/doroshell/panel.conf';wrapper=home/'.local/bin/doroshell-native-panel'
        # File-backed output avoids breaking launched applications when a parent exits.
        script='#!/usr/bin/python3\nimport os\nfrom pathlib import Path\np=Path.home()/".local/state/doroshell/native-panel.log"\np.parent.mkdir(parents=True,exist_ok=True)\nfd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)\nos.dup2(fd,1);os.dup2(fd,2);os.close(fd)\nos.execv('+repr(str(binary))+','+repr([str(binary),'--config',str(config)])+')\n'
        quoted=str(wrapper).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
        desktop='[Desktop Entry]\nType=Application\nName=DoroShell Panel\nExec="'+quoted+'"\nOnlyShowIn=LXQt;\nX-LXQt-Module=true\n'
        files={config:content,wrapper:script.encode(),home/'.config/autostart/lxqt-panel.desktop':desktop.encode()}
        record=saved if saved is not None else {}
    edited_config = None
    for path,data in files.items():
        safe(path,home);key=str(path.relative_to(home));current=path.read_bytes() if path.exists() else None
        if saved is not None:
            before = base64.b64decode(record[key]['before'], validate=True) if record[key]['before'] is not None else None
            if current != before and digest(current) != record[key]['after']:
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


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','preview-next-login','enable-next-login','restore-next-login'])
    p.add_argument('--home',type=Path,default=Path.home());p.add_argument('--prepared',type=Path);p.add_argument('--binary',type=Path);p.add_argument('--hide',action='append',default=None)
    p.add_argument('--keep-panel-edits', action='store_true', help='Save changed panel settings privately before restoring the previous panel')
    a=p.parse_args()
    if a.action=='prepare':
        if not a.prepared or not a.binary:p.error('prepare needs --prepared and --binary')
        prepare(a.home,a.prepared,a.binary,a.hide)
    elif a.action in ('preview-next-login', 'enable-next-login'):
        if not a.prepared:p.error('enable-next-login needs --prepared')
        switch(a.home,a.prepared,preview=a.action=='preview-next-login')
    else:switch(a.home,rollback=True,keep_panel_edits=a.keep_panel_edits)
