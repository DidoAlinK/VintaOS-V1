"""
Schema step — users.permissions.

WHY
    Until now a staff account's authority was the word "staff" and nothing
    else: every staff member could do exactly what every other staff member
    could do, and the only way to limit one was to limit all of them. This
    column carries each staff member's own grant — which areas of the app they
    may open, whether they may only read or also change, and the few named
    actions (taking payments, paying teachers, seeing the profit reports,
    minting logins, erasing the academy's data) that are handed out one tick at
    a time. The catalogue is ``app/permissions.py``.

WHY NULLABLE, AND WHY THAT IS THE WHOLE MIGRATION
    NULL means "never configured", and ``app/permissions.normalize`` reads it
    as the documented staff default: the day-to-day areas, no money, no
    settings. That is what let the enforcement ship without a lock-out —
    every staff row in the database is null on the day this ran, and reading
    null as "nothing granted" would have refused all of them at once. Reading
    it as the default leaves each of them working exactly as they did
    yesterday, and the owner narrows them afterwards, deliberately.

    An owner's column is ignored entirely, whatever it holds. An owner with a
    half-written row is still the owner.

WHY A SCRIPT AND NOT ALEMBIC
    ``migrations/versions/`` is stale and the running schema comes from
    ``db.create_all()``, which creates missing *tables* but never adds a
    missing *column*. Same pattern as ``add_teacher_share_percentage.py``,
    ``add_lifecycle_columns.py`` and ``nullable_activity_log_actor.py``.

IDEMPOTENT — safe to run repeatedly.
Run from anywhere:   py add_user_permissions.py
"""

import os
import sqlite3
import sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))

NEW_COLUMNS = [
    # (table, column, sqlite column definition)
    # No default and no NOT NULL: NULL is meaningful here ("never configured",
    # which reads as the staff default), so the ALTER must leave existing rows
    # null rather than inventing a value for them.
    (
        "users",
        "permissions",
        "JSON",
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

    # Every existing row should still be null: null is the "never configured"
    # reading, and a value written here by some earlier run would silently
    # override the default for that person.
    if ok:
        cur.execute("SELECT COUNT(*) FROM users WHERE permissions IS NOT NULL")
        configured = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'staff'")
        staff = cur.fetchone()[0]
        print(f"  [ok ] {staff} staff account(s), {configured} with a stored grant")

    conn.close()
    print(f"\nDone. {added} column(s) added.")
    print("Restart the Flask server.")


if __name__ == "__main__":
    main()
