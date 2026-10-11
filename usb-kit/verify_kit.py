"""
End-to-end verification of the built USB kit.

Builds can succeed and still be broken. This drives the real artifacts the way
the operator will -- run Setup.exe, start the installed program, use the API --
and checks the promises the kit makes:

    * Setup installs the program and creates the database.
    * The installed program starts and serves both the API and the interface.
    * Signing up, creating an owner and logging in all work.
    * The PDF export works, which is what proves reportlab, arabic-reshaper and
      python-bidi survived freezing. They are imported lazily, so a missing one
      is invisible until an owner clicks Export.
    * Re-running Setup preserves the school's records.
    * Uninstalling removes the program but keeps the records.

Everything happens in a scratch folder, and the one shortcut it creates is
removed again at the end, so running this does not disturb the machine.

    python usb-kit/verify_kit.py
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BUILD = Path(__file__).resolve().parent
USB = BUILD / "out" / "USB"
SANDBOX = BUILD / "out" / "_verify"

EXE_NAME = "Vinta OS.exe"
APP_NAME = "Vinta OS"

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    results.append((PASS if ok else FAIL, label, detail))
    mark = "ok  " if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f"  -- {detail}" if detail and not ok else ""), flush=True)
    return ok


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def post(url: str, payload: dict, token: str | None = None,
         headers: dict | None = None) -> tuple[int, dict | str]:
    body = json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            try:
                return response.status, json.loads(raw.decode())
            except ValueError:
                return response.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def get(url: str, token: str | None = None, headers: dict | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, method="GET")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def wait_for_health(base: str, process: subprocess.Popen, timeout: float = 90) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=2) as response:
                if json.loads(response.read().decode()) == {"status": "ok"}:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    if not (USB / "Setup.exe").is_file():
        print(f"No kit at {USB}. Run build_usb.py first.")
        return 2

    print("\n=== Vinta OS USB kit verification ===\n")
    print(f"  Kit: {USB}\n")

    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    install = SANDBOX / "install"
    records = SANDBOX / "records"
    SANDBOX.mkdir(parents=True)

    # Setup creates both shortcuts, so both have to be remembered and removed:
    # leaving a Start Menu entry behind would leave this machine with a link to
    # a folder that the uninstall step goes on to delete.
    created_links: list[Path] = []
    desktop_link = None
    try:
        import shortcuts
        desktop_link = shortcuts.desktop_dir() / f"{APP_NAME}.lnk"
        created_links.append(desktop_link)
        created_links.append(shortcuts.start_menu_dir() / f"{APP_NAME}.lnk")
    except Exception:
        pass

    # ---------------------------------------------------------------- install
    print("-- Setup.exe -------------------------------------------------")
    result = subprocess.run(
        [str(USB / "Setup.exe"),
         "--dir", str(install), "--data-dir", str(records),
         "--no-registry", "--silent"],
        capture_output=True, text=True, timeout=1200,
    )
    check("Setup exits cleanly", result.returncode == 0,
          f"exit {result.returncode}\n{(result.stdout or '')[-1500:]}")

    exe = install / EXE_NAME
    check("Program installed", exe.is_file(), str(exe))
    check("Runtime bundled (_internal)", (install / "_internal").is_dir())
    check("Uninstaller installed", (install / "Uninstall.exe").is_file())

    database = records / "vinta.db"
    check("Database created in the records folder", database.is_file(), str(database))

    if database.is_file():
        with sqlite3.connect(database) as connection:
            tables = [r[0] for r in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
        check(f"Schema built ({len(tables)} tables)", len(tables) > 10,
              f"only {len(tables)} tables")
        for expected in ("academies", "users", "students", "teachers", "classes"):
            check(f"  table '{expected}' present", expected in tables)

    check("Shortcut points at the installed program",
          bool(desktop_link and desktop_link.is_file()), str(desktop_link))

    # ---------------------------------------------------------------- run it
    print("\n-- The installed application ---------------------------------")
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [str(exe), "--no-browser", "--port", str(port), "--data-dir", str(records)],
        cwd=str(install), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        alive = wait_for_health(base, process)
        check("Application starts and answers /api/health", alive)
        if not alive:
            output = ""
            if process.poll() is not None and process.stdout:
                output = process.stdout.read() or ""
            print(f"\n  --- application output ---\n{output[-3000:]}\n")
            raise SystemExit(1)

        status, page = get(f"{base}/")
        check("Interface served at /", status == 200 and b"root" in page)

        status, page = get(f"{base}/app/dashboard")
        check("Deep link returns the app shell", status == 200 and b"root" in page)

        # --- the real workflow a school would run ---
        email = "owner@verify-vinta.dz"
        password = "VerifyPass123!"

        status, signup = post(f"{base}/api/auth/signup", {
            "name": "Verification Academy",
            "email": email,
            "password": password,
        })
        check("Academy signup", status in (200, 201), f"{status} {signup}")
        academy_id = signup.get("academy_id") if isinstance(signup, dict) else None
        check("Signup returns an academy ID", bool(academy_id), f"{signup}")

        # Every academy-scoped route identifies the academy by this header, not
        # by anything in the token, so it has to travel with each request. A
        # client that forgets it gets a 400 that looks like a broken server.
        tenant = {"X-Academy-Id": academy_id} if academy_id else {}

        status, owner = post(f"{base}/api/auth/create-owner", {
            "academy_id": academy_id,
            "name": "Verification Owner",
            "email": email,
            "password": password,
            "pin": "4321",
        }, headers=tenant)
        check("Owner creation", status in (200, 201), f"{status} {owner}")

        status, login = post(f"{base}/api/auth/login", {
            "email": email, "password": password,
        })
        check("Login", status == 200, f"{status} {login}")
        token = login.get("access_token") if isinstance(login, dict) else None
        check("Login returns a token", bool(token))

        if token:
            status, body = get(f"{base}/api/auth/me", token=token)
            check("Authenticated request (/api/auth/me)", status == 200, f"{status} {body[:200]}")

            status, body = get(f"{base}/api/auth/profiles", token=token, headers=tenant)
            check("Profile picker lists the owner", status == 200 and b"owner" in body.lower(),
                  f"{status} {body[:200]}")

            # This is the real test of the frozen bundle: the PDF path pulls in
            # reportlab, arabic-reshaper and python-bidi, all imported lazily,
            # so a missing one is invisible until an owner clicks Export.
            status, body = get(f"{base}/api/billing/records/export?format=pdf",
                               token=token, headers=tenant)
            check("PDF export works", status == 200 and body[:4] == b"%PDF",
                  f"{status} {body[:200]!r}")

            status, body = get(f"{base}/api/billing/records/export?format=csv",
                               token=token, headers=tenant)
            check("CSV export works", status == 200 and len(body) > 0, f"{status}")

            status, body = get(f"{base}/api/billing/records/export?format=pdf",
                               token=token, headers={**tenant, "Accept-Language": "ar"})
            check("Arabic PDF export works (shaping)", status == 200 and body[:4] == b"%PDF",
                  f"{status} {body[:200]!r}")

            status, body = get(f"{base}/api/students", token=token, headers=tenant)
            check("Students index reachable", status == 200, f"{status} {body[:200]}")

            status, body = get(f"{base}/api/analytics/dashboard", token=token, headers=tenant)
            check("Dashboard overview reachable", status == 200, f"{status} {body[:200]}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()

    # --------------------------------------------------- reinstall keeps data
    print("\n-- Reinstall (the update path) -------------------------------")
    result = subprocess.run(
        [str(USB / "Setup.exe"),
         "--dir", str(install), "--data-dir", str(records),
         "--no-registry", "--no-shortcuts", "--silent"],
        capture_output=True, text=True, timeout=1200,
    )
    check("Setup can be run again over an existing install", result.returncode == 0,
          f"exit {result.returncode}")

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [str(exe), "--no-browser", "--port", str(port), "--data-dir", str(records)],
        cwd=str(install), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        if wait_for_health(base, process):
            status, login = post(f"{base}/api/auth/login", {
                "email": "owner@verify-vinta.dz", "password": "VerifyPass123!",
            })
            check("Records survived the reinstall (login still works)", status == 200,
                  f"{status} {login}")
        else:
            check("Application still starts after a reinstall", False)
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()

    # ------------------------------------------------------------- uninstall
    print("\n-- Uninstall -------------------------------------------------")
    result = subprocess.run(
        [str(install / "Uninstall.exe"), "--silent", "--dir", str(install)],
        capture_output=True, text=True, timeout=600,
    )
    check("Uninstaller exits cleanly", result.returncode == 0,
          f"exit {result.returncode}\n{(result.stdout or '')[-800:]}")

    # The uninstaller cannot delete its own running image, so it hands the
    # deletion to a copy of itself outside the folder and exits. The removal
    # therefore finishes just after this command returns; wait for it rather
    # than failing on a race that the design creates on purpose.
    deadline = time.time() + 90
    while install.exists() and time.time() < deadline:
        time.sleep(0.5)
    leftovers = sorted(p.name for p in install.iterdir())[:8] if install.exists() else []
    check("Program removed", not install.exists(), f"left behind: {leftovers}")
    check("Records kept by default", records.is_dir() and (records / "vinta.db").is_file())

    # ---------------------------------------------------------- diagnostics
    # Read before the sandbox is deleted. When something fails, the
    # application's own log is what says why — and the failures worth catching
    # here are exactly the ones that do not reproduce on demand.
    app_log = ""
    log_file = records / "vinta-os.log"
    if log_file.is_file():
        try:
            app_log = log_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

    # --------------------------------------------------------------- cleanup
    removed_links = 0
    for link in created_links:
        if link.is_file():
            try:
                link.unlink()
                removed_links += 1
            except OSError:
                pass
    if removed_links:
        print(f"\n  (removed {removed_links} test shortcut(s))")
    shutil.rmtree(SANDBOX, ignore_errors=True)

    # ---------------------------------------------------------------- report
    failed = [r for r in results if r[0] == FAIL]
    print("\n" + "=" * 66)
    print(f"  {len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("  FAILED:")
        for _, label, detail in failed:
            print(f"    - {label}  {detail[:300]}")
        if app_log:
            print("\n  --- vinta-os.log (last 60 lines) ---")
            for line in app_log.splitlines()[-60:]:
                print(f"  {line}")
            print("  --- end of log ---")
    print("=" * 66)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.path.insert(0, str(BUILD))
    sys.exit(main())
