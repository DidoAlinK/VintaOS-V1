"""
Vinta School OS — Route Decorators

@tenant_required      who you are, and which academy you are asking about
@owner_only           the owner, and nobody else
@require_permission   an area of the app, and what the holder may do in it
@verify_staff_pin     a step-up: prove it is really you, again

Order matters, outermost first::

    @jwt_required()
    @tenant_required
    @require_permission("billing", "reports")
    def handler(): ...

``tenant_required`` is what puts ``g.current_user`` in place, so anything that
asks a question about the user belongs inside it.

The rule itself is not written here. What each area opens, what ``view`` and
``manage`` mean, and which actions exist at all live in :mod:`app.permissions`
— one table, served to the settings screen, so the switch an owner flips and
the check that refuses them are readings of the same document.
"""
from functools import wraps
from flask import request, g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app import permissions
from app.extensions import db
from app.models.user import User
from app.models.academy import Academy


def _current_user():
    """The authenticated user: from ``g`` when ``tenant_required`` has already
    put them there, and from the token otherwise.

    Every decorator below needs the same thing and each used to fetch it in its
    own words. One helper means the fallback path — a decorator used without
    ``tenant_required`` above it — behaves identically in all of them, instead
    of in three nearly identical ways.
    """
    user = getattr(g, "current_user", None)
    if user is not None:
        return user

    verify_jwt_in_request()
    user = db.session.get(User, get_jwt_identity())
    if user is not None:
        g.current_user = user
    return user


def tenant_required(fn):
    """
    Ensures the authenticated user belongs to the academy
    specified in X-Academy-Id header and sets g.current_academy.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = db.session.get(User, user_id)
        if not user:
            return {"error": "User not found"}, 404

        academy_id = request.headers.get("X-Academy-Id")
        if not academy_id:
            return {"error": "X-Academy-Id header is required"}, 400

        if user.academy_id != academy_id:
            return {"error": "Access denied: not a member of this academy"}, 403

        if not user.is_active:
            return {"error": "Account is deactivated"}, 403

        g.current_user = user
        g.current_academy_id = academy_id

        academy = db.session.get(Academy, academy_id)
        if not academy:
            return {"error": "Academy not found"}, 404

        g.current_academy = academy
        return fn(*args, **kwargs)

    return wrapper


def owner_only(fn):
    """
    Restricts access to owner role only.
    Must be used after @tenant_required.

    Kept for the routes that are the owner's by their nature rather than by a
    permission — the account's own login details, chiefly. Everything an owner
    might delegate goes through ``require_permission`` instead, so that a staff
    member the owner chose to trust is not refused by a decorator whose name
    says "owner" but whose intent was "not everyone".
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not user:
            return {"error": "User not found"}, 404

        if not permissions.is_owner(user):
            return {"error": "Owner access required"}, 403

        return fn(*args, **kwargs)

    return wrapper


def require_permission(area: str, need: str = "view"):
    """Requires the caller to hold ``need`` in ``area``.

    ``need`` is ``"view"``, ``"manage"``, or the name of one of that area's
    actions — :mod:`app.permissions` has the catalogue and what each level
    opens. Must be used after ``@tenant_required``.

    The owner passes without their own row being read: an owner holds
    everything by definition, and an owner locked out of their own academy by
    a bad permission row would be a worse failure than anything this could
    withhold.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = _current_user()
            if not user:
                return {"error": "User not found"}, 404

            if not permissions.allowed(user, area, need):
                # 403, never 401. The caller's session is perfectly valid — the
                # action is simply not theirs to take. A 401 here is read by the
                # frontend's interceptor as an expired session: it clears the
                # tokens and redirects to login mid-screen, throwing away
                # whatever they were in the middle of. Same rule as a wrong PIN.
                return {
                    "error": "You do not have permission to do this",
                    "area": area,
                    "required": need,
                }, 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_any_permission(*requirements: tuple[str, str]):
    """Requires the caller to hold *one* of the given ``(area, need)`` pairs.

    For the few reads that genuinely serve two masters — see
    :func:`app.permissions.allowed_any`. Must be used after
    ``@tenant_required``.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = _current_user()
            if not user:
                return {"error": "User not found"}, 404

            if not permissions.allowed_any(user, requirements):
                return {
                    "error": "You do not have permission to do this",
                    "required_any": [f"{area}:{need}" for area, need in requirements],
                }, 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def verify_staff_pin(fn):
    """
    Verifies the staff member's PIN before performing a sensitive action.
    Expects JSON body with 'pin' field.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not user:
            return {"error": "User not found"}, 404

        data = request.get_json() or {}
        pin = data.get("pin")
        if not pin:
            return {"error": "PIN is required"}, 400

        if not user.verify_pin(pin):
            # 403, not 401: the caller is authenticated — the credential is
            # simply not valid for this action. A 401 here is read by the
            # frontend's axios interceptor as "session expired", which clears
            # the tokens and redirects to login mid-payment. The message text
            # is kept as "Invalid PIN" (the client string-matches 'pin').
            return {"error": "Invalid PIN"}, 403

        return fn(*args, **kwargs)

    return wrapper
