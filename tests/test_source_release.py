from pathlib import Path
import tempfile
import unittest
import source_release as release


class SourceReleaseTests(unittest.TestCase):
    def fixture(self, root):
        for name in (release.MANIFEST, release.SCAN):
            (root/name).write_text('{}')
        (root/release.SUMS).write_text('')
        (root/'source.py').write_text('print("fixture")\n')
        return release.source_files(root)

    def test_archive_inventory_and_changed_payload_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = self.fixture(root)
            release.refresh(root, files)
            release.check(root, release.source_files(root))
            (root/'source.py').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'payload'):
                release.check(root, files)

    def test_new_source_cannot_be_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = self.fixture(root)
            release.refresh(root, files)
            (root/'new.patch').write_text('new source\n')
            with self.assertRaisesRegex(ValueError, 'inventory'):
                release.check(root, release.source_files(root))
            (root/'panel/patches').mkdir(parents=True)
            (root/'panel/patches/0009-untracked.patch').write_text('new patch\n')
            with self.assertRaisesRegex(ValueError, 'omitted'):
                release.refresh(root, files)

    def test_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            (root/'linked.py').symlink_to(root/'source.py')
            with self.assertRaisesRegex(ValueError, 'regular file'):
                release.payload(root, 'linked.py')

    def test_only_hash_catalogued_artwork_is_allowed(self):
        import hashlib, json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'assets').mkdir()
            data=b'GIF89a\0fixture'
            (root/'assets/art.gif').write_bytes(data)
            (root/'assets/catalog.json').write_text(json.dumps({'assets':[{'path':'assets/art.gif', 'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}]}))
            release.payload(root,'assets/art.gif')
            (root/'assets/art.gif').write_bytes(data+b'changed')
            with self.assertRaisesRegex(ValueError,'changed artwork'): release.payload(root,'assets/art.gif')
            (root/'binary').write_bytes(b'ELF\0')
            with self.assertRaisesRegex(ValueError,'Binary'): release.payload(root,'binary')
