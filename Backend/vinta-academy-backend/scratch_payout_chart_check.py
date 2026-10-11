"""Teacher cost in the monthly chart — before and after. Delete when done.

The owner reported teacher cost "getting calculated but not showing up" in the
Financial Reports bar chart. The all-time KPI read a non-zero figure while every
month of the series read zero for it.

Cause: the monthly bucket matched on the *session* date alone, and a payout
recorded by hand has no session, so its date was NULL and it matched no month.
The all-time total sums every payout, session or not — hence a figure on the KPI
and an empty series.

This script states both rules side by side over the live data, then asks the
running server what it is actually serving, so the fix is verified end to end
rather than by reading the diff.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://127.0.0.1:5000/api"
OWNER = "direction@academie-el-feth.dz"
PASSWORD = "owner1234"
MONTHS = 6
FAILURES = []


def call(method, path, token=None, academy=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if academy:
        req.add_header("X-Academy-Id", academy)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def check(label, ok, detail=""):
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


# ── Log in ──────────────────────────────────────────────────────────────────
status, body = call("POST", "/auth/login", body={"email": OWNER, "password": PASSWORD})
if status != 200:
    print(f"login failed ({status}): {body}")
    sys.exit(1)
token = body["access_token"]
academy = body.get("academy_id") or body.get("user", {}).get("academy_id")
print(f"logged in as {OWNER}  academy={academy}\n")

# ── The two rules, over the live rows ───────────────────────────────────────
from app import create_app  # noqa: E402
from app.models.billing import PayoutRecord  # noqa: E402
from app.models.scheduling import Session  # noqa: E402
from app.services.billing_service import _payout_effective_date, _shift_month  # noqa: E402

app = create_app()
with app.app_context():
    payouts = PayoutRecord.query.filter_by(academy_id=academy).all()
    sessions = {s.id: s for s in Session.query.filter_by(academy_id=academy).all()}

today = date.today()
windows = []
for back in range(MONTHS - 1, -1, -1):
    year, month = _shift_month(today.year, today.month, back)
    first = date(year, month, 1)
    last = (date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1))
    windows.append((first, last.fromordinal(last.toordinal() - 1)))

old_rule = defaultdict(int)
new_rule = defaultdict(int)
manual_total = 0
manual_dropped_by_old_rule = 0

for p in payouts:
    session = sessions.get(p.session_id) if p.session_id else None
    session_date = session.date if session else None
    effective = _payout_effective_date(p, session_date)
    cut = int(p.teacher_cut_da or 0)
    is_manual = (p.source or "SESSION") == "MANUAL"
    if is_manual:
        manual_total += cut

    for start, end in windows:
        label = start.strftime("%b %Y")
        if session_date and start <= session_date <= end:
            old_rule[label] += cut
        if effective and start <= effective <= end:
            new_rule[label] += cut
        elif is_manual and effective is None:
            pass

    # Did the old rule lose this row from the whole window?
    if cut and is_manual:
        if not (session_date and any(s <= session_date <= e for s, e in windows)):
            manual_dropped_by_old_rule += cut

print("payout rows:", len(payouts))
print(f"manual payout value on record: {manual_total:,} DA")
print(f"of that, the old monthly rule dropped: {manual_dropped_by_old_rule:,} DA\n")

print(f"{'month':<10} {'old rule':>12} {'new rule':>12}   delta")
for start, _ in windows:
    label = start.strftime("%b %Y")
    delta = new_rule[label] - old_rule[label]
    print(f"{label:<10} {old_rule[label]:>12,} {new_rule[label]:>12,}   {delta:+,}")

# ── What the server actually serves ─────────────────────────────────────────
status, summary = call("GET", f"/billing/financial-summary?months={MONTHS}", token, academy)
check("GET /billing/financial-summary -> 200", status == 200, f"got {status}")

print("\nserved series:")
for point in summary.get("series", []):
    print(
        f"  {point['month']:<10} revenue={point['revenue']:>10,}  "
        f"teacher_cost={point['teacher_cost']:>10,}  expense={point['expense']:>9,}  "
        f"net={point['net']:>10,}"
    )

print(f"\n  teacher_cost_total_da (all time) = {summary.get('teacher_cost_total_da', 0):,}")

print("\n== served teacher_cost matches the effective-date rule ==")
for point in summary.get("series", []):
    want = new_rule[point["month"]]
    check(
        f"{point['month']}: series teacher_cost == {want:,}",
        point["teacher_cost"] == want,
        f"got {point['teacher_cost']:,}",
    )

print("\n== the chart is not empty for teacher cost ==")
served_series = summary.get("series", [])
nonzero = [p for p in served_series if p["teacher_cost"]]
check(
    "at least one month shows a teacher cost",
    bool(nonzero),
    f"{len(nonzero)} of {len(served_series)} months",
)
check(
    "months with a teacher cost sum to the all-time total",
    sum(p["teacher_cost"] for p in served_series) == summary.get("teacher_cost_total_da", -1),
    f"series {sum(p['teacher_cost'] for p in served_series):,} vs "
    f"total {summary.get('teacher_cost_total_da', 0):,}",
)

# ── The figures the add-payout modal pre-fills from ─────────────────────────
status, teachers = call("GET", "/teachers", token, academy)
rows = teachers.get("teachers", teachers) if isinstance(teachers, dict) else teachers
check("GET /teachers -> 200", status == 200, f"got {status}")
if rows:
    tid = rows[0]["id"]
    status, payload = call(
        "GET", f"/billing/teacher-payments?teacher_id={tid}", token, academy
    )
    check("GET /billing/teacher-payments -> 200", status == 200, f"got {status}")
    row = (payload.get("teachers") or [None])[0]
    if row:
        print(
            f"\n  prefill for {row.get('teacher_name')}: "
            f"{row['session_count']} sessions · {row['duration_hours']} h · "
            f"gross {row['gross_revenue_da']:,} DA"
        )
        for key in ("session_count", "duration_hours", "gross_revenue_da"):
            check(f"teacher-payments row carries {key}", key in row)
        check(
            "duration_hours is a number",
            isinstance(row["duration_hours"], (int, float)),
            f"got {type(row['duration_hours']).__name__}",
        )
    else:
        print("\n  (this teacher has no payout records, so no row is returned — "
              "the modal falls back to an empty form)")

print("\n" + "=" * 60)
if FAILURES:
    print(f"FAILURES ({len(FAILURES)}):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("All checks passed.")
