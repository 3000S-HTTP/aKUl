# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the aKUl desktop comparison app.

Build:  pyinstaller aKUl.spec --noconfirm
Output: dist/aKUl.exe
"""

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

SPEC_DIR = SPECPATH
APP_DIR = os.path.join(SPEC_DIR, "desktop")

datas = [(os.path.join(APP_DIR, "index.html"), ".")]
binaries = []
hiddenimports = [
    "keylimits",
    "keylimits.checker",
    "keylimits.comparison",
    "keylimits.formatting",
    "keylimits.report",
    "keylimits.http",
    "keylimits.models",
    "keylimits.providers",
]

# pywebview pulls in .NET / CLR loader machinery that PyInstaller cannot infer.
for package in ("webview", "pythonnet", "clr_loader"):
    collected = collect_all(package)
    datas += collected[0]
    binaries += collected[1]
    hiddenimports += collected[2]

hiddenimports += collect_submodules("keylimits.providers")

a = Analysis(
    [os.path.join(APP_DIR, "app.py")],
    pathex=[SPEC_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
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
    name="aKUl",
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
)