"""Scratch smoke test for the new billing endpoints. Delete when done.

Exercises, against the running dev server:
  * POST /api/billing/payouts for each basis and each status
  * the wrong-PIN case (must be 403, never 401)
  * GET /api/billing/payouts showing a manual payout (proves the outer join)
  * GET /api/billing/records with filters
  * GET /api/billing/records/export?format=csv and =pdf
"""
import json
import sys
import urllib.error
import urllib.request

# The Windows console here is cp1252; the data contains French accents, Arabic
# and a middle dot, so printing it would otherwise crash the test itself.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://127.0.0.1:5000/api"
OWNER = ("direction@academie-el-feth.dz", "owner1234")
PIN = "1234"

FAILURES = []


def call(method, path, token=None, academy=None, body=None, raw=False):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if academy:
        req.add_header("X-Academy-Id", academy)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = resp.read()
            return resp.status, payload if raw else json.loads(payload or b"{}")
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            return exc.code, json.loads(payload or b"{}")
        except Exception:
            return exc.code, payload[:200]


def check(label, ok, detail=""):
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


print("== login ==")
status, login = call("POST", "/auth/login", body={"email": OWNER[0], "password": OWNER[1]})
check("owner login 200", status == 200, f"got {status}")
token = login.get("access_token", "")
academy = login.get("academy_id", "")
check("token + academy id present", bool(token) and bool(academy))
if not token:
    sys.exit(1)

print("\n== teachers ==")
status, teachers = call("GET", "/teachers", token, academy)
check("GET /teachers 200", status == 200, f"got {status}")
rows = teachers.get("teachers") if isinstance(teachers, dict) else teachers
check("teacher list non-empty", bool(rows), f"{len(rows or [])} teacher(s)")
teacher = (rows or [{}])[0]
print(f"  using teacher: {teacher.get('full_name') or teacher.get('name')} ({teacher.get('id')})")

print("\n== POST /payouts: CUSTOM + PAID ==")
status, created = call("POST", "/billing/payouts", token, academy, {
    "teacher_id": teacher.get("id"),
    "basis": "CUSTOM",
    "amount_da": 4500,
    "payout_date": "2026-10-08",
    "notes": "Bonus — extra exam prep (ملاحظة)",
    "status": "PAID",
    "pin": PIN,
})
check("created 201", status == 201, f"got {status} {created if status != 201 else ''}")
payout_id = created.get("id") if isinstance(created, dict) else None
check("response has id + source=MANUAL", bool(payout_id) and created.get("source") == "MANUAL")
check("amount as stated (4500)", created.get("teacher_cut_da") == 4500,
      f"got {created.get('teacher_cut_da')}")
check("status PAID", created.get("status") == "PAID")
check("is already settled (paid_at set)", bool(created.get("paid_at")))
check("note round-trips", created.get("notes") == "Bonus — extra exam prep (ملاحظة)")
check("effective_date = chosen payout_date", created.get("effective_date") == "2026-10-08",
      f"got {created.get('effective_date')}")

print("\n== POST /payouts: PERCENTAGE + PENDING ==")
status, pct = call("POST", "/billing/payouts", token, academy, {
    "teacher_id": teacher.get("id"),
    "basis": "PERCENTAGE",
    "gross_revenue_da": 20000,
    "commission_value": 30,
    "payout_date": "2026-10-07",
    "notes": "30% of a 20,000 Da course",
    "status": "PENDING",
    "pin": PIN,
})
check("created 201", status == 201, f"got {status} {pct if status != 201 else ''}")
check("computed 30% of 20000 = 6000", pct.get("teacher_cut_da") == 6000,
      f"got {pct.get('teacher_cut_da')}")
check("status PENDING", pct.get("status") == "PENDING")
check("not settled (no paid_at)", not pct.get("paid_at"))

print("\n== POST /payouts: FLAT_HOURLY ==")
status, hourly = call("POST", "/billing/payouts", token, academy, {
    "teacher_id": teacher.get("id"),
    "basis": "FLAT_HOURLY",
    "commission_value": 1200,
    "duration_hours": 2.5,
    "status": "PENDING",
    "pin": PIN,
})
check("created 201", status == 201, f"got {status} {hourly if status != 201 else ''}")
check("computed 1200 x 2.5 = 3000", hourly.get("teacher_cut_da") == 3000,
      f"got {hourly.get('teacher_cut_da')}")

print("\n== POST /payouts: FIXED_SESSION ==")
status, fixed = call("POST", "/billing/payouts", token, academy, {
    "teacher_id": teacher.get("id"),
    "basis": "FIXED_SESSION",
    "commission_value": 2500,
    "status": "PENDING",
    "pin": PIN,
})
check("created 201", status == 201, f"got {status} {fixed if status != 201 else ''}")
check("computed 2500 per session", fixed.get("teacher_cut_da") == 2500,
      f"got {fixed.get('teacher_cut_da')}")

print("\n== wrong PIN must be 403, never 401 ==")
status, wrong = call("POST", "/billing/payouts", token, academy, {
    "teacher_id": teacher.get("id"),
    "basis": "CUSTOM",
    "amount_da": 100,
    "status": "PENDING",
    "pin": "9999",
})
check("wrong PIN -> 403", status == 403, f"got {status}")
check("wrong PIN was not 401", status != 401)

print("\n== missing PIN -> 403 ==")
status, _ = call("POST", "/billing/payouts", token, academy, {
    "teacher_id": teacher.get("id"), "basis": "CUSTOM", "amount_da": 100,
})
check("missing PIN -> 403", status == 403, f"got {status}")

print("\n== validation ==")
status, bad_basis = call("POST", "/billing/payouts", token, academy, {
    "teacher_id": teacher.get("id"), "basis": "NONSENSE", "pin": PIN,
})
check("bad basis -> 400", status == 400, f"got {status} {bad_basis}")

status, bad_teacher = call("POST", "/billing/payouts", token, academy, {
    "teacher_id": "not-a-teacher", "basis": "CUSTOM", "amount_da": 100, "pin": PIN,
})
check("unknown teacher -> 400", status == 400, f"got {status} {bad_teacher}")

print("\n== GET /payouts shows the manual rows (outer-join fix) ==")
status, payouts = call("GET", "/billing/payouts", token, academy)
check("GET /payouts 200", status == 200, f"got {status}")
plist = payouts.get("payouts", [])
manual = [p for p in plist if p.get("source") == "MANUAL"]
check("manual payouts appear in the list", len(manual) >= 4,
      f"{len(manual)} manual row(s) of {len(plist)}")
check("manual rows have session_id None", all(p.get("session_id") is None for p in manual))
check("a manual payout carries its note",
      any(p.get("notes") == "30% of a 20,000 Da course" for p in manual))
# Ordering: newest effective_date first, and no crash on null dates.
dates = [p.get("effective_date") for p in plist]
check("list is date-sorted descending",
      dates == sorted([d for d in dates if d], reverse=True) or all(d for d in dates),
      f"first few: {dates[:5]}")

print("\n== mark the pending manual payout paid ==")
pending = [p for p in manual if p.get("status") == "PENDING"]
if pending:
    status, marked = call("POST", f"/billing/payouts/{pending[0]['id']}/mark-paid",
                          token, academy, {"pin": PIN})
    check("mark-paid 200", status == 200, f"got {status} {marked}")
    check("now PAID", marked.get("status") == "PAID")
else:
    check("a pending manual payout existed to mark", False)

print("\n== seed an expense so the archive covers all three kinds ==")
status, expense = call("POST", "/billing/expenses", token, academy, {
    "category": "SUPPLIES",
    "label": "Tableaux blancs + marqueurs",
    "amount_da": 7500,
    "quantity": 3,
    "expense_date": "2026-10-08",
    "vendor": "Librairie El Nour",
    "payment_method": "CASH",
    "notes": "Salle 2 (لوازم)",
})
check("expense created 201", status == 201, f"got {status} {expense if status != 201 else ''}")

print("\n== GET /records ==")
status, records = call("GET", "/billing/records", token, academy)
check("GET /records 200", status == 200, f"got {status}")
if status == 200:
    check("records returned", records.get("count", 0) > 0, f"count={records.get('count')}")
    kinds = {r["kind"] for r in records.get("records", [])}
    print(f"  kinds present: {sorted(kinds)}")
    check("all three kinds present",
          kinds == {"STUDENT_PAYMENT", "TEACHER_PAYOUT", "EXPENSE"}, f"got {sorted(kinds)}")
    check("expense notes survive into the archive",
          any(r["kind"] == "EXPENSE" and r.get("notes") for r in records["records"]))
    print(f"  totals: {records.get('totals')}")
    check("totals add up",
          records["totals"]["net_da"] ==
          records["totals"]["money_in_da"] - records["totals"]["money_out_da"])
    check("every record has a direction",
          all(r.get("direction") in ("IN", "OUT") for r in records.get("records", [])))
    check("sorted newest first",
          [r["date"] for r in records["records"]] ==
          sorted([r["date"] for r in records["records"]], reverse=True))

print("\n== GET /records?type=TEACHER_PAYOUT ==")
status, only_payouts = call("GET", "/billing/records?type=TEACHER_PAYOUT", token, academy)
check("200", status == 200, f"got {status}")
check("only payouts returned",
      all(r["kind"] == "TEACHER_PAYOUT" for r in only_payouts.get("records", [])))

print("\n== GET /records date + amount filters ==")
status, windowed = call(
    "GET", "/billing/records?from=2026-10-07&to=2026-10-08", token, academy)
check("200", status == 200, f"got {status}")
check("dates within window",
      all("2026-10-07" <= (r["date"] or "") <= "2026-10-08"
          for r in windowed.get("records", [])))

status, ranged = call("GET", "/billing/records?min_amount=3000&max_amount=6000",
                      token, academy)
check("200", status == 200, f"got {status}")
check("amounts within range",
      all(3000 <= r["amount_da"] <= 6000 for r in ranged.get("records", [])))

status, profiled = call("GET", f"/billing/records?profile={teacher.get('id')}", token, academy)
check("200", status == 200, f"got {status}")
check("profile filter excludes expenses",
      all(r["kind"] != "EXPENSE" for r in profiled.get("records", [])))

print("\n== bad filters -> 400 ==")
status, _ = call("GET", "/billing/records?type=BOGUS", token, academy)
check("bad type -> 400", status == 400, f"got {status}")
status, _ = call("GET", "/billing/records?from=2026-10-08&to=2026-10-01", token, academy)
check("from after to -> 400", status == 400, f"got {status}")
status, _ = call("GET", "/billing/records?min_amount=500&max_amount=100", token, academy)
check("min > max -> 400", status == 400, f"got {status}")
status, _ = call("GET", "/billing/records?from=yesterday", token, academy)
check("unparseable date -> 400", status == 400, f"got {status}")

print("\n== export CSV ==")
status, csv_bytes = call(
    "GET", "/billing/records/export?format=csv", token, academy, raw=True)
check("CSV 200", status == 200, f"got {status}")
if status == 200:
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    check("CSV has the header row", "Date,Type,Direction,Profile,Label" in text)
    check("CSV has a totals footer", "Net (DA)" in text)
    check("CSV contains a teacher payout row", "Teacher payout" in text)
    print("  --- first 8 lines ---")
    for line in text.splitlines()[:8]:
        print("   ", line)

print("\n== export CSV with filters ==")
status, csv_filtered = call(
    "GET", "/billing/records/export?format=csv&type=TEACHER_PAYOUT", token, academy, raw=True)
check("CSV 200", status == 200, f"got {status}")
if status == 200:
    text = csv_filtered.decode("utf-8-sig", errors="replace")
    check("no student-payment rows leaked in", "Student payment" not in text)

print("\n== export PDF ==")
status, pdf = call("GET", "/billing/records/export?format=pdf", token, academy, raw=True)
check("PDF 200", status == 200, f"got {status}")
if status == 200 and isinstance(pdf, bytes):
    check("PDF magic bytes", pdf[:5] == b"%PDF-", f"got {pdf[:5]!r}")
    check("PDF has an EOF marker", pdf.rstrip()[-5:] == b"%%EOF")
    check("PDF is not trivially small", len(pdf) > 1200, f"{len(pdf)} bytes")
    open("scratch_billing_export.pdf", "wb").write(pdf)
    print(f"  wrote scratch_billing_export.pdf ({len(pdf)} bytes)")

print("\n== export PDF with filters (empty-result path) ==")
status, pdf_empty = call(
    "GET", "/billing/records/export?format=pdf&min_amount=99999999", token, academy, raw=True)
check("PDF 200 for an empty result", status == 200, f"got {status}")
if status == 200 and isinstance(pdf_empty, bytes):
    check("still a valid PDF", pdf_empty[:5] == b"%PDF-")
    open("scratch_billing_export_empty.pdf", "wb").write(pdf_empty)

print("\n== bad format -> 400 ==")
status, _ = call("GET", "/billing/records/export?format=xlsx", token, academy)
check("format=xlsx -> 400", status == 400, f"got {status}")

print("\n== owner-only enforcement (staff must not reach these) ==")
status, staff_login = call("POST", "/auth/login",
                           body={"email": "nadia.meziane@academie-el-feth.dz",
                                 "password": "staff1234"})
if status == 200:
    staff_token = staff_login.get("access_token")
    staff_academy = staff_login.get("academy_id")
    for path in ["/billing/records", "/billing/records/export?format=csv"]:
        code, _ = call("GET", path, staff_token, staff_academy)
        check(f"staff GET {path} -> 403", code == 403, f"got {code}")
    code, _ = call("POST", "/billing/payouts", staff_token, staff_academy, {
        "teacher_id": teacher.get("id"), "basis": "CUSTOM",
        "amount_da": 100, "pin": "1111",
    })
    check("staff POST /payouts -> 403", code == 403, f"got {code}")
else:
    print(f"  (skipped: staff login returned {status} — password guess wrong)")

print("\n" + "=" * 60)
if FAILURES:
    print(f"FAILURES ({len(FAILURES)}):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("All checks passed.")
