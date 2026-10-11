# Vinta School OS — Billing Guide

> **Scope:** how money works in this application, end to end, with a spreadsheet or paper equivalent for every mechanism.
> **Audience:** the person who runs a small academy and thinks in spreadsheets.
> **Rule of this document:** every claim is checked against the source. Where the code does not make a behaviour clear, this document says so instead of guessing.
> **All money in this app is integer Algerian Dinars — `DA` or `DZD`.** There are no floats, no centimes, no decimals anywhere in the stored figures.

---

## The one-paragraph version

Vinta School OS holds **two billing systems that were built at different times and both still exist**. The older one — *plans* — sells a student a dated cycle ("Math, 30 days, 4 500 DA") and counts everything in **days**; it still answers an API, but no screen in this build uses it and nothing in the current money flow writes to it. The current one — the *money model* — sells a student access to a **course group**, counted in **weeks** and **credits**, and records money as three kinds of row in three tables: a student's purchase (money in), a teacher's payout (money out), and a school expense (money out). When a class is conducted, the app writes **one payout row per session** — not per month — starting as `PENDING`, and the owner later flips it to `PAID` with a PIN. A **payout schedule** (added later) says *when* paydays fall, so the app can tell you "this teacher's payday has passed and they are still owed X"; it never moves money by itself, and nothing in the app runs on a timer. Every number on every billing screen is a sum over those rows, and every one of them can be reproduced in a spreadsheet with a `SUMIF`.

---

## Table of contents

1. [Two generations of billing, and which one is real](#1-two-generations-of-billing-and-which-one-is-real)
2. [The money tables, field by field](#2-the-money-tables-field-by-field)
3. [The lifecycle, end to end](#3-the-lifecycle-end-to-end)
4. [The payout schedule](#4-the-payout-schedule)
5. [The export paths](#5-the-export-paths)
6. [The Excel / pen-and-paper counterpart](#6-the-excel--pen-and-paper-counterpart)
7. [Where the numbers can go wrong](#7-where-the-numbers-can-go-wrong)
8. [What this document could not verify](#8-what-this-document-could-not-verify)

---

## 1. Two generations of billing, and which one is real

Both live in the same file, `Backend/vinta-academy-backend/app/models/billing.py`, which opens by admitting it:

> `"""PaymentPlan, StudentBilling, PaymentLog (legacy, kept for backward compat). StudentSubscription, RevenueEntry, PayoutRecord (VINTA SCHOOL OS money model). All monetary columns are Integer (DZD)."""` — `app/models/billing.py:1-6`

### 1.1 The legacy plan model — counted in days

| Table | What it is | Key idea |
|---|---|---|
| `payment_plans` | A reusable price list: "Monthly — 30 days — 4 500 DA" | `duration_days` |
| `student_billings` | One row per student per cycle: amount due, `due_date`, `status` | `due_date`, `cycle_start`, `cycle_end` |
| `payment_logs` | A payment made against a billing cycle | `student_billing_id` |

`PaymentPlan.duration_days` is literally measured in days — `app/models/billing.py:30` comments it "30 for monthly, 90 for term". `StudentBilling` carries `cycle_start` / `cycle_end` / `due_date` as calendar dates.

**Is it dead?** No — the routes still exist and still work. But in this build **no screen calls them.** Verified by searching the whole frontend for the endpoint strings:

| Legacy endpoint | Frontend callers |
|---|---|
| `GET/POST /billing/plans` | 0 |
| `GET /billing/students` | 0 |
| `POST /billing/record-payment` | 0 (one code comment only, `features/students/StudentDrawer.tsx:17`, recording that it was rejected) |
| `GET /billing/payroll` (legacy list) | 0 |
| `POST /billing/payroll/settle/<id>` | 0 |
| `POST /billing/check-overdue` | 0 |
| `POST /billing/renew-cycles` | 0 |
| `GET /billing/aging-buckets` | 1 — `features/billing/FinanceBreakdown.tsx:74` |

So the **only** legacy surface with a live screen is the aging-bucket breakdown (the 1–7 / 8–30 / 30+ day overdue buckets), which reads `StudentBilling` rows with `status = "overdue"` (`app/services/billing_service.py:489-512`).

One more legacy trace survives on a current screen: `BillingConfig.tsx` still exposes **Plan Duration (days)** (`default_plan_duration`, default 30), which writes the legacy plan-duration default. It has no effect on the money model.

### 1.2 The money model — counted in weeks and credits

| Table | What it records | Unit |
|---|---|---|
| `student_subscriptions` | A student bought access to a course group | weeks and credits |
| `revenue_entries` | One student attended (or was charged for) one session | one seat price |
| `payout_records` | Money owed to a teacher | one row per session |
| `expenses` | Money the academy spent | one receipt |
| `payout_schedules` | When a teacher is paid | a cadence, no money |

Access is counted in **weeks**: a `TIME_BASED` subscription gets `access_end_date = today + access_duration_weeks` (`app/services/billing_service.py:763-765`). Credits: a `CREDIT_BASED` subscription gets `total_credits = remaining_credits = credits_per_cycle`, extended in `weeks` by `cycle_week_limit` (`app/services/billing_service.py:753-760`).

### 1.3 Which is authoritative

**The money model is authoritative for money.** Concretely:

- The revenue KPI, the monthly and weekly charts, and the net-profit figure all sum `StudentSubscription.amount_paid_da`, not the legacy tables (`_collected_between`, `app/services/billing_service.py:329-354`; `get_financial_summary`, `:2305-2392`).
- The teacher-payroll donut reads `PayoutRecord` (`get_billing_stats`, `:255-326`), and its docstring states why the legacy ring was removed: *"The legacy `TeacherPayroll` ring was dropped: no route generates payroll rows any more"* (`:266-267`).
- The money flow writes `RevenueEntry` and `PayoutRecord`; nothing in it writes `StudentBilling` or `PaymentLog`.

The legacy tables remain **readable** (aging buckets, the `/billing/payroll` list) but nothing in the current flow **writes** them, so on an academy that has only used the money model they are empty.

### 1.4 Code that is dead, and code that only looks dead

Verified with grep across the whole repository. This is the honest picture — the original brief guessed some of it, and the guesses were partly wrong.

**Fully dead (no call site anywhere):**

| Symbol | File:line | Finding |
|---|---|---|
| `generate_monthly_payroll` | `app/services/payroll_service.py:75` | Exactly one hit in the whole repository — its own definition. No caller, no import, no test. **It was the only writer of `TeacherPayroll`.** |
| `log_teacher_hours` | `app/services/payroll_service.py:151` | No callers. **It was the only writer of `TeacherHoursLog`.** |
| `calculate_payout_for_session` | `app/services/payroll_service.py:256` | No callers. |
| `list_payouts` / `mark_paid` / `get_teacher_payout_dashboard` | `payroll_service.py:277, 286, 297` | No callers. Note the inversion: the *newer* "money-model wrapper" block is the dead one — routes call `billing_service` directly. |
| `init_scheduler` / `shutdown_scheduler` / `CRON_JOBS` dispatch | `app/tasks/scheduler.py:14, 44`; `app/tasks/cron_jobs.py:195` | **No call site.** `init_scheduler` is referenced only in two comments and a packaging spec. The scheduler is never started. |

**Live but read-only — the model exists, its only writer is dead:**

| Symbol | Definition | Read by | Written by |
|---|---|---|---|
| `TeacherPayroll` | `app/models/teacher.py:131` | `GET /billing/payroll` (`routes/billing.py:229`), `POST /billing/payroll/settle/<id>` (`:241`), teacher drawer (`routes/teachers.py:365`) | nobody — `generate_monthly_payroll` is dead |
| `TeacherHoursLog` | `app/models/teacher.py:177` | `export_teacher_hours` (`services/export_service.py:978, 1025`), `get_teacher_summary` (`:211-214`), teacher delete (`routes/teachers.py:623-624`) | nobody — `log_teacher_hours` is dead |

In other words: `TeacherPayroll` always comes back empty on an academy that was not seeded, because nothing can create a row. That is not a bug in the reader; there is simply no producer. `TeacherHoursLog` has the same shape.

**`payroll_service.py` is not dead as a file.** Three functions are live: `list_teacher_payrolls` (`:168`), `settle_payroll` (`:122`), and `get_teacher_summary` (`:195`). Six are not.

---

## 2. The money tables, field by field

### 2.1 Money is integer DZD — no exceptions

Every monetary column is a SQLAlchemy `Integer`. There is no `Numeric`, no `Float`, no `Decimal` among them. The only float anywhere in the money pipeline is a session's **duration in hours**, which is used to multiply, and the product is cast back to `int`.

- `amount_da`, `paid_amount`, `gross_revenue_da`, `commission_value`, `teacher_cut_da`, `amount_paid_da`, `expense.amount_da` — all `Integer`.
- Formatting appends the code: `format_dzd` returns `f"{amount:,} DA"` (`app/utils/formatters.py:45-47`), so `15000` prints as `15,000 DA`. **`DA` is a currency code and is never translated** (`app/i18n/catalogue.py:16-19`).

The practical consequence: money can be *truncated*, never *rounded*. See §6.6 and §7.

### 2.2 The money-model tables

#### `student_subscriptions` — one purchase (`app/models/billing.py:132-200`)

Defined as `StudentSubscription`, with a backwards-compatible alias `Subscription = StudentSubscription` (`:204`). The table name is deliberately `student_subscriptions` to avoid colliding with the legacy SaaS `subscriptions` table.

| Column | Type | Meaning in money terms |
|---|---|---|
| `id` | string (UUID) | Row identity. |
| `academy_id` | FK `academies.id` | Tenant. Every query filters on it. |
| `enrollment_id` | FK `enrollments.id`, nullable | The enrolment this purchase attaches to, when there is one. |
| `student_id` | FK `students.id` | Who paid. |
| `group_id` | FK `classes.id` | Which course group the money bought. This is the price list — the group holds `price_da`. |
| `billing_model` | string(20) | `CREDIT_BASED` or `TIME_BASED`. Copies the group's model at purchase time. |
| `total_credits` | int, nullable | Credits bought. **Credits, not money** — but each credit is worth `group.price_da` when spent. Null on `TIME_BASED`. |
| `remaining_credits` | int, nullable | Credits not yet spent. Reaches 0 → status `DEPLETED`. |
| `cycle_start_date` | date | When the credit cycle began. |
| `cycle_deadline` | date | `cycle_start_date + cycle_week_limit` **weeks** (`billing_service.py:759-760`). |
| `access_start_date` | date | When time-based access began. |
| `access_end_date` | date | `access_start_date + access_duration_weeks` **weeks**, or null for open-ended (`:763-767`). |
| `max_groups_included` | int (default 1) | How many groups one time-based subscription may bundle. |
| `enrolled_group_ids` | JSON list | The group ids that bundle covers. |
| `amount_paid_da` | int (default 0) | **The money that actually changed hands.** Every revenue figure reads this column. |
| `payment_method` | enum `CASH` \| `CCP` \| `BARIDI_MOB` | How it was paid. |
| `recorded_by_staff_id` | FK `users.id` | Which staff member took it. |
| `makeup_credits` | int (default 0) | Credits granted back for an absence, when the group allows makeups. |
| `status` | string(20) | `ACTIVE` \| `EXPIRED` \| `OVERDUE` \| `DEPLETED` \| `CANCELLED` \| `SUSPENDED`. |
| `created_at` | datetime | **The date every revenue bucket uses** (`_collected_between` filters on it). |

#### `revenue_entries` — one seat, one session (`app/models/billing.py:207-241`)

The docstring calls it *"immutable revenue fact per conducted session allocation"*.

| Column | Meaning |
|---|---|
| `academy_id` | Tenant. |
| `group_id`, `student_id`, `session_id` | What was sold: this student, in this group, in this session. All nullable in the schema but always set by the writer. |
| `amount_da` | The seat price charged — written as `int(group.price_da)` (`billing_service.py:1046`). |
| `recorded_at` | When the row was written (at check-in, not at close). |

**Written when the student is checked in**, not when the class is finalised. `record_checkin_billing_side_effects` (`billing_service.py:947-1099`) creates one row per student per session at `group.price_da` — and only when that price is above zero (`:1039`).

#### `payout_records` — money owed to a teacher (`app/models/billing.py:244-335`)

| Column | Meaning in money terms |
|---|---|
| `teacher_id` | Who is owed. |
| `session_id` | **Unique**, nullable. The session that generated this payout. Null for a hand-recorded payout — which is why the column is nullable. |
| `gross_revenue_da` | The session's total take, before the split. |
| `commission_type` | `PERCENTAGE` \| `FLAT_HOURLY` \| `FIXED_SESSION` — snapshotted from the teacher at finalise time so a later rate change does not rewrite history. |
| `commission_value` | The rate that was applied: a percent, a DA/hour, or a DA/session. |
| `teacher_cut_da` | **What the teacher is owed for this session.** |
| `status` | `PENDING` \| `PAID`. |
| `source` | `SESSION` (derived from a conducted session) or `MANUAL` (owner-entered). |
| `payout_date` | The day a manual payout is *for*, chosen by the owner. |
| `notes` | Free note, shown in the archive. |
| `recorded_at` | When the row was written. |
| `recorded_by_staff_id` | Who typed a manual payout. |
| `paid_at`, `paid_by_staff_id` | Stamped by `mark_payout_paid`. |

There is **no academy-share column.** The academy's share is `gross_revenue_da − teacher_cut_da`, computed on read, never stored — so the two can never disagree.

#### `expenses` — money out, no student (`app/models/billing.py:450-523`)

| Column | Meaning |
|---|---|
| `category` | One of `EXPENSE_CATEGORIES` (`:434-445`): `SUPPLIES`, `RENT`, `UTILITIES`, `SALARIES`, `MAINTENANCE`, `EQUIPMENT`, `MARKETING`, `TRANSPORT`, `TAXES`, `OTHER`. A plain string, not a DB enum, so a new category is a code change and not a table rebuild. |
| `label` | What was bought, e.g. "Whiteboard markers". |
| `amount_da` | **The total paid, always positive.** Never a unit price. |
| `quantity` | How many units, when it comes in units — informational only; `amount_da` is already the total, so a total never has to be multiplied out. |
| `expense_date` | The day the money left. |
| `vendor` | Who was paid. Optional. |
| `payment_method` | One of `CASH`, `CCP`, `BARIDI_MOB`, `BANK`, `OTHER` (`:447`). |
| `recorded_by` | Which staff member logged it. |

#### `payout_schedules` — when, not how much (`app/models/billing.py:338-428`)

| Column | Meaning |
|---|---|
| `academy_id` | Tenant. |
| `teacher_id` | **`NULL` = the academy-wide default row (one per academy). Set = that teacher's override.** |
| `cadence` | `NONE` \| `WEEKLY` \| `MONTHLY`. Plain string, deliberately not a DB enum. |
| `day_of_week` | `WEEKLY` only: **0 = Monday … 6 = Sunday**, matching Python's `date.weekday()` (`:397-400`). |
| `day_of_month` | `MONTHLY` only: 1–31. **A 31 in a 30-day month means that month's last day** (`:401-404`). |

### 2.3 The supporting tables that define the prices

| Table | Column | Meaning |
|---|---|---|
| `classes` (course group) | `price_da` | **The seat price.** This is what one attendance charges. |
| | `billing_model` | `CREDIT_BASED` (default) or `TIME_BASED`. |
| | `credits_per_cycle` | Credits granted per purchase (default 4). |
| | `cycle_week_limit` | How many **weeks** a credit cycle lasts. |
| | `allow_rollover` | Unused credits carry into the next purchase. |
| | `allow_makeups` | An absence can be made up. |
| | `access_duration_weeks` | How many **weeks** a time-based purchase lasts. |
| | `max_groups_included` | Bundling limit (default 1). |
| | `enforce_attendance`, `attendance_threshold` | Below the ratio, the subscription goes `SUSPENDED`. |
| `teachers` | `commission_type` | `PERCENTAGE` \| `FLAT_HOURLY` \| `FIXED_SESSION`. Authoritative. |
| | `commission_value` | Integer DZD: percent, DA/hour, or DA/session (default 30). |
| | `contract_type`, `hourly_rate`, `per_student_rate` | **Legacy** — kept for compatibility; `commission_type` is authoritative. |
| `academy_settings` | `default_teacher_share_percentage` | The academy-wide fallback teacher share, integer 0–100, **default 30** (`app/models/academy.py:149-151`). The school's share is `100 − this` and is never stored. |
| | `absence_consumes_credit` | Whether a no-show spends a credit (and therefore earns the academy a `RevenueEntry`). |
| | `free_session_auto_present` | Whether a free session's register fills itself. |

---

## 3. The lifecycle, end to end

This is where a row is born and where it dies.

### Step 1 — a student is enrolled in a course group

`Enrollment` (`app/models/student.py:101-137`) links a student to a `Class`. Status is lowercase `active` here — note that `StudentSubscription.status` is **uppercase**, and mixing them silently returns nothing (`materialize_roster` warns about exactly this at `session_lifecycle_service.py:93-95`).

### Step 2 — a payment creates a subscription

The desk records a payment through `POST /api/billing/subscriptions/pay` (`routes/billing.py:279-336`, permission `billing.payments`, PIN-gated). It calls `create_multi_payment` → `record_multi_payment` (`billing_service.py:931-944`, `:830-928`), which for each line item:

1. finds or creates the `Enrollment` (`:882-893`);
2. calls `create_subscription_for_payment` (`:617-773`), which writes the `StudentSubscription` with `amount_paid_da = amount`, status `ACTIVE`, and either credits (`:753-760`) or a week-based access window (`:761-769`).

If any line fails, `MultiPaymentError` is raised and the route rolls the whole thing back — *"Nothing was charged"* (`routes/billing.py:316-320`).

**Money in is now recorded**, as `student_subscriptions.amount_paid_da`. This is the only thing the revenue figures read.

### Step 3 — the class is started, and the register is created

`start_session` (`session_lifecycle_service.py:148-234`) moves `scheduled → in_progress`, stamps `actual_start_time`, and calls `materialize_roster` (`:70-125`). It **refuses to start a class on any day but its own** (`:210-215`) — a deliberate guard so a future class cannot sit live.

`materialize_roster` creates one `SessionStudent` per active enrolment, each starting **`ABSENT`** — "false until true" (`:76-78`). The register is the attendance record, not the money record.

### Step 4 — the money is written at check-in

Each student who arrives is checked in through `attendance_service.check_in_student`, which calls `record_checkin_billing_side_effects` (`billing_service.py:947`). That function:

- returns early for a free session — *"no credit consumed, no revenue"* (`:989-991`);
- returns early for an absence when `absence_consumes_credit` is off (`:998-1002`);
- for `CREDIT_BASED`: decrements `remaining_credits` by 1 (`:1021`), grants a makeup credit for an absence when allowed (`:1025-1029`), sets `DEPLETED` at zero (`:1031-1034`), and **writes one `RevenueEntry` of `group.price_da`** (`:1039-1049`);
- for `TIME_BASED`: decrements nothing (`:1051-1056`), and recomputes the attended/conducted ratio, setting `SUSPENDED` below the threshold (`:1058-1096`).

**So a session's gross revenue is the sum of its `RevenueEntry` rows.** Since each row is one charged seat, gross is effectively `charged attendees × group.price_da`.

### Step 5 — the class is closed

There are **two different endpoints**, and they do different things. This matters.

| Action | Endpoint | Handler | Writes a payout? |
|---|---|---|---|
| "End Class" (Classes tab) | `POST /api/sessions/{id}/end` | `session_lifecycle_service.end_session` (`:280-339`) | **No** |
| "Class Done" (Dashboard finalize modal) | `POST /api/billing/sessions/{id}/finalize` | `billing_service.finalize_session` (`:1135-1232`) | **Yes** |

`end_session` (`:280`) settles absences via `settle_absences` (`:237-277`) — which charges the students who did **not** turn up, and only them, because the attendees were already charged at check-in (`:244-246`) — then sets `status = CONDUCTED` and stamps `actual_end_time`. It creates no `PayoutRecord`.

`finalize_session` (`:1135`) is the one that writes the payout, and it is the path the Dashboard's PIN modal uses (`features/calendar/FinalizeSessionModal.tsx:61`). It requires an explicit `conducted` boolean (`routes/billing.py:946-951`) and then, for `conducted=True`:

```python
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
```
— `app/services/billing_service.py:1166-1178`

The teacher's cut is then computed by `_compute_teacher_cut` (`:1114-1132`):

```python
    if commission_type == "PERCENTAGE":
        return int(gross_da * commission_value / 100)
    if commission_type == "FLAT_HOURLY":
        return int(float(duration_hours or 0) * commission_value)
    if commission_type == "FIXED_SESSION":
        return commission_value
    return int(gross_da * commission_value / 100)
```

The commission comes from the teacher, falling back to the academy default: `teacher.commission_value` if set, else `academy_rules.default_teacher_share_percentage(academy_id)` (`:1186-1190`).

### Step 6 — the payout row is born: one per session, not per month

This is the load-bearing claim, so here is the code that proves it, quoted verbatim (`app/services/billing_service.py:1196-1210`):

```python
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
```

`status="PENDING"` — the string is exactly that, on line **1208**. The `session_id` column carries a `UNIQUE` constraint (`app/models/billing.py:278-280`), so the database itself guarantees "one payout per session", and re-finalising returns the existing row instead of duplicating it (the idempotency branch at `:1155-1164`). For `conducted=False` the session is set `cancelled` and **any pending revenue and payout rows for that session are deleted** (`:1221-1227`).

### Step 7 — the owner settles it

`mark_payout_paid` (`billing_service.py:1393-1404`) sets `status = "PAID"`, stamps `paid_at` and `paid_by_staff_id`. It is reached through `POST /api/billing/payouts/{id}/mark-paid` with the owner's PIN (`routes/billing.py:432-456`, permission `billing.payouts`). A wrong PIN returns **403, never 401** — a deliberate choice, because the frontend's axios interceptor reads 401 as "session expired" and would log the user out mid-action (`:444-447`).

### Step 8 — a payout can also be born by hand

`create_manual_payout` (`billing_service.py:1414-1502`) covers a bonus, a correction, an advance, or pay for a lesson never marked conducted. It writes `source="MANUAL"` and `session_id=None`. Its amount goes through the **same** `_compute_teacher_cut` for the three commission bases, so a hand-entered payout and a session-derived one from the same gross cannot disagree — except for `basis="CUSTOM"`, where the stated amount is the amount (`:1430-1435`).

---

## 4. The payout schedule

Added after the ledger existed. The reason is stated plainly in the model docstring (`app/models/billing.py:344-348`):

> *"Every payout in this app is written **per session**. `finalize_session` stamps one `PayoutRecord` with `status="PENDING"` each time a class is conducted, and it stays pending until somebody settles it. There is no month and no week anywhere in that flow — so 'when is this teacher paid?' had no answer the database could give."*

### 4.1 The three states of a teacher's schedule

`resolve_schedule` (`payout_schedule_service.py:299-333`) is the one function the rest of the app is meant to call. It folds three distinct situations into one answer:

| Stored row | Meaning | Result |
|---|---|---|
| **no row** | "whatever the academy does" | inherit the academy default |
| **a row with `cadence="NONE"`** | "pay this one by hand, whatever the academy does" | explicitly no cadence |
| **a row with `WEEKLY` / `MONTHLY`** | this teacher's own cadence | that cadence wins over the default |

The distinction between "no row" and "a stored NONE" is the whole point, and it is spelled out in `delete_schedule`'s docstring (`:247-265`): a stored `NONE` is *not* the same as absence, because a contractor who invoices ad hoc should not acquire a payday just because somebody set one for everyone else.

The API spells the absent state as a fourth dropdown value, `INHERIT`, which is **not a stored cadence** — it deletes the row (`set_teacher_schedule`, `:274-296`).

The table is unique on `(academy_id, teacher_id)` (`app/models/billing.py:415-419`), so the academy row and a teacher's row cannot collide, and no teacher can end up with two paydays.

**Why a new table and not a new column.** `packaging/launcher.py:207` runs only `db.create_all()`, which creates missing **tables** but never adds a missing **column** to a table that already exists. The backend root does hold ALTER scripts — `add_payout_manual_fields.py`, `add_teacher_share_percentage.py`, `add_lifecycle_columns.py`, `add_expense_quantity.py`, `add_user_permissions.py`, `nullable_activity_log_actor.py` — but they are not shipped: the packaging spec's `datas` list has exactly one entry, the built frontend (`packaging/vinta_review.spec:103-106`). A new column would therefore leave every existing install without it, while a new table is created automatically on the next start.

**The feature is opt-in.** With no row anywhere, the resolved cadence is `NONE`, so an academy that upgrades and never opens Settings behaves exactly as it did before: no paydays, no due flags, nothing to dismiss.

### 4.2 The date arithmetic, exactly

Four small pure functions, no cleverness (`payout_schedule_service.py:51-146`).

**`_clamp_day(year, month, day)`** (`:61-68`): `min(day, calendar.monthrange(year, month)[1])`. A teacher paid on the 31st is paid on the 30th in April. The alternative — skipping or rolling into May — surprises the person being paid.

**`next_payout_date(cadence, day_of_week, day_of_month, from_date)`** (`:77-98`) — the first payday **on or after** `from_date`:

- `WEEKLY`: `from_date + ((day_of_week − from_date.weekday()) mod 7)` days.
- `MONTHLY`: this month's clamped day if it is ≥ `from_date`, else next month's.
- `NONE`: `None`.

"On or after" is deliberate: *"on the 5th itself the desk wants to see that today is payday, not that the next one is a month away"* (`:83-84`).

**`previous_payout_date(...)`** (`:101-122`) — the last payday **on or before** `from_date`. This is the date the currently-owed period closes on.

**`is_period_due(cadence, day_of_week, day_of_month, pending_dates, today=None)`** (`:125-146`) — whether an unpaid period has closed:

```python
    if cadence == "NONE" or not pending_dates:
        return False
    today = today or date.today()
    oldest = min(d for d in pending_dates if d is not None)
    due_on = previous_payout_date(cadence, day_of_week, day_of_month, today)
    return due_on is not None and oldest <= due_on
```

Two properties fall out of this, both worth remembering:

1. **A teacher owed nothing is never due**, however long ago payday was — *"a due badge over a zero is a nag, not a fact"* (`:133-134`).
2. **Due-ness is measured from the oldest unsettled payout**, not from today alone. If money was earned before the last payday, the period has closed on it.

`validate_cadence` (`:154-191`) rejects a weekly cadence with no weekday, a monthly with no day, a weekday outside 0–6, and a day outside 1–31. It also **clears** the day the chosen cadence does not use — *"a weekly cadence that kept a stale day-of-month would be a trap"* (`:159-162`).

### 4.3 The endpoints

| Endpoint | Permission | What it does |
|---|---|---|
| `GET /api/settings/billing-config` | `settings.manage` (owner) | Returns every billing setting **plus** `payout_schedule` — the resolved academy default (`routes/settings.py:188-233`). |
| `PUT /api/settings/billing-config` | `settings.manage` (owner) | Writes `payout_schedule` into `payout_schedules` with `teacher_id=None`, and range-checks `default_teacher_share_percentage` to 0–100 (`routes/settings.py:236-334`). An invalid cadence is a **400, not a silent no-op** (`:327-328`). |
| `PUT /api/settings/teachers/{id}` | `teachers.manage` + `teachers.commission` for the pay fields | Accepts `payout_schedule` as a per-teacher override; `INHERIT` deletes it, `NONE` stores it (`routes/teachers.py:496-601`, `_resolve_payout_schedule` at `:149-192`). A refusal is **403, never 401** (`:160-162`). |
| `GET /api/billing/payroll/due` | `billing.payouts` or `billing.reports` | Every teacher whose payday has passed with unsettled payouts, largest debt first (`routes/billing.py:651-672` → `list_due_teachers`, `payout_schedule_service.py:630-695`). |
| `GET /api/billing/teachers/{id}/payout-details` | same | Everything behind the "due" card: totals, per-group breakdown, students taught vs enrolled, the due flag (`routes/billing.py:675-705` → `get_teacher_payout_details`, `:396-616`). |
| `GET /api/billing/teachers/{id}/payout-export` | same | The same numbers as CSV or PDF, with the line items included (`routes/billing.py:708-778`). |

Permission names come from the catalogue in `app/permissions.py:72-88`: the `billing` area carries actions `payments`, `payouts`, `expenses`, `reports`; the `settings` area carries `staff`, `danger`; `teachers` carries `commission`.

### 4.4 Nothing runs on a timer — and what that means for you

**Verified by grep across the whole repository:** `init_scheduler` (`app/tasks/scheduler.py:14`) has **no call site**. It appears only in its own definition, in a packaging spec comment, and in a docstring. `CRON_JOBS` (`app/tasks/cron_jobs.py:195`) is referenced only by that unreachable function. There is no Celery, no `@scheduler` decorator, no APScheduler use outside that file. The only timer anywhere is a one-second `threading.Timer` that opens the browser in the packaged launcher (`packaging/launcher.py:285`).

So every cron job in `app/tasks/cron_jobs.py` — auto-checkout, closing past one-off classes, overdue checks, cycle renewals, renewal reminders — is never invoked in a running deployment. The functions themselves are exercised by unit tests only.

What this means for the payout schedule, and it is stated in the module's own header (`payout_schedule_service.py:16-22`):

> *"**Nothing here writes money.** A cadence decides whether something is *marked* due; settling is still `billing_service.mark_payout_paid` behind the owner's PIN. A scheduled week does not move money on its own, and it cannot, because nothing in this app runs on a timer … Every date below is computed on read, from `date.today()`, so the answer is correct the moment somebody looks and needs no job to have fired."*

**In plain terms: the app tells you a payday has arrived; it never pays anything by itself.** And because the dates are computed on read, the answer is never stale — you do not have to have left the app open, and there is no nightly job that might have failed.

All four parts of the schedule reach a screen:

- **The academy-wide cadence** — `features/settings/BillingConfig.tsx` renders a "Payout Schedule" card (cadence buttons at `:984`, plus the weekday picker, the day-of-month field and the next/previous payday display) and saves through `saveAcademyPayoutSchedule` (`:417`), then re-reads with `fetchAcademyPayoutSchedule` (`:418`) so the card shows what the server actually stored.
- **The per-teacher override** — `features/teachers/TeacherDrawer.tsx` offers four choices, `INHERIT`, `NONE`, `WEEKLY`, `MONTHLY` (`PAYOUT_CHOICES`, `:132`), and sends them as `payload.payout_schedule` (`:416`). `INHERIT` is the UI's spelling of "delete the row", exactly as §4.1 describes; on load, a teacher whose cadence came from the academy is shown as `INHERIT` rather than as the academy's cadence copied in (`:357-359`).
- **The due list** — `fetchDueTeachers` (`lib/payoutSchedule.ts:361`) is called from `features/billing/TeacherPayments.tsx:101`. That is the consumer for `GET /billing/payroll/due`.
- **The statement** — `features/billing/PayoutDetailsCard.tsx` calls `/billing/teachers/{id}/payout-details` and `/payout-export`, and is rendered from `TeacherPayments.tsx:360`.

No line numbers are given for `PayoutDetailsCard.tsx` on purpose: that file was still being written while this section was written (see §8.9), and it changed between two readings minutes apart. The endpoint names are the stable part; the offsets are not. The same caution applies to the whole list — these four bullets describe the working tree as it stood, and a checkout that predates the change will have the API and not the buttons.

---

## 5. The export paths

### 5.1 Billing records — CSV and PDF

`GET /api/billing/records/export` (`routes/billing.py:504-565`), permission `billing.reports`, `format=csv|pdf`. It calls `export_billing_records` (`export_service.py:385-417`), which builds its rows from **`list_billing_records`** — *"the same function behind the on-screen archive — so the file and the screen can never disagree about what the filters selected"* (`:395-397`).

The record set is the three-way archive: `STUDENT_PAYMENT` (in), `TEACHER_PAYOUT` (out), `EXPENSE` (out) merged, date-sorted, with totals (`billing_service.py:1527-1707`). Columns (`export_service.py:28-31`): `Date, Type, Direction, Profile, Label, Amount (DA), Status, Method, Notes`.

**What it deliberately omits:** nothing is omitted from the columns, but note the filters. A `profile` filter that names a **teacher** excludes student payments entirely — *"a teacher is not the profile on a student's payment"* (`:1596-1598`) — and excludes expenses too, because an expense belongs to no profile (`:1668-1669`). So filtering by a teacher gives you that teacher's payouts and nothing else.

### 5.2 The single-teacher statement

`GET /api/billing/teachers/{id}/payout-export` → `export_teacher_payout` (`export_service.py:850-891`). Same numbers as the on-screen card, because it calls `get_teacher_payout_details` with `include_lines=True` — *"the card shows totals and a table of a few thousand rows would be a heavy way to say four numbers; the export turns it on because there the line items are the point of the file"* (`payout_schedule_service.py:411-414`).

Contents, in order (`teacher_payout_csv`, `export_service.py:581-625`):

1. header block — Teacher, Academy, Generated, Period, Payroll cadence;
2. totals — gross, cut, pending, paid, average class revenue, sessions, manual payouts, hours, students taught, groups;
3. line items — `Date, Group, Source, Gross (DA), Teacher cut (DA), Status, Hours, Notes`;
4. per-group summary — `Group, Sessions, Gross (DA), Teacher cut (DA), Still owed (DA)`.

The per-group rows are built to **add up to the teacher's own figures**, *"which is what makes the breakdown checkable by hand rather than something the desk has to take on trust"* (`payout_schedule_service.py:498-500`).

The filename is transliterated to ASCII (`_ascii_slug`, `:444-456`) because the `Content-Disposition` header is bytes; the teacher's real name, in whatever script, is inside the file.

### 5.3 The full-school archive

`GET /api/settings/export/school` → `build_school_archive` (`school_export_service.py:195-274`). A ZIP containing, per table, a CSV and a JSON, plus a database snapshot, a `README.txt`, and a `manifest.json`.

Two deliberate omissions:

- `EXCLUDED_TABLES = {"activity_logs"}` — kept out of the portable CSV/JSON half, but **still present in the database copy**, and the README says so (`:56-58`).
- `SECRET_COLUMNS = {"pin_hash", "password_hash"}` — redacted from the portable half and named in the manifest (`:54`, `:253`).

The date format is ISO and booleans become `1`/`0` — *"so the file reads the same in any locale"* and so the import that reads it back agrees (`:66-72`).

### 5.4 The import

`POST /api/settings/import` → `import_upload` / `import_zip` (`import_service.py:715, 759`). One importer matters for money: `_import_billing_records` (`:605-646`).

**It imports only the expense rows.** A `STUDENT_PAYMENT` row is skipped, and the report notes `payments_not_importable`:

> *"A `STUDENT_PAYMENT` row is not a payment on its own — it is a line that was *derived* from a subscription and a cycle, and writing it back without those would create money the ledger cannot account for. Those rows are reported, not guessed at."* — `import_service.py:606-611`

So the billing-records CSV is a **one-way** document: you can round-trip expenses through it, but student payments must be re-entered through the payments screen where the subscription exists. The import also runs a dry run first (`dry_run`), and the expense categories on import default to `OTHER` (`:630`).

### 5.5 The two translation rules, and why CSV and PDF differ

Both rules come from `app/i18n/catalogue.py:14-23`:

> *"`DA` is a currency code and is never translated. The amounts beside it are formatted by `app/utils/formatters.py`, which appends `DA` and is not language-aware, so translating the code in the header alone would put two different currency names in one column. Values that came out of the database — a status, a payment method, a person's name — are not translated. `PAID` and `CASH` are enum values the rest of the system matches on, and a PDF is not the place to start rewriting them."*

Concretely: a French billing PDF has the header **"Montant (DA)"** — the word translated, the code not (`catalogue.py:148`). A status cell still reads `PAID`; a method cell still reads `CASH`. The row builder enforces this by never passing `status` or `method` through the translator at all (`export_service.py:143-154`).

**Why the CSV stays English while the PDF follows the interface language** — `billing_records_csv`'s docstring (`export_service.py:177-186`):

> *"Written in English whatever the interface language is, and not by accident: a CSV is read by formulas and scripts far more often than by a person, and its column names are the contract those were written against. Renaming a column because the desk switched to French would break the spreadsheet somebody built last month. The PDF is the format that follows the interface language; this one stays still."*

The CSV therefore calls `translator("en")` explicitly (`:187`), while the PDF takes the request's `Accept-Language` and, for Arabic, **reverses the column order and mirrors the text** — *"a table that reads right to left while its columns still run left to right is not an Arabic document, it is an English one with Arabic words in it"* (`:227-231`, `:264-266`). The route sets `Vary: Accept-Language` on the response so a cache cannot hand the Arabic PDF to the next person who asked in French (`routes/billing.py:774-776`).

---

## 6. The Excel / pen-and-paper counterpart

This section gives every mechanism in the app a row in a spreadsheet and a line in a cash book. Two sheets and a config block are enough to reproduce the whole system.

### 6.1 The sheet you would build

**Sheet `Config`** — three cells.

| Cell | Label | Example value |
|---|---|---|
| `A1` / `B1` | Default teacher share % | `40` |
| `A2` / `B2` | Next payday | `2026-10-11` |
| `A3` / `B3` | Currency | `DZD` |

**Sheet `Ledger`** — one row per money record, exactly the columns the app's export uses.

| Col | Header | Matches in the app |
|---|---|---|
| A | Date | `date` |
| B | Type | `kind` — `STUDENT_PAYMENT` / `TEACHER_PAYOUT` / `EXPENSE` |
| C | Direction | `direction` — `IN` / `OUT` |
| D | Profile | `profile_name` |
| E | Label | `label` |
| F | Amount (DA) | `amount_da` |
| G | Status | `status` |
| H | Method | `method` |
| I | Notes | `notes` |

**Sheet `Sessions`** — one row per conducted session: the `payout_records` table.

| Col | Header |
|---|---|
| A | Date |
| B | Group |
| C | Teacher |
| D | Gross (DA) |
| E | Commission Type |
| F | Commission Value |
| G | Teacher Cut (DA) |
| H | Academy Share (DA) |
| I | Status (`PENDING` / `PAID`) |
| J | Session ID |

### 6.2 The mapping table

| In the app | In Excel | On paper |
|---|---|---|
| A `RevenueEntry` / `PayoutRecord` / `Expense` row | A row in `Ledger` or `Sessions` | A line in the cash book |
| A session's split into academy share and teacher cut | Two columns, `G` and `H`, with `H` a formula | Two ink colours — black for gross, red for the teacher's share |
| `finalize_session` (`billing_service.py:1135`) | The moment you type the row | The moment you write it down |
| Settling a payout — `mark_payout_paid` (`:1393`) | Flipping `Sessions!I` from `PENDING` to `PAID`, or a conditional format on it | The settlement receipt: every slip in the pile crossed off, totalled, and both parties signed on the one line that says `PAID` |
| The cadence (`payout_schedules`) | A recurring reminder in the calendar app | A wall calendar with the payday ringed in marker — one colour for the academy's default, another for the teachers who differ |
| The per-teacher override | A second reminder rule, or a note on the person's own calendar row | That teacher's name written under a different ringed day |
| "Inherit the academy default" | Deleting the override rule | Rubbing the name off the teacher's own day, so only the academy ring is left |
| The "due" flag (`is_period_due`) | `=IF(AND(TODAY()>=Config!$B$2,SUMIF(Sessions!$I:$I,"PENDING",Sessions!$G:$G)>0),"DUE","")` | The pile of unsettled session slips the payday was meant to clear, held up against the ringed date: slips still there and the date gone by means the teacher is owed |
| A KPI card | A `SUM` / `SUMIF` / `COUNTIF` / `AVERAGEIF` formula | A hand-ruled total at the foot of a page |
| The per-teacher statement | A filtered sheet, or a pivot table on `Teacher` | A page ruled by hand and totalled |
| The per-group breakdown | A pivot table grouped by `Group` | One page per group |
| The export (`export_billing_records`) | File → Save As / Print | Photocopying the page |
| The import (`_import_billing_records`) | Pasting a column in | Retyping a page |

### 6.3 A worked example, checked

Take one session and confirm every figure.

- Course group **"Math — CM2"**, seat price `price_da = 5 000 DA`.
- Three students are present and checked in. At each check-in the app writes one `RevenueEntry` of 5 000 DA.
- Teacher commission: `PERCENTAGE`, `commission_value = 40`.

**Gross** = 3 × 5 000 = **15 000 DA** (the sum of the three `RevenueEntry` rows).

**Teacher cut** = `int(15 000 × 40 / 100)` = `int(6 000.0)` = **6 000 DA** — `_compute_teacher_cut`, `billing_service.py:1126-1127`.

**Academy share** = 15 000 − 6 000 = **9 000 DA** (never stored; computed as the remainder).

| Ledger row | Date | Type | Dir | Profile | Amount |
|---|---|---|---|---|---|
| 1 | 2026-10-08 | STUDENT_PAYMENT | IN | Amina B. | 15 000 |
| 2 | 2026-10-08 | TEACHER_PAYOUT | OUT | M. Haddad | 6 000 |

`Sessions` row: `A=2026-10-08, B=Math — CM2, C=M. Haddad, D=15000, E=PERCENTAGE, F=40, G=6000, H=9000, I=PENDING`.

In Excel, `H2 = D2-G2` gives 9 000, and `G2 = TRUNC(D2*F2/100)` gives 6 000. Summing the `Ledger` gives money in 15 000, money out 6 000, net 9 000.

Now scale it: four such sessions in a week, all still `PENDING`:

| Session | Gross | Cut (40 %) | Academy |
|---|---|---|---|
| 1 | 15 000 | 6 000 | 9 000 |
| 2 | 10 000 | 4 000 | 6 000 |
| 3 | 15 000 | 6 000 | 9 000 |
| 4 | 5 000 | 2 000 | 3 000 |
| **Total** | **45 000** | **18 000** | **27 000** |

With a weekly cadence falling on Saturday and today past that Saturday, the due flag reads `DUE` because `SUMIF(Sessions!I:I,"PENDING",Sessions!G:G)` = 18 000 > 0. Settling the four rows flips each `I` to `PAID`; the same `SUMIF` on `"PAID"` then returns 18 000 and the pending sum returns 0, so the flag clears itself. That is exactly what `is_period_due` does: a teacher owed nothing is never due.

### 6.4 The other two commission bases

| Basis | App formula (`billing_service.py:1126-1131`) | Excel | Worked example |
|---|---|---|---|
| `PERCENTAGE` | `int(gross × value / 100)` | `=TRUNC(D2*F2/100)` | gross 15 000, 40 % → 6 000 |
| `FLAT_HOURLY` | `int(duration_hours × value)` | `=TRUNC(Hours*F2)` | 2 h at 800 DA/h → 1 600 |
| `FIXED_SESSION` | `value` | `=F2` | 1 500 DA per session → 1 500 |

Note the second and third do **not** depend on gross at all: a `FIXED_SESSION` teacher is owed their rate even if the session earned the academy nothing. In the app that means a payout row with `gross_revenue_da = 0` and `teacher_cut_da = 1500`. Spreadsheets rarely have a column that behaves that way, so it is worth a second look when you reconcile.

### 6.5 Every KPI card, with the formula that reproduces it

`Ledger` columns are `A`–`I` as above; `Sessions` columns `A`–`J`.

| Screen card (field) | App source | Spreadsheet formula |
|---|---|---|
| "This month's income" (`month_income`) | `_collected_between` for the current month (`billing_service.py:296-303`) | `=SUMIFS(Ledger!F:F,Ledger!C:C,"IN",Ledger!A:A,">="&EOMONTH(TODAY(),-1)+1,Ledger!A:A,"<="&TODAY())` |
| Money in / out / Net (archive totals) | `list_billing_records` (`:1696-1706`) | in `=SUMIF(Ledger!C:C,"IN",Ledger!F:F)`; out `=SUMIF(Ledger!C:C,"OUT",Ledger!F:F)`; net `=SUMIF(Ledger!C:C,"IN",Ledger!F:F)-SUMIF(Ledger!C:C,"OUT",Ledger!F:F)` |
| Student tuition donut — Paid / Due / Overdue / Total | `get_billing_stats` (`:273, 311-315`) | A `COUNTIF` per bucket over a roster sheet: paid `=COUNTIF(Roster!$D:$D,"ACTIVE")`, overdue `=COUNTIF(Roster!$D:$D,"OVERDUE")+COUNTIF(Roster!$D:$D,"SUSPENDED")`, total `=COUNTA(Roster!$A$2:$A$9999)`. The app folds each student to their **strongest** state first (`_unique_students_by_subscription_state`, `:208-252`), so a student is counted once — replicate that with a pivot before the `COUNTIF`. |
| Teacher payroll donut — Pending / Settled / Overdue | `get_billing_stats` (`:286-294`) | pending `=COUNTIF(Sessions!I:I,"PENDING")`; settled `=COUNTIF(Sessions!I:I,"PAID")`; overdue = `PENDING` rows whose date is more than 30 days old: `=COUNTIFS(Sessions!I:I,"PENDING",Sessions!A:A,"<"&TODAY()-30)` |
| "Owed to teachers" | `get_teacher_payments` (`owed_da = pending_da`) | `=SUMIF(Sessions!I:I,"PENDING",Sessions!G:G)` |
| "Already paid" | same (`settled_da = paid_da`) | `=SUMIF(Sessions!I:I,"PAID",Sessions!G:G)` |
| "Gross collected" | same (`gross_revenue_da`) | `=SUM(Sessions!D:D)` |
| Payout dashboard — Total Pending / Paid / All | `PayoutRecord` sums | `=SUMIF(Sessions!I:I,"PENDING",Sessions!G:G)`, `=SUMIF(Sessions!I:I,"PAID",Sessions!G:G)`, `=SUM(Sessions!G:G)` |
| "Total revenue" | `get_financial_summary` (`:2322-2329`) | `=SUMIFS(Ledger!F:F,Ledger!B:B,"STUDENT_PAYMENT",Ledger!G:G,"<>CANCELLED")` |
| "Teacher cost" | same (`:2332-2333`) | `=SUM(Sessions!G:G)` — settled or not; the class ran, so the money is owed |
| "School expenses" | same (`:2338-2339`) | `=SUMIF(Ledger!B:B,"EXPENSE",Ledger!F:F)` |
| "Net profit" | same (`net_profit = revenue − teacher cost − expenses`) | `=SUMIFS(Ledger!F:F,Ledger!B:B,"STUDENT_PAYMENT",Ledger!G:G,"<>CANCELLED")-SUM(Sessions!G:G)-SUMIF(Ledger!B:B,"EXPENSE",Ledger!F:F)` |
| Expense panel — "Last 6 months" / "All time" / "Records" | `get_expense_summary` (`:2253-2302`) | window `=SUMIFS(Ledger!F:F,Ledger!B:B,"EXPENSE",Ledger!A:A,">="&EDATE(TODAY(),-6))`; all time `=SUMIF(Ledger!B:B,"EXPENSE",Ledger!F:F)`; count `=COUNTIF(Ledger!B:B,"EXPENSE")` |
| Average class revenue (statement line) | `average_class_revenue = int(gross / session_count)` (`payout_schedule_service.py:560`) | `=TRUNC(SUM(Sessions!D:D)/COUNT(Sessions!D:D))` |
| Hours on a statement | `_session_duration_hours` (`:1102-1111`) | End − Start on a time column; the app floors at 1 h when times are missing |

Two honest notes on these formulas. First, the app computes each figure from its **own table** — revenue from `student_subscriptions`, teacher cost from `payout_records` — so the spreadsheet must not "simplify" by deriving one from another; that is precisely how the app's own numbers once disagreed before `_payout_effective_date` was introduced to unify them (`billing_service.py:373-393`). Second, the app **truncates** (`int(...)`), it does not round; use `TRUNC`, not `ROUND`.

### 6.6 The due flag, and the two-column comparison

The app's rule, in one line (`payout_schedule_service.py:139-146`): *is there money in the ledger from a period that has ended?* In the spreadsheet that is a single `IF`, and on paper it is two columns read against each other:

| Cell | Formula | What it says |
|---|---|---|
| `Config!B2` | `=DATE(2026,10,11)` | the next payday |
| any cell | `=IF(AND(TODAY()>=Config!$B$2,SUMIF(Sessions!$I:$I,"PENDING",Sessions!$G:$G)>0),"DUE","")` | payday has passed **and** something is still owed |

The two conditions are both required. Dropping the second one gives you a nag: an academy on a weekly cadence owes nothing after it has paid, and a badge over a zero is not a fact.

### 6.7 Statements and breakdowns

- **Per-teacher statement** → filter `Ledger` (and `Sessions`) on one name, or build a pivot table with `Teacher` as the filter field. On paper: rule a page, copy every line for that teacher, total the `G` column, and write `PENDING` in the margin beside anything unpaid.
- **Per-group breakdown** → a pivot table with `Group` as the row field and `SUM` of Gross / Cut / Still owed. On paper: one page per group, each totalled, and the group totals summed to the teacher's own figure — which is the property the app guarantees (`payout_schedule_service.py:498-500`).
- **The aging buckets** (the one legacy screen still in use) → `=COUNTIFS(...,"<="&TODAY(),...)` per band, against the buckets the app uses: 1–7 days = `recent`, 8–30 = `aging`, 30+ = `critical` (`overdue_bucket`, `app/utils/formatters.py:80-90`).
- **Export** → File → Save As for the spreadsheet, Print for the PDF. **Import** → paste the `Ledger` column back in, but only the `EXPENSE` rows; student payments must be retyped (see §5.4).

---

## 7. Where the numbers can go wrong

Honest limits, verified in the code.

1. **Two coexisting models, one of them unwritten.** `StudentBilling`, `PaymentLog` and `PaymentPlan` are still readable and still have working endpoints, but nothing in the money flow writes them. On an academy that has only used the money model they are empty, and the one screen that reads them (aging buckets) shows nothing. If you ever reconcile against a legacy report, it will be blank for reasons that are structural, not editorial.

2. **"End Class" and "Class Done" are not the same button.** `POST /api/sessions/{id}/end` (the Classes tab) closes the register, charges absences, and marks the class `conducted` — **but writes no payout**. Only `POST /api/billing/sessions/{id}/finalize` (the Dashboard's PIN modal) calls `finalize_session` and writes the `PENDING` `PayoutRecord`. A class ended from the Classes tab, and never finalised, will show as conducted with no money owed to its teacher until something calls finalize. This is a real gap between two entry points, and it is the single most likely way for a teacher's pay to be under-counted.

3. **Nothing schedules.** Every job in `app/tasks/cron_jobs.py` is unreachable because `init_scheduler` has no call site. That means: no automatic overdue marking, no automatic cycle renewal, no automatic renewal reminders, no automatic closing of past one-off classes. Anything a cron job would have done, a person must do, or it does not happen.

4. **A cadence marks due; it never pays.** `payout_schedules` stores a date rule. Reading it produces a flag. Only `mark_payout_paid` moves a record to `PAID`, and that needs the owner's PIN. There is no path from "the 5th arrived" to "money moved" that does not go through a human pressing a button.

5. **A `FIXED_SESSION` teacher is owed even on a zero-gross class.** If a class is conducted with no charged attendees, the payout is still `commission_value` (for `FIXED_SESSION`) while `gross_revenue_da` is 0. The academy's share on that row is negative in arithmetic terms (`0 − 1500`). The app never computes an academy share as a stored number, so nothing breaks — but a spreadsheet that adds a share column will show `-1500` and look alarming.

6. **Truncation, not rounding.** `int(gross_da * commission_value / 100)` truncates toward zero. A 1 050 DA session at 33 % gives `int(346.5)` = **346 DA** to the teacher, not 347. Over a term this is a few dinars against the teacher, always. `round()` in a spreadsheet will disagree with the app by one dinar on such rows; `TRUNC()` will not.

7. **`RevenueEntry` is written at check-in, not at close.** If a student is checked in and then the class is cancelled, `finalize_session(conducted=False)` **deletes** the session's `RevenueEntry` and `PayoutRecord` rows (`billing_service.py:1221-1227`). But a class merely left `in_progress` — never ended and never finalised — keeps its revenue entries with no payout against them, so revenue and teacher cost drift apart for that session.

8. **A free session earns and costs nothing.** `record_checkin_billing_side_effects` returns early for `is_free_session` (`:989-991`), so no credit is spent and no revenue is written. If a free session is later finalised, gross falls back to `present_count × price_da` — which can *invent* revenue for a class the academy meant to give away. The fallback at `:1173-1177` does not consult `is_free_session`.

9. **Absences and the `absence_consumes_credit` toggle change gross.** With the toggle on, an absent student still spends a credit and still earns the academy a `RevenueEntry` at check-in (`:1014-1049`); with it off, they earn nothing (`:998-1002`). Flipping the toggle changes future gross, and there is no historical marker on the row to say which rule applied.

10. **The activity log is the audit trail.** Every money-touching action writes an `ActivityLog` row with the acting user: payments (`routes/billing.py:325-333`), manual payouts (`:411-426`), the finalize flow (`:963-971`), the statement export (`:757-765`). Note that `activity_logs` is **excluded from the portable half** of the school archive (`school_export_service.py:56-58`) but present in its database copy — so a CSV-only archive will not contain the audit trail.

11. **`TeacherPayroll` and `TeacherHoursLog` are always empty on a real academy.** Their only writers are dead. A screen reading them (the teacher drawer's "payroll summary", the legacy `/billing/payroll` list) will show zeros. This is not "no payroll yet"; it is "no producer".

12. **A cadence you do not actually follow nags forever.** Due-ness is recomputed from `date.today()` on every read (§4.2), so once a payday has passed with money outstanding that teacher is due — and stays due every single day until somebody settles the rows. A fortnightly habit entered as `WEEKLY` will show the desk a due badge twice as often as it pays, and the badge carries no memory that last week's was ignored. The cadence is a claim about your own behaviour; the app has no way to check whether you kept it.

---

## 8. What this document could not verify

Stated so these can be checked rather than trusted.

1. **Which end-of-class path a real desk uses.** Both endpoints exist and both are reachable from the frontend, so I cannot say whether the Classes-tab "End Class" is used in practice or whether the Dashboard's "Class Done" is the only one operators press. The consequence of the gap (§7.2) is real either way, but its frequency is not something the code can tell me.

2. **That `db.create_all()` actually runs on every packaged start.** I verified both halves that can be read statically: `packaging/launcher.py:207` contains the call, and `packaging/vinta_review.spec:103-106` bundles only the built frontend — no ALTER script — which is why a new *table* is the safe way to add schema and a new column is not. What I did not do is run the packaged build, so I can confirm the call is written, not that it executes on every launch of a shipped `.exe`.

3. **Whether any existing academy database already has a `payout_schedules` row.** I did not open `vinta_seed.db` or reproduce the seed, so I do not know whether the default row is created for an academy that has never opened Settings. The model's default (`cadence="NONE"`) implies the app behaves as before when no row exists, but I did not confirm a row is ever auto-created.

4. **The exact set of `status` values a subscription can hold in live data.** The model comments list six (`ACTIVE|EXPIRED|OVERDUE|DEPLETED|CANCELLED|SUSPENDED`), and the code sets `ACTIVE`, `DEPLETED` and `SUSPENDED` in paths I read. I did not find the writer that sets `EXPIRED` or `OVERDUE`, so I cannot say what marks a subscription expired — it may be an unread path, a cron job that never runs (§7.3), or nothing at all.

5. **The frontend's billing type declarations versus what is rendered.** `vinta-school-os/src/types/billing.ts` declares legacy types (`PaymentPlan`, `PaymentLog`, `StudentBilling` with `payment_plan_id` and `duration_days`) that no component consumes. I verified absence of consumers by grep; I did not run the app to confirm no dynamic access reaches them.

6. **Whether the `FLAT_HOURLY` duration is always as billed.** `_session_duration_hours` floors at 1.0 hours when start/end times are missing (`billing_service.py:1106-1111`), so a session with no times bills as a full hour. I did not verify how often times are absent in practice, so the size of this effect is unknown.

7. **Whether the school archive's database snapshot is byte-complete.** I read that `_database_snapshot` catches exceptions and returns `None` rather than failing the export (`school_export_service.py:165-168`), so the database half can be silently absent. The README states it plainly to the user, but I did not exercise the path to see how often it degrades.

8. **Line numbers are correct as of this reading.** Every function and route cited was read at the stated line. A line number is a property of a revision, and `graphify update .` was not run (per the project's own note, code changes would require it); if the source moves, the numbers move with it.

9. **The frontend was changing while this document was written.** A parallel change was landing in `vinta-school-os/src` throughout — adding the teacher-side payout UI described in §4.4 and touching `features/billing/PayoutDetailsCard.tsx`, `features/billing/TeacherPayments.tsx`, `features/teachers/TeacherDrawer.tsx`, `features/settings/BillingConfig.tsx`, `lib/payoutSchedule.ts`, `types/settings.ts`, `types/teacher.ts` and the three `i18n/locales/*/` billing, settings and teachers files. Every frontend statement in this guide was re-checked late in the writing, but there is no commit to pin them to: `Backend/vinta-academy-backend` reports *Is a git repository: false*, so no diff can tell you which of those edits preceded this reading and which followed it. Re-grep before relying on any sentence of the form "the frontend does X".

10. **The backend was mid-change too.** The same period saw edits to `app/models/billing.py`, `app/routes/billing.py`, `app/routes/settings.py`, `app/routes/teachers.py` and `app/i18n/catalogue.py`. The line numbers and behaviours quoted here are from the revisions I read; because there is no version control in this tree, I cannot tell you whether those files moved after my last read of them.

