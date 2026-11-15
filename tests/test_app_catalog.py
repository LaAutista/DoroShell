"""Fresh-process GIO fixtures prevent process-global XDG caches reading user data."""
import unittest
from check_app_catalog_offscreen import isolated


class RealCatalogTests(unittest.TestCase):
    def test_real_notifications_overrides_and_focus(self):
        result=isolated('changes')
        self.assertGreater(result['signals'],0)
        self.assertLessEqual(result['burst_queries'],3)

    def test_exports_need_environment_registration(self):
        self.assertEqual(isolated('no-exports')['scenario'],'no-exports')

    def test_real_localized_and_unicode_metadata(self):
        self.assertEqual(isolated('localized')['scenario'],'localized')
