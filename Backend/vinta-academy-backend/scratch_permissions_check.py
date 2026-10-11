"""RBAC enforcement, proven end to end through the real app. Delete when done.

Runs against a throwaway SQLite file (never the seed database) and drives the
actual WSGI app with its test client, so what is asserted is the behaviour of
the routes as they are wired — decorators, schemas, serializers and all — not
a re-reading of the table in ``app/permissions.py``.

What it is here to catch
    * a route that was gated in the wrong order, or not at all;
    * a permission denial that answers 401 instead of 403, which the frontend
      would read as an expired session and act on by logging the user out;
    * a payload that claims a grant the server would not honour, which is how
      the client would come to render a screen it cannot use;
    * the export routes quietly remaining a way round the gated screens.

Run from the backend directory:   py scratch_permissions_check.py
"""

import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(HERE, "scratch_permissions.db")

# Set before anything imports the app factory: config reads DATABASE_URL while
# create_app() runs, and this has to win over the .env the real server uses.
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.replace(os.sep, '/')}"

from app import create_app, permissions  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import tenant_service  # noqa: E402
from flask_jwt_extended import create_access_token  # noqa: E402

FAILURES = []
CHECKS = [0]


def check(label, ok, detail=""):
    CHECKS[0] += 1
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


app = create_app()

with app.app_context():
    db.create_all()

    academy = tenant_service.create_academy(
        name="Permission Check Academy",
        email="checks@example.dz",
        password="ownerpass123",
    )
    academy_id = academy["academy_id"]

    owner = tenant_service.create_owner_profile(
        academy_id=academy_id,
        name="Owner",
        email="checks@example.dz",
        password="ownerpass123",
        pin="1111",
    )
    # Never configured: permissions is NULL, which must read as the documented
    # staff default rather than as nothing at all. This is the row that proves
    # the feature did not lock every existing staff account out.
    staff_default = tenant_service.create_staff_profile(
        academy_id=academy_id, name="Default Staff", pin="2222"
    )
    # Trusted with the desk but not the books: Billing can be opened and read,
    # payments can be taken, the profit reports and the expenses cannot.
    # `teachers.commission` is ticked so this account is the control for the
    # opposite case — same area, same level as the default staff member, with
    # the action and without it.
    staff_billing = tenant_service.create_staff_profile(
        academy_id=academy_id,
        name="Billing Clerk",
        pin="3333",
        permissions_map=permissions.parse({
            "levels": {
                "students": "manage", "teachers": "manage", "classes": "manage",
                "calendar": "manage", "attendance": "manage",
                "billing": "view", "settings": "none",
            },
            "actions": {"billing": ["payments"], "teachers": ["commission"]},
        }),
    )
    # Trusted to mint logins — the delegation path that used to be owner-only.
    # Settings is at `manage` with only the `staff` action ticked: the academy's
    # own configuration stays the owner's, the people do not.
    staff_manager = tenant_service.create_staff_profile(
        academy_id=academy_id,
        name="Office Manager",
        pin="4444",
        permissions_map=permissions.parse({
            "levels": {
                "students": "manage", "teachers": "manage", "classes": "manage",
                "calendar": "manage", "attendance": "manage",
                "billing": "none", "settings": "manage",
            },
            "actions": {"settings": ["staff"]},
        }),
    )
    db.session.commit()

    tokens = {}
    for label, user in (
        ("owner", owner),
        ("default", staff_default),
        ("billing", staff_billing),
        ("manager", staff_manager),
    ):
        tokens[label] = create_access_token(
            identity=user.id,
            additional_claims={"academy_id": academy_id, "role": user.role},
        )

    ids = {
        "owner": owner.id,
        "default": staff_default.id,
        "billing": staff_billing.id,
        "manager": staff_manager.id,
    }

client = app.test_client()


def call(method, path, as_who=None, body=None, academy=True):
    headers = {}
    if as_who:
        headers["Authorization"] = f"Bearer {tokens[as_who]}"
    if academy:
        headers["X-Academy-Id"] = academy_id
    resp = client.open(
        path,
        method=method,
        headers=headers,
        data=json.dumps(body) if body is not None else None,
        content_type="application/json",
    )
    return resp.status_code, resp


def payload(resp):
    try:
        return resp.get_json()
    except Exception:
        return None


# ── 1. The identity that travels with a token ───────────────────────────────

print("== 1. sign-in returns the identity the token belongs to ==")

status, resp = call("POST", "/api/auth/login", body={
    "email": "checks@example.dz", "password": "ownerpass123",
}, academy=False)
body = payload(resp) or {}
check("owner login -> 200", status == 200, f"got {status}")
check("owner login carries a user object", isinstance(body.get("user"), dict))
check("owner user.role == owner", (body.get("user") or {}).get("role") == "owner")
owner_perms = (body.get("user") or {}).get("permissions") or {}
check(
    "owner holds every area at manage",
    owner_perms.get("levels") == {a: "manage" for a in permissions.AREA_ORDER},
)
check(
    "owner holds every action",
    owner_perms.get("actions") == {a: list(v) for a, v in permissions.AREAS.items()},
)

status, resp = call("POST", "/api/auth/verify-pin", academy=True, body={
    "user_id": ids["billing"], "pin": "3333",
})
body = payload(resp) or {}
check("verify-pin -> 200", status == 200, f"got {status}")
check("verify-pin carries a user object", isinstance(body.get("user"), dict))
# The bug this closes: the client keeps whatever identity it is handed here for
# the rest of the session, so a picker that returned no user left an owner's
# role (and permissions) attached to a staff token.
check(
    "verify-pin user.role is the staff member's, not the previous session's",
    (body.get("user") or {}).get("role") == "staff",
    f"got {(body.get('user') or {}).get('role')}",
)
check(
    "verify-pin user.permissions matches that staff member's grant",
    (body.get("user") or {}).get("permissions", {}).get("levels", {}).get("billing") == "view",
)

status, resp = call("GET", "/api/auth/me", as_who="default")
body = payload(resp) or {}
check("/auth/me -> 200", status == 200, f"got {status}")
check("/auth/me carries permissions", isinstance(body.get("permissions"), dict))
check(
    "/auth/me reports the staff default for an unconfigured account",
    body.get("permissions", {}).get("levels") == permissions.DEFAULT_STAFF,
)
check(
    "/auth/me reports no money for the staff default",
    body.get("permissions", {}).get("levels", {}).get("billing") == "none",
)

# ── 2. The served catalogue ─────────────────────────────────────────────────

print("\n== 2. the catalogue served to the screen ==")

status, resp = call("GET", "/api/settings/permissions", as_who="owner")
body = payload(resp)
check("GET /settings/permissions -> 200 for an owner", status == 200, f"got {status}")
check("served catalogue equals app/permissions.catalogue()", body == permissions.catalogue())
areas = (body or {}).get("areas", [])
check("catalogue lists every area in order", [a.get("key") for a in areas] == list(permissions.AREA_ORDER))
check("catalogue carries the three levels", (body or {}).get("levels") == list(permissions.LEVELS))
check("catalogue carries the staff default", (body or {}).get("default") == permissions.DEFAULT_STAFF)

# ── 3. Refusals, area by area ───────────────────────────────────────────────

print("\n== 3. a default staff account: day-to-day open, money and settings shut ==")

for path in ["/api/students", "/api/classes", "/api/teachers", "/api/calendar/week",
             "/api/settings/academy"]:
    status, _ = call("GET", path, as_who="default")
    check(f"default staff GET {path} -> 200", status == 200, f"got {status}")

for path in ["/api/billing/records", "/api/billing/students", "/api/billing/expenses",
             "/api/billing/financial-summary", "/api/billing/stats",
             "/api/settings/staff", "/api/settings/permissions",
             "/api/settings/billing-config", "/api/settings/automations"]:
    status, resp = call("GET", path, as_who="default")
    check(f"default staff GET {path} -> 403", status == 403, f"got {status}")
    # If any of these came back 401 the frontend would clear the session and
    # throw the user out mid-task, instead of showing them a refusal.
    check(f"   ... and it is 403, not 401", status != 401, f"got {status}")

print("\n== 4. the export routes are not a way round the gated screens ==")
for path in ["/api/analytics/export/billing", "/api/settings/export/billing",
             "/api/analytics/export/teacher_hours"]:
    status, _ = call("GET", path, as_who="default")
    check(f"default staff GET {path} -> 403", status == 403, f"got {status}")
# The ones a staff member legitimately uses must still work: the Data & Export
# panel offers them, and gating the whole route would have taken them away.
for path in ["/api/analytics/export/students", "/api/settings/export/students"]:
    status, _ = call("GET", path, as_who="default")
    check(f"default staff GET {path} -> 200", status == 200, f"got {status}")

print("\n== 5. reads that serve two masters still open for the front desk ==")
# Billing is switched off for this account, but "who is paid up" is the front
# desk's working knowledge while a check-in is being taken.
for path in ["/api/billing/subscriptions"]:
    status, _ = call("GET", path, as_who="default")
    check(f"default staff GET {path} -> 200 (classes.view satisfies it)", status == 200, f"got {status}")
# Deliberately tenant-only: three staff-facing screens read it (dashboard,
# session check-in, teacher drawer), so gating it would break check-in.
status, _ = call("GET", "/api/billing/payouts", as_who="default")
check("default staff GET /billing/payouts -> 200 (by design)", status == 200, f"got {status}")

# ── 6. Levels and actions are independent ───────────────────────────────────

print("\n== 6. the action toggles bite, at the level they were ticked ==")

status, resp = call("POST", "/api/teachers", as_who="owner", body={
    "first_name": "Check", "last_name": "Teacher",
})
created = payload(resp) or {}
teacher_id = created.get("id")
check("owner POST /teachers -> 201", status == 201, f"got {status}")

# Same area, same level — one has the action, one does not.
status, _ = call("PUT", f"/api/teachers/{teacher_id}", as_who="default",
                 body={"first_name": "Renamed"})
check("default staff (teachers.manage, no commission) rename -> 200", status == 200, f"got {status}")

status, _ = call("PUT", f"/api/teachers/{teacher_id}", as_who="default",
                 body={"commission_value": 500})
check("default staff setting a teacher's pay -> 403", status == 403, f"got {status}")

status, _ = call("PUT", f"/api/teachers/{teacher_id}", as_who="billing",
                 body={"commission_value": 500})
check("staff with teachers.manage + commission -> not refused", status != 403, f"got {status}")

print("\n== 7. a view-level grant reads but does not work ==")
status, _ = call("GET", "/api/billing/students", as_who="billing")
check("billing clerk GET /billing/students -> 200", status == 200, f"got {status}")
for path in ["/api/billing/records", "/api/billing/expenses", "/api/billing/financial-summary"]:
    status, _ = call("GET", path, as_who="billing")
    check(f"billing clerk GET {path} -> 403 (no reports/expenses tick)", status == 403, f"got {status}")
status, _ = call("POST", "/api/billing/expenses", as_who="billing",
                 body={"label": "x", "amount_da": 100, "category": "OTHER"})
check("billing clerk POST /billing/expenses -> 403", status == 403, f"got {status}")

# ── 8. Delegating staff management ──────────────────────────────────────────

print("\n== 8. an account trusted with staff management can use it ==")

status, _ = call("GET", "/api/settings/staff", as_who="manager")
check("office manager GET /settings/staff -> 200", status == 200, f"got {status}")
status, resp = call("GET", "/api/settings/staff", as_who="manager")
rows = (payload(resp) or {}).get("staff", [])
check("staff list carries email", all("email" in r for r in rows))
check("staff list carries permissions", all("permissions" in r for r in rows))
owner_row = next((r for r in rows if r.get("role") == "owner"), None)
check("staff list includes the owner's row", owner_row is not None)
check(
    "the owner's row reads as full access",
    (owner_row or {}).get("permissions", {}).get("levels") == {a: "manage" for a in permissions.AREA_ORDER},
)

status, _ = call("POST", "/api/settings/staff", as_who="manager", body={
    "name": "No Pin Given", "pin": "5555", "owner_pin": "wrong",
})
check("creating staff with a wrong caller PIN -> 403", status == 403, f"got {status}")

status, resp = call("POST", "/api/settings/staff", as_who="manager", body={
    "name": "Address Only", "pin": "5555", "owner_pin": "4444",
    "email": "address.only@example.dz",
})
check("an email without a password -> 400", status == 400, f"got {status}")

status, resp = call("POST", "/api/settings/staff", as_who="manager", body={
    "name": "Password Only", "pin": "5555", "owner_pin": "4444",
    "password": "somepassword1",
})
check("a password without an address -> 400", status == 400, f"got {status}")

status, resp = call("POST", "/api/settings/staff", as_who="manager", body={
    "name": "Short", "pin": "5555", "owner_pin": "4444",
    "email": "short@example.dz", "password": "abc",
})
check("a password under the minimum -> 400", status == 400, f"got {status}")

status, resp = call("POST", "/api/settings/staff", as_who="manager", body={
    "name": "Front Desk", "pin": "5555", "owner_pin": "4444",
    "email": "frontdesk@example.dz", "password": "frontdesk123",
    "permissions": {
        "levels": {
            "students": "manage", "teachers": "view", "classes": "manage",
            "calendar": "manage", "attendance": "manage",
            "billing": "view", "settings": "none",
        },
        "actions": {"billing": ["payments"]},
    },
})
body = payload(resp) or {}
check("creating a staff member with an address -> 201", status == 201, f"got {status}")
check("response carries the email", body.get("email") == "frontdesk@example.dz")
check(
    "response carries the grant that was asked for",
    body.get("permissions", {}).get("levels", {}).get("billing") == "view",
)
check(
    "response carries the ticked action",
    body.get("permissions", {}).get("actions", {}).get("billing") == ["payments"],
)
new_staff_id = body.get("id")

status, _ = call("POST", "/api/settings/staff", as_who="manager", body={
    "name": "Duplicate", "pin": "5555", "owner_pin": "4444",
    "email": "frontdesk@example.dz", "password": "frontdesk123",
})
check("a duplicate address -> 409", status == 409, f"got {status}")

print("\n== 9. the new account can actually sign in with what it was given ==")
status, resp = call("POST", "/api/auth/login", academy=False, body={
    "email": "frontdesk@example.dz", "password": "frontdesk123",
})
body = payload(resp) or {}
check("staff email + password login -> 200", status == 200, f"got {status}")
check("staff login returns a staff role", (body.get("user") or {}).get("role") == "staff")

status, _ = call("POST", "/api/auth/login", academy=False, body={
    "email": "frontdesk@example.dz", "password": "wrongpassword",
})
check("staff login with the wrong password -> 401", status == 401, f"got {status}")

status, resp = call("POST", "/api/auth/login", academy=False, body={
    "email": "frontdesk@example.dz", "password": "frontdesk123",
})
front_token = (payload(resp) or {}).get("access_token")
check("the new staff account's token was issued", bool(front_token))
resp = client.open(
    "/api/billing/students",
    method="GET",
    headers={"Authorization": f"Bearer {front_token}", "X-Academy-Id": academy_id},
)
check("the new staff token is honoured on a permitted route -> 200",
      resp.status_code == 200, f"got {resp.status_code}")
resp = client.open(
    "/api/billing/records",
    method="GET",
    headers={"Authorization": f"Bearer {front_token}", "X-Academy-Id": academy_id},
)
check("... and refused on a gated one -> 403",
      resp.status_code == 403, f"got {resp.status_code}")

# ── 10. Editing permissions ─────────────────────────────────────────────────

print("\n== 10. changing someone's permissions afterwards ==")

status, _ = call("PUT", f"/api/settings/staff/{ids['default']}", as_who="owner", body={
    "permissions": {
        "levels": {a: "manage" for a in permissions.AREA_ORDER},
        "actions": {},
    },
})
check("owner widening a staff account -> 200", status == 200, f"got {status}")
status, _ = call("GET", "/api/billing/students", as_who="default")
check("every area at manage opens Billing itself -> 200", status == 200, f"got {status}")
# The point of the two axes: turning Billing all the way up still does not hand
# over the profit reports, because the reports are a tick and not a level. This
# is what lets an owner say "she may take money at the desk, she may not see
# what the school earns" without withholding Billing altogether.
status, _ = call("GET", "/api/billing/records", as_who="default")
check("... but the reports need their own tick -> 403", status == 403, f"got {status}")

status, _ = call("PUT", f"/api/settings/staff/{ids['default']}", as_who="owner", body={
    "permissions": {
        "levels": {a: "manage" for a in permissions.AREA_ORDER},
        "actions": {"billing": ["reports"]},
    },
})
check("owner ticking reports -> 200", status == 200, f"got {status}")
status, _ = call("GET", "/api/billing/records", as_who="default")
check("the tick is what opens the reports -> 200", status == 200, f"got {status}")

status, _ = call("PUT", f"/api/settings/staff/{ids['default']}", as_who="owner", body={
    "permissions": {"levels": dict(permissions.DEFAULT_STAFF), "actions": {}},
})
check("owner narrowing it again -> 200", status == 200, f"got {status}")
status, _ = call("GET", "/api/billing/records", as_who="default")
check("the narrowed account is refused again -> 403", status == 403, f"got {status}")
status, _ = call("GET", "/api/students", as_who="default")
check("... and the day-to-day areas are still open -> 200", status == 200, f"got {status}")

# A toggle this release does not know about is dropped, never stored. A client
# one release behind must not be able to grant something the server has no rule
# for — its failure mode has to be a narrower account, never a wider one.
status, _ = call("PUT", f"/api/settings/staff/{ids['default']}", as_who="owner", body={
    "permissions": {
        "levels": {**{a: "manage" for a in permissions.AREA_ORDER}, "vault": "manage"},
        "actions": {"billing": ["payments", "teleport"], "nowhere": ["x"]},
    },
})
check("a permission map naming an unknown area/action -> 200", status == 200, f"got {status}")
status, resp = call("GET", "/api/settings/staff", as_who="owner")
row = next((r for r in (payload(resp) or {}).get("staff", []) if r.get("id") == ids["default"]), {})
check("the unknown area was dropped, not stored",
      "vault" not in (row.get("permissions", {}).get("levels") or {}))
check("the unknown action was dropped, not stored",
      (row.get("permissions", {}).get("actions", {}).get("billing")) == ["payments"])
check("the known action it arrived with was kept",
      "payments" in (row.get("permissions", {}).get("actions", {}).get("billing") or []))

status, _ = call("PUT", f"/api/settings/staff/{ids['default']}", as_who="owner", body={
    "permissions": {"levels": dict(permissions.DEFAULT_STAFF), "actions": {}},
})
check("restored to the staff default -> 200", status == 200, f"got {status}")

status, _ = call("PUT", f"/api/settings/staff/{ids['owner']}", as_who="owner", body={
    "permissions": {"levels": {a: "none" for a in permissions.AREA_ORDER}, "actions": {}},
})
check("setting permissions on an owner row -> 400 (nothing to change)", status == 400, f"got {status}")
status, _ = call("GET", "/api/billing/records", as_who="owner")
check("the owner is still the owner -> 200", status == 200, f"got {status}")

status, _ = call("PUT", f"/api/settings/staff/{new_staff_id}", as_who="owner", body={
    "permissions": {"levels": dict(permissions.DEFAULT_STAFF), "actions": {}},
})
check("re-sending an unchanged address of the same row -> 200 (not a self-clash)",
      status == 200, f"got {status}")

status, _ = call("PUT", f"/api/settings/staff/{new_staff_id}", as_who="owner", body={
    "email": "checks@example.dz",
})
check("taking the owner's address -> 409", status == 409, f"got {status}")

status, _ = call("PUT", f"/api/settings/staff/{new_staff_id}", as_who="owner", body={
    "email": "",
})
check("clearing an address -> 200", status == 200, f"got {status}")
status, _ = call("POST", "/api/auth/login", academy=False, body={
    "email": "frontdesk@example.dz", "password": "frontdesk123",
})
check("a cleared address can no longer sign in -> 401", status == 401, f"got {status}")

# ── 11. The owner is never locked out ───────────────────────────────────────

print("\n== 11. the owner is never locked out of their own academy ==")
for path in ["/api/students", "/api/billing/records", "/api/billing/expenses",
             "/api/settings/staff", "/api/settings/academy", "/api/settings/permissions",
             "/api/teachers"]:
    status, _ = call("GET", path, as_who="owner")
    check(f"owner GET {path} -> 200", status == 200, f"got {status}")

print("\n== 12. no token still means 401, not 403 ==")
for path in ["/api/students", "/api/billing/records", "/api/settings/staff"]:
    status, _ = call("GET", path)
    check(f"anonymous GET {path} -> 401", status == 401, f"got {status}")

# ── 13. The frontend mirror still agrees with the server ────────────────────
#
# `vinta-school-os/src/lib/permissions.ts` is the client-side twin of
# `app/permissions.py`, and the navigation is drawn from it. The two are kept
# apart on purpose — the app cannot wait for a request before it knows which
# pages to offer — so they can drift, and this is the guard against it.
#
# The tables are read out of the TypeScript source rather than imported,
# because there is no way to import TypeScript into Python and no build step
# here to produce one. That makes this brittle by construction: a reformatted
# table would read as a mismatch. That is the safe direction for the failure
# to run in — it reports a drift that may not exist rather than missing one
# that does.

print("\n== 13. the frontend mirror still matches the server ==")

TS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "vinta-school-os", "src", "lib", "permissions.ts",
)


def _ts_block(name):
    """The source of a `const NAME = { ... }` or `[ ... ]` literal."""
    try:
        with open(TS_PATH, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    start = text.find(name)
    if start == -1:
        return None
    open_at = text.find("=", start)
    if open_at == -1:
        return None
    opener = text[open_at + 1:].lstrip()[:1]
    if opener not in "{[":
        return None
    closer = "}" if opener == "{" else "]"
    begin = text.find(opener, open_at)
    depth = 0
    for i in range(begin, len(text)):
        if text[i] in "{[(":
            depth += 1
        elif text[i] in "}])":
            depth -= 1
            if depth == 0:
                return text[begin:i + 1]
    return None


check("the frontend mirror is present", os.path.exists(TS_PATH), TS_PATH)

order_block = _ts_block("PERMISSION_AREA_ORDER")
check("the mirror declares an area order", order_block is not None)
if order_block:
    mirrored_areas = re.findall(r"'([a-z_]+)'", order_block)
    check(
        "mirrored area order equals the server's",
        mirrored_areas == list(permissions.AREA_ORDER),
        f"mirror={mirrored_areas} server={list(permissions.AREA_ORDER)}",
    )

actions_block = _ts_block("PERMISSION_AREA_ACTIONS")
check("the mirror declares per-area actions", actions_block is not None)
if actions_block:
    mirrored_actions = {}
    for area, inner in re.findall(r"(\w+):\s*\[([^\]]*)\]", actions_block):
        mirrored_actions[area] = re.findall(r"'([a-z_]+)'", inner)
    check(
        "mirrored actions equal the server's, area by area",
        mirrored_actions == {k: list(v) for k, v in permissions.AREAS.items()},
        f"mirror={mirrored_actions} server={dict(permissions.AREAS)}",
    )

default_block = _ts_block("DEFAULT_STAFF_PERMISSIONS")
check("the mirror declares a staff default", default_block is not None)
if default_block:
    mirrored_default = dict(re.findall(r"(\w+):\s*'(\w+)'", default_block))
    check(
        "mirrored staff default equals the server's",
        mirrored_default == dict(permissions.DEFAULT_STAFF),
        f"mirror={mirrored_default} server={dict(permissions.DEFAULT_STAFF)}",
    )

levels_block = _ts_block("PERMISSION_LEVELS")
check("the mirror declares the levels", levels_block is not None)
if levels_block:
    mirrored_levels = re.findall(r"'(\w+)'", levels_block)
    check(
        "mirrored levels equal the server's",
        mirrored_levels == list(permissions.LEVELS),
        f"mirror={mirrored_levels} server={list(permissions.LEVELS)}",
    )

# Every area and action the mirror knows must have a translated label in all
# three dictionaries, or the editor renders a raw key where a word belongs.
LOCALES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "vinta-school-os", "src", "i18n", "locales",
)
for lang in ("en", "fr", "ar"):
    try:
        with open(os.path.join(LOCALES, lang, "settings.json"), encoding="utf-8") as fh:
            settings_catalogue = json.load(fh).get("permissions", {})
    except (OSError, ValueError) as exc:
        check(f"{lang}/settings.json carries the permission labels", False, str(exc))
        continue

    missing = [
        f"area.{area}" for area in permissions.AREA_ORDER
        if area not in (settings_catalogue.get("area") or {})
    ]
    for area, acts in permissions.AREAS.items():
        for action in acts:
            if action not in ((settings_catalogue.get("action") or {}).get(area) or {}):
                missing.append(f"action.{area}.{action}")
            if action not in ((settings_catalogue.get("actionHint") or {}).get(area) or {}):
                missing.append(f"actionHint.{area}.{action}")
    for level in permissions.LEVELS:
        if level not in (settings_catalogue.get("level") or {}):
            missing.append(f"level.{level}")
        if level not in (settings_catalogue.get("levelShort") or {}):
            missing.append(f"levelShort.{level}")
    check(f"{lang}/settings.json labels every area, action and level", not missing, ", ".join(missing))

print("\n" + "=" * 62)
print(f"{CHECKS[0]} checks, {len(FAILURES)} failed")

with app.app_context():
    db.session.remove()
    db.engine.dispose()
try:
    os.remove(DB_FILE)
except OSError:
    pass  # Left behind only if a handle is still open; allowlisted by the seeder.

if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("All checks passed.")
