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
        result=[];inserted=False
        for name in plugins:
            kind=cfg.value(name+'/type',name)
            if kind in ('dockbarx','taskbar'):
                if not inserted:
                    result.extend(['doroshellPins','doroshellTasks']);inserted=True
            else:result.append(name)
        if not inserted:
            result[1:1]=['doroshellPins','doroshellTasks']
        for name,kind in [('doroshellPins','quicklaunch'),('doroshellTasks','taskbar')]:
            # Do not silently overwrite unrelated widgets with our identifiers.
            if cfg.contains(name+'/type') and cfg.value(name+'/type')!=kind:
                raise ValueError('Panel widget name conflict: '+name)
            cfg.setValue(name+'/type',kind)
        cfg.setValue('doroshellPins/alignment','Left')
        cfg.beginWriteArray('doroshellPins/apps',len(launchers))
        for i,path in enumerate(launchers):
            path=Path(path)
            if not path.is_absolute() or path.suffix!='.desktop' or not path.is_file():
                raise ValueError('Unavailable desktop launcher: '+str(path))
            cfg.setArrayIndex(i);cfg.setValue('desktop',str(path))
        cfg.endArray()
        for key,value in {'buttonStyle':'Icon','buttonWidth':48,'groupingEnabled':True,'iconByClass':True,'showOnlyOneDesktopTasks':False}.items():
            cfg.setValue('doroshellTasks/'+key,value)
        notifier=next((n for n in result if cfg.value(n+'/type',n)=='statusnotifier'),None)
        if notifier is None:
            notifier='doroshellNotifier';result.append(notifier);cfg.setValue(notifier+'/type','statusnotifier')
        cfg.setValue(notifier+'/alignment','Right');cfg.setValue(notifier+'/doroshellPopup',True)
        if hidden is not None:cfg.setValue(notifier+'/hideList',hidden)
        cfg.setValue('panel1/plugins',result)
        for key,value in {'doroshellTheme':True,'position':'Bottom','panelSize':40,'iconSize':28,'lineCount':1}.items():cfg.setValue('panel1/'+key,value)
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
    if launchers is None:
        if home.resolve()!=Path.home().resolve():raise ValueError('Alternate-home preparation requires explicit launcher data')
        launchers=launchers_from_dockbarx()
    content=profile(original.decode(),home,launchers,hidden)
    output.mkdir(parents=True,exist_ok=True);output.chmod(0o700)
    atomic(output/'panel.conf',content)
    atomic(output/'plan.json',json.dumps({'binary':str(binary),'binary_hash':digest(binary.read_bytes()),'source_hash':digest(original),'profile_hash':digest(content)},indent=2).encode())
    print('Prepared:',output,'— current panel and autostart unchanged')


def switch(home, prepared=None, rollback=False):
    manifest=home/'.local/state/doroshell/native-panel.json'
    safe(manifest,home)
    if rollback:
        if not manifest.exists():return
        record=json.loads(manifest.read_text())
        files={home/k:base64.b64decode(v['before']) if v['before'] is not None else None for k,v in record.items()}
    else:
        if manifest.exists():raise RuntimeError('Already staged; restore before preparing another switch')
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
        record={}
    for path,data in files.items():
        safe(path,home);key=str(path.relative_to(home));current=path.read_bytes() if path.exists() else None
        if rollback:
            if digest(current)!=record[key]['after']:raise RuntimeError('Personal edit; refusing restore: '+key)
        else:record[key]={'before':base64.b64encode(current).decode() if current is not None else None,'mode':path.stat().st_mode&0o777 if path.exists() else 0o600,'after':digest(data)}
    if not rollback:atomic(manifest,json.dumps(record,indent=2).encode())
    for path,data in files.items():
        if data is None:path.unlink(missing_ok=True)
        else:atomic(path,data,record[str(path.relative_to(home))]['mode'] if rollback else (0o755 if path.name=='doroshell-native-panel' else 0o600))
    if rollback:manifest.unlink()
    print('Saved for your next normal login. No process stopped or started.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','enable-next-login','restore-next-login'])
    p.add_argument('--home',type=Path,default=Path.home());p.add_argument('--prepared',type=Path);p.add_argument('--binary',type=Path);p.add_argument('--hide',action='append',default=None)
    a=p.parse_args()
    if a.action=='prepare':
        if not a.prepared or not a.binary:p.error('prepare needs --prepared and --binary')
        prepare(a.home,a.prepared,a.binary,a.hide)
    elif a.action=='enable-next-login':
        if not a.prepared:p.error('enable-next-login needs --prepared')
        switch(a.home,a.prepared)
    else:switch(a.home,rollback=True)
