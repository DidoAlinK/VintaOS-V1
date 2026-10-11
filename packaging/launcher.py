"""
Vinta School OS — offline review build launcher.

Runs the Flask API and the built frontend from a single origin on localhost, so
the reviewer double-clicks one file, a browser opens, and the app is up.

Everything this process writes lives in a `data/` folder beside the executable.
Nothing outside that folder is touched, and the application's normal
configuration (`Backend/.../.env`, the developer databases under
`instance/`) is neither read nor shipped.

Environment variables are set *before* `app` is imported. That ordering is
required, not stylistic: `app/config.py` reads `os.environ` while the
configuration class bodies are being evaluated, so anything set afterwards
would be ignored. `python-dotenv` is also called during that import, but it
does not overwrite variables that are already set — which is what keeps a
stray `.env` from redirecting the database.

Usage:
    VintaSchoolOS.exe                     start (opens the browser)
    VintaSchoolOS.exe --reset             wipe the database, then start
    VintaSchoolOS.exe --no-browser        start without opening a browser
    VintaSchoolOS.exe --port 5055         start on a specific port
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 5000
# If 5000 is taken (a stale instance, or another app), walk upward rather than
# failing: the reviewer should never see a port error.
PORT_SCAN_LIMIT = 12

BANNER_WIDTH = 66


def install_dir() -> Path:
    """
    The folder the reviewer sees — the one holding the .exe.

    This is where `data/` is created. It must be writable and must survive
    restarts, so it cannot live inside the PyInstaller bundle.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # Running from source: packaging/ sits one level below the project root.
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    """Read-only resources bundled into the executable (the built frontend)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def resolve_web_dir(override: str | None) -> Path:
    """Locate the built frontend (index.html + assets/)."""
    candidates = []
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(bundle_dir() / "web")

    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate.resolve()

    raise SystemExit(
        "Could not find the built frontend (expected a folder containing "
        "index.html).\nLooked in:\n"
        + "\n".join(f"  - {c}" for c in candidates)
        + "\n\nRun the build script to produce it, or pass --web-dir."
    )


def load_or_create_secrets(data_dir: Path) -> dict:
    """
    Reuse one signing key pair across runs, generating it on first launch.

    Persisting matters: JWTs are signed with JWT_SECRET_KEY, so regenerating it
    every start would silently invalidate the reviewer's session and log him out
    mid-review. It also keeps the build self-contained — no shared secret and no
    production credential is shipped inside it.
    """
    secrets_path = data_dir / "instance-secrets.json"
    if secrets_path.is_file():
        try:
            stored = json.loads(secrets_path.read_text(encoding="utf-8"))
            if stored.get("SECRET_KEY") and stored.get("JWT_SECRET_KEY"):
                return stored
        except (OSError, ValueError):
            # Unreadable or corrupt: fall through and mint a fresh pair.
            pass

    generated = {
        "SECRET_KEY": secrets.token_hex(32),
        "JWT_SECRET_KEY": secrets.token_hex(32),
    }
    try:
        secrets_path.write_text(json.dumps(generated, indent=2), encoding="utf-8")
    except OSError as exc:
        # Not fatal — the app runs, the session just will not persist its key.
        print(f"  ! Could not save session keys ({exc}); sessions reset on restart.")
    return generated


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
    Is something already serving Vinta on this port?

    Distinguishes "the reviewer launched it twice" (open a browser tab, leave the
    running copy alone) from "an unrelated program holds port 5000" (use the next
    port instead).
    """
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/health", timeout=1.5) as response:
            return b'"ok"' in response.read(200)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def choose_port(requested: int | None) -> int:
    if requested:
        if not port_is_free(requested):
            raise SystemExit(
                f"Port {requested} is already in use. Close the other program "
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
        "use. Close some programs and try again, or pass --port."
    )


def configure_environment(install: Path, web_dir: Path, db_path: Path, port: int) -> None:
    """Set every variable the app reads, before `app` is imported."""
    os.environ["FLASK_ENV"] = "production"

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    keys = load_or_create_secrets(install / "data")
    os.environ["SECRET_KEY"] = keys["SECRET_KEY"]
    os.environ["JWT_SECRET_KEY"] = keys["JWT_SECRET_KEY"]

    # Same-origin build: the browser never sends a cross-origin request, but
    # CORS is configured anyway so the app behaves identically if the reviewer
    # opens it as "localhost" instead of "127.0.0.1".
    os.environ["CORS_ORIGINS"] = (
        f"http://{HOST}:{port},http://localhost:{port}"
    )

    # See app/__init__.py: eventlet's monkey-patching is unreliable inside a
    # PyInstaller bundle, and the frontend opens no Socket.IO connection.
    os.environ["SOCKETIO_ASYNC_MODE"] = "threading"

    os.environ["VINTA_WEB_DIR"] = str(web_dir)


def prepare_database(app, db_path: Path, reset: bool) -> bool:
    """
    Create the schema on first run, or rebuild it after --reset.

    `migrations/versions/` in this repository is empty, so `flask db upgrade` has
    nothing to apply and the schema is created from the models instead.
    """
    from app.extensions import db

    created = False
    if reset and db_path.exists():
        db_path.unlink()

    if not db_path.exists():
        created = True

    with app.app_context():
        db.create_all()
    return created


def print_banner(url: str, db_path: Path, created: bool) -> None:
    line = "=" * BANNER_WIDTH
    print(line)
    print("  Vinta School OS — Review Build".center(BANNER_WIDTH))
    print(line)
    print()
    print(f"  The app is running at:  {url}")
    print()
    print("  A browser window should have opened automatically.")
    print("  If it did not, copy the address above into your browser.")
    print()
    if created:
        print("  This is a fresh start — there is no data yet.")
        print("  Create your academy with 'Sign up' on the login screen.")
        print()
    print(f"  Your data is stored in: {db_path.parent}")
    print("  Nothing is sent anywhere; it all stays on this computer.")
    print()
    print("  " + "-" * (BANNER_WIDTH - 4))
    print("  KEEP THIS WINDOW OPEN WHILE YOU USE THE APP.")
    print("  Closing it (or pressing Ctrl+C) stops the app.")
    print("  " + "-" * (BANNER_WIDTH - 4))
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="VintaSchoolOS",
        description="Launch the Vinta School OS review build.",
    )
    parser.add_argument("--reset", action="store_true",
                        help="delete the stored data and start from empty")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open a browser window")
    parser.add_argument("--port", type=int, default=None,
                        help=f"port to listen on (default {DEFAULT_PORT})")
    parser.add_argument("--web-dir", default=None,
                        help="path to a built frontend (for running from source)")
    args = parser.parse_args(argv)

    install = install_dir()
    web_dir = resolve_web_dir(args.web_dir)

    data_dir = install / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "vinta_review.db"

    port = choose_port(args.port)
    if port < 0:
        live_port = -port
        url = f"http://{HOST}:{live_port}/"
        print(f"\n  Vinta School OS is already running at {url}")
        if not args.no_browser:
            webbrowser.open(url)
        print("  Use the window that is already open.\n")
        return 0

    configure_environment(install, web_dir, db_path, port)

    # Imported only now: app/config.py snapshots os.environ at import time.
    from app import create_app

    app = create_app("production")
    created = prepare_database(app, db_path, reset=args.reset)

    url = f"http://{HOST}:{port}/"
    print_banner(url, db_path, created)

    from werkzeug.serving import make_server

    server = make_server(HOST, port, app, threaded=True)

    if not args.no_browser:
        # Delayed so the socket is accepting before the browser requests it.
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down — your data has been saved.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
