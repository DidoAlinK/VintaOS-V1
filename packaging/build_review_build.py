"""
Build the Vinta School OS offline review build.

Produces a self-contained folder that can be copied to a USB stick and run on a
machine with no Python, no Node, and no internet.

Steps:
  1. Build the frontend (Vite) with VITE_API_URL=/api.
  2. Bundle the webfonts and rewrite the built index.html to use them.
  3. Freeze backend + frontend into VintaSchoolOS.exe with PyInstaller.
  4. Assemble the deliverable folder (exe, README, reset helper).

Usage:
    python packaging/build_review_build.py
    python packaging/build_review_build.py --skip-frontend    reuse existing dist/
    python packaging/build_review_build.py --output D:/builds
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parent
PROJECT = SPEC_DIR.parent
BACKEND = PROJECT / "Backend" / "vinta-academy-backend"
FRONTEND = PROJECT / "vinta-school-os"
FRONTEND_DIST = FRONTEND / "dist"
SPEC_FILE = SPEC_DIR / "vinta_review.spec"

DEFAULT_OUTPUT = PROJECT / "dist-review"
FOLDER_NAME = "Vinta School OS Review Build"
BUILT_NAME = "VintaSchoolOS"


def log(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def warn(message: str) -> None:
    print(f"  ! {message}", flush=True)


def run_direct(args: list[str], cwd: Path, *, label: str) -> int:
    """
    Run an executable directly, without a shell.

    No shell means no re-parsing of the argument list, which matters because
    several of these paths contain spaces ("Vinta School OS Review Build").
    """
    print(f"  $ {' '.join(args)}", flush=True)
    completed = subprocess.run([str(a) for a in args], cwd=str(cwd))
    if completed.returncode != 0:
        warn(f"{label} exited with code {completed.returncode}")
    return completed.returncode


def run_shell(command: str, cwd: Path, *, label: str, env: dict | None = None) -> int:
    """
    Run a shell command line.

    Needed for npm/npx, which on Windows are .cmd shims rather than executables
    and so are not reachable by name without a shell.
    """
    print(f"  $ {command}", flush=True)
    completed = subprocess.run(
        command, cwd=str(cwd), shell=True, env=env
    )
    if completed.returncode != 0:
        warn(f"{label} exited with code {completed.returncode}")
    return completed.returncode


def build_frontend(skip: bool) -> None:
    log("Frontend: building")

    if skip:
        if not (FRONTEND_DIST / "index.html").is_file():
            raise SystemExit("--skip-frontend was passed but dist/index.html does not exist.")
        print("  Reusing the existing dist/ build.")
        return

    if not (FRONTEND / "node_modules").is_dir():
        log("Frontend: installing dependencies (first run, this takes a while)")
        if run_shell("npm install", FRONTEND, label="npm install") != 0:
            raise SystemExit("npm install failed.")

    # Vite bakes VITE_API_URL into the bundle at build time. '/api' makes every
    # request relative, which is what lets the app follow whatever port Flask
    # ends up on — see choose_port() in launcher.py.
    env = os.environ.copy()
    env["VITE_API_URL"] = "/api"
    print("  VITE_API_URL=/api", flush=True)

    # `npm run build` is `tsc -b && vite build`, so one type error in the
    # application code aborts the whole packaging run. The JavaScript bundle is
    # what actually ships, so fall back to vite alone and say so loudly, rather
    # than returning no artifact at all.
    if run_shell("npm run build", FRONTEND, label="npm run build", env=env) == 0:
        return

    warn("`npm run build` failed (this is usually a TypeScript error).")
    warn("Retrying with `npx vite build` to skip type-checking...")
    if run_shell("npx vite build", FRONTEND, label="vite build", env=env) != 0:
        raise SystemExit(
            "Frontend build failed. Fix the errors above, or run "
            "`npm run build` in vinta-school-os/ to see them in full."
        )
    warn("Built WITHOUT type-checking — the bundle may contain latent type "
         "errors. Run `npm run build` yourself before the real launch.")

    if not (FRONTEND_DIST / "index.html").is_file():
        raise SystemExit("Frontend build produced no dist/index.html.")


def bundle_fonts() -> None:
    log("Fonts: bundling for offline use")
    if run_direct(
        [sys.executable, SPEC_DIR / "selfhost_fonts.py", "--dist", FRONTEND_DIST],
        PROJECT,
        label="selfhost_fonts",
    ) != 0:
        warn("Font bundling did not complete — the build will keep the CDN "
             "links and use system fonts offline.")


def freeze(output: Path, skip: bool) -> Path:
    log("Backend: freezing to an executable")

    if skip:
        existing = output / FOLDER_NAME / "VintaSchoolOS.exe"
        if not existing.is_file():
            raise SystemExit(
                "--skip-freeze was passed but no previous build was found at "
                f"{existing}."
            )
        print("  Reusing the existing executable.")
        return existing

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit(
            "PyInstaller is not installed.\n"
            f"Install it with:  {sys.executable} -m pip install pyinstaller"
        )

    code = run_direct(
        [
            sys.executable, "-m", "PyInstaller",
            SPEC_FILE,
            "--noconfirm",
            "--clean",
            "--distpath", output,
            "--workpath", output / "_pyinstaller",
        ],
        PROJECT,
        label="PyInstaller",
    )
    if code != 0:
        raise SystemExit(
            "PyInstaller failed. The usual cause is a missing hidden import — "
            "the traceback above names the module; add it to `hidden` in "
            "packaging/vinta_review.spec and re-run."
        )

    exe = output / BUILT_NAME / "VintaSchoolOS.exe"
    if not exe.is_file():
        raise SystemExit(f"Expected {exe} to exist after the build.")
    return exe


def assemble(output: Path, *, reused: bool) -> Path:
    log("Assembling the deliverable folder")

    final = output / FOLDER_NAME
    built = output / BUILT_NAME

    if reused:
        # Reusing a previous freeze: the assembled folder *is* the deliverable,
        # so it must not be cleared — that would delete the executable we just
        # chose to keep.
        if not final.is_dir():
            raise SystemExit(f"Nothing to reuse: {final} does not exist.")
    else:
        if not built.is_dir():
            raise SystemExit(f"Expected PyInstaller output at {built}.")
        if final.exists():
            shutil.rmtree(final)
        shutil.move(str(built), str(final))

    shutil.copy2(SPEC_DIR / "README-FIRST.txt", final / "README-FIRST.txt")

    (final / "Reset Data.cmd").write_text(
        "@echo off\r\n"
        "cd /d \"%~dp0\"\r\n"
        "echo This deletes everything entered into the review build and\r\n"
        "echo starts again from empty.\r\n"
        "echo.\r\n"
        "pause\r\n"
        "VintaSchoolOS.exe --reset\r\n",
        encoding="utf-8",
    )

    # Shipping a database from an earlier run would defeat the point of a clean
    # review, and could carry the previous tester's data to the next machine.
    data_dir = final / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)

    return final


def report(final: Path) -> None:
    total = sum(f.stat().st_size for f in final.rglob("*") if f.is_file())
    count = sum(1 for f in final.rglob("*") if f.is_file())

    log("Done")
    print(f"  Folder:  {final}")
    print(f"  Files:   {count}")
    print(f"  Size:    {total / 1024 / 1024:.1f} MB")
    print()
    print(f"  Entry point: {final / 'VintaSchoolOS.exe'}")
    print()
    print("  Smoke-test it here before copying to the USB stick:")
    print(f'    "{final / "VintaSchoolOS.exe"}"')
    print()
    print("  Then copy the whole folder to the USB stick.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-frontend", action="store_true",
                        help="reuse the existing frontend dist/")
    parser.add_argument("--skip-freeze", action="store_true",
                        help="reuse the existing executable")
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    print("Vinta School OS — review build")
    print(f"Project: {PROJECT}")
    print(f"Output:  {output}")

    build_frontend(args.skip_frontend)
    bundle_fonts()
    freeze(output, args.skip_freeze)
    final = assemble(output, reused=args.skip_freeze)
    report(final)
    return 0


if __name__ == "__main__":
    sys.exit(main())
