"""
Live RBAC smoke test — drives the running dev server on :5000 the way the
frontend does, then removes what it created.

This is not a replacement for ``scratch_permissions_check.py`` (which drives a
throwaway database and asserts far more). It exists to prove one thing the
in-process check cannot: that the requests the *browser* actually sends are
answered the way the UI assumes. Run it with the dev server up.
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:5000/api"
OWNER_EMAIL = "direction@academie-el-feth.dz"
OWNER_PASSWORD = "owner1234"
TEST_EMAIL = "rbac.smoke@academie-el-feth.dz"
TEST_PASSWORD = "smoke-pass-1234"

FAILURES = []
CHECKS = [0]


def check(label, ok, detail=""):
    CHECKS[0] += 1
    mark = "ok " if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{mark}] {label}{suffix}")
    if not ok:
        FAILURES.append(label)


def call(method, path, token=None, body=None, academy=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if academy:
        req.add_header("X-Academy-Id", academy)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"raw": raw}
    except urllib.error.URLError as exc:
        print(f"\n  the dev server is not answering on {BASE} ({exc})")
        sys.exit(2)


print("== the owner signs in the way the browser does ==")
status, body = call("POST", "/auth/login", body={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
check("POST /auth/login -> 200", status == 200, f"got {status}")
if status != 200:
    print(f"  {body}")
    sys.exit(1)

token = body["access_token"]
academy = body["academy_id"]
owner_identity = body.get("user")
check("the login answer carries a `user` object", isinstance(owner_identity, dict))
check("... whose role is owner", (owner_identity or {}).get("role") == "owner")
check(
    "... and whose grant is full",
    all(v == "manage" for v in ((owner_identity or {}).get("permissions", {}).get("levels") or {}).values())
    and bool((owner_identity or {}).get("permissions", {}).get("levels")),
    json.dumps((owner_identity or {}).get("permissions", {}).get("levels")),
)

print("\n== the catalogue the editor is drawn from ==")
status, catalogue = call("GET", "/settings/permissions", token, academy=academy)
check("GET /settings/permissions -> 200 for the owner", status == 200, f"got {status}")
check("it lists seven areas", len((catalogue or {}).get("areas", [])) == 7)
check("it lists three levels", (catalogue or {}).get("levels") == ["none", "view", "manage"])

print("\n== create a staff member the way the Add modal does ==")
grant = {
    "levels": {
        "students": "manage", "teachers": "manage", "classes": "manage",
        "calendar": "view", "attendance": "manage",
        "billing": "view", "settings": "none",
    },
    "actions": {"billing": ["reports"]},
}
status, created = call(
    "POST", "/settings/staff", token,
    body={
        "name": "RBAC Smoke",
        "pin": "4242",
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "owner_pin": "1234",
        "permissions": grant,
    },
    academy=academy,
)
check("POST /settings/staff -> 201", status == 201, f"got {status} {created if status != 201 else ''}")
staff_id = (created or {}).get("id")

print("\n== the staff list reads as the screen needs it ==")
status, listing = call("GET", "/settings/staff", token, academy=academy)
check("GET /settings/staff -> 200", status == 200, f"got {status}")
rows = {r["id"]: r for r in (listing or {}).get("staff", [])}
check("the new member is listed", staff_id in rows)
row = rows.get(staff_id, {})
check("... with its email", row.get("email") == TEST_EMAIL, str(row.get("email")))
check("... and a resolved grant", row.get("permissions", {}).get("levels", {}).get("billing") == "view")
check("... keeping only the ticked action", row.get("permissions", {}).get("actions", {}).get("billing") == ["reports"])
owner_row = next((r for r in rows.values() if r["role"] == "owner"), {})
check(
    "the owner's own row reads as full access",
    all(v == "manage" for v in owner_row.get("permissions", {}).get("levels", {}).values()),
)

print("\n== that staff member signs in with the address and password given ==")
status, sbody = call("POST", "/auth/login", body={"email": TEST_EMAIL, "password": TEST_PASSWORD})
check("POST /auth/login as the staff member -> 200", status == 200, f"got {status}")
stoken = (sbody or {}).get("access_token")
identity = (sbody or {}).get("user") or {}
check("the answer identifies the staff member, not the last session", identity.get("role") == "staff")
check("... carrying the granted billing level", identity.get("permissions", {}).get("levels", {}).get("billing") == "view")
check("... and settings still shut", identity.get("permissions", {}).get("levels", {}).get("settings") == "none")
check("... and the granted reports tick", identity.get("permissions", {}).get("actions", {}).get("billing") == ["reports"])

print("\n== and is answered the way the UI's guards assume ==")
for path, expected in [
    ("/students", 200),
    ("/classes", 200),
    ("/teachers", 200),
    ("/billing/records", 200),      # billing is 'view'
    ("/billing/expenses", 403),     # expenses was not ticked
    ("/settings/staff", 403),       # settings is 'none'
    ("/settings/permissions", 403),
]:
    status, _ = call("GET", path, stoken, academy=academy)
    check(f"staff GET {path} -> {expected}", status == expected, f"got {status}")
    check(f"   ... not 401 on {path}", status != 401, f"got {status}")

print("\n== /auth/me agrees with the sign-in answer ==")
status, me = call("GET", "/auth/me", stoken, academy=academy)
check("GET /auth/me -> 200", status == 200, f"got {status}")
check("its role matches", (me or {}).get("role") == "staff")
check("its grant matches", (me or {}).get("permissions", {}).get("levels", {}) == identity.get("permissions", {}).get("levels"))

print("\n== cleaning up ==")
if staff_id:
    status, _ = call("DELETE", f"/settings/staff/{staff_id}", token, academy=academy)
    check("DELETE the smoke account -> 200", status == 200, f"got {status}")
    status, _ = call("GET", f"/settings/staff", token, academy=academy)
    remaining = {r["id"] for r in ((_ or {}).get("staff") or [])}
    check("it is gone from the list", staff_id not in remaining)

print("\n" + "=" * 62)
print(f"{CHECKS[0]} checks, {len(FAILURES)} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("All checks passed.")
