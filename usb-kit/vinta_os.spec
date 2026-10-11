# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Vinta OS.

Produces a ONE-FOLDER build: ``Vinta OS.exe`` plus an ``_internal`` directory.
One-folder rather than one-file on purpose — a one-file build unpacks the whole
Python runtime to a temp directory on every single launch, which on an older
school machine is several seconds of a black window before anything happens.
The assistant still double-clicks one file; the folder around it is invisible
to them.

Build it with (prefer usb-kit/build_usb.py, which does the whole pipeline):
    python -m PyInstaller usb-kit/vinta_os.spec --noconfirm --clean
"""
import ast
import importlib.util
import sys
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()          # usb-kit/
PROJECT = SPEC_DIR.parent                    # repository root
BACKEND = PROJECT / "Backend" / "vinta-academy-backend"
FRONTEND_DIST = PROJECT / "vinta-school-os" / "dist"
APP_PKG = BACKEND / "app"
ICON = SPEC_DIR / "assets" / "vinta.ico"


def app_modules() -> list[str]:
    """
    Every module in the ``app`` package, by dotted name.

    The application imports its blueprints, schemas, services and models
    *inside* functions (the app factory, ``_register_blueprints``, the service
    helpers). Static analysis usually follows those, but a miss surfaces only
    at runtime as a ModuleNotFoundError on whichever request happens to touch
    that module — the worst possible failure, because it appears in front of a
    customer. Enumerating the tree removes the guesswork entirely and keeps
    working as files are added.
    """
    modules: list[str] = []
    for path in sorted(APP_PKG.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        parts = list(path.relative_to(APP_PKG.parent).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            modules.append(".".join(parts))
    return modules


def third_party_imports() -> list[str]:
    """
    Third-party modules the application imports, discovered from its AST.

    Several dependencies are imported lazily inside functions — reportlab,
    arabic-reshaper and python-bidi, for instance, load only when a PDF is
    exported. A hidden-import list maintained by hand silently rots the moment
    one of those moves, and the failure lands on a customer mid-invoice.
    Reading the imports out of the source keeps the list honest.
    """
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    found: set[str] = set()

    for path in APP_PKG.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            roots: list[str] = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:          # relative import: stays inside `app`
                    continue
                if node.module:
                    roots = [node.module.split(".")[0]]
            for root in roots:
                if root in stdlib or root == "app":
                    continue
                if importlib.util.find_spec(root) is None:
                    continue
                found.add(root)

    return sorted(found)


hidden = app_modules() + third_party_imports()

hidden += [
    # Flask-Smorest discovers schemas and builds its OpenAPI document through
    # these; they are reached by registry lookup rather than by import.
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
    # Socket.IO resolves its driver by name at import time. app/__init__.py
    # pins async_mode="threading" for this build, but the lookup still happens.
    # The drivers live under engineio; flask-socketio has no async_drivers
    # package of its own, so only this one is listed.
    "engineio.async_drivers.threading",
    # Auth + config.
    "bcrypt",
    "dotenv",
    # Referenced by app/tasks/scheduler.py. That module is currently unreachable
    # (init_scheduler has no callers), but satisfying the import is cheap and
    # discovering it missing at runtime is not.
    "apscheduler",
    "apscheduler.schedulers.background",
    "apscheduler.triggers.cron",
    "apscheduler.triggers.interval",
    "apscheduler.executors.pool",
    "apscheduler.jobstores.memory",
    # reportlab loads its font metrics and encodings by name at runtime, and
    # imports arabic-reshaper/python-bidi through it when shaping Arabic text.
    "reportlab",
    "reportlab.pdfbase.ttfonts",
    "reportlab.pdfbase.pdfmetrics",
    "reportlab.pdfbase._fontdata",
    "reportlab.pdfbase._fontdata_widths_helvetica",
    "arabic_reshaper",
    "bidi",
    "bidi.algorithm",
    # reportlab imports Pillow unconditionally at module level: lib/utils.py does
    # a bare ``from PIL import Image``, and every part of reportlab reaches that
    # module. So Pillow is not optional here, however little of it a table of
    # numbers actually uses. It is named explicitly because this application's
    # own source never imports it, which makes it exactly the dependency an
    # exclusion list removes without anyone noticing.
    "PIL",
    "PIL.Image",
    # Runtime metadata lookups (importlib.metadata) for flask/werkzeug versions.
    "importlib.metadata",
]

excludes = [
    # Nothing in this application's own source uses these, and pinning them
    # keeps PyInstaller from dragging them in through a transitive import and
    # doubling the bundle size.
    #
    # The bar for adding a name here is higher than it looks. "Our code does not
    # import it" is not the same as "nothing in the shipped bundle imports it",
    # and a dependency that is only reached through a library is invisible until
    # the one feature that needs it is used. Pillow was on this list once, on
    # the reasoning that a table of numbers needs no image library; reportlab
    # does a bare ``from PIL import Image`` in lib/utils.py, so every PDF export
    # raised ModuleNotFoundError. Remove a name only after checking that no
    # bundled dependency imports it at module level.
    "eventlet",          # avoided on purpose; see SOCKETIO_ASYNC_MODE
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
    "scipy",
    "PyInstaller",
    "setuptools",
    "pip",
]

datas = [
    # The built frontend, served by Flask at "/" (see app/spa.py).
    (str(FRONTEND_DIST), "web"),
    # The bundled Arabic/Latin TTF that app/services/export_service.py looks for
    # relative to the app package. Without it, a packaged build silently falls
    # back to a system font and an Arabic PDF can render as blank glyphs.
    (str(APP_PKG / "assets"), "app/assets"),
]

a = Analysis(
    [str(SPEC_DIR / "launcher_os.py")],
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
    name="Vinta OS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is disabled: it has a long history of corrupting the bundled DLLs of
    # Python extensions, and the failure mode is a crash on someone else's
    # machine rather than an error here.
    upx=False,
    # The console window is the app's window: it shows the address, the data
    # folder, and any error, and closing it is how staff stop the app.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.is_file() else None,
    version=str(SPEC_DIR / "assets" / "version_info.txt")
            if (SPEC_DIR / "assets" / "version_info.txt").is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Vinta OS",
)
