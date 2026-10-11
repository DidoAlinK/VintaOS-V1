"""
Build the Vinta OS USB kit.

Everything that has to be true is made true here, once, on a machine that has
the toolchain -- so that the install performed at the school is a file copy
with no build steps, no compiler, no Node, and no internet.

Pipeline:
    1. Draw the application icon.
    2. Build the frontend (Vite) with a relative API path.
    3. Make the fonts self-contained, so the app looks designed offline.
    4. Freeze backend + frontend into "Vinta OS.exe".
    5. Build the uninstaller and drop it inside the application folder.
    6. Build Setup.exe.
    7. Assemble the USB folder.

Usage:
    python usb-kit/build_usb.py
    python usb-kit/build_usb.py --skip-frontend      reuse an existing dist/
    python usb-kit/build_usb.py --skip-app           reuse the frozen app
    python usb-kit/build_usb.py --skip-icon

Run it with the build virtualenv (usb-kit/.buildenv), which is the interpreter
that has both the application's dependencies and PyInstaller:
    usb-kit/.buildenv/Scripts/python.exe usb-kit/build_usb.py
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BUILD = Path(__file__).resolve().parent
PROJECT = BUILD.parent
BACKEND = PROJECT / "Backend" / "vinta-academy-backend"
FRONTEND = PROJECT / "vinta-school-os"
FRONTEND_DIST = FRONTEND / "dist"

OUT = BUILD / "out"
APP_DIST = OUT / "app"           # PyInstaller distpath for the application
BIN_DIST = OUT / "bin"           # PyInstaller distpath for Setup/Uninstall
WORK = OUT / "_work"             # PyInstaller scratch
USB = OUT / "USB"                # the folder to copy onto the stick

APP_FOLDER = "Vinta OS"
EXE_NAME = "Vinta OS.exe"


def log(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def warn(message: str) -> None:
    print(f"  ! {message}", flush=True)


def run(args: list[str], cwd: Path, *, label: str, env: dict | None = None) -> int:
    """Run a program directly (no shell), so spaces in paths stay intact."""
    print(f"  $ {' '.join(str(a) for a in args)}", flush=True)
    completed = subprocess.run(
        [str(a) for a in args], cwd=str(cwd), env=env
    )
    if completed.returncode != 0:
        warn(f"{label} exited with code {completed.returncode}")
    return completed.returncode


def run_shell(command: str, cwd: Path, *, label: str, env: dict | None = None) -> int:
    """
    Run a shell command line.

    Needed for npm/npx, which on Windows are .cmd shims rather than executables
    and so cannot be launched by name without a shell.
    """
    print(f"  $ {command}", flush=True)
    completed = subprocess.run(command, cwd=str(cwd), shell=True, env=env)
    if completed.returncode != 0:
        warn(f"{label} exited with code {completed.returncode}")
    return completed.returncode


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------
def step_icon() -> None:
    log("Icon: drawing the application mark")
    code = run(
        [sys.executable, BUILD / "make_icon.py", "--out", BUILD / "assets" / "vinta.ico"],
        PROJECT, label="make_icon",
    )
    if code != 0:
        warn("The icon could not be generated; the build will use the default.")


def step_frontend(skip: bool) -> None:
    log("Frontend: building the user interface")

    if skip:
        if not (FRONTEND_DIST / "index.html").is_file():
            raise SystemExit("--skip-frontend was given but dist/index.html is missing.")
        print("  Reusing the existing dist/ build.")
        return

    if not (FRONTEND / "node_modules").is_dir():
        log("Frontend: installing dependencies (first run; this takes a while)")
        if run_shell("npm install", FRONTEND, label="npm install") != 0:
            raise SystemExit("npm install failed.")

    env = os.environ.copy()
    # Vite bakes VITE_API_URL into the bundle at build time. '/api' keeps every
    # request relative, so the app follows whatever port Flask ends up on --
    # see choose_port() in launcher_os.py.
    env["VITE_API_URL"] = "/api"
    print("  VITE_API_URL=/api", flush=True)

    # `npm run build` is `tsc -b && vite build`, so a single type error aborts
    # the whole packaging run. The JavaScript bundle is what actually ships, so
    # fall back to vite alone and say so loudly rather than producing nothing.
    if run_shell("npm run build", FRONTEND, label="npm run build", env=env) == 0:
        pass
    else:
        warn("`npm run build` failed (usually a TypeScript error).")
        warn("Retrying with `npx vite build` to skip type-checking...")
        if run_shell("npx vite build", FRONTEND, label="vite build", env=env) != 0:
            raise SystemExit(
                "The frontend build failed. Run `npm run build` in "
                "vinta-school-os/ to see the errors in full."
            )
        warn("Built WITHOUT type-checking -- run a clean `npm run build` before "
             "shipping if this kit is going to a customer.")

    if not (FRONTEND_DIST / "index.html").is_file():
        raise SystemExit("The frontend build produced no dist/index.html.")


def step_fonts() -> None:
    log("Fonts: making the app self-contained and offline-correct")
    if run(
        [sys.executable, BUILD.parent / "packaging" / "selfhost_fonts.py",
         "--dist", FRONTEND_DIST],
        PROJECT, label="selfhost_fonts",
    ) != 0:
        warn("Font bundling did not complete -- the app will fall back to "
             "system fonts, and will look different from the design.")


def step_freeze(skip: bool) -> Path:
    log("Application: freezing to an executable")

    built = APP_DIST / APP_FOLDER
    if skip:
        if not (built / EXE_NAME).is_file():
            raise SystemExit(f"--skip-app was given but {built / EXE_NAME} is missing.")
        print("  Reusing the existing executable.")
        return built

    if APP_DIST.exists():
        shutil.rmtree(APP_DIST)

    code = run(
        [sys.executable, "-m", "PyInstaller", BUILD / "vinta_os.spec",
         "--noconfirm", "--clean",
         "--distpath", APP_DIST, "--workpath", WORK / "app"],
        PROJECT, label="PyInstaller (app)",
    )
    if code != 0:
        raise SystemExit(
            "PyInstaller failed. A missing hidden import is the usual cause: the "
            "traceback above names the module, and vinta_os.spec derives most of "
            "them from the source, so check for a new dependency first."
        )
    if not (built / EXE_NAME).is_file():
        raise SystemExit(f"Expected {built / EXE_NAME} to exist after the build.")
    return built


def step_uninstaller(app_built: Path) -> None:
    log("Uninstaller: building")
    code = run(
        [sys.executable, "-m", "PyInstaller", BUILD / "uninstall.spec",
         "--noconfirm", "--clean",
         "--distpath", BIN_DIST, "--workpath", WORK / "uninstall"],
        PROJECT, label="PyInstaller (uninstall)",
    )
    if code != 0:
        raise SystemExit("Building the uninstaller failed.")

    built = BIN_DIST / "Uninstall.exe"
    if not built.is_file():
        raise SystemExit(f"Expected {built} to exist.")

    # It lives inside the application folder, so Setup copies it into place and
    # it lands in the same directory as the program it removes.
    shutil.copy2(built, app_built / "Uninstall.exe")
    print(f"  Placed Uninstall.exe beside {EXE_NAME}.")


def step_setup() -> Path:
    log("Installer: building Setup.exe")
    code = run(
        [sys.executable, "-m", "PyInstaller", BUILD / "setup.spec",
         "--noconfirm", "--clean",
         "--distpath", BIN_DIST, "--workpath", WORK / "setup"],
        PROJECT, label="PyInstaller (setup)",
    )
    if code != 0:
        raise SystemExit("Building Setup.exe failed.")

    built = BIN_DIST / "Setup.exe"
    if not built.is_file():
        raise SystemExit(f"Expected {built} to exist.")
    return built


def step_assemble(app_built: Path, setup_exe: Path) -> Path:
    log("Assembling the USB kit")

    if USB.exists():
        shutil.rmtree(USB)
    USB.mkdir(parents=True)

    shutil.copy2(setup_exe, USB / "Setup.exe")

    destination = USB / APP_FOLDER
    shutil.copytree(app_built, destination)

    readme = BUILD / "README-USB.txt"
    if readme.is_file():
        shutil.copy2(readme, USB / "README.txt")

    return USB


def step_smoke_test(app_built: Path) -> None:
    """
    Prove the frozen application starts and answers before it is shipped.

    A frozen Python app can build cleanly and still die on launch from a missing
    module, which is exactly the failure that would otherwise be discovered in
    front of a customer. Running it here costs seconds.
    """
    log("Smoke test: does the frozen application actually run?")

    scratch = OUT / "_smoke"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)

    exe = app_built / EXE_NAME
    code = run(
        [exe, "--init-db", "--data-dir", scratch],
        app_built, label="init-db",
    )
    database = scratch / "vinta.db"
    if code != 0 or not database.is_file():
        raise SystemExit(
            "The frozen application could not create its database. Do not ship "
            "this kit -- see the output above."
        )
    print(f"  Database created: {database} "
          f"({database.stat().st_size / 1024:.0f} KB)")

    # Serve it and ask the API whether it is alive.
    import json
    import socket
    import threading
    import urllib.request

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    process = subprocess.Popen(
        [str(exe), "--no-browser", "--port", str(port), "--data-dir", str(scratch)],
        cwd=str(app_built),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        health = f"http://127.0.0.1:{port}/api/health"
        deadline = time.time() + 60
        alive = False
        while time.time() < deadline:
            if process.poll() is not None:
                break
            try:
                with urllib.request.urlopen(health, timeout=2) as response:
                    if json.loads(response.read().decode()) == {"status": "ok"}:
                        alive = True
                        break
            except Exception:
                time.sleep(0.5)

        if not alive:
            output = ""
            if process.poll() is not None:
                output = (process.stdout.read() if process.stdout else "") or ""
            raise SystemExit(
                "The frozen application did not answer on /api/health.\n"
                f"{output[-2000:]}"
            )
        print("  API is up (/api/health -> ok)")

        # The UI must be served from the same origin, not just the API.
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as response:
            page = response.read().decode("utf-8", "replace")
        if "root" not in page:
            raise SystemExit("The frontend was not served at /.")
        print("  Frontend is served at /")

        # A deep link must return the app shell, or a refresh inside the app
        # would 404 for the user.
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/app/dashboard", timeout=10) as response:
            deep = response.read().decode("utf-8", "replace")
        if "root" not in deep:
            raise SystemExit("A deep link did not return the app shell.")
        print("  Deep links resolve (history-API fallback works)")

    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()

    shutil.rmtree(scratch, ignore_errors=True)


# --------------------------------------------------------------------------
def report(usb: Path) -> None:
    def folder_size(path: Path) -> tuple[int, int]:
        files = [f for f in path.rglob("*") if f.is_file()]
        return sum(f.stat().st_size for f in files), len(files)

    total, count = folder_size(usb)
    setup_size = (usb / "Setup.exe").stat().st_size

    log("Done")
    print(f"  USB kit : {usb}")
    print(f"  Files   : {count}")
    print(f"  Size    : {total / 1024 / 1024:.1f} MB")
    print(f"    Setup.exe        {setup_size / 1024 / 1024:.1f} MB")
    print()
    print("  Copy the ENTIRE contents of that folder onto the USB stick.")
    print("  At the school: open the stick, run Setup.exe, then double-click")
    print(f'  "Vinta OS" on the Desktop.')
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-frontend", action="store_true",
                        help="reuse the existing frontend dist/")
    parser.add_argument("--skip-app", action="store_true",
                        help="reuse the existing frozen application")
    parser.add_argument("--skip-icon", action="store_true")
    parser.add_argument("--skip-smoke-test", action="store_true")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    print("Vinta OS -- USB kit build")
    print(f"  Project : {PROJECT}")
    print(f"  Python  : {sys.version.split()[0]}  ({sys.executable})")
    print(f"  Output  : {USB}")

    if not args.skip_icon:
        step_icon()
    step_frontend(args.skip_frontend)
    step_fonts()
    app_built = step_freeze(args.skip_app)
    step_uninstaller(app_built)
    setup_exe = step_setup()

    if not args.skip_smoke_test:
        step_smoke_test(app_built)

    usb = step_assemble(app_built, setup_exe)
    report(usb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
