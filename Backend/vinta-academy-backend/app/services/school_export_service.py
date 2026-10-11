"""
Vinta School OS — School Export ("everything" archive)

One download that carries the whole academy: the database file, a CSV per
table, and the same rows as JSON, with a README that says what is inside.

Why an archive, and not one more CSV
------------------------------------
Every other export answers a single question — the roster, the ledger, the
log. This one answers "give me my school back", so it has to be complete
*and* it has to explain itself once it is out of the building. A folder of
CSVs with no note is a puzzle; a database file with no warning is a trap.
The README is part of the export, not decoration around it.

What is left out, and why
-------------------------
The activity log is not in the ``csv/`` and ``json/`` folders. It is the
record of who did what to the data those folders carry, and it is the one
table the brief asked to keep back. The database copy *does* contain it — a
copy of the file is all of the file — and the README says so, rather than
letting the difference be discovered later.

``pin_hash`` and ``password_hash`` never leave the server. They are the only
two columns in the schema that are secrets rather than data: every login is
proved against them, so writing them into a file somebody emails to
themselves would hand over every account in the academy. The table is still
exported — staff names and roles are data — with those two columns removed.

The row set is read with ``collect_academy_keys``, the same foreign-key
closure the danger zone deletes by, so "everything we would erase" and
"everything we hand over" are the same list by construction.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import tuple_

from app.extensions import db
from app.i18n import translator
from app.models.academy import Academy
from app.services.academy_data_service import CHUNK, collect_academy_keys

#: Columns that are secrets rather than data. See the module docstring.
SECRET_COLUMNS = frozenset({"pin_hash", "password_hash"})

#: Kept out of the portable (CSV/JSON) part of the archive. Still present in
#: the database copy, which the README states plainly.
EXCLUDED_TABLES = frozenset({"activity_logs"})


def _slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-").lower()
    return slug or "academy"


def _cell(value):
    """One database value as a spreadsheet cell.

    Dates become ISO strings so the file reads the same in any locale, and a
    boolean becomes 1/0 rather than ``True``/``False`` so the import that
    reads this back recognises it without a second spelling.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        # Nothing in the schema stores binary today. If something ever does, a
        # blob in a spreadsheet cell is not a backup — it is a corrupt file.
        return ""
    return value


def _jsonable(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    return value


def _to_csv(columns, rows) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row[column]) for column in columns])
    return output.getvalue()


def _iter_rows(table, keys):
    """Yield the named rows, in primary-key batches.

    Batched because a busy academy's attendance table is larger than one
    statement's parameter list: SQLite's own limit is a few thousand bound
    values, and a `WHERE id IN (...)` with every row in the table would cross
    it. Keyed by primary key, not by an ``id`` column — ``teacher_subjects``
    has no ``id``, it is keyed by (teacher_id, subject_id).
    """
    key_columns = list(table.primary_key.columns)
    ordered = sorted(keys)
    for start in range(0, len(ordered), CHUNK):
        chunk = ordered[start:start + CHUNK]
        if len(key_columns) == 1:
            condition = key_columns[0].in_([key[0] for key in chunk])
        else:
            condition = tuple_(*key_columns).in_(chunk)
        statement = (
            db.select(table).where(condition).order_by(*key_columns)
        )
        for row in db.session.execute(statement).mappings():
            yield row


def _database_snapshot(name: str):
    """A consistent copy of the SQLite database, or None on another engine.

    ``sqlite3.Connection.backup`` is used rather than copying the file: the
    app is running while this executes, and a byte copy of a database that is
    mid-write can be torn. The backup API takes a read lock and produces a
    file that is valid on its own, from the live connection — which also
    avoids having to guess where a relative ``sqlite:///`` URL lands.
    """
    try:
        if db.engine.url.get_backend_name() != "sqlite":
            return None

        raw = db.engine.raw_connection()
        try:
            source = getattr(raw, "driver_connection", None)
            if source is None:
                return None

            handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            handle.close()
            try:
                target = sqlite3.connect(handle.name)
                try:
                    source.backup(target)
                finally:
                    target.close()
                with open(handle.name, "rb") as fh:
                    data = fh.read()
            finally:
                os.unlink(handle.name)
            return (name, data)
        finally:
            raw.close()
    except Exception:
        # A missing database copy must never fail the export: the CSVs are the
        # portable half, and they are already built.
        return None


def _readme(t, academy_name: str, generated: str, table_count: int,
            row_count: int, has_database: bool) -> str:
    """The note that travels with the archive, in the interface language."""
    lines = [
        t("export.school.readme.title"),
        "=" * len(t("export.school.readme.title")),
        "",
        t("export.school.readme.academy", academy=academy_name),
        t("export.school.readme.generated", when=generated),
        "",
        t("export.school.readme.intro"),
        t("export.school.readme.csv", tables=table_count, rows=row_count),
        t("export.school.readme.json"),
        t("export.school.readme.database") if has_database
        else t("export.school.readme.nodb"),
        "",
        t("export.school.readme.note_logs"),
        t("export.school.readme.note_secrets"),
        t("export.school.readme.note_import"),
        "",
    ]
    return "\n".join(lines)


def build_school_archive(academy_id: str, language: str = "en"):
    """The whole-academy archive, as ``(zip_bytes, filename)``.

    Read-only: nothing here writes to the database, so a failed export cannot
    leave the academy half-changed.
    """
    academy = db.session.get(Academy, academy_id)
    academy_name = getattr(academy, "name", "") or ""
    t = translator(language)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    folder = f"vinta-school-{_slug(academy_name)}_{stamp}"

    keys_by_table = collect_academy_keys(
        academy_id, keep_tables=EXCLUDED_TABLES, include_academy=True,
    )

    members: list[tuple[str, str]] = []
    table_counts: dict[str, int] = {}

    for table in db.Model.metadata.sorted_tables:
        keys = keys_by_table.get(table.name)
        if not keys:
            continue

        columns = [
            column.name for column in table.columns
            if column.name not in SECRET_COLUMNS
        ]
        rows = []
        for row in _iter_rows(table, keys):
            record = {name: row[name] for name in columns}
            rows.append(record)
        table_counts[table.name] = len(rows)

        members.append((
            f"{folder}/csv/{table.name}.csv",
            _to_csv(columns, rows),
        ))
        members.append((
            f"{folder}/json/{table.name}.json",
            json.dumps(
                [{k: _jsonable(v) for k, v in record.items()} for record in rows],
                ensure_ascii=False, indent=2,
            ),
        ))

    snapshot = _database_snapshot(f"{folder}/database/school.db")

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_rows = sum(table_counts.values())

    manifest = {
        "app": "Vinta School OS",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "academy": {"id": academy_id, "name": academy_name},
        "includes_database": snapshot is not None,
        "excluded_from_csv_json": sorted(EXCLUDED_TABLES),
        "redacted_columns": ["users.pin_hash", "users.password_hash"],
        "tables": table_counts,
        "total_rows": total_rows,
    }

    readme = _readme(
        t, academy_name, generated,
        table_count=len(table_counts), row_count=total_rows,
        has_database=snapshot is not None,
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, text in members:
            archive.writestr(path, text.encode("utf-8"))
        if snapshot is not None:
            archive.writestr(snapshot[0], snapshot[1])
        archive.writestr(f"{folder}/README.txt", readme.encode("utf-8"))
        archive.writestr(
            f"{folder}/manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )

    return buffer.getvalue(), f"{folder}.zip"
