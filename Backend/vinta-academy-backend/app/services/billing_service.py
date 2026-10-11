"""
Vinta School OS — Billing Service
Cycle renewals, aging buckets (1-7d, 8-30d, 30d+), payment logs, status management.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import desc, func, extract
from app.extensions import db
from app.models.billing import (
    PaymentPlan,
    StudentBilling,
    PaymentLog,
    StudentSubscription,
    RevenueEntry,
    PayoutRecord,
    Expense,
    EXPENSE_CATEGORIES,
    EXPENSE_PAYMENT_METHODS,
)
from app.models.student import Student
from app.models.audit import ActivityLog
from app.services import academy_rules
from app.utils.formatters import days_overdue, overdue_bucket


def list_payment_plans(academy_id: str) -> list:
    """List all payment plans for an academy."""
    plans = PaymentPlan.query.filter_by(academy_id=academy_id).order_by(PaymentPlan.amount_da).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "duration_days": p.duration_days,
            "amount_da": p.amount_da,
        }
        for p in plans
    ]


def create_payment_plan(academy_id: str, data: dict) -> PaymentPlan:
    """Create a new payment plan."""
    plan = PaymentPlan(
        id=str(uuid.uuid4()),
        academy_id=academy_id,
        name=data["name"],
        duration_days=data["duration_days"],
        amount_da=data["amount_da"],
    )
    db.session.add(plan)
    db.session.flush()
    return plan


def list_student_billings(academy_id: str, student_id: str = None, status: str = None) -> list:
    """List billing records, optionally filtered by student and status."""
    query = StudentBilling.query.join(Student).filter(Student.academy_id == academy_id)

    if student_id:
        query = query.filter(StudentBilling.student_id == student_id)
    if status:
        query = query.filter(StudentBilling.status == status)

    billings = query.order_by(desc(StudentBilling.created_at)).all()

    return [
        {
            "id": b.id,
            "student_id": b.student_id,
            "student_name": f"{b.student.first_name} {b.student.last_name}" if b.student else None,
            "payment_plan": b.payment_plan.name if b.payment_plan else None,
            "amount_da": b.amount_da,
            "status": b.status,
            "due_date": b.due_date.isoformat(),
            "paid_date": b.paid_date.isoformat() if b.paid_date else None,
            "paid_amount": b.paid_amount,
            "cycle_start": b.cycle_start.isoformat(),
            "cycle_end": b.cycle_end.isoformat(),
            "days_overdue": days_overdue(b.due_date) if b.status == "overdue" else 0,
        }
        for b in billings
    ]


def record_payment(
    billing_id: str, amount: int, payment_method: str,
    recorded_by: str, academy_id: str, notes: str = None
) -> dict:
    """Record a payment against a billing record."""
    billing = db.session.get(StudentBilling, billing_id)
    if not billing:
        return None

    # Create payment log
    log_entry = PaymentLog(
        id=str(uuid.uuid4()),
        student_billing_id=billing_id,
        amount_da=amount,
        payment_method=payment_method,
        recorded_by=recorded_by,
        notes=notes,
    )
    db.session.add(log_entry)

    # Update billing
    billing.paid_amount = (billing.paid_amount or 0) + amount
    billing.updated_at = datetime.now(timezone.utc)

    if billing.paid_amount >= billing.amount_da:
        billing.status = "paid"
        billing.paid_date = date.today()

    db.session.flush()

    return {
        "billing_id": billing_id,
        "amount_paid": amount,
        "total_paid": billing.paid_amount,
        "status": billing.status,
    }


def check_overdue_billings(academy_id: str) -> int:
    """
    Check for billings that are past due_date and mark them as overdue.
    Returns count of newly overdue records.
    """
    today = date.today()
    overdue_billings = StudentBilling.query.join(Student).filter(
        Student.academy_id == academy_id,
        StudentBilling.status == "due",
        StudentBilling.due_date < today,
    ).all()

    count = 0
    for billing in overdue_billings:
        billing.status = "overdue"
        count += 1

        student = db.session.get(Student, billing.student_id)
        student_name = f"{student.first_name} {student.last_name}" if student else "Unknown"

        log = ActivityLog(
            id=str(uuid.uuid4()),
            academy_id=academy_id,
            # NULL, never the string "system": user_id is a foreign key to
            # users.id and SQLite enforces it, so the sentinel made this
            # sweep raise IntegrityError whenever it found an overdue row.
            # Nobody acted on an individual billing here — the sweep did.
            user_id=None,
            entity_type="billing",
            entity_id=billing.id,
            action="payment_overdue",
            description=f"Payment overdue — {student_name}",
        )
        db.session.add(log)

    if count > 0:
        db.session.flush()

    return count


def renew_billing_cycles(academy_id: str) -> int:
    """
    Create new billing records for students whose cycles have ended.
    Returns count of renewals created.
    """
    today = date.today()
    expired = StudentBilling.query.join(Student).filter(
        Student.academy_id == academy_id,
        StudentBilling.cycle_end <= today,
    ).all()

    count = 0
    for billing in expired:
        # Check if a renewal already exists
        existing = StudentBilling.query.filter(
            StudentBilling.student_id == billing.student_id,
            StudentBilling.payment_plan_id == billing.payment_plan_id,
            StudentBilling.cycle_start >= today,
        ).first()
        if existing:
            continue

        plan = billing.payment_plan
        if not plan:
            continue

        new_billing = StudentBilling(
            id=str(uuid.uuid4()),
            student_id=billing.student_id,
            payment_plan_id=plan.id,
            amount_da=plan.amount_da,
            status="due",
            due_date=today + timedelta(days=plan.duration_days),
            cycle_start=today,
            cycle_end=today + timedelta(days=plan.duration_days),
        )
        db.session.add(new_billing)
        count += 1

    if count > 0:
        db.session.flush()

    return count


def _unique_students_by_subscription_state(academy_id: str) -> dict:
    """Classify each student by the strongest subscription state they hold.

    A ``StudentSubscription`` row is one *purchase* — one student, one group.
    A student buying into three groups, or renewing twice, owns three rows but
    is one student. The donut counts people, so the rows are folded down to
    distinct ``student_id`` first.

    Where a student holds several states at once (say an ACTIVE subscription
    in maths and an EXPIRED one in physics) they are filed under their
    strongest state — active beats overdue beats due — so the three buckets
    partition the roster and their sum is the ring's centre figure. Filing
    them in every bucket they touch would make the ring add up to more
    students than the academy has.

    CANCELLED rows are ignored: a voided purchase is not a state of the money.
    """
    subs = StudentSubscription.query.filter(
        StudentSubscription.academy_id == academy_id,
        StudentSubscription.status != "CANCELLED",
    ).all()

    # Lower rank wins. Anything unrecognised (a status added later without
    # being taught to this function) lands in "due" rather than vanishing.
    RANK = {
        "ACTIVE": 0,
        "OVERDUE": 1,
        "SUSPENDED": 1,
        "EXPIRED": 2,
        "DEPLETED": 2,
    }

    best: dict[str, int] = {}
    for sub in subs:
        rank = RANK.get(sub.status, 2)
        current = best.get(sub.student_id)
        if current is None or rank < current:
            best[sub.student_id] = rank

    return {
        "paid": sum(1 for rank in best.values() if rank == 0),
        "overdue": sum(1 for rank in best.values() if rank == 1),
        "due": sum(1 for rank in best.values() if rank == 2),
        "total": len(best),
    }


def get_billing_stats(academy_id: str) -> dict:
    """Get aggregate billing statistics for the donut chart.

    Student ring: distinct students, bucketed by subscription state (see
    :func:`_unique_students_by_subscription_state`) — never the raw row count.

    Teacher ring: ``PayoutRecord``, the money model the session-finalisation
    flow actually writes. It has two states (PENDING / PAID); "overdue" is the
    slice of PENDING whose session is more than 30 days old, reusing the
    aging vocabulary ``get_aging_buckets`` already speaks.

    The legacy ``TeacherPayroll`` ring was dropped: no route generates payroll
    rows any more, so the ring was structurally all zeros and said nothing.

    Returns a flat dict matching the frontend ``BillingStats`` interface.
    """
    from app.models.student import Enrollment

    students = _unique_students_by_subscription_state(academy_id)

    # ── Teacher payout ring ───────────────────────────────
    payouts = (
        db.session.query(PayoutRecord, Session.date)
        .outerjoin(Session, PayoutRecord.session_id == Session.id)
        .filter(PayoutRecord.academy_id == academy_id)
        .all()
    )

    overdue_cutoff = date.today() - timedelta(days=30)
    teacher_pending = 0
    teacher_settled = 0
    teacher_overdue = 0
    for payout, session_date in payouts:
        if payout.status == "PAID":
            teacher_settled += 1
        elif session_date is not None and session_date < overdue_cutoff:
            teacher_overdue += 1
        else:
            teacher_pending += 1
    teacher_total = teacher_pending + teacher_settled + teacher_overdue

    # ── This month's income ───────────────────────────────
    today = date.today()
    month_start = today.replace(day=1)
    month_income = _collected_between(
        academy_id,
        datetime.combine(month_start, datetime.min.time()),
        datetime.combine(today, datetime.max.time()),
    )

    # ── Total active enrollments ──────────────────────────
    total_enrolled = Enrollment.query.join(Student).filter(
        Student.academy_id == academy_id,
        Enrollment.status == "active",
    ).count()

    return {
        "student_paid": students["paid"],
        "student_due": students["due"],
        "student_overdue": students["overdue"],
        "student_total": students["total"],
        "teacher_pending": teacher_pending,
        "teacher_settled": teacher_settled,
        "teacher_overdue": teacher_overdue,
        "teacher_total": teacher_total,
        "month_income": month_income,
        "total_enrolled": total_enrolled,
        # The academy's default teacher share (0–100). Surfaced here so the
        # Financial Reports split card and the payments panels read the same
        # number the settlement path uses, without a second owner-only call.
        "teacher_share_percentage": academy_rules.default_teacher_share_percentage(academy_id),
    }


def _collected_between(academy_id: str, start: datetime, end: datetime) -> int:
    """Money actually collected in [start, end], as integer DZD.

    Counted from ``StudentSubscription.amount_paid_da`` — the purchase row is
    the record of money that changed hands. Two things are excluded on
    purpose:

    * CANCELLED rows. A voided purchase returns nothing to the academy's
      income. (Attendance credit restores are a separate concern and do not
      rewrite the amount collected, which is what actually happened.)
    * Anything outside the window, so a month's figure is that month's money
      and not a running total.

    This is the one definition of "collected" the whole billing surface reads;
    the monthly chart, the weekly chart and the income KPI all call it.
    """
    return int(
        db.session.query(func.sum(StudentSubscription.amount_paid_da))
        .filter(
            StudentSubscription.academy_id == academy_id,
            StudentSubscription.status != "CANCELLED",
            StudentSubscription.created_at >= start,
            StudentSubscription.created_at <= end,
        )
        .scalar() or 0
    )


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    """First and last calendar day of a month."""
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return first, last


def _shift_month(year: int, month: int, back: int) -> tuple[int, int]:
    """Step a (year, month) back by ``back`` months."""
    index = year * 12 + (month - 1) - back
    return index // 12, index % 12 + 1


def _payout_effective_date(payout, session_date: date | None) -> date | None:
    """Which day a payout belongs to, for reporting.

    A payout derived from a session belongs to the day the class ran. A payout
    recorded by hand has no session at all, so it falls back to the day the
    owner said it was for, and failing that to the day it was written down.

    This is the rule ``list_payouts`` orders by and ``list_billing_records``
    filters on, stated in Python so the monthly report cannot bucket a payout
    under a different day than the archive lists it under. The two did disagree:
    the monthly chart read the session date alone, so every hand-recorded payout
    was counted in the all-time teacher-cost total and then dropped from every
    month — "calculated, but not showing up".
    """
    if session_date:
        return session_date
    if payout.payout_date:
        return payout.payout_date
    if payout.recorded_at:
        return payout.recorded_at.date()
    return None
def get_revenue_chart(academy_id: str, months: int = 6) -> list:
    """Monthly income for the last N months, from real payment rows.

    This used to read the legacy ``StudentBilling`` table with
    ``status == "paid"``. Nothing in the money-model flow ever writes that
    table — payments land in ``StudentSubscription`` — so every bar was zero
    and the chart was decorative. It now reads the same collection the KPI
    does, via :func:`_collected_between`.

    Shape is unchanged (``month`` / ``income`` / ``overdue_count``) so the
    dashboard, which shares this service function, keeps working.
    """
    from app.models.student import Enrollment

    today = date.today()
    months = max(1, min(int(months or 6), 36))
    chart_data = []

    for back in range(months - 1, -1, -1):
        year, month = _shift_month(today.year, today.month, back)
        month_start, month_end = _month_bounds(year, month)

        income = _collected_between(
            academy_id,
            datetime.combine(month_start, datetime.min.time()),
            datetime.combine(month_end, datetime.max.time()),
        )

        # Overdue is a live count of the debt still open, not a per-month
        # historical fact — the same figure on every row would be noise, so it
        # rides only on the newest row (as before).
        chart_data.append({
            "month": month_start.strftime("%b %Y"),
            "income": int(income),
            "overdue_count": 0,
        })

    if chart_data:
        chart_data[-1]["overdue_count"] = StudentSubscription.query.filter(
            StudentSubscription.academy_id == academy_id,
            StudentSubscription.status.in_(("OVERDUE", "SUSPENDED")),
        ).count()

    return chart_data


def get_weekly_income(academy_id: str, weeks: int = 12) -> list:
    """Weekly income for the last N weeks, from real payment rows.

    Weeks are ISO weeks starting Monday, labelled by their first day
    (``2026-09-28``). That keeps every bucket a fixed seven days rather than
    a month's ragged 28–31, which is the point of a weekly view: a payment is
    attributed to the week it was taken, and adding, confirming or voiding a
    payment moves exactly one bar.

    ``has_data`` marks the weeks inside the academy's own history — a week
    before the first payment ever taken is not "zero income", it is a week the
    academy was not running, and the chart greys it out.
    """
    today = date.today()
    weeks = max(1, min(int(weeks or 12), 104))
    this_monday = today - timedelta(days=today.weekday())

    first_payment_at = (
        db.session.query(func.min(StudentSubscription.created_at))
        .filter(
            StudentSubscription.academy_id == academy_id,
            StudentSubscription.status != "CANCELLED",
        )
        .scalar()
    )
    first_day = first_payment_at.date() if first_payment_at else None

    result = []
    for back in range(weeks - 1, -1, -1):
        week_start = this_monday - timedelta(weeks=back)
        week_end = week_start + timedelta(days=6)

        income = _collected_between(
            academy_id,
            datetime.combine(week_start, datetime.min.time()),
            datetime.combine(week_end, datetime.max.time()),
        )

        result.append({
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "label": week_start.strftime("%d %b"),
            "income": int(income),
            "has_data": first_day is not None and week_end >= first_day,
        })

    return result


def get_aging_buckets(academy_id: str) -> dict:
    """Classify overdue billings into aging buckets."""
    overdue = StudentBilling.query.join(Student).filter(
        Student.academy_id == academy_id,
        StudentBilling.status == "overdue",
    ).all()

    buckets = {"recent": [], "aging": [], "critical": []}
    for billing in overdue:
        days = days_overdue(billing.due_date)
        bucket = overdue_bucket(days)
        student = billing.student
        buckets[bucket].append({
            "id": billing.id,
            "student_name": f"{student.first_name} {student.last_name}" if student else "Unknown",
            "amount_da": billing.amount_da,
            "days_overdue": days,
        })

    return {
        "recent": {"count": len(buckets["recent"]), "items": buckets["recent"]},
        "aging": {"count": len(buckets["aging"]), "items": buckets["aging"]},
        "critical": {"count": len(buckets["critical"]), "items": buckets["critical"]},
    }


# ═══════════════════════════════════════════════════════════════════
# VINTA SCHOOL OS — Money Model Functions
# StudentSubscription, RevenueEntry, PayoutRecord, check-in side
# effects, session finalization, multi-payment, group swap.
# All monetary values are integers (DZD).
# ═══════════════════════════════════════════════════════════════════

from app.models.billing import (
    StudentSubscription, RevenueEntry, PayoutRecord,
)
from app.models.class_room import Class
from app.models.student import Enrollment
from app.models.scheduling import Session
from app.models.teacher import Teacher
from app.models.attendance import SessionStudent
from datetime import datetime, timezone, timedelta


def find_active_subscription(student_id: str, group_id: str) -> StudentSubscription | None:
    """Find the active subscription covering (student, group).

    Lookup order:
    1. Direct subscription: ``group_id`` matches and status is ACTIVE.
    2. Shared TIME_BASED subscription: ``group_id`` is listed in the
       subscription's ``enrolled_group_ids`` (multi-group bundle under the
       same teacher/subject/level).

    Stale subscriptions are lazily transitioned: TIME_BASED past its
    ``access_end_date`` becomes EXPIRED; CREDIT_BASED with no credits left
    becomes DEPLETED. Returns None when nothing usable covers the group.
    """
    candidates = (
        StudentSubscription.query.filter_by(student_id=student_id, status="ACTIVE")
        .order_by(StudentSubscription.created_at.desc())
        .all()
    )

    sub = next((s for s in candidates if s.group_id == group_id), None)
    if sub is None:
        sub = next(
            (
                s
                for s in candidates
                if s.billing_model == "TIME_BASED"
                and isinstance(s.enrolled_group_ids, list)
                and group_id in s.enrolled_group_ids
            ),
            None,
        )
    if sub is None:
        return None

    # For TIME_BASED, also check access window
    if sub.billing_model == "TIME_BASED" and sub.access_end_date:
        if sub.access_end_date < date.today():
            sub.status = "EXPIRED"
            db.session.flush()
            return None

    # For CREDIT_BASED, check credits remaining
    if sub.billing_model == "CREDIT_BASED":
        if (sub.remaining_credits or 0) <= 0:
            sub.status = "DEPLETED"
            db.session.flush()
            return None

    return sub


def find_subscription_for_level(
    student_id: str, teacher_id: str,
    subject: str | None = None, academic_level: str | None = None,
) -> StudentSubscription | None:
    """Find the active CREDIT_BASED subscription for a teaching level.

    A "level" is (``teacher_id``, ``subject``, ``academic_level``): any
    group with the same triple shares the credit pool, so students can
    swap groups (guest check-ins, makeups) without a new payment.
    When ``subject``/``academic_level`` are omitted, any group taught by
    the teacher matches (legacy behavior).
    """
    # Get all classes taught by this teacher, narrowed to the level.
    query = Class.query.filter_by(teacher_id=teacher_id)
    if subject is not None:
        query = query.filter_by(subject=subject)
    if academic_level is not None:
        query = query.filter_by(academic_level=academic_level)
    class_ids = [c.id for c in query.all()]
    if not class_ids:
        return None

    subs = StudentSubscription.query.filter(
        StudentSubscription.student_id == student_id,
        StudentSubscription.group_id.in_(class_ids),
        StudentSubscription.billing_model == "CREDIT_BASED",
        StudentSubscription.status == "ACTIVE",
        StudentSubscription.remaining_credits > 0,
    ).order_by(StudentSubscription.created_at.desc()).all()

    return subs[0] if subs else None


def create_subscription_for_payment(
    enrollment_or_group,
    amount: int,
    method: str,
    staff_id: str,
    academy_id: str,
    group_id: str = None,
) -> StudentSubscription | None:
    """Create a subscription for a payment covering a course group.

    Args:
        enrollment_or_group: an ``Enrollment`` instance, an enrollment id,
            a ``Class`` (group) instance, or a group id. When an enrollment
            (or its id) is given, the group is taken from it unless
            ``group_id`` overrides it.
        amount: amount received, integer DZD (no floating money).
        method: CASH | CCP | BARIDI_MOB (case-insensitive).
        staff_id: staff member recording the payment (PIN attribution is
            enforced at the route layer via ``@verify_staff_pin``; the id is
            stored on ``recorded_by_staff_id``).
        academy_id: tenant scope.
        group_id: explicit group override; also used to extend the
            ``enrolled_group_ids`` bundle of a shared TIME_BASED
            subscription.

    CREDIT_BASED: ``total = remaining = creditsPerCycle`` plus any
    rollover leftover from the student's most recent subscription for the
    same group when the group allows rollover.
    TIME_BASED: ``access_start`` is today; ``access_end`` is today +
    ``access_duration_weeks`` (or None for open-ended). Groups under the
    same teacher/subject/level share one subscription via
    ``enrolled_group_ids``: paying for an extra group extends the existing
    bundle (up to ``max_groups_included``) instead of creating a duplicate.
    Multi-group CREDIT_BASED payments create one Subscription per group.
    """
    from app.models.student import Enrollment as _Enrollment

    enrollment = None
    group = None
    if isinstance(enrollment_or_group, str):
        enrollment = db.session.get(_Enrollment, enrollment_or_group)
        group = db.session.get(Class, group_id) if group_id else None
        if enrollment is not None and group is None:
            group = db.session.get(Class, enrollment.class_id)
        elif group is not None and enrollment is None:
            group = group  # plain group id passed as first arg
            enrollment = None
    elif isinstance(enrollment_or_group, _Enrollment):
        enrollment = enrollment_or_group
        group = db.session.get(Class, group_id or enrollment.class_id)
    elif isinstance(enrollment_or_group, Class):
        group = enrollment_or_group
        if group_id:
            group = db.session.get(Class, group_id) or group
    elif enrollment_or_group is None and group_id:
        group = db.session.get(Class, group_id)

    # First positional arg may itself be a group id string.
    if group is None and isinstance(enrollment_or_group, str):
        maybe_group = db.session.get(Class, enrollment_or_group)
        if maybe_group is not None:
            group = maybe_group
            enrollment = None
    if group is None and group_id:
        group = db.session.get(Class, group_id)
    if group is None:
        return None

    group_id = group.id
    student_id = enrollment.student_id if enrollment is not None else None
    if student_id is None:
        # Caller passed only a group: nothing to attach — require enrollment.
        return None

    amount = int(amount or 0)
    method = (method or "CASH").upper()
    if method not in ("CASH", "CCP", "BARIDI_MOB"):
        method = "CASH"
    today = date.today()

    if group.billing_model == "TIME_BASED":
        existing = (
            StudentSubscription.query.filter_by(
                student_id=student_id, status="ACTIVE",
                billing_model="TIME_BASED",
            )
            .order_by(StudentSubscription.created_at.desc())
            .all()
        )
        for sub in existing:
            covered = list(sub.enrolled_group_ids or [])
            sibling = db.session.get(Class, sub.group_id)
            same_bundle = (
                sibling is not None
                and sibling.teacher_id == group.teacher_id
                and (sibling.subject or "") == (group.subject or "")
                and (sibling.academic_level or "") == (group.academic_level or "")
            )
            if sub.group_id == group_id or group_id in covered or same_bundle:
                if group_id not in covered:
                    if len(covered) >= max(int(sub.max_groups_included or 1), 1):
                        break  # bundle full — fall through to a new subscription
                    covered.append(group_id)
                    sub.enrolled_group_ids = covered
                sub.amount_paid_da = int(sub.amount_paid_da or 0) + amount
                if enrollment is not None and not sub.enrollment_id:
                    sub.enrollment_id = enrollment.id
                db.session.flush()
                return sub

    rollover_leftover = 0
    if group.billing_model == "CREDIT_BASED" and group.allow_rollover:
        previous = (
            StudentSubscription.query.filter_by(
                student_id=student_id, group_id=group_id,
                billing_model="CREDIT_BASED",
            )
            .order_by(StudentSubscription.created_at.desc())
            .first()
        )
        if previous is not None and (previous.remaining_credits or 0) > 0:
            rollover_leftover = int(previous.remaining_credits or 0)

    sub = StudentSubscription(
        id=str(uuid.uuid4()),
        academy_id=academy_id,
        student_id=student_id,
        group_id=group_id,
        enrollment_id=enrollment.id if enrollment is not None else None,
        billing_model=group.billing_model,
        amount_paid_da=amount,
        payment_method=method,
        recorded_by_staff_id=staff_id,
        status="ACTIVE",
    )

    if group.billing_model == "CREDIT_BASED":
        credits = int(group.credits_per_cycle or 0) + rollover_leftover
        sub.total_credits = credits
        sub.remaining_credits = credits
        sub.makeup_credits = 0
        sub.cycle_start_date = today
        if group.cycle_week_limit:
            sub.cycle_deadline = today + timedelta(weeks=int(group.cycle_week_limit))
    else:
        # TIME_BASED
        sub.access_start_date = today
        if group.access_duration_weeks:
            sub.access_end_date = today + timedelta(weeks=int(group.access_duration_weeks))
        else:
            sub.access_end_date = None
        sub.max_groups_included = int(group.max_groups_included or 1)
        sub.enrolled_group_ids = [group_id]

    db.session.add(sub)
    db.session.flush()
    return sub


def create_subscription(
    academy_id: str, student_id: str, group_id: str,
    amount: int, method: str, staff_id: str,
    enrollment_id: str = None,
) -> StudentSubscription:
    """Create a new subscription for a student paying for a course group.

    Thin wrapper around :func:`create_subscription_for_payment` kept for
    backward compatibility with existing callers. Handles both
    CREDIT_BASED and TIME_BASED models.
    """
    from app.models.student import Enrollment as _Enrollment

    enrollment = db.session.get(_Enrollment, enrollment_id) if enrollment_id else None
    if enrollment is None:
        enrollment = _Enrollment.query.filter_by(
            student_id=student_id, class_id=group_id, status="active"
        ).first()
    if enrollment is None:
        # No enrollment row (e.g. legacy caller): create a lightweight
        # in-memory enrollment so the payment still attaches to the student.
        enrollment = _Enrollment(
            id=str(uuid.uuid4()),
            student_id=student_id,
            class_id=group_id,
            status="active",
        )
        db.session.add(enrollment)
        db.session.flush()
    return create_subscription_for_payment(
        enrollment,
        amount,
        method,
        staff_id,
        academy_id,
        group_id=group_id,
    )


class MultiPaymentError(Exception):
    """A multi-payment could not be recorded — nothing was charged.

    Raised instead of returning an error-shaped dict: a dict carrying an
    ``error`` key is truthy, so a route's ``if not receipt`` guard reads the
    failure as success, commits, and answers 201. ``status_code`` is the
    HTTP status the route should answer with.
    """

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def record_multi_payment(
    student_id: str,
    items: list,
    total_received: int,
    method: str,
    staff_id: str,
    academy_id: str,
) -> dict:
    """Multi-teacher payment flow: one receipt covering several groups.

    Creates separate subscriptions — one per group paid (CREDIT_BASED
    groups each get their own Subscription row). TIME_BASED groups under
    the same teacher/subject/level share a subscription via
    ``enrolled_group_ids`` (see :func:`create_subscription_for_payment`).

    Args:
        student_id: payer.
        items: ``[{group_id, amount}]`` — amounts are integer DZD.
        total_received: cash actually received (integer DZD); each line
            item is validated and the receipt echoes the breakdown.
        method: CASH | CCP | BARIDI_MOB.
        staff_id: recording staff (PIN attribution at route layer).
        academy_id: tenant scope.

    Returns a receipt breakdown dict with per-group charges.

    Raises:
        MultiPaymentError: the receipt could not be produced — unknown
            student or group, an invalid line item (missing ``group_id`` or
            a non-positive amount), or a line item whose subscription could
            not be created. Callers must treat this as "nothing was charged".
    """
    from app.models.student import Student
    student = db.session.get(Student, student_id)
    if student is None:
        raise MultiPaymentError("Student not found", 404)
    student_name = f"{student.first_name} {student.last_name}"

    charges = []
    expected_total = 0
    for item in items or []:
        group_id = item.get("group_id")
        amount = int(item.get("amount") or 0)
        if not group_id or amount <= 0:
            raise MultiPaymentError(
                "Invalid line item (group_id and positive amount required)"
            )
        group = db.session.get(Class, group_id)
        if group is None:
            raise MultiPaymentError(f"Group not found: {group_id}", 404)

        # Separate Enrollment row per group paid (spec §1).
        enrollment = Enrollment.query.filter_by(
            student_id=student_id, class_id=group_id, status="active"
        ).first()
        if not enrollment:
            enrollment = Enrollment(
                id=str(uuid.uuid4()),
                student_id=student_id,
                class_id=group_id,
                status="active",
            )
            db.session.add(enrollment)
            db.session.flush()

        sub = create_subscription_for_payment(
            enrollment, amount, method, staff_id, academy_id,
            group_id=group_id,
        )
        if sub is None:
            # Student and group are both known here, so the factory returning
            # nothing is a server-side fault — never a receipt without a
            # subscription behind it.
            raise MultiPaymentError(
                f"Subscription could not be created for group {group_id}", 500
            )
        expected_total += amount
        charges.append({
            "group_id": group_id,
            "group_name": group.name,
            "amount_da": amount,
            "subscription_id": sub.id,
            "billing_model": group.billing_model,
            "credits": (
                sub.total_credits
                if group.billing_model == "CREDIT_BASED"
                else None
            ),
        })

    return {
        "student_id": student_id,
        "student_name": student_name,
        "total_da": int(total_received or 0),
        "expected_total_da": expected_total,
        "payment_method": (method or "CASH").upper(),
        "recorded_by_staff_id": staff_id,
        "charges": charges,
    }


def create_multi_payment(
    academy_id: str, student_id: str,
    items: list, total_received: int,
    method: str, staff_id: str,
) -> dict:
    """Multi-teacher payment: create separate subscriptions per group.

    Thin wrapper around :func:`record_multi_payment` kept for backward
    compatibility with existing callers. ``items`` =
    ``[{"group_id": ..., "amount": ...}]``. Returns receipt breakdown.
    """
    return record_multi_payment(
        student_id, items, total_received, method, staff_id, academy_id,
    )


def record_checkin_billing_side_effects(
    session_id: str, student_id: str, status: str,
    is_group_swap: bool, checked_in_by: str, academy_id: str,
) -> dict:
    """Apply billing side effects after an attendance record is created.

    Called by ``attendance_service.check_in_student`` (which owns the
    ``SessionStudent`` row) and by the finalise step for students who did not
    turn up; this function only touches money state.

    Two academy policies are consulted first, because both can mean "charge
    nothing here":

    * a free session bills nothing at all — no credit, no revenue;
    * with ``absence_consumes_credit`` off, an ABSENT student spends nothing
      and the seat they did not use earns nothing.

    CREDIT_BASED: the level subscription
    (``teacher_id`` + ``subject`` + ``academic_level``) is decremented by 1.
    When the group allows makeups and the student is ABSENT, a
    ``makeup_credits`` flag is incremented so the absence can be made up
    later. When ``remaining`` hits 0 the subscription becomes DEPLETED. A
    ``RevenueEntry`` of ``group.price_da`` (integer DZD) is recorded.
    TIME_BASED: no decrement. When the group enforces attendance the
    attended/conducted ratio is recomputed and the subscription becomes
    SUSPENDED below the group's threshold.
    """
    session = db.session.get(Session, session_id)
    if not session:
        return {"error": "Session not found"}

    group = db.session.get(Class, session.class_id)
    if not group:
        return {"error": "Group not found"}

    result = {"billing_model": group.billing_model, "actions": []}
    status = (status or "PRESENT").upper()

    # A free session records attendance for the register and bills nothing:
    # no credit is consumed and no revenue is written. Checked here rather
    # than at each call site so a manual check-in on a free session cannot
    # slip past it.
    if session.is_free_session:
        result["actions"].append("free session: no credit consumed, no revenue")
        return result

    # Whether an absence spends a credit is the academy's policy, read now
    # (never cached) rather than baked in. With the toggle off, only PRESENT
    # spends a credit — an absence is a free retry, and the seat it did not
    # use earns nothing.
    from app.services.academy_rules import absence_consumes_credit
    if status == "ABSENT" and not absence_consumes_credit(academy_id):
        result["actions"].append(
            "absence does not consume a credit (absence_consumes_credit=False)"
        )
        return result

    if group.billing_model == "CREDIT_BASED":
        # Level-based lookup: any group with same teacher + subject +
        # academic_level shares the credit pool (covers group swaps).
        sub = find_subscription_for_level(
            student_id, group.teacher_id,
            subject=group.subject, academic_level=group.academic_level,
        )
        if sub is None and not is_group_swap:
            sub = find_active_subscription(student_id, group.id)

        if sub and (sub.remaining_credits or 0) > 0:
            # The seat is consumed by the booking, not by the arrival — an
            # ABSENT student still spends a credit, which is the academy's
            # default. The toggle that can change that
            # (``absence_consumes_credit``) was already consulted above and
            # returned early, so by the time control reaches here a decrement
            # is always the intended outcome.
            sub.remaining_credits = int(sub.remaining_credits or 0) - 1
            result["subscription_id"] = sub.id
            result["actions"].append(f"credits decremented to {sub.remaining_credits}")

            if status == "ABSENT" and group.allow_makeups:
                sub.makeup_credits = int(sub.makeup_credits or 0) + 1
                result["actions"].append(
                    f"makeup credit granted (total {sub.makeup_credits})"
                )

            if (sub.remaining_credits or 0) <= 0:
                sub.remaining_credits = 0
                sub.status = "DEPLETED"
                result["actions"].append("subscription DEPLETED")
        else:
            result["actions"].append("no active subscription found or credits exhausted")

        # Revenue entry: academy earns the seat price on check-in.
        if int(group.price_da or 0) > 0:
            rev = RevenueEntry(
                id=str(uuid.uuid4()),
                academy_id=academy_id,
                group_id=group.id,
                student_id=student_id,
                session_id=session_id,
                amount_da=int(group.price_da),
            )
            db.session.add(rev)
            result["actions"].append(f"revenue entry: {group.price_da} Da")

    elif group.billing_model == "TIME_BASED":
        # No credit decrement — access is time-window based.
        sub = find_active_subscription(student_id, group.id)
        if sub is not None:
            result["subscription_id"] = sub.id
        result["actions"].append("time-based: no credit decrement")

        # Attendance enforcement: recompute attended/conducted ratio.
        if group.enforce_attendance and group.attendance_threshold:
            enrollment = Enrollment.query.filter_by(
                student_id=student_id, class_id=group.id, status="active"
            ).first()
            if enrollment is not None:
                enrolled_at = enrollment.enrolled_at.date() if hasattr(
                    enrollment.enrolled_at, "date") else enrollment.enrolled_at
            else:
                enrolled_at = sub.access_start_date if sub is not None else None

            conducted_q = SessionStudent.query.join(Session).filter(
                Session.class_id == group.id,
                Session.status.in_(["conducted", "completed"]),
            )
            attended_q = SessionStudent.query.filter_by(
                student_id=student_id, is_present=True
            ).join(Session).filter(
                Session.class_id == group.id,
                Session.status.in_(["conducted", "completed"]),
            )
            if enrolled_at is not None:
                conducted_q = conducted_q.filter(Session.date >= enrolled_at)
                attended_q = attended_q.filter(Session.date >= enrolled_at)
            total_conducted = conducted_q.count()
            total_attended = attended_q.count()

            result["attended"] = total_attended
            result["conducted"] = total_conducted
            if total_conducted > 0:
                ratio = total_attended / total_conducted
                result["attendance_ratio"] = round(ratio, 4)
                if ratio < float(group.attendance_threshold):
                    if sub is not None:
                        sub.status = "SUSPENDED"
                    result["actions"].append(
                        f"attendance below threshold: {ratio:.0%} < "
                        f"{float(group.attendance_threshold):.0%} — subscription SUSPENDED"
                    )

    db.session.flush()
    return result


def _session_duration_hours(session) -> float:
    """Session length in hours from start/end times (min 1h fallback)."""
    from app.utils.formatters import session_duration_hours

    if session.start_time and session.end_time:
        try:
            return max(session_duration_hours(session.start_time, session.end_time), 0.0)
        except Exception:
            return 1.0
    return 1.0


def _compute_teacher_cut(
    gross_da: int, commission_type: str, commission_value: int,
    duration_hours: float,
) -> int:
    """Compute the teacher's cut (integer DZD) for a conducted session.

    PERCENTAGE: ``gross * pct / 100``; FLAT_HOURLY: ``duration_hours *
    value``; FIXED_SESSION: flat ``value`` per session. All money stays
    integer — fractional hours are the only float in the pipeline.
    """
    gross_da = int(gross_da or 0)
    commission_value = int(commission_value or 0)
    if commission_type == "PERCENTAGE":
        return int(gross_da * commission_value / 100)
    if commission_type == "FLAT_HOURLY":
        return int(float(duration_hours or 0) * commission_value)
    if commission_type == "FIXED_SESSION":
        return commission_value
    return int(gross_da * commission_value / 100)


def finalize_session(
    session_id: str, conducted: bool, academy_id: str, staff_id: str,
) -> dict:
    """Finalize a session — the "Is class done?" flow.

    ``conducted=True``: status becomes CONDUCTED; gross revenue is the sum
    of ``RevenueEntry`` rows for the session (falling back to
    ``present check-ins × group.price_da`` when no entries exist yet);
    the teacher cut follows the teacher's ``commissionType``
    (PERCENTAGE / FLAT_HOURLY / FIXED_SESSION, integer DZD); a
    PENDING ``PayoutRecord`` with commission snapshots is created.
    ``conducted=False``: status becomes CANCELLED and no payout is
    created. Finalization is idempotent — re-finalizing returns the
    existing outcome (including the payout id) instead of duplicating.
    """
    session = db.session.get(Session, session_id)
    if not session or session.academy_id != academy_id:
        return {"error": "Session not found"}

    if conducted:
        existing_payout = PayoutRecord.query.filter_by(session_id=session_id).first()
        if session.status == "conducted" and existing_payout is not None:
            return {
                "session_id": session_id,
                "status": "conducted",
                "gross_revenue_da": int(existing_payout.gross_revenue_da or 0),
                "teacher_cut_da": int(existing_payout.teacher_cut_da or 0),
                "commission_type": existing_payout.commission_type,
                "payout_id": existing_payout.id,
            }

        session.status = "conducted"

        # Gross = sum of RevenueEntry rows for this session; fallback to
        # present check-ins × group price when entries are missing.
        entries = RevenueEntry.query.filter_by(session_id=session_id).all()
        gross = sum(int(e.amount_da or 0) for e in entries)
        group = db.session.get(Class, session.class_id)
        if gross == 0 and group is not None:
            roster_count = SessionStudent.query.filter_by(
                session_id=session_id, is_present=True
            ).count()
            gross = roster_count * int(group.price_da or 0)
        gross = int(gross)

        # Teacher cut per commissionType (integer DZD).
        teacher = db.session.get(Teacher, session.teacher_id)
        commission_type = (
            teacher.commission_type if teacher and teacher.commission_type
            else "PERCENTAGE"
        )
        commission_value = (
            int(teacher.commission_value)
            if teacher and teacher.commission_value is not None
            else academy_rules.default_teacher_share_percentage(academy_id)
        )
        teacher_cut = _compute_teacher_cut(
            gross, commission_type, commission_value,
            _session_duration_hours(session),
        )

        # One payout per session (unique session_id) — reuse if raced.
        payout = PayoutRecord.query.filter_by(session_id=session_id).first()
        if payout is None:
            payout = PayoutRecord(
                id=str(uuid.uuid4()),
                academy_id=academy_id,
                teacher_id=session.teacher_id,
                session_id=session_id,
                gross_revenue_da=gross,
                commission_type=commission_type,
                commission_value=commission_value,
                teacher_cut_da=teacher_cut,
                status="PENDING",
            )
            db.session.add(payout)
        db.session.flush()

        return {
            "session_id": session_id,
            "status": "conducted",
            "gross_revenue_da": gross,
            "teacher_cut_da": int(payout.teacher_cut_da or 0),
            "commission_type": payout.commission_type,
            "payout_id": payout.id,
        }
    else:
        session.status = "cancelled"
        # A cancelled session earns nothing: drop pending revenue facts and
        # never create a payout.
        RevenueEntry.query.filter_by(session_id=session_id).delete()
        PayoutRecord.query.filter_by(session_id=session_id).delete()
        db.session.flush()

        return {
            "session_id": session_id,
            "status": "cancelled",
        }


def list_subscriptions(
    academy_id: str, student_id: str = None,
    group_id: str = None, status: str = None,
) -> list:
    """List student subscriptions with optional filters."""
    from app.models.student import Student

    query = StudentSubscription.query.filter_by(academy_id=academy_id)
    if student_id:
        query = query.filter_by(student_id=student_id)
    if group_id:
        query = query.filter_by(group_id=group_id)
    if status:
        query = query.filter_by(status=status.upper())

    subs = query.order_by(StudentSubscription.created_at.desc()).all()
    result = []
    for sub in subs:
        student = db.session.get(Student, sub.student_id)
        group = db.session.get(Class, sub.group_id)
        result.append({
            "id": sub.id,
            "student_id": sub.student_id,
            "student_name": f"{student.first_name} {student.last_name}" if student else None,
            "group_id": sub.group_id,
            "group_name": group.name if group else None,
            "billing_model": sub.billing_model,
            "total_credits": sub.total_credits,
            "remaining_credits": sub.remaining_credits,
            "cycle_start_date": sub.cycle_start_date.isoformat() if sub.cycle_start_date else None,
            "cycle_deadline": sub.cycle_deadline.isoformat() if sub.cycle_deadline else None,
            "access_start_date": sub.access_start_date.isoformat() if sub.access_start_date else None,
            "access_end_date": sub.access_end_date.isoformat() if sub.access_end_date else None,
            "amount_paid_da": sub.amount_paid_da,
            "payment_method": sub.payment_method,
            "status": sub.status,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
        })
    return result


def renew_subscription(subscription_id: str, academy_id: str) -> dict:
    """Renew an expired/depleted subscription for the same group."""
    sub = db.session.get(StudentSubscription, subscription_id)
    if not sub or sub.academy_id != academy_id:
        return None

    group = db.session.get(Class, sub.group_id)
    if not group:
        return None

    now = date.today()
    if group.billing_model == "CREDIT_BASED":
        credits = group.credits_per_cycle
        # Rollover: if allow_rollover and previous has leftover
        if group.allow_rollover and sub.remaining_credits and sub.remaining_credits > 0:
            credits += sub.remaining_credits
        sub.total_credits = credits
        sub.remaining_credits = credits
        sub.cycle_start_date = now
        if group.cycle_week_limit:
            sub.cycle_deadline = now + timedelta(weeks=group.cycle_week_limit)
    else:
        sub.access_start_date = now
        if group.access_duration_weeks:
            sub.access_end_date = now + timedelta(weeks=group.access_duration_weeks)

    sub.status = "ACTIVE"
    sub.makeup_credits = 0
    db.session.flush()

    return {
        "id": sub.id,
        "status": sub.status,
        "total_credits": sub.total_credits,
        "remaining_credits": sub.remaining_credits,
    }


def serialize_payout(record: PayoutRecord) -> dict:
    """One payout record as the API returns it.

    The single source of truth for this shape. A payout just created by
    ``POST /payouts`` has to look identical to one returned by ``GET /payouts``,
    or the frontend needs two code paths for the same row.
    """
    teacher = db.session.get(Teacher, record.teacher_id)
    session = db.session.get(Session, record.session_id) if record.session_id else None

    session_date = session.date.isoformat() if session and session.date else None
    payout_date = record.payout_date.isoformat() if record.payout_date else None
    recorded_at = record.recorded_at.isoformat() if record.recorded_at else None
    effective = _payout_effective_date(record, session.date if session else None)

    return {
        "id": record.id,
        "teacher_id": record.teacher_id,
        "teacher_name": teacher.full_name if teacher else None,
        "session_id": record.session_id,
        "session_date": session_date,
        "gross_revenue_da": int(record.gross_revenue_da or 0),
        "commission_type": record.commission_type,
        "commission_value": int(record.commission_value or 0),
        "teacher_cut_da": int(record.teacher_cut_da or 0),
        "status": record.status,
        "paid_at": record.paid_at.isoformat() if record.paid_at else None,
        "paid_by_staff_id": record.paid_by_staff_id,
        "source": record.source or "SESSION",
        "notes": record.notes,
        "payout_date": payout_date,
        "recorded_at": recorded_at,
        "recorded_by_staff_id": record.recorded_by_staff_id,
        # The one date a row should be shown and sorted under, so the client
        # does not have to re-implement the session/manual fallback. Computed
        # by the shared helper, which the monthly report also reads, so the day
        # a payout is listed under is the day it counts in.
        "effective_date": effective.isoformat() if effective else None,
        # Kept for backward compatibility: the frontend already reads this key.
        # It was always the *session* date rather than a payout timestamp;
        # `recorded_at` above is the honest one.
        "created_at": session_date,
    }


def list_payouts(
    academy_id: str, teacher_id: str = None, status: str = None,
) -> list:
    """List teacher payout records with optional filters.

    Newest first, ordered by the best date the row actually has: the linked
    session's date, else the payout's own ``payout_date``, else the day it was
    recorded.

    The join to ``Session`` is an OUTER join deliberately. A manually recorded
    payout has no session, and an inner join would silently drop exactly the
    rows this list exists to show.
    """
    query = (
        PayoutRecord.query.filter_by(academy_id=academy_id)
        .outerjoin(Session, PayoutRecord.session_id == Session.id)
    )
    if teacher_id:
        query = query.filter(PayoutRecord.teacher_id == teacher_id)
    if status:
        query = query.filter(PayoutRecord.status == status.upper())

    # COALESCE, not Session.date on its own: a NULL session date sorts as the
    # smallest value, which would bury every manual payout at the bottom of the
    # list instead of placing it where it happened.
    effective_date = func.coalesce(
        Session.date,
        PayoutRecord.payout_date,
        func.date(PayoutRecord.recorded_at),
    )
    records = query.order_by(desc(effective_date), desc(Session.start_time)).all()
    return [serialize_payout(rec) for rec in records]


def mark_payout_paid(payout_id: str, academy_id: str, staff_id: str) -> dict:
    """Mark a payout record as PAID (owner-only, PIN verified at route layer)."""
    rec = db.session.get(PayoutRecord, payout_id)
    if not rec or rec.academy_id != academy_id:
        return None

    rec.status = "PAID"
    rec.paid_at = datetime.now(timezone.utc)
    rec.paid_by_staff_id = staff_id
    db.session.flush()

    return {"id": rec.id, "status": rec.status, "paid_at": rec.paid_at.isoformat()}


#: How a manually recorded payout was arrived at. The first three mirror
#: ``Teacher.commission_type`` exactly, so a manual payout is computed by the
#: same function as an automatic one. ``CUSTOM`` means the owner stated a flat
#: amount with no commission model behind it.
MANUAL_PAYOUT_BASES = ("PERCENTAGE", "FLAT_HOURLY", "FIXED_SESSION", "CUSTOM")


def create_manual_payout(academy_id: str, staff_id: str, data: dict) -> dict:
    """Record a teacher payout by hand. Raises ValueError on a bad field.

    Covers what the session-finalisation flow structurally cannot: a bonus, a
    correction, an advance, a one-off arrangement, or pay for a lesson that was
    never marked conducted. All of those are money the academy really owes, and
    until now there was nowhere to write them down.

    ``status`` decides where the record lands:

      * ``PAID``    — the money has already changed hands, so ``paid_at`` and
                      ``paid_by_staff_id`` are stamped now and it never appears
                      among the outstanding payouts.
      * ``PENDING`` — it joins the payout list to be marked paid later, exactly
                      like a session-derived payout.

    The amount goes through :func:`_compute_teacher_cut` for the three
    commission bases, so a payout entered here and one produced by
    ``finalize_session`` from the same gross and the same commission cannot
    disagree — a second calculation path is how two numbers start drifting
    apart. ``CUSTOM`` is the exception by definition: there is no percentage or
    rate to derive it from, so the stated amount is the amount.
    """
    raw_teacher_id = str(data.get("teacher_id") or "").strip()
    teacher = db.session.get(Teacher, raw_teacher_id) if raw_teacher_id else None
    if not teacher or teacher.academy_id != academy_id:
        raise ValueError("teacher_id must name a teacher in this academy")

    basis = str(
        data.get("basis") or data.get("commission_type") or ""
    ).strip().upper()
    if basis not in MANUAL_PAYOUT_BASES:
        raise ValueError("basis must be one of " + ", ".join(MANUAL_PAYOUT_BASES))

    status = str(data.get("status") or "PENDING").strip().upper()
    if status not in ("PENDING", "PAID"):
        raise ValueError("status must be PENDING or PAID")

    gross_da = int(data.get("gross_revenue_da") or 0)
    commission_value = int(data.get("commission_value") or 0)

    if basis == "CUSTOM":
        teacher_cut_da = _parse_amount(data.get("amount_da"))
        # Store the amount as the recorded rate so the row explains itself the
        # same way a FIXED_SESSION row does.
        commission_value = teacher_cut_da
    else:
        teacher_cut_da = _compute_teacher_cut(
            gross_da, basis, commission_value,
            float(data.get("duration_hours") or 0),
        )
        if teacher_cut_da <= 0:
            raise ValueError(
                "that works out to a payout of zero — check the gross amount, "
                "the rate, and the teacher's commission settings"
            )

    notes = data.get("notes")
    notes = (str(notes).strip() or None) if notes is not None else None

    now = datetime.now(timezone.utc)
    is_paid = status == "PAID"

    record = PayoutRecord(
        id=str(uuid.uuid4()),
        academy_id=academy_id,
        teacher_id=teacher.id,
        # No session: this is the manual path, and the column is nullable
        # precisely so this row can exist.
        session_id=None,
        gross_revenue_da=gross_da,
        commission_type=basis,
        commission_value=commission_value,
        teacher_cut_da=teacher_cut_da,
        status=status,
        source="MANUAL",
        # Optional: `_parse_date` insists on a value (right for an expense,
        # whose date is mandatory), but a manual payout without a stated date
        # simply falls back to when it was recorded.
        payout_date=_optional_date(data.get("payout_date"), "payout_date"),
        notes=notes,
        recorded_at=now,
        recorded_by_staff_id=staff_id,
        paid_at=now if is_paid else None,
        paid_by_staff_id=staff_id if is_paid else None,
    )
    db.session.add(record)
    db.session.flush()
    return serialize_payout(record)


#: The three things that move money in an academy. One vocabulary, so the
#: archive, the export and their filters all agree on what a "type" is.
BILLING_RECORD_KINDS = ("STUDENT_PAYMENT", "TEACHER_PAYOUT", "EXPENSE")


def _optional_date(raw, field: str):
    """An optional ``YYYY-MM-DD`` bound. ``None``/``""`` mean "unbounded"."""
    if raw is None or str(raw).strip() == "":
        return None
    return _parse_date(raw, field)


def _optional_int(raw, field: str):
    """An optional whole-number bound. ``None``/``""`` mean "unbounded"."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        raise ValueError(f"{field} must be a whole number")


def list_billing_records(academy_id: str, filters: dict = None) -> dict:
    """Every money record an academy has ever recorded, newest first.

    Three sources, one shape:

      * ``STUDENT_PAYMENT`` — a ``StudentSubscription`` purchase (money in)
      * ``TEACHER_PAYOUT``  — a ``PayoutRecord``, session-derived or manual (money out)
      * ``EXPENSE``         — an ``Expense`` (money out)

    They stay in their own tables, which is right: a subscription, a payout and
    an expense are genuinely different facts with different owners. They are
    unified here, at the edge, because the question the owner is actually asking
    — "what moved, and when?" — spans all three, and no single table can answer
    it.

    Filters: ``date_from``/``from``, ``date_to``/``to``, ``profile`` (a student
    or teacher id), ``type``, ``min_amount``, ``max_amount``. Raises ValueError
    on a malformed filter.

    Filtering is pushed into SQL per source where the columns allow it, then the
    three lists are merged in Python. A SQL UNION across three different notions
    of "date" would be harder to read and no faster at these volumes.
    """
    filters = filters or {}

    date_from = _optional_date(
        filters.get("date_from") or filters.get("from"), "from"
    )
    date_to = _optional_date(
        filters.get("date_to") or filters.get("to"), "to"
    )
    min_amount = _optional_int(filters.get("min_amount"), "min_amount")
    max_amount = _optional_int(filters.get("max_amount"), "max_amount")
    profile_id = str(filters.get("profile") or "").strip() or None
    kind = str(filters.get("type") or "").strip().upper() or None

    if kind and kind not in BILLING_RECORD_KINDS:
        raise ValueError("type must be one of " + ", ".join(BILLING_RECORD_KINDS))
    if date_from and date_to and date_from > date_to:
        raise ValueError("from must not be after to")
    if (
        min_amount is not None and max_amount is not None
        and min_amount > max_amount
    ):
        raise ValueError("min_amount must not exceed max_amount")

    def wants(record_kind: str) -> bool:
        return kind is None or kind == record_kind

    def in_window(day) -> bool:
        if day is None:
            return True
        if date_from and day < date_from:
            return False
        if date_to and day > date_to:
            return False
        return True

    def in_amount(amount: int) -> bool:
        if min_amount is not None and amount < min_amount:
            return False
        if max_amount is not None and amount > max_amount:
            return False
        return True

    records: list = []

    # ── Money in: student purchases ────────────────────────────────────
    #
    # A profile filter that names a teacher excludes these entirely, which is
    # the honest answer rather than an empty-looking bug: a teacher is not the
    # profile on a student's payment.
    if wants("STUDENT_PAYMENT"):
        query = StudentSubscription.query.filter_by(academy_id=academy_id)
        if profile_id:
            query = query.filter(StudentSubscription.student_id == profile_id)
        for sub in query.all():
            day = sub.created_at.date() if sub.created_at else None
            amount = int(sub.amount_paid_da or 0)
            if not in_window(day) or not in_amount(amount):
                continue
            student = db.session.get(Student, sub.student_id)
            group = db.session.get(Class, sub.group_id) if sub.group_id else None
            records.append({
                "id": sub.id,
                "kind": "STUDENT_PAYMENT",
                "date": day.isoformat() if day else None,
                "profile_id": sub.student_id,
                "profile_type": "STUDENT",
                "profile_name": (
                    f"{student.first_name} {student.last_name}".strip()
                    if student else None
                ),
                "label": group.name if group else None,
                "amount_da": amount,
                "direction": "IN",
                "status": sub.status,
                "method": sub.payment_method,
                "notes": None,
                # What the row was bought for, so a "why" is visible without
                # opening anything.
                "detail": sub.billing_model,
            })

    # ── Money out: teacher payouts ─────────────────────────────────────
    if wants("TEACHER_PAYOUT"):
        payout_query = PayoutRecord.query.filter_by(academy_id=academy_id)
        if profile_id:
            payout_query = payout_query.filter(PayoutRecord.teacher_id == profile_id)
        for payout in payout_query.all():
            serialized = serialize_payout(payout)
            amount = int(serialized["teacher_cut_da"] or 0)
            day_text = serialized["effective_date"]
            if not in_amount(amount):
                continue
            if not in_window(date.fromisoformat(day_text) if day_text else None):
                continue
            records.append({
                "id": payout.id,
                "kind": "TEACHER_PAYOUT",
                "date": day_text,
                "profile_id": payout.teacher_id,
                "profile_type": "TEACHER",
                "profile_name": serialized["teacher_name"],
                "label": None,
                "amount_da": amount,
                "direction": "OUT",
                "status": payout.status,
                # A payout has no payment method of its own; the style it was
                # computed under is the closest honest thing to it.
                "method": None,
                "notes": payout.notes,
                "source": serialized["source"],
                "commission_type": serialized["commission_type"],
                "commission_value": serialized["commission_value"],
                "gross_revenue_da": serialized["gross_revenue_da"],
                "detail": serialized["commission_type"],
            })

    # ── Money out: school expenses ─────────────────────────────────────
    #
    # An expense belongs to no profile, so any profile filter excludes the lot.
    if wants("EXPENSE") and not profile_id:
        for expense in Expense.query.filter_by(academy_id=academy_id).all():
            amount = int(expense.amount_da or 0)
            if not in_window(expense.expense_date) or not in_amount(amount):
                continue
            records.append({
                "id": expense.id,
                "kind": "EXPENSE",
                "date": (
                    expense.expense_date.isoformat() if expense.expense_date else None
                ),
                "profile_id": None,
                "profile_type": None,
                "profile_name": expense.vendor,
                "label": expense.label,
                "amount_da": amount,
                "direction": "OUT",
                "status": "PAID",
                "method": expense.payment_method,
                "notes": expense.notes,
                "detail": expense.category,
            })

    # Newest first. The id is the tie-break so the order is stable across calls
    # rather than merely arbitrary within a day.
    records.sort(key=lambda row: (row["date"] or "", row["id"]), reverse=True)

    money_in = sum(r["amount_da"] for r in records if r["direction"] == "IN")
    money_out = sum(r["amount_da"] for r in records if r["direction"] == "OUT")

    return {
        "records": records,
        "count": len(records),
        "totals": {
            "money_in_da": money_in,
            "money_out_da": money_out,
            "net_da": money_in - money_out,
        },
    }


def _same_level(group_a: Class, group_b: Class) -> bool:
    """Two groups share a billing level: same teacher + subject + level."""
    return (
        group_a is not None
        and group_b is not None
        and group_a.teacher_id == group_b.teacher_id
        and (group_a.subject or "") == (group_b.subject or "")
        and (group_a.academic_level or "") == (group_b.academic_level or "")
    )


def transfer_enrollment(enrollment_id: str, new_group_id: str) -> dict | None:
    """Transfer an enrollment to another group, keeping billing coherent.

    Same teacher/subject/level: the active subscription transparently
    follows — CREDIT_BASED pools are level-wide by design, and TIME_BASED
    bundles gain the new group via ``enrolled_group_ids`` (when the
    bundle still has room). The enrollment row is pointed at the new
    group and stays ``active``.
    Different level: the current subscription cannot cover the new group;
    the enrollment still moves but the result flags
    ``requires_new_payment=True`` so the caller can collect payment
    (e.g. via :func:`create_subscription_for_payment`).
    """
    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return None

    old_group = db.session.get(Class, enrollment.class_id)
    new_group = db.session.get(Class, new_group_id)
    if not old_group or not new_group:
        return None

    student_id = enrollment.student_id
    move = repoint_subscriptions_for_transfer(
        student_id, old_group.id, new_group_id
    )
    if "error" in move:
        return None

    enrollment.class_id = new_group_id
    enrollment.status = "active"
    db.session.flush()

    return {
        "enrollment_id": enrollment_id,
        "student_id": student_id,
        "old_group_id": old_group.id,
        "new_group_id": new_group_id,
        "same_level": move["same_level"],
        "requires_new_payment": move["requires_new_payment"],
        "moved_subscriptions": move["moved_subscriptions"],
    }


def repoint_subscriptions_for_transfer(
    student_id: str, old_group_id: str, new_group_id: str,
) -> dict:
    """Move a student's subscriptions across groups after a transfer.

    Same teacher/subject/level: ACTIVE subscriptions follow the move
    (CREDIT_BASED pools are level-wide; TIME_BASED bundles gain the new
    group via ``enrolled_group_ids`` when room allows) and stay ACTIVE.
    Different level: subscriptions stay put and the result flags
    ``requires_new_payment=True`` so the caller can collect a fresh
    payment for the new group.
    """
    old_group = db.session.get(Class, old_group_id)
    new_group = db.session.get(Class, new_group_id)
    if not old_group or not new_group:
        return {"error": "Group not found"}

    same = _same_level(old_group, new_group)
    moved: list[str] = []
    if same:
        for sub in StudentSubscription.query.filter_by(
            student_id=student_id, group_id=old_group_id, status="ACTIVE"
        ).all():
            if sub.billing_model == "CREDIT_BASED":
                sub.group_id = new_group_id
                moved.append(sub.id)
            elif sub.billing_model == "TIME_BASED":
                covered = list(sub.enrolled_group_ids or [])
                if new_group_id not in covered:
                    if len(covered) < max(int(sub.max_groups_included or 1), 1):
                        covered.append(new_group_id)
                        sub.enrolled_group_ids = covered
                sub.group_id = new_group_id
                moved.append(sub.id)
        db.session.flush()

    return {
        "same_level": same,
        "requires_new_payment": not same,
        "moved_subscriptions": moved,
    }


def guest_swap_checkin(student_id: str, session_id: str) -> dict:
    """Guest (group-swap) check-in helper for the service layer.

    Marks the attendance row ``is_group_swap=True`` and decrements the
    student's level-based CREDIT_BASED subscription (same
    teacher/subject/level as the session's group). Returns the attendance
    record id plus the billing side-effect summary. The attendance row
    itself is owned by ``attendance_service.check_in_student``.
    """
    from app.services import attendance_service as _attendance

    session = db.session.get(Session, session_id)
    if not session:
        return {"error": "Session not found"}

    # apply_billing=False: side effects are applied exactly once via the
    # explicit record_checkin_billing_side_effects call below.
    record = _attendance.check_in_student(
        session_id=session_id,
        student_id=student_id,
        academy_id=session.academy_id,
        checked_in_by=None,
        status="PRESENT",
        is_group_swap=True,
        apply_billing=False,
    )
    billing = record_checkin_billing_side_effects(
        session_id=session_id,
        student_id=student_id,
        status="PRESENT",
        is_group_swap=True,
        checked_in_by=record.checked_in_by,
        academy_id=session.academy_id,
    )
    return {
        "attendance_id": record.id,
        "session_id": session_id,
        "student_id": student_id,
        "is_group_swap": True,
        "billing": billing,
    }


def get_revenue(
    academy_id: str, group_id: str = None, session_id: str = None,
) -> dict:
    """Get revenue totals with optional filters."""
    query = RevenueEntry.query.filter_by(academy_id=academy_id)
    if group_id:
        query = query.filter_by(group_id=group_id)
    if session_id:
        query = query.filter_by(session_id=session_id)

    entries = query.all()
    total = sum(e.amount_da for e in entries)
    return {"total_da": total, "count": len(entries)}


def get_session_attendance_summary(student_id: str, subscription: StudentSubscription) -> dict:
    """
    Compute attendance summary for a student based on their subscription.
    Used by roster to show ATTENDANCE_WARNING badges.
    """
    from app.models.attendance import SessionStudent

    if not subscription:
        return {"total_sessions": 0, "attended": 0, "absent": 0, "attendance_rate": 1.0}

    # Count all session students for this student in the subscription's group
    total = SessionStudent.query.filter_by(student_id=student_id).count()
    attended = SessionStudent.query.filter_by(
        student_id=student_id, is_present=True
    ).count()

    rate = attended / total if total > 0 else 1.0

    return {
        "total_sessions": total,
        "attended": attended,
        "absent": total - attended,
        "attendance_rate": rate,
    }


# ═══════════════════════════════════════════════════════════════════
# Teacher payments — what the academy owes, per teacher and per group
#
# The source is ``PayoutRecord``: the money model stamps one row per
# conducted session with the gross it earned and the teacher's cut, and
# ``finalize_session`` is the only writer. Reading anything else here would
# be a second answer to a question that already has one.
#
# "Owed" and "paid" are the record's own two states (PENDING / PAID). The
# teacher's cut is earned when the class runs, not when the cash leaves, so
# the per-group figures below are earnings; whether they have been settled is
# carried alongside rather than folded in.
# ═══════════════════════════════════════════════════════════════════


def get_teacher_payments(academy_id: str, teacher_id: str = None) -> list:
    """Per-teacher payout totals, each with a breakdown by group.

    A teacher's revenue is the sum over *all* their groups — the same teacher
    may hold several classes, and reading only one of them is how the numbers
    drifted. Each group row below is that group's share of the same total, so
    the rows add up to the teacher's own figure.
    """
    query = (
        db.session.query(PayoutRecord, Session)
        .join(Session, PayoutRecord.session_id == Session.id)
        .filter(PayoutRecord.academy_id == academy_id)
    )
    if teacher_id:
        query = query.filter(PayoutRecord.teacher_id == teacher_id)

    by_teacher: dict[str, dict] = {}

    for payout, session in query.all():
        bucket = by_teacher.setdefault(payout.teacher_id, {
            "teacher_id": payout.teacher_id,
            "gross_revenue_da": 0,
            "teacher_cut_da": 0,
            "pending_da": 0,
            "paid_da": 0,
            "session_count": 0,
            "duration_hours": 0.0,
            "pending_count": 0,
            "paid_count": 0,
            "groups": {},
        })

        cut = int(payout.teacher_cut_da or 0)
        gross = int(payout.gross_revenue_da or 0)
        is_paid = payout.status == "PAID"
        # Length comes from the same helper the finalisation flow bills with, so
        # an hour reported here is the hour that was actually paid for rather
        # than a second guess at it.
        duration = _session_duration_hours(session)

        bucket["gross_revenue_da"] += gross
        bucket["teacher_cut_da"] += cut
        bucket["session_count"] += 1
        bucket["duration_hours"] += duration
        if is_paid:
            bucket["paid_da"] += cut
            bucket["paid_count"] += 1
        else:
            bucket["pending_da"] += cut
            bucket["pending_count"] += 1

        group_id = session.class_id
        group = bucket["groups"].setdefault(group_id, {
            "group_id": group_id,
            "group_name": None,
            "gross_revenue_da": 0,
            "teacher_cut_da": 0,
            "pending_da": 0,
            "paid_da": 0,
            "session_count": 0,
            "duration_hours": 0.0,
        })
        group["gross_revenue_da"] += gross
        group["teacher_cut_da"] += cut
        group["session_count"] += 1
        group["duration_hours"] += duration
        if is_paid:
            group["paid_da"] += cut
        else:
            group["pending_da"] += cut

    # Names and rosters, resolved once per teacher.
    for bucket in by_teacher.values():
        teacher = db.session.get(Teacher, bucket["teacher_id"])
        bucket["teacher_name"] = teacher.full_name if teacher else None

        class_ids = [cid for cid in bucket["groups"] if cid]
        name_by_class = {}
        if class_ids:
            name_by_class = {
                c.id: c.name
                for c in Class.query.filter(Class.id.in_(class_ids)).all()
            }
        for group_id, group in bucket["groups"].items():
            group["group_name"] = name_by_class.get(group_id)

        # The roster across every group the teacher holds — one student in
        # three of their groups is one student, so distinct ids are counted.
        bucket["group_count"] = len(bucket["groups"])
        bucket["student_count"] = _distinct_students_for_classes(
            _class_ids_for_teacher(bucket["teacher_id"])
        )
        bucket["groups"] = sorted(
            bucket["groups"].values(), key=lambda g: g["teacher_cut_da"], reverse=True
        )

    result = sorted(by_teacher.values(), key=lambda b: b["teacher_cut_da"], reverse=True)
    # Present the money as a plain summary first so callers do not have to
    # know which of the four cut columns they actually want.
    for bucket in result:
        bucket["owed_da"] = bucket["pending_da"]
        bucket["settled_da"] = bucket["paid_da"]
        # Summing 2-dp floats leaves noise (26.500000000000004), and an hours
        # figure that reads like that on screen is worse than rounding once here.
        bucket["duration_hours"] = round(bucket["duration_hours"], 2)
        for group in bucket["groups"]:
            group["duration_hours"] = round(group["duration_hours"], 2)

    return result


def _class_ids_for_teacher(teacher_id: str) -> list[str]:
    """Every class (group) assigned to a teacher."""
    return [c.id for c in Class.query.filter_by(teacher_id=teacher_id).all()]


def _distinct_students_for_classes(class_ids: list[str]) -> int:
    """Distinct active students enrolled in any of these classes."""
    if not class_ids:
        return 0
    return int(
        db.session.query(func.count(func.distinct(Enrollment.student_id)))
        .filter(
            Enrollment.class_id.in_(class_ids),
            Enrollment.status == "active",
        )
        .scalar() or 0
    )


def count_students_for_teacher(teacher_id: str) -> int:
    """Active students across all of a teacher's groups, counted once each.

    Shared by the teacher roster (which shows the figure per row) and the
    payments breakdown, so the two can never disagree.
    """
    return _distinct_students_for_classes(_class_ids_for_teacher(teacher_id))


# ═══════════════════════════════════════════════════════════════════
# School expenses — money that left the academy
#
# The model existed with no way to write or read it. These are the writers.
# Validation lives here rather than in the route so the rules travel with
# the data: a category the model does not know, a negative amount or a
# malformed date is refused with a sentence the desk can act on.
# ═══════════════════════════════════════════════════════════════════


def _parse_date(raw, field: str = "expense_date") -> date:
    """A ``YYYY-MM-DD`` string (or a date) as a date, or a ValueError."""
    if raw is None or raw == "":
        raise ValueError(f"{field} is required")
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw.strip())
        except ValueError:
            raise ValueError(f"{field} must be a date in YYYY-MM-DD form")
    raise ValueError(f"{field} must be a date in YYYY-MM-DD form")


def _parse_amount(raw) -> int:
    """A positive integer DZD amount, or a ValueError.

    Expenses are recorded as positive numbers and subtracted where they are
    used. Storing a sign here would let one record flip the meaning of a
    total on one typo.
    """
    if isinstance(raw, bool) or not isinstance(raw, int):
        # Accept a numeric string too — a form field arrives as text.
        if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
            raw = int(raw.strip())
        else:
            raise ValueError("amount_da must be a whole number of dinars")
    if raw <= 0:
        raise ValueError("amount_da must be greater than zero")
    if raw > 1_000_000_000:
        raise ValueError("amount_da is implausibly large")
    return int(raw)


def _parse_quantity(raw) -> int | None:
    """An optional positive integer unit count, or a ValueError.

    ``None``/``""`` mean "not stated" and are stored as NULL rather than 0 —
    zero of something is not a quantity anybody records, and a NULL keeps
    "we did not say" distinguishable from a number the desk did type.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        raise ValueError("quantity must be a whole number")
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        if not text.isdigit():
            raise ValueError("quantity must be a whole number")
        raw = int(text)
    if not isinstance(raw, int):
        raise ValueError("quantity must be a whole number")
    if raw < 1:
        raise ValueError("quantity must be at least 1")
    if raw > 1_000_000:
        raise ValueError("quantity is implausibly large")
    return int(raw)


def serialize_expense(expense: Expense) -> dict:
    """One expense row, in the shape the billing UI reads."""
    return {
        "id": expense.id,
        "category": expense.category,
        "label": expense.label,
        "amount_da": int(expense.amount_da or 0),
        "quantity": int(expense.quantity) if expense.quantity is not None else None,
        "expense_date": expense.expense_date.isoformat() if expense.expense_date else None,
        "vendor": expense.vendor,
        "payment_method": expense.payment_method,
        "notes": expense.notes,
        "created_at": expense.created_at.isoformat() if expense.created_at else None,
    }


def list_expenses(
    academy_id: str,
    start: date | None = None,
    end: date | None = None,
    category: str | None = None,
) -> list:
    """Expense records, newest first, optionally narrowed by window/category."""
    query = Expense.query.filter_by(academy_id=academy_id)
    if start is not None:
        query = query.filter(Expense.expense_date >= start)
    if end is not None:
        query = query.filter(Expense.expense_date <= end)
    if category:
        query = query.filter(Expense.category == category.upper())

    rows = query.order_by(desc(Expense.expense_date), desc(Expense.created_at)).all()
    return [serialize_expense(row) for row in rows]


def get_expense(expense_id: str, academy_id: str) -> Expense | None:
    """One expense, scoped to the academy."""
    expense = db.session.get(Expense, expense_id)
    if not expense or expense.academy_id != academy_id:
        return None
    return expense


def create_expense(academy_id: str, data: dict, recorded_by: str | None = None) -> dict:
    """Record a school expense. Raises ValueError on a bad field."""
    category = str(data.get("category") or "OTHER").strip().upper()
    if category not in EXPENSE_CATEGORIES:
        raise ValueError(
            "category must be one of " + ", ".join(EXPENSE_CATEGORIES)
        )

    label = str(data.get("label") or "").strip()
    if not label:
        raise ValueError("label is required")

    method = str(data.get("payment_method") or "CASH").strip().upper()
    if method not in EXPENSE_PAYMENT_METHODS:
        raise ValueError(
            "payment_method must be one of " + ", ".join(EXPENSE_PAYMENT_METHODS)
        )

    expense = Expense(
        id=str(uuid.uuid4()),
        academy_id=academy_id,
        category=category,
        label=label[:255],
        amount_da=_parse_amount(data.get("amount_da")),
        quantity=_parse_quantity(data.get("quantity")),
        expense_date=_parse_date(data.get("expense_date")),
        vendor=(str(data["vendor"]).strip()[:255] if data.get("vendor") else None),
        payment_method=method,
        notes=data.get("notes"),
        recorded_by=recorded_by,
    )
    db.session.add(expense)
    db.session.flush()
    return serialize_expense(expense)


def update_expense(expense_id: str, academy_id: str, data: dict) -> dict | None:
    """Edit an expense. Raises ValueError on a bad field, None if not found."""
    expense = get_expense(expense_id, academy_id)
    if not expense:
        return None

    if "category" in data:
        category = str(data["category"] or "").strip().upper()
        if category not in EXPENSE_CATEGORIES:
            raise ValueError("category must be one of " + ", ".join(EXPENSE_CATEGORIES))
        expense.category = category

    if "label" in data:
        label = str(data["label"] or "").strip()
        if not label:
            raise ValueError("label is required")
        expense.label = label[:255]

    if "payment_method" in data:
        method = str(data["payment_method"] or "").strip().upper()
        if method not in EXPENSE_PAYMENT_METHODS:
            raise ValueError(
                "payment_method must be one of " + ", ".join(EXPENSE_PAYMENT_METHODS)
            )
        expense.payment_method = method

    if "amount_da" in data:
        expense.amount_da = _parse_amount(data["amount_da"])

    if "quantity" in data:
        expense.quantity = _parse_quantity(data["quantity"])

    if "expense_date" in data:
        expense.expense_date = _parse_date(data["expense_date"])

    if "vendor" in data:
        expense.vendor = str(data["vendor"]).strip()[:255] if data["vendor"] else None

    if "notes" in data:
        expense.notes = data["notes"]

    db.session.flush()
    return serialize_expense(expense)


def delete_expense(expense_id: str, academy_id: str) -> bool:
    """Remove an expense. False if it is not this academy's."""
    expense = get_expense(expense_id, academy_id)
    if not expense:
        return False
    db.session.delete(expense)
    db.session.flush()
    return True


def get_expense_summary(academy_id: str, months: int = 6) -> dict:
    """Expenses by category and by month, plus the running totals.

    Categories with no spending are left out of ``by_category`` rather than
    listed as zero: the chart draws what happened, and a fixed palette of
    empty wedges implies a policy nobody set.
    """
    months = max(1, min(int(months or 6), 36))
    today = date.today()
    window_start, _ = _month_bounds(*_shift_month(today.year, today.month, months - 1))

    rows = Expense.query.filter_by(academy_id=academy_id).all()
    total_all = sum(int(r.amount_da or 0) for r in rows)

    by_category: dict[str, int] = {}
    by_method: dict[str, int] = {}
    for row in rows:
        by_category[row.category] = by_category.get(row.category, 0) + int(row.amount_da or 0)
        by_method[row.payment_method] = by_method.get(row.payment_method, 0) + int(row.amount_da or 0)

    series = []
    for back in range(months - 1, -1, -1):
        year, month = _shift_month(today.year, today.month, back)
        month_start, month_end = _month_bounds(year, month)
        amount = sum(
            int(r.amount_da or 0)
            for r in rows
            if r.expense_date and month_start <= r.expense_date <= month_end
        )
        series.append({
            "month": month_start.strftime("%b %Y"),
            "expense": amount,
        })

    window_total = sum(int(r.amount_da or 0) for r in rows if r.expense_date and r.expense_date >= window_start)

    return {
        "total_da": total_all,
        "window_total_da": window_total,
        "count": len(rows),
        "by_category": [
            {"category": category, "amount_da": amount}
            for category, amount in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "by_method": [
            {"payment_method": method, "amount_da": amount}
            for method, amount in sorted(by_method.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "series": series,
    }


def get_financial_summary(academy_id: str, months: int = 6) -> dict:
    """Revenue, teacher cost, expenses and net profit — all from live rows.

    ``net_profit_da = revenue − teacher cost − expenses``, with every term
    computed from the tables that own it. Teacher cost counts the cut earned
    by a conducted session, settled or not: the class ran, so the money is
    owed. How much of it has actually left is reported separately as
    ``teacher_paid_da`` / ``teacher_pending_da`` rather than being hidden in
    the subtraction.

    ``series`` carries the same three terms per month so the chart and the
    headline figure cannot drift apart — both are built from one pass.
    """
    months = max(1, min(int(months or 6), 36))
    today = date.today()

    # ── Revenue, all time and by month ────────────────────
    revenue_total = int(
        db.session.query(func.sum(StudentSubscription.amount_paid_da))
        .filter(
            StudentSubscription.academy_id == academy_id,
            StudentSubscription.status != "CANCELLED",
        )
        .scalar() or 0
    )

    # ── Teacher cost, all time ────────────────────────────
    payouts = PayoutRecord.query.filter_by(academy_id=academy_id).all()
    teacher_cost_total = sum(int(p.teacher_cut_da or 0) for p in payouts)
    teacher_paid_da = sum(int(p.teacher_cut_da or 0) for p in payouts if p.status == "PAID")
    teacher_pending_da = teacher_cost_total - teacher_paid_da

    # ── Expenses, all time ────────────────────────────────
    expenses = Expense.query.filter_by(academy_id=academy_id).all()
    expenses_total = sum(int(e.amount_da or 0) for e in expenses)

    net_profit = revenue_total - teacher_cost_total - expenses_total

    # ── Month-by-month series ─────────────────────────────
    # Teacher cost is bucketed by the session's date (when the class ran);
    # revenue by the purchase date; expenses by the day the money left.
    payout_months = (
        db.session.query(PayoutRecord, Session.date)
        .outerjoin(Session, PayoutRecord.session_id == Session.id)
        .filter(PayoutRecord.academy_id == academy_id)
        .all()
    )

    series = []
    for back in range(months - 1, -1, -1):
        year, month = _shift_month(today.year, today.month, back)
        month_start, month_end = _month_bounds(year, month)

        month_revenue = _collected_between(
            academy_id,
            datetime.combine(month_start, datetime.min.time()),
            datetime.combine(month_end, datetime.max.time()),
        )
        month_teacher = sum(
            int(payout.teacher_cut_da or 0)
            for payout, session_date in payout_months
            if (day := _payout_effective_date(payout, session_date))
            and month_start <= day <= month_end
        )
        month_expense = sum(
            int(e.amount_da or 0)
            for e in expenses
            if e.expense_date and month_start <= e.expense_date <= month_end
        )

        series.append({
            "month": month_start.strftime("%b %Y"),
            "revenue": month_revenue,
            "teacher_cost": month_teacher,
            "expense": month_expense,
            "net": month_revenue - month_teacher - month_expense,
        })

    return {
        "revenue_total_da": revenue_total,
        "teacher_cost_total_da": teacher_cost_total,
        "teacher_paid_da": teacher_paid_da,
        "teacher_pending_da": teacher_pending_da,
        "expenses_total_da": expenses_total,
        "net_profit_da": net_profit,
        "teacher_share_percentage": academy_rules.default_teacher_share_percentage(academy_id),
        "series": series,
    }
