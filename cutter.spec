# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)

# OCR is optional at runtime, so collect its packages explicitly.  This keeps
# the native ONNX Runtime extension and the Shapely/pyclipper backends in the
# frozen build even though they are imported lazily by the UI.
ocr_datas = []
ocr_binaries = []
ocr_hiddenimports = []
for _package in ("onnxruntime", "PIL", "shapely", "pyclipper"):
    try:
        _datas, _binaries, _hiddenimports = collect_all(_package)
    except Exception:
        continue
    ocr_datas += _datas
    ocr_binaries += _binaries
    ocr_hiddenimports += _hiddenimports

a = Analysis(
    [str(ROOT / "cutter.py")],
    pathex=[str(ROOT)],
    binaries=ocr_binaries,
    datas=[
        (str(ROOT / "hulencutter.ico"), "."),
        (str(ROOT / "LICENSE"), "."),
        (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
        (str(ROOT / "cutter_app" / "locales"), "cutter_app/locales"),
        (str(ROOT / "cutter_app" / "assets"), "cutter_app/assets"),
        (str(ROOT / "cutter_app" / "models"), "cutter_app/models"),
    ] + ocr_datas,
    hiddenimports=ocr_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HulenCut",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "hulencutter.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HulenCut",
)
