# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Setup.exe - the Vinta OS installer.

ONE-FILE on purpose. The installer is the one artifact the operator has to find
on a USB stick and double-click, so it is the one thing that should never be
separable from anything. The application it installs is NOT embedded: it sits
in the "Vinta OS" folder beside Setup.exe and is copied from there. Embedding a
150 MB payload would mean unpacking it to temp and then copying it again, which
is both slower and needs twice the free disk on a machine that may be short of
it.

One-file is also harmless here, unlike for the application itself: Setup runs
once, so the startup unpack cost is paid once rather than on every launch.

Build with (usb-kit/build_usb.py drives the whole pipeline):
    python -m PyInstaller usb-kit/setup.spec --noconfirm --clean
"""
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
ICON = SPEC_DIR / "assets" / "vinta.ico"

a = Analysis(
    [str(SPEC_DIR / "setup_boot.py")],
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
    name="Setup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # Console, not windowed: the operator needs to see the progress and any
    # error, and the run is short.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.is_file() else None,
)
