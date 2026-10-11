"""
Auth schemas — Login, Signup, PIN verification, Profile management.
"""
from marshmallow import EXCLUDE, Schema, fields, validate


# ── Request Schemas ────────────────────────────────────────────────

class SignupRequestSchema(Schema):
    """POST /api/auth/signup"""
    name = fields.String(required=True, metadata={"description": "Academy name", "example": "Al-Baraka Academy"})
    email = fields.String(required=True, metadata={"description": "Academy email", "example": "admin@albaraka.dz"})
    password = fields.String(required=True, metadata={"description": "Owner password", "example": "SecurePass123!"})


class LoginRequestSchema(Schema):
    """POST /api/auth/login"""
    email = fields.String(required=True, metadata={"description": "Owner email", "example": "owner@albaraka.dz"})
    password = fields.String(required=True, metadata={"description": "Owner password", "example": "SecurePass123!"})


class VerifyPinRequestSchema(Schema):
    """POST /api/auth/verify-pin"""
    user_id = fields.String(required=True, metadata={"description": "Profile user ID", "example": "uuid-string"})
    pin = fields.String(required=True, validate=[
        validate.Length(min=4, max=6),
        validate.Regexp(r"^\d{4,6}$", error="PIN must be 4-6 numeric digits"),
    ], metadata={"description": "4-6 digit PIN", "example": "1234"})


class CreateOwnerRequestSchema(Schema):
    """POST /api/auth/create-owner"""
    academy_id = fields.String(required=True, metadata={"description": "Academy ID from signup", "example": "uuid-string"})
    name = fields.String(required=True, metadata={"description": "Owner full name", "example": "Ahmed Benali"})
    email = fields.String(required=True, metadata={"description": "Owner email", "example": "ahmed@albaraka.dz"})
    password = fields.String(required=True, metadata={"description": "Owner password", "example": "SecurePass123!"})
    pin = fields.String(required=True, validate=[
        validate.Length(min=4, max=6),
        validate.Regexp(r"^\d{4,6}$", error="PIN must be 4-6 numeric digits"),
    ], metadata={"description": "4-6 digit PIN for quick login", "example": "1234"})


class CreateProfileRequestSchema(Schema):
    """POST /api/auth/create-profile"""
    name = fields.String(required=True, metadata={"description": "Staff name", "example": "Fatima Zohra"})
    pin = fields.String(required=True, validate=[
        validate.Length(min=4, max=6),
        validate.Regexp(r"^\d{4,6}$", error="PIN must be 4-6 numeric digits"),
    ], metadata={"description": "4-6 digit PIN", "example": "5678"})
    role = fields.String(load_default="staff", metadata={"description": "Role: owner or staff", "example": "staff"})
    phone = fields.String(load_default=None, metadata={"description": "Phone number", "example": "+213555123456"})
    owner_pin = fields.String(load_default=None, metadata={"description": "Owner's PIN for authorization", "example": "1234"})
    email = fields.String(load_default=None, metadata={"description": "Login address. Optional — without one the profile signs in by PIN only.", "example": "fatima@albaraka.dz"})
    password = fields.String(load_default=None, metadata={"description": "Login password. Must accompany an email; ignored without one."})
    permissions = fields.Raw(load_default=None, metadata={"description": "Staff authority map ({levels, actions}). Omitted means the day-to-day default."})

    class Meta:
        unknown = EXCLUDE


class ChangePinRequestSchema(Schema):
    """POST /api/auth/change-pin"""
    old_pin = fields.String(required=True, validate=[
        validate.Length(min=4, max=6),
        validate.Regexp(r"^\d{4,6}$", error="PIN must be 4-6 numeric digits"),
    ], metadata={"description": "Current PIN", "example": "1234"})
    new_pin = fields.String(required=True, validate=[
        validate.Length(min=4, max=6),
        validate.Regexp(r"^\d{4,6}$", error="PIN must be 4-6 numeric digits"),
    ], metadata={"description": "New PIN", "example": "5678"})


# ── Response Schemas ───────────────────────────────────────────────

class PermissionGrantSchema(Schema):
    """What a user may do — the resolved grant, not the stored column.

    Handed to the client on every sign-in and on ``/auth/me`` so the two agree
    by construction: the navigation and the page guards read this object, and
    it is produced by the same ``app/permissions`` call the server enforces
    with. The client never re-derives the fallback, so it cannot render a
    screen the server would refuse, or hide one it would allow.
    """
    role = fields.String(metadata={"description": "owner or staff"})
    levels = fields.Dict(
        keys=fields.String(),
        values=fields.String(),
        metadata={
            "description": "Level per area: none, view or manage",
            "example": {"students": "manage", "billing": "view", "settings": "none"},
        },
    )
    actions = fields.Dict(
        keys=fields.String(),
        values=fields.List(fields.String()),
        metadata={
            "description": "Ticked actions per area",
            "example": {"billing": ["payments"]},
        },
    )


class UserIdentitySchema(Schema):
    """The identity that travels with a token.

    One shape, returned by login, by the PIN picker and by ``/auth/me``, so
    the client has a single object to store and never has to merge a partial
    answer from one route into a stale one from another.
    """
    id = fields.String(metadata={"description": "User ID"})
    academy_id = fields.String(metadata={"description": "Academy ID"})
    name = fields.String(metadata={"description": "User name"})
    email = fields.String(metadata={"description": "Login address, empty for a PIN-only profile"})
    phone = fields.String(metadata={"description": "Phone number"})
    role = fields.String(metadata={"description": "User role: owner or staff"})
    picture = fields.String(metadata={"description": "Profile picture URL"})
    avatar_color_1 = fields.String(metadata={"description": "Avatar gradient color 1"})
    avatar_color_2 = fields.String(metadata={"description": "Avatar gradient color 2"})
    is_active = fields.Boolean(metadata={"description": "Account active status"})
    permissions = fields.Nested(PermissionGrantSchema, metadata={"description": "Resolved authority"})
    created_at = fields.String(metadata={"description": "ISO 8601 creation time"})
    updated_at = fields.String(metadata={"description": "ISO 8601 last-modified time"})


class TokenResponseSchema(Schema):
    """JWT token response."""
    access_token = fields.String(metadata={"description": "JWT access token"})
    refresh_token = fields.String(metadata={"description": "JWT refresh token (login only)"})
    user_id = fields.String(metadata={"description": "User ID"})
    name = fields.String(metadata={"description": "User name"})
    role = fields.String(metadata={"description": "User role: owner or staff"})
    academy_id = fields.String(metadata={"description": "Academy ID"})
    # The flat fields above are the legacy shape and stay for older clients.
    # This is the one the app reads: a single object carrying the role *and*
    # the permissions, so a client holding a freshly swapped token cannot be
    # left describing the person it used to be signed in as.
    user = fields.Nested(
        UserIdentitySchema,
        metadata={"description": "Identity belonging to the returned token"},
    )


class SignupResponseSchema(Schema):
    """POST /api/auth/signup response."""
    academy_id = fields.String(metadata={"description": "Newly created academy ID"})
    name = fields.String(metadata={"description": "Academy name"})


class CreateOwnerResponseSchema(Schema):
    """POST /api/auth/create-owner response."""
    id = fields.String(metadata={"description": "Owner user ID"})
    name = fields.String(metadata={"description": "Owner name"})
    role = fields.String(metadata={"description": "Role: owner"})
    academy_id = fields.String(metadata={"description": "Academy ID"})


class ProfileResponseSchema(Schema):
    """POST /api/auth/create-profile response."""
    id = fields.String(metadata={"description": "User ID"})
    name = fields.String(metadata={"description": "User name"})
    role = fields.String(metadata={"description": "Role: owner or staff"})


class ProfileListSchema(Schema):
    """Single profile in the profiles list."""
    id = fields.String(metadata={"description": "User ID"})
    name = fields.String(metadata={"description": "User name"})
    role = fields.String(metadata={"description": "Role: owner or staff"})
    picture = fields.String(metadata={"description": "Profile picture URL"})
    avatar_color_1 = fields.String(metadata={"description": "Avatar gradient color 1"})
    avatar_color_2 = fields.String(metadata={"description": "Avatar gradient color 2"})


class ProfileListResponseSchema(Schema):
    """GET /api/auth/profiles response."""
    profiles = fields.List(fields.Nested(ProfileListSchema))


class MeResponseSchema(UserIdentitySchema):
    """GET /api/auth/me response — the same identity a token arrives with."""


class PermissionAreaSchema(Schema):
    """One row of the permission table: an area and the actions it carries."""
    key = fields.String(metadata={"description": "Area key", "example": "billing"})
    actions = fields.List(
        fields.String(),
        metadata={"description": "Named actions in this area", "example": ["payments", "reports"]},
    )


class PermissionsCatalogResponseSchema(Schema):
    """GET /api/settings/permissions response.

    The catalogue the staff screen is drawn from: which areas exist, the three
    levels, the actions inside each area, and what a brand-new staff member
    starts with. Served rather than hard-coded in the client so the screen
    cannot offer a switch the server would not honour.
    """
    areas = fields.List(fields.Nested(PermissionAreaSchema))
    levels = fields.List(
        fields.String(),
        metadata={"description": "Selectable levels, weakest first", "example": ["none", "view", "manage"]},
    )
    default = fields.Dict(
        keys=fields.String(),
        values=fields.String(),
        metadata={"description": "What a new staff member starts with, per area"},
    )
