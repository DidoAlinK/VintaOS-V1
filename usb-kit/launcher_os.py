"""
Vinta OS — application launcher.

Starts the Flask API and serves the built frontend from a single origin on
127.0.0.1, then opens the assistant's browser. One process, one origin, no
internet: the frontend's Content-Security-Policy is ``connect-src 'self'``, so
the API and the UI must share an origin or the browser blocks every request
before CORS is ever consulted.

Where things live (Windows):
    program   %LOCALAPPDATA%\\Vinta OS\\Vinta OS.exe   (installed by Setup.exe)
    data      %APPDATA%\\Vinta OS\\vinta.db            (the academy's database)

The database deliberately lives under %APPDATA% and NOT beside the executable.
An update or a reinstall replaces the program folder wholesale; if the database
sat inside it, an update would delete the school's entire records. Separating
them is what makes "reinstall to update" safe.

Environment variables are set *before* ``app`` is imported. That ordering is
required, not stylistic: ``app/config.py`` reads ``os.environ`` while its
configuration class bodies are being evaluated, so anything set afterwards is
ignored. ``python-dotenv`` also runs during that import, but it does not
overwrite variables that are already set — which is what stops a stray ``.env``
from redirecting the database.

Usage:
    Vinta OS.exe                  start and open the browser
    Vinta OS.exe --init-db        create the database and exit (used by Setup)
    Vinta OS.exe --reset          delete the stored data, then start empty
    Vinta OS.exe --no-browser     start without opening a browser
    Vinta OS.exe --port 5055      listen on a specific port
    Vinta OS.exe --data-dir PATH  keep the database somewhere else
    Vinta OS.exe --version        print the version and exit
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import socket
import sys
import threading
import traceback
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

#: Kept in step with the installer, which shows it in Add/Remove Programs.
APP_NAME = "Vinta OS"
APP_VERSION = "1.6.3"

HOST = "127.0.0.1"
DEFAULT_PORT = 5000
#: If 5000 is taken (a stale copy, or another program), walk upward rather than
#: failing. Nobody standing in a school office should ever see a port error.
PORT_SCAN_LIMIT = 12

DB_FILENAME = "vinta.db"
BANNER_WIDTH = 68

log = logging.getLogger("vinta")


# --------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------
def app_dir() -> Path:
    """The folder holding the executable the user double-clicked."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # Running from source: this file sits in usb-kit/.
    return Path(__file__).resolve().parent


def bundle_dir() -> Path:
    """Read-only resources bundled into the executable (the built frontend)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def default_data_dir() -> Path:
    """
    %APPDATA%\\Vinta OS — the roaming application data folder.

    Roaming rather than Local so the school's records follow the staff account
    if the machine is ever re-imaged or the profile is moved. Falls back to the
    user's home if APPDATA is somehow unset, which beats crashing on launch.
    """
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME.lower().replace(' ', '-')}"


def resolve_web_dir(override: str | None) -> Path:
    """Locate the built frontend (a folder containing index.html)."""
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(bundle_dir() / "web")
    candidates.append(app_dir() / "web")

    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate.resolve()

    raise SystemExit(
        "Could not find the Vinta OS user interface (expected a folder holding "
        "index.html).\nLooked in:\n"
        + "\n".join(f"  - {c}" for c in candidates)
        + "\n\nReinstall Vinta OS with Setup.exe."
    )


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
def start_logging(data_dir: Path, verbose: bool) -> None:
    """
    Mirror output to the console and to a file in the data folder.

    The file matters in the field: whoever installs this at a school can read
    ``vinta-os.log`` afterwards instead of trying to describe a black window
    that has already been closed.

    The file handler goes on the *root* logger as well as on this module's. The
    application logs through Flask's own logger, which neither of this module's
    handlers would ever see, so a traceback would reach a console that is about
    to be closed and nothing else — the one case the log file existed for.
    Werkzeug keeps the console handler it makes for itself, so nothing is
    printed twice; only the file gains lines.
    """
    level = logging.DEBUG if verbose else logging.INFO
    log.setLevel(level)
    log.propagate = False

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(stream)

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(data_dir / "vinta-os.log", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-7s %(name)s  %(message)s")
        )
    except OSError:
        # A locked-down or read-only profile is not a reason to refuse to start.
        return

    log.addHandler(handler)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


# --------------------------------------------------------------------------
# Secrets
# --------------------------------------------------------------------------
def load_or_create_secrets(data_dir: Path) -> dict:
    """
    Reuse one signing key pair across runs, generating it on first launch.

    Persisting matters: the session token is signed with JWT_SECRET_KEY, so
    regenerating it on every start would log the staff out mid-shift. It also
    keeps the build self-contained — no shared secret and no production
    credential is ever shipped inside the executable.
    """
    secrets_path = data_dir / "instance-secrets.json"
    if secrets_path.is_file():
        try:
            stored = json.loads(secrets_path.read_text(encoding="utf-8"))
            if stored.get("SECRET_KEY") and stored.get("JWT_SECRET_KEY"):
                return stored
        except (OSError, ValueError):
            log.warning("Session keys were unreadable; generating a new pair.")

    generated = {
        "SECRET_KEY": secrets.token_hex(32),
        "JWT_SECRET_KEY": secrets.token_hex(32),
    }
    try:
        secrets_path.write_text(json.dumps(generated, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("Could not save session keys (%s); sessions reset on restart.", exc)
    return generated


# --------------------------------------------------------------------------
# Ports
# --------------------------------------------------------------------------
def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((HOST, port))
            return True
        except OSError:
            return False


def looks_like_our_app(port: int) -> bool:
    """
    Is Vinta already serving on this port?

    Separates "the staff member launched it twice" (open a browser tab, leave
    the running copy alone) from "an unrelated program holds port 5000" (move
    to the next port instead).
    """
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/health", timeout=1.5) as response:
            return b'"ok"' in response.read(200)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def choose_port(requested: int | None) -> int:
    """Return a usable port, or its negative if Vinta is already running on it."""
    if requested:
        if not port_is_free(requested):
            raise SystemExit(
                f"Port {requested} is already in use. Close the other program, "
                f"or start with --port {requested + 1}."
            )
        return requested

    for candidate in range(DEFAULT_PORT, DEFAULT_PORT + PORT_SCAN_LIMIT):
        if not port_is_free(candidate):
            if looks_like_our_app(candidate):
                return -candidate  # Negative signals "already running".
            continue
        return candidate

    raise SystemExit(
        f"Ports {DEFAULT_PORT}-{DEFAULT_PORT + PORT_SCAN_LIMIT - 1} are all in "
        "use. Restart the computer and try again."
    )


# --------------------------------------------------------------------------
# Environment + database
# --------------------------------------------------------------------------
def configure_environment(web_dir: Path, db_path: Path, data_dir: Path, port: int) -> None:
    """Set every variable the application reads, before ``app`` is imported."""
    os.environ["FLASK_ENV"] = "production"

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    keys = load_or_create_secrets(data_dir)
    os.environ["SECRET_KEY"] = keys["SECRET_KEY"]
    os.environ["JWT_SECRET_KEY"] = keys["JWT_SECRET_KEY"]

    # Same-origin build: the browser never sends a cross-origin request, but
    # CORS is configured anyway so the app behaves identically if staff open it
    # as "localhost" rather than "127.0.0.1".
    os.environ["CORS_ORIGINS"] = f"http://{HOST}:{port},http://localhost:{port}"

    # See app/__init__.py: eventlet's monkey-patching does not survive
    # PyInstaller's import graph, and the frontend opens no Socket.IO
    # connection, so the extra concurrency buys nothing in this build.
    os.environ["SOCKETIO_ASYNC_MODE"] = "threading"

    os.environ["VINTA_WEB_DIR"] = str(web_dir)


def prepare_database(app, db_path: Path, reset: bool) -> tuple[bool, int]:
    """
    Create the schema on first run, or rebuild it after --reset.

    ``migrations/versions/`` is empty in this repository, so ``flask db
    upgrade`` has nothing to apply and the schema is created from the models
    directly. Returns (created, table_count).
    """
    from app.extensions import db

    created = False
    if reset and db_path.exists():
        log.info("Removing the existing database (--reset).")
        db_path.unlink()

    if not db_path.exists():
        created = True

    with app.app_context():
        db.create_all()
        tables = len(db.metadata.tables)
    return created, tables


# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------
def print_banner(url: str, db_path: Path, created: bool) -> None:
    line = "=" * BANNER_WIDTH
    log.info(line)
    log.info(f"  {APP_NAME} — running".center(BANNER_WIDTH))
    log.info(line)
    log.info("")
    log.info(f"  The app is open at:  {url}")
    log.info("")
    log.info("  A browser window should have opened automatically.")
    log.info("  If it did not, copy the address above into your browser.")
    log.info("")
    if created:
        log.info("  This is a fresh start — there is no data yet.")
        log.info("  Create your academy with 'Sign up' on the login screen.")
        log.info("")
    log.info(f"  Your records are stored in: {db_path.parent}")
    log.info("  Nothing is sent anywhere; it all stays on this computer.")
    log.info("")
    log.info("  " + "-" * (BANNER_WIDTH - 4))
    log.info("  KEEP THIS WINDOW OPEN WHILE YOU USE VINTA OS.")
    log.info("  Closing it stops the app. Your work is saved as you go.")
    log.info("  " + "-" * (BANNER_WIDTH - 4))
    log.info("")


def harden_console() -> None:
    """
    Keep one unencodable character from taking the whole program down.

    The banner and the diagnostics use a few typographic dashes. A console on a
    legacy codepage -- cp850 turns up on French and Arabic Windows, and has no
    em dash -- raises UnicodeEncodeError the moment one is written, which kills
    the app before the window ever appears. Anything that reaches an ordinary
    console is also written to a pipe or a file when the program is started by
    a script or an installer, where the encoding is the same guess.

    Asking for errors="replace" trades a stray '?' for a program that starts.
    The log file is unaffected; it is UTF-8 by construction.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError, ValueError):
            # No stream at all (a windowed build), or an object that cannot be
            # reconfigured. Neither is a reason to refuse to start.
            pass


def fatal(message: str) -> None:
    """
    Report a startup failure on a machine with no console attached.

    The build is a console application, so normally the traceback is visible.
    This is the safety net for a windowed build: without it a hard failure
    would look like nothing happening at all.
    """
    log.error(message)
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, f"{APP_NAME} — error", 0x10)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    harden_console()

    parser = argparse.ArgumentParser(
        prog=APP_NAME, description="Run Vinta OS on this computer."
    )
    parser.add_argument("--reset", action="store_true",
                        help="delete the stored data and start from empty")
    parser.add_argument("--init-db", action="store_true",
                        help="create the database if missing, then exit")
    parser.add_argument("--no-browser", action="store_true",
                        help="start without opening a browser")
    parser.add_argument("--port", type=int, default=None,
                        help=f"port to listen on (default {DEFAULT_PORT})")
    parser.add_argument("--data-dir", default=None,
                        help="store the database somewhere other than the default")
    parser.add_argument("--web-dir", default=None,
                        help="path to a built frontend (for running from source)")
    parser.add_argument("--version", action="store_true", help="print the version")
    parser.add_argument("--verbose", action="store_true", help="log every request")
    args = parser.parse_args(argv)

    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    # VINTA_DATA_DIR lets the installer's smoke test (and ours) point the app at
    # a scratch folder without touching a real profile.
    data_dir = Path(
        args.data_dir or os.environ.get("VINTA_DATA_DIR") or default_data_dir()
    ).expanduser().resolve()

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        fatal(
            f"{APP_NAME} could not create its data folder:\n\n  {data_dir}\n\n"
            f"Reason: {exc}\n\n"
            "Check that this account is allowed to write to its own AppData folder."
        )
        return 2

    start_logging(data_dir, args.verbose)
    db_path = data_dir / DB_FILENAME

    try:
        web_dir = resolve_web_dir(args.web_dir)

        port = choose_port(args.port)
        if port < 0:
            # Already running. Point the browser at the copy that exists.
            live = -port
            url = f"http://{HOST}:{live}/"
            log.info("")
            log.info(f"  {APP_NAME} is already running at {url}")
            if not args.no_browser:
                webbrowser.open(url)
            log.info("  Use the window that is already open.")
            log.info("")
            return 0

        configure_environment(web_dir, db_path, data_dir, port)

        # Imported only now: app/config.py snapshots os.environ at import time.
        from app import create_app

        app = create_app("production")
        created, tables = prepare_database(app, db_path, reset=args.reset)

        if args.init_db:
            log.info("")
            log.info(f"  {APP_NAME} {APP_VERSION} — database ready")
            log.info(f"  File:   {db_path}")
            log.info(f"  Tables: {tables}")
            log.info("")
            return 0

        url = f"http://{HOST}:{port}/"
        print_banner(url, db_path, created)

        from werkzeug.serving import make_server

        server = make_server(HOST, port, app, threaded=True)

        if not args.no_browser:
            # Delayed so the socket is accepting before the browser asks for it.
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log.info("")
            log.info("  Shutting down — your work has been saved.")
        finally:
            server.server_close()
        return 0

    except SystemExit:
        raise
    except Exception:
        detail = traceback.format_exc()
        log.error(detail)
        fatal(
            f"{APP_NAME} could not start.\n\n"
            f"A log of this has been written to:\n  {data_dir / 'vinta-os.log'}\n\n"
            "Please send that file to Vinta support."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
