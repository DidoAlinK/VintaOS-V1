import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { DayPicker } from '../../components/ui/DayPicker'
import type { BillingRecordFilters, BillingRecordKind } from '../../types/billing'
import { PRESETS, matchPreset, presetRange, type PresetKey } from './recordFilterState'
import { Search, X } from 'lucide-react'

/* ─── Filter fields, shared by the archive and the export ───
 *
 * Rendered in both the payment-records archive and the export popup. It holds
 * no state of its own beyond the profile search box: the filter object lives
 * with the caller, so the two screens cannot drift into having their own
 * private idea of what is selected. */

export interface ProfileOption {
  id: string
  name: string
  type: 'STUDENT' | 'TEACHER'
}

interface BillingRecordFiltersProps {
  filters: BillingRecordFilters
  onChange: (next: BillingRecordFilters) => void
  /** Rendered in a tighter two-column layout inside the export popup. */
  compact?: boolean
}

const TYPES: { value: BillingRecordKind; labelKey: string }[] = [
  { value: 'STUDENT_PAYMENT', labelKey: 'records.type.studentPayment' },
  { value: 'TEACHER_PAYOUT', labelKey: 'records.type.teacherPayout' },
  { value: 'EXPENSE', labelKey: 'records.type.expense' },
]

/* ─── Profile picker ───
 *
 * A plain `<select>` of every profile is not an option: an academy can hold
 * four figures' worth of students, and a dropdown of 1,000 names is unusable.
 * Students are searched server-side (`/students?q=`, the same debounced call
 * the payment flows use); teachers come from the full roster, which is small
 * enough to filter here.
 */

function ProfilePicker({
  value,
  onChange,
}: {
  value: string
  onChange: (profileId: string, label?: string) => void
}) {
  const { t } = useTranslation('billing')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<ProfileOption[]>([])
  const [searching, setSearching] = useState(false)
  const [open, setOpen] = useState(false)
  /* The chosen profile's display name. Held here rather than derived, because
     once a profile is picked the list it came from is gone. */
  const [picked, setPicked] = useState<{ id: string; name: string } | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const box = useRef<HTMLDivElement | null>(null)

  /* ── Full teacher roster, once per open ── */
  const [teachers, setTeachers] = useState<ProfileOption[]>([])
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const { data } = await api.get('/teachers')
        const rows = data.teachers ?? data ?? []
        if (!cancelled) {
          setTeachers(
            rows.map((row: { id: string; full_name?: string; name?: string }) => ({
              id: row.id,
              name: row.full_name ?? row.name ?? '',
              type: 'TEACHER' as const,
            })),
          )
        }
      } catch {
        if (!cancelled) setTeachers([])
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  /* ── Debounced student search ── */
  const handleQuery = useCallback((next: string) => {
    setQuery(next)
    if (timer.current) clearTimeout(timer.current)
    if (next.trim().length < 2) {
      setResults([])
      setSearching(false)
      return
    }
    setSearching(true)
    timer.current = setTimeout(async () => {
      try {
        const { data } = await api.get('/students', { params: { q: next.trim() } })
        const rows = data.students ?? data ?? []
        setResults(
          rows.map((row: { id: string; full_name?: string; first_name?: string; last_name?: string }) => ({
            id: row.id,
            name:
              row.full_name ??
              `${row.first_name ?? ''} ${row.last_name ?? ''}`.trim(),
            type: 'STUDENT' as const,
          })),
        )
      } catch {
        setResults([])
      } finally {
        setSearching(false)
      }
    }, 300)
  }, [])

  /* ── Click-away ── */
  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  const teacherMatches = query.trim().length < 2
    ? []
    : teachers.filter((tt) =>
        tt.name.toLowerCase().includes(query.trim().toLowerCase()),
      )

  const options: ProfileOption[] = [...teacherMatches, ...results]
  // A picked profile whose id no longer appears in the list is still selected;
  // only clear the *search* when the caller clears the filter.
  useEffect(() => {
    if (!value) setPicked(null)
  }, [value])

  if (picked) {
    return (
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-[var(--muted)]">
          {t('records.filters.profile')}
        </label>
        <div className="flex items-center gap-2 h-10 px-3 rounded-[var(--radius-sm)] bg-[var(--input-bg)] border border-[var(--glass-border)]">
          <span className="text-sm text-[var(--text)] truncate flex-1 min-w-0">{picked.name}</span>
          <button
            type="button"
            onClick={() => {
              setPicked(null)
              setQuery('')
              setResults([])
              onChange('')
            }}
            className="shrink-0 text-[var(--muted)] hover:text-[var(--red)] transition-colors"
            aria-label={t('records.filters.clearProfile')}
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1.5" ref={box}>
      <label className="text-xs font-medium text-[var(--muted)]">
        {t('records.filters.profile')}
      </label>
      <div className="relative">
        <Search className="absolute start-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)] pointer-events-none" />
        <input
          type="text"
          value={query}
          placeholder={t('records.filters.profilePlaceholder')}
          onChange={(e) => { handleQuery(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          className={cn(
            'w-full h-10 ps-9 pe-3 rounded-[var(--radius-sm)]',
            'text-sm text-[var(--text)] placeholder:text-[var(--muted)]/50',
            'bg-[var(--input-bg)] border border-[var(--glass-border)]',
            'outline-none focus:border-[var(--gold)] focus:ring-1 focus:ring-[var(--gold)]/30',
            'transition-colors',
          )}
        />
        {searching && (
          <div className="absolute end-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 border-2 border-[var(--gold)] border-t-transparent rounded-full animate-spin" />
        )}

        {open && options.length > 0 && (
          <div
            className={cn(
              'absolute z-30 mt-1 w-full max-h-52 overflow-y-auto',
              'rounded-[var(--radius-sm)] shadow-lg',
              'bg-[var(--glass)] backdrop-blur-[22px] border border-[var(--glass-border)]',
            )}
          >
            {options.slice(0, 40).map((opt) => (
              <button
                key={`${opt.type}-${opt.id}`}
                type="button"
                onClick={() => {
                  setPicked({ id: opt.id, name: opt.name })
                  setOpen(false)
                  setQuery('')
                  setResults([])
                  onChange(opt.id, opt.name)
                }}
                className={cn(
                  'w-full flex items-center justify-between gap-2 px-3 py-2 text-start text-sm',
                  'hover:bg-[var(--glass-strong)] transition-colors',
                  'border-b border-[var(--glass-border)]/30 last:border-b-0',
                )}
              >
                <span className="text-[var(--text)] truncate">{opt.name}</span>
                <span className="shrink-0 text-[10px] uppercase tracking-wide text-[var(--muted)]">
                  {t(`records.profileType.${opt.type === 'TEACHER' ? 'teacher' : 'student'}`)}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── The fields ─── */

export function BillingRecordFilters({
  filters,
  onChange,
  compact = false,
}: BillingRecordFiltersProps) {
  const { t } = useTranslation('billing')

  const set = (patch: Partial<BillingRecordFilters>) =>
    onChange({ ...filters, ...patch })

  const active = matchPreset(filters)

  const applyPreset = (key: string) => {
    const range = presetRange(key as PresetKey)
    set({ from: range.from, to: range.to })
  }

  return (
    <div className="flex flex-col gap-4">
      {/* ── Range ── */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-[var(--muted)]">
            {t('records.filters.range')}
          </span>
          {/* A preset a user cannot see the provenance of is a preset they
              cannot trust, so an edited range says so rather than leaving a
              preset chip looking selected. */}
          {active === 'custom' && (
            <span className="text-[10px] uppercase tracking-wide text-[var(--gold)]">
              {t('records.filters.custom')}
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => applyPreset(key)}
              aria-pressed={active === key}
              className={cn(
                'px-2.5 py-1 rounded-full text-xs font-medium border transition-colors',
                active === key
                  ? 'bg-[var(--gold-soft)] border-[var(--gold)] text-[var(--gold)]'
                  : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)]',
              )}
            >
              {t(`records.preset.${key}`)}
            </button>
          ))}
        </div>

        <div className={cn('grid gap-3', compact ? 'grid-cols-2' : 'grid-cols-1 sm:grid-cols-2')}>
          {/* `allowPast` is not optional here. `DayPicker` disables days before
              today by default — right for booking a class, wrong for every use
              this component has, since a record of money that has already moved
              is entirely in the past. Without it, both date filters would open
              on a calendar where nothing can be picked. */}
          <DayPicker
            label={t('records.filters.from')}
            value={filters.from}
            onChange={(iso) => set({ from: iso })}
            placeholder={t('records.filters.anyDate')}
            allowPast
          />
          <DayPicker
            label={t('records.filters.to')}
            value={filters.to}
            onChange={(iso) => set({ to: iso })}
            placeholder={t('records.filters.anyDate')}
            allowPast
          />
        </div>

        {/* The server rejects an inverted range with a 400, but a user should
            not have to submit the form to find out the two dates are the wrong
            way round. */}
        {filters.from && filters.to && filters.from > filters.to && (
          <p role="alert" className="text-xs font-medium text-[var(--red)]">
            {t('records.filters.rangeReversed')}
          </p>
        )}
      </div>

      {/* ── Profile + type ── */}
      <div className={cn('grid gap-3', compact ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2')}>
        <ProfilePicker value={filters.profile} onChange={(id) => set({ profile: id })} />

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--muted)]">
            {t('records.filters.type')}
          </label>
          <Select
            value={filters.type}
            onChange={(v) => set({ type: v as BillingRecordFilters['type'] })}
            options={[
              { value: '', label: t('records.filters.allTypes') },
              ...TYPES.map((tt) => ({ value: tt.value, label: t(tt.labelKey) })),
            ]}
            className={cn(
              'h-10 px-3 rounded-[var(--radius-sm)] text-sm',
              'bg-[var(--input-bg)] border border-[var(--glass-border)]',
              'text-[var(--text)] outline-none',
              'focus:border-[var(--gold)] focus:ring-1 focus:ring-[var(--gold)]/30',
            )}
          />
        </div>
      </div>

      {/* ── Amount ── */}
      <div className={cn('grid gap-3', compact ? 'grid-cols-2' : 'grid-cols-1 sm:grid-cols-2')}>
        <Input
          label={t('records.filters.minAmount')}
          type="number"
          min={0}
          inputMode="numeric"
          value={filters.min_amount}
          onChange={(e) => set({ min_amount: e.target.value })}
        />
        <Input
          label={t('records.filters.maxAmount')}
          type="number"
          min={0}
          inputMode="numeric"
          value={filters.max_amount}
          onChange={(e) => set({ max_amount: e.target.value })}
        />
      </div>

      {/* ── Clear ── */}
      <div>
        <button
          type="button"
          onClick={() => onChange({ from: '', to: '', profile: '', type: '', min_amount: '', max_amount: '' })}
          className={cn(
            'inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--radius-sm)]',
            'text-xs font-medium text-[var(--muted)]',
            'hover:text-[var(--red)] hover:bg-[var(--red-soft)]',
            'transition-colors',
          )}
        >
          <X className="w-3.5 h-3.5" />
          {t('records.filters.clear')}
        </button>
      </div>
    </div>
  )
}

export default BillingRecordFilters
