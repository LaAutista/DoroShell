# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bounded panel selection and preservation for standard LXQt INI profiles."""
from pathlib import Path
import re
import tempfile
from install import PlanError

PANEL = r'panel[1-9][0-9]*'
NAME = r'[A-Za-z][A-Za-z0-9_-]*'
RESERVED = {'doroshellTasks', 'doroshellStart', 'doroshellNotifier',
            'doroshellClock', 'doroshellShowDesktop', 'doroClipboard'}


def values(value):
    return [value] if isinstance(value, str) else value


def panel_ids(cfg):
    panels = values(cfg.value('panels', ['panel1']))
    if (not isinstance(panels, list) or not panels
            or any(not isinstance(p, str) or not re.fullmatch(PANEL, p) for p in panels)
            or len(set(panels)) != len(panels)
            or set(panels) != {g for g in cfg.childGroups() if re.fullmatch(PANEL, g)}):
        raise PlanError('Ambiguous panel list; use explicit, unique panelN sections and panels= entries.')
    return panels


def select_panel(cfg, requested):
    panels = panel_ids(cfg)
    if requested is None:
        if panels != ['panel1']:
            raise PlanError('Multiple or nondefault panels require prepare --panel PANEL_ID; available: '+', '.join(panels))
        return 'panel1'  # Retain the legacy single-panel adapter's accepted widget names.
    if requested not in panels:
        raise PlanError('Selected panel is unavailable; available: '+', '.join(panels))
    owners = {}
    for panel in panels:
        plugins = values(cfg.value(panel+'/plugins', []))
        if (not isinstance(plugins, list) or not plugins
                or any(not isinstance(p, str) or not re.fullmatch(NAME, p) or p in panels or p == 'General' for p in plugins)
                or len(set(plugins)) != len(plugins)):
            raise PlanError('Missing or ambiguous plugin list for '+panel)
        for plugin in plugins:
            if plugin in owners:
                raise PlanError('Shared panel widget; refusing to alter '+plugin)
            owners[plugin] = panel
            if panel != requested:
                # --config does not inherit implicit plugin types from the stock profile.
                if not isinstance(cfg.value(plugin+'/type'), str) or not cfg.value(plugin+'/type'):
                    raise PlanError('Unselected widget needs an explicit type: '+plugin)
                if plugin in RESERVED:
                    raise PlanError('DoroShell widget belongs to another panel: '+plugin)
    if any(name in cfg.childGroups() and owners.get(name) != requested for name in RESERVED):
        raise PlanError('Unowned DoroShell widget identifier; preserve the existing section for review.')
    return requested


def installed_panel(text):
    """Locate one owned taskbar; retain legacy single-panel adapters without guessing in multi-panel files."""
    prefix, blocks = sections(text)
    declared = re.findall(r'(?m)^\s*panels\s*=([^\r\n]*)', prefix+blocks.get('General', ''))
    if ({name for name in blocks if re.fullmatch(PANEL, name)} == {'panel1'}
            and (not declared or declared == ['panel1'])):
        return 'panel1'  # Keep legacy single-panel previews usable without GUI bindings.
    try:
        from PySide6.QtCore import QSettings
    except ModuleNotFoundError as error:
        if error.name != 'PySide6': raise
        raise PlanError('Install PySide6 before inspecting a multi-panel profile.') from error
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'panel.conf'; path.write_text(text)
        cfg = QSettings(str(path), QSettings.Format.IniFormat)
        panels = panel_ids(cfg)
        if panels == ['panel1']:
            return 'panel1'
        plugins = {p: values(cfg.value(p+'/plugins', [])) for p in panels}
        if any(not isinstance(value, list) for value in plugins.values()):
            raise PlanError('Malformed panel plugin list; preserve this profile for review.')
        owners = [p for p in panels if 'doroshellTasks' in plugins[p]]
        if len(owners) != 1 or cfg.value('doroshellTasks/type') != 'taskbar':
            raise PlanError('Cannot identify one DoroShell taskbar panel; preserve this profile for review.')
        return select_panel(cfg, owners[0])


def sections(text):
    matches = list(re.finditer(r'(?m)^\[([^\]\r\n]+)\][ \t]*\r?$', text))
    names = [m[1] for m in matches]
    if (len(re.findall(r'(?m)^[ \t]*\[', text)) != len(matches)
            or len(set(names)) != len(names) or any(not re.fullmatch(NAME, name) for name in names)):
        raise PlanError('Duplicate or encoded INI sections need manual review before panel selection.')
    return text[:matches[0].start()] if matches else text, {
        match[1]: text[match.start():matches[i+1].start() if i+1 < len(matches) else len(text)]
        for i, match in enumerate(matches)}


def preserve_sections(original, serialized, changed):
    """Replace only changed sections; leave all unrelated source spans byte-for-byte."""
    from PySide6.QtCore import QSettings
    prefix, before = sections(original)
    _, after = sections(serialized)
    result = prefix+''.join(after.get(name, '') if name in changed else block for name, block in before.items())
    additions = ''.join(block for name, block in after.items() if name in changed and name not in before)
    result += ('\n' if additions and result and not result.endswith('\n') else '')+additions
    # Compare fresh parses: QSettings' in-memory QVariant types differ from an INI reload.
    with tempfile.TemporaryDirectory() as directory:
        snapshots = []
        for name, text in [('expected', serialized), ('preserved', result)]:
            path = Path(directory)/name; path.write_text(text)
            cfg = QSettings(str(path), QSettings.Format.IniFormat)
            snapshots.append({key: cfg.value(key) for key in cfg.allKeys()})
            if cfg.status() != QSettings.Status.NoError:
                raise PlanError('Malformed panel INI; original profile preserved.')
        if snapshots[0] != snapshots[1]:
            raise PlanError('Ambiguous INI serialization; original profile preserved.')
    return result
