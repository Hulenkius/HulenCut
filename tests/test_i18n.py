import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cutter_app.i18n import i18n


class TranslationTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("zh_TW", persist=False)

    def test_english_translation(self):
        i18n.set_language("en_US", persist=False)
        self.assertEqual(i18n.translate("切片列表"), "Slice list")
        self.assertEqual(i18n.translate("請先導入圖片"), "Import an image first")

    def test_simplified_chinese_translation(self):
        i18n.set_language("zh_CN", persist=False)
        self.assertEqual(i18n.translate("切片預覽"), "切片预览")
        self.assertEqual(i18n.translate("請先導入圖片"), "请先导入图片")

    def test_round_trip_label(self):
        i18n.set_language("en_US", persist=False)
        translated = i18n.translate("切片預覽")
        self.assertEqual(i18n.to_source(translated), "切片預覽")

    def test_locale_catalogs_stay_in_sync(self):
        locale_dir = Path(__file__).resolve().parents[1] / "cutter_app" / "locales"
        catalogs = {
            path.stem: json.loads(path.read_text("utf-8"))["messages"]
            for path in locale_dir.glob("*.json")
        }
        reference = catalogs["zh_TW"]
        for language, messages in catalogs.items():
            self.assertEqual(set(messages), set(reference), language)
            for key, value in messages.items():
                key_slots = sorted(re.findall(r"\{(\d+)", key))
                value_slots = sorted(re.findall(r"\{(\d+)", value))
                self.assertEqual(key_slots, value_slots, f"{language}: {key}")

    def test_about_translation_key_matches_source(self):
        import ast

        source_path = Path(__file__).resolve().parents[1] / "cutter_app" / "main_window.py"
        tree = ast.parse(source_path.read_text("utf-8"))
        about_key = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "HulenCut v" in node.value and "https://vistudium.top/gouken/" in node.value:
                    about_key = node.value
                    break
        self.assertIsNotNone(about_key)
        i18n.set_language("en_US", persist=False)
        translated = i18n.translate(about_key)
        self.assertIn("Credits:", translated)
        self.assertIn("DeepSeek Harness", translated)

    def test_format_template(self):
        i18n.set_language("en_US", persist=False)
        message = i18n.translate("切片 {0} 移動完成").format(3)
        self.assertEqual(message, "Slice 3 moved")


if __name__ == "__main__":
    unittest.main()
