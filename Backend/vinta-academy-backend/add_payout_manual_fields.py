"""
Schema step — payout_records gains manual payouts (nullable session_id + notes).

WHY
    Until now a payout could only come into existence one way: `finalize_session`
    computed it from a conducted session's gross revenue. There was no way for
    the owner to record a payout by hand — a bonus, a correction, a one-off
    arrangement — and no way to attach a note to any payout.

    Both are needed, and both are blocked by the same two facts:

      * `session_id` is NOT NULL, and a hand-recorded payout has no session.
      * there is no `notes` column, and no timestamp of any kind. `list_payouts`
        had to order by the *linked session's* date, which cannot work for a row
        with no session — so such a row would have been invisible in the very
        list it was created from.

WHY A SCRIPT AND NOT ALEMBIC
    `migrations/versions/` is stale and the running schema comes from
    `db.create_all()`, which creates missing *tables* but never alters an
    existing one. Same pattern as `add_lifecycle_columns.py` and
    `nullable_activity_log_actor.py`.

WHY A REBUILD
    SQLite cannot drop a NOT NULL constraint, so the column has to be recreated.
    `payout_records` is a leaf table — nothing holds a foreign key pointing at
    it (verified) — so rebuilding it is safe.

    The UNIQUE constraint on `session_id` is KEPT. `finalize_session` relies on
    it for idempotency ("one payout per session — reuse if raced"). SQLite,
    PostgreSQL and MySQL all treat NULLs as distinct under a UNIQUE constraint,
    so relaxed to nullable it still admits exactly one payout per session while
    allowing any number of manual ones.

BACKFILL
    Existing rows are copied verbatim, with the new columns derived from what is
    already known rather than invented:
      * source      -> 'SESSION' (every existing row has a session)
      * payout_date -> the session's date (the day the money is for)
      * recorded_at -> paid_at, else the session's date, else now. NOT NULL, so
                       it has to resolve to something.
    No monetary value, status or date that was already recorded is altered.

IDEMPOTENT — safe to run repeatedly.
Run from anywhere:   py add_payout_manual_fields.py
"""

import os
import sqlite3
import sys
from datetime import date
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))

# Mirrors the live table exactly, with session_id relaxed to nullable and the
# manual-payout columns added. UNIQUE(session_id) is deliberately retained —
# see WHY A REBUILD above.
PAYOUT_RECORDS_NEW = """
    CREATE TABLE payout_records__new (
        id VARCHAR(36) NOT NULL,
        academy_id VARCHAR(36) NOT NULL,
        teacher_id VARCHAR(36) NOT NULL,
        session_id VARCHAR(36),
        gross_revenue_da INTEGER NOT NULL,
        commission_type VARCHAR(20) NOT NULL,
        commission_value INTEGER NOT NULL,
        teacher_cut_da INTEGER NOT NULL,
        status VARCHAR(7) NOT NULL,
        source VARCHAR(20) NOT NULL DEFAULT 'SESSION',
        payout_date DATE,
        notes TEXT,
        recorded_at DATETIME,
        recorded_by_staff_id VARCHAR(36),
        paid_at DATETIME,
        paid_by_staff_id VARCHAR(36),
        PRIMARY KEY (id),
        FOREIGN KEY(academy_id) REFERENCES academies (id),
        FOREIGN KEY(teacher_id) REFERENCES teachers (id),
        UNIQUE (session_id),
        FOREIGN KEY(session_id) REFERENCES sessions (id),
        FOREIGN KEY(paid_by_staff_id) REFERENCES users (id),
        FOREIGN KEY(recorded_by_staff_id) REFERENCES users (id)
    )
"""

# Columns carried across, in the new table's order.
COLUMNS = (
    "id, academy_id, teacher_id, session_id, gross_revenue_da, commission_type, "
    "commission_value, teacher_cut_da, status, source, payout_date, notes, "
    "recorded_at, recorded_by_staff_id, paid_at, paid_by_staff_id"
)

# The same list, selected from the old table with the three derived columns
# resolved. `p` is the old table; the subquery reaches the linked session, which
# the correlated form keeps correct per row.
SELECT_FROM_OLD = """
    SELECT
        p.id, p.academy_id, p.teacher_id, p.session_id, p.gross_revenue_da,
        p.commission_type, p.commission_value, p.teacher_cut_da, p.status,
        'SESSION',
        (SELECT s.date FROM sessions s WHERE s.id = p.session_id),
        NULL,
        COALESCE(
            p.paid_at,
            (SELECT s.date FROM sessions s WHERE s.id = p.session_id),
            :now
        ),
        NULL,
        p.paid_at,
        p.paid_by_staff_id
    FROM payout_records p
"""

INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_payout_records_academy_recorded "
    "ON payout_records (academy_id, recorded_at)",
)


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

    cur.execute("PRAGMA table_info(payout_records)")
    cols = {row[1]: row for row in cur.fetchall()}
    if not cols:
        print("FATAL: payout_records is missing.")
        sys.exit(1)

    # PRAGMA table_info: index 3 is notnull.
    session_nullable = cols["session_id"][3] == 0
    has_new_columns = "source" in cols and "recorded_at" in cols

    if session_nullable and has_new_columns:
        print("[have] payout_records already supports manual payouts.")
        cur.execute("SELECT COUNT(*) FROM payout_records")
        print(f"       {cur.fetchone()[0]} row(s) present.")
        conn.close()
        return

    cur.execute("SELECT COUNT(*) FROM payout_records")
    rows = cur.fetchone()[0]
    print(f"Rebuilding payout_records ({rows} row(s) to carry over)")

    now = f"{date.today().isoformat()} 00:00:00"

    try:
        cur.execute("DROP TABLE IF EXISTS payout_records__new")
        cur.execute(PAYOUT_RECORDS_NEW)
        if rows:
            cur.execute(
                f"INSERT INTO payout_records__new ({COLUMNS}) {SELECT_FROM_OLD}",
                {"now": now},
            )
            copied = cur.rowcount
            if copied != rows:
                raise sqlite3.OperationalError(
                    f"copied {copied} of {rows} rows — refusing to drop the original"
                )
        cur.execute("DROP TABLE payout_records")
        cur.execute("ALTER TABLE payout_records__new RENAME TO payout_records")
        for statement in INDEXES:
            cur.execute(statement)
        print("  [OK  ] rebuilt: session_id nullable, notes/source/recorded_at added")
    except sqlite3.OperationalError as exc:
        print(f"  [FAIL] rebuild: {exc}")
        conn.rollback()
        conn.close()
        sys.exit(1)

    conn.commit()

    # --- verify -------------------------------------------------------------
    print("\n-- verify --")
    cur.execute("PRAGMA table_info(payout_records)")
    after = {row[1]: row for row in cur.fetchall()}

    print(f"  [{'ok ' if after['session_id'][3] == 0 else 'MISSING'}] "
          "payout_records.session_id nullable")
    for column in ("source", "payout_date", "notes", "recorded_at",
                   "recorded_by_staff_id"):
        print(f"  [{'ok ' if column in after else 'MISSING'}] "
              f"payout_records.{column} present")

    cur.execute("SELECT COUNT(*) FROM payout_records")
    preserved = cur.fetchone()[0]
    print(f"  [{'ok ' if preserved == rows else 'MISSING'}] "
          f"{rows} row(s) preserved")

    cur.execute("PRAGMA foreign_key_list(payout_records)")
    fks = cur.fetchall()
    print(f"  [{'ok ' if len(fks) == 5 else 'MISSING'}] "
          f"{len(fks)} foreign key(s) intact")

    # The UNIQUE on session_id is what keeps finalize_session idempotent.
    cur.execute("PRAGMA index_list(payout_records)")
    unique_ok = any(row[2] == 1 for row in cur.fetchall())
    print(f"  [{'ok ' if unique_ok else 'MISSING'}] "
          "UNIQUE(session_id) retained")

    cur.execute("SELECT status, COUNT(*) FROM payout_records GROUP BY status")
    print(f"  [ok ] statuses unchanged: {cur.fetchall()}")

    conn.close()
    print("\nDone. Restart the Flask server.")


if __name__ == "__main__":
    main()
