"""Tests for OCR character slicing without running the heavy model."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt5.QtCore import QPoint, QRectF, Qt
from PyQt5.QtGui import QColor, QImage, QKeySequence
from PyQt5.QtWidgets import QAction, QApplication, QDialog, QMenu

from cutter_app import text_recognition
from cutter_app.dialogs import TextRecognitionSliceDialog
from cutter_app.graphics import SliceRect
from cutter_app.i18n import i18n
from cutter_app.main_window import MainWindow
from cutter_app.text_recognition import (
    RecognizedCharacter,
    recognize_characters,
    recognize_text,
)


def _quad(x1, y1, x2, y2):
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


class FakeDetector:
    def __init__(self, results, fallback_text=""):
        self.results = results
        self.fallback_text = fallback_text

    def recognize(self, _image_rgb, short_size=960):
        return self.results

    def recognize_line_text(self, _image_rgb):
        return self.fallback_text


class TextRecognitionBackendTests(unittest.TestCase):
    def _run_with_results(self, results, orientation):
        original = text_recognition._get_detector
        text_recognition._get_detector = lambda: FakeDetector(results)
        try:
            image = np.full((60, 140, 3), 255, dtype=np.uint8)
            return recognize_characters(image, orientation=orientation)
        finally:
            text_recognition._get_detector = original

    def test_horizontal_order_skips_spaces_and_keeps_bounds(self):
        results = [
            {
                "bbox": np.array(_quad(0, 0, 130, 20)),
                "result": {
                    "char_list": [
                        {"char": "甲", "bbox": _quad(5, 4, 18, 18)},
                        {"char": " ", "bbox": _quad(20, 4, 24, 18)},
                        {"char": "乙", "bbox": _quad(28, 4, 42, 18)},
                    ]
                },
            },
            {
                "bbox": np.array(_quad(0, 25, 130, 45)),
                "result": {
                    "char_list": [
                        {"char": "丙", "bbox": _quad(5, 28, 18, 43)},
                    ]
                },
            },
        ]
        chars = self._run_with_results(results, "horizontal")
        self.assertEqual([item.char for item in chars], ["甲", "乙", "丙"])
        x, y, w, h = chars[0].bounds()
        self.assertEqual((x, y, w, h), (5.0, 4.0, 13.0, 14.0))

    def test_recognize_text_joins_detected_lines(self):
        results = [
            {
                "bbox": np.array(_quad(0, 0, 80, 20)),
                "result": {"line_pred": "甲乙"},
            },
            {
                "bbox": np.array(_quad(0, 25, 80, 45)),
                "result": {"line_pred": "丙丁"},
            },
        ]
        original = text_recognition._get_detector
        text_recognition._get_detector = lambda: FakeDetector(results)
        try:
            image = np.full((60, 100, 3), 255, dtype=np.uint8)
            self.assertEqual(recognize_text(image), "甲乙 丙丁")
        finally:
            text_recognition._get_detector = original

    def test_recognize_text_falls_back_to_crnn(self):
        original = text_recognition._get_detector
        text_recognition._get_detector = lambda: FakeDetector(
            [], fallback_text="單字"
        )
        try:
            image = np.full((32, 32, 3), 255, dtype=np.uint8)
            self.assertEqual(recognize_text(image), "單字")
        finally:
            text_recognition._get_detector = original

    def test_vertical_order_reads_columns_right_to_left(self):
        results = [
            {
                "bbox": np.array(_quad(0, 0, 30, 55)),
                "result": {
                    "char_list": [
                        {"char": "左", "bbox": _quad(5, 5, 20, 20)},
                    ]
                },
            },
            {
                "bbox": np.array(_quad(80, 0, 110, 55)),
                "result": {
                    "char_list": [
                        {"char": "右", "bbox": _quad(85, 5, 100, 20)},
                    ]
                },
            },
        ]
        chars = self._run_with_results(results, "vertical")
        self.assertEqual([item.char for item in chars], ["右", "左"])


class CharacterSliceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setOrganizationName("_HulenCutTests")
        cls.app.setApplicationName("_HulenCutTestsOCR")
        MainWindow.settings_organization = "_HulenCutTests"
        MainWindow.settings_application = "_HulenCutTestsOCRMainWindow"
        i18n.initialize(cls.app)

    def test_action_and_dialog_offer_horizontal_and_vertical(self):
        i18n.set_language("zh_TW", persist=False)
        window = MainWindow()
        action_texts = [action.text() for action in window.findChildren(type(window.actCommandPalette))]
        self.assertIn("依圖形識別切片", action_texts)
        self.assertIn("依文字識別切片", action_texts)

        ocr_action = next(
            action
            for action in window.findChildren(QAction)
            if action.text() == "依文字識別切片"
        )
        self.assertEqual(ocr_action.shortcut(), QKeySequence("Ctrl+W"))
        self.assertEqual(ocr_action.shortcutContext(), Qt.WindowShortcut)

        toolbar = window.findChild(__import__("PyQt5.QtWidgets", fromlist=["QToolBar"]).QToolBar, "mainToolbar")
        toolbar_actions = {
            action.text(): action
            for action in toolbar.actions()
            if not action.isSeparator()
        }
        self.assertIn("依文字識別切片", toolbar_actions)
        self.assertNotEqual(
            toolbar_actions["依文字識別切片"].icon().cacheKey(),
            toolbar_actions["批量重命名"].icon().cacheKey(),
        )

        dialog = TextRecognitionSliceDialog(window)
        self.assertTrue(dialog.radioHorizontal.isChecked())
        dialog.radioVertical.setChecked(True)
        self.assertEqual(dialog.getValues()["orientation"], "vertical")
        dialog.close()
        window.close()

    def test_all_action_shortcuts_are_portable_and_unique(self):
        i18n.set_language("zh_TW", persist=False)
        window = MainWindow()
        seen = {}
        for action in window.findChildren(QAction):
            sequence = action.shortcut()
            if sequence.isEmpty():
                continue
            portable = sequence.toString(QKeySequence.PortableText)
            self.assertTrue(portable)
            self.assertNotIn(
                portable,
                seen,
                f"Duplicate shortcut {portable}: {seen.get(portable)} / {action.text()}",
            )
            seen[portable] = action.text()
        self.assertIn("Ctrl+W", seen)
        self.assertEqual(seen["Ctrl+W"], "依文字識別切片")
        window.close()

    def test_command_creates_one_named_slice_per_character(self):
        i18n.set_language("zh_TW", persist=False)
        window = MainWindow()
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = os.path.join(temp_dir, "ocr.png")
            image = QImage(120, 80, QImage.Format_RGB32)
            image.fill(QColor("white"))
            self.assertTrue(image.save(image_path))
            window.sliceView.loadImage(image_path)

            characters = [
                RecognizedCharacter("甲", ((5, 5), (20, 5), (20, 25), (5, 25))),
                RecognizedCharacter("乙", ((25, 5), (40, 5), (40, 25), (25, 25))),
            ]

            class FakeDialog:
                def __init__(self, _parent=None):
                    pass

                def exec_(self):
                    return QDialog.Accepted

                def getValues(self):
                    return {"orientation": "horizontal"}

            with patch(
                "cutter_app.main_window.TextRecognitionSliceDialog", FakeDialog
            ), patch(
                "cutter_app.main_window.recognize_characters",
                return_value=characters,
            ):
                window.autoRecognizeCharacterSlices()

            slices = sorted(
                [
                    item
                    for item in window.sliceView.scene().items()
                    if isinstance(item, SliceRect)
                ],
                key=lambda item: item.number,
            )
            self.assertEqual([item.name for item in slices], ["甲", "乙"])
            self.assertEqual(window.sliceList.count(), 2)
        window.close()

    def test_recognize_slice_text_names_multiple_selected_slices(self):
        i18n.set_language("zh_TW", persist=False)
        window = MainWindow()
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = os.path.join(temp_dir, "ocr_slices.png")
            image = QImage(120, 80, QImage.Format_RGB32)
            image.fill(QColor("white"))
            self.assertTrue(image.save(image_path))
            window.sliceView.loadImage(image_path)

            first = SliceRect(QRectF(5, 5, 20, 20), 1)
            second = SliceRect(QRectF(30, 5, 20, 20), 2)
            window.sliceView.scene().addItem(first)
            window.sliceView.scene().addItem(second)

            with patch(
                "cutter_app.main_window.recognize_text",
                side_effect=["甲", "乙"],
            ) as mocked:
                window.recognizeSliceText([first, second])

            self.assertEqual(mocked.call_count, 2)
            self.assertEqual([first.name, second.name], ["甲", "乙"])
        window.close()

    def test_both_context_menus_offer_recognize_text(self):
        i18n.set_language("zh_TW", persist=False)
        window = MainWindow()
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = os.path.join(temp_dir, "context.png")
            image = QImage(120, 80, QImage.Format_RGB32)
            image.fill(QColor("white"))
            self.assertTrue(image.save(image_path))
            window.sliceView.loadImage(image_path)

            slice_item = SliceRect(QRectF(5, 5, 20, 20), 1)
            window.sliceView.scene().addItem(slice_item)
            slice_item.setSelected(True)
            window.updateSliceList()
            window.sliceList.item(0).setSelected(True)

            captured = []

            def capture_menu_actions(menu, *_args, **_kwargs):
                captured.append([action.text() for action in menu.actions()])
                return None

            class FakeEvent:
                def screenPos(self):
                    return QPoint(0, 0)

                def accept(self):
                    pass

            with patch.object(QMenu, "exec_", capture_menu_actions):
                slice_item.contextMenuEvent(FakeEvent())
                window.sliceList.showContextMenu(QPoint(0, 0))

            self.assertEqual(len(captured), 2)
            self.assertTrue(all("識別文字" in actions for actions in captured))
        window.close()


if __name__ == "__main__":
    unittest.main()
