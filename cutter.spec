# -*- mode: python ; coding: utf-8 -*-
import os

# 自定義 tree 函數，替代原本的 Tree
def tree(src, prefix):
    res = []
    for root, dirs, files in os.walk(src):
        for file in files:
            full_path = os.path.join(root, file)
            dest_path = os.path.join(prefix, os.path.relpath(root, src))
            res.append((full_path, dest_path))
    return res

a = Analysis(
    ['cutter.py'],
    pathex=[],
    binaries=[],
    # 更新 datas 參數，使用自定義 tree 函數
    datas=tree('dist/HulenCut', 'HulenCut'),
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
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HulenCut'
)
