"""
Vinta School OS — Permission Catalogue

The one place that decides what a staff account may do, and the table the
settings screen is drawn from so the two cannot disagree.

Two roles exist: ``owner`` and ``staff``. An owner is never asked about here —
the owner holds every permission by virtue of being the owner, and nothing in
the database can take one away (:func:`effective`). Everything below is about
what a *staff* member may do, which is the owner's decision to make per person.

The shape of a permission
─────────────────────────

An **area** is a part of the app — Students, Billing, Settings, and so on.
Every area has a **level**, and some areas carry named **actions** for the
powers too sharp to hand out as part of "manage":

    level    what it opens
    ────────────────────────────────────────────────────────────────
    none     the area is shut. Its page is hidden, its endpoints refuse.
    view     the area can be read. Nothing in it can be changed.
    manage   the area can be read and worked in.

An action is granted by its own tick, on its own, as long as its area is not
``none``. Having both is the point: *"she can open Billing and take money at
the desk, but she cannot see the profit reports or touch the expenses"* is
``billing: view`` with ``payments`` ticked — a setting that neither a level nor
a tick could express alone.

Why the catalogue is data
─────────────────────────

:func:`catalogue` is served to the client by ``GET /settings/permissions`` and
drawn straight into the staff screen. The screen therefore cannot offer a
switch this module would not honour, and adding an area here is enough to make
it appear there. The frontend keeps a mirror of this table for its own
routing; ``scratch_permissions_check.py`` fetches the served copy and fails if
the two have drifted apart.

Nothing here imports the app. The module is deliberately dependency-free so
the decorators, the routes, the services and the seeder can all consult it
without a circular import.
"""
from __future__ import annotations

from typing import Any, Iterable

# ── The catalogue ─────────────────────────────────────────────────────────

LEVELS: tuple[str, ...] = ("none", "view", "manage")

#: Areas in the order the settings screen lists them. The order is the
#: document's, not a set's — a screen that reshuffles itself between releases
#: is a screen an owner has to re-read every time.
AREA_ORDER: tuple[str, ...] = (
    "students",
    "teachers",
    "classes",
    "calendar",
    "attendance",
    "billing",
    "settings",
)

#: Each area's named actions — the "big ones", as few as can be got away with.
#:
#: Every entry here is a power that an owner might reasonably want to withhold
#: from someone they otherwise trust with the whole area. Anything that is
#: merely *work* belongs in the level instead: a long list of toggles is a list
#: an owner will not read, and an unread list grants whatever it was left at.
AREAS: dict[str, tuple[str, ...]] = {
    "students": (),
    # Setting a teacher's pay is not the same as keeping their record.
    "teachers": ("commission",),
    "classes": (),
    # Calling off a class that is already running, with a reason attached.
    "calendar": ("cancel",),
    "attendance": (),
    # The four things that move money or reveal it.
    "billing": ("payments", "payouts", "expenses", "reports"),
    # Minting a login, and erasing the academy's data.
    "settings": ("staff", "danger"),
}

#: What a staff account gets before its owner has decided anything.
#:
#: Day-to-day work only. No money, no configuration — a new account can do its
#: job on the first morning and cannot move a single dinar.
DEFAULT_STAFF: dict[str, str] = {
    "students": "manage",
    "teachers": "manage",
    "classes": "manage",
    "calendar": "manage",
    "attendance": "manage",
    "billing": "none",
    "settings": "none",
}

OWNER_LEVELS: dict[str, str] = {area: "manage" for area in AREA_ORDER}
OWNER_ACTIONS: dict[str, tuple[str, ...]] = {area: tuple(actions) for area, actions in AREAS.items()}


# ── The catalogue, as the client needs it ─────────────────────────────────


def catalogue() -> dict[str, Any]:
    """The table above, in a shape a screen can render."""
    return {
        "areas": [{"key": area, "actions": list(AREAS[area])} for area in AREA_ORDER],
        "levels": list(LEVELS),
        "default": dict(DEFAULT_STAFF),
    }


# ── Reading and writing a stored permission map ───────────────────────────


def _clean_levels(raw: Any) -> dict[str, str] | None:
    """A level for every area, from a payload's ``levels`` — or ``None`` if
    the payload does not carry a usable one at all.

    A level that is missing or unrecognised becomes ``none``. That direction
    matters: a value this release does not know is a value it cannot reason
    about, and the only safe reading of an unknown grant is no grant.
    """
    if not isinstance(raw, dict):
        return None
    levels: dict[str, str] = {}
    for area in AREA_ORDER:
        value = raw.get(area)
        levels[area] = value if value in LEVELS else "none"
    return levels


def _clean_actions(raw: Any) -> dict[str, list[str]]:
    """The ticked actions, per area, ordered by the catalogue.

    Ordered by the catalogue rather than by the payload so that two accounts
    holding the same permissions store the same bytes — which is what lets
    "has this changed?" be a comparison rather than a diff.
    """
    actions: dict[str, list[str]] = {}
    if not isinstance(raw, dict):
        return actions
    for area in AREA_ORDER:
        chosen = raw.get(area)
        if not isinstance(chosen, (list, tuple, set)):
            continue
        wanted = set(chosen)
        kept = [action for action in AREAS[area] if action in wanted]
        if kept:
            actions[area] = kept
    return actions


def normalize(raw: Any) -> dict[str, Any]:
    """A complete, valid permission map from whatever is in the column.

    ``None`` — never configured — reads as :data:`DEFAULT_STAFF` rather than as
    nothing at all. That is what let this ship without a migration window:
    every staff account in the database had a null column on the day it
    deployed, and reading null as "no permissions" would have locked all of
    them out of the app the moment the new checks went live. Reading it as the
    default leaves their working day exactly as it was, and the owner can then
    narrow each account deliberately, one screen at a time.

    A map that *is* present is taken at its word — including a map whose every
    area is ``none``, which is a decision, not an absence.
    """
    if not isinstance(raw, dict):
        return {"levels": dict(DEFAULT_STAFF), "actions": {}}
    if "levels" not in raw:
        return {"levels": dict(DEFAULT_STAFF), "actions": {}}
    levels = _clean_levels(raw.get("levels"))
    if levels is None:
        return {"levels": dict(DEFAULT_STAFF), "actions": {}}
    return {"levels": levels, "actions": _clean_actions(raw.get("actions"))}


def parse(payload: Any) -> dict[str, Any]:
    """Validate a permission map sent by the owner, or raise ``ValueError``.

    Anything not in the catalogue is dropped rather than refused. A client one
    release behind may still be sending a toggle that has since been removed,
    and it should neither fail to save nor — far worse — succeed in granting
    something this release does not know about. The failure mode of a stale
    client is therefore a *narrower* account, never a wider one.
    """
    if not isinstance(payload, dict):
        raise ValueError("Permissions must be an object")
    levels = _clean_levels(payload.get("levels"))
    if levels is None:
        raise ValueError("Permissions must include a 'levels' object")
    return {"levels": levels, "actions": _clean_actions(payload.get("actions"))}


# ── Asking the question ───────────────────────────────────────────────────


def is_owner(user: Any) -> bool:
    return getattr(user, "role", None) == "owner"


def effective(user: Any) -> dict[str, str]:
    """The level this user holds in every area.

    The owner is answered without consulting the column at all. An owner with
    a null ``permissions`` field, a half-written one, or one an older release
    left in a shape this one does not recognise, is still the owner — and an
    owner who could be locked out of their own academy by a bad row would be a
    worse bug than any permission this feature could withhold.
    """
    if is_owner(user):
        return dict(OWNER_LEVELS)
    return normalize(getattr(user, "permissions", None))["levels"]


def effective_actions(user: Any) -> dict[str, tuple[str, ...]]:
    if is_owner(user):
        return dict(OWNER_ACTIONS)
    return normalize(getattr(user, "permissions", None))["actions"]


def allowed(user: Any, area: str, need: str = "view") -> bool:
    """Whether ``user`` may do ``need`` in ``area``.

    ``need`` is ``"view"``, ``"manage"``, or the name of one of the area's
    actions. An area this release does not know is refused rather than
    ignored — a route asking about an area that has been renamed must break
    loudly in development, not silently open in production.
    """
    if user is None:
        return False
    if is_owner(user):
        return True
    if area not in AREAS:
        return False
    level = effective(user).get(area, "none")
    if level == "none":
        return False
    if need == "view":
        return True
    if need == "manage":
        return level == "manage"
    if need not in AREAS[area]:
        return False
    return need in effective_actions(user).get(area, ())


def allowed_any(user: Any, requirements: Iterable[tuple[str, str]]) -> bool:
    """Whether the user satisfies *any* of the given ``(area, need)`` pairs.

    For the handful of reads that genuinely serve two masters. Which students
    are up to date on their fees is billing information *and* the front desk's
    working knowledge — the Classes and Calendar screens show it while a
    check-in is being taken. Requiring Billing alone would hide it from a
    staff member whose owner switched Billing off precisely because they were
    trusted with the classes and nothing else.
    """
    return any(allowed(user, area, need) for area, need in requirements)


def describe(user: Any) -> dict[str, Any]:
    """What this user holds, in the shape the client can store verbatim."""
    return {
        "role": getattr(user, "role", None),
        "levels": effective(user),
        "actions": {area: list(actions) for area, actions in effective_actions(user).items()},
    }
