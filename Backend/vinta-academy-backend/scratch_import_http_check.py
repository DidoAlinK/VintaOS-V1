"""Drives the two new Settings routes over HTTP, not just the services.

`scratch_export_import_check.py` proves the archive and the importers do the
right thing to rows. What it cannot prove is everything between the browser and
those services: that Flask parses the multipart upload, that the download
carries a filename, and — the one that actually bites — that a staff member is
refused with **403 and not 401**. A 401 is read by the frontend's axios
interceptor as "your session is dead", so a permission refusal that answers 401
logs the user out and throws away whatever they were doing.

No server: Flask's test client exercises the real WSGI stack, decorators and
all.

Run from the backend root:  PYTHONPATH=. python scratch_import_http_check.py
"""
import io
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from flask_jwt_extended import create_access_token                    # noqa: E402

from app import create_app                                            # noqa: E402
from app.extensions import db                                         # noqa: E402
from app.models.academy import Academy                                # noqa: E402
from app.models.student import Student                                # noqa: E402
from app.models.user import User                                      # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(("  PASS  " if ok else "  FAIL  ") + label)


def note(label, value):
    print(f"  ..    {label}: {value}")


app = create_app("testing")

with app.app_context():
    db.create_all()

    users = [
        User(id="u-owner", academy_id="ac1", name="Nadia Owner",
             email="owner@example.dz", role="owner",
             pin_hash="x", password_hash="y", is_active=True),
        User(id="u-staff", academy_id="ac1", name="Karim Staff",
             email="staff@example.dz", role="staff",
             pin_hash="x", password_hash="y", is_active=True),
    ]
    db.session.add_all([Academy(id="ac1", name="Vinta Academy"), *users])
    db.session.commit()

    def auth(user_id, academy_id="ac1"):
        token = create_access_token(
            identity=user_id,
            additional_claims={"academy_id": academy_id, "role":
                               "owner" if user_id == "u-owner" else "staff"},
        )
        return {"Authorization": f"Bearer {token}", "X-Academy-Id": academy_id}

    client = app.test_client()
    owner = auth("u-owner")
    staff = auth("u-staff")

    def upload(headers, csv_bytes, filename="students.csv", **form):
        data = {"file": (io.BytesIO(csv_bytes), filename), **form}
        return client.post("/api/settings/import", data=data,
                           content_type="multipart/form-data", headers=headers)

    ROSTER = b"Name,Phone,Parent Phone\nKarim B.,0551111111,0661111111\n"

    # ── The preview refuses to write ────────────────────────────────────
    print("\nPOST /settings/import — preview")
    response = upload(owner, ROSTER, dry_run="1")
    check("preview accepted", response.status_code, 200)
    body = response.get_json()
    check("it says what it found", body["dataset"], "students")
    check("it says what it would do", body["created"], 1)
    check("it admits it is a preview", body["dry_run"], True)
    check("and nothing was written",
          Student.query.filter_by(academy_id="ac1").count(), 0)

    # ── The write ───────────────────────────────────────────────────────
    print("\nPOST /settings/import — commit")
    response = upload(owner, ROSTER)
    check("import accepted", response.status_code, 200)
    check("one student created", response.get_json()["created"], 1)
    check("it landed", Student.query.filter_by(academy_id="ac1").count(), 1)

    response = upload(owner, ROSTER)
    check("a second run updates rather than duplicating",
          (response.get_json()["created"], response.get_json()["updated"]), (0, 1))
    check("still one student",
          Student.query.filter_by(academy_id="ac1").count(), 1)

    # ── A file that cannot be read is an answer, not a crash ────────────
    print("\nPOST /settings/import — refusals")
    response = upload(owner, b"a,b,c\n1,2,3\n")
    check("nonsense is a 400", response.status_code, 400)
    check("with a code the screen can translate",
          response.get_json()["code"], "unknown_dataset")

    response = upload(owner, b"Name,Notes\nX,a note\n")
    check("a two-way header is a 400", response.status_code, 400)
    check("and it offers what it might be",
          sorted(response.get_json()["candidates"]), ["classes", "students"])

    response = upload(owner, b"Name,Notes\nX,a note\n", dataset="classes")
    check("the owner's choice is honoured", response.status_code, 200)
    check("with the dataset they named", response.get_json()["dataset"], "classes")

    response = upload(owner, b"", "empty.csv")
    check("an empty file is refused", response.get_json()["code"], "empty_file")

    # A `.xlsx` is not a CSV and must say so rather than be half-read.
    response = upload(owner, b"PK\x03\x04not really", "roster.xlsx")
    check("a spreadsheet is refused",
          response.get_json()["code"], "unsupported_file")

    # ── A whole Export-School archive ───────────────────────────────────
    print("\nPOST /settings/import — an archive")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("vinta-school-x_2026/csv/students.csv",
                         "Name,Phone\nArchive Student,0770000000\n")
    response = upload(owner, buffer.getvalue(), "vinta-school.zip")
    check("archive accepted", response.status_code, 200)
    check("reported as an archive", response.get_json()["archive"], True)
    note("members", [f["file"] for f in response.get_json()["files"]])
    check("its roster was imported",
          Student.query.filter_by(first_name="Archive", last_name="Student").count(), 1)

    # ── The download ────────────────────────────────────────────────────
    print("\nGET /settings/export/school")
    response = client.get("/api/settings/export/school", headers=owner)
    check("export accepted", response.status_code, 200)
    check("it is a zip", response.mimetype, "application/zip")
    check("it is offered as a download",
          "attachment" in response.headers.get("Content-Disposition", ""), True)
    check("the filename is ascii-safe",
          response.headers["Content-Disposition"].isascii(), True)
    check("and the answer varies by language",
          response.headers.get("Vary"), "Accept-Language")
    check("the body is a real zip", response.data[:2], b"PK")

    archive = zipfile.ZipFile(io.BytesIO(response.data))
    names = archive.namelist()
    check("the database is inside",
          any(n.endswith("database/school.db") for n in names), True)
    check("so is the roster",
          any(n.endswith("csv/students.csv") for n in names), True)
    check("and no activity log in the csv/ folder",
          any(n.endswith("csv/activity_logs.csv") for n in names), False)

    # The README is written in the language the request asked for.
    french = client.get("/api/settings/export/school",
                        headers={**owner, "Accept-Language": "fr"})
    check("the french export is still fine", french.status_code, 200)
    fr_archive = zipfile.ZipFile(io.BytesIO(french.data))
    fr_names = [n for n in fr_archive.namelist() if n.endswith("README.txt")]
    check("it still carries one README", len(fr_names), 1)
    fr_readme = fr_archive.read(fr_names[0]).decode("utf-8")
    check("and that README is french", "Exportation complète" in fr_readme, True)

    # ── Who may do any of this ──────────────────────────────────────────
    print("\nthe owner gate")
    response = upload(staff, ROSTER, dry_run="1")
    check("staff cannot preview an import", response.status_code, 403)
    check("and the refusal is not a 401 — that would log them out",
          response.status_code != 401, True)
    check("it is refused, not silently ignored",
          response.get_json()["error"], "Owner access required")

    response = upload(staff, ROSTER)
    check("staff cannot import", response.status_code, 403)

    response = client.get("/api/settings/export/school", headers=staff)
    check("staff cannot export the school", response.status_code, 403)
    check("nor is that a 401", response.status_code != 401, True)

    # The staff import attempt must not have written anything either.
    check("the refused import wrote nothing",
          Student.query.filter_by(academy_id="ac1").count(), 2)

    # A token from another academy is a different refusal again — still not 401.
    response = client.post("/api/settings/import",
                           data={"file": (io.BytesIO(ROSTER), "students.csv")},
                           content_type="multipart/form-data",
                           headers=auth("u-owner", "ac2"))
    check("another academy's header is refused", response.status_code, 403)

    # No token at all is only ever the framework's own 401, before our code.
    response = client.get("/api/settings/export/school")
    check("no token is a 401", response.status_code, 401)

    db.session.remove()

print()
if FAILED:
    print(f"{len(FAILED)} FAILED")
    for line in FAILED:
        print("  - " + line)
    sys.exit(1)
print("all checks passed")
