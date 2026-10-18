import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication, QToolBar

from cutter_app.command_palette import CommandPaletteDialog
from cutter_app.graphics import SliceRect
from cutter_app.i18n import i18n
from cutter_app.main_window import MainWindow
from cutter_app.theme import theme_manager


class MainWindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setOrganizationName("_HulenCutTests")
        cls.app.setApplicationName("_HulenCutTests")
        MainWindow.settings_organization = "_HulenCutTests"
        MainWindow.settings_application = "_HulenCutTestsMainWindow"
        i18n.initialize(cls.app)
        theme_manager.initialize(cls.app)

    def test_language_switch_retranslates_open_window(self):
        i18n.set_language("zh_TW", persist=False)
        window = MainWindow()
        self.assertIn("HulenCut", window.windowTitle())
        window.changeLanguage("en_US")
        self.assertEqual(window.windowTitle(), "HulenCut v0.8.0")
        window.changeLanguage("zh_TW")
        self.assertIn("囫圇切", window.windowTitle())
        window.close()
        window.deleteLater()

    def test_simplified_chinese_retranslation(self):
        i18n.set_language("zh_TW", persist=False)
        window = MainWindow()
        window.changeLanguage("zh_CN")
        self.assertEqual(window.windowTitle(), "囫囵切 HulenCut v0.8.0")
        window.close()
        window.deleteLater()

    def test_theme_switch(self):
        window = MainWindow()
        window.changeTheme("light")
        self.assertEqual(theme_manager.resolved_theme, "light")
        window.changeTheme("dark")
        self.assertEqual(theme_manager.resolved_theme, "dark")
        window.close()
        window.deleteLater()

    def test_drag_and_drop_image_routing(self):
        i18n.set_language("en_US", persist=False)
        window = MainWindow()
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = os.path.join(temp_dir, "sample.png")
            image = QImage(32, 24, QImage.Format_RGB32)
            image.fill(QColor("white"))
            self.assertTrue(image.save(image_path))
            window.handleDroppedPaths([image_path])
            self.assertIsNotNone(window.sliceView.image_item)
            self.assertEqual(window.currentImagePath, image_path)
        window.close()
        window.deleteLater()

    def test_command_palette_filters_actions(self):
        i18n.set_language("en_US", persist=False)
        window = MainWindow()
        dialog = CommandPaletteDialog(window.findChildren(__import__("PyQt5.QtWidgets", fromlist=["QAction"]).QAction), window)
        self.assertGreater(dialog.commands.count(), 0)
        dialog.search.setText("export")
        labels = [dialog.commands.item(i).text().lower() for i in range(dialog.commands.count())]
        self.assertTrue(any("export" in label for label in labels))
        dialog.close()
        window.close()
        window.deleteLater()

    def test_slice_labels_hide_when_selected(self):
        slice_item = SliceRect(QRectF(0, 0, 100, 50), 1, name="Test slice")
        self.assertTrue(slice_item.labelsVisible())
        slice_item.setSelected(True)
        self.assertFalse(slice_item.labelsVisible())
        slice_item.setSelected(False)
        self.assertTrue(slice_item.labelsVisible())

    def test_photoshop_shell_has_menu_bar_and_icon_strip(self):
        i18n.set_language("en_US", persist=False)
        window = MainWindow()
        self.assertGreaterEqual(len(window.menuBar().actions()), 6)
        toolbar = window.findChild(QToolBar, "mainToolbar")
        self.assertIsNotNone(toolbar)
        self.assertEqual(toolbar.toolButtonStyle(), Qt.ToolButtonIconOnly)
        action_icons = [a.icon().isNull() for a in toolbar.actions() if not a.isSeparator()]
        self.assertTrue(action_icons)
        self.assertFalse(any(action_icons))
        window.close()
        window.deleteLater()

    def test_language_specific_font_family(self):
        i18n.set_language("zh_TW", persist=False)
        self.assertIn(theme_manager.ui_font().family(), ("Microsoft JhengHei", "Microsoft JhengHei UI"))
        i18n.set_language("zh_CN", persist=False)
        self.assertIn(theme_manager.ui_font().family(), ("Microsoft YaHei", "Microsoft YaHei UI"))
        i18n.set_language("en_US", persist=False)
        self.assertIn(theme_manager.ui_font().family(), ("Segoe UI", "Segoe UI Variable"))

    def test_theme_stepper_assets_exist(self):
        assets = Path(__file__).resolve().parents[1] / "cutter_app" / "assets"
        for name in ("spin_up_dark.png", "spin_down_dark.png", "spin_up_light.png", "spin_down_light.png"):
            self.assertTrue((assets / name).is_file(), name)

    def test_public_entry_point_reexports_main_window(self):
        import cutter

        self.assertIs(cutter.MainWindow, MainWindow)


if __name__ == "__main__":
    unittest.main()
