"""
Vinta OS - uninstaller.

Removes the program, its shortcuts and its Add/Remove Programs entry.

Ships as a ONE-FILE executable that lives inside the install folder, and hands
the job to a copy of itself in %TEMP% whenever that folder is the one it has
been asked to remove.

The copy is not a nicety. Windows locks the image of a running executable, so
this program sitting in the folder it is deleting cannot remove its own file,
and the whole uninstall fails on that one path with an access-denied error.
Unpacking to a temp directory does not help either: the bootloader process is
still the file in the install folder. So the original exits, releasing the
lock, and the copy deletes everything — the original executable included — as
ordinary files.

The academy's records in %APPDATA% are preserved unless they are explicitly
asked for. Deleting a school's students and payment history is not something to
do on a default path, and "reinstall to fix something" must never cost data.

One deliberate cost of the hand-over: the copy in %TEMP% cannot delete its own
running image either, so it leaves itself behind — a single file in the
standard temporary folder, which Windows clears on its own schedule. The
alternative is advertising an uninstall that fails, or asking for administrator
rights to schedule a delete-on-reboot, and neither is worth one orphaned file.

    Uninstall.exe                ask, then uninstall (records kept by default)
    Uninstall.exe --silent       no prompts; records kept
    Uninstall.exe --remove-data  also delete the records folder
    Uninstall.exe --dir PATH     uninstall from PATH instead of beside this file
"""
from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APP_NAME = "Vinta OS"
EXE_NAME = "Vinta OS.exe"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"

MB_OK = 0x0
MB_YESNO = 0x4
MB_ICONERROR = 0x10
MB_ICONINFORMATION = 0x40
MB_ICONWARNING = 0x30
MB_SETFOREGROUND = 0x10000
IDYES = 6

LONG_PATH_THRESHOLD = 200
silent = False


def say(message: str = "") -> None:
    print(message, flush=True)


def fs(path: Path) -> str:
    """Extended-length path form, for the deeply nested frozen Python tree."""
    text = os.path.abspath(str(path))
    if len(text) < LONG_PATH_THRESHOLD or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text[2:]
    return "\\\\?\\" + text


def ask(question: str, title: str) -> bool:
    if silent:
        return False
    try:
        answer = ctypes.windll.user32.MessageBoxW(
            None, question, title, MB_YESNO | MB_ICONWARNING | MB_SETFOREGROUND
        )
        return answer == IDYES
    except Exception:
        return False


def tell(text: str, title: str, flags: int) -> None:
    if silent:
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, flags | MB_SETFOREGROUND)
    except Exception:
        pass


def data_dir() -> Path:
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home()) / APP_NAME


def install_dir(override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def running_image() -> Path | None:
    """
    The executable file Windows has locked, or None when running from source.

    In a one-file build ``sys.executable`` is the program the user launched,
    not the Python interpreter, which is what makes it the file that cannot be
    deleted while this process lives.
    """
    if not getattr(sys, "frozen", False):
        return None
    try:
        return Path(sys.executable).resolve()
    except OSError:
        return None


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def wait_for_exit(pid: int, timeout: float = 60.0) -> None:
    """
    Block until another process has exited.

    The copy in %TEMP% uses this to wait for the original, rather than sleeping
    a guessed interval and then failing a delete that was never going to work.
    A process that has already gone is not an error: ``OpenProcess`` fails and
    there is nothing left to wait for.
    """
    SYNCHRONIZE = 0x00100000
    kernel32 = ctypes.windll.kernel32
    # The handle is a pointer; leaving the default c_int return type would
    # truncate it on 64-bit Windows and wait on a handle we do not own.
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.CloseHandle.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return
    try:
        kernel32.WaitForSingleObject(handle, int(timeout * 1000))
    finally:
        kernel32.CloseHandle(handle)


def hand_over_to_temp_copy(install: Path, args: argparse.Namespace) -> int | None:
    """
    Re-run this uninstaller from a copy outside the folder it must delete.

    Returns the exit code to use, or None when the job can be done in place.

    The copy is started *without* detaching it from this console, so the window
    the user is watching stays alive and keeps narrating the removal after this
    process is gone. Detaching would be worse than the bug it fixes: the user
    would see the window vanish and nothing else.
    """
    image = running_image()
    if image is None or not is_inside(image, install):
        return None

    say("  Restarting outside the folder so it can be removed completely...")
    temp_root = Path(tempfile.mkdtemp(prefix="vinta-uninstall-"))
    copy = temp_root / "Uninstall.exe"
    try:
        shutil.copy2(image, copy)
    except OSError as exc:
        say(f"  ! Could not prepare the removal: {exc}")
        return 1

    command = [str(copy), "--dir", str(install), "--parent-pid", str(os.getpid())]
    if args.silent:
        command.append("--silent")
    if args.remove_data:
        command.append("--remove-data")

    try:
        subprocess.Popen(command, cwd=str(temp_root), close_fds=True)
    except OSError as exc:
        say(f"  ! Could not start the removal: {exc}")
        return 1

    # Nothing else may happen here: this process has to end for the copy to be
    # allowed to delete it.
    return 0


def stop_application(install: Path) -> None:
    """
    Stop Vinta OS if it is open, so its files are not locked mid-delete.

    Matched on the executable path rather than the image name alone, so an
    unrelated process that happens to be called "Vinta OS.exe" is left alone.
    """
    exe = install / EXE_NAME
    if not exe.exists():
        return
    say("  Closing Vinta OS if it is running...")
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", EXE_NAME],
            capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    # Give Windows a moment to release the file handles behind the process.
    time.sleep(1.5)


def remove_shortcuts() -> list[str]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import shortcuts
    except Exception:
        return []

    removed: list[str] = []
    for getter in (shortcuts.desktop_dir, shortcuts.start_menu_dir):
        try:
            folder = getter()
        except OSError:
            continue
        link = folder / f"{APP_NAME}.lnk"
        try:
            if link.exists():
                link.unlink()
                removed.append(link.name)
        except OSError:
            pass
    return removed


def remove_registry_entry() -> bool:
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def remove_tree(path: Path, attempts: int = 5) -> tuple[bool, str]:
    """
    Delete a directory, retrying briefly.

    A freshly closed process can hold a file open for a second or two after
    taskkill returns, and a single failed rmtree would otherwise leave a
    half-deleted installation behind.
    """
    last = ""
    for attempt in range(attempts):
        try:
            shutil.rmtree(fs(path))
            return True, ""
        except FileNotFoundError:
            return True, ""
        except OSError as exc:
            last = str(exc)
            time.sleep(0.8 * (attempt + 1))
    return False, last


def main(argv: list[str] | None = None) -> int:
    global silent

    parser = argparse.ArgumentParser(prog="Uninstall", description="Remove Vinta OS.")
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--remove-data", action="store_true",
                        help="also delete the school's records (permanent)")
    parser.add_argument("--dir", default=None, help="install folder to remove")
    parser.add_argument("--parent-pid", type=int, default=None,
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    silent = args.silent

    # Running as the copy in %TEMP%: the original is still holding a lock on the
    # file we are about to delete until it has actually gone, so wait for it
    # rather than retrying a delete that cannot succeed yet.
    if args.parent_pid:
        wait_for_exit(args.parent_pid)

    install = install_dir(args.dir)
    records = data_dir()

    # If this program is itself inside the folder it has been asked to remove,
    # it cannot delete its own file. Hand over to a copy that can, and exit.
    handoff = hand_over_to_temp_copy(install, args)
    if handoff is not None:
        return handoff

    say()
    say("=" * 66)
    say(f"  {APP_NAME} - uninstall".center(66))
    say("=" * 66)
    say()
    say(f"  Program : {install}")
    say(f"  Records : {records}")
    say()

    if not silent:
        answer = ctypes.windll.user32.MessageBoxW(
            None,
            f"Remove {APP_NAME} from this computer?\n\n"
            f"Your school's records in:\n{records}\n\n"
            "will be KEPT, so you can reinstall later without losing anything.",
            f"{APP_NAME} - uninstall",
            MB_YESNO | MB_ICONWARNING | MB_SETFOREGROUND,
        )
        if answer != IDYES:
            say("  Cancelled. Nothing was removed.")
            return 0

    stop_application(install)

    removed_links = remove_shortcuts()
    say(f"  Shortcuts removed: {len(removed_links)}")

    if remove_registry_entry():
        say("  Removed from Add/Remove Programs.")

    say("  Deleting the program files...")
    ok, error = remove_tree(install)
    if not ok:
        message = (
            f"Some files could not be deleted:\n\n{error}\n\n"
            f"Close {APP_NAME} and any open Explorer window showing the folder, "
            "then try again."
        )
        say(f"  ! {message}")
        tell(message, f"{APP_NAME} - uninstall", MB_ICONERROR | MB_OK)
        return 1
    say("  Program files deleted.")

    # Records are destroyed only when explicitly requested, never as a side
    # effect of a repair or a reinstall.
    delete_records = args.remove_data
    if not delete_records and not silent:
        delete_records = ask(
            "Also delete your school's records?\n\n"
            f"{records}\n\n"
            "This is permanent. Choose No to keep them.",
            f"{APP_NAME} - records",
        )

    if delete_records:
        say("  Deleting your school's records...")
        ok, error = remove_tree(records)
        say("  Records deleted." if ok else f"  ! Could not delete records: {error}")
        records_note = "Your school's records have been deleted." if ok else \
            "The records folder could not be deleted."
    else:
        records_note = f"Your school's records were kept in:\n{records}"

    say()
    say("=" * 66)
    say(f"  {APP_NAME} has been uninstalled".center(66))
    say("=" * 66)
    say()

    tell(
        f"{APP_NAME} has been removed from this computer.\n\n{records_note}",
        f"{APP_NAME} - uninstalled",
        MB_ICONINFORMATION | MB_OK,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
