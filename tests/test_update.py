import unittest

from cutter_app.dialogs import is_newer_version


class UpdateVersionTests(unittest.TestCase):
    def test_same_version_with_bom_is_not_update(self):
        self.assertFalse(is_newer_version("v0.8.2", "\ufeffv0.8.2\r\n"))

    def test_newer_version_is_detected(self):
        self.assertTrue(is_newer_version("v0.8.2", "v0.8.3"))

    def test_older_version_is_not_update(self):
        self.assertFalse(is_newer_version("v0.8.2", "v0.8.1"))


if __name__ == "__main__":
    unittest.main()
