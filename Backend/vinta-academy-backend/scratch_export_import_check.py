"""Checks the school export archive and the autodetect import.

Standalone but not serverless: both features are about rows, so this builds a
real (in-memory) database, an academy and an owner, and drives the two
services exactly as the routes do. No HTTP, no dev server.

Run from the backend root:  PYTHONPATH=. python scratch_export_import_check.py
"""
import io
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import create_app                                          # noqa: E402
from app.extensions import db                                       # noqa: E402
from app.models.academy import Academy                              # noqa: E402
from app.models.student import Student                              # noqa: E402
from app.models.teacher import Teacher                              # noqa: E402
from app.models.billing import Expense                              # noqa: E402
from app.models.user import User                                    # noqa: E402
from app.services import import_service, school_export_service      # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(("  PASS  " if ok else "  FAIL  ") + label)


def note(label, value):
    print(f"  ..    {label}: {value}")


def norm(headers):
    return [import_service.normalize_header(h) for h in headers]


app = create_app("testing")

with app.app_context():
    db.create_all()

    owner = User(
        id="u-owner", academy_id="ac1", name="Nadia Owner",
        email="owner@example.dz", role="owner",
        pin_hash="x", password_hash="y",
    )
    db.session.add_all([Academy(id="ac1", name="Académie الفتح"), owner])
    db.session.commit()

    # ── Detection: does a header row name its own dataset? ──────────────
    print("\ndetect_dataset")
    check("roster -> students",
          import_service.detect_dataset(norm(
              ["Name", "Phone", "Parent Phone", "Classes", "Status", "Plan"]))[0],
          "students")
    check("staff list -> teachers",
          import_service.detect_dataset(norm(
              ["First Name", "Last Name", "Phone", "Email", "Subject",
               "Contract Type", "Hourly Rate"]))[0],
          "teachers")
    check("class list -> classes",
          import_service.detect_dataset(norm(
              ["Name", "Subject", "Teacher", "Schedule"]))[0],
          "classes")
    check("expense log -> expenses",
          import_service.detect_dataset(norm(
              ["Date", "Category", "Label", "Amount", "Method"]))[0],
          "expenses")
    check("audit feed -> activity_logs",
          import_service.detect_dataset(norm(
              ["Type", "Action", "Description", "User", "Date"]))[0],
          "activity_logs")
    check("billing records -> billing_records",
          import_service.detect_dataset(norm(
              ["Date", "Type", "Direction", "Profile", "Label", "Amount (DA)",
               "Status", "Method", "Notes"]))[0],
          "billing_records")
    check("nonsense is refused",
          import_service.detect_dataset(norm(["a", "b", "c"]))[0], None)

    # A BOM and a spreadsheet's semicolons must not hide a roster.
    _, headers, rows = import_service.read_table(
        "Name;Phone;Parent Phone\nKarim B;0551111111;0661111111\n"
        .encode("utf-8-sig"))
    check("semicolons and BOM survive", headers[0], "name")
    check("one data row read", len(rows), 1)

    # ── Import: create, then correct — never duplicate ──────────────────
    print("\nimport_upload — students")
    roster = "Name,Phone,Parent Phone\nKarim B.,0551111111,0661111111\n".encode()

    first = import_service.import_upload(
        "ac1", "students.csv", roster, actor_id=owner.id)
    check("first run creates", (first["created"], first["updated"]), (1, 0))

    second = import_service.import_upload(
        "ac1", "students.csv", roster, actor_id=owner.id)
    check("second run updates", (second["created"], second["updated"]), (0, 1))
    check("no duplicate student",
          Student.query.filter_by(academy_id="ac1").count(), 1)

    dry = import_service.import_upload(
        "ac1", "students.csv",
        "Name,Phone,Parent Phone\nSomeone New,0770000000,\n".encode(),
        actor_id=owner.id, dry_run=True)
    check("dry run reports a create", dry["created"], 1)
    check("dry run writes nothing",
          Student.query.filter_by(academy_id="ac1").count(), 1)

    # "Name,Phone" reads as a roster and nothing else, so it is not offered
    # a choice it does not need.
    plain = import_service.import_upload(
        "ac1", "people.csv", "Name,Phone\nPlain Row,0770000000\n".encode(),
        actor_id=owner.id, dry_run=True)
    check("a plain name+phone file is a roster", plain["dataset"], "students")

    # A file that could genuinely be read two ways is offered, not guessed at.
    try:
        import_service.import_upload(
            "ac1", "ambiguous.csv", "Name,Notes\nAmbiguous Row,some note\n".encode(),
            actor_id=owner.id, dry_run=True)
        check("ambiguous file is refused", "no error", "ImportDetectionError")
    except import_service.ImportDetectionError as exc:
        check("ambiguous file is refused", exc.code, "unknown_dataset")
        check("and it says what it might be",
              sorted(exc.candidates), ["classes", "students"])

    # ...and the owner's choice is honoured.
    forced = import_service.import_upload(
        "ac1", "ambiguous.csv", "Name,Notes\nAmbiguous Row,some note\n".encode(),
        actor_id=owner.id, dry_run=True, dataset="classes")
    check("forced dataset is used", forced["dataset"], "classes")

    # ── A row that names a teacher who does not exist is refused ────────
    print("\nimport_upload — unresolvable reference")
    classes = "Name,Subject,Teacher\nMath CM2,Math,Nobody Here\n".encode()
    report = import_service.import_upload(
        "ac1", "classes.csv", classes, actor_id=owner.id)
    check("row refused", report["failed"], 1)
    check("reason is the missing teacher",
          report["errors"][0]["code"], "teacher_not_found")

    teacher = Teacher(id="t1", academy_id="ac1", first_name="Nadia", last_name="Meziane")
    db.session.add(teacher)
    db.session.commit()
    ok = import_service.import_upload(
        "ac1", "classes.csv", "Name,Subject,Teacher\nMath CM2,Math,Nadia Meziane\n".encode(),
        actor_id=owner.id)
    check("resolved teacher imports", ok["created"], 1)

    # ── Expenses ────────────────────────────────────────────────────────
    print("\nimport_upload — expenses")
    expenses = ("Date,Category,Label,Amount,Method\n"
                "2026-10-01,SUPPLIES,Markers,1500,CASH\n").encode()
    exp = import_service.import_upload(
        "ac1", "expenses.csv", expenses, actor_id=owner.id)
    check("expense created", exp["created"], 1)
    check("expense row landed",
          Expense.query.filter_by(academy_id="ac1").count(), 1)
    check("amount parsed",
          Expense.query.filter_by(academy_id="ac1").first().amount_da, 1500)

    # ── The full archive ────────────────────────────────────────────────
    print("\nbuild_school_archive")
    payload, filename = school_export_service.build_school_archive("ac1", "fr")
    check("is a zip", payload[:2], b"PK")
    check("named for the academy and the date", filename.endswith(".zip"), True)

    archive = zipfile.ZipFile(io.BytesIO(payload))
    names = archive.namelist()
    note("members", len(names))
    check("has a student table", any(n.endswith("csv/students.csv") for n in names), True)
    check("has an expense table", any(n.endswith("csv/expenses.csv") for n in names), True)
    check("has a README", any(n.endswith("README.txt") for n in names), True)
    check("has a manifest", any(n.endswith("manifest.json") for n in names), True)
    check("activity log is left out",
          any("activity_logs" in n for n in names), False)

    users_csv = [n for n in names if n.endswith("csv/users.csv")]
    check("staff table is present", len(users_csv), 1)
    users_text = archive.read(users_csv[0]).decode("utf-8")
    check("password hash is not in it", "password_hash" in users_text, False)
    check("pin hash is not in it", "pin_hash" in users_text, False)
    check("the staff name still is", "Nadia Owner" in users_text, True)

    # SQLite is the shipped engine, so the database copy should be there and
    # must be a readable database, not a truncated file.
    db_members = [n for n in names if n.endswith("database/school.db")]
    check("database copy included", len(db_members), 1)
    if db_members:
        import sqlite3
        import tempfile
        import os
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.write(archive.read(db_members[0]))
        handle.close()
        try:
            conn = sqlite3.connect(handle.name)
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            conn.close()
            check("the copy is a real database", "students" in tables, True)
        finally:
            os.unlink(handle.name)

    readme = archive.read(
        [n for n in names if n.endswith("README.txt")][0]).decode("utf-8")
    check("README follows the asked-for language",
          "Exportation complète" in readme, True)

    # ── Routes are actually registered ──────────────────────────────────
    print("\nroutes")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    check("export/school is routed", "/api/settings/export/school" in rules, True)
    check("import is routed", "/api/settings/import" in rules, True)
    methods = {rule.rule: rule.methods for rule in app.url_map.iter_rules()}
    check("import takes POST", "POST" in methods["/api/settings/import"], True)

    db.session.remove()

print()
if FAILED:
    print(f"{len(FAILED)} FAILED")
    for line in FAILED:
        print("  - " + line)
    sys.exit(1)
print("all checks passed")
