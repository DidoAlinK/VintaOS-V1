import type { BillingRecordFilters } from '../../types/billing'

/* ─── The filter set, in one place ───
 *
 * The archive and the export both read this shape, and `toParams` below is the
 * only thing that turns it into a query string. Two screens, one definition:
 * a filter that narrows the table cannot end up meaning something else in the
 * file the user downloads from it. */

export const EMPTY_FILTERS: BillingRecordFilters = {
  from: '',
  to: '',
  profile: '',
  type: '',
  min_amount: '',
  max_amount: '',
}

/* ─── Local-date helpers ───
 *
 * Deliberately NOT `toISOString().slice(0, 10)`: that converts to UTC first, so
 * anywhere east of Greenwich the first of the month would come out as the last
 * day of the previous one. */

/** `YYYY-MM-DD` from local calendar parts. */
export function isoDay(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function monthStart(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

export function monthEnd(d: Date): Date {
  // Day 0 of the next month is the last day of this one — no table of lengths,
  // and it stays right in a leap year.
  return new Date(d.getFullYear(), d.getMonth() + 1, 0)
}

/* ─── Presets ───
 *
 * `key` names the dictionary entry; the ranges are computed, never stored, so a
 * preset cannot go stale across a month boundary the way a hard-coded date
 * range would. */

export type PresetKey =
  | 'all'
  | 'thisMonth'
  | 'lastMonth'
  | 'last3Months'
  | 'thisYear'

export const PRESETS: PresetKey[] = [
  'all',
  'thisMonth',
  'lastMonth',
  'last3Months',
  'thisYear',
]

export function presetRange(key: PresetKey, today = new Date()): { from: string; to: string } {
  switch (key) {
    case 'thisMonth':
      return { from: isoDay(monthStart(today)), to: isoDay(monthEnd(today)) }
    case 'lastMonth': {
      const last = new Date(today.getFullYear(), today.getMonth() - 1, 1)
      return { from: isoDay(monthStart(last)), to: isoDay(monthEnd(last)) }
    }
    case 'last3Months': {
      const start = new Date(today.getFullYear(), today.getMonth() - 2, 1)
      return { from: isoDay(monthStart(start)), to: isoDay(monthEnd(today)) }
    }
    case 'thisYear':
      return {
        from: isoDay(new Date(today.getFullYear(), 0, 1)),
        to: isoDay(new Date(today.getFullYear(), 11, 31)),
      }
    case 'all':
    default:
      return { from: '', to: '' }
  }
}

/* ─── Serialising ─── */

/**
 * The filter set as query params, omitting anything unset.
 *
 * Sending `min_amount=''` would reach the server as an unparseable bound and
 * come back 400, so an empty field has to leave the query entirely.
 */
export function toParams(filters: BillingRecordFilters): Record<string, string> {
  const params: Record<string, string> = {}
  if (filters.from) params.from = filters.from
  if (filters.to) params.to = filters.to
  if (filters.profile) params.profile = filters.profile
  if (filters.type) params.type = filters.type
  if (filters.min_amount.trim() !== '') params.min_amount = filters.min_amount.trim()
  if (filters.max_amount.trim() !== '') params.max_amount = filters.max_amount.trim()
  return params
}

/** True when nothing is narrowed — used to label the state as "all records". */
export function isUnfiltered(filters: BillingRecordFilters): boolean {
  return Object.keys(toParams(filters)).length === 0
}

/** The number of active filters, for a badge on the collapsed panel. */
export function activeFilterCount(filters: BillingRecordFilters): number {
  return Object.keys(toParams(filters)).length
}

/** The preset a given range corresponds to, or `'custom'` when it matches none. */
export function matchPreset(
  filters: BillingRecordFilters,
  today = new Date(),
): PresetKey | 'custom' {
  for (const key of PRESETS) {
    const range = presetRange(key, today)
    if (range.from === filters.from && range.to === filters.to) return key
  }
  return 'custom'
}
