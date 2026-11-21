import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
from panel import build


class PanelBuildTests(unittest.TestCase):
    def test_all_patches_declared_in_numeric_order(self):
        paths = build.patch_paths()
        self.assertEqual([int(p.name.split('-')[0]) for p in paths], list(range(1, len(paths)+1)))
        self.assertEqual(set(paths), set((build.ROOT/'patches').glob('*.patch')))

    def test_inventory_mismatch_fails_before_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'patches').mkdir()
            with patch.object(build, 'ROOT', root), patch.object(build, 'PATCHES', ('0001-test.patch',)), patch.object(build, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'missing='):
                    build.build(root/'work', 1)
                (root/'patches/0001-test.patch').write_text('fixture')
                (root/'patches/0002-forgotten.patch').write_text('fixture')
                with self.assertRaisesRegex(RuntimeError, 'unlisted='):
                    build.build(root/'work', 1)
                run.assert_not_called()

    def test_applied_patches_are_all_shipped_with_licenses(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)/'work'
            applied = []

            def fake_run(args, **kwargs):
                args = list(map(str, args))
                if args[:2] == ['git', 'clone']:
                    Path(args[-1]).mkdir()
                if args[:2] == ['git', 'apply'] and '--check' not in args:
                    applied.append(Path(args[-1]))
                if args[:2] == ['cmake', '--install'] and 'env' in kwargs:
                    target = Path(kwargs['env']['DESTDIR'])/str(work/'runtime').lstrip('/')/'bin'
                    target.mkdir(parents=True)
                    (target/'lxqt-panel').write_text('fake build')

            def revision(args, cwd, **kwargs):
                return build.PANEL_REV if Path(cwd).name == 'source' else build.TOOLS['2.4'][1]

            selected = dict(lxqt_version='2.4.0', lxqt_prefix='/fixture', lxqt_dir='/fixture/share/cmake/lxqt',
                            tools_tag='2.4.0', tools_revision=build.TOOLS['2.4'][1], metadata_sha256={})
            with patch.object(build, 'dependencies', return_value=selected), patch.object(build, 'run', side_effect=fake_run), patch.object(build.subprocess, 'check_output', side_effect=revision), contextlib.redirect_stdout(io.StringIO()):
                build.build(work, 1)
            self.assertEqual(applied, list(build.patch_paths()))
            notices = work/'runtime/share/doroshell-panel'
            self.assertEqual({p.name for p in notices.glob('*.patch')}, set(build.PATCHES))
            for source in build.patch_paths():
                self.assertEqual(source.read_bytes(), (notices/source.name).read_bytes())
            self.assertEqual((build.ROOT/'licenses/LGPL-2.1.txt').read_bytes(), (notices/'licenses/LGPL-2.1.txt').read_bytes())
            self.assertEqual(json.loads((notices/'build-provenance.json').read_text())['status'], 'complete')


class PanelDependenciesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.tmp)
        self.prefix = self.root/'prepared prefix'
        self.directory = self.prefix/'share/cmake/lxqt'
        self.directory.mkdir(parents=True)
        self.config = self.directory/'lxqt-config.cmake'
        self.version_file = self.directory/'lxqt-config-version.cmake'
        self.write_version('2.5.0')
        self.enterContext(patch.dict(os.environ, {'CMAKE_PREFIX_PATH': ''}))
        self.enterContext(patch.object(build.shutil, 'which', return_value='/fixture/tool'))
        self.query = self.enterContext(patch.object(build.subprocess, 'check_output', side_effect=self.pkg_query))
        self.pkg = self.enterContext(patch.object(build.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)))
        self.commands = []
        self.run = self.enterContext(patch.object(build, 'run', side_effect=self.fake_run))
        self.enterContext(patch('native_rebuild.snapshot'))  # Recipe copying is covered in test_native_rebuild.

    def write_version(self, version, tools=None):
        tools = tools or '.'.join(version.split('.')[:2])+'.0'
        self.config.write_text(f'set(LXQT_VERSION "{version}")\nfind_dependency(lxqt2-build-tools {tools})\n'
                               'find_dependency(Qt6Widgets 6.10.0)\nfind_dependency(Qt6DBus 6.10.0)\nfind_dependency(Qt6Xdg 4.5.0)\n')
        self.version_file.write_text(f'set(PACKAGE_VERSION "{version}")\n'
                                    'if(NOT CMAKE_SIZEOF_VOID_P STREQUAL "8")\n'
                                    '  set(PACKAGE_VERSION "${PACKAGE_VERSION} (${installedBits}bit)")\nendif()\n')
        self.version = version

    def pkg_query(self, args, **kwargs):
        if args[0] == 'git':
            return build.PANEL_REV if Path(kwargs['cwd']).name == 'source' else build.TOOLS['.'.join(self.version.split('.')[:2])][1]
        return str(self.prefix) if '--variable=prefix' in args else self.version

    def fake_run(self, args, **kwargs):
        args = list(map(str, args)); self.commands.append(args)
        if args[:2] == ['git', 'clone']:
            Path(args[-1]).mkdir()
        if args[:2] == ['cmake', '--install'] and 'env' in kwargs:
            work = Path(args[-1]).parent
            target = Path(kwargs['env']['DESTDIR'])/str(work/'runtime').lstrip('/')/'bin'
            target.mkdir(parents=True)
            (target/'lxqt-panel').write_text('fixture executable, not run')

    def refused_before_writes(self, text):
        work = self.root/'work'
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(build.BuildError, text):
            build.build(work, 1)
        self.run.assert_not_called()
        self.assertFalse(work.exists())
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_known_families_select_exact_pins_and_record_installed_provenance(self):
        for version in ('2.4.0', '2.4.2', '2.5.0', '2.5.1'):
            with self.subTest(version=version), contextlib.redirect_stdout(io.StringIO()):
                self.write_version(version)
                work = self.root/version
                build.build(work, 2)
                record = json.loads((work/'build-provenance.json').read_text())
                tag, revision = build.TOOLS['.'.join(version.split('.')[:2])]
                self.assertEqual(record['tools_revision'], revision)
                self.assertEqual(record['lxqt_version'], version)
                self.assertIn(['git','clone','--depth','1','--branch',tag,'https://github.com/lxqt/lxqt-build-tools.git',str(work/'tools')], self.commands)
                configure = next(c for c in self.commands if '-S' in c and str(work/'source') in c)
                self.assertIn('-Dlxqt_DIR='+str(self.directory), configure)
                self.assertIn('-Dlxqt2-build-tools_DIR='+str(work/'deps/share/cmake/lxqt2-build-tools'), configure)
                self.assertEqual((work/'build-provenance.json').read_bytes(), (work/'runtime/share/doroshell-panel/build-provenance.json').read_bytes())
                self.assertEqual(record['status'], 'complete')

    def test_explicit_prefix_ignores_unrelated_pkgconfig_library(self):
        self.query.side_effect = AssertionError('No liblxqt pkg-config query expected')
        self.assertEqual(build.dependencies(self.prefix)['lxqt_version'], '2.5.0')

    def test_environment_prefix_precedes_pkgconfig(self):
        with patch.dict(os.environ, {'CMAKE_PREFIX_PATH': str(self.root/'unrelated')+os.pathsep+str(self.prefix)}):
            self.query.side_effect = AssertionError('No liblxqt pkg-config query expected')
            self.assertEqual(build.dependencies()['lxqt_dir'], str(self.directory))

    def test_missing_tools_fail_before_queries_or_writes(self):
        with patch.object(build.shutil, 'which', return_value=None):
            self.refused_before_writes('Missing build tools.*pacman')
        self.query.assert_not_called()

    def test_missing_library_is_actionable(self):
        self.query.side_effect = subprocess.CalledProcessError(1, ['pkg-config'])
        self.refused_before_writes('liblxqt development metadata is missing')

    def test_missing_cmake_config_is_actionable(self):
        self.config.unlink()
        self.refused_before_writes('No liblxqt CMake')

    def test_unknown_or_old_versions_refused(self):
        for version in ('2.3.0', '2.6.0', '3.0.0'):
            with self.subTest(version=version):
                self.write_version(version)
                self.refused_before_writes('Unsupported liblxqt')

    def test_new_tools_requirement_needs_reviewed_pin(self):
        self.write_version('2.5.1', '2.5.1')
        self.refused_before_writes('new source pin must be reviewed')

    def test_conflicting_metadata_is_refused(self):
        self.version_file.write_text('set(PACKAGE_VERSION "2.4.0")\n')
        self.refused_before_writes('Conflicting liblxqt')

    def test_pkgconfig_version_mismatch_is_refused(self):
        self.version = '2.4.0'
        self.refused_before_writes('Conflicting liblxqt')

    def test_malformed_and_duplicate_versions_are_refused(self):
        original = self.config.read_text()
        for text in (original.replace('"2.5.0"', '"${UNKNOWN}"'), original+'set(LXQT_VERSION "2.4.0")\n',
                     original.replace('2.5.0)', 'invalid)'), original.replace('"2.5.0"', '"2.5.0')):
            with self.subTest(text=text):
                self.config.write_text(text)
                self.refused_before_writes('Unsupported liblxqt metadata')

    def test_oversized_metadata_is_refused(self):
        self.config.write_bytes(b'x'*65537)
        self.refused_before_writes('Oversized')

    def test_ambiguous_prefix_is_refused(self):
        duplicate = self.prefix/'lib/cmake/lxqt'
        duplicate.mkdir(parents=True)
        (duplicate/self.config.name).write_text(self.config.read_text())
        self.refused_before_writes('Ambiguous')

    def test_missing_qt_or_gio_fails_before_acquisition(self):
        self.pkg.return_value = subprocess.CompletedProcess([], 1)
        self.refused_before_writes('Missing development dependencies.*Qt6Widgets.*gio-unix')

    def test_query_timeout_reports_without_traceback_or_writes(self):
        self.query.side_effect = subprocess.TimeoutExpired(['pkg-config'], 10)
        with contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(build.main(['--work', str(self.root/'work')]), 1)
        self.assertIn('timed out', output.getvalue())
        self.assertNotIn('Traceback', output.getvalue())
        self.assertFalse((self.root/'work').exists())

    def test_check_only_is_read_only_even_with_work_option(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(build.main(['--check-dependencies', '--work', str(self.root/'work')]), 0)
        self.assertIn(build.TOOLS['2.5'][1], output.getvalue())
        self.run.assert_not_called()
        self.assertFalse((self.root/'work').exists())

    def test_nonempty_work_is_preserved_before_dependency_lookup(self):
        work = self.root/'work'; work.mkdir(); (work/'keep').write_text('original')
        with patch.object(build, 'dependencies', side_effect=AssertionError('Must not query')):
            with self.assertRaisesRegex(build.BuildError, 'empty'):
                build.build(work, 1)
        self.assertEqual((work/'keep').read_text(), 'original')

    def test_changed_tag_retains_failed_evidence_and_stops_cmake(self):
        self.query.side_effect = lambda args, **kw: 'wrong revision' if args[0]=='git' else self.pkg_query(args, **kw)
        work = self.root/'work'
        with self.assertRaisesRegex(build.BuildError, 'tag changed'):
            build.build(work, 1)
        self.assertEqual(json.loads((work/'build-provenance.json').read_text())['status'], 'failed-or-interrupted')
        self.assertFalse(any(c[0]=='cmake' for c in self.commands))

    def test_dependency_change_during_acquisition_refuses_panel_configure(self):
        def change(args, **kwargs):
            self.fake_run(args, **kwargs)
            if list(map(str,args))[:2] == ['cmake','--install']:
                self.config.write_text(self.config.read_text()+'# changed\n')
        self.run.side_effect = change
        with self.assertRaisesRegex(build.BuildError, 'metadata changed'):
            build.build(self.root/'work', 1)
        self.assertFalse(any('-S' in c and str(self.root/'work/source') in c for c in self.commands))

    def test_build_failure_and_cancellation_leave_failed_record_no_success(self):
        for error in (subprocess.CalledProcessError(1, ['cmake']), KeyboardInterrupt()):
            with self.subTest(error=error), tempfile.TemporaryDirectory(dir=self.root) as temp:
                self.run.side_effect = error
                with self.assertRaises(type(error)):
                    build.build(Path(temp)/'work', 1)
                self.assertEqual(json.loads((Path(temp)/'work/build-provenance.json').read_text())['status'], 'failed-or-interrupted')

    def test_programming_errors_are_not_masked(self):
        with patch.object(build, 'dependencies', side_effect=TypeError('unexpected bug')):
            with self.assertRaisesRegex(TypeError, 'unexpected bug'):
                build.main(['--check-dependencies'])

    def test_unsafe_cmake_list_path_refused(self):
        with self.assertRaisesRegex(build.BuildError, 'absolute prefix/work path'):
            build.dependencies(self.root/'ambiguous;prefix')

    def test_prefix_alias_cannot_introduce_cmake_separator_or_control(self):
        for name in ('bad;prefix', 'bad\tprefix'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=self.root) as tmp:
                root=Path(tmp); target=root/name; target.mkdir()
                alias=root/'alias'; alias.symlink_to(target, target_is_directory=True)
                for prefix in (target, alias):
                    with self.assertRaisesRegex(build.BuildError, 'absolute prefix/work path'):
                        build.build(root/'work', 1, prefix)
                self.assertFalse((root/'work').exists())
                self.assertEqual(list(target.iterdir()), [])
        self.query.assert_not_called()
        self.pkg.assert_not_called()
        self.run.assert_not_called()

    def test_work_alias_cannot_introduce_cmake_separator_or_control(self):
        for name in ('bad;prefix', 'bad\tprefix'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=self.root) as tmp:
                root=Path(tmp); target=root/name; target.mkdir()
                alias=root/'alias'; alias.symlink_to(target, target_is_directory=True)
                with patch.object(build, 'dependencies') as dependencies:
                    for work in (target/'work', alias/'work'):
                        with self.assertRaisesRegex(build.BuildError, 'absolute prefix/work path'):
                            build.build(work, 1)
                    dependencies.assert_not_called()
                self.assertEqual(list(target.iterdir()), [])
        self.query.assert_not_called()
        self.pkg.assert_not_called()
        self.run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
