"""Regenerate the Simplified Chinese locale from zh_TW.json.

The locale keys intentionally remain the original Traditional Chinese source
text. OpenCC is therefore used only to convert the translated values; the keys
are restored by position after conversion.

Usage:
    python tools/generate_zh_cn.py
    set OPENCC_DIR=D:\Opencc && python tools/generate_zh_cn.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "cutter_app" / "locales"
OPENCC_DIR = Path(os.environ.get("OPENCC_DIR", r"D:\Opencc"))
OPENCC_EXE = OPENCC_DIR / "opencc.exe"
OPENCC_CONFIG = OPENCC_DIR / "t2s.json"


def main() -> None:
    if not OPENCC_EXE.exists() or not OPENCC_CONFIG.exists():
        raise SystemExit(f"OpenCC not found in {OPENCC_DIR}")

    source_path = LOCALES / "zh_TW.json"
    target_path = LOCALES / "zh_CN.json"
    source = json.loads(source_path.read_text("utf-8"))

    with tempfile.TemporaryDirectory() as temp_dir:
        converted_path = Path(temp_dir) / "zh_CN.json"
        subprocess.run(
            [
                str(OPENCC_EXE),
                "-i", str(source_path),
                "-o", str(converted_path),
                "-c", str(OPENCC_CONFIG),
            ],
            check=True,
        )
        converted = json.loads(converted_path.read_text("utf-8"))

    source_messages = source["messages"]
    converted_messages = converted["messages"]
    if len(source_messages) != len(converted_messages):
        raise SystemExit("OpenCC output has a different number of messages")

    payload = {
        "locale": "zh_CN",
        "name": "简体中文",
        "messages": dict(zip(source_messages.keys(), converted_messages.values())),
    }
    target_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Updated {target_path}")


if __name__ == "__main__":
    main()
