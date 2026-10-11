"""When teachers get paid, and what a period is worth.

The app writes one ``PayoutRecord`` per conducted session
(``billing_service.finalize_session``), each starting life as ``PENDING`` and
staying that way until somebody settles it. That is a *ledger*, not a payroll:
nothing in it knows that teachers are paid on the 5th, or every Saturday, or
that a month's worth of pending rows has come due.

This module supplies that missing calendar — a cadence an owner sets once for
the academy and can override per teacher — and the period report that the
"due" card shows and the export prints.

Two things worth stating plainly, because they are the kind of thing that gets
quietly wrong:

* **Nothing here writes money.** A cadence decides whether something is
  *marked* due; settling is still ``billing_service.mark_payout_paid`` behind
  the owner's PIN. A scheduled week does not move money on its own, and it
  cannot, because nothing in this app runs on a timer — see
  ``app/tasks/scheduler.py``, whose ``init_scheduler`` has no call site. Every
  date below is computed on read, from ``date.today()``, so the answer is
  correct the moment somebody looks and needs no job to have fired.
* **A window is inclusive at both ends.** ``date_from`` and ``date_to`` are
  both counted. A report "for August" is the 1st through the 31st, not the 1st
  through the 30th.
"""

import calendar
from datetime import date, datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.attendance import SessionStudent
from app.models.billing import PayoutRecord, PayoutSchedule
from app.models.scheduling import Session
from app.models.teacher import Teacher
from app.utils.formatters import session_duration_hours

#: The cadences an academy may choose. NONE is "settle by hand", which is what
#: the app did before this module existed and remains the default.
CADENCES = ("NONE", "WEEKLY", "MONTHLY")

#: Python's ``date.weekday()`` order, spelled out for the one place that has to
#: translate it: the Settings screen.
WEEKDAY_NAMES = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
)


# ──────────────────────────────────────────────────────────────────────────
# Date arithmetic
#
# Kept as four small pure functions rather than one clever one, because the
# forward and backward answers are needed in different places (forward for
# "next payday" on screen, backward for "has this period closed?") and a single
# function that took a direction flag would have to be read twice to be trusted.
# ──────────────────────────────────────────────────────────────────────────


def _clamp_day(year: int, month: int, day: int) -> int:
    """`day`, or the last day of the month when the month is too short.

    A teacher paid on the 31st is paid on the 30th in April. The alternative —
    skipping April, or rolling into May — surprises the person being paid, and
    the whole point of a cadence is that it is predictable.
    """
    return min(int(day), calendar.monthrange(year, month)[1])


def _shift_month(year: int, month: int, step: int) -> tuple[int, int]:
    """The (year, month) `step` months away. `step` may be negative."""
    index = (year * 12 + (month - 1)) + step
    return index // 12, index % 12 + 1


def next_payout_date(
    cadence: str, day_of_week: int | None, day_of_month: int | None,
    from_date: date,
) -> date | None:
    """The first payday on or after `from_date`, or None for cadence NONE.

    "On or after" rather than "after" on purpose: on the 5th itself the desk
    wants to see that today is payday, not that the next one is a month away.
    """
    if cadence == "WEEKLY" and day_of_week is not None:
        delta = (int(day_of_week) - from_date.weekday()) % 7
        return from_date + timedelta(days=delta)

    if cadence == "MONTHLY" and day_of_month is not None:
        day = _clamp_day(from_date.year, from_date.month, day_of_month)
        candidate = date(from_date.year, from_date.month, day)
        if candidate >= from_date:
            return candidate
        year, month = _shift_month(from_date.year, from_date.month, 1)
        return date(year, month, _clamp_day(year, month, day_of_month))

    return None


def previous_payout_date(
    cadence: str, day_of_week: int | None, day_of_month: int | None,
    from_date: date,
) -> date | None:
    """The last payday on or before `from_date`, or None for cadence NONE.

    This is the date the currently-owed period closes on, which is what makes a
    payout "due" — see :func:`is_period_due`.
    """
    if cadence == "WEEKLY" and day_of_week is not None:
        delta = (from_date.weekday() - int(day_of_week)) % 7
        return from_date - timedelta(days=delta)

    if cadence == "MONTHLY" and day_of_month is not None:
        day = _clamp_day(from_date.year, from_date.month, day_of_month)
        candidate = date(from_date.year, from_date.month, day)
        if candidate <= from_date:
            return candidate
        year, month = _shift_month(from_date.year, from_date.month, -1)
        return date(year, month, _clamp_day(year, month, day_of_month))

    return None


def is_period_due(
    cadence: str, day_of_week: int | None, day_of_month: int | None,
    pending_dates: list[date], today: date | None = None,
) -> bool:
    """Whether an unpaid period has closed for this teacher.

    True when the cadence has fired at least once since the oldest unsettled
    payout — i.e. there is money in the ledger from a period that has ended and
    it has not been paid out. A teacher owed nothing is never "due", however
    long ago payday was: a due badge over a zero is a nag, not a fact.

    `pending_dates` are the effective dates of that teacher's PENDING payouts.
    Only the oldest matters, so the caller can pass them unsorted.
    """
    if cadence == "NONE" or not pending_dates:
        return False
    today = today or date.today()
    # The oldest unsettled payout is the one the period boundaries are measured
    # from: money earned before payday should be settled on payday.
    oldest = min(d for d in pending_dates if d is not None)
    due_on = previous_payout_date(cadence, day_of_week, day_of_month, today)
    return due_on is not None and oldest <= due_on


# ──────────────────────────────────────────────────────────────────────────
# Reading and writing schedules
# ──────────────────────────────────────────────────────────────────────────


def validate_cadence(
    cadence, day_of_week=None, day_of_month=None,
) -> tuple[str, int | None, int | None]:
    """Check a cadence triple, or raise ValueError explaining what is wrong.

    Returns the normalised triple, so the caller stores exactly what was
    validated rather than re-reading the request. Days that the chosen cadence
    does not use are returned as None — a weekly cadence that kept a stale
    day-of-month would be a trap for whoever reads the row next.
    """
    cadence = (cadence or "NONE").strip().upper()
    if cadence not in CADENCES:
        raise ValueError(f"cadence must be one of {', '.join(CADENCES)}")

    if cadence == "NONE":
        return cadence, None, None

    if cadence == "WEEKLY":
        if day_of_week is None or day_of_week == "":
            raise ValueError("a weekly payout needs a day of the week")
        try:
            weekday = int(day_of_week)
        except (TypeError, ValueError):
            raise ValueError("day_of_week must be a number from 0 to 6")
        if not 0 <= weekday <= 6:
            raise ValueError("day_of_week must be a number from 0 to 6")
        return cadence, weekday, None

    # MONTHLY
    if day_of_month is None or day_of_month == "":
        raise ValueError("a monthly payout needs a day of the month")
    try:
        day = int(day_of_month)
    except (TypeError, ValueError):
        raise ValueError("day_of_month must be a number from 1 to 31")
    if not 1 <= day <= 31:
        raise ValueError("day_of_month must be a number from 1 to 31")
    return cadence, None, day


def get_schedule_row(academy_id: str, teacher_id: str | None = None):
    """The stored row for a teacher (or the academy default), or None.

    `teacher_id=None` asks for the academy default. A teacher with no row of
    their own legitimately returns None here — that is what "inherit the
    default" looks like in the database, and :func:`resolve_schedule` is what
    turns it into an answer.
    """
    query = PayoutSchedule.query.filter_by(academy_id=academy_id)
    if teacher_id is None:
        query = query.filter(PayoutSchedule.teacher_id.is_(None))
    else:
        query = query.filter(PayoutSchedule.teacher_id == teacher_id)
    return query.first()


def upsert_schedule(
    academy_id: str, teacher_id: str | None, cadence, day_of_week=None,
    day_of_month=None,
):
    """Write a schedule row, creating it if this is the first time.

    Read-then-write rather than a database upsert, because the uniqueness that
    matters here — "one academy-default row per academy" — is not something a
    UNIQUE constraint can express: NULLs are distinct in a unique index on every
    engine this app runs on, so two default rows would be admitted happily.
    This function is the only writer, so doing it in one place is enough.

    Raises ValueError on a cadence that does not validate.
    """
    cadence, day_of_week, day_of_month = validate_cadence(
        cadence, day_of_week, day_of_month
    )

    row = get_schedule_row(academy_id, teacher_id)
    if row is None:
        row = PayoutSchedule(
            academy_id=academy_id,
            teacher_id=teacher_id,
            cadence=cadence,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
        )
        db.session.add(row)
    else:
        row.cadence = cadence
        row.day_of_week = day_of_week
        row.day_of_month = day_of_month

    db.session.flush()
    return row


def delete_schedule(academy_id: str, teacher_id: str) -> bool:
    """Drop a teacher's override so they go back to the academy default.

    There are three things a teacher's schedule can be, and two of them look
    alike if the row's absence is not treated as meaningful in its own right:

    * **no row** — "whatever the academy does". This function creates that
      state. It is the right answer when an owner changes the academy default
      and expects a teacher who was never individually configured to follow it.
    * **a row with cadence NONE** — "pay this one by hand, whatever the academy
      does". Stored, not deleted, precisely so it can disagree with the default;
      a contractor who invoices ad hoc should not acquire a payday because
      somebody set one for everyone else.
    * **a row with WEEKLY / MONTHLY** — the explicit override.

    Returns True when a row was removed, False when there was none — the caller
    distinguishes "reset" from "already following the academy" with that, and
    neither is an error.
    """
    row = get_schedule_row(academy_id, teacher_id)
    if row is None:
        return False
    db.session.delete(row)
    db.session.flush()
    return True


def set_teacher_schedule(
    academy_id: str, teacher_id: str, cadence, day_of_week=None,
    day_of_month=None,
) -> dict:
    """Apply a profile's schedule choice, including "follow the academy".

    The one writer for a per-teacher schedule, so the three states described on
    :func:`delete_schedule` are decided in a single place rather than by each
    route guessing what an incoming cadence means.

    ``cadence="INHERIT"`` is not a stored cadence — it is the absence of one,
    and it is spelled as a fourth value here because that is what the profile
    dropdown offers next to the other three. Everything else is validated by
    :func:`validate_cadence` and stored as given.

    Raises ValueError on a cadence that does not validate.
    """
    if str(cadence or "").strip().upper() == "INHERIT":
        delete_schedule(academy_id, teacher_id)
        return resolve_schedule(academy_id, teacher_id)

    upsert_schedule(academy_id, teacher_id, cadence, day_of_week, day_of_month)
    return resolve_schedule(academy_id, teacher_id)


def resolve_schedule(
    academy_id: str, teacher_id: str | None = None, today: date | None = None,
) -> dict:
    """A teacher's effective cadence: their override, else the academy default.

    This is the only function the rest of the app should call to ask "when does
    this teacher get paid". Reading the row directly is right only when the
    question is "what did *this teacher* configure" rather than "when are they
    paid" — which is why the distinction is named here instead of left to
    each caller.
    """
    override = get_schedule_row(academy_id, teacher_id) if teacher_id else None
    default = get_schedule_row(academy_id, None)

    source = override or default
    cadence = (source.cadence if source else "NONE") or "NONE"
    day_of_week = source.day_of_week if source else None
    day_of_month = source.day_of_month if source else None

    today = today or date.today()
    return {
        "teacher_id": teacher_id,
        "cadence": cadence,
        "day_of_week": day_of_week,
        "day_of_month": day_of_month,
        # Where the value came from, so the screen can say "from the academy"
        # rather than showing a number that looks edited but is not.
        "source": "teacher" if override is not None else ("academy" if default else "none"),
        "next_payout_date": _iso(
            next_payout_date(cadence, day_of_week, day_of_month, today)
        ),
        "last_payout_date": _iso(
            previous_payout_date(cadence, day_of_week, day_of_month, today)
        ),
    }


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value else None


# ──────────────────────────────────────────────────────────────────────────
# The period report
# ──────────────────────────────────────────────────────────────────────────


def _teacher_or_none(academy_id: str, teacher_id: str) -> Teacher | None:
    teacher = db.session.get(Teacher, teacher_id)
    if not teacher or teacher.academy_id != academy_id:
        return None
    return teacher


def _optional_date(raw, field: str) -> date | None:
    """An optional YYYY-MM-DD bound. None and "" both mean "unbounded"."""
    if raw is None or str(raw).strip() == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip())
    except ValueError:
        raise ValueError(f"{field} must be a date in YYYY-MM-DD form")


def _distinct_students_taught(teacher_id: str, start: date, end: date) -> int:
    """How many different students actually showed up to this teacher's classes.

    Deliberately not the same number as the roster count
    (``billing_service.count_students_for_teacher``), and both are reported
    because they answer different questions. The roster is "who is enrolled with
    them today"; this is "who did they teach in this window". A student who left
    in March still counts here for March and not at all in the roster, and the
    two disagreeing is correct rather than a bug to reconcile.

    `is_present` is the only filter that means anything: a roster row is created
    for every enrolled student the moment a class starts, defaulting to ABSENT
    (see ``SessionStudent.status``), so counting rows would count the register's
    blank lines as attendance.
    """
    total = (
        db.session.query(func.count(func.distinct(SessionStudent.student_id)))
        .select_from(SessionStudent)
        .join(Session, SessionStudent.session_id == Session.id)
        .filter(
            Session.teacher_id == teacher_id,
            SessionStudent.is_present.is_(True),
            Session.date >= start,
            Session.date <= end,
        )
        .scalar()
    )
    return int(total or 0)


def get_teacher_payout_details(
    academy_id: str, teacher_id: str, date_from=None, date_to=None,
    today: date | None = None, include_lines: bool = False,
) -> dict | None:
    """Everything behind the "due" card: what one teacher earned, and when.

    Returns None when the teacher is not in this academy, which the route turns
    into a 404 rather than an empty report — an empty report would read as "this
    teacher earned nothing", which is a different and much more alarming claim.

    The window defaults to *everything*, not to the current period. The card is
    opened to answer "what do we owe them", and a period filter that silently
    hid older unpaid rows would understate the very number it exists to show.
    Callers that want a period pass one.

    `include_lines` adds the individual payout rows under ``lines``. It is off
    by default because the card shows totals and a table of a few thousand rows
    would be a heavy way to say four numbers; the export turns it on because
    there the line items are the point of the file.

    Unlike ``get_teacher_payments``, the join to ``Session`` here is an OUTER
    join, so manually recorded payouts (a bonus, an advance) are included. That
    function excludes them on purpose — it is about session-derived earnings —
    but this one is about what the academy owes a person, and a bonus is owed.
    """
    teacher = _teacher_or_none(academy_id, teacher_id)
    if teacher is None:
        return None

    start = _optional_date(date_from, "from")
    end = _optional_date(date_to, "to")
    if start and end and start > end:
        raise ValueError("from must not be after to")

    # Which day a payout belongs to: the session's day, else the day the owner
    # said it was for, else the day it was written down. The same COALESCE
    # `list_payouts` orders by, so a payout lands in the same period wherever it
    # is reported.
    effective = func.coalesce(
        Session.date,
        PayoutRecord.payout_date,
        func.date(PayoutRecord.recorded_at),
    )

    query = (
        db.session.query(PayoutRecord, Session)
        .outerjoin(Session, PayoutRecord.session_id == Session.id)
        .filter(
            PayoutRecord.academy_id == academy_id,
            PayoutRecord.teacher_id == teacher_id,
        )
    )
    if start:
        query = query.filter(effective >= start)
    if end:
        query = query.filter(effective <= end)

    from app.services.billing_service import _session_duration_hours

    gross = 0
    cut = 0
    pending_da = 0
    paid_da = 0
    pending_count = 0
    paid_count = 0
    manual_count = 0
    session_count = 0
    duration_hours = 0.0
    pending_dates: list[date] = []
    groups: dict[str | None, dict] = {}
    lines: list[dict] = []

    for payout, session in query.all():
        row_gross = int(payout.gross_revenue_da or 0)
        row_cut = int(payout.teacher_cut_da or 0)
        is_paid = payout.status == "PAID"

        gross += row_gross
        cut += row_cut
        if is_paid:
            paid_da += row_cut
            paid_count += 1
        else:
            pending_da += row_cut
            pending_count += 1

        row_hours = 0.0
        if session is not None:
            session_count += 1
            row_hours = _session_duration_hours(session)
            duration_hours += row_hours
        else:
            manual_count += 1

        day = (
            session.date if session is not None
            else payout.payout_date
            or (payout.recorded_at.date() if payout.recorded_at else None)
        )
        if not is_paid and day is not None:
            pending_dates.append(day)

        # Per-group rows add up to the teacher's own figures, which is what
        # makes the breakdown checkable by hand rather than something the desk
        # has to take on trust.
        key = session.class_id if session is not None else None
        bucket = groups.setdefault(key, {
            "group_id": key,
            "group_name": None,
            "gross_revenue_da": 0,
            "teacher_cut_da": 0,
            "pending_da": 0,
            "paid_da": 0,
            "session_count": 0,
            "duration_hours": 0.0,
        })
        bucket["gross_revenue_da"] += row_gross
        bucket["teacher_cut_da"] += row_cut
        if is_paid:
            bucket["paid_da"] += row_cut
        else:
            bucket["pending_da"] += row_cut
        if session is not None:
            bucket["session_count"] += 1
            bucket["duration_hours"] += row_hours

        if include_lines:
            lines.append({
                "payout_id": payout.id,
                "date": day.isoformat() if day else None,
                "group_id": key,
                "group_name": None,          # filled in below, once names are known
                "session_id": payout.session_id,
                "source": payout.source or "SESSION",
                "commission_type": payout.commission_type,
                "commission_value": int(payout.commission_value or 0),
                "gross_revenue_da": row_gross,
                "teacher_cut_da": row_cut,
                "status": payout.status,
                "duration_hours": round(row_hours, 2),
                "notes": payout.notes,
            })

    # Names for the groups, in one query rather than one per group.
    from app.models.class_room import Class

    named = {
        c.id: c.name
        for c in Class.query.filter(
            Class.id.in_([k for k in groups if k])
        ).all()
    } if any(groups) else {}
    for group_id, bucket in groups.items():
        bucket["group_name"] = named.get(group_id)
        bucket["duration_hours"] = round(bucket["duration_hours"], 2)

    for line in lines:
        line["group_name"] = named.get(line["group_id"])

    schedule = resolve_schedule(academy_id, teacher_id, today)

    # "Average class revenue" is the number the details card was asked for and
    # the one no code computed: gross over sessions, guarded, because a teacher
    # with no sessions yet is a 0/0 and not a crash.
    average_class_revenue = int(gross / session_count) if session_count else 0
    average_cut = int(cut / session_count) if session_count else 0

    return {
        "teacher_id": teacher.id,
        "teacher_name": teacher.full_name,
        "teacher_status": teacher.status,
        "commission_type": teacher.commission_type,
        "commission_value": int(teacher.commission_value or 0),
        "window": {
            "from": start.isoformat() if start else None,
            "to": end.isoformat() if end else None,
        },
        "gross_revenue_da": gross,
        "teacher_cut_da": cut,
        "pending_da": pending_da,
        "paid_da": paid_da,
        "owed_da": pending_da,
        "settled_da": paid_da,
        "pending_count": pending_count,
        "paid_count": paid_count,
        "payout_count": pending_count + paid_count,
        "session_count": session_count,
        "manual_count": manual_count,
        "duration_hours": round(duration_hours, 2),
        "average_class_revenue_da": average_class_revenue,
        "average_cut_per_session_da": average_cut,
        # Two student counts, both honest, answering different questions —
        # see `_distinct_students_taught`.
        "students_taught": _distinct_students_taught(
            teacher_id,
            start or date(1970, 1, 1),
            end or date(2100, 1, 1),
        ),
        "students_enrolled": _enrolled_count(teacher_id),
        "group_count": len([g for g in groups if g]),
        "groups": sorted(
            groups.values(), key=lambda g: g["teacher_cut_da"], reverse=True
        ),
        "schedule": schedule,
        "due": {
            "is_due": is_period_due(
                schedule["cadence"], schedule["day_of_week"],
                schedule["day_of_month"], pending_dates, today,
            ),
            "pending_da": pending_da,
            "oldest_pending_date": (
                min(pending_dates).isoformat() if pending_dates else None
            ),
        },
        # Newest first, so a statement reads the way a bank statement does. The
        # loop above walks the query's own order, which is not a promise, so the
        # sort is explicit rather than assumed.
        "lines": sorted(
            lines, key=lambda line: line["date"] or "", reverse=True
        ) if include_lines else None,
    }


def _enrolled_count(teacher_id: str) -> int:
    """The current active roster across a teacher's groups.

    A local import because ``billing_service`` imports this package's siblings
    and a module-level import here would close a cycle at load time.
    """
    from app.services.billing_service import count_students_for_teacher

    return count_students_for_teacher(teacher_id)


def list_due_teachers(
    academy_id: str, today: date | None = None,
) -> list[dict]:
    """Every teacher with an unpaid period that has closed.

    One query for the pending dates of every teacher, then the date arithmetic
    in Python: a cadence is not a column, so whether a teacher is due cannot be
    asked of the database without materialising a row per (teacher, period),
    which is a job — and there is no job runner here.

    Returns a list of ``{teacher_id, teacher_name, pending_da, pending_count,
    ...}`` for the teachers who are due, largest debt first.
    """
    today = today or date.today()

    rows = (
        db.session.query(PayoutRecord, Session)
        .outerjoin(Session, PayoutRecord.session_id == Session.id)
        .filter(
            PayoutRecord.academy_id == academy_id,
            PayoutRecord.status == "PENDING",
        )
        .all()
    )

    by_teacher: dict[str, dict] = {}
    for payout, session in rows:
        bucket = by_teacher.setdefault(payout.teacher_id, {
            "pending_da": 0,
            "pending_count": 0,
            "dates": [],
        })
        bucket["pending_da"] += int(payout.teacher_cut_da or 0)
        bucket["pending_count"] += 1
        day = (
            session.date if session is not None
            else payout.payout_date
            or (payout.recorded_at.date() if payout.recorded_at else None)
        )
        if day is not None:
            bucket["dates"].append(day)

    due: list[dict] = []
    for teacher_id, bucket in by_teacher.items():
        schedule = resolve_schedule(academy_id, teacher_id, today)
        if not is_period_due(
            schedule["cadence"], schedule["day_of_week"],
            schedule["day_of_month"], bucket["dates"], today,
        ):
            continue

        teacher = db.session.get(Teacher, teacher_id)
        due.append({
            "teacher_id": teacher_id,
            "teacher_name": teacher.full_name if teacher else None,
            "pending_da": bucket["pending_da"],
            "pending_count": bucket["pending_count"],
            "oldest_pending_date": (
                min(bucket["dates"]).isoformat() if bucket["dates"] else None
            ),
            "last_payout_date": schedule["last_payout_date"],
            "next_payout_date": schedule["next_payout_date"],
            "cadence": schedule["cadence"],
        })

    return sorted(due, key=lambda d: d["pending_da"], reverse=True)


def format_cadence(cadence: str, day_of_week=None, day_of_month=None) -> str:
    """A cadence as one English phrase. For the export and the activity log.

    Not translated here: the PDF and the CSV already carry a language, and this
    returns the *English* phrase that the catalogue keys are built from — the
    export looks up ``payout.cadence.<key>`` rather than embedding prose that
    would then be invisible to the translator.
    """
    if cadence == "WEEKLY" and day_of_week is not None:
        # Deliberately not spread modulo 7. A cadence can only be written with
        # a day in 0..6 (``validate_cadence`` refuses anything else), so a
        # number outside that range means the row was handwritten, imported, or
        # written by something that did not ask us. Wrapping it would answer
        # "every Wednesday" for 9 — a confident, specific, wrong day on a
        # financial document. "none" says we could not read it, which is true.
        day = int(day_of_week)
        if 0 <= day <= 6:
            return f"weekly:{WEEKDAY_NAMES[day]}"
    if cadence == "MONTHLY" and day_of_month is not None:
        day = int(day_of_month)
        if 1 <= day <= 31:
            return f"monthly:{day}"
    return "none"


