"""
Vinta School OS — Billing Blueprint
/api/billing — Payment Plans, Cycles, Installments, Overdue, Revenue
"""
from flask_smorest import Blueprint
from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.utils.decorators import tenant_required, verify_staff_pin, require_permission, require_any_permission
from app.utils.audit import log_activity
from app.services import billing_service
from app.schemas.billing import (
    CreatePlanRequestSchema, RecordPaymentRequestSchema,
    PaymentPlanListResponseSchema, StudentBillingListResponseSchema,
    BillingStatsResponseSchema, RevenueChartResponseSchema,
    AgingBucketsResponseSchema, PayrollListResponseSchema, RecordPaymentResponseSchema,
)
from app.schemas.base import ErrorSchema, MessageSchema

billing_bp = Blueprint("billing", __name__, description="Payment plans, billing cycles & payroll")


def _query_date(name):
    """
    Read an optional YYYY-MM-DD query param as a date.

    Returns None when absent. Raises ValueError with a sentence naming the
    parameter when it is present but unreadable — a silently ignored date
    filter reads as "no expenses in that window", which is a wrong answer
    rather than an obvious failure.
    """
    from datetime import date as _date

    raw = request.args.get(name)
    if raw is None or raw == "":
        return None
    try:
        return _date.fromisoformat(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be a date in YYYY-MM-DD form")


@billing_bp.route("/plans", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "view")
def list_plans():
    """List all payment plans for the academy."""
    from flask import g
    plans = billing_service.list_payment_plans(g.current_academy_id)
    return jsonify({"plans": plans}), 200


@billing_bp.route("/plans", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("billing", "manage")
def create_plan():
    """
    Create a new payment plan.
    Body: { name, duration_days, amount_da }
    """
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    required = ("name", "duration_days", "amount_da")
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    plan = billing_service.create_payment_plan(g.current_academy_id, data)
    db.session.commit()

    return jsonify({
        "id": plan.id,
        "name": plan.name,
        "duration_days": plan.duration_days,
        "amount_da": plan.amount_da,
    }), 201


@billing_bp.route("/students", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "view")
def list_student_billings():
    """
    List billing records.
    Query params: student_id, status
    """
    from flask import g
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    billings = billing_service.list_student_billings(
        g.current_academy_id, student_id, status
    )
    return jsonify({"billings": billings}), 200


@billing_bp.route("/record-payment", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("billing", "payments")
def record_payment():
    """
    Record a payment against a billing record.
    Body: { billing_id, amount, payment_method, notes? }
    """
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    required = ("billing_id", "amount")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    result = billing_service.record_payment(
        billing_id=data["billing_id"],
        amount=data["amount"],
        payment_method=data.get("payment_method", "cash"),
        recorded_by=g.current_user.id,
        academy_id=g.current_academy_id,
        notes=data.get("notes"),
    )
    if not result:
        return jsonify({"error": "Billing record not found"}), 404

    log_activity(
        academy_id=g.current_academy_id,
        user_id=g.current_user.id,
        entity_type="payment",
        entity_id=data["billing_id"],
        action="payment_received",
        description=f"Payment of {data['amount']} received",
        metadata={"amount": data["amount"], "payment_method": data.get("payment_method", "cash")},
    )

    db.session.commit()
    return jsonify(result), 200


@billing_bp.route("/stats", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "reports")
def get_stats():
    """
    Get billing stats for the donut ring cards (owner-only).

    Owner-gated because it is the Billing section's own summary — the sidebar
    hides the section from staff, and the API now agrees rather than trusting
    the client to have hidden it. The staff-visible dashboard reads the same
    figures through /analytics/dashboard, which is a separate surface.
    """
    from flask import g
    stats = billing_service.get_billing_stats(g.current_academy_id)
    return jsonify(stats), 200


@billing_bp.route("/revenue-chart", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "reports")
def get_revenue_chart():
    """
    Get revenue chart data (owner-only).
    Query params: months (default 6)
    """
    from flask import g
    months = request.args.get("months", 6, type=int)
    chart_data = billing_service.get_revenue_chart(g.current_academy_id, months)
    return jsonify({"chart_data": chart_data}), 200


@billing_bp.route("/aging-buckets", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "reports")
def get_aging_buckets():
    """Get overdue accounts classified into aging buckets (owner-only)."""
    from flask import g
    buckets = billing_service.get_aging_buckets(g.current_academy_id)
    return jsonify(buckets), 200


@billing_bp.route("/check-overdue", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("billing", "manage")
def check_overdue():
    """Trigger overdue status checks. Called by cron job."""
    from flask import g
    count = billing_service.check_overdue_billings(g.current_academy_id)
    db.session.commit()
    return jsonify({"overdue_count": count}), 200


@billing_bp.route("/renew-cycles", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("billing", "manage")
def renew_cycles():
    """Trigger billing cycle renewals. Called by cron job."""
    from flask import g
    count = billing_service.renew_billing_cycles(g.current_academy_id)
    db.session.commit()
    return jsonify({"renewed_count": count}), 200


# ── Teacher Payroll ─────────────────────────────────────────────────

@billing_bp.route("/payroll", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "payouts")
def list_payroll():
    """
    List payroll records.
    Query params: teacher_id
    """
    from flask import g
    from app.services import payroll_service
    teacher_id = request.args.get("teacher_id")
    payrolls = payroll_service.list_teacher_payrolls(g.current_academy_id, teacher_id)
    return jsonify({"payrolls": payrolls}), 200


@billing_bp.route("/payroll/settle/<payroll_id>", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("billing", "payouts")
def settle_payroll(payroll_id):
    """Mark a payroll record as settled (paid)."""
    from flask import g
    from app.services import payroll_service
    success = payroll_service.settle_payroll(
        payroll_id, g.current_academy_id, g.current_user.id
    )
    if not success:
        return jsonify({"error": "Payroll record not found"}), 404

    db.session.commit()
    return jsonify({"message": "Payroll settled"}), 200


# ═══════════════════════════════════════════════════════════════════
# VINTA SCHOOL OS — Money Model Endpoints
# Subscriptions, multi-pay, payouts, revenue, session finalization
# ═══════════════════════════════════════════════════════════════════

from app.utils.decorators import verify_staff_pin


@billing_bp.route("/subscriptions", methods=["GET"])
@jwt_required()
@tenant_required
@require_any_permission(("billing", "view"), ("classes", "view"))
def list_subscriptions():
    """
    List student subscriptions.
    Query params: student_id, group_id, status
    """
    from flask import g
    student_id = request.args.get("student_id")
    group_id = request.args.get("group_id")
    status = request.args.get("status")

    subs = billing_service.list_subscriptions(
        g.current_academy_id, student_id, group_id, status
    )
    return jsonify({"subscriptions": subs}), 200


@billing_bp.route("/subscriptions/pay", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("billing", "payments")
@verify_staff_pin
def pay_subscription():
    """
    Multi-teacher subscription payment.
    Body: { student_id, items: [{group_id, amount}], payment_method, pin }
    PIN verified by @verify_staff_pin decorator.
    """
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    required = ("student_id", "items")
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    items = data.get("items", [])
    if not items:
        return jsonify({"error": "At least one payment item is required"}), 400

    total_received = sum(i.get("amount", 0) for i in items)
    method = data.get("payment_method", "CASH")

    try:
        receipt = billing_service.create_multi_payment(
            academy_id=g.current_academy_id,
            student_id=data["student_id"],
            items=items,
            total_received=total_received,
            method=method,
            staff_id=g.current_user.id,
        )
    except billing_service.MultiPaymentError as exc:
        # Nothing was charged: discard any partial flush (e.g. an Enrollment
        # created for an earlier line item) instead of committing it.
        db.session.rollback()
        return jsonify({"error": exc.message}), exc.status_code

    if not receipt:
        return jsonify({"error": "Payment failed"}), 400

    log_activity(
        academy_id=g.current_academy_id,
        user_id=g.current_user.id,
        entity_type="subscription",
        entity_id=data["student_id"],
        action="payment_received",
        description=f"Multi-payment of {total_received} Da received",
        metadata={"amount": total_received, "method": method, "groups": len(items)},
    )

    db.session.commit()
    return jsonify(receipt), 201


@billing_bp.route("/subscriptions/<subscription_id>/renew", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("billing", "manage")
def renew_subscription(subscription_id):
    """
    Renew an expired/depleted subscription.
    Body: { pin } (optional)
    """
    from flask import g
    result = billing_service.renew_subscription(subscription_id, g.current_academy_id)
    if not result:
        return jsonify({"error": "Subscription not found"}), 404
    db.session.commit()
    return jsonify(result), 200


# ── Payouts (Teacher Dashboard) ────────────────────────────────────

@billing_bp.route("/payouts", methods=["GET"])
@jwt_required()
@tenant_required
def list_payouts():
    """
    List teacher payout records.
    Query params: teacher_id, status
    """
    from flask import g
    teacher_id = request.args.get("teacher_id")
    status = request.args.get("status")
    payouts = billing_service.list_payouts(
        g.current_academy_id, teacher_id, status
    )
    return jsonify({"payouts": payouts}), 200


@billing_bp.route("/payouts", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("billing", "payouts")
def create_payout():
    """
    Record a teacher payout by hand (owner-only).

    Body: { teacher_id, basis, amount_da?, commission_value?, gross_revenue_da?,
            duration_hours?, payout_date?, notes?, status, pin }

    This covers what the session-finalisation flow cannot: a bonus, a
    correction, an advance, or pay for a lesson never marked conducted.
    `status` decides whether it is already settled (PAID) or still owed
    (PENDING, to be marked paid later).
    """
    from flask import g

    data = request.get_json() or {}
    if not data.get("teacher_id"):
        return jsonify({"error": "teacher_id is required"}), 400

    pin = data.get("pin")
    if not pin or not g.current_user.verify_pin(pin):
        # 403 for a wrong PIN — a 401 is read as "session expired" by the axios
        # interceptor (clears tokens + redirects mid-action). Same rule as
        # mark_payout_paid and @verify_staff_pin.
        return jsonify({"error": "Owner PIN is required"}), 403

    try:
        created = billing_service.create_manual_payout(
            g.current_academy_id, g.current_user.id, data
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    log_activity(
        academy_id=g.current_academy_id,
        user_id=g.current_user.id,
        entity_type="payout",
        entity_id=created["id"],
        action="created",
        description=(
            f"Payout recorded — {created['teacher_name']} "
            f"({created['teacher_cut_da']} Da, {created['source'].lower()})"
        ),
        metadata={
            "amount": created["teacher_cut_da"],
            "basis": created["commission_type"],
            "status": created["status"],
        },
    )

    db.session.commit()
    return jsonify(created), 201


@billing_bp.route("/payouts/<payout_id>/mark-paid", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("billing", "payouts")
def mark_payout_paid(payout_id):
    """
    Mark a payout as PAID (owner-only).
    Body: { pin } — owner PIN verified.
    """
    from flask import g
    data = request.get_json() or {}
    pin = data.get("pin")
    if not pin or not g.current_user.verify_pin(pin):
        # 403 for a wrong PIN — a 401 is treated as "session expired" by the
        # axios interceptor (clears tokens + redirects), same as @verify_staff_pin.
        return jsonify({"error": "Owner PIN is required"}), 403

    result = billing_service.mark_payout_paid(
        payout_id, g.current_academy_id, g.current_user.id
    )
    if not result:
        return jsonify({"error": "Payout record not found"}), 404

    db.session.commit()
    return jsonify(result), 200


# ── Payment records (archive + export) ─────────────────────────────

def _record_filters():
    """The shared filter set for the archive and the export.

    One reader for both, so a filter that works in the on-screen archive cannot
    silently mean something else in the downloaded file.
    """
    return {
        "date_from": request.args.get("from") or request.args.get("date_from"),
        "date_to": request.args.get("to") or request.args.get("date_to"),
        "profile": request.args.get("profile"),
        "type": request.args.get("type"),
        "min_amount": request.args.get("min_amount"),
        "max_amount": request.args.get("max_amount"),
    }


@billing_bp.route("/records", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "reports")
def list_records():
    """
    Every money record in the academy — the payment-records archive (owner-only).

    Merges student payments (money in), teacher payouts (money out) and school
    expenses (money out) into one date-sorted list, with totals.

    Query params: from, to (YYYY-MM-DD), profile (student/teacher id),
                  type (STUDENT_PAYMENT|TEACHER_PAYOUT|EXPENSE),
                  min_amount, max_amount.
    """
    from flask import g

    try:
        result = billing_service.list_billing_records(
            g.current_academy_id, _record_filters()
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result), 200


@billing_bp.route("/records/export", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "reports")
def export_records():
    """
    Export the payment records as CSV or PDF (owner-only).

    Takes the same filters as ``GET /records`` plus ``format=csv|pdf``.
    """
    from flask import g, Response
    from app.services import export_service

    fmt = (request.args.get("format") or "csv").strip().lower()
    if fmt not in ("csv", "pdf"):
        return jsonify({"error": "format must be csv or pdf"}), 400

    filters = _record_filters()

    # The file outlives the request that produced it: it cannot look a word up
    # later, so its language is settled here, from the one the browser states
    # on every call it makes. Everything else on the page is translated in the
    # browser and needs nothing from this route.
    language = request.headers.get("Accept-Language")

    try:
        payload, mimetype, filename = export_service.export_billing_records(
            g.current_academy_id, filters, fmt, language
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        # A PDF backend that will not build must not cost the owner their data:
        # say so plainly rather than returning a half-written file. The traceback
        # still goes to the log — this is the one failure a school cannot
        # describe over the phone, and a packaged build is exactly where a
        # lazily-imported module goes missing.
        current_app.logger.exception("Billing records export failed (format=%s)", fmt)
        return jsonify({"error": "Could not build the export"}), 500

    log_activity(
        academy_id=g.current_academy_id,
        user_id=g.current_user.id,
        entity_type="export",
        entity_id="billing-records",
        action="exported",
        description=f"Exported billing records as {fmt.upper()}",
        metadata={"format": fmt},
    )
    db.session.commit()

    return Response(
        payload,
        mimetype=mimetype,
        headers={
            "Content-Disposition": f"attachment;filename={filename}",
            # This body now depends on a request header, so anything caching it
            # has to key on that header too — otherwise the Arabic PDF gets
            # handed to the next person who asked in French.
            "Vary": "Accept-Language",
        },
    )


# ── Revenue ────────────────────────────────────────────────────────

@billing_bp.route("/revenue", methods=["GET"])
@jwt_required()
@tenant_required
def get_revenue():
    """
    Get revenue totals.
    Query params: group_id, session_id
    """
    from flask import g
    group_id = request.args.get("group_id")
    session_id = request.args.get("session_id")
    result = billing_service.get_revenue(
        g.current_academy_id, group_id, session_id
    )
    return jsonify(result), 200


# ── Session Finalization ───────────────────────────────────────────

@billing_bp.route("/income-chart", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "reports")
def income_chart():
    """
    Income over time, from real payment rows (owner-only).

    Query params:
      period  — "weekly" (default) or "monthly"
      buckets — how many buckets to return (default 12 for weeks, 6 for months)
    """
    from flask import g

    period = (request.args.get("period") or "weekly").lower()
    if period not in ("weekly", "monthly"):
        return jsonify({"error": "period must be 'weekly' or 'monthly'"}), 400

    if period == "weekly":
        try:
            buckets = int(request.args.get("buckets", 12))
        except (TypeError, ValueError):
            return jsonify({"error": "buckets must be a whole number"}), 400
        return jsonify({
            "period": "weekly",
            "points": billing_service.get_weekly_income(g.current_academy_id, buckets),
        }), 200

    try:
        buckets = int(request.args.get("buckets", 6))
    except (TypeError, ValueError):
        return jsonify({"error": "buckets must be a whole number"}), 400
    chart = billing_service.get_revenue_chart(g.current_academy_id, buckets)
    return jsonify({
        "period": "monthly",
        "points": [
            {"label": row["month"], "income": row["income"], "has_data": True}
            for row in chart
        ],
    }), 200


# ── Teacher Payments (owed / settled, per teacher and per group) ────

@billing_bp.route("/teacher-payments", methods=["GET"])
@jwt_required()
@tenant_required
@require_any_permission(("billing", "payouts"), ("billing", "reports"))
def teacher_payments():
    """
    What each teacher has earned, and its breakdown across all their groups.

    Query params: teacher_id — optional, narrows to one teacher.
    """
    from flask import g

    teacher_id = request.args.get("teacher_id")
    return jsonify({
        "teachers": billing_service.get_teacher_payments(
            g.current_academy_id, teacher_id
        )
    }), 200


# ── Payroll cadence: who has come due, and what a period is worth ───

@billing_bp.route("/payroll/due", methods=["GET"])
@jwt_required()
@tenant_required
@require_any_permission(("billing", "payouts"), ("billing", "reports"))
def payroll_due():
    """Teachers whose payday has passed with unsettled payouts.

    A teacher appears here when their cadence has fired at least once since the
    oldest unpaid payout — i.e. there is money from a closed period that has not
    been paid out. A teacher owed nothing never appears, however long ago their
    payday was: a "due" badge over a zero is a nag rather than a fact.

    Academies on the default cadence (NONE) get an empty list and therefore see
    no badges at all, which is exactly how this screen behaved before the
    feature existed.
    """
    from flask import g
    from app.services import payout_schedule_service

    return jsonify({
        "teachers": payout_schedule_service.list_due_teachers(g.current_academy_id),
    }), 200


@billing_bp.route("/teachers/<teacher_id>/payout-details", methods=["GET"])
@jwt_required()
@tenant_required
@require_any_permission(("billing", "payouts"), ("billing", "reports"))
def teacher_payout_details(teacher_id):
    """One teacher's finances for a period — the "Details" card behind a due badge.

    Query params: from, to (YYYY-MM-DD, both inclusive, both optional). With
    neither, the window is everything this teacher has ever earned, which is the
    question the card is opened to ask: "what do we owe them?"

    Reports `gross_revenue_da` (what the students with this teacher generated),
    `session_count`, `students_taught` / `students_enrolled`,
    `average_class_revenue_da`, the settled/owed split, and a per-group
    breakdown that adds up to the same totals.
    """
    from flask import g
    from app.services import payout_schedule_service

    try:
        details = payout_schedule_service.get_teacher_payout_details(
            g.current_academy_id, teacher_id,
            date_from=request.args.get("from") or request.args.get("date_from"),
            date_to=request.args.get("to") or request.args.get("date_to"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if details is None:
        return jsonify({"error": "Teacher not found"}), 404
    return jsonify(details), 200


@billing_bp.route("/teachers/<teacher_id>/payout-export", methods=["GET"])
@jwt_required()
@tenant_required
@require_any_permission(("billing", "payouts"), ("billing", "reports"))
def teacher_payout_export(teacher_id):
    """One teacher's finances as CSV or PDF, in the app's language.

    Query params: from, to (YYYY-MM-DD), format=csv|pdf.

    The language comes off the request header exactly as the billing-records
    export does, and the PDF is the format that follows it — the CSV stays
    English on purpose, because its column names are a contract with whatever
    spreadsheet was built against them (see ``billing_records_csv``).
    """
    from flask import g, Response
    from app.services import export_service, payout_schedule_service

    fmt = (request.args.get("format") or "csv").strip().lower()
    if fmt not in ("csv", "pdf"):
        return jsonify({"error": "format must be csv or pdf"}), 400

    try:
        details = payout_schedule_service.get_teacher_payout_details(
            g.current_academy_id, teacher_id,
            date_from=request.args.get("from") or request.args.get("date_from"),
            date_to=request.args.get("to") or request.args.get("date_to"),
            # The line items are the point of the file, unlike on the card.
            include_lines=True,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if details is None:
        return jsonify({"error": "Teacher not found"}), 404

    # The file outlives the request that produced it, so its language is settled
    # here, from the header the browser states on every call it makes.
    language = request.headers.get("Accept-Language")

    try:
        payload, mimetype, filename = export_service.export_teacher_payout(
            details, fmt, language, g.current_academy_id
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        # A PDF backend that will not build must not cost the owner their data.
        # See the billing-records export for why the traceback is logged.
        current_app.logger.exception("Teacher statement export failed (format=%s)", fmt)
        return jsonify({"error": "Could not build the export"}), 500

    log_activity(
        academy_id=g.current_academy_id,
        user_id=g.current_user.id,
        entity_type="export",
        entity_id=f"teacher-payout:{teacher_id}",
        action="exported",
        description=f"Exported a teacher's finances as {fmt.upper()}",
        metadata={"format": fmt, "teacher_id": teacher_id},
    )
    db.session.commit()

    return Response(
        payload,
        mimetype=mimetype,
        headers={
            "Content-Disposition": f"attachment;filename={filename}",
            # This body depends on a request header, so anything caching it has
            # to key on that header too — otherwise the Arabic PDF gets handed
            # to the next person who asked in French.
            "Vary": "Accept-Language",
        },
    )


# ── School Expenses ────────────────────────────────────────────────

@billing_bp.route("/expenses", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "expenses")
def list_expenses():
    """
    List school expenses (owner-only).

    Query params: from, to (YYYY-MM-DD), category.
    """
    from flask import g

    try:
        start = _query_date("from")
        end = _query_date("to")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    rows = billing_service.list_expenses(
        g.current_academy_id, start, end, request.args.get("category")
    )
    return jsonify({"expenses": rows}), 200


@billing_bp.route("/expenses", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("billing", "expenses")
def create_expense():
    """
    Record a school expense (owner-only).
    Body: { category, label, amount_da, expense_date,
            quantity?, vendor?, payment_method?, notes? }
    """
    from flask import g

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    try:
        created = billing_service.create_expense(
            g.current_academy_id, data, recorded_by=g.current_user.id
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    log_activity(
        academy_id=g.current_academy_id,
        user_id=g.current_user.id,
        entity_type="expense",
        entity_id=created["id"],
        action="created",
        description=f"Expense recorded — {created['label']} ({created['amount_da']} Da)",
        metadata={"amount": created["amount_da"], "category": created["category"]},
    )

    db.session.commit()
    return jsonify(created), 201


@billing_bp.route("/expenses/<expense_id>", methods=["PUT"])
@jwt_required()
@tenant_required
@require_permission("billing", "expenses")
def update_expense(expense_id):
    """Edit a school expense (owner-only)."""
    from flask import g

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    try:
        updated = billing_service.update_expense(
            expense_id, g.current_academy_id, data
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if updated is None:
        return jsonify({"error": "Expense not found"}), 404

    db.session.commit()
    return jsonify(updated), 200


@billing_bp.route("/expenses/<expense_id>", methods=["DELETE"])
@jwt_required()
@tenant_required
@require_permission("billing", "expenses")
def delete_expense(expense_id):
    """Remove a school expense (owner-only)."""
    from flask import g

    if not billing_service.delete_expense(expense_id, g.current_academy_id):
        return jsonify({"error": "Expense not found"}), 404

    db.session.commit()
    return jsonify({"message": "Expense deleted"}), 200


@billing_bp.route("/expense-summary", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "reports")
def expense_summary():
    """Expenses by category and by month (owner-only). Query: months."""
    from flask import g

    months = request.args.get("months", 6, type=int)
    return jsonify(
        billing_service.get_expense_summary(g.current_academy_id, months)
    ), 200


@billing_bp.route("/expense-categories", methods=["GET"])
@jwt_required()
@tenant_required
@require_any_permission(("billing", "expenses"), ("billing", "reports"))
def expense_categories():
    """The categories and payment methods the server will accept (owner-only)."""
    from app.models.billing import EXPENSE_CATEGORIES, EXPENSE_PAYMENT_METHODS

    return jsonify({
        "categories": list(EXPENSE_CATEGORIES),
        "payment_methods": list(EXPENSE_PAYMENT_METHODS),
    }), 200


# ── Financial summary (net profit) ─────────────────────────────────

@billing_bp.route("/financial-summary", methods=["GET"])
@jwt_required()
@tenant_required
@require_permission("billing", "reports")
def financial_summary():
    """
    Revenue, teacher cost, expenses and net profit (owner-only). Query: months.
    """
    from flask import g

    months = request.args.get("months", 6, type=int)
    return jsonify(
        billing_service.get_financial_summary(g.current_academy_id, months)
    ), 200


@billing_bp.route("/sessions/<session_id>/finalize", methods=["POST"])
@jwt_required()
@tenant_required
@require_permission("calendar", "manage")
@verify_staff_pin
def finalize_session(session_id):
    """
    "Is the class done?" flow.
    Body: { conducted: bool, pin }
    PIN verified by @verify_staff_pin.
    Yes → session becomes CONDUCTED, teacher payout computed.
    No → session becomes CANCELLED, no payout.
    """
    from flask import g
    data = request.get_json() or {}
    # `conducted` must be explicit: a missing field would otherwise fall
    # through to the cancel branch (status=cancelled + bulk-delete of the
    # session's RevenueEntry/PayoutRecord rows) and still report success.
    if "conducted" not in data:
        return jsonify({"error": "conducted is required"}), 400
    conducted = bool(data["conducted"])

    result = billing_service.finalize_session(
        session_id=session_id,
        conducted=conducted,
        academy_id=g.current_academy_id,
        staff_id=g.current_user.id,
    )

    if not result or "error" in result:
        return jsonify(result or {"error": "Session not found"}), 404

    log_activity(
        academy_id=g.current_academy_id,
        user_id=g.current_user.id,
        entity_type="session",
        entity_id=session_id,
        action="session_finalized",
        description=f"Session {'conducted' if conducted else 'cancelled'}",
        metadata={"conducted": conducted},
    )

    db.session.commit()
    return jsonify(result), 200
