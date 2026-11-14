"""Installer simulation in disposable homes; no OS packages, personal X11 or login."""
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import compatibility
import deploy
import install
import modules
from panel import profile


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.output = contextlib.redirect_stdout(io.StringIO()); self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def fixture(self):
        panel = self.home/'.config/lxqt/panel.conf'; panel.parent.mkdir(parents=True)
        panel.write_text('panels=panel1\n[panel1]\nplugins=fancymenu,taskbar,statusnotifier,worldclock\n')
        rc = self.home/'.config/openbox/rc.xml'; rc.parent.mkdir(parents=True)
        rc.write_text('<openbox_config><theme><name>Original</name></theme><keyboard></keyboard></openbox_config>')
        shortcuts = panel.with_name('globalkeyshortcuts.conf')
        shortcuts.write_text('[Print.1]\nExec=screengrab\nEnabled=true\nComment=Original\n')

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.read_bytes(),p.stat().st_mode & 0o777)
                for p in self.home.rglob('*') if p.is_file() and 'deployments' not in p.parts}

    def test_capability_not_distro_name_guessing_and_custom_layouts(self):
        self.fixture()
        env=dict(XDG_CURRENT_DESKTOP='LXQt',XDG_SESSION_TYPE='x11')
        for distro in ('arch','cachyos','endeavouros','other-derivative'):
            with patch.object(compatibility.shutil,'which',return_value='/usr/bin/pacman'):
                report=compatibility.inspect(self.home,deploy.CORE,env,dict(ID=distro,ID_LIKE='arch'))
                self.assertEqual(report['issues'],[])
        env['XDG_SESSION_TYPE']='wayland'
        self.assertTrue(compatibility.inspect(self.home,[],env,dict(ID='arch'))['issues'])
        env['XDG_SESSION_TYPE']='x11';env['XDG_CONFIG_HOME']='/alternate'
        self.assertTrue(compatibility.inspect(self.home,[],env,dict(ID='arch'))['issues'])
        (self.home/'.config/lxqt/panel.conf').write_text('panels=panel1,panel2\n')
        self.assertTrue(compatibility.inspect(self.home,['native-panel'],{},dict(ID='debian'))['issues'])

    def test_stock_start_icon_upgrades_to_doro_but_keeps_personal_pictures(self):
        manifest = self.home/'.local/state/lxqt-comfort/menu-install.json'
        entry = self.home/'.local/share/applications/lxqt-comfort.desktop'
        art = self.home/'.local/share/lxqt-comfort'
        self.assertTrue(deploy.stock_start_icon(self.home, manifest))  # first install
        manifest.parent.mkdir(parents=True); manifest.write_text('{}')
        entry.parent.mkdir(parents=True)
        entry.write_text('[Desktop Entry]\nName=DoroShell Start\nIcon='+str(art/'start.svg')+'\n')
        self.assertTrue(deploy.stock_start_icon(self.home, manifest))  # earlier install, plain icon
        entry.write_text('[Desktop Entry]\nName=DoroShell Start\nIcon=/home/someone/Pictures/mine.png\n')
        self.assertFalse(deploy.stock_start_icon(self.home, manifest))  # personal Icon= path
        entry.write_text('[Desktop Entry]\nName=DoroShell Start\nIcon='+str(art/'start.svg')+'\n')
        art.mkdir(parents=True); (art/'start-icon.png').write_bytes(b'png')
        self.assertFalse(deploy.stock_start_icon(self.home, manifest))  # personal picture chosen
        (art/'start-icon.png').unlink(); entry.unlink()
        self.assertFalse(deploy.stock_start_icon(self.home, manifest))  # manifest but no launcher: leave it

    def test_default_single_panel_without_panels_key_is_supported(self):
        # LXQt writes no `panels=` line for its default single-panel layout.
        self.fixture()
        panel = self.home/'.config/lxqt/panel.conf'
        panel.write_text('[General]\n__userfile__=true\n\n[panel1]\nplugins=fancymenu, quicklaunch, taskbar\n')
        env = dict(XDG_CURRENT_DESKTOP='LXQt', XDG_SESSION_TYPE='x11')
        with patch.object(compatibility.shutil, 'which', return_value='/usr/bin/pacman'):
            self.assertEqual(compatibility.inspect(self.home, deploy.CORE, env, dict(ID='cachyos', ID_LIKE='arch'))['issues'], [])
            panel.write_text('[General]\npanels = panel1, panel2\n[panel1]\n')
            self.assertTrue(compatibility.inspect(self.home, ['native-panel'], env, dict(ID='arch'))['issues'])
            panel.write_text('[General]\n__userfile__=true\n')
            self.assertTrue(compatibility.inspect(self.home, ['native-panel'], env, dict(ID='arch'))['issues'])

    def test_optional_dependencies_and_scoped_removal(self):
        self.assertEqual(deploy.select_modules(['clipboard']),['menu','native-panel','clipboard'])
        self.assertEqual(deploy.select_modules(['clipboard'],expand=False),['clipboard'])
        self.assertEqual(deploy.select_modules(['display']),['wallpaper','display'])
        self.assertIn('breeze-cursors',deploy.packages_for(['cursor']))
        self.assertNotIn('qt6-multimedia',deploy.packages_for(['menu']))
        with self.assertRaises(ValueError): deploy.select_modules(['typo'])

    def test_legacy_optional_modules_are_detected_and_retained_in_registry(self):
        for name in ('clipboard','wallpaper'):
            path=deploy.manifest_for(self.home,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}')
        wrapper=self.home/'.local/bin/doroshell-wallpaper-desktop';wrapper.parent.mkdir(parents=True)
        wrapper.write_text('fixture doroshell-display-backend.py')
        self.assertEqual(deploy.installed_modules(self.home),['clipboard','wallpaper','display'])
        with patch.object(install,'targets',return_value={self.home/'a':(b'new',0o644)}):deploy.deploy(self.home,['menu'],{})
        registry=json.loads((self.home/'.local/state/doroshell/deployment.json').read_text())
        self.assertEqual(registry['modules'],['menu','clipboard','wallpaper','display'])

    def test_plan_missing_capabilities_needs_no_bindings_or_writes(self):
        env={'HOME':str(self.home),'PATH':'/empty','QT_QPA_PLATFORM':'offscreen'}
        result=subprocess.run([sys.executable,'-S',str(deploy.ROOT/'deploy.py'),'--modules','menu'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Plan only',result.stdout)
        self.assertEqual(self.snapshot(),{})

    def test_missing_packages_refused_before_build_or_home_writes(self):
        with patch.object(compatibility,'inspect',return_value={'issues':[]}), patch.object(compatibility,'package_versions',return_value={'python':None}), patch('source_release.check'), patch.object(deploy.os,'geteuid',return_value=1000), patch.object(deploy,'build_native') as build:
            with self.assertRaisesRegex(ValueError,'Missing packages'):
                deploy.main(['--home',str(self.home),'--modules','menu','--apply','--no-packages'])
            build.assert_not_called(); self.assertEqual(self.snapshot(),{})

    def test_missing_package_offer_is_full_update_and_no_unattended_approval(self):
        with patch.object(compatibility,'inspect',return_value={'issues':[]}), patch.object(compatibility,'package_versions',side_effect=[{'python':None},{'python':'fixture'}]), patch('source_release.check'), patch.object(deploy.os,'geteuid',return_value=1000), patch.object(deploy,'run') as run, patch.object(deploy,'build_native',return_value={}), patch.object(deploy,'deploy') as apply:
            deploy.main(['--home',str(self.home),'--modules','menu','--apply'])
            command=run.call_args.args[0]
            self.assertEqual(command[:4],['sudo','pacman','-Syu','--needed'])
            self.assertNotIn('--noconfirm',command);apply.assert_called_once()

    def test_build_reuse_checks_complete_payload_and_modes(self):
        def fake_build(argv):
            work=Path(argv[argv.index('--work')+1]);binary=work/'runtime/bin/lxqt-panel'
            binary.parent.mkdir(parents=True);binary.write_bytes(b'fixture native');binary.chmod(0o755)
        with patch.object(deploy,'run',side_effect=fake_build) as build:
            binaries=deploy.build_native(self.home,['native-panel'],{'qt6-base':'fixture'})
            self.assertEqual(binaries,deploy.build_native(self.home,['native-panel'],{'qt6-base':'fixture'}))
            self.assertEqual(build.call_count,1)
            binaries['native-panel'].chmod(0o644)
            with self.assertRaisesRegex(RuntimeError,'Changed native'):deploy.build_native(self.home,['native-panel'],{'qt6-base':'fixture'})

    def test_real_menu_repeat_upgrade_undo_and_first_baseline(self):
        self.fixture()
        original=self.home/'.local/share/lxqt-comfort/start.svg';original.parent.mkdir(parents=True)
        original.write_bytes(b'prior');original.chmod(0o640)
        deploy.deploy(self.home,['menu','maintenance'],{})
        installed=self.snapshot(); baseline=(self.home/'.local/state/lxqt-comfort/menu-install.json').read_bytes()
        job=deploy.deploy(self.home,['menu','maintenance'],{})
        self.assertEqual((self.home/'.local/state/lxqt-comfort/menu-install.json').read_bytes(),baseline)
        deploy.undo(self.home,job)
        self.assertEqual(self.snapshot(),installed)
        deploy.deploy(self.home,['menu','maintenance'],{},remove=True)
        self.assertEqual(original.read_bytes(),b'prior');self.assertEqual(original.stat().st_mode&0o777,0o640)
        self.assertFalse((self.home/'.local/bin/lxqt-comfort-menu').exists())

    def test_failed_module_recover_keeps_baseline_then_exact_undo(self):
        targets={self.home/'a':(b'new',0o644),self.home/'b':(b'new',0o644)}
        for path in targets: path.write_bytes(b'old');path.chmod(0o640)
        before=self.snapshot(); real=install.atomic
        def fail(path,data,mode=0o600):
            if path==self.home/'b': raise OSError('injected')
            real(path,data,mode)
        with patch.object(install,'targets',return_value=targets),patch.object(install,'atomic',side_effect=fail):
            with self.assertRaises(OSError):deploy.deploy(self.home,['menu'],{})
        with patch.object(install,'targets',return_value=targets):
            with self.assertRaisesRegex(RuntimeError,'Interrupted'):deploy.deploy(self.home,['menu'],{})
            job=deploy.deploy(self.home,['menu'],{},recover=True)
        deploy.undo(self.home,job)
        self.assertEqual(self.snapshot(),before)

    def test_undo_content_mode_and_symlink_conflicts_leave_everything(self):
        path=self.home/'a';path.write_bytes(b'old')
        with patch.object(install,'targets',return_value={path:(b'new',0o644)}):
            job=deploy.deploy(self.home,['menu'],{})
        for content,mode in ((b'personal',0o644),(b'new',0o600)):
            path.write_bytes(content);path.chmod(mode);before=self.snapshot()
            with self.assertRaises(RuntimeError):deploy.undo(self.home,job)
            self.assertEqual(before,self.snapshot())
        path.unlink();path.symlink_to(self.home/'unrelated')
        with self.assertRaises((ValueError,RuntimeError)):deploy.undo(self.home,job)

    def test_malformed_undo_mode_refused_before_writes(self):
        with patch.object(install,'targets',return_value={self.home/'a':(b'new',0o644)}):job=deploy.deploy(self.home,['menu'],{})
        path=self.home/'.local/state/doroshell/deployments'/job/'journal.json'
        journal=json.loads(path.read_text());journal['before']['a']={'data':base64.b64encode(b'prior').decode(),'mode':-1}
        path.write_text(json.dumps(journal));before=self.snapshot()
        with self.assertRaises(ValueError):deploy.undo(self.home,job)
        self.assertEqual(before,self.snapshot())

    def test_final_pointer_interruption_can_finalize_then_undo(self):
        real=deploy.atomic
        def fail(path,data,mode=0o600):
            if path.name=='deployment.json' and json.loads(data)['status']=='complete':raise OSError('finalization interrupted')
            real(path,data,mode)
        with patch.object(install,'targets',return_value={self.home/'a':(b'new',0o644)}):
            with patch.object(deploy,'atomic',side_effect=fail),self.assertRaises(OSError):deploy.deploy(self.home,['menu'],{})
            job=deploy.deploy(self.home,['menu'],{},recover=True)
        deploy.undo(self.home,job);self.assertFalse((self.home/'a').exists())

    def test_core_helpers_stage_together_and_restore_configuration(self):
        self.fixture();before=self.snapshot()
        selected=deploy.select_modules(['menu','native-panel','theme','snapping','screenshots','clipboard','maintenance'])
        # Executable is never launched: native profile setup only records its bytes/path.
        binaries={'native-panel':Path('/usr/bin/true')}
        deploy.deploy(self.home,selected,binaries)
        cfg=self.home/'.config/doroshell/panel.conf'
        self.assertIn('doroClipboard',cfg.read_text())
        self.assertTrue((self.home/'.config/autostart/doroshell-snap.desktop').is_file())
        job=deploy.deploy(self.home,selected,binaries)
        deploy.undo(self.home,job)
        deploy.deploy(self.home,selected,{},remove=True)
        for name,value in before.items():self.assertEqual(self.snapshot()[name],value)
        self.assertFalse(cfg.exists())


class PanelUpgradeTests(unittest.TestCase):
    def test_upgrade_retains_edits_and_original_manifest_then_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);panel=home/'.config/lxqt/panel.conf';panel.parent.mkdir(parents=True)
            panel.write_text('panels=panel1\n[panel1]\nplugins=taskbar,statusnotifier\n')
            prepared=home/'prepared';profile.prepare(home,prepared,Path('/usr/bin/true'));profile.switch(home,prepared)
            manifest=home/'.local/state/doroshell/native-panel.json'
            original=json.loads(manifest.read_text())
            config=home/'.config/doroshell/panel.conf';config.write_text(config.read_text()+'\n# personal edit\n');edited=config.read_bytes()
            profile.upgrade(home,Path('/usr/bin/false'))
            self.assertEqual(config.read_bytes(),edited)
            current=json.loads(manifest.read_text())
            self.assertEqual([x['before'] for x in original.values()],[x['before'] for x in current.values()])
            wrapper=home/'.local/bin/doroshell-native-panel';saved=wrapper.read_bytes();wrapper.chmod(0o600)
            with self.assertRaises(RuntimeError):profile.upgrade(home,Path('/usr/bin/true'))
            self.assertEqual(wrapper.read_bytes(),saved);wrapper.chmod(0o755)
            profile.switch(home,rollback=True,keep_panel_edits=True)
            self.assertFalse(wrapper.exists())

    def test_interrupted_upgrade_can_retry_without_changing_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);panel=home/'.config/lxqt/panel.conf';panel.parent.mkdir(parents=True)
            panel.write_text('panels=panel1\n[panel1]\nplugins=taskbar,statusnotifier\n')
            profile.prepare(home,home/'prepared',Path('/usr/bin/true'));profile.switch(home,home/'prepared')
            real=profile.atomic
            def fail(path,*args):
                if path.name=='doroshell-native-panel':raise OSError('injected')
                real(path,*args)
            with patch.object(profile,'atomic',side_effect=fail),self.assertRaises(OSError):profile.upgrade(home,Path('/usr/bin/false'))
            profile.upgrade(home,Path('/usr/bin/false'))
            self.assertIn('/usr/bin/false',(home/'.local/bin/doroshell-native-panel').read_text())
            profile.switch(home,rollback=True)
