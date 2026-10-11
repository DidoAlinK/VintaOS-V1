"""
Vinta School OS — Tenant Service
Provisioning academies, default seeds (currency, plans, settings).
"""
import uuid
from datetime import datetime, timedelta, timezone
from app.extensions import db
from app.models.academy import Academy, AcademySettings, Subscription
from app.models.user import User
from app.models.billing import PaymentPlan


def create_academy(name: str, email: str, password: str) -> dict:
    """
    Full academy provisioning flow:
    1. Create Academy record
    2. Create AcademySettings with defaults
    3. Create Subscription (starter tier)
    4. Seed default PaymentPlans
    Returns the created academy dict.
    """
    academy = Academy(
        id=str(uuid.uuid4()),
        name=name,
        email=User.normalize_email(email),
        weekend_day=5,  # Friday for Algeria
        current_term="2026 — Fall term",
    )
    db.session.add(academy)
    db.session.flush()

    # AcademySettings defaults
    settings = AcademySettings(
        academy_id=academy.id,
        currency="DZD",
        default_plan_duration=30,
        billing_reminder_days_before=3,
        due_date_reminder_timing="same_day",
        auto_checkout_enabled=True,
        end_class_popup_enabled=True,
        default_theme="light",
        default_font_size="normal",
        default_language="fr",
    )
    db.session.add(settings)

    # Subscription defaults
    subscription = Subscription(
        academy_id=academy.id,
        tier="starter",
        status="active",
        invoicing_method="Manual",
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(subscription)

    # Seed default payment plans
    default_plans = [
        {"name": "Monthly — 3,500 DA", "duration_days": 30, "amount_da": 3500},
        {"name": "Monthly — 3,000 DA", "duration_days": 30, "amount_da": 3000},
        {"name": "Term — 9,000 DA", "duration_days": 90, "amount_da": 9000},
        {"name": "Term — 8,000 DA", "duration_days": 90, "amount_da": 8000},
    ]
    for plan in default_plans:
        pp = PaymentPlan(
            id=str(uuid.uuid4()),
            academy_id=academy.id,
            **plan,
        )
        db.session.add(pp)

    db.session.flush()
    return {"academy_id": academy.id, "name": academy.name}


def create_owner_profile(
    academy_id: str, name: str, email: str, password: str, pin: str
) -> User:
    """
    Create the initial owner profile for a newly provisioned academy.
    Called after academy signup during first-time setup.
    """
    owner = User(
        id=str(uuid.uuid4()),
        academy_id=academy_id,
        name=name,
        # Stored normalised: this is the address `authenticate_credentials`
        # will be searched with on every later login, and the two must match
        # exactly.
        email=User.normalize_email(email),
        role="owner",
        pin_hash=User.hash_pin(pin),
        password_hash=User.hash_password(password),
        is_active=True,
    )
    db.session.add(owner)
    db.session.flush()
    return owner


def create_staff_profile(
    academy_id: str,
    name: str,
    pin: str,
    phone: str = None,
    role: str = "staff",
    email: str = None,
    password: str = None,
    permissions_map: dict = None,
) -> User:
    """Create a new staff (or additional owner) profile.

    ``email``/``password`` are the optional second way in. A staff member given
    an address and a password can sign in by typing them; one given neither is
    exactly what every staff profile used to be — a name and a PIN, chosen at
    the picker. Both routes that create staff go through here, so the two
    cannot disagree about which fields are kept.

    ``permissions_map`` is validated by ``app/permissions.parse`` at the route,
    before it reaches this writer, so what lands in the column is always a
    complete map. Left ``None`` it stays NULL, which reads as the documented
    staff default — day-to-day work, no money, no settings.
    """
    from app.models.user import User

    user = User(
        id=str(uuid.uuid4()),
        academy_id=academy_id,
        name=name,
        # Empty string, not None: the column is NOT NULL and every pre-existing
        # PIN-only profile carries "" — `authenticate_credentials` matches on
        # the address, and the uniqueness check treats "" as no address at all.
        email=User.normalize_email(email) if email else "",
        phone=phone,
        role=role,
        pin_hash=User.hash_pin(pin),
        password_hash=User.hash_password(password) if password else None,
        permissions=permissions_map,
        is_active=True,
    )
    db.session.add(user)
    db.session.flush()
    return user


def get_academy_profiles(academy_id: str) -> list:
    """Get all active user profiles for an academy."""
    from app.models.user import User
    return User.query.filter_by(academy_id=academy_id, is_active=True).all()
