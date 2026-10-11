# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Vinta School OS offline review build.

Produces a one-folder build: `VintaSchoolOS.exe` plus a `_internal/` directory.
One-folder rather than one-file because one-file unpacks the entire Python
runtime to a temp directory on every launch — several seconds of startup, on a
USB stick, for no benefit here. The reviewer still double-clicks a single .exe.

Build it with:
    python -m PyInstaller packaging/vinta_review.spec --noconfirm
"""
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()          # packaging/
PROJECT = SPEC_DIR.parent                    # repository root
BACKEND = PROJECT / "Backend" / "vinta-academy-backend"
FRONTEND_DIST = PROJECT / "vinta-school-os" / "dist"


def collect_package_modules(package_dir: Path, package_name: str) -> list[str]:
    """
    Enumerate every module under a package.

    The app imports its blueprints, schemas, services and models *inside*
    functions (the app factory, `_register_blueprints`, service helpers). Static
    analysis usually follows those, but a miss surfaces only at runtime as a
    ModuleNotFoundError on whichever request happens to touch that module — the
    worst possible failure mode for a build handed to someone else. Enumerating
    the tree removes the guesswork and keeps working when files are added.
    """
    modules: list[str] = []
    for path in sorted(package_dir.rglob("*.py")):
        parts = list(path.relative_to(package_dir.parent).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            modules.append(".".join(parts))
    return modules


hidden = collect_package_modules(BACKEND / "app", "app")

hidden += [
    # Flask-Smorest discovers schemas and builds its spec through these.
    "flask_smorest",
    "marshmallow",
    "webargs",
    "apispec",
    "apispec.ext.marshmallow",
    # Extensions.
    "flask_sqlalchemy",
    "flask_migrate",
    "flask_jwt_extended",
    "flask_cors",
    "flask_socketio",
    "flask_limiter",
    "limits",
    "sqlalchemy",
    "sqlalchemy.sql.default_comparator",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "alembic",
    # Socket.IO drivers. app/__init__.py pins async_mode="threading" for this
    # build, but the package still resolves the driver by name at import time.
    "engineio.async_drivers.threading",
    "socketio.async_drivers.threading",
    # Auth + config.
    "bcrypt",
    "dotenv",
    # Apscheduler is installed and referenced by app/tasks/scheduler.py. That
    # module is currently unreachable (init_scheduler has no callers), but the
    # import is cheap to satisfy and expensive to discover missing at runtime.
    "apscheduler",
    "apscheduler.schedulers.background",
    "apscheduler.triggers.cron",
    "apscheduler.triggers.interval",
    "apscheduler.executors.pool",
    "apscheduler.jobstores.memory",
    # Runtime metadata lookups (importlib.metadata) for flask/werkzeug versions.
    "importlib.metadata",
]

excludes = [
    # Not used by this application. Pinned explicitly so PyInstaller does not
    # drag them in through a transitive import and double the bundle size.
    "eventlet",          # deliberately avoided; see SOCKETIO_ASYNC_MODE
    "gevent",
    "greenlet",
    "pymysql",           # SQLite build only
    "csvkit",
    "agate",
    "pandas",
    "numpy",
    "matplotlib",
    "tkinter",
    "pytest",
    "IPython",
    "PIL",
    "scipy",
]

datas = [
    # The built frontend, served by Flask at "/" (see app/spa.py).
    (str(FRONTEND_DIST), "web"),
]

a = Analysis(
    [str(SPEC_DIR / "launcher.py")],
    pathex=[str(BACKEND), str(SPEC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VintaSchoolOS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX compression is disabled: it has a long history of corrupting the
    # bundled DLLs of Python extensions, and the failure mode is a crash on
    # someone else's machine rather than a build error here.
    upx=False,
    console=True,          # The console is the app's window; see print_banner.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VintaSchoolOS",
)
