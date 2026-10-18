# -*- mode: python ; coding: utf-8 -*-
import os

# 修改後的自定義 tree 函數，僅加入有效檔案，避免加入目錄
def tree(src, prefix):
    res = []
    for root, dirs, files in os.walk(src):
        for file in files:
            full_path = os.path.join(root, file)
            if os.path.isfile(full_path):  # 僅加入有效檔案
                dest_path = os.path.join(prefix, os.path.relpath(root, src))
                res.append((full_path, dest_path))
    return res

# 定義並過濾資料資源
data_files = [d for d in tree('dist/HulenCut', 'HulenCut') if os.path.isfile(d[0])]

a = Analysis(
    ['cutter.py'],
    pathex=[],
    binaries=[],
    datas=data_files,  # 使用已過濾的資料資源
    hiddenimports=[],
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
    name='HulenCut',
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
    icon='hulencutter.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    data_files,  # 統一使用 data_files
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HulenCut'
)
