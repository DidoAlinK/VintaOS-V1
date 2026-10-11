# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Uninstall.exe.

ONE-FILE, which keeps the uninstaller a single file the user can also double-
click from inside the install folder. It still cannot delete its own running
image, so it re-runs itself from a copy in %TEMP% to finish the job — see the
note at the top of uninstall.py.

Build with (usb-kit/build_usb.py drives the whole pipeline):
    python -m PyInstaller usb-kit/uninstall.spec --noconfirm --clean
"""
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
ICON = SPEC_DIR / "assets" / "vinta.ico"

a = Analysis(
    [str(SPEC_DIR / "uninstall.py")],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=["shortcuts"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PIL", "numpy", "pandas", "matplotlib", "pytest"],
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
    name="Uninstall",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.is_file() else None,
)
