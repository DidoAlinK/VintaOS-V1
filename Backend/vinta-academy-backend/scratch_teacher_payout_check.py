"""Checks the teacher-statement export: the CSV, the PDF, and the language.

Standalone, like `scratch_pdf_language_check.py`: the row builders and the two
document builders take their data and their header block as arguments and never
touch the session, so the whole string-and-layout path can be exercised from a
dict. Only the outer `export_teacher_payout` needs an app context, because it
looks up the academy's name for the header — so that part runs inside a
throwaway in-memory app.

Run from the backend root:  python scratch_teacher_payout_check.py
"""
import re
import sys
import zlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.i18n import translator                                       # noqa: E402
from app.services.export_service import (                             # noqa: E402
    TEACHER_GROUP_HEADERS, TEACHER_PAYOUT_HEADERS, _ascii_slug, _cadence_phrase,
    _ensure_font, _payout_period, _payout_period_span, teacher_payout_csv,
    teacher_payout_pdf,
)

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(("  PASS  " if ok else "  FAIL  ") + label)


def note(label, value):
    print(f"  ..    {label}: {value}")


def text_runs(pdf: bytes) -> set:
    """Every 4-hex-digit code in the document's ToUnicode maps.

    reportlab subsets the TTF and writes glyph ids into the page, not
    characters, so the page bytes say nothing about the words that were drawn.
    The ToUnicode CMap is the translation table it writes alongside, and that
    is where the actual codepoints can be read back.
    """
    found = set()
    for match in re.finditer(rb"stream\r?\n", pdf):
        end = pdf.find(b"endstream", match.end())
        if end == -1:
            continue
        try:
            chunk = zlib.decompress(pdf[match.end():end])
        except zlib.error:
            continue
        for code in re.findall(rb"<([0-9A-Fa-f]{4})>", chunk):
            found.add(int(code, 16))
    return found


# ── The fixture: one teacher's statement, shaped like the service's payload ──
ACADEMY = "أكاديمية الفتح"
TEACHER = "Nadia Meziane"

DETAILS = {
    "teacher_id": "t1",
    "teacher_name": TEACHER,
    "teacher_status": "active",
    "commission_type": "PERCENTAGE",
    "commission_value": 40,
    "window": {"from": "2026-09-01", "to": "2026-09-30"},
    "gross_revenue_da": 120000,
    "teacher_cut_da": 48000,
    "pending_da": 30000,
    "paid_da": 18000,
    "owed_da": 30000,
    "settled_da": 18000,
    "pending_count": 5,
    "paid_count": 3,
    "payout_count": 8,
    "session_count": 8,
    "manual_count": 1,
    "duration_hours": 12.5,
    "average_class_revenue_da": 15000,
    "average_cut_per_session_da": 6000,
    "students_taught": 14,
    "students_enrolled": 18,
    "group_count": 2,
    "groups": [
        {
            "group_id": "c1", "group_name": "3AS Maths",
            "gross_revenue_da": 80000, "teacher_cut_da": 32000,
            "pending_da": 20000, "paid_da": 12000,
            "session_count": 5, "duration_hours": 7.5,
        },
        {
            "group_id": "c2", "group_name": "فوج الفيزياء",
            "gross_revenue_da": 40000, "teacher_cut_da": 16000,
            "pending_da": 10000, "paid_da": 6000,
            "session_count": 3, "duration_hours": 5.0,
        },
    ],
    "schedule": {
        "teacher_id": "t1", "cadence": "WEEKLY", "day_of_week": 6,
        "day_of_month": None, "source": "teacher",
        "next_payout_date": "2026-10-11", "last_payout_date": "2026-10-04",
    },
    "due": {
        "is_due": True, "pending_da": 30000,
        "oldest_pending_date": "2026-09-05",
    },
    "lines": [
        {
            "payout_id": "p1", "date": "2026-09-30", "group_id": "c1",
            "group_name": "3AS Maths", "session_id": "s1", "source": "SESSION",
            "commission_type": "PERCENTAGE", "commission_value": 40,
            "gross_revenue_da": 15000, "teacher_cut_da": 6000,
            "status": "PENDING", "duration_hours": 1.5, "notes": "",
        },
        {
            # A manual payout: no session, so no group and no hours. This is the
            # row that proves the outer join survived into the file.
            "payout_id": "p2", "date": "2026-09-28", "group_id": None,
            "group_name": None, "session_id": None, "source": "MANUAL",
            "commission_type": "FIXED", "commission_value": 2000,
            "gross_revenue_da": 0, "teacher_cut_da": 2000,
            "status": "PENDING", "duration_hours": 0, "notes": "منحة",
        },
        {
            "payout_id": "p3", "date": "2026-09-20", "group_id": "c2",
            "group_name": "فوج الفيزياء", "session_id": "s2", "source": "SESSION",
            "commission_type": "PERCENTAGE", "commission_value": 40,
            "gross_revenue_da": 12000, "teacher_cut_da": 4800,
            "status": "PAID", "duration_hours": 1.5, "notes": None,
        },
    ],
}

META = {"academy": ACADEMY, "generated": "2026-10-11 09:30", "totals": {}}

# ── Filenames have to be ASCII ─────────────────────────────────────────────
# `Content-Disposition` is a byte header with no encoding of its own; a name
# that is not ASCII is how a download arrives mangled or not at all.
print("\n_ascii_slug")
check("latin name", _ascii_slug("Nadia Meziane"), "nadia-meziane")
check("arabic name falls back", _ascii_slug("أمين"), "teacher")
check("cyrillic name falls back", _ascii_slug("Амина"), "teacher")
check("accents are dropped", _ascii_slug("Amélie"), "am-lie")
check("punctuation collapses", _ascii_slug("Ben  Ali__Said!"), "ben-ali-said")
check("empty falls back", _ascii_slug(""), "teacher")
check("None falls back", _ascii_slug(None), "teacher")
check("result is always ascii",
      all(_ascii_slug(n).isascii() for n in
          ("Nadia Meziane", "أمين بلقاسم", "Amélie", "")), True)
check("long names are cut", len(_ascii_slug("x" * 200)) <= 48, True)

# ── The period line ────────────────────────────────────────────────────────
print("\n_payout_period")
en, fr, ar = translator("en"), translator("fr"), translator("ar")
check("closed range", _payout_period(DETAILS, en),
      "Period: 2026-09-01 to 2026-09-30")
check("closed range, french", _payout_period(DETAILS, fr),
      "Période : du 2026-09-01 au 2026-09-30")
check("closed range, arabic", _payout_period(DETAILS, ar),
      "الفترة: من 2026-09-01 إلى 2026-09-30")
check("open start", _payout_period({"window": {"from": None, "to": "2026-09-30"}}, en),
      "Period: up to 2026-09-30")
check("open end", _payout_period({"window": {"from": "2026-09-01", "to": None}}, en),
      "Period: from 2026-09-01")
check("no window at all", _payout_period({}, en), "Period: all time")
check("null window", _payout_period({"window": None}, en), "Period: all time")

# The value half, which is what the CSV puts beside its own label. If the
# label were baked in here too, the CSV would read `Period,Period: ...`.
check("span: closed range", _payout_period_span(DETAILS, en),
      "2026-09-01 to 2026-09-30")
check("span: open start", _payout_period_span({"window": {"to": "2026-09-30"}}, en),
      "up to 2026-09-30")
check("span: open end", _payout_period_span({"window": {"from": "2026-09-01"}}, en),
      "from 2026-09-01")
check("span: all time", _payout_period_span({}, en), "all time")
check("span is never the sentence", ":" in _payout_period_span(DETAILS, en), False)

# ── The payroll cadence ────────────────────────────────────────────────────
print("\n_cadence_phrase")
check("weekly, english", _cadence_phrase(
    en, {"cadence": "WEEKLY", "day_of_week": 6}), "every Sunday")
check("weekly, french", _cadence_phrase(
    fr, {"cadence": "WEEKLY", "day_of_week": 6}), "chaque dimanche")
check("weekly, arabic", _cadence_phrase(
    ar, {"cadence": "WEEKLY", "day_of_week": 6}), "كل الأحد")
check("monthly", _cadence_phrase(
    en, {"cadence": "MONTHLY", "day_of_month": 5}), "day 5 of each month")
check("monthly, french", _cadence_phrase(
    fr, {"cadence": "MONTHLY", "day_of_month": 5}), "le 5 de chaque mois")
check("none", _cadence_phrase(en, {"cadence": "NONE"}), "settled by hand")
check("missing schedule", _cadence_phrase(en, None), "settled by hand")
check("empty schedule", _cadence_phrase(en, {}), "settled by hand")
# A day-of-week that is not 0..6 has no name. Printing the key would put
# `export.teacher.weekday.9` down a financial document; falling back to "by
# hand" is the honest answer, because we genuinely do not know the day.
check("out-of-range weekday degrades", _cadence_phrase(
    en, {"cadence": "WEEKLY", "day_of_week": 9}), "settled by hand")
check("weekly with no day degrades", _cadence_phrase(
    en, {"cadence": "WEEKLY"}), "settled by hand")

# ── The CSV ────────────────────────────────────────────────────────────────
print("\nteacher_payout_csv")
csv_text = teacher_payout_csv(DETAILS, META)
rows = [line.split(",") for line in csv_text.splitlines()]
flat = csv_text

check("names the teacher", "Teacher,Nadia Meziane" in csv_text, True)
check("names the academy", f"Academy,{ACADEMY}" in csv_text, True)
check("carries the period", "Period,2026-09-01 to 2026-09-30" in csv_text, True)
check("carries the cadence", "Payroll,every Sunday" in csv_text, True)
check("totals label is english",
      'Revenue generated,"120,000 DA"' in csv_text, True)
# Read back through the csv module rather than by splitting on commas: the
# amounts carry thousands separators, so a naive split is what a spreadsheet
# would do wrong, not what the file does wrong.
import csv as _csv                                                     # noqa: E402
parsed = list(_csv.reader(csv_text.splitlines()))
check("a money cell reads back whole",
      [r for r in parsed if r and r[0] == "Revenue generated"][0],
      ["Revenue generated", "120,000 DA"])
check("the teacher row reads back whole",
      [r for r in parsed if r[:1] == ["Teacher"]][0], ["Teacher", TEACHER])
check("headings are english", list(TEACHER_PAYOUT_HEADERS) in rows, True)
check("group headings are english", list(TEACHER_GROUP_HEADERS) in rows, True)
check("a session line is listed",
      any(r[:1] == ["2026-09-30"] and r[1] == "3AS Maths" for r in rows), True)
check("a manual line is listed",
      any(r[:2] == ["2026-09-28", ""] for r in rows), True)
check("manual source is named", "Manual" in flat, True)
check("session source is named", "Session" in flat, True)
check("statuses are left as enums",
      "PENDING" in flat and "PAID" in flat, True)
check("arabic survives into the csv", "فوج الفيزياء" in csv_text, True)
check("every line count adds up",
      len([r for r in rows if r and r[0] == "2026-09-30"]), 1)

# A statement with nothing on it still has to be a statement — an export that
# raises because a teacher had a quiet month loses the owner a document rather
# than producing an empty one.
empty_csv = teacher_payout_csv(
    {"teacher_name": "New Hire", "window": {}, "schedule": {}, "lines": [],
     "groups": [], "gross_revenue_da": 0, "teacher_cut_da": 0, "pending_da": 0,
     "paid_da": 0, "average_class_revenue_da": 0, "session_count": 0,
     "manual_count": 0, "duration_hours": 0, "students_taught": 0,
     "group_count": 0},
    META,
)
check("empty statement still builds", "Teacher,New Hire" in empty_csv, True)
check("empty statement keeps its headings",
      list(TEACHER_PAYOUT_HEADERS) in [l.split(",") for l in empty_csv.splitlines()],
      True)

# `lines: None` is what the details payload carries when the caller did not ask
# for them — the shape an export must never silently accept as "no payouts".
none_csv = teacher_payout_csv({**DETAILS, "lines": None}, META)
check("lines=None does not raise", "Teacher,Nadia Meziane" in none_csv, True)

# ── The PDF ────────────────────────────────────────────────────────────────
print("\nteacher_payout_pdf")
font = _ensure_font()
note("font", font)

built = {}
for lang in ("en", "fr", "ar"):
    data = teacher_payout_pdf(DETAILS, META, lang)
    built[lang] = data
    check(f"{lang}: is a PDF", data[:5], b"%PDF-")
    note(f"{lang}: size", f"{len(data)} bytes")

check("french differs from english", built["fr"] != built["en"], True)
check("arabic differs from english", built["ar"] != built["en"], True)
check("language may be omitted",
      teacher_payout_pdf(DETAILS, META)[:5], b"%PDF-")
check("unknown language falls back",
      teacher_payout_pdf(DETAILS, META, "sv")[:5], b"%PDF-")
check("full header accepted",
      teacher_payout_pdf(DETAILS, META, "ar-DZ,ar;q=0.9")[:5], b"%PDF-")
check("a statement with no payouts still builds",
      teacher_payout_pdf({"teacher_name": "New Hire", "lines": [], "groups": []},
                         META, "ar")[:5], b"%PDF-")

# Every Arabic string in the document goes through `paragraph()`, so an isolated
# Arabic letter surviving into the output means some path skipped the shaper —
# in the Arabic document that is every heading and every total, and in the
# French one it is the teacher's own name.
for lang in ("en", "fr", "ar"):
    codes = text_runs(built[lang])
    forms = sum(1 for c in codes if 0xFE70 <= c <= 0xFEFF)
    left = sorted(c for c in codes if 0x0600 <= c <= 0x06FF)
    note(f"{lang}: presentation forms", forms)
    check(f"{lang}: unshaped arabic left over", left, [])

check("arabic pdf contains shaped glyphs",
      any(0xFE70 <= c <= 0xFEFF for c in text_runs(built["ar"])), True)

# ── The outer call: format dispatch and the filename on the wire ───────────
print("\nexport_teacher_payout")
from flask import Flask                                              # noqa: E402
from app.extensions import db                                        # noqa: E402
import app.models  # noqa: F401,E402  — so create_all sees every table

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
db.init_app(app)

with app.app_context():
    db.create_all()

    from app.services.export_service import export_teacher_payout

    payload, mimetype, filename = export_teacher_payout(
        DETAILS, "csv", "ar", academy_id="missing")
    check("csv mimetype", mimetype, "text/csv")
    check("csv filename is ascii", filename.isascii(), True)
    check("csv filename names the teacher", filename, "teacher-statement-nadia-meziane.csv")
    check("csv payload is the csv", payload[:9], "Teacher,N")

    pdf_bytes, pdf_mime, pdf_name = export_teacher_payout(
        DETAILS, "pdf", "ar", academy_id="missing")
    check("pdf mimetype", pdf_mime, "application/pdf")
    check("pdf filename is ascii", pdf_name.isascii(), True)
    check("pdf filename ends right", pdf_name.endswith(".pdf"), True)
    check("pdf payload is a pdf", pdf_bytes[:5], b"%PDF-")

    # An unrecognised format is a 400 at the route, not a silent CSV.
    try:
        export_teacher_payout(DETAILS, "xlsx", "en", academy_id="missing")
        check("bad format raises", False, True)
    except ValueError:
        check("bad format raises", True, True)

    # A teacher whose name has no Latin characters must still get a file.
    _, _, arabic_name = export_teacher_payout(
        {**DETAILS, "teacher_name": "أمين بلقاسم"}, "pdf", "ar", academy_id="missing")
    check("arabic teacher name is ascii",
          arabic_name.isascii() and arabic_name.endswith(".pdf"), True)
    note("arabic teacher filename", arabic_name)

    # No academy row at all: the header loses the name, the document survives.
    check("missing academy still builds",
          export_teacher_payout(DETAILS, "pdf", "en")[0][:5], b"%PDF-")

# ── Report ─────────────────────────────────────────────────────────────────
print()
if FAILED:
    print(f"{len(FAILED)} FAILED")
    for line in FAILED:
        print("  - " + line)
    sys.exit(1)
print("all checks passed")
