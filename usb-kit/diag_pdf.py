"""
Focused diagnostic: why does the PDF export fail in the packaged build?

The route answers a failing export with a flat 500 and, until it was changed,
logged nothing at all — so the failure is invisible from outside. This drives
the packaged application through signup, owner creation and login, asks for the
PDF, and then prints the application's own log, which now carries the traceback.

    python usb-kit/diag_pdf.py [app-dir]

Defaults to the built application in usb-kit/out/app/Vinta OS. Leaves its
scratch folder in place so the log can be read afterwards.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRATCH = BUILD / "out" / "_diag"

EMAIL = "owner@diag-vinta.dz"
PASSWORD = "DiagPass123!"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def request(url, *, payload=None, token=None, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main() -> int:
    app_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 \
        else BUILD / "out" / "app" / "Vinta OS"
    exe = app_dir / "Vinta OS.exe"
    if not exe.is_file():
        print(f"No application at {exe}")
        return 2

    if SCRATCH.exists():
        shutil.rmtree(SCRATCH, ignore_errors=True)
    SCRATCH.mkdir(parents=True)

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    print(f"  app   : {exe}")
    print(f"  data  : {SCRATCH}")
    print(f"  url   : {base}\n")

    process = subprocess.Popen(
        [str(exe), "--no-browser", "--port", str(port), "--data-dir", str(SCRATCH)],
        cwd=str(app_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            if process.poll() is not None:
                print("The application exited before answering.")
                return 1
            try:
                status, _ = request(f"{base}/api/health")
                if status == 200:
                    break
            except Exception:
                time.sleep(0.5)
        else:
            print("The application never became ready.")
            return 1

        status, body = request(f"{base}/api/auth/signup", payload={
            "name": "Diagnostic Academy", "email": EMAIL, "password": PASSWORD,
        })
        academy_id = json.loads(body).get("academy_id") if status in (200, 201) else None
        print(f"  signup   -> {status} academy={academy_id}")
        tenant = {"X-Academy-Id": academy_id} if academy_id else {}

        status, body = request(f"{base}/api/auth/create-owner", payload={
            "academy_id": academy_id, "name": "Diag Owner",
            "email": EMAIL, "password": PASSWORD, "pin": "4321",
        }, headers=tenant)
        print(f"  owner    -> {status}")

        status, body = request(f"{base}/api/auth/login", payload={
            "email": EMAIL, "password": PASSWORD,
        })
        token = json.loads(body).get("access_token") if status == 200 else None
        print(f"  login    -> {status} token={'yes' if token else 'no'}")
        if not token:
            print(body[:500])
            return 1

        for fmt, extra in (("csv", {}), ("pdf", {}), ("pdf", {"Accept-Language": "ar"})):
            status, body = request(
                f"{base}/api/billing/records/export?format={fmt}",
                token=token, headers={**tenant, **extra},
            )
            label = f"{fmt}{' (ar)' if extra else ''}"
            print(f"  export {label:<8} -> {status} {len(body)} bytes {body[:6]!r}")

        # The reason we are here.
        time.sleep(1.0)
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()

    log_file = SCRATCH / "vinta-os.log"
    print("\n" + "=" * 70)
    print("  application log")
    print("=" * 70)
    if log_file.is_file():
        print(log_file.read_text(encoding="utf-8", errors="replace"))
    else:
        print(f"  (no log at {log_file})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
