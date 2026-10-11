"""
Vinta School OS — Billing Models
PaymentPlan, StudentBilling, PaymentLog (legacy, kept for backward compat).
StudentSubscription, RevenueEntry, PayoutRecord (VINTA SCHOOL OS money model).
All monetary columns are Integer (DZD).
"""
import uuid
from datetime import date, datetime, timezone
from sqlalchemy import (
    String, Integer, Text, ForeignKey, DateTime, Date,
    JSON, Boolean, Index, UniqueConstraint,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db


class PaymentPlan(db.Model):
    """Reusable billing plans that can be assigned to students."""

    __tablename__ = "payment_plans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    academy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academies.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, comment="30 for monthly, 90 for term")
    amount_da: Mapped[int] = mapped_column(Integer, nullable=False, comment="Price in Algerian Dinars")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    academy = relationship("Academy", back_populates="payment_plans")
    billings = relationship("StudentBilling", back_populates="payment_plan", lazy="dynamic")

    def __repr__(self):
        return f"<PaymentPlan {self.name} {self.amount_da} DA>"


class StudentBilling(db.Model):
    """One record per billing cycle per student. Core billing entity."""

    __tablename__ = "student_billings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id"), nullable=False
    )
    payment_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payment_plans.id"), nullable=False
    )
    amount_da: Mapped[int] = mapped_column(Integer, nullable=False, comment="Amount due for this cycle")
    status: Mapped[str] = mapped_column(
        SAEnum("paid", "due", "overdue", name="billing_status_enum"),
        default="due",
    )
    due_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    paid_date: Mapped[datetime | None] = mapped_column(Date)
    paid_amount: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Actual amount paid (may differ if partial)"
    )
    cycle_start: Mapped[datetime] = mapped_column(Date, nullable=False)
    cycle_end: Mapped[datetime] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    student = relationship("Student", back_populates="billings")
    payment_plan = relationship("PaymentPlan", back_populates="billings")
    payment_logs = relationship(
        "PaymentLog", back_populates="student_billing", lazy="dynamic",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<StudentBilling {self.student_id} {self.amount_da} DA ({self.status})>"


class PaymentLog(db.Model):
    """Individual payment transactions against a billing record."""

    __tablename__ = "payment_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    student_billing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_billings.id"), nullable=False
    )
    amount_da: Mapped[int] = mapped_column(Integer, nullable=False, comment="Amount paid in this transaction")
    payment_method: Mapped[str | None] = mapped_column(
        String(50), comment="Cash, bank transfer, etc."
    )
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("classes.id"), nullable=True,
        comment="Course group / class this payment covers (money-model)"
    )
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sessions.id"), nullable=True,
        comment="Session this payment is linked to (money-model, finalize flow)"
    )
    recorded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False,
        comment="Which staff member logged the payment"
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    student_billing = relationship("StudentBilling", back_populates="payment_logs")
    recorded_by_user = relationship("User")

    def __repr__(self):
        return f"<PaymentLog {self.amount_da} DA>"


class StudentSubscription(db.Model):
    """Student purchase of a Class offer (credit-based or time-based).

    Table name is ``student_subscriptions`` to avoid colliding with the
    legacy SaaS ``subscriptions`` table (Academy tier gating in academy.py).
    """

    __tablename__ = "student_subscriptions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    academy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academies.id"), nullable=False
    )
    enrollment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("enrollments.id"), nullable=True
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id"), nullable=False
    )
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id"), nullable=False,
        comment="CourseGroup (-> classes.id)",
    )
    billing_model: Mapped[str] = mapped_column(String(20), nullable=False)
    total_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cycle_start_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    cycle_deadline: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    access_start_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    access_end_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    max_groups_included: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enrolled_group_ids: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="List of group (class) ids included"
    )
    amount_paid_da: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="DZD integer"
    )
    payment_method: Mapped[str] = mapped_column(
        SAEnum("CASH", "CCP", "BARIDI_MOB", name="subscription_payment_method_enum"),
        default="CASH", nullable=False,
    )
    recorded_by_staff_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    makeup_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", nullable=False,
        comment="ACTIVE|EXPIRED|OVERDUE|DEPLETED|CANCELLED|SUSPENDED",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    academy = relationship("Academy")
    student = relationship("Student")
    enrollment = relationship("Enrollment")
    group = relationship("Class")
    recorded_by = relationship("User")

    def __repr__(self):
        return f"<StudentSubscription {self.student_id} group={self.group_id} ({self.status})>"


# Backwards-compatible alias: spec calls this entity "Subscription".
Subscription = StudentSubscription


class RevenueEntry(db.Model):
    """Immutable revenue fact per conducted session allocation (DZD integers)."""

    __tablename__ = "revenue_entries"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    academy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academies.id"), nullable=False
    )
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("classes.id"), nullable=True
    )
    student_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("students.id"), nullable=True
    )
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sessions.id"), nullable=True
    )
    amount_da: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="DZD integer"
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    academy = relationship("Academy")
    group = relationship("Class")
    student = relationship("Student")
    session = relationship("Session")

    def __repr__(self):
        return f"<RevenueEntry {self.amount_da} DA session={self.session_id}>"


class PayoutRecord(db.Model):
    """Money owed to a teacher — either derived from a session, or recorded by hand.

    ``source`` says which:

    * ``SESSION`` — written by ``finalize_session`` from a conducted session's
      gross revenue. Carries a ``session_id``.
    * ``MANUAL`` — entered by the owner in Billing (a bonus, a correction, a
      one-off arrangement). Has **no** session, which is why ``session_id`` is
      nullable.

    ``session_id`` keeps its UNIQUE constraint because ``finalize_session``
    relies on it for idempotency ("one payout per session — reuse if raced").
    SQLite, PostgreSQL and MySQL all treat NULLs as distinct under a UNIQUE
    constraint, so a manually recorded payout never collides with another one.

    Ordering note: there was no timestamp on this table at all, so
    ``list_payouts`` had to sort by the *linked session's* date — which cannot
    work for a payout with no session. ``recorded_at`` (when the row was
    written) and ``payout_date`` (the day the money is for, which the owner
    picks) close that gap.
    """

    __tablename__ = "payout_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    academy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academies.id"), nullable=False
    )
    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teachers.id"), nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sessions.id"), unique=True, nullable=True
    )
    gross_revenue_da: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="DZD integer"
    )
    commission_type: Mapped[str] = mapped_column(String(20), nullable=False)
    commission_value: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="DZD integer"
    )
    teacher_cut_da: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="DZD integer"
    )
    status: Mapped[str] = mapped_column(
        SAEnum("PENDING", "PAID", name="payout_status_enum"),
        default="PENDING", nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SESSION", server_default="SESSION",
        comment="SESSION (derived from a conducted session) or MANUAL (owner-entered)",
    )
    payout_date: Mapped[date | None] = mapped_column(
        Date, nullable=True,
        comment="The day the payment is for; owner-chosen on a manual payout",
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Free note shown in the payment-records archive",
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        comment="When this row was written (the table had no timestamp before)",
    )
    recorded_by_staff_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True,
        comment="Which user recorded a MANUAL payout",
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_by_staff_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_payout_records_academy_recorded", "academy_id", "recorded_at"),
    )

    # Relationships
    academy = relationship("Academy")
    teacher = relationship("Teacher")
    session = relationship("Session")
    # Both point at users.id, so each relationship has to name its own column —
    # without this SQLAlchemy cannot tell them apart and raises at mapper
    # configuration time.
    paid_by = relationship("User", foreign_keys=[paid_by_staff_id])
    recorded_by = relationship("User", foreign_keys=[recorded_by_staff_id])

    def __repr__(self):
        return f"<PayoutRecord teacher={self.teacher_id} {self.teacher_cut_da} DA ({self.status})>"


class PayoutSchedule(db.Model):
    """When a teacher is paid — a cadence, not an event.

    Why this table exists at all, and why it is a table rather than two more
    columns on ``academy_settings``:

    * Every payout in this app is written **per session**. ``finalize_session``
      stamps one ``PayoutRecord`` with ``status="PENDING"`` each time a class is
      conducted, and it stays pending until somebody settles it. There is no
      month and no week anywhere in that flow — so "when is this teacher paid?"
      had no answer the database could give.
    * ``academy_settings`` can gain a *table* in every runtime for free:
      ``packaging/launcher.py`` calls ``db.create_all()`` on startup, which
      creates missing tables but **never** adds a missing column. A new column
      there would need the additive-ALTER dance (see
      ``add_teacher_share_percentage.py``) on every existing install, and that
      script is not bundled into the shipped ``.exe``. A new table simply
      appears, here, in dev MySQL, and in the packaged build alike.

    ``teacher_id`` is the whole design in one column:

    * ``NULL`` — the **academy default**, set in Settings → Billing Config. One
      row per academy. It is what applies to every teacher who has no row of
      their own.
    * set — that teacher's **override**, edited from their profile by anyone
      holding the money permission. It wins over the default.

    The partial-uniqueness implied above is enforced in the service rather than
    by a constraint: SQLite, MySQL and PostgreSQL all treat NULLs as distinct in
    a UNIQUE index, so a constraint on ``(academy_id, teacher_id)`` would happily
    admit two academy-default rows. ``payout_schedule_service.upsert_schedule``
    is the only writer and always reads-then-writes.

    ``cadence="NONE"`` is the default and means exactly what the app did before
    this table existed: payouts accumulate as PENDING and are settled by hand,
    with nothing ever marked due. An academy that never opens Settings keeps
    today's behaviour rather than silently acquiring a payroll calendar.
    """

    __tablename__ = "payout_schedules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    academy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academies.id"), nullable=False
    )
    teacher_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("teachers.id"), nullable=True,
        comment="NULL = the academy-wide default row; set = one teacher's override",
    )

    # Plain string, not a DB enum — the same reasoning `PayoutRecord.source`
    # and `EXPENSE_CATEGORIES` already follow: adding a cadence should be a code
    # change, never a table rebuild on a live academy database.
    cadence: Mapped[str] = mapped_column(
        String(20), nullable=False, default="NONE", server_default="NONE",
        comment="NONE (settle by hand) | WEEKLY | MONTHLY",
    )
    day_of_week: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="WEEKLY only: 0=Monday .. 6=Sunday, Python's date.weekday()",
    )
    day_of_month: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="MONTHLY only: 1..31. 31 in a 30-day month means the last day.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "academy_id", "teacher_id", name="uq_payout_schedule_per_teacher"
        ),
        Index("ix_payout_schedules_academy", "academy_id"),
    )

    # Relationships
    academy = relationship("Academy")
    teacher = relationship("Teacher")

    def __repr__(self):
        who = self.teacher_id or "academy-default"
        return f"<PayoutSchedule {who} {self.cadence}>"


# Canonical expense categories. Stored as a plain string (not a DB enum) so a
# new category is a code change and a deploy, never a migration on a live
# academy database — the same reasoning the money-model tables use for status.
EXPENSE_CATEGORIES = (
    "SUPPLIES",      # stationery: tables, markers, paper, chalk, boards
    "RENT",
    "UTILITIES",     # water, electricity, internet
    "SALARIES",      # non-teaching staff wages
    "MAINTENANCE",   # repairs, cleaning
    "EQUIPMENT",     # furniture, devices
    "MARKETING",
    "TRANSPORT",
    "TAXES",
    "OTHER",
)

EXPENSE_PAYMENT_METHODS = ("CASH", "CCP", "BARIDI_MOB", "BANK", "OTHER")


class Expense(db.Model):
    """A school operating expense — money that left the academy.

    Deliberately its own table rather than a negative RevenueEntry: revenue
    entries are immutable facts *generated* by the session lifecycle and are
    keyed to a student/session allocation, whereas an expense is a manually
    recorded admin fact with a category, a vendor and no student. Keeping them
    apart also means the net-profit figure can never be corrupted by a bug in
    the attendance-driven revenue path.

    All monetary values are integer DZD, matching every other money column.
    """

    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    academy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academies.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(40), nullable=False, default="OTHER",
        comment="One of EXPENSE_CATEGORIES",
    )
    label: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="What was bought, e.g. 'Whiteboard markers'"
    )
    amount_da: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="DZD integer, always positive"
    )
    quantity: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment=(
            "How many of the thing, when it comes in units — '3' boxes of "
            "markers for `amount_da` 45000. Optional: plenty of expenses are "
            "a single payment (rent, a licence). `amount_da` is always the "
            "total paid, never a unit price, so a total never has to be "
            "multiplied out to be correct."
        ),
    )
    expense_date: Mapped[datetime] = mapped_column(
        Date, nullable=False, comment="The day the money left"
    )
    vendor: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Who was paid, optional"
    )
    payment_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="CASH"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True,
        comment="Which staff member logged the expense",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_expenses_academy_date", "academy_id", "expense_date"),
    )

    # Relationships
    academy = relationship("Academy")
    recorded_by_user = relationship("User")

    def __repr__(self):
        return f"<Expense {self.category} {self.amount_da} DA ({self.expense_date})>"
