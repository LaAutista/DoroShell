import contextlib
import io
from pathlib import Path
import tempfile
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
                return build.PANEL_REV if Path(cwd).name == 'source' else build.TOOLS_REV

            with patch.object(build, 'run', side_effect=fake_run), patch.object(build.subprocess, 'check_output', side_effect=revision), contextlib.redirect_stdout(io.StringIO()):
                build.build(work, 1)
            self.assertEqual(applied, list(build.patch_paths()))
            notices = work/'runtime/share/doroshell-panel'
            self.assertEqual({p.name for p in notices.glob('*.patch')}, set(build.PATCHES))
            for source in build.patch_paths():
                self.assertEqual(source.read_bytes(), (notices/source.name).read_bytes())
            self.assertEqual((build.ROOT/'licenses/LGPL-2.1.txt').read_bytes(), (notices/'licenses/LGPL-2.1.txt').read_bytes())
