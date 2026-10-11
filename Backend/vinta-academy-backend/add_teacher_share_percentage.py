"""
Schema step — academy_settings.default_teacher_share_percentage.

WHY
    The teacher/school split used to be a literal ``30`` inside
    ``billing_service.finalize_session``, which meant an owner could not change
    it and no screen could show it. It is now a column on the academy's
    settings row, read through ``academy_rules.default_teacher_share_percentage``
    at the moment a session is finalised. The school's share is derived
    (100 − this) and is deliberately not stored, so the two halves of a split
    can never disagree.

    The default is 30 — the same number the literal held — so an academy that
    never opens Settings pays its teachers exactly what it paid before this
    column existed.

WHY A SCRIPT AND NOT ALEMBIC
    ``migrations/versions/`` is stale and the running schema comes from
    ``db.create_all()``, which creates missing *tables* but never adds a
    missing *column*. Same pattern as ``add_lifecycle_columns.py`` and
    ``nullable_activity_log_actor.py``.

    The ``expenses`` table needs no step here: it is a whole table, so
    ``create_all()`` already creates it from the model. This script only has
    to add the one column ``create_all()`` cannot.

IDEMPOTENT — safe to run repeatedly.
Run from anywhere:   py add_teacher_share_percentage.py
"""

import os
import sqlite3
import sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))

NEW_COLUMNS = [
    # (table, column, sqlite column definition)
    # NOT NULL with a default so the ALTER can backfill every existing row;
    # matches the model's `server_default="30"`.
    (
        "academy_settings",
        "default_teacher_share_percentage",
        "INTEGER NOT NULL DEFAULT 30",
    ),
]


def resolve_db_path() -> str:
    """Resolve the SQLite file the app actually opens, from DATABASE_URL."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        env_path = os.path.join(HERE, ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if not url:
        print("FATAL: no DATABASE_URL found in environment or backend/.env")
        sys.exit(1)

    if not url.startswith("sqlite"):
        print(f"FATAL: this migration only handles SQLite. DATABASE_URL={url}")
        sys.exit(1)

    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "":
        return parsed.netloc
    name = parsed.path.lstrip("/")
    # Flask resolves a relative SQLite path against the app's instance folder.
    return os.path.join(HERE, "instance", os.path.basename(name))


def main() -> None:
    db_path = resolve_db_path()
    print(f"Database: {db_path}")

    if not os.path.exists(db_path):
        print("FATAL: database file not found.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print("\n-- columns --")
    added = 0
    for table, column, definition in NEW_COLUMNS:
        cur.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cur.fetchall()}
        if not existing:
            print(f"  [SKIP] table missing: {table}")
            continue
        if column in existing:
            print(f"  [have] {table}.{column}")
            continue
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            added += 1
            print(f"  [ADD ] {table}.{column} {definition}")
        except sqlite3.OperationalError as exc:
            print(f"  [FAIL] {table}.{column}: {exc}")

    conn.commit()

    print("\n-- verify --")
    ok = True
    for table, column, _ in NEW_COLUMNS:
        cur.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in cur.fetchall()}
        present = column in cols
        ok = ok and present
        print(f"  [{'ok ' if present else 'MISSING'}] {table}.{column}")

    # A stored value outside 0–100 would invert the split, so say so loudly
    # rather than letting it reach a payout.
    if ok:
        cur.execute(
            "SELECT COUNT(*) FROM academy_settings "
            "WHERE default_teacher_share_percentage < 0 "
            "   OR default_teacher_share_percentage > 100"
        )
        bad = cur.fetchone()[0]
        print(f"  [{'ok ' if bad == 0 else 'WARN'}] {bad} row(s) outside 0–100")

    conn.close()
    print(f"\nDone. {added} column(s) added.")
    print("Restart the Flask server.")


if __name__ == "__main__":
    main()
