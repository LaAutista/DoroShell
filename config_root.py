"""Bounded config-root selection for the config-only Openbox adapter."""
import json
import os
from pathlib import Path
from install import safe


def validate(home, value):
    home = Path(home).absolute()
    if not isinstance(value, (str, Path)):
        raise ValueError('Choose an absolute configuration directory inside the selected home')
    raw = str(value); root = Path(raw)
    if (not root.is_absolute() or str(root) != raw or any(ord(c)<32 or ord(c)==127 for c in raw)
            or '..' in root.parts or root == home or not root.is_relative_to(home)):
        raise ValueError('Configuration root must be a canonical absolute directory inside the selected home')
    safe(root,home)
    if root.exists() and not root.is_dir():
        raise ValueError('Configuration root must be a directory')
    if root != home/'.config':
        reserved=[home/name for name in ('.config','.local','.cache','.icons')]
        for key in ('XDG_CACHE_HOME','XDG_RUNTIME_DIR'):
            value=os.environ.get(key,'')
            if Path(value).is_absolute():reserved.append(Path(os.path.normpath(value)))
        for other in reserved:
            if root.is_relative_to(other) or other.is_relative_to(root):
                raise ValueError('Configuration root overlaps a default config/data/state/cache/runtime path')
    return root


def recorded(home, value):
    if not isinstance(value,str) or not value or Path(value).is_absolute() or str(Path(value))!=value:
        raise ValueError('Invalid recorded configuration root')
    root=validate(home,str(home/value))
    if root==home/'.config':raise ValueError('Custom root record cannot describe the legacy default')
    return root


def choose(home, selected, requested=None):
    """No environment-only relocation; reuse only an explicitly owned root."""
    home=Path(home).absolute()
    root=validate(home,requested) if requested is not None else home/'.config'
    if 'single-desktop' in selected:
        manifest=home/'.local/state/doroshell/single-desktop.json';safe(manifest,home)
        if manifest.exists():
            saved=json.loads(manifest.read_text())
            if not isinstance(saved,dict):raise ValueError('Invalid module manifest')
            owned=recorded(home,saved['config_root']) if 'config_root' in saved else home/'.config'
            from modules import validate_module_record
            validate_module_record(saved)
            target=str((owned/'openbox/rc.xml').relative_to(home))
            if (set(saved['backup'])!={target} or not saved['edits']
                    or any(e['file']!=target for e in saved['edits'])
                    or ('config_root' not in saved and 'phase' in saved)):
                raise ValueError('Configuration-root metadata conflicts with the owned paths')
            if requested is not None and root!=owned:
                raise ValueError('Configuration root differs from recorded ownership; restore it before choosing another root')
            root=owned
    if root!=home/'.config':
        if list(selected)!=['single-desktop']:
            raise ValueError('Custom configuration roots support only the single-desktop module')
        for key,default in (('XDG_DATA_HOME','.local/share'),('XDG_STATE_HOME','.local/state')):
            if os.environ.get(key) and Path(os.environ[key])!=home/default:
                raise ValueError(key+' must retain the default home layout')
    if requested is not None or 'single-desktop' in selected:
        env=os.environ.get('XDG_CONFIG_HOME')
        if env and Path(env)!=root:
            raise ValueError('XDG_CONFIG_HOME differs from the selected/recorded configuration root; no implicit relocation')
    return validate(home,str(root)) if root!=home/'.config' else root
