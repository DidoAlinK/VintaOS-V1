"""Owner-only enforcement, proven against the running dev server. Delete when done.

The billing smoke test skipped this because the seeder never calls set_password
for the two staff users, so they have no password and cannot log in. Rather than
give one a password — which would mean writing to the seed database — this mints
a staff token in-process from the app's own secret, exactly as auth_service does
for a real login, and uses it over HTTP. Nothing is written.

Expected: every gated billing endpoint answers 403 for a staff token, and 401
(not 403) for no token at all — the two are different failures and the client
reacts to them differently.
"""
import json
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://127.0.0.1:5000/api"
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
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:200]


def check(label, ok, detail=""):
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


# ── mint a staff token in-process ───────────────────────────────────────────
from flask_jwt_extended import create_access_token  # noqa: E402

from app import create_app  # noqa: E402
from app.models.user import User  # noqa: E402

app = create_app()
with app.app_context():
    staff = (
        User.query.filter_by(role="staff", is_active=True)
        .order_by(User.created_at.asc())
        .first()
    )
    if not staff:
        print("no active staff user in the database — cannot run this check")
        sys.exit(1)
    owner = (
        User.query.filter_by(role="owner", academy_id=staff.academy_id)
        .order_by(User.created_at.asc())
        .first()
    )
    print(f"staff: {staff.name} ({staff.email})  academy={staff.academy_id}")
    print(f"owner: {owner.name if owner else '?'}\n")
    staff_token = create_access_token(
        identity=staff.id,
        additional_claims={"academy_id": staff.academy_id, "role": "staff"},
    )
    academy = staff.academy_id
    owner_token = create_access_token(
        identity=owner.id,
        additional_claims={"academy_id": owner.academy_id, "role": "owner"},
    )

GETS = [
    "/billing/records",
    "/billing/records/export?format=csv",
    "/billing/records/export?format=pdf",
    "/billing/financial-summary",
    "/billing/stats",
]

print("== staff token: every gated endpoint must be 403 ==")
for path in GETS:
    status, body = call("GET", path, staff_token, academy)
    check(f"staff GET {path} -> 403", status == 403, f"got {status}")

print("\n== GET /billing/payouts is intentionally NOT owner-only ==")
# Not an oversight to be 'fixed': three staff-facing screens read it —
#   src/features/calendar/SessionCheckInModal.tsx
#   src/features/dashboard/SessionMenu.tsx
#   src/features/teachers/TeacherDrawer.tsx
# so gating it would break the session check-in flow. Asserted here so the
# intent is recorded rather than rediscovered as a surprise.
status, _ = call("GET", "/billing/payouts", staff_token, academy)
check("staff GET /billing/payouts -> 200 (by design)", status == 200, f"got {status}")

print("\n== staff token: write endpoints must be 403 ==")
# A *correct* staff-account PIN is the dangerous case: if the role gate were
# missing, a valid PIN would let staff record a payout on the school's books.
status, body = call("POST", "/billing/payouts", staff_token, academy, {
    "teacher_id": "irrelevant",
    "basis": "CUSTOM",
    "amount_da": 100,
    "status": "PENDING",
    "pin": "1111",
})
check("staff POST /billing/payouts -> 403", status == 403, f"got {status}")

print("\n== no token at all -> 401 (session expiry, not permission) ==")
for path in ["/billing/records", "/billing/records/export?format=csv"]:
    status, _ = call("GET", path, None, academy)
    check(f"anonymous GET {path} -> 401", status == 401, f"got {status}")

print("\n== the same endpoints do open for the owner token ==")
# Without this the check above would also 'pass' if the routes were simply
# broken for everyone.
for path in GETS:
    status, _ = call("GET", path, owner_token, academy)
    check(f"owner GET {path} -> 200", status == 200, f"got {status}")

print("\n" + "=" * 60)
if FAILURES:
    print(f"FAILURES ({len(FAILURES)}):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("All checks passed.")
