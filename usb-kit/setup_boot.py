"""
Vinta OS - installer.

Copies the prepared application from the USB stick onto this computer, creates
the academy's data folder under %APPDATA%, builds the empty database, and puts
a Vinta OS shortcut on the Desktop and in the Start Menu.

No internet is used and no administrator rights are needed: everything is
written inside the current user's own profile, so this works from a standard
school account.

Layout on the USB stick:
    Setup.exe            <- the operator double-clicks this
    Vinta OS\\            <- the application itself (Vinta OS.exe + _internal)
    README.txt

Layout after installing:
    %LOCALAPPDATA%\\Vinta OS\\      the program
    %APPDATA%\\Vinta OS\\           the school's records (never touched again)

The program folder and the data folder are deliberately separate. Reinstalling
an update replaces the program folder completely; if the database lived inside
it, updating would wipe every student record the school owns.

Usage:
    Setup.exe                  install (recommended)
    Setup.exe --dir PATH       install somewhere other than %LOCALAPPDATA%
    Setup.exe --data-dir PATH  keep the database somewhere else
    Setup.exe --no-shortcuts   skip the Desktop/Start Menu shortcuts
    Setup.exe --no-registry    do not add an Add/Remove Programs entry
    Setup.exe --silent         no messages, no prompts (for scripted testing)
"""
from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shortcuts  # noqa: E402

APP_NAME = "Vinta OS"
APP_VERSION = "1.6.3"
PUBLISHER = "Vinta Automation"
APP_DESCRIPTION = "Vinta OS - school management system"
EXE_NAME = "Vinta OS.exe"

UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"

#: Folder names the payload might use on the stick, best guess first.
PAYLOAD_NAMES = ("Vinta OS", "payload", "app")

MB_OK = 0x0
MB_ICONERROR = 0x10
MB_ICONINFORMATION = 0x40
MB_ICONWARNING = 0x30
MB_SETFOREGROUND = 0x10000

#: Paths longer than this get the Windows extended-length prefix, because the
#: frozen Python tree nests deeply and a long user name can otherwise push a
#: file past the 260-character limit mid-copy.
LONG_PATH_THRESHOLD = 200

silent = False


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def say(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "-") -> None:
    say(char * 66)


def message_box(text: str, title: str, flags: int) -> None:
    if silent:
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, flags | MB_SETFOREGROUND)
    except Exception:
        pass


def fail(message: str, code: int = 1) -> int:
    say()
    say("  INSTALLATION FAILED")
    rule()
    for line in message.splitlines():
        say(f"  {line}")
    say()
    message_box(message, f"{APP_NAME} - installation failed", MB_ICONERROR | MB_OK)
    return code


# --------------------------------------------------------------------------
# Filesystem helpers
# --------------------------------------------------------------------------
def fs(path: Path) -> str:
    """
    A path string the Win32 file APIs will accept even when it is very long.

    The ``\\\\?\\`` prefix opts out of MAX_PATH normalisation. It requires an
    absolute, backslash-only path, so both are enforced here.
    """
    text = os.path.abspath(str(path))
    if len(text) < LONG_PATH_THRESHOLD or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text[2:]
    return "\\\\?\\" + text


def exe_dir() -> Path:
    """The folder the operator launched Setup.exe from (usually the USB)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_payload() -> Path | None:
    """
    Locate the application files to install.

    Searched beside the executable first, so the operator can replace the app
    on the stick without rebuilding the installer.
    """
    candidates: list[Path] = [exe_dir() / name for name in PAYLOAD_NAMES]
    # Embedded fallback, should the build ever pack the payload inside.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates += [Path(meipass) / name for name in ("payload",) + PAYLOAD_NAMES]

    for candidate in candidates:
        if (candidate / EXE_NAME).is_file():
            return candidate
    return None


def is_locked(path: Path) -> bool:
    """
    Is this file open for writing by another process?

    A running executable cannot be opened for append, which is how a second run
    of Setup detects that Vinta OS is still open. Checking beats guessing: the
    alternative is a copy that fails halfway through with a permission error.
    """
    if not path.exists():
        return False
    try:
        with open(fs(path), "a"):
            return False
    except PermissionError:
        return True
    except OSError:
        return False


def copy_application(source: Path, target: Path) -> int:
    """
    Copy the application into place, replacing any previous copy.

    The target is emptied first rather than overwritten in place. A frozen
    Python build ships thousands of files, and mixing an old ``_internal`` with
    a new one produces DLL mismatches that fail at launch with no useful error.
    """
    files = [p for p in source.rglob("*") if p.is_file()]
    total = len(files)
    if total == 0:
        raise RuntimeError(f"No files found to install in {source}")

    if target.exists():
        say(f"  Removing the previous installation...")
        shutil.rmtree(fs(target), ignore_errors=True)
    os.makedirs(fs(target), exist_ok=True)

    say(f"  Copying {total} files...")
    done = 0
    started = time.time()
    for item in files:
        destination = target / item.relative_to(source)
        os.makedirs(fs(destination.parent), exist_ok=True)
        shutil.copy2(fs(item), fs(destination))
        done += 1
        if done % 100 == 0 or done == total:
            elapsed = max(time.time() - started, 0.001)
            say(f"    {done}/{total}  ({done / elapsed:.0f} files/s)")
    return total


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
def register_uninstaller(target: Path) -> bool:
    """
    Add an entry to the user's own Add/Remove Programs list.

    Written under HKCU so it appears without administrator rights; a machine-wide
    HKLM entry would need elevation this installer deliberately avoids.
    """
    import winreg

    exe = target / EXE_NAME
    uninstaller = target / "Uninstall.exe"

    if not uninstaller.is_file():
        # Never advertise an uninstall that cannot run. This entry is what a
        # school's IT person reaches for, and an entry that fails — or worse,
        # that launches the program instead of removing it — is harder to
        # explain than a missing entry. Setup always copies the uninstaller in,
        # so this only happens if the package was assembled wrongly.
        say("  ! Uninstall.exe is missing; not adding an Add/Remove Programs entry.")
        return False

    command = f'"{uninstaller}"'

    try:
        size_kb = sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) // 1024
    except OSError:
        size_kb = 0

    values = {
        "DisplayName": APP_NAME,
        "DisplayVersion": APP_VERSION,
        "Publisher": PUBLISHER,
        "InstallLocation": str(target),
        "DisplayIcon": str(exe),
        # No --dir: the uninstaller defaults to the folder it is running from,
        # which is this one.
        "UninstallString": command,
        "QuietUninstallString": f"{command} --silent",
        "NoModify": 1,
        "NoRepair": 1,
        "EstimatedSize": size_kb,
    }

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            for name, value in values.items():
                kind = winreg.REG_DWORD if isinstance(value, int) else winreg.REG_SZ
                winreg.SetValueEx(key, name, 0, kind, value)
        return True
    except OSError:
        return False


def resolve_data_dir(override: str | None) -> Path:
    """
    Where the school's records will live — the same answer the application gives.

    Deliberately mirrors the application's own precedence (its ``--data-dir``,
    then ``VINTA_DATA_DIR``, then ``%APPDATA%\\Vinta OS``) instead of deriving a
    path of its own. Two independent guesses that drift apart fail quietly: the
    installer prepares a database in a folder nothing ever opens, and tells the
    user to protect the wrong one. A school only finds out when it comes to
    restoring a backup.
    """
    if override:
        return Path(override).expanduser()
    from_environment = os.environ.get("VINTA_DATA_DIR")
    if from_environment:
        return Path(from_environment).expanduser()
    return shortcuts.data_dir(APP_NAME)


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
def initialise_database(target: Path, data_dir: Path) -> tuple[bool, str]:
    """
    Create the empty database in the data folder before the app is first opened.

    Run through the application itself (``--init-db``) rather than by importing
    its models, so the schema is built by exactly the code that will later use
    it. A failure here is not fatal: the app creates the database on first launch
    anyway, it just means the folder is not pre-warmed.

    The folder is always passed explicitly. The application would derive the
    same one on its own, but passing it means the database is prepared in the
    exact folder this installer has just printed on screen and told the user to
    keep safe — the two cannot drift apart later without this failing loudly.
    """
    exe = target / EXE_NAME
    command = [str(exe), "--init-db", "--data-dir", str(data_dir)]

    environment = os.environ.copy()
    # The child prints an em dash; force UTF-8 so a legacy code page on a school
    # machine cannot turn its output into an encoding error.
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=300,
            env=environment, cwd=str(target),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"could not run the application: {exc}"

    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        tail = "\n".join(output.strip().splitlines()[-6:])
        return False, f"exit code {result.returncode}\n{tail}"
    return True, output.strip()


# --------------------------------------------------------------------------
# Shortcuts
# --------------------------------------------------------------------------
def create_shortcuts(target: Path) -> tuple[list[str], list[str]]:
    """Put Vinta OS on the Desktop and in the Start Menu. Returns (made, failed)."""
    exe = target / EXE_NAME
    icon = exe if exe.is_file() else None

    destinations: list[tuple[str, Path]] = []
    try:
        destinations.append(("Desktop", shortcuts.desktop_dir() / f"{APP_NAME}.lnk"))
    except OSError:
        pass
    try:
        destinations.append(("Start Menu", shortcuts.start_menu_dir() / f"{APP_NAME}.lnk"))
    except OSError:
        pass

    made: list[str] = []
    failed: list[str] = []
    for label, link in destinations:
        try:
            shortcuts.create_shortcut(
                link, exe,
                working_dir=target,
                icon=icon,
                description=APP_DESCRIPTION,
            )
            made.append(label)
        except OSError as exc:
            failed.append(f"{label} ({exc})")
    return made, failed


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    global silent

    parser = argparse.ArgumentParser(prog="Setup", description="Install Vinta OS.")
    parser.add_argument("--dir", default=None,
                        help="install location (default %%LOCALAPPDATA%%\\Vinta OS)")
    parser.add_argument("--data-dir", default=None,
                        help="data location (default %%APPDATA%%\\Vinta OS)")
    parser.add_argument("--no-shortcuts", action="store_true")
    parser.add_argument("--no-registry", action="store_true")
    parser.add_argument("--silent", action="store_true")
    args = parser.parse_args(argv)
    silent = args.silent

    say()
    rule("=")
    say(f"  {APP_NAME} {APP_VERSION} - installation".center(66))
    say(f"  {PUBLISHER}".center(66))
    rule("=")
    say()

    # --- locate the application on the stick ------------------------------
    payload = find_payload()
    if payload is None:
        return fail(
            "Setup could not find the Vinta OS application files.\n\n"
            "The folder \"Vinta OS\" must sit next to Setup.exe. Copy the entire\n"
            "contents of the USB stick to this computer, then run Setup.exe again.\n\n"
            f"Looked in: {exe_dir()}"
        )
    say(f"  Application : {payload}")

    # --- decide where everything goes -------------------------------------
    target = (
        Path(args.dir).expanduser()
        if args.dir else shortcuts.local_app_data(APP_NAME)
    )
    data_dir = resolve_data_dir(args.data_dir)
    say(f"  Install to  : {target}")
    say(f"  Records in  : {data_dir}")
    say()

    # --- refuse to fight a running copy -----------------------------------
    running_exe = target / EXE_NAME
    if is_locked(running_exe):
        return fail(
            f"{APP_NAME} is currently running on this computer.\n\n"
            "Please close the Vinta OS window first, then run Setup again.\n\n"
            "(Your records are not affected. Only the program is replaced.)"
        )

    # --- can we write there? ----------------------------------------------
    try:
        os.makedirs(fs(target), exist_ok=True)
        probe = target / ".vinta-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return fail(
            f"Cannot write to:\n  {target}\n\nReason: {exc}\n\n"
            "If this computer is managed by an IT department, ask them to allow\n"
            "this folder, or install with:  Setup.exe --dir C:\\Vinta OS"
        )

    # --- copy -------------------------------------------------------------
    try:
        count = copy_application(payload, target)
    except (OSError, RuntimeError) as exc:
        return fail(f"Copying the application failed:\n\n{exc}")
    say(f"  Installed {count} files.")
    say()

    installed_exe = target / EXE_NAME
    if not installed_exe.is_file():
        return fail(f"The installation is incomplete: {installed_exe} is missing.")

    # --- data folder + empty database -------------------------------------
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return fail(f"Could not create the records folder:\n  {data_dir}\n\n{exc}")

    say("  Preparing the database...")
    ok, detail = initialise_database(target, data_dir)
    if ok:
        for line in detail.splitlines():
            if line.strip():
                say(f"    {line.strip()}")
    else:
        say("  ! The database could not be prepared in advance:")
        for line in detail.splitlines():
            say(f"      {line}")
        say("  ! This is not fatal - it will be created the first time the app opens.")

    # --- shortcuts --------------------------------------------------------
    made: list[str] = []
    failed: list[str] = []
    if not args.no_shortcuts:
        say()
        say("  Creating shortcuts...")
        made, failed = create_shortcuts(target)
        for label in made:
            say(f"    {label}: created")
        for item in failed:
            say(f"    ! could not create: {item}")

    # --- Add/Remove Programs ----------------------------------------------
    if not args.no_registry:
        if register_uninstaller(target):
            say("  Added to Add/Remove Programs.")
        else:
            say("  ! Could not add an Add/Remove Programs entry (not fatal).")

    # --- done -------------------------------------------------------------
    say()
    rule("=")
    say(f"  {APP_NAME} is installed".center(66))
    rule("=")
    say()
    say("  To start it, double-click the Vinta OS icon on the Desktop.")
    say("  (Or open it from the Start Menu.)")
    say()
    say(f"  Your records will be kept in:")
    say(f"      {data_dir}")
    say()
    say("  Keep that folder safe - it is the school's entire database.")
    say()

    if not args.silent:
        lines = [
            f"{APP_NAME} has been installed on this computer.",
            "",
            "To start it, double-click the Vinta OS icon on the Desktop.",
            "",
            "Your records are kept in:",
            data_dir,
        ]
        if failed:
            lines += ["", "Note: a shortcut could not be created:", *failed]
        message_box("\n".join(lines), f"{APP_NAME} - installed", MB_ICONINFORMATION | MB_OK)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
