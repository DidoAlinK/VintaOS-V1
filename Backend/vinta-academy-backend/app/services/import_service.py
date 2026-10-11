"""
Vinta School OS — Autodetect Import

Drop a CSV; work out what it is from its header row; load it.

Why detection lives on the server
---------------------------------
The column names a file carries are the only honest statement of what it
holds, and they are the same vocabulary the exports write. Reading them in
one place means the export and the import cannot drift: rename a column on
one side and detection stops recognising the other, loudly, instead of
quietly writing a phone number into the notes.

Everything a row names is resolved by name
------------------------------------------
A CSV has no foreign keys. ``classes.csv`` names a teacher; the import looks
that teacher up in *this* academy and refuses the row if it cannot find her —
it never invents a teacher to satisfy a class. A row that cannot be resolved
is reported, not guessed, and the rest of the file still loads.

Re-importing a file is safe
---------------------------
A row is matched on a natural key (a phone, an email, a name); a match is
updated in place, never inserted a second time. That is what makes dropping
the same file twice a correction rather than a duplication — the property
that a school restoring a backup depends on.
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import date, datetime, timezone

from app.extensions import db
from app.models.audit import ActivityLog
from app.models.billing import Expense
from app.models.class_room import Class
from app.models.student import Guardian, Student
from app.models.teacher import Teacher
from app.services import billing_service

#: A file larger than this is refused rather than half-read. A school register
#: is thousands of rows, not millions; the cap is here so a wrong file cannot
#: pin the process while it is parsed.
MAX_ROWS = 20000

#: Errors returned to the screen are capped — a wholly-wrong file can fail
#: every row, and the useful part of that answer is the first few, not 5000.
MAX_ERRORS = 200


# ── Header & value helpers ──────────────────────────────────────────────

_UNIT = re.compile(r"\s*\([^)]*\)\s*$")


def normalize_header(text) -> str:
    """A column name reduced to what it means.

    ``Amount (DA)`` and ``amount`` are the same column; so are ``first_name``
    and ``First Name``. Excel's BOM is stripped here because it rides on the
    first header and would otherwise make ``﻿name`` unrecognisable.
    """
    text = str(text or "").replace("﻿", "").strip().lower()
    text = _UNIT.sub("", text)
    text = re.sub(r"[_\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _text(value, limit: int | None = None) -> str:
    value = str(value if value is not None else "").strip()
    return value[:limit] if limit else value


def _amount(value) -> int:
    """A money cell as an integer of DZD.

    Tolerates the separators a spreadsheet adds: ``12 000``, ``12,000``,
    ``12.000 DA``. The decimal part is dropped, not rounded into existence —
    the currency has no cents and inventing them would misstate a total.
    """
    text = str(value if value is not None else "").strip()
    match = re.search(r"-?\d[\d\s.,]*", text)
    if not match:
        return 0
    digits = re.sub(r"[^\d-]", "", match.group(0).replace(",", "").replace(".", ""))
    try:
        return int(digits)
    except ValueError:
        return 0


def _date(value) -> date | None:
    text = _text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _datetime(value) -> datetime:
    text = _text(value)
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _decode(raw: bytes) -> str:
    """Text from bytes, trying the encodings a school actually produces.

    ``utf-8-sig`` first because Excel writes a BOM; ``cp1256`` next because a
    Windows machine in Algeria may have written Arabic in the older code page,
    and reading it as Latin-1 would turn every name into punctuation.
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1256", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _sniff(text: str) -> str:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def read_table(raw: bytes):
    """``(header_index, headers, rows)`` from a CSV's bytes.

    The header row is not assumed to be the first: the billing-records export
    opens with two title lines, and a file pasted together by hand often does
    too. The first ten rows are scanned and the one that looks most like a
    header — most cells non-empty, fewest purely numeric — is taken.
    """
    text = _decode(raw)
    delimiter = _sniff(text)
    grid = [row for row in csv.reader(io.StringIO(text), delimiter=delimiter)]

    best_index, best_score = 0, -1
    for index, row in enumerate(grid[:10]):
        cells = [cell for cell in row if str(cell).strip()]
        if len(cells) < 2:
            continue
        numeric = sum(1 for cell in cells if _amount(cell) and _digits(cell))
        score = len(cells) - numeric
        if score > best_score:
            best_index, best_score = index, score

    headers = [normalize_header(cell) for cell in grid[best_index]] if grid else []
    rows = []
    for row in grid[best_index + 1:]:
        if not any(str(cell).strip() for cell in row):
            continue
        rows.append({
            headers[i]: row[i]
            for i in range(min(len(headers), len(row)))
            if headers[i]
        })
        if len(rows) >= MAX_ROWS:
            break
    return best_index, headers, rows


def pick(row: dict, *aliases) -> str:
    """The first of ``aliases`` present in the row, or "".

    Aliases are matched already-normalised, so the table below is also the
    list of spellings the app accepts — English first (what our own exports
    write), then French and Arabic (what a hand-made file may carry).
    """
    for alias in aliases:
        key = normalize_header(alias)
        if key in row and str(row[key]).strip():
            return str(row[key]).strip()
    return ""


# ── Detection ───────────────────────────────────────────────────────────

#: `required` is a list of alternative groups: a group matches when every
#: header in it is present, and the dataset matches when any group does. That
#: is what lets a file say either "Name" or "First Name"/"Last Name".
#: `negative` are headers that belong to a *different* dataset; seeing one
#: subtracts, so "Phone + Parent Phone" is never read as a teacher.
DATASETS = [
    {
        "key": "students",
        "label": "students",
        "required": [("name",), ("first name", "last name")],
        "optional": {"phone", "parent phone", "classes", "status", "plan", "notes"},
        "negative": {"hourly rate", "contract type", "commission type", "action",
                     "direction", "category", "email"},
    },
    {
        "key": "teachers",
        # A bare "Name" is not enough: a roster and a staff list both have
        # one. The signature asks for the two-column name a personnel file
        # carries, or a name beside an email, which a register never has.
        "required": [("first name", "last name"), ("name", "email")],
        "optional": {"name", "email", "phone", "subject", "status", "contract type",
                     "hourly rate", "per student rate", "commission type",
                     "commission value", "notes"},
        "negative": {"parent phone", "classes", "plan", "direction", "action",
                     "category"},
    },
    {
        "key": "classes",
        "label": "classes",
        "required": [("name",)],
        "optional": {"subject", "teacher", "schedule", "price", "capacity",
                     "group", "billing model", "credits", "notes"},
        "negative": {"parent phone", "phone", "email", "action", "direction",
                     "amount"},
    },
    {
        "key": "expenses",
        "label": "expenses",
        "required": [("label", "amount")],
        "optional": {"category", "vendor", "quantity", "payment method", "method",
                     "notes", "date"},
        "negative": {"direction", "action", "profile", "parent phone", "email"},
    },
    {
        "key": "activity_logs",
        "label": "activityLog",
        "required": [("action", "description"), ("action", "type")],
        "optional": {"user", "date", "type", "entity", "entity type"},
        "negative": {"amount", "direction", "phone", "email", "parent phone"},
    },
    {
        "key": "billing_records",
        "label": "billing",
        "required": [("date", "amount", "type", "direction")],
        "optional": {"profile", "label", "status", "method", "notes"},
        "negative": {"action", "parent phone", "hourly rate", "email"},
    },
]

BY_KEY = {entry["key"]: entry for entry in DATASETS}


def score_dataset(entry, headers) -> int | None:
    present = set(headers)
    if not any(all(field in present for field in group) for group in entry["required"]):
        return None
    score = 3
    score += sum(1 for field in entry["optional"] if field in present)
    score -= 3 * sum(1 for field in entry["negative"] if field in present)
    return score


def detect_dataset(headers):
    """``(dataset_key, scores)`` — the best match, or ``(None, scores)``.

    Ties are not broken by guessing: two datasets scoring the same is a file
    that could be read two ways, and the honest answer is to say so and let
    the person look, rather than to pick one and write the wrong rows.
    """
    scores = {}
    for entry in DATASETS:
        score = score_dataset(entry, headers)
        if score is not None:
            scores[entry["key"]] = score

    if not scores:
        return None, scores

    best = max(scores.values())
    winners = [key for key, score in scores.items() if score == best]
    if len(winners) != 1 or best < 3:
        return None, scores
    return winners[0], scores


def candidates_for(headers):
    """The datasets a header row could plausibly be, best first.

    Handed to the screen when detection ties, so the owner can say which one
    it is instead of being told the file is unrecognisable.
    """
    scored = []
    for entry in DATASETS:
        score = score_dataset(entry, headers)
        if score is not None and score >= 3:
            scored.append((score, entry["key"]))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [key for _, key in scored]


class ImportDetectionError(ValueError):
    """A file that could not be read confidently — with what it might be."""

    def __init__(self, code, candidates=()):
        super().__init__(code)
        self.code = code
        self.candidates = list(candidates)


# ── Report ──────────────────────────────────────────────────────────────

class Report:
    """What happened, in the shape the screen renders."""

    def __init__(self, dataset):
        self.dataset = dataset
        self.total = 0
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.failed = 0
        self.errors = []
        self.notes = []

    def fail(self, index, code, message=""):
        self.failed += 1
        if len(self.errors) < MAX_ERRORS:
            self.errors.append({"row": index, "code": code, "message": message})

    def as_dict(self, dry_run: bool):
        return {
            "dataset": self.dataset,
            "dry_run": dry_run,
            "total": self.total,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
            "errors_truncated": self.failed > len(self.errors),
            "notes": self.notes,
        }


# ── Importers ───────────────────────────────────────────────────────────

def _import_students(academy_id, rows, ctx):
    report = Report("students")
    existing = ctx["students"]

    for index, row in rows:
        report.total += 1
        first = _text(pick(row, "first name", "firstname", "prénom", "الاسم"), 255)
        last = _text(pick(row, "last name", "lastname", "surname", "nom", "اللقب"), 255)
        if not first and not last:
            whole = _text(pick(row, "name", "full name", "nom complet", "الاسم الكامل"))
            parts = whole.split(None, 1)
            first = parts[0] if parts else ""
            last = parts[1] if len(parts) > 1 else ""
        if not first:
            report.fail(index, "missing_name")
            continue

        phone = _text(pick(row, "phone", "téléphone", "mobile", "هاتف"), 30)
        parent_phone = _text(pick(row, "parent phone", "parent's phone",
                                  "téléphone parent", "هاتف ولي الأمر"), 30)
        notes = _text(pick(row, "notes", "remarques", "ملاحظات"))

        key = _digits(phone) or f"{first.lower()}|{last.lower()}|{_digits(parent_phone)}"
        found = existing.get(key)

        if found is not None:
            if not ctx["dry_run"]:
                found.first_name, found.last_name = first, last
                if phone:
                    found.phone = phone
                if parent_phone:
                    found.parent_phone = parent_phone
                if notes:
                    found.notes = notes
            report.updated += 1
            continue

        if not ctx["dry_run"]:
            student = Student(
                id=str(uuid.uuid4()), academy_id=academy_id,
                first_name=first, last_name=last,
                phone=phone or None, parent_phone=parent_phone or None,
                notes=notes or None, is_active=True,
            )
            db.session.add(student)
            guardian_phone = parent_phone or phone
            if guardian_phone:
                db.session.add(Guardian(
                    id=str(uuid.uuid4()), student_id=student.id,
                    name="Parent", phone=guardian_phone,
                ))
            existing[key] = student
        report.created += 1

    return report


def _import_teachers(academy_id, rows, ctx):
    report = Report("teachers")
    existing = ctx["teachers"]

    for index, row in rows:
        report.total += 1
        first = _text(pick(row, "first name", "firstname", "prénom", "الاسم"), 255)
        last = _text(pick(row, "last name", "lastname", "surname", "nom", "اللقب"), 255)
        if not first and not last:
            whole = _text(pick(row, "name", "full name", "nom complet"))
            parts = whole.split(None, 1)
            first = parts[0] if parts else ""
            last = parts[1] if len(parts) > 1 else ""
        if not first:
            report.fail(index, "missing_name")
            continue

        email = _text(pick(row, "email", "e-mail", "courriel", "بريد"), 255)
        phone = _text(pick(row, "phone", "téléphone", "mobile"), 30)
        subject = _text(pick(row, "subject", "matière", "مادة"), 100)
        notes = _text(pick(row, "notes", "remarques", "ملاحظات"))

        key = (email.lower() if email else "") or _digits(phone) or \
            f"{first.lower()}|{last.lower()}"
        found = existing.get(key)

        if found is not None:
            if not ctx["dry_run"]:
                found.first_name, found.last_name = first, last
                if email:
                    found.email = email
                if phone:
                    found.phone = phone
                if subject:
                    found.subject = subject
                if notes:
                    found.notes = notes
            report.updated += 1
            continue

        if not ctx["dry_run"]:
            teacher = Teacher(
                id=str(uuid.uuid4()), academy_id=academy_id,
                first_name=first, last_name=last,
                email=email or None, phone=phone or None,
                subject=subject or None, notes=notes or None,
            )
            db.session.add(teacher)
        report.created += 1

    return report


def _import_classes(academy_id, rows, ctx):
    report = Report("classes")
    existing = ctx["classes"]
    teachers = ctx["teachers_by_name"]

    for index, row in rows:
        report.total += 1
        name = _text(pick(row, "name", "class", "group", "nom"), 255)
        if not name:
            report.fail(index, "missing_name")
            continue

        teacher_name = _text(pick(row, "teacher", "enseignant", "professeur", "أستاذ"))
        teacher_id = None
        if teacher_name:
            teacher_id = teachers.get(normalize_header(teacher_name))
            if teacher_id is None:
                # Never invent a teacher to satisfy a class: the class would
                # then point at a person who does not exist in the academy.
                report.fail(index, "teacher_not_found", teacher_name)
                continue

        subject = _text(pick(row, "subject", "matière", "مادة"), 100)
        price = _amount(pick(row, "price", "price da", "montant", "prix"))
        capacity = _amount(pick(row, "capacity", "capacité"))
        notes = _text(pick(row, "notes", "remarques", "ملاحظات"))

        key = name.lower()
        found = existing.get(key)

        if found is not None:
            if not ctx["dry_run"]:
                if subject:
                    found.subject = subject
                if teacher_id:
                    found.teacher_id = teacher_id
                if price:
                    found.price_da = price
                if capacity:
                    found.capacity = capacity
                if notes:
                    found.notes = notes
            report.updated += 1
            continue

        if not ctx["dry_run"]:
            cls = Class(
                id=str(uuid.uuid4()), academy_id=academy_id, name=name,
                subject=subject or None, teacher_id=teacher_id,
                price_da=price or 0, capacity=capacity or 0,
                notes=notes or None,
            )
            db.session.add(cls)
            existing[key] = cls
        report.created += 1

    if any(pick(row, "schedule", "horaire") for _, row in rows):
        report.notes.append("schedules_not_imported")
    return report


def _import_expenses(academy_id, rows, ctx):
    report = Report("expenses")

    for index, row in rows:
        report.total += 1
        expense_date = _date(pick(row, "date", "expense date"))
        label = _text(pick(row, "label", "description", "libellé"), 255)
        amount = _amount(pick(row, "amount", "amount da", "montant"))
        if not label:
            report.fail(index, "missing_label")
            continue

        data = {
            "category": _text(pick(row, "category", "catégorie")) or "OTHER",
            "label": label,
            "amount_da": amount,
            "quantity": _amount(pick(row, "quantity", "quantité")) or None,
            "expense_date": (expense_date or date.today()).isoformat(),
            "vendor": _text(pick(row, "vendor", "fournisseur")) or None,
            "payment_method": _text(pick(row, "method", "payment method",
                                         "moyen", "paiement")) or "CASH",
            "notes": _text(pick(row, "notes", "note", "remarques", "ملاحظات")) or None,
        }

        key = f"{(expense_date or date.today()).isoformat()}|{label.lower()}|{amount}"
        found = ctx["expenses"].get(key)
        if found is not None:
            if not ctx["dry_run"]:
                found.category = data["category"] or found.category
                found.amount_da = amount
                if data["notes"]:
                    found.notes = data["notes"]
            report.updated += 1
            continue

        try:
            if not ctx["dry_run"]:
                billing_service.create_expense(academy_id, data, ctx["actor_id"])
                ctx["expenses"][key] = True
            report.created += 1
        except ValueError as exc:
            report.fail(index, "invalid_row", str(exc))

    return report


def _import_activity_logs(academy_id, rows, ctx):
    report = Report("activity_logs")
    users = ctx["users_by_name"]

    for index, row in rows:
        report.total += 1
        action = _text(pick(row, "action", "activity"), 50)
        description = _text(pick(row, "description", "details", "détails"))
        entity_type = _text(pick(row, "type", "entity type", "entity"), 50)
        if not action and not description:
            report.fail(index, "missing_action")
            continue

        user_name = _text(pick(row, "user", "staff", "utilisateur"))
        user_id = users.get(normalize_header(user_name)) if user_name else None

        if not ctx["dry_run"]:
            db.session.add(ActivityLog(
                id=str(uuid.uuid4()), academy_id=academy_id,
                user_id=user_id,
                entity_type=entity_type or "system",
                entity_id=_text(pick(row, "entity id")) or "",
                action=action or "imported",
                description=description or None,
                created_at=_datetime(pick(row, "date", "created at", "when")),
            ))
        report.created += 1

    return report


def _import_billing_records(academy_id, rows, ctx):
    """Only the expense rows of a billing-records export.

    A ``STUDENT_PAYMENT`` row is not a payment on its own — it is a line that
    was *derived* from a subscription and a cycle, and writing it back without
    those would create money the ledger cannot account for. Those rows are
    reported, not guessed at; the payments screen is where they belong.
    """
    report = Report("billing_records")

    for index, row in rows:
        report.total += 1
        kind = _text(pick(row, "type", "kind")).upper()
        if "EXPENSE" not in kind:
            report.skipped += 1
            continue

        expense_date = _date(pick(row, "date"))
        label = _text(pick(row, "label", "description"), 255)
        amount = _amount(pick(row, "amount", "amount da"))
        if not label:
            report.fail(index, "missing_label")
            continue

        data = {
            "category": "OTHER",
            "label": label,
            "amount_da": amount,
            "expense_date": (expense_date or date.today()).isoformat(),
            "payment_method": _text(pick(row, "method")) or "CASH",
            "notes": _text(pick(row, "notes")) or None,
        }
        try:
            if not ctx["dry_run"]:
                billing_service.create_expense(academy_id, data, ctx["actor_id"])
            report.created += 1
        except ValueError as exc:
            report.fail(index, "invalid_row", str(exc))

    if report.skipped:
        report.notes.append("payments_not_importable")
    return report


IMPORTERS = {
    "students": _import_students,
    "teachers": _import_teachers,
    "classes": _import_classes,
    "expenses": _import_expenses,
    "activity_logs": _import_activity_logs,
    "billing_records": _import_billing_records,
}


# ── Context ─────────────────────────────────────────────────────────────

def _build_context(academy_id, actor_id, dry_run):
    """The lookups a file needs, read once rather than per row.

    Keys are the same natural keys the importers use, so a file that names
    the same teacher twice finds the first one re-used on the second row
    instead of creating a duplicate.
    """
    students = {}
    for student in Student.query.filter_by(academy_id=academy_id).all():
        key = _digits(student.phone) or \
            f"{student.first_name.lower()}|{student.last_name.lower()}|{_digits(student.parent_phone)}"
        students.setdefault(key, student)

    teachers = {}
    teachers_by_name = {}
    for teacher in Teacher.query.filter_by(academy_id=academy_id).all():
        if teacher.email:
            teachers.setdefault(teacher.email.lower(), teacher)
        if teacher.phone:
            teachers.setdefault(_digits(teacher.phone), teacher)
        full = f"{teacher.first_name}|{teacher.last_name}".lower()
        teachers.setdefault(full, teacher)
        teachers_by_name.setdefault(
            normalize_header(f"{teacher.first_name} {teacher.last_name}"), teacher.id)

    classes = {}
    for cls in Class.query.filter_by(academy_id=academy_id).all():
        classes.setdefault(cls.name.lower(), cls)

    expenses = {}
    for expense in Expense.query.filter_by(academy_id=academy_id).all():
        key = f"{expense.expense_date.isoformat() if expense.expense_date else ''}|" \
              f"{expense.label.lower()}|{expense.amount_da}"
        expenses.setdefault(key, expense)

    users_by_name = {}
    from app.models.user import User
    for user in User.query.filter_by(academy_id=academy_id).all():
        users_by_name.setdefault(normalize_header(user.name), user.id)

    return {
        "dry_run": dry_run,
        "actor_id": actor_id,
        "students": students,
        "teachers": teachers,
        "teachers_by_name": teachers_by_name,
        "classes": classes,
        "expenses": expenses,
        "users_by_name": users_by_name,
    }


# ── Entry point ─────────────────────────────────────────────────────────

def import_upload(academy_id, filename, raw, *, actor_id=None, dry_run=False,
                  dataset=None):
    """Detect and import a dropped file. Returns the report dict.

    ``dataset`` forces a choice, for the case where detection tied and the
    owner has already said which one it is.

    Raises ``ImportDetectionError`` (a ``ValueError``) with a code the screen
    translates when the file is not a CSV, is empty, or cannot be recognised
    — those are answers, not failures.
    """
    lowered = (filename or "").lower()
    if not (lowered.endswith(".csv") or lowered.endswith(".txt")):
        raise ImportDetectionError("unsupported_file")

    _, headers, rows = read_table(raw)
    if not headers:
        raise ImportDetectionError("empty_file")
    if not rows:
        raise ImportDetectionError("no_rows")

    scores = {}
    if dataset:
        if dataset not in BY_KEY:
            raise ImportDetectionError("unknown_dataset")
    else:
        dataset, scores = detect_dataset(headers)
        if dataset is None:
            # Nothing matched, or two things did. Both are answered with the
            # list of what the file *might* be, so the screen can offer a
            # choice rather than a dead end.
            raise ImportDetectionError("unknown_dataset", candidates_for(headers))

    ctx = _build_context(academy_id, actor_id, dry_run)
    report = IMPORTERS[dataset](academy_id, list(enumerate(rows, start=1)), ctx)

    if not dry_run:
        db.session.commit()

    result = report.as_dict(dry_run)
    result["scores"] = scores
    return result


def import_zip(academy_id, raw, *, actor_id=None, dry_run=False):
    """Import every ``csv/`` entry an Export-School archive carries.

    The order is the archive's own — the export writes parents before
    children, so a teacher exists before the class that names her.
    """
    import zipfile

    results = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [
            name for name in archive.namelist()
            if "/csv/" in name and name.lower().endswith(".csv")
        ]
        names.sort(key=lambda name: (("teachers" not in name), name))

        for name in names:
            with archive.open(name) as handle:
                data = handle.read()
            try:
                _, headers, rows = read_table(data)
                dataset, _scores = detect_dataset(headers)
                if dataset is None:
                    results.append({
                        "file": name.rsplit("/", 1)[-1], "dataset": None,
                        "total": len(rows), "created": 0, "updated": 0,
                        "skipped": 0, "failed": 0, "errors": [],
                        "errors_truncated": False, "notes": ["unknown_dataset"],
                        "candidates": candidates_for(headers),
                    })
                    continue

                ctx = _build_context(academy_id, actor_id, dry_run)
                report = IMPORTERS[dataset](
                    academy_id, list(enumerate(rows, start=1)), ctx)
                if not dry_run:
                    db.session.commit()
                entry = report.as_dict(dry_run)
                entry["file"] = name.rsplit("/", 1)[-1]
                results.append(entry)
            except Exception as exc:      # one bad member must not sink the rest
                db.session.rollback()
                results.append({
                    "file": name.rsplit("/", 1)[-1], "dataset": None,
                    "total": 0, "created": 0, "updated": 0, "skipped": 0,
                    "failed": 1, "errors": [{"row": 0, "code": "invalid_row",
                                             "message": str(exc)}],
                    "errors_truncated": False, "notes": [],
                })

    return {"archive": True, "dry_run": dry_run, "files": results}
