"""Actual GIO discovery/notifications in disposable XDG roots; never launch entries."""
import argparse
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def isolated(scenario, installed=False):
    with tempfile.TemporaryDirectory(prefix='doroshell-catalog-fixture-') as directory:
        home = Path(directory); (home/'run').mkdir(mode=0o700)
        roots = [home/'system-a', home/'system-b', home/'.local/share/flatpak/exports/share',
                 home/'system-flatpak/exports/share']
        env = dict(PATH='/usr/bin:/bin', LANG='C.UTF-8', HOME=str(home),
                   QT_QPA_PLATFORM='offscreen', GSETTINGS_BACKEND='memory', PYTHONDONTWRITEBYTECODE='1',
                   XDG_CURRENT_DESKTOP='LXQt', XDG_DATA_HOME=str(home/'.local/share'),
                   XDG_DATA_DIRS=':'.join(map(str, roots[:2] if scenario=='no-exports' else roots)),
                   XDG_CONFIG_HOME=str(home/'config'), XDG_STATE_HOME=str(home/'state'),
                   XDG_CACHE_HOME=str(home/'cache'), XDG_RUNTIME_DIR=str(home/'run'),
                   DBUS_SESSION_BUS_ADDRESS='unix:path='+str(home/'no-session-bus'),
                   DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(home/'no-system-bus'))
        if scenario=='localized': env['LANGUAGE']='fr'
        command = [sys.executable, '-B', str(Path(__file__).resolve()), '--worker', scenario]
        if installed: command.append('--installed')
        result = subprocess.run(command, cwd=home, env=env, capture_output=True, text=True, timeout=25)
        if result.returncode:
            raise AssertionError(result.stdout+result.stderr)
        return json.loads(result.stdout)


def worker(scenario, installed):
    home = Path.home()
    assert home.name.startswith('doroshell-catalog-fixture-') and home.parent==Path(tempfile.gettempdir())
    assert os.environ.get('QT_QPA_PLATFORM')=='offscreen' and not os.environ.get('DISPLAY')
    from gi.repository import GLib
    user = Path(GLib.get_user_data_dir())
    systems = list(map(Path, GLib.get_system_data_dirs()))
    assert user==home/'.local/share' and all(p.is_relative_to(home) for p in systems)
    exports = [home/'.local/share/flatpak/exports/share', home/'system-flatpak/exports/share']
    roots = [user, home/'system-a', home/'system-b', *exports]
    for root in roots: (root/'applications').mkdir(parents=True, exist_ok=True)
    executable = home/'fixture executable'
    executable.write_text('#!/bin/sh\necho forbidden > "$HOME/launch-marker"\nexit 97\n')
    executable.chmod(0o755)
    def entry(root, ident, name, extra=''):
        path=root/'applications'/('org.fixture.'+ident+'.desktop')
        path.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec="'+str(executable)+'"\nCategories=Utility;\n'+extra)
        return path
    def ident(name): return 'org.fixture.'+name+'.desktop'
    entry(roots[1],'Override','System choice'); entry(user,'Override','User choice')
    entry(roots[1],'Priority','First system root'); entry(roots[2],'Priority','Second system root')
    entry(roots[1],'Hidden','Lower visible hidden'); hidden=entry(user,'Hidden','User hidden','Hidden=true\n')
    entry(roots[1],'NoDisplay','Lower visible nodisplay'); nodisplay=entry(user,'NoDisplay','User nodisplay','NoDisplay=true\n')
    entry(roots[1],'DuplicateA','Same name'); entry(roots[2],'DuplicateB','Same name')
    entry(roots[1],'Unicode','Éditeur Straße 日本語','Name[fr]=Éditeur Français 日本語\nKeywords=Édition;日本語;\n')
    entry(roots[1],'OnlyLXQt','LXQt only','OnlyShowIn=LXQt;\n')
    entry(roots[1],'WrongDesktop','Wrong desktop','OnlyShowIn=NeverFixture;\n')
    entry(roots[1],'NotLXQt','Not LXQt','NotShowIn=LXQt;\n')
    entry(roots[1],'MissingExecutable','Missing executable','TryExec='+str(home/'absent')+'\n')
    entry(exports[0],'FlatpakUser','User export','X-Flatpak=org.fixture.FlatpakUser\n')
    entry(exports[1],'FlatpakSystem','System export','X-Flatpak=org.fixture.FlatpakSystem\n')
    sys.path.insert(0,str(ROOT))
    installer=None
    if installed:
        import install as installer
        with contextlib.redirect_stdout(io.StringIO()): installer.install(home,True)
        runtime=home/'.local/share/lxqt-comfort'; toolkit=home/'.local/share/doroshell/toolkit'
        for name in ('start_menu.py','app_search.py','folder_cascade.py','power_capabilities.py',
                     'portrait_crop.py','wallpaper_glass.py'):
            assert (runtime/name).read_bytes()==(ROOT/'menu'/name).read_bytes()
            assert (toolkit/'menu'/name).read_bytes()==(ROOT/'menu'/name).read_bytes()
        assert (runtime/'themes.py').read_bytes()==(toolkit/'themes.py').read_bytes()==(ROOT/'themes.py').read_bytes()
        sys.path.remove(str(ROOT));sys.path[:0]=[str(runtime),str(toolkit)]
    else: sys.path.insert(0,str(ROOT/'menu'))
    import start_menu as menu
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QAbstractEventDispatcher, Qt
    from unittest.mock import patch
    import shiboken6
    class Power(menu.PowerCapabilities):
        def refresh(self): pass
    def forbid(*args,**kwargs): raise AssertionError('No real application/URI/session dispatch')
    checks=[]; queries=[]; signals=[]
    query=menu.applications
    def catalog():
        queries.append(time.monotonic()); apps=query()
        assert all(a.get_id().startswith('org.fixture.') or a.get_id()=='doroshell-settings.desktop' for a in apps)
        return apps
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    state=Path(os.environ['XDG_CONFIG_HOME'])/'lxqt-comfort';state.mkdir(parents=True,exist_ok=True)
    pins=[ident('DuplicateB'),ident('MissingPin')]
    (state/'favorites.json').write_text(json.dumps(pins))
    (state/'recent.json').write_text('{"enabled":false,"items":[]}')
    saved={p:p.read_bytes() for p in state.iterdir()}
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(menu,'PowerCapabilities',Power))
        stack.enter_context(patch.object(menu,'has_compositor',return_value=False))
        stack.enter_context(patch.object(menu,'applications',side_effect=catalog))
        stack.enter_context(patch.object(menu.Gio.AppInfo,'launch_default_for_uri',side_effect=forbid))
        stack.enter_context(patch.object(menu.Gio.DesktopAppInfo,'launch',side_effect=forbid))
        stack.enter_context(patch.object(menu.StartMenu,'session_action',side_effect=forbid))
        w=menu.StartMenu();w.show();w.category.setCurrentText('All applications');app.processEvents()
        if installed:
            for name in ('start_menu','app_search','folder_cascade','power_capabilities',
                         'portrait_crop','wallpaper_glass','themes'):
                assert Path(importlib.import_module(name).__file__).resolve()==runtime/(name+'.py')
        def wait(predicate, seconds=4):
            end=time.monotonic()+seconds
            while not predicate() and time.monotonic()<end: app.processEvents();time.sleep(.01)
            assert predicate(), 'Catalog condition timed out: '+str(sorted(w.by_id))
        def settle(seconds=.4):
            end=time.monotonic()+seconds
            while time.monotonic()<end:app.processEvents();time.sleep(.01)
        def listed():return [w.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(w.list.count())]
        def selected():return w.list.currentItem().data(Qt.ItemDataRole.UserRole) if w.list.currentItem() else None
        try:
            settle()
            assert w.by_id[ident('Override')].get_display_name()=='User choice'
            assert w.by_id[ident('Priority')].get_display_name()=='First system root'
            assert not {ident(n) for n in ('Hidden','NoDisplay','WrongDesktop','NotLXQt','MissingExecutable')} & set(w.by_id)
            assert ident('OnlyLXQt') in w.by_id
            checks.append('user/system precedence and Hidden/NoDisplay/desktop/TryExec visibility')
            assert [a.get_id() for a in w.search_index.search('same name')]==[ident('DuplicateA'),ident('DuplicateB')]
            checks.append('duplicate names retain deterministic distinct desktop IDs')
            term='editeur francais 日本語' if scenario=='localized' else 'EDITEUR STRASSE 日本語'
            assert [a.get_id() for a in w.search_index.search(term)]==[ident('Unicode')]
            assert [a.get_id() for a in w.search_index.search('e\u0301dition 日本語')]==[ident('Unicode')]
            checks.append('real localized/Unicode metadata and normalized cached search')
            expected=scenario!='no-exports'
            assert all((ident(n) in w.by_id)==expected for n in ('FlatpakUser','FlatpakSystem'))
            checks.append('Flatpak-shaped export roots follow supplied XDG_DATA_DIRS')
            if scenario=='changes':
                w.catalog_changed.connect(lambda:signals.append(time.monotonic()))
                w.category.setCurrentText('Utility');w.search.setText('Same name');w.list.setCurrentRow(1)
                w.edit_links_button.setFocus();app.processEvents()
                before=len(queries)
                for i in range(32):entry(roots[1],f'Burst{i}','Burst fixture '+str(i))
                wait(lambda:all(ident(f'Burst{i}') in w.by_id for i in range(32)));settle()
                burst_queries=len(queries)-before
                assert 1<=burst_queries<=3 and signals
                assert w.catalog_timer.isSingleShot() and w.catalog_timer.interval()==150
                assert selected()==ident('DuplicateB') and w.edit_links_button.hasFocus()
                assert w.category.currentText()=='Utility' and w.search.text()=='Same name'
                checks.append('actual GIO burst notification/debounce preserves selected ID and cross-column focus')
                before=len(queries)
                for term in ('same','editeur','日本語','no-match','Same name'):w.search.setText(term)
                assert len(queries)==before
                checks.append('search typing performs no new catalog query')
                suppressed=entry(user,'DuplicateB','Masked duplicate','NoDisplay=true\n')
                wait(lambda:ident('DuplicateB') not in w.by_id)
                assert listed()==[ident('DuplicateA')] and w.edit_links_button.hasFocus()
                suppressed.unlink();wait(lambda:ident('DuplicateB') in w.by_id)
                hidden.unlink();nodisplay.unlink()
                wait(lambda:ident('Hidden') in w.by_id and ident('NoDisplay') in w.by_id)
                assert w.by_id[ident('Hidden')].get_display_name()=='Lower visible hidden'
                (roots[1]/'applications'/ident('Priority')).unlink()
                wait(lambda:w.by_id[ident('Priority')].get_display_name()=='Second system root')
                checks.append('live override removal/masking restores lower-priority entries without pin writes')
                entry(user,'Override','Renamed user choice','Keywords=NewKeyword;\n')
                wait(lambda:w.by_id[ident('Override')].get_display_name()=='Renamed user choice')
                assert [a.get_id() for a in w.search_index.search('newkeyword')]==[ident('Override')]
                (exports[0]/'applications'/ident('FlatpakUser')).unlink()
                wait(lambda:ident('FlatpakUser') not in w.by_id)
                checks.append('metadata updates and export removal rebuild real cached index')
                settle();before=len(queries);w.list.dragging=True
                entry(user,'AfterDrag','Drag deferred fixture');settle(.4)
                assert len(queries)==before and ident('AfterDrag') not in w.by_id
                w.list.dragging=False;wait(lambda:ident('AfterDrag') in w.by_id);settle()
                before=len(queries);settle(.4);assert len(queries)==before and not w.catalog_timer.isActive()
                checks.append('drag defers catalog queries; settled catalog has no polling queries')
                w.search.clear();w.category.setCurrentText('Home');assert listed()==[ident('DuplicateB')]
            assert all(p.read_bytes()==data for p,data in saved.items()) and w.favorites==pins
            assert not (home/'launch-marker').exists();checks.append('pins/missing pin/privacy preferences unchanged and no launch')
        finally:w.close();shiboken6.delete(w)
    if installer:
        manifest=home/'.local/state/lxqt-comfort/menu-install.json';record=manifest.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):installer.install(home,True)
        assert manifest.read_bytes()==record
        with contextlib.redirect_stdout(io.StringIO()):installer.rollback(home)
        assert all(p.read_bytes()==data for p,data in saved.items())
        assert not (home/'.local/share/lxqt-comfort/start_menu.py').exists()
        checks.append('installed helper closure, repeat ownership and removal preserve preferences')
    return {'scenario':scenario,'installed':installed,'checks':checks,'queries':len(queries),'signals':len(signals),
            'dispatcher':QAbstractEventDispatcher.instance().metaObject().className(),
            'burst_queries':burst_queries if scenario=='changes' else None}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--worker',choices=('changes','no-exports','localized'))
    parser.add_argument('--installed',action='store_true')
    args=parser.parse_args()
    if args.worker:print(json.dumps(worker(args.worker,args.installed)))
    elif args.run:print(json.dumps([isolated(s,args.installed) for s in ('changes','no-exports','localized')],indent=2))
    else:parser.error('Use --run for disposable offscreen acceptance')
