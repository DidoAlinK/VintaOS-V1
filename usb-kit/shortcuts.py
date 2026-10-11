"""
Windows shortcut (.lnk) creation through COM, with no third-party dependency.

The obvious way to make a shortcut is to shell out to PowerShell and let
WScript.Shell do it. That fails on exactly the machines this installer is built
for: a school PC with an execution policy or an AppLocker rule that refuses to
run a script. Calling the same COM object directly from Python sidesteps the
policy question entirely — there is no script to block.

The .lnk format itself is a structured binary with a documented-but-fiddly
layout; writing it by hand is far more brittle than driving the shell's own
implementation through IShellLinkW and IPersistFile.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

ole32 = ctypes.windll.ole32
kernel32 = ctypes.windll.kernel32

CLSCTX_INPROC_SERVER = 0x1
HRESULT = ctypes.c_long

CLSID_SHELLLINK = "{00021401-0000-0000-C000-000000000046}"
IID_ISHELLLINKW = "{000214F9-0000-0000-C000-000000000046}"
IID_IPERSISTFILE = "{0000010b-0000-0000-C000-000000000046}"

# IShellLinkW methods, in vtable order, after the three IUnknown slots.
_SL_SET_DESCRIPTION = 7
_SL_SET_WORKING_DIR = 9
_SL_SET_ARGUMENTS = 11
_SL_SET_SHOW_CMD = 15
_SL_SET_ICON_LOCATION = 17
_SL_SET_PATH = 20

# IPersistFile methods, likewise.
_PF_SAVE = 6

SW_SHOWNORMAL = 1


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> GUID:
    result = GUID()
    if ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(result)) != 0:
        raise OSError(f"Could not parse GUID {text}")
    return result


def _vtable_call(pointer: ctypes.c_void_p, index: int, restype, *argtypes):
    """Bind one method out of a COM object's vtable."""
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return prototype(table[index])


def _check(hr: int, what: str) -> None:
    if hr != 0:
        raise OSError(f"{what} failed (HRESULT 0x{hr & 0xFFFFFFFF:08X})")


def create_shortcut(
    link_path: Path,
    target: Path,
    *,
    arguments: str = "",
    working_dir: Path | None = None,
    icon: Path | None = None,
    description: str = "",
) -> None:
    """
    Write a .lnk at ``link_path`` pointing at ``target``.

    Raises OSError if the shell refuses, so callers can report a real reason
    rather than leaving the user with a silently missing desktop icon.
    """
    ole32.CoInitialize(None)
    shell_link = ctypes.c_void_p()
    persist_file = ctypes.c_void_p()
    try:
        clsid = _guid(CLSID_SHELLLINK)
        iid = _guid(IID_ISHELLLINKW)
        _check(
            ole32.CoCreateInstance(
                ctypes.byref(clsid), None, CLSCTX_INPROC_SERVER,
                ctypes.byref(iid), ctypes.byref(shell_link),
            ),
            "CoCreateInstance(ShellLink)",
        )

        set_path = _vtable_call(
            shell_link, _SL_SET_PATH, HRESULT, ctypes.c_wchar_p, wintypes.DWORD
        )
        _check(set_path(shell_link, str(target), 0), "IShellLink::SetPath")

        if working_dir is not None:
            set_dir = _vtable_call(shell_link, _SL_SET_WORKING_DIR, HRESULT, ctypes.c_wchar_p)
            _check(set_dir(shell_link, str(working_dir)), "IShellLink::SetWorkingDirectory")

        if arguments:
            # SetArguments is slot 11; bound here rather than above so the
            # common no-arguments case stays a single call.
            set_args = _vtable_call(shell_link, _SL_SET_ARGUMENTS, HRESULT, ctypes.c_wchar_p)
            _check(set_args(shell_link, arguments), "IShellLink::SetArguments")

        if description:
            set_desc = _vtable_call(shell_link, _SL_SET_DESCRIPTION, HRESULT, ctypes.c_wchar_p)
            _check(set_desc(shell_link, description), "IShellLink::SetDescription")

        set_show = _vtable_call(shell_link, _SL_SET_SHOW_CMD, HRESULT, ctypes.c_int)
        _check(set_show(shell_link, SW_SHOWNORMAL), "IShellLink::SetShowCmd")

        if icon is not None:
            set_icon = _vtable_call(
                shell_link, _SL_SET_ICON_LOCATION, HRESULT, ctypes.c_wchar_p, ctypes.c_int
            )
            _check(set_icon(shell_link, str(icon), 0), "IShellLink::SetIconLocation")

        # The link is written through IPersistFile, which the shell link object
        # also implements.
        query_interface = _vtable_call(
            shell_link, 0, HRESULT, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)
        )
        iid_pf = _guid(IID_IPERSISTFILE)
        _check(
            query_interface(shell_link, ctypes.byref(iid_pf), ctypes.byref(persist_file)),
            "QueryInterface(IPersistFile)",
        )

        save = _vtable_call(persist_file, _PF_SAVE, HRESULT, ctypes.c_wchar_p, ctypes.c_int)
        link_path.parent.mkdir(parents=True, exist_ok=True)
        _check(save(persist_file, str(link_path), 1), "IPersistFile::Save")

    finally:
        # Release in reverse order of acquisition; a leak here would keep the
        # installer process alive and leave the file locked.
        for pointer in (persist_file, shell_link):
            if pointer:
                release = _vtable_call(pointer, 2, ctypes.c_ulong)
                release(pointer)
        ole32.CoUninitialize()


def desktop_dir() -> Path:
    """
    The current user's Desktop.

    Asked of the shell rather than assumed to be ``%USERPROFILE%\\Desktop``: on
    a managed machine the Desktop is regularly redirected into OneDrive or a
    network share, and a shortcut written to the literal path would simply not
    appear.
    """
    return _known_folder("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}")


def start_menu_dir() -> Path:
    """The current user's Start Menu \\ Programs folder."""
    return _known_folder("{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}")


def _known_folder(guid_text: str) -> Path:
    """Resolve one of the shell's KNOWNFOLDERID locations."""
    folder = ctypes.c_wchar_p()
    fol = _guid(guid_text)
    # SHGetKnownFolderPath(REFKNOWNFOLDERID, DWORD, HANDLE, PWSTR*) -> HRESULT
    shell32 = ctypes.windll.shell32
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    shell32.SHGetKnownFolderPath.restype = HRESULT
    hr = shell32.SHGetKnownFolderPath(
        ctypes.byref(fol), 0, None, ctypes.byref(folder)
    )
    if hr != 0 or not folder.value:
        raise OSError(f"Could not locate known folder {guid_text}")
    try:
        return Path(folder.value)
    finally:
        ole32.CoTaskMemFree(folder)


def data_dir(app_name: str) -> Path:
    """%APPDATA%\\<app_name>, the roaming data folder the app writes its DB to."""
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home()) / app_name


def local_app_data(app_name: str) -> Path:
    """%LOCALAPPDATA%\\<app_name>, the default install location."""
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home()) / app_name
