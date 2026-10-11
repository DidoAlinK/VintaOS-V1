"""
Schema step — expenses.quantity.

WHY
    §11 of the billing brief asks an owner to record an expense with a
    quantity ("3 boxes of markers"), and ``create_expense`` had nowhere to
    put it: the ``expenses`` table shipped in the money model with category,
    label, amount, date, vendor, method and notes — but no unit count.

    It is nullable on purpose. Rent and a licence have no unit count, and a
    NOT NULL default would have to pick a number (0? 1?) for every row that
    does not have one, which is a fabricated fact in a financial table. NULL
    is the honest value for "not stated".

    ``amount_da`` stays the TOTAL paid, never a unit price, so no existing
    row changes meaning when a quantity is added.

WHY A SCRIPT AND NOT ALEMBIC
    ``migrations/versions/`` is stale and the running schema comes from
    ``db.create_all()``, which creates missing *tables* but never adds a
    missing *column* to one that already exists — and ``expenses`` has
    existed as a model for a while, so ``create_all()`` will leave the live
    table exactly as it is. Same pattern as ``add_lifecycle_columns.py``,
    ``nullable_activity_log_actor.py`` and ``add_teacher_share_percentage.py``.

    If the table does not exist yet this is a no-op and ``create_all()``
    builds it complete — the [SKIP] line below says so.

IDEMPOTENT — safe to run repeatedly.
Run from anywhere:   py add_expense_quantity.py
"""

import os
import sqlite3
import sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))

NEW_COLUMNS = [
    # (table, column, sqlite column definition)
    # Nullable with no default: existing rows keep "no quantity stated".
    (
        "expenses",
        "quantity",
        "INTEGER",
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
            print(f"  [SKIP] table missing: {table} (create_all() will build it whole)")
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
        if not cols:
            print(f"  [skip] {table} (table missing)")
            continue
        present = column in cols
        ok = ok and present
        print(f"  [{'ok ' if present else 'MISSING'}] {table}.{column}")

    # A quantity below 1 is refused by `_parse_quantity`, so a stored one would
    # have come from somewhere other than the API — say so rather than let it
    # render as a nonsense "0 ×".
    if ok:
        cur.execute(
            "SELECT COUNT(*) FROM expenses "
            "WHERE quantity IS NOT NULL AND quantity < 1"
        )
        bad = cur.fetchone()[0]
        print(f"  [{'ok ' if bad == 0 else 'WARN'}] {bad} row(s) with quantity < 1")

    conn.close()
    print(f"\nDone. {added} column(s) added.")
    print("Restart the Flask server.")


if __name__ == "__main__":
    main()
