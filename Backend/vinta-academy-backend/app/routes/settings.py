"""
Vinta School OS — Settings Blueprint
/api/settings — Academy Config, Staff Management, Automations, Profile
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from flask_smorest import Blueprint
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.utils.decorators import tenant_required, require_permission, owner_only
from app.utils.audit import log_activity
from app.models.user import User
from app.models.academy import Academy, AcademySettings, Subscription
from app.services import (
    tenant_service, auth_service, export_service, import_service,
    school_export_service,
)
from app.services.academy_data_service import purge_academy_data
from app.schemas.settings import (
    UpdateAcademyRequestSchema, UpdateAppearanceRequestSchema,
    UpdateBillingConfigRequestSchema, UpdateAutomationsRequestSchema,
    AddStaffRequestSchema, UpdateStaffRequestSchema, UpdateProfileRequestSchema,
    AcademyResponseSchema, AppearanceResponseSchema, BillingConfigResponseSchema,
    AutomationsResponseSchema, StaffListResponseSchema, AddStaffResponseSchema,
    ProfileResponseSchema, SubscriptionResponseSchema,
)
from app.schemas.auth import PermissionsCatalogResponseSchema
from app.schemas.base import ErrorSchema, MessageSchema

settings_bp = Blueprint("settings", __name__, description="Academy settings, staff & subscriptions")

# How long the activity log keeps anything. Two weeks — long enough to
# answer "what happened to last week's classes" and to reconstruct a
# disputed register, short enough that the log stays a window on the recent
# past rather than an archive nobody reads. Applies to the academy-wide
# feed and a group's own log alike: they read the same table, so they
# expire on the same clock.
ACTIVITY_LOG_RETENTION_DAYS = 14

# Most rows the group-filtered read will look at before narrowing. The
# retention window means this is never reached in practice; it is here so a
# busy academy's read stays bounded rather than loading the whole table to
# return twenty rows.
RETENTION_READ_CAP = 2000


@settings_bp.route("/academy", methods=["GET"])
@jwt_required()
@tenant_required
def get_academy():
    """Get academy profile details."""
    from flask import g
    academy = g.current_academy
    return jsonify({
        "id": academy.id,
        "name": academy.name,
        "phone": academy.phone,
        "email": academy.email,
        "address": academy.address,
        "weekend_day": academy.weekend_day,
        "current_term": academy.current_term,
    }), 200


@settings_bp.route("/academy", methods=["PUT"])
@jwt_required()
@tenant_required
@require_permission("settings", "manage")
def update_academy():
    """
    Update academy profile (owner-only).
    Body: { name?, phone?, email?, address?, weekend_day?, current_term? }
    """
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    academy = g.current_academy

    # Handle academy deletion via confirm_delete flag
    if data.get("confirm_delete"):
        from flask import g

        academy_id = g.current_academy_id

        # Nothing is kept, and the academy row goes with it — the row itself
        # last, since everything else points at it. Same ordering service as
        # the reset: see app/services/academy_data_service.py.
        removed = purge_academy_data(academy_id, drop_academy=True)

        return jsonify({"message": "Academy deleted", "removed": removed}), 200

    for field in ("name", "phone", "email", "address", "weekend_day", "current_term"):
        if field in data:
            setattr(academy, field, data[field])

    db.session.commit()
    return jsonify({"message": "Academy updated"}), 200


@settings_bp.route("/appearance", methods=["GET"])
@jwt_required()
@tenant_required
def get_appearance():
    """Get appearance settings."""
    from flask import g
    settings = AcademySettings.query.filter_by(academy_id=g.current_academy_id).first()
    if not settings:
        return jsonify({"error": "Settings not found"}), 404

    return jsonify({
        "theme": settings.default_theme,
        "font_size": settings.default_font_size,
        "language": settings.default_language,
    }), 200


@settings_bp.route("/appearance", methods=["PUT"])
@jwt_required()
@tenant_required
def update_appearance():
    """
    Update appearance settings.
    Body: { theme?, font_size?, language? }
    """
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    settings = AcademySettings.query.filter_by(academy_id=g.current_academy_id).first()
    if not settings:
        return jsonify({"error": "Settings not found"}), 404

    if "theme" in data:
        settings.default_theme = data["theme"]
    if "font_size" in data:
        settings.default_font_size = data["font_size"]
    if "language" in data:
        settings.default_language = data["language"]

    db.session.commit()
    return jsonify({"message": "Appearance updated"}), 200


# ── Billing Rules toggles ───────────────────────────────────────────
# The six per-academy edge-case switches on AcademySettings. They are plain
# booleans, but they arrive over JSON where clients send "false" (string) or
# 0/1 rather than a real boolean. The column type will not rescue that: a bare
# setattr of "false" reaches the Boolean bind processor and raises at flush
# (an unhandled 500), and a junk value would be stored as-is on a laxer
# backend. So they are coerced explicitly on write instead.
BILLING_BOOL_FIELDS = (
    "absence_consumes_credit",
    "count_gap_sessions",
    "restore_credits_on_cancellation",
    "free_session_auto_present",
    "share_credits_across_groups",
    "early_payment_on_extra_sessions",
)


def _coerce_bool(value):
    """
    Return the boolean a JSON client meant, or None if the value is not
    unambiguously boolean-ish (the caller turns None into a 400).

    Accepted: real booleans; "true"/"false" (any case); "1"/"0"; 1/0.
    Everything else — "yes", 2, null, lists — is rejected rather than stored.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1"):
            return True
        if lowered in ("false", "0"):
            return False
        return None
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return None


@settings_bp.route("/billing-config", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("settings", "manage")
def get_billing_config():
    """Get billing configuration (owner-only)."""
    from flask import g
    settings = AcademySettings.query.filter_by(academy_id=g.current_academy_id).first()
    if not settings:
        return jsonify({"error": "Settings not found"}), 404

    # The payout cadence is not a column on this table — it lives in
    # `payout_schedules` (see the model's docstring for why a table and not a
    # column: `create_all()` builds tables in every runtime, including the
    # packaged .exe, but never adds a column to one that already exists). It is
    # returned here anyway because this is the endpoint the Billing Config
    # screen reads, and a screen that had to make a second call for one field
    # would be a screen that eventually forgets to.
    from app.services import payout_schedule_service

    return jsonify({
        "currency": settings.currency,
        "default_plan_duration": settings.default_plan_duration,
        "billing_reminder_days_before": settings.billing_reminder_days_before,
        "due_date_reminder_timing": settings.due_date_reminder_timing,
        "whatsapp_template": settings.whatsapp_template,
        "default_credits_per_cycle": settings.default_credits_per_cycle,
        "allow_rollover_default": settings.allow_rollover_default,
        "allow_makeups_default": settings.allow_makeups_default,
        # The teacher/school split. One number: the teacher's share of gross.
        # The school's share is the remainder, so it is never stored.
        "default_teacher_share_percentage": settings.default_teacher_share_percentage,
        "default_access_weeks": settings.default_access_weeks,
        "default_max_groups": settings.default_max_groups,
        "absence_consumes_credit": settings.absence_consumes_credit,
        "count_gap_sessions": settings.count_gap_sessions,
        "restore_credits_on_cancellation": settings.restore_credits_on_cancellation,
        "free_session_auto_present": settings.free_session_auto_present,
        "share_credits_across_groups": settings.share_credits_across_groups,
        "early_payment_on_extra_sessions": settings.early_payment_on_extra_sessions,
        # The academy-wide payroll default every teacher inherits unless they
        # have an override of their own.
        "payout_schedule": payout_schedule_service.resolve_schedule(
            g.current_academy_id, None
        ),
    }), 200


@settings_bp.route("/billing-config", methods=["PUT"])
@jwt_required()
@tenant_required
@require_permission("settings", "manage")
def update_billing_config():
    """
    Update billing configuration (owner-only).
    Body: { currency?, default_plan_duration?, billing_reminder_days_before?,
            due_date_reminder_timing?, whatsapp_template?,
            default_credits_per_cycle?, allow_rollover_default?,
            allow_makeups_default?, default_access_weeks?, default_max_groups?,
            default_teacher_share_percentage?,
            absence_consumes_credit?, count_gap_sessions?,
            restore_credits_on_cancellation?, free_session_auto_present?,
            share_credits_across_groups?, early_payment_on_extra_sessions?,
            payout_schedule? }
    Currency is locked to DZD on write: any other value is ignored with a warning.
    The six Billing Rules toggles are coerced to real booleans ("false" and 0
    both mean False); a value that is not boolean-ish is rejected with a 400
    naming the field. default_teacher_share_percentage is range-checked to
    0–100. payout_schedule is { cadence, day_of_week?, day_of_month? } and sets
    the academy-wide payroll default; an invalid cadence is a 400 rather than a
    silent no-op, because a payday that quietly did not save is worse than one
    that says why it would not. Unknown fields are ignored.
    """
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    settings = AcademySettings.query.filter_by(academy_id=g.current_academy_id).first()
    if not settings:
        return jsonify({"error": "Settings not found"}), 404

    warning = None
    if "currency" in data and data["currency"] != "DZD":
        warning = "currency is locked to DZD and was not changed"

    # Billing Rules toggles: coerce before writing, so a client that sends
    # "false" cannot store a truthy value and junk cannot reach the column.
    for field in BILLING_BOOL_FIELDS:
        if field in data:
            coerced = _coerce_bool(data[field])
            if coerced is None:
                return jsonify({"error": f"{field} must be a boolean"}), 400
            setattr(settings, field, coerced)

    for field in ("default_plan_duration", "billing_reminder_days_before",
                  "due_date_reminder_timing", "whatsapp_template",
                  "default_credits_per_cycle", "allow_rollover_default",
                  "allow_makeups_default", "default_access_weeks",
                  "default_max_groups"):
        if field in data:
            setattr(settings, field, data[field])

    # The teacher/school split. Range-checked rather than clamped, for the same
    # reason the commission editor range-checks: silently rewriting 150 to 100
    # would hide a typo inside a number that decides people's pay. The school's
    # share is derived (100 − this) and never stored, so the two can't disagree.
    if "default_teacher_share_percentage" in data:
        raw = data["default_teacher_share_percentage"]
        # bool is an int subclass — reject it explicitly.
        if isinstance(raw, bool) or not isinstance(raw, int):
            return jsonify({
                "error": "default_teacher_share_percentage must be a whole number between 0 and 100",
            }), 400
        if raw < 0 or raw > 100:
            return jsonify({
                "error": "default_teacher_share_percentage must be between 0 and 100",
            }), 400
        settings.default_teacher_share_percentage = raw

    # The academy-wide payroll default. Written to `payout_schedules`, not to
    # this row — but through this endpoint, so the Billing Config screen has one
    # place to save and one place to read, the same way it has for every other
    # field in this form.
    if "payout_schedule" in data:
        from app.services import payout_schedule_service

        schedule = data["payout_schedule"] or {}
        if not isinstance(schedule, dict):
            return jsonify({
                "error": "payout_schedule must be an object with a cadence",
            }), 400
        try:
            payout_schedule_service.upsert_schedule(
                g.current_academy_id,
                None,                       # None = the academy default row
                schedule.get("cadence"),
                schedule.get("day_of_week"),
                schedule.get("day_of_month"),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    db.session.commit()
    payload = {"message": "Billing config updated"}
    if warning:
        payload["warning"] = warning
    return jsonify(payload), 200


@settings_bp.route("/automations", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("settings", "manage")
def get_automations():
    """Get automation settings (owner-only, gated by Scaler tier)."""
    from flask import g
    settings = AcademySettings.query.filter_by(academy_id=g.current_academy_id).first()
    subscription = Subscription.query.filter_by(academy_id=g.current_academy_id).first()

    return jsonify({
        "auto_checkout_enabled": settings.auto_checkout_enabled if settings else True,
        "end_class_popup_enabled": settings.end_class_popup_enabled if settings else True,
        "tier": subscription.tier if subscription else "starter",
    }), 200


@settings_bp.route("/automations", methods=["PUT"])
@jwt_required()
@tenant_required
@require_permission("settings", "manage")
def update_automations():
    """
    Update automation settings (owner-only).
    Body: { auto_checkout_enabled?, end_class_popup_enabled? }
    Gated by Scaler subscription tier.
    """
    from flask import g
    data = request.get_json()

    subscription = Subscription.query.filter_by(academy_id=g.current_academy_id).first()
    if subscription and subscription.tier not in ("pro", "scaler"):
        return jsonify({"error": "Automations require Pro or Scaler tier"}), 403

    settings = AcademySettings.query.filter_by(academy_id=g.current_academy_id).first()
    if not settings:
        return jsonify({"error": "Settings not found"}), 404

    if "auto_checkout_enabled" in data:
        settings.auto_checkout_enabled = data["auto_checkout_enabled"]
    if "end_class_popup_enabled" in data:
        settings.end_class_popup_enabled = data["end_class_popup_enabled"]

    db.session.commit()
    return jsonify({"message": "Automations updated"}), 200


# ── Staff Management ────────────────────────────────────────────────

@settings_bp.route("/permissions", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("settings", "staff")
@settings_bp.response(200, PermissionsCatalogResponseSchema)
def get_permissions_catalogue():
    """The permission catalogue the staff screen is drawn from.

    Served rather than hard-coded in the client so the screen cannot offer a
    switch the server would not honour, and so adding an area to
    ``app/permissions.py`` is enough to make it appear in the editor.
    """
    from app import permissions

    return jsonify(permissions.catalogue()), 200


@settings_bp.route("/staff", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("settings", "staff")
def list_staff():
    """List all active profiles for the academy, with what each may do.

    Includes the owner's own row. The screen needs it to show the account every
    other one is measured against, and ``permissions.describe`` answers for an
    owner with everything held — so the row renders as "full access" rather
    than as a blank panel the owner might mistake for a broken one.

    Each grant is the *resolved* map (``describe``), not the stored column, for
    the same reason the sign-in payload is: a staff member whose column is
    still NULL must show the day-to-day default that is actually in force, not
    an empty table that would read as "no access at all".
    """
    from flask import g
    from app import permissions

    profiles = tenant_service.get_academy_profiles(g.current_academy_id)
    return jsonify({
        "staff": [
            {
                "id": p.id,
                "name": p.name,
                "role": p.role,
                "phone": p.phone,
                "email": p.email,
                "is_active": p.is_active,
                "permissions": permissions.describe(p),
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in profiles
        ]
    }), 200


@settings_bp.route("/staff", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("settings", "staff")
def add_staff():
    """
    Add a new staff profile (requires the staff permission + the caller's PIN).
    Body: { name, pin, email?, password?, phone?, permissions? }

    An email and a password are optional and go together: with them the person
    can sign in by typing them, without them they sign in at the profile picker
    with their PIN, which is what every staff profile used to do.
    ``permissions`` omitted means the documented staff default — day-to-day
    work, no money, no settings.
    """
    from flask import g
    from app import permissions

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    # Verify the caller's own PIN as a step-up check.
    # 403, not 401 — see the note in auth.py:create_profile. The caller holds a
    # valid session; only this step-up check failed, and answering 401 would make
    # the frontend treat it as an expired session and log them out mid-form.
    owner_pin = data.get("owner_pin")
    if not owner_pin or not g.current_user.verify_pin(owner_pin):
        return jsonify({"error": "PIN verification required"}), 403

    required = ("name", "pin")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    email, email_error = auth_service.clean_email(data.get("email"))
    if email_error:
        return jsonify({"error": email_error}), 400
    password, password_error = auth_service.clean_password(data.get("password"))
    if password_error:
        return jsonify({"error": password_error}), 400
    # Both or neither — an address nobody has a password for is not a way in,
    # and a password with no address is not a way to be found.
    if bool(email) != bool(password):
        return jsonify({
            "error": "An email and a password go together — provide both, or neither",
        }), 400
    if auth_service.email_taken(email):
        return jsonify({"error": "An account with this email already exists"}), 409

    raw_perms = data.get("permissions")
    if raw_perms is None:
        permissions_map = None
    else:
        try:
            permissions_map = permissions.parse(raw_perms)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    user = tenant_service.create_staff_profile(
        academy_id=g.current_academy_id,
        name=data["name"],
        pin=data["pin"],
        phone=data.get("phone"),
        role="staff",  # Always staff — owner creation is a separate flow
        email=email,
        password=password,
        permissions_map=permissions_map,
    )

    log_activity(
        academy_id=g.current_academy_id,
        user_id=g.current_user.id,
        entity_type="staff",
        entity_id=user.id,
        action="created",
        description=f"Staff {user.name} ({user.role}) added",
    )

    db.session.commit()

    return jsonify({
        "id": user.id,
        "name": user.name,
        "role": user.role,
        "email": user.email,
        "permissions": permissions.describe(user),
    }), 201


@settings_bp.route("/staff/<user_id>", methods=["PUT"])
@jwt_required()
@tenant_required
@require_permission("settings", "staff")
def update_staff(user_id):
    """
    Update a staff profile — name, phone, login address, password, permissions.
    Body: { name?, phone?, email?, password?, permissions? }

    Role cannot be changed here; an owner is made by the separate flow.
    """
    from flask import g
    from app import permissions as perm

    user = db.session.get(User, user_id)
    if not user or user.academy_id != g.current_academy_id:
        return jsonify({"error": "Staff not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    # An owner holds everything by virtue of the role, and nothing written to
    # the column can add to or take from that (``permissions.effective`` never
    # reads it for an owner). Accepting a grant here would look like it had
    # been applied and change nothing, so it is refused with the reason.
    if user.role == "owner" and data.get("permissions") is not None:
        return jsonify({
            "error": "An owner holds every permission — there is nothing to change",
        }), 400

    for field in ("name", "phone"):
        if field in data:
            setattr(user, field, data[field])

    if "email" in data:
        email, email_error = auth_service.clean_email(data.get("email"))
        if email_error:
            return jsonify({"error": email_error}), 400
        # Exclusive of this row: re-sending an unchanged address must not read
        # as a clash with itself. An address may be cleared (null or "") to
        # take away the email sign-in and leave the PIN-only one.
        if auth_service.email_taken(email, exclude_user_id=user.id):
            return jsonify({"error": "An account with this email already exists"}), 409
        user.email = email or ""

    if data.get("password"):
        password, password_error = auth_service.clean_password(data["password"])
        if password_error:
            return jsonify({"error": password_error}), 400
        # Refused rather than stored against an address-less profile, where it
        # could never be used and would only make the row look like it had a
        # login.
        if not user.email:
            return jsonify({
                "error": "Add a login address before setting a password for it",
            }), 400
        user.set_password(password)

    if data.get("permissions") is not None:
        try:
            user.permissions = perm.parse(data["permissions"])
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    db.session.commit()
    return jsonify({"message": "Staff updated"}), 200


@settings_bp.route("/staff/<user_id>/deactivate", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("settings", "staff")
def deactivate_staff(user_id):
    """Deactivate a staff profile (soft-delete)."""
    from flask import g
    user = db.session.get(User, user_id)
    if not user or user.academy_id != g.current_academy_id:
        return jsonify({"error": "Staff not found"}), 404

    if user.role == "owner":
        return jsonify({"error": "Cannot deactivate an owner account"}), 400

    if user_id == g.current_user.id:
        return jsonify({"error": "Cannot deactivate your own account"}), 400

    user.is_active = False
    db.session.commit()
    return jsonify({"message": "Staff deactivated"}), 200


@settings_bp.route("/staff/<user_id>/reactivate", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("settings", "staff")
def reactivate_staff(user_id):
    """Reactivate a previously deactivated staff profile."""
    from flask import g
    user = db.session.get(User, user_id)
    if not user or user.academy_id != g.current_academy_id:
        return jsonify({"error": "Staff not found"}), 404

    if user.is_active:
        return jsonify({"message": "Staff is already active"}), 200

    user.is_active = True
    db.session.commit()
    return jsonify({"message": "Staff reactivated"}), 200


@settings_bp.route("/staff/<user_id>", methods=["DELETE"])
@jwt_required()
@tenant_required
@require_permission("settings", "staff")
def delete_staff(user_id):
    """Permanently delete a staff profile (owner-only)."""
    from flask import g
    user = db.session.get(User, user_id)
    if not user or user.academy_id != g.current_academy_id:
        return jsonify({"error": "Staff not found"}), 404

    if user.role == "owner":
        return jsonify({"error": "Cannot delete an owner account"}), 400

    if user_id == g.current_user.id:
        return jsonify({"error": "Cannot delete your own account"}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Staff deleted"}), 200


# ── Profile ─────────────────────────────────────────────────────────

@settings_bp.route("/profile", methods=["GET"])
@jwt_required()
@tenant_required
def get_profile():
    """Get current user's profile."""
    from flask import g
    user = g.current_user
    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "picture": user.picture,
    }), 200


@settings_bp.route("/profile", methods=["PUT"])
@jwt_required()
@tenant_required
def update_profile():
    """
    Update current user's profile.
    Body: { name?, phone?, email? }
    """
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    user = g.current_user

    for field in ("name", "phone", "email"):
        if field in data:
            setattr(user, field, data[field])

    db.session.commit()
    return jsonify({"message": "Profile updated"}), 200


# ── Reset Data ──────────────────────────────────────────────────────

@settings_bp.route("/reset-data", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("settings", "danger")
def reset_academy_data():
    """
    Reset all academy data (students, teachers, classes, billing, sessions).
    Keeps the academy itself and staff accounts.
    """
    from flask import g

    academy_id = g.current_academy_id

    # What a reset keeps is what the academy *is* rather than what it has
    # accumulated: the academy row, its staff accounts, its settings and its
    # subscription tier. Everything else goes, in an order the foreign keys
    # accept — see app/services/academy_data_service.py for why the order is
    # derived rather than written down.
    removed = purge_academy_data(
        academy_id,
        keep_tables=frozenset({"academies", "users", "academy_settings", "subscriptions"}),
    )

    log_activity(
        academy_id=academy_id,
        user_id=g.current_user.id,
        entity_type="academy",
        entity_id=academy_id,
        action="reset",
        description="Academy data reset by owner",
    )

    # The log entry is written *after* the purge, so it survives it: the
    # reset leaves exactly one line behind saying that it happened.
    db.session.commit()
    return jsonify({"message": "Academy data has been reset", "removed": removed}), 200


# ── Subscription ────────────────────────────────────────────────────

@settings_bp.route("/subscription", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("settings", "manage")
def get_subscription():
    """Get academy subscription details (owner-only)."""
    from flask import g
    sub = Subscription.query.filter_by(academy_id=g.current_academy_id).first()
    if not sub:
        return jsonify({"error": "Subscription not found"}), 404

    return jsonify({
        "tier": sub.tier,
        "status": sub.status,
        "invoicing_method": sub.invoicing_method,
        "started_at": sub.started_at.isoformat() if sub.started_at else None,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
    }), 200


# ── Data Export ────────────────────────────────────────────────────

@settings_bp.route("/export/<dataset>", methods=["GET"])
@jwt_required()
@tenant_required
def export_data(dataset):
    """
    Export academy data as CSV.
    Supported datasets: students, teachers, classes, billing, activity-log
    """
    from flask import g, Response

    try:
        if dataset == "students":
            csv_data = export_service.export_student_roster(g.current_academy_id)
            filename = "students.csv"
        elif dataset == "teachers":
            csv_data = export_service.export_teacher_hours(g.current_academy_id)
            filename = "teachers.csv"
        elif dataset == "classes":
            from app.models.class_room import Class
            from app.models.scheduling import Schedule
            classes = Class.query.filter_by(academy_id=g.current_academy_id).all()
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Name", "Subject", "Teacher", "Schedule"])
            for cls in classes:
                teacher_name = f"{cls.teacher.first_name} {cls.teacher.last_name}" if cls.teacher else ""
                schedules = Schedule.query.filter_by(class_id=cls.id).all()
                schedule_str = ", ".join(f"{s.day_of_week}:{s.start_time}-{s.end_time}" for s in schedules)
                writer.writerow([cls.name, cls.subject or "", teacher_name, schedule_str])
            csv_data = output.getvalue()
            filename = "classes.csv"
        elif dataset == "billing":
            # The only dataset here that is money. The rest of this route is
            # open to any staff member because the Data & Export panel offers
            # it to them; a billing ledger is a different question, and there
            # is no reason for the export to be the way round the screen that
            # was switched off. 403, not 401 — see the note on decorators.
            from app import permissions
            if not permissions.allowed(g.current_user, "billing", "reports"):
                return jsonify({
                    "error": "You do not have permission to do this",
                    "area": "billing",
                    "required": "reports",
                }), 403
            csv_data = export_service.export_billing_history(g.current_academy_id)
            filename = "billing.csv"
        elif dataset == "activity-log":
            from app.models.audit import ActivityLog
            from app.models.user import User
            logs = (
                ActivityLog.query
                .filter_by(academy_id=g.current_academy_id)
                .order_by(ActivityLog.created_at.desc())
                .limit(1000)
                .all()
            )
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Type", "Action", "Description", "User", "Date"])
            for log in logs:
                user = db.session.get(User, log.user_id)
                user_name = f"{user.name}" if user else ""
                writer.writerow([
                    log.entity_type,
                    log.action,
                    log.description or "",
                    user_name,
                    log.created_at.isoformat() if log.created_at else "",
                ])
            csv_data = output.getvalue()
            filename = "activity-log.csv"
        else:
            return jsonify({"error": f"Unknown dataset: {dataset}"}), 400

        log_activity(
            academy_id=g.current_academy_id,
            user_id=g.current_user.id,
            entity_type="export",
            entity_id=dataset,
            action="exported",
            description=f"Exported {dataset} data",
        )

        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"},
        )
    except Exception:
        return jsonify({"error": "Internal server error"}), 500


# ── School Export & Autodetect Import ─────────────────────────────
#
# Two owner-only doors onto the same idea: the whole academy, out and back.
# Neither is a report. Export School writes a ZIP that carries the database
# file; the import writes to every table at once. Both are the owner's the
# way the account's own login details are — no permission row grants them,
# because no arrangement of them is safe for someone else to hold.

#: The largest file the import box will read. A register is thousands of
#: rows, not millions; the cap is here so a wrong file is refused with a
#: sentence rather than pinning the process while it is parsed.
MAX_IMPORT_BYTES = 10 * 1024 * 1024


def _import_summary(report) -> str:
    """One line for the audit trail, whichever shape the report has."""
    if report.get("archive"):
        created = sum(f.get("created", 0) for f in report["files"])
        updated = sum(f.get("updated", 0) for f in report["files"])
        return f"Imported archive: {created} created, {updated} updated"
    return (
        f"Imported {report.get('dataset')}: "
        f"{report.get('created', 0)} created, {report.get('updated', 0)} updated, "
        f"{report.get('failed', 0)} failed"
    )


@settings_bp.route("/export/school", methods=["GET"])
@jwt_required()
@tenant_required
@owner_only
def export_school():
    """Everything the academy owns, as one ZIP.

    The archive carries a copy of the database, a CSV per table and the same
    rows as JSON. Owner-only because of the first of those: a staff member
    handed this would be handed the academy, not a report about it.
    """
    from flask import g, Response

    try:
        payload, filename = school_export_service.build_school_archive(
            g.current_academy_id, request.headers.get("Accept-Language"),
        )
    except Exception:
        logging.exception("School export failed")
        return jsonify({"error": "Internal server error"}), 500

    log_activity(
        academy_id=g.current_academy_id,
        user_id=g.current_user.id,
        entity_type="export",
        entity_id="school",
        action="exported",
        description="Exported all academy data (ZIP)",
    )
    db.session.commit()

    return Response(
        payload,
        mimetype="application/zip",
        headers={
            "Content-Disposition": f"attachment;filename={filename}",
            # The README inside follows the interface language, so this
            # answer differs by language even though its URL does not.
            "Vary": "Accept-Language",
        },
    )


@settings_bp.route("/import", methods=["POST"])
@jwt_required()
@tenant_required
@owner_only
def import_data():
    """Detect what a dropped CSV (or Export-School ZIP) is, and load it.

    ``dry_run=1`` detects and counts without writing — the preview the screen
    shows before the owner commits. Answers are machine-readable codes
    (``unsupported_file``, ``unknown_dataset``, …) that the interface
    translates, so the server does not have to guess the reader's language
    for a message that belongs on a button.
    """
    from flask import g

    upload = request.files.get("file")
    if upload is None:
        return jsonify({"error": "No file uploaded", "code": "no_file"}), 400

    raw = upload.read()
    if not raw:
        return jsonify({"error": "Empty file", "code": "empty_file"}), 400
    if len(raw) > MAX_IMPORT_BYTES:
        return jsonify({"error": "File too large", "code": "too_large"}), 413

    filename = upload.filename or ""
    dry_run = str(request.form.get("dry_run", "")).lower() in ("1", "true", "yes")
    dataset = (request.form.get("dataset") or "").strip() or None

    try:
        if filename.lower().endswith(".zip"):
            report = import_service.import_zip(
                g.current_academy_id, raw,
                actor_id=g.current_user.id, dry_run=dry_run,
            )
        else:
            report = import_service.import_upload(
                g.current_academy_id, filename, raw,
                actor_id=g.current_user.id, dry_run=dry_run, dataset=dataset,
            )
    except import_service.ImportDetectionError as exc:
        # An unrecognisable or ambiguous header is an answer, not a failure:
        # 400 with the code the screen turns into a sentence, plus the list of
        # datasets it might be so the screen can offer a choice.
        db.session.rollback()
        return jsonify({
            "error": exc.code, "code": exc.code, "candidates": exc.candidates,
        }), 400
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc), "code": str(exc)}), 400
    except Exception:
        db.session.rollback()
        logging.exception("Autodetect import failed")
        return jsonify({"error": "Internal server error", "code": "server_error"}), 500

    if not dry_run:
        log_activity(
            academy_id=g.current_academy_id,
            user_id=g.current_user.id,
            entity_type="import",
            entity_id=report.get("dataset") or "archive",
            action="imported",
            description=_import_summary(report),
        )
        db.session.commit()

    return jsonify(report), 200


# ── Activity Log (Dashboard) ──────────────────────────────────────

@settings_bp.route("/activity-log", methods=["GET"])
@jwt_required()
@tenant_required
def get_activity_log():
    """
    Get recent activity log entries.

    Query params:
      limit     default 20, capped at 200
      class_id  optional — only what happened to that group

    The same table answers two questions. The dashboard asks "what has been
    going on" and wants the academy's whole recent history; a group's own
    hamburger asks "what happened to THIS class", and used to be handed the
    academy-wide feed instead, which told the desk nothing it could not
    already see and buried the one line it wanted.

    An entry belongs to a group when it names the group itself, when it
    names one of the group's sessions, or when it carries the class_id in
    its metadata. All three are checked because the log has been written by
    three different code paths over time and history is not re-writable.

    Retention: entries older than ACTIVITY_LOG_RETENTION_DAYS are deleted
    here, before the read. Two weeks is the horizon the desk asked for, and
    pruning on read is what makes it self-maintaining — nobody has to
    remember a cleanup job, and no reader can ever see a row past it.
    """
    from flask import g
    from app.models.audit import ActivityLog as ActivityLogModel
    from app.models.scheduling import Session as SessionModel

    limit = request.args.get("limit", 20, type=int)
    limit = max(1, min(limit, 200))
    class_id = request.args.get("class_id")

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        days=ACTIVITY_LOG_RETENTION_DAYS
    )
    pruned = (
        ActivityLogModel.query
        .filter(
            ActivityLogModel.academy_id == g.current_academy_id,
            ActivityLogModel.created_at < cutoff,
        )
        .delete(synchronize_session=False)
    )
    if pruned:
        db.session.commit()

    # Filtering a group's history happens in Python rather than in SQL
    # because "belongs to this group" spans three columns, one of them
    # JSON. The retention window keeps the row count small enough that this
    # stays a cheap read rather than a scan of the academy's whole past.
    if class_id:
        session_ids = {
            sid for (sid,) in db.session.query(SessionModel.id)
            .filter(
                SessionModel.academy_id == g.current_academy_id,
                SessionModel.class_id == class_id,
            )
            .all()
        }
        candidates = (
            ActivityLogModel.query
            .filter_by(academy_id=g.current_academy_id)
            .order_by(ActivityLogModel.created_at.desc())
            .limit(RETENTION_READ_CAP)
            .all()
        )
        logs = [log for log in candidates if _log_belongs_to_class(log, class_id, session_ids)][:limit]
    else:
        logs = (
            ActivityLogModel.query
            .filter_by(academy_id=g.current_academy_id)
            .order_by(ActivityLogModel.created_at.desc())
            .limit(limit)
            .all()
        )

    # Map backend action types to frontend activity types
    ACTION_TYPE_MAP = {
        "payment_received": "payment",
        "payment_overdue": "payment",
        "checked_in": "checkin",
        "checked_out": "checkin",
        "enrolled": "student",
        "withdrawn": "student",
        "created": "student",
        "updated": "student",
        "extended": "checkin",
        "deleted": "alert",
    }

    activities = []
    for log in logs:
        user = db.session.get(User, log.user_id)
        user_name = user.name if user else "System"
        activity_type = ACTION_TYPE_MAP.get(log.action, "alert")

        # Build a human-readable title from the action
        title = log.description or f"{log.action.replace('_', ' ').title()} — {log.entity_type}"

        activities.append({
            "id": log.id,
            "type": activity_type,
            "title": title,
            "description": log.description or "",
            "timestamp": log.created_at.isoformat() + "Z" if log.created_at else "",
            "staff_name": user_name,
            # The frontend colours by these; a group's log can then show a
            # free session or a teacher absence without re-reading anything.
            "action": log.action,
            "cancelled_reason": (log.log_metadata or {}).get("cancelled_reason"),
        })

    return jsonify({
        "activities": activities,
        "class_id": class_id,
        "retention_days": ACTIVITY_LOG_RETENTION_DAYS,
    }), 200


def _log_belongs_to_class(log, class_id: str, session_ids: set) -> bool:
    """Is this entry part of that group's story?"""
    if (log.log_metadata or {}).get("class_id") == class_id:
        return True
    if log.entity_type == "class" and log.entity_id == class_id:
        return True
    if log.entity_type == "session" and log.entity_id in session_ids:
        return True
    return False
