"""Bounded config-root selection for the Openbox adapters."""
import json
import os
from pathlib import Path
from install import safe as install_safe

SUPPORTED = ('snapping', 'single-desktop')


def targets(home, root, module):
    xml = str((root/'openbox/rc.xml').relative_to(home))
    prefix = 'root-' if root != home/'.config' else ''
    if module == 'single-desktop':
        return [(xml, prefix+'desktop'), (xml, prefix+'firstdesk')]
    return [(name, prefix+kind) for name, kind in (
        ('.local/share/doroshell/snap.py', 'file'),
        ('.local/bin/doroshell-snap', 'file'),
        (str((root/'autostart/doroshell-snap.desktop').relative_to(home)), 'file'),
        (xml, 'snapkeys'))]


def validate_owned(home, root, module, saved):
    from modules import validate_module_record
    validate_module_record(saved)
    expected = targets(home,root,module)
    if root == home/'.config':
        # Legacy single-desktop records may predate firstdesk ownership.
        if ('phase' in saved or any(e['kind'].startswith('root-') for e in saved['edits'])
                or (module=='single-desktop' and (set(saved['backup'])!={expected[0][0]}
                    or not saved['edits'] or any(e['file']!=expected[0][0] for e in saved['edits'])))):
            raise ValueError('Configuration-root metadata conflicts with legacy ownership')
        return
    if (set(saved['backup']) != {name for name,kind in expected}
            or [(e['file'],e['kind']) for e in saved['edits']] != expected
            or (module == 'single-desktop' and any(e['after'] != '1' for e in saved['edits']))):
        raise ValueError('Configuration-root metadata conflicts with the owned paths')
    if saved.get('phase') not in ('pending','complete','restoring'):
        raise ValueError('Invalid custom-root ownership/recovery record')


def safe_path(path, home):
    install_safe(path,home)
    # An in-home alias can still redirect a config path into reserved storage.
    for part in (path,*path.parents):
        if part.is_symlink():
            raise RuntimeError('Refusing symlink component in configuration path: '+str(part))
        if part==home:break


def validate(home, value):
    home = Path(home).absolute()
    if not isinstance(value, (str, Path)):
        raise ValueError('Choose an absolute configuration directory inside the selected home')
    raw = str(value); root = Path(raw)
    if (not root.is_absolute() or str(root) != raw or any(ord(c)<32 or ord(c)==127 for c in raw)
            or '..' in root.parts or root == home or not root.is_relative_to(home)):
        raise ValueError('Configuration root must be a canonical absolute directory inside the selected home')
    safe_path(root,home)
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
    safe_path(root/'openbox/rc.xml',home)
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
    owned_roots = set()
    for module in SUPPORTED:
        if module not in selected:continue
        manifest=home/'.local/state/doroshell'/f'{module}.json';safe_path(manifest,home)
        if manifest.exists():
            saved=json.loads(manifest.read_text())
            if not isinstance(saved,dict):raise ValueError('Invalid module manifest')
            owned=recorded(home,saved['config_root']) if 'config_root' in saved else home/'.config'
            validate_owned(home,owned,module,saved)
            if requested is not None and root!=owned:
                raise ValueError('Configuration root differs from recorded ownership; restore it before choosing another root')
            owned_roots.add(owned)
    if len(owned_roots)>1:
        raise ValueError('Selected modules have different recorded ownership roots; restore them separately')
    if owned_roots:root=owned_roots.pop()
    if root!=home/'.config':
        if not selected or not set(selected).issubset(SUPPORTED):
            raise ValueError('Custom configuration roots support only snapping and single-desktop')
        for key,default in (('XDG_DATA_HOME','.local/share'),('XDG_STATE_HOME','.local/state')):
            if os.environ.get(key) and Path(os.environ[key])!=home/default:
                raise ValueError(key+' must retain the default home layout')
    if requested is not None or set(selected).intersection(SUPPORTED):
        env=os.environ.get('XDG_CONFIG_HOME')
        if env and Path(env)!=root:
            raise ValueError('XDG_CONFIG_HOME differs from the selected/recorded configuration root; no implicit relocation')
    for module in set(selected).intersection(SUPPORTED):
        for name,kind in targets(home,root,module):safe_path(home/name,home)
        # Both custom adapters touch rc.xml; callers take these locks in this order.
        if root!=home/'.config':
            for owner in SUPPORTED:safe_path(home/'.local/state/doroshell'/f'{owner}.lock',home)
    return validate(home,str(root)) if root!=home/'.config' else root
