/**
 * Vinta School OS — When teachers get paid
 *
 * The app has always recorded a teacher's earnings one session at a time: at
 * End Class the server writes one `PayoutRecord(status="PENDING")` per
 * conducted session, and it stays pending until somebody settles it behind the
 * owner's PIN. That is a *ledger*, and a good one — but nothing in it knows
 * that teachers are paid on a Saturday, or on the 5th, or that a month's worth
 * of pending rows has come due. This module supplies the missing calendar.
 *
 * Two things it deliberately does not do:
 *
 *   * **It never moves money.** A cadence decides whether somebody is *marked*
 *     due. Settling is still the PIN-gated payout action, and the server's due
 *     list is a filter over pending rows, not a payment run. Nothing in this
 *     app runs on a timer — the server computes every payday from today's date
 *     when it is asked — so a week that has "arrived" cannot pay itself out.
 *   * **It does not compute dates in the browser.** `next_payout_date` comes
 *     from the server, which owns the month-length and weekend rules. A second
 *     implementation of "the 31st in February" here would be a second answer to
 *     the same question, and the two would disagree eventually.
 *
 * Three states, which is one more than it looks:
 *
 *   * no stored row at all          → the teacher inherits the academy default
 *   * a stored `NONE` row           → this teacher is settled by hand, whatever
 *                                     the academy default says
 *   * a stored `WEEKLY`/`MONTHLY`   → this teacher's own cadence
 *
 * The middle one is why `INHERIT` exists as a *choice* and not as a cadence:
 * "follow the academy" and "pay by hand" are different intentions and have to
 * be distinguishable, or an owner who wanted a manual teacher would have to
 * give up their academy default to get one.
 */

import api from './api'

// ─────────────────────────────────────────────
// The vocabulary
// ─────────────────────────────────────────────

/** What the server stores in `payout_schedules.cadence`. */
export type PayoutCadence = 'NONE' | 'WEEKLY' | 'MONTHLY'

/**
 * What a person may choose. `INHERIT` is not a cadence — it is the absence of
 * one, and the server implements it by deleting the row rather than by storing
 * a fourth value.
 */
export type PayoutChoice = PayoutCadence | 'INHERIT'

export const PAYOUT_CADENCES: PayoutCadence[] = ['NONE', 'WEEKLY', 'MONTHLY']

/** Where a resolved schedule came from — the teacher's own row, or the academy's. */
export type PayoutScheduleSource = 'teacher' | 'academy' | 'none'

export interface PayoutSchedule {
  teacher_id: string | null
  cadence: PayoutCadence
  /** 0 = Monday … 6 = Sunday, matching Python's `date.weekday()`. */
  day_of_week: number | null
  /** 1 … 31. A 31 in a 30-day month means that month's last day. */
  day_of_month: number | null
  source: PayoutScheduleSource
  /** ISO `YYYY-MM-DD`, or null when no cadence is set. */
  next_payout_date: string | null
  last_payout_date: string | null
}

/** A cadence being edited, before it is written. */
export interface PayoutDraft {
  cadence: PayoutChoice
  day_of_week: number | null
  day_of_month: number | null
}

/**
 * The week, in the server's numbering.
 *
 * Monday is 0 because that is what `date.weekday()` answers, and the index is
 * the server's index — not a display order that happens to start on Monday.
 * Algeria's week runs Sunday to Thursday, so Sunday (6) is the natural default
 * payday and is last in this list rather than first.
 */
export const WEEKDAYS: { value: number; key: string }[] = [
  { value: 0, key: 'mon' },
  { value: 1, key: 'tue' },
  { value: 2, key: 'wed' },
  { value: 3, key: 'thu' },
  { value: 4, key: 'fri' },
  { value: 5, key: 'sat' },
  { value: 6, key: 'sun' },
]

/** Sunday — the last day of the working week in Algeria, and payday here. */
export const DEFAULT_DAY_OF_WEEK = 6

/** The 1st: unambiguous in every month, unlike the 29th-31st. */
export const DEFAULT_DAY_OF_MONTH = 1

/**
 * What the server answers for an academy that has never opened the setting —
 * and what this module falls back to when it has no answer at all.
 *
 * `NONE` on purpose. An academy that upgrades into this feature and never
 * touches it must behave exactly as it did before it existed: no paydays, no
 * due badges, nothing settled but by hand.
 */
export const NO_SCHEDULE: PayoutSchedule = {
  teacher_id: null,
  cadence: 'NONE',
  day_of_week: null,
  day_of_month: null,
  source: 'none',
  next_payout_date: null,
  last_payout_date: null,
}

// ─────────────────────────────────────────────
// Reading what the server sent
// ─────────────────────────────────────────────

function asCadence(value: unknown, fallback: PayoutCadence): PayoutCadence {
  return value === 'NONE' || value === 'WEEKLY' || value === 'MONTHLY' ? value : fallback
}

function asDay(value: unknown, min: number, max: number): number | null {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isInteger(n) || n < min || n > max) return null
  return n
}

function asIsoDate(value: unknown): string | null {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null
}

/**
 * Turn an API payload into a `PayoutSchedule`, dropping anything unreadable.
 *
 * Defensive rather than trusting, because this feeds a settlement decision on a
 * screen an owner reads to decide whether someone is owed money. A cadence the
 * server and this build disagree about must not arrive as `WEEKLY` by
 * accident — better to fall back to "settled by hand", which is the state that
 * asks a human to look, than to invent a payday.
 */
export function parseSchedule(raw: unknown): PayoutSchedule {
  if (!raw || typeof raw !== 'object') return { ...NO_SCHEDULE }
  const row = raw as Record<string, unknown>

  const cadence = asCadence(row.cadence, 'NONE')
  const source = row.source
  const teacherId = row.teacher_id

  return {
    teacher_id: typeof teacherId === 'string' ? teacherId : null,
    cadence,
    // A day is only meaningful for the cadence that reads it. Keeping a stale
    // `day_of_week` on a monthly schedule would let the UI show a weekday for a
    // rule that does not use one.
    day_of_week: cadence === 'WEEKLY' ? asDay(row.day_of_week, 0, 6) : null,
    day_of_month: cadence === 'MONTHLY' ? asDay(row.day_of_month, 1, 31) : null,
    source: source === 'teacher' || source === 'academy' ? source : 'none',
    next_payout_date: cadence === 'NONE' ? null : asIsoDate(row.next_payout_date),
    last_payout_date: cadence === 'NONE' ? null : asIsoDate(row.last_payout_date),
  }
}

/** The draft a schedule represents, so the controls open on the stored values. */
export function draftFrom(schedule: PayoutSchedule | null | undefined): PayoutDraft {
  const s = schedule ?? NO_SCHEDULE
  return {
    cadence: s.cadence,
    day_of_week: s.day_of_week ?? DEFAULT_DAY_OF_WEEK,
    day_of_month: s.day_of_month ?? DEFAULT_DAY_OF_MONTH,
  }
}

/** True when the draft differs from what is stored — i.e. Save has something to do. */
export function isDraftDirty(draft: PayoutDraft, schedule: PayoutSchedule | null | undefined): boolean {
  const s = schedule ?? NO_SCHEDULE
  if (draft.cadence !== s.cadence) return true
  if (draft.cadence === 'WEEKLY') return (draft.day_of_week ?? DEFAULT_DAY_OF_WEEK) !== s.day_of_week
  if (draft.cadence === 'MONTHLY') return (draft.day_of_month ?? DEFAULT_DAY_OF_MONTH) !== s.day_of_month
  return false
}

/**
 * Whether a draft can be written. `WEEKLY` needs a weekday and `MONTHLY` a day
 * of the month; the server refuses a half-filled cadence with a 400, and
 * catching it here means the button is disabled rather than the request failing.
 */
export function isDraftComplete(draft: PayoutDraft): boolean {
  if (draft.cadence === 'NONE' || draft.cadence === 'INHERIT') return true
  if (draft.cadence === 'WEEKLY') return draft.day_of_week !== null
  return draft.day_of_month !== null
}

/**
 * A 29th, 30th or 31st does not exist in every month, and the server resolves
 * that by paying on the month's last day. Worth saying out loud on the screen,
 * because "the 31st" and "the last day" are only the same thing five months a
 * year.
 */
export function mayClampToMonthEnd(draft: PayoutDraft): boolean {
  return draft.cadence === 'MONTHLY' && (draft.day_of_month ?? 0) > 28
}

// ─────────────────────────────────────────────
// Saying it
// ─────────────────────────────────────────────

/**
 * The cadence as one sentence: "Every Sunday", "Day 5 of each month".
 *
 * Keys are fully qualified (`billing:`) so this works with a `t` from any
 * namespace — the Settings screen, the teacher drawer and the payouts dialog
 * all say the same sentence, and three copies of it would eventually diverge.
 * The caller passes the i18next `t` rather than this module importing it, so
 * the sentence follows a language switch without a reload.
 */
export function describeCadence(
  t: (key: string, options?: Record<string, unknown>) => string,
  schedule: {
    cadence: PayoutCadence
    day_of_week?: number | null
    day_of_month?: number | null
  } | null | undefined,
): string {
  const cadence = schedule?.cadence ?? 'NONE'
  if (cadence === 'WEEKLY') {
    const day = weekdayLabel(t, schedule?.day_of_week ?? null)
    if (day) return t('billing:payoutSchedule.summary.WEEKLY', { day })
  }
  if (cadence === 'MONTHLY' && schedule?.day_of_month) {
    return t('billing:payoutSchedule.summary.MONTHLY', { day: schedule.day_of_month })
  }
  return t('billing:payoutSchedule.summary.NONE')
}

/** The same sentence for a draft, including the "follows the academy" case. */
export function describeDraft(
  t: (key: string, options?: Record<string, unknown>) => string,
  draft: PayoutDraft,
): string {
  if (draft.cadence === 'INHERIT') return t('billing:payoutSchedule.summary.INHERIT')
  // Narrowed into a local rather than passing `draft` straight through:
  // narrowing one property does not narrow the object that carries it, so
  // TypeScript still reads `PayoutChoice` at the call below. Widening
  // `describeCadence` to accept `INHERIT` would be worse — it would oblige that
  // function to invent a sentence for a value that is not a cadence, and there
  // is no such sentence.
  const cadence: PayoutCadence = draft.cadence
  return describeCadence(t, {
    cadence,
    day_of_week: draft.day_of_week,
    day_of_month: draft.day_of_month,
  })
}

/** A weekday's full name, or null when the number is not a weekday. */
export function weekdayLabel(
  t: (key: string) => string,
  dayOfWeek: number | null,
): string | null {
  const match = WEEKDAYS.find((d) => d.value === dayOfWeek)
  return match ? t(`billing:payoutSchedule.weekday.${match.key}`) : null
}

// ─────────────────────────────────────────────
// Writing it
// ─────────────────────────────────────────────

/**
 * A draft as the server wants it.
 *
 * `INHERIT` is sent as the word itself, not as `null`: the server has to be
 * able to tell "delete this teacher's row" from "no opinion about this
 * teacher", and an omitted key means the latter. A day that belongs to the
 * other cadence is sent as null rather than left behind, so switching a teacher
 * from weekly to monthly cannot leave a weekday on a monthly row.
 */
export function schedulePayload(draft: PayoutDraft): {
  cadence: PayoutChoice
  day_of_week: number | null
  day_of_month: number | null
} {
  return {
    cadence: draft.cadence,
    day_of_week: draft.cadence === 'WEEKLY' ? draft.day_of_week : null,
    day_of_month: draft.cadence === 'MONTHLY' ? draft.day_of_month : null,
  }
}

/**
 * The academy-wide default, as `GET /settings/billing-config` reports it.
 *
 * Owner-only: that endpoint needs `settings.manage`, so staff get a 403 and
 * this throws. Callers that are rendering something anyway should treat a
 * failure as "unknown" rather than as "no schedule".
 */
export async function fetchAcademyPayoutSchedule(): Promise<PayoutSchedule> {
  const { data } = await api.get('/settings/billing-config')
  return parseSchedule((data as Record<string, unknown>)?.payout_schedule)
}

/**
 * Set the academy-wide default.
 *
 * Writes immediately, like the billing rules do, and for the same reason: the
 * server reads the cadence live, so a staged promise would describe behaviour
 * the app does not have. Throws on refusal — a 403 means the owner role, a 400
 * carries the server's own sentence about the field it did not like.
 */
export async function saveAcademyPayoutSchedule(draft: PayoutDraft): Promise<void> {
  await api.put('/settings/billing-config', { payout_schedule: schedulePayload(draft) })
}

// ─────────────────────────────────────────────
// The due card
// ─────────────────────────────────────────────

/**
 * One teacher as `GET /billing/payroll/due` reports them.
 *
 * Mirrors `payout_schedule_service.list_due_teachers` field for field. The
 * `day_of_week` / `day_of_month` that a schedule otherwise carries are *not* on
 * this row — the server flattens only the cadence and the two dates — so they
 * are not declared here. A field that the server never sends and this parser
 * therefore always answers `null` for is worse than an absent one: it reads as
 * "no weekday set" when the truth is "not asked".
 */
export interface DueTeacher {
  teacher_id: string
  teacher_name: string
  cadence: PayoutCadence
  /** What is owed, and how many unsettled rows make it up. */
  pending_da: number
  pending_count: number
  /** The oldest unsettled row's date — how long this has been owed. */
  oldest_pending_date: string | null
  next_payout_date: string | null
  last_payout_date: string | null
}

export function parseDueTeacher(raw: unknown): DueTeacher | null {
  if (!raw || typeof raw !== 'object') return null
  const row = raw as Record<string, unknown>
  const id = row.teacher_id
  if (typeof id !== 'string' || !id) return null
  return {
    teacher_id: id,
    teacher_name: typeof row.teacher_name === 'string' ? row.teacher_name : '',
    cadence: asCadence(row.cadence, 'NONE'),
    pending_da: Number(row.pending_da) || 0,
    pending_count: Number(row.pending_count) || 0,
    oldest_pending_date: asIsoDate(row.oldest_pending_date),
    next_payout_date: asIsoDate(row.next_payout_date),
    last_payout_date: asIsoDate(row.last_payout_date),
  }
}

/**
 * Teachers whose payday has passed with money still unsettled.
 *
 * An empty list is the ordinary answer, not a failure: an academy on the
 * default cadence has no paydays at all, so this returns nothing and the
 * payments screen shows no badges — exactly how it behaved before the feature
 * existed. That is why a failure here is worth swallowing into an empty list
 * at the call site rather than into an error state on a screen whose real job
 * is showing earnings.
 */
export async function fetchDueTeachers(): Promise<DueTeacher[]> {
  const { data } = await api.get('/billing/payroll/due')
  const rows = (data as { teachers?: unknown })?.teachers
  if (!Array.isArray(rows)) return []
  return rows.map(parseDueTeacher).filter((row): row is DueTeacher => row !== null)
}
