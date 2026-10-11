"""
Vinta School OS — Auth Service
Hashing, JWT tokens, PIN validation, credential authorization.
"""
import re

from flask_jwt_extended import create_access_token, create_refresh_token
from sqlalchemy import func
from app import permissions
from app.extensions import db
from app.models.user import User

# Deliberately loose. The address is a sign-in handle, not a mailbox the app
# ever posts to, so the cost of refusing a real address that does not look like
# one is higher than the cost of accepting a typo the owner will notice the
# first time they try to sign in with it.
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")

# bcrypt hashes at most 72 bytes and silently ignores the rest, so a longer
# password is not stronger — it only looks it, and two passwords sharing their
# first 72 bytes would open the same account. Refused rather than truncated.
PASSWORD_MIN = 8
PASSWORD_MAX = 72


def _session_user(user: User) -> dict:
    """The identity that travels with a token, in the client's own shape.

    Sent on every sign-in rather than only on the boot-time ``/auth/me`` read.
    The client holds one ``user`` object and drives everything that depends on
    who you are from it — the sidebar, the page guards, the permission checks —
    and it has to be the object belonging to *the token it is holding*. Between
    choosing a profile and the next page reload there is no other moment the
    client could learn this, and a client that guesses would either hide work
    from someone entitled to it or, far worse, offer work they are not.

    ``permissions`` is the resolved grant — the owner's "everything", a staff
    member's own table, or the documented staff default if they have never been
    configured. So the client never has to re-implement the fallback, and the
    answer it renders with is the answer the server will enforce.
    """
    held = permissions.describe(user)
    return {
        "id": user.id,
        "academy_id": user.academy_id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "picture": user.picture,
        "avatar_color_1": user.avatar_color_1,
        "avatar_color_2": user.avatar_color_2,
        "is_active": user.is_active,
        "permissions": held,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def clean_email(raw: object) -> tuple[str | None, str | None]:
    """Format-check a login address. Returns ``(value, error)``.

    Absent, null and empty all mean "no address" and are not an error — a
    profile without an address is a perfectly ordinary profile, it simply signs
    in at the picker with a PIN. A value that is present but malformed is an
    error, because that one *was* meant to be a way in.

    Stored lower-cased and trimmed, so the uniqueness rule and the sign-in
    lookup agree about what "the same address" means.
    """
    if raw is None:
        return None, None
    if not isinstance(raw, str):
        return None, "email must be a valid email address"
    value = raw.strip().lower()
    if not value:
        return None, None
    if len(value) > 254 or not EMAIL_RE.match(value):
        return None, "email must be a valid email address"
    return value, None


def clean_password(raw: object) -> tuple[str | None, str | None]:
    """Check a login password. Returns ``(value, error)``."""
    if raw is None:
        return None, None
    if not isinstance(raw, str):
        return None, f"password must be at least {PASSWORD_MIN} characters"
    if len(raw) < PASSWORD_MIN:
        return None, f"password must be at least {PASSWORD_MIN} characters"
    if len(raw.encode("utf-8")) > PASSWORD_MAX:
        return None, f"password must be at most {PASSWORD_MAX} bytes"
    return raw, None


def email_taken(email: str, exclude_user_id: str | None = None) -> bool:
    """True if an active account already logs in with this address.

    The login request carries an email and nothing else — no academy id — so an
    address has to identify exactly one account, globally. A per-academy check
    cannot do that job: signup mints a brand-new academy_id every time, so the
    newly provisioned academy is empty by construction and a check scoped to it
    passes on the second signup with the same address too.

    This used to look only at owners, which was right when only owners had an
    address. Staff are given one now — they can sign in with it — so the
    question is about anyone who could answer to it. An empty address is not an
    address: PIN-only staff all share ``""`` and must not collide with one
    another.

    Deactivated accounts are excluded, matching :func:`authenticate_credentials`:
    they cannot log in, so they must not hold their address hostage. That also
    means the address of someone who has left can be handed straight to their
    replacement.

    ``exclude_user_id`` is for the edit case — changing nothing but the phone
    number must not be refused because the account's own address "is taken".
    """
    normalized = User.normalize_email(email)
    if not normalized:
        return False
    query = User.query.filter(
        func.lower(User.email) == normalized,
        User.is_active.is_(True),
    )
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)
    return query.first() is not None


def authenticate_credentials(email: str, password: str) -> dict | None:
    """
    Authenticate anyone with an email and a password.
    Returns tokens dict on success, None on failure.

    Was ``authenticate_owner``, and filtered on the owner role. Staff have an
    address and a password of their own now, set when the owner creates them,
    so the filter would have refused the very accounts the staff screen had
    just made. Anyone without a stored password — every PIN-only staff member
    — still cannot use this route, because ``verify_password`` answers False
    for them rather than comparing against nothing.
    """
    user = (
        User.query.filter(
            # Case-insensitive so accounts written before addresses were
            # normalised on insert still match the address they typed.
            func.lower(User.email) == User.normalize_email(email),
            User.is_active.is_(True),
        )
        # Duplicate addresses are refused when accounts are created, but rows
        # written before that guard existed are still in the table. Ordering
        # makes the pick deterministic instead of "whichever row the engine
        # reaches first" — and with two rows sharing an address, only one of
        # their passwords can ever be the right one.
        .order_by(User.created_at.asc(), User.id.asc())
        .first()
    )
    if not user or not user.verify_password(password):
        return None

    access_token = create_access_token(
        identity=user.id,
        additional_claims={"academy_id": user.academy_id, "role": user.role},
    )
    refresh_token = create_refresh_token(
        identity=user.id,
        additional_claims={"academy_id": user.academy_id, "role": user.role},
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": user.id,
        "name": user.name,
        "role": user.role,
        "academy_id": user.academy_id,
        "user": _session_user(user),
    }


def authenticate_profile(user_id: str, pin: str) -> dict | None:
    """
    Authenticate a profile (owner or staff) with PIN.
    Returns tokens dict on success, None on failure.
    """
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return None

    if not user.verify_pin(pin):
        return None

    access_token = create_access_token(
        identity=user.id,
        additional_claims={"academy_id": user.academy_id, "role": user.role},
    )
    return {
        "access_token": access_token,
        "user_id": user.id,
        "name": user.name,
        "role": user.role,
        "academy_id": user.academy_id,
        # The same identity the login route returns, and for a sharper reason:
        # this is the moment the client changes which token it is holding. The
        # profile picked here may be a different person from the one who typed
        # a password a moment ago — an owner's account choosing a staff PIN at
        # the picker — so the client is handed the identity that belongs to the
        # new token instead of being left to keep the old one, which would have
        # shown the wrong navigation for the rest of the session.
        "user": _session_user(user),
    }


def get_session_identity(user_id: str) -> dict | None:
    """The identity payload for a signed-in user, or ``None`` if there is none.

    ``/auth/me`` answers with this, which is what makes the boot-time read and
    the sign-in responses the *same object*. The client refreshes its stored
    user from ``/me`` on every reload, so if the two shapes differed even
    slightly — one carrying ``permissions`` and the other not — a page reload
    would quietly strip the authority the client had been holding, and the
    navigation would change under the person mid-session.
    """
    user = get_current_user(user_id)
    if not user:
        return None
    return _session_user(user)


def verify_pin(user_id: str, pin: str) -> bool:
    """Verify a PIN for a specific user."""
    user = db.session.get(User, user_id)
    if not user:
        return False
    return user.verify_pin(pin)


def change_pin(user_id: str, old_pin: str, new_pin: str) -> bool:
    """Change a user's PIN. Returns True on success."""
    user = db.session.get(User, user_id)
    if not user:
        return False

    if not user.verify_pin(old_pin):
        return False

    user.set_pin(new_pin)
    db.session.commit()
    return True


def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    """Change a user's password. Returns True on success.

    Was owner-only, which was the same thing as "everyone who had one" until
    staff were given addresses. Anyone can change their own password, and the
    old one is still demanded, so this is not a way to take over an account you
    cannot already sign in to.
    """
    user = db.session.get(User, user_id)
    if not user:
        return False

    if not user.verify_password(old_password):
        return False

    user.set_password(new_password)
    db.session.commit()
    return True


def get_current_user(user_id: str) -> User | None:
    """Get the current authenticated user."""
    return db.session.get(User, user_id)
