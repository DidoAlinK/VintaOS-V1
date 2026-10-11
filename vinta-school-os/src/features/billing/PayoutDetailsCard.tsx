import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Download, RefreshCw } from 'lucide-react'
import api from '../../lib/api'
import { cn } from '../../lib/cn'
import { triggerDownload, describeRange } from '../../lib/download'
import {
  formatCurrency,
  formatDateFull,
  formatDateISO,
  formatDateShort,
  formatNumber,
} from '../../lib/formatters'
import {
  describeCadence,
  type PayoutCadence,
  type PayoutScheduleSource,
} from '../../lib/payoutSchedule'
import { toast } from '../../stores/uiStore'
import { Badge } from '../../components/ui/Badge'
import { Modal } from '../../components/ui/Modal'
import { Figure } from './TeacherPayments'

/* ─── The details card behind the gold "Due" badge ───
 *
 * One teacher's finances over a period the owner picks, plus that period as a
 * file. It is the answer to "what do we owe them, and for what" — the question
 * the due badge raises and cannot itself answer.
 *
 * The figures come from `GET /billing/teachers/:id/payout-details`, whose
 * per-group rows are built to add up to the same totals shown above them (see
 * `get_teacher_payout_details`); the table below repeats those totals so the
 * owner can check the arithmetic rather than take it on trust.
 *
 * The endpoint deliberately returns `lines: null` — the line items exist for
 * the *export*, which asks for them, and not for this card, which would render
 * a few thousand rows to say four numbers. Nothing here reads `lines`, and the
 * type below says so out loud so nobody renders it by accident.
 */

/* ─── The payload ─── */

interface PayoutDetailsGroup {
  group_id: string | null
  group_name: string | null
  gross_revenue_da: number
  teacher_cut_da: number
  pending_da: number
  paid_da: number
  session_count: number
  duration_hours: number
}

/**
 * One teacher's finances for a window, as the route reports them.
 *
 * `pending_da` / `paid_da` are read rather than their `owed_da` / `settled_da`
 * aliases: the server computes both pairs from the same sums, and reading one
 * pair everywhere is what keeps the two from ever disagreeing on screen.
 */
interface PayoutDetails {
  teacher_id: string
  teacher_name: string
  gross_revenue_da: number
  teacher_cut_da: number
  pending_da: number
  paid_da: number
  session_count: number
  manual_count: number
  duration_hours: number
  average_class_revenue_da: number
  average_cut_per_session_da: number
  /** Who they taught inside the window… */
  students_taught: number
  /** …and who is on their roster today. Two honest numbers, not one. */
  students_enrolled: number
  group_count: number
  groups: PayoutDetailsGroup[]
  schedule: {
    cadence: PayoutCadence
    day_of_week: number | null
    day_of_month: number | null
    source: PayoutScheduleSource
    /** ISO `YYYY-MM-DD`, computed by the server — never in the browser. */
    next_payout_date: string | null
    last_payout_date: string | null
  }
  /**
   * Whether a payday has passed with money still unsettled, and since when.
   *
   * Read from `oldest_pending_date` rather than recomputed from the rows below:
   * it is the same minimum the due list takes over the same pending rows, so the
   * card and the row's tooltip cannot end up disagreeing about how long this has
   * been owed.
   */
  due: {
    is_due: boolean
    pending_da: number
    oldest_pending_date: string | null
  }
  /** Always null on this endpoint; only the export asks the server for lines. */
  lines: null
}

/* ─── The period ─── */

type Preset = 'all' | 'thisMonth' | 'lastMonth' | 'custom'

const PRESETS: Preset[] = ['all', 'thisMonth', 'lastMonth', 'custom']

/** The dictionary path per preset. Fully spelled out so a missing one is greppable. */
const PRESET_LABEL_KEY: Record<Preset, string> = {
  all: 'teacherPayments.details.range.all',
  thisMonth: 'teacherPayments.details.range.thisMonth',
  lastMonth: 'teacherPayments.details.range.lastMonth',
  custom: 'teacherPayments.details.range.custom',
}

/**
 * A preset's bounds, as local calendar days.
 *
 * `formatDateISO` is the app's canonical local-ISO helper (`toLocalISO` under
 * it) — deliberately not `toISOString().slice(0, 10)`, which converts to UTC
 * first and so hands back the previous day for anyone east of Greenwich. This
 * app ships in Algeria, at UTC+1, where that is every day of the year.
 *
 * `thisMonth` stops at *today* rather than at the month's end: a period that
 * reaches into the future would be a claim about sessions that have not
 * happened. `lastMonth` runs its full length, since all of it is past.
 */
function presetRange(preset: Preset): { from: string; to: string } {
  const today = new Date()
  switch (preset) {
    case 'thisMonth':
      return {
        from: formatDateISO(new Date(today.getFullYear(), today.getMonth(), 1)),
        to: formatDateISO(today),
      }
    case 'lastMonth':
      return {
        from: formatDateISO(new Date(today.getFullYear(), today.getMonth() - 1, 1)),
        // Day 0 of this month is the last day of the previous one — no table of
        // month lengths, and it stays right in a leap year.
        to: formatDateISO(new Date(today.getFullYear(), today.getMonth(), 0)),
      }
    case 'all':
    case 'custom':
    default:
      return { from: '', to: '' }
  }
}

/**
 * A typed custom span, with its bounds the right way round.
 *
 * `from > to` is a slip, not an intention — the server refuses it with a 400 —
 * and both bounds are inclusive, so the span is the same either way. Sorting
 * them means the request the owner sees in the span text is the request that is
 * actually sent.
 */
function customRange(from: string, to: string): { from: string; to: string } {
  if (from && to && from > to) return { from: to, to: from }
  return { from, to }
}

/**
 * Only the bounds that are set.
 *
 * An empty `from=` would reach the server as a blank date; it tolerates that,
 * but omitting the key is what "unbounded" actually means. Same rule as
 * `recordFilterState.toParams`.
 */
function rangeParams(from: string, to: string): Record<string, string> {
  const params: Record<string, string> = {}
  if (from) params.from = from
  if (to) params.to = to
  return params
}

/**
 * The filename the server chose, out of `Content-Disposition`.
 *
 * Preferred over a name of our own because the server's carries the period and
 * the language (`teacher-statement-…-ar.pdf`), which is exactly what tells two
 * exports of the same teacher apart in a Downloads folder. Reading it is
 * best-effort: a browser only exposes the header on a same-origin response or
 * when the server lists it in `Access-Control-Expose-Headers`, which is why the
 * caller always has a fallback.
 */
function filenameFromDisposition(header: unknown, fallback: string): string {
  if (typeof header !== 'string') return fallback
  // RFC 5987 form first (`filename*=UTF-8''…`), which is how a non-ASCII name
  // arrives; the plain form is the ASCII-only one.
  const encoded = /filename\*\s*=\s*(?:UTF-8'')?([^;]+)/i.exec(header)
  if (encoded?.[1]) {
    try {
      return decodeURIComponent(encoded[1].trim().replace(/^"|"$/g, ''))
    } catch {
      /* A malformed escape is not worth a crash — fall through to the plain form. */
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(header)
  return plain?.[1]?.trim() || fallback
}

type Format = 'csv' | 'pdf'

/* ─── Props ─── */

export interface PayoutDetailsCardProps {
  teacherId: string
  teacherName: string
  isOpen: boolean
  onClose: () => void
}

/* ─── Component ─── */

export function PayoutDetailsCard({
  teacherId,
  teacherName,
  isOpen,
  onClose,
}: PayoutDetailsCardProps) {
  const { t } = useTranslation('billing')

  const [preset, setPreset] = useState<Preset>('all')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')

  const [details, setDetails] = useState<PayoutDetails | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [hasError, setHasError] = useState(false)
  /** Bumped by Retry; the fetch effect watches it. */
  const [reloadKey, setReloadKey] = useState(0)

  const [exporting, setExporting] = useState<Format | null>(null)

  const { from, to } =
    preset === 'custom' ? customRange(customFrom, customTo) : presetRange(preset)

  /* ── Load on open, and again whenever the range changes ──
   *
   * The `cancelled` flag is the same guard `TeacherDrawer` uses: changing the
   * period, or closing the card, while a request is in flight must not let the
   * older answer overwrite the newer one — or land on a closed card. */
  useEffect(() => {
    if (!isOpen) return
    let cancelled = false
    setIsLoading(true)
    setHasError(false)

    void (async () => {
      try {
        const { data } = await api.get<PayoutDetails>(
          `/billing/teachers/${teacherId}/payout-details`,
          { params: rangeParams(from, to) },
        )
        if (cancelled) return
        setDetails(data)
      } catch {
        if (cancelled) return
        setDetails(null)
        setHasError(true)
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [isOpen, teacherId, from, to, reloadKey])

  /* ── Export the period as a file ── */
  const handleExport = async (format: Format) => {
    if (exporting) return
    setExporting(format)
    try {
      const response = await api.get<Blob>(
        `/billing/teachers/${teacherId}/payout-export`,
        {
          // No `lang` param on purpose: `lib/api.ts` already puts the current
          // language on the `Accept-Language` header of every request, and the
          // route reads it there. A second copy in the query string would be a
          // second answer to the same question.
          params: { ...rangeParams(from, to), format },
          responseType: 'blob',
        },
      )
      // `responseType: 'blob'` makes this a Blob in every browser this app
      // runs in; the guard is for a proxy or an error page answering with text.
      const blob =
        response.data instanceof Blob
          ? response.data
          : new Blob([response.data], {
              type: format === 'pdf' ? 'application/pdf' : 'text/csv',
            })
      const header = (response.headers as Record<string, unknown> | undefined)?.[
        'content-disposition'
      ]
      triggerDownload(
        blob,
        filenameFromDisposition(header, `teacher-statement-${teacherId}.${format}`),
      )
    } catch {
      toast.error(t('teacherPayments.details.exportFailed'))
    } finally {
      setExporting(null)
    }
  }

  // After the hooks, so the rules of hooks hold on every render — the card is
  // rendered for the whole life of the list, open or not.
  if (!isOpen) return null

  /** A period total: a dash rather than "0 DA", which reads as a figure. */
  const moneyOrDash = (amount: number) =>
    amount > 0 ? formatCurrency(amount) : t('common:dash')

  const groups = details?.groups ?? []
  const groupSessions = groups.reduce((sum, group) => sum + (group.session_count ?? 0), 0)

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={`${t('teacherPayments.details.title')} · ${teacherName}`}
      size="lg"
      footer={
        <button
          type="button"
          onClick={onClose}
          className={cn(
            'px-4 py-2 rounded-[var(--radius-sm)] text-sm font-medium',
            'text-[var(--muted)] bg-[var(--input-bg)] border border-[var(--glass-border)]',
            'hover:text-[var(--text)] transition-colors',
          )}
        >
          {t('teacherPayments.details.close')}
        </button>
      }
    >
      <div className="flex flex-col gap-5">
        {/* ── The period ── */}
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-[var(--muted)] uppercase tracking-wide">
            {t('teacherPayments.details.range.label')}
          </span>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setPreset(key)}
                aria-pressed={preset === key}
                className={cn(
                  'px-3 py-1.5 rounded-[var(--radius-sm)] text-xs font-semibold',
                  'border transition-all duration-150',
                  preset === key
                    ? 'bg-[var(--gold-soft)] border-[var(--gold)] text-[var(--gold)]'
                    : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)]',
                )}
              >
                {t(PRESET_LABEL_KEY[key])}
              </button>
            ))}
          </div>

          {/* Custom bounds, only while "custom" is the chosen period — a pair of
              date fields under "All time" would invite a value that does
              nothing. */}
          {preset === 'custom' && (
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1 text-[11px] font-medium text-[var(--muted)]">
                {t('teacherPayments.details.range.from')}
                <input
                  type="date"
                  value={customFrom}
                  onChange={(e) => setCustomFrom(e.target.value)}
                  className={cn(
                    'w-full px-3 py-2 rounded-[var(--radius-sm)]',
                    'text-sm text-[var(--text)] tabular-nums',
                    'bg-[var(--input-bg)] border border-[var(--glass-border)]',
                    'outline-none focus:border-[var(--gold)] focus:ring-1 focus:ring-[var(--gold)]/30',
                    'transition-colors',
                  )}
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] font-medium text-[var(--muted)]">
                {t('teacherPayments.details.range.to')}
                <input
                  type="date"
                  value={customTo}
                  onChange={(e) => setCustomTo(e.target.value)}
                  className={cn(
                    'w-full px-3 py-2 rounded-[var(--radius-sm)]',
                    'text-sm text-[var(--text)] tabular-nums',
                    'bg-[var(--input-bg)] border border-[var(--glass-border)]',
                    'outline-none focus:border-[var(--gold)] focus:ring-1 focus:ring-[var(--gold)]/30',
                    'transition-colors',
                  )}
                />
              </label>
            </div>
          )}

          {/* The span actually being fetched, so the two date fields above are
              never the only statement of it. */}
          <p className="text-xs text-[var(--muted)] tabular-nums">
            {describeRange(from, to)}
          </p>
        </div>

        {/* ── The report ── */}
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-[var(--muted)]">
            <div className="w-4 h-4 border-2 border-[var(--gold)] border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">{t('teacherPayments.details.loading')}</span>
          </div>
        ) : hasError ? (
          <div className="flex flex-col items-center gap-3 py-10">
            <p role="alert" className="text-sm font-semibold text-[var(--red)]">
              {t('teacherPayments.details.error')}
            </p>
            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)]',
                'text-xs font-semibold text-white',
                'bg-gradient-to-r from-[#b3872a] to-[#0f6b4d]',
                'hover:opacity-90 active:scale-[0.98] transition-all',
              )}
            >
              <RefreshCw size={13} />
              {t('common:action.retry')}
            </button>
          </div>
        ) : details ? (
          <>
            {/* ── Since when ──
                Shown only when the server says it is due (`due.is_due`), which
                is the same answer that put the row on the due list. The row can
                state this only in its tooltip — the line has no width for a
                phrase — so this is where the owner can actually read it. */}
            {details.due.is_due && (
              <div>
                <Badge
                  title={t('teacherPayments.due.title')}
                  className="border border-[var(--gold)] bg-[var(--gold-soft)] text-[var(--gold)]"
                >
                  {details.due.oldest_pending_date
                    ? t('teacherPayments.due.since', {
                        date: formatDateShort(details.due.oldest_pending_date),
                      })
                    : t('teacherPayments.due.badge')}
                </Badge>
              </div>
            )}

            {/* ── Totals ── */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3">
              <Figure
                label={t('teacherPayments.details.gross')}
                value={formatCurrency(details.gross_revenue_da)}
                strong
              />
              <Figure
                label={t('teacherPayments.details.cut')}
                value={formatCurrency(details.teacher_cut_da)}
                strong
              />
              <Figure
                label={t('teacherPayments.details.pending')}
                value={moneyOrDash(details.pending_da)}
                color="var(--gold)"
              />
              <Figure
                label={t('teacherPayments.details.paid')}
                value={moneyOrDash(details.paid_da)}
                color="var(--emerald)"
              />
              <Figure
                label={t('teacherPayments.details.sessions')}
                value={formatNumber(details.session_count)}
              />
              <Figure
                label={t('teacherPayments.details.students')}
                value={formatNumber(details.students_taught)}
              />
              {/* Deliberately a second figure, not the same one: "taught in this
                  window" and "on the roster today" are different questions and
                  the server reports both on purpose. The card has no dictionary
                  key of its own for the roster count, so it borrows the billing
                  namespace's "Total enrolled" — the label the billing overview
                  already uses for this exact quantity. */}
              <Figure
                label={t('kpi.totalEnrolled')}
                value={formatNumber(details.students_enrolled)}
              />
              <Figure
                label={t('teacherPayments.details.hours')}
                value={formatNumber(details.duration_hours)}
              />
              <Figure
                label={t('teacherPayments.details.averageRevenue')}
                value={formatCurrency(details.average_class_revenue_da)}
              />
              <Figure
                label={t('teacherPayments.details.average')}
                value={formatCurrency(details.average_cut_per_session_da)}
              />
              <Figure
                label={t('teacherPayments.details.manual')}
                value={formatNumber(details.manual_count)}
              />
              <Figure
                label={t('teacherPayments.details.groups')}
                value={formatNumber(details.group_count)}
              />
            </div>

            {/* ── When they are paid ── */}
            <div className="grid grid-cols-2 gap-4 border-t border-[var(--glass-border)]/50 pt-3">
              <Figure
                label={t('teacherPayments.details.cadence')}
                value={describeCadence(t, details.schedule)}
              />
              <Figure
                label={t('teacherPayments.details.next')}
                value={
                  details.schedule.next_payout_date
                    ? formatDateFull(details.schedule.next_payout_date)
                    : t('teacherPayments.details.nextNone')
                }
              />
            </div>

            {/* ── Per group ──
                The rows carry the same two quantities as the totals above
                (`teacher_cut_da` and `pending_da`), so the footer adds up to
                them. A breakdown in different units would be uncheckable. */}
            <div className="flex flex-col gap-2">
              <span className="text-xs font-medium text-[var(--muted)] uppercase tracking-wide">
                {t('teacherPayments.details.groupsTitle')}
              </span>
              {groups.length === 0 ? (
                <p className="text-xs text-[var(--muted)]">
                  {t('teacherPayments.details.noGroups')}
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--glass-border)]/50">
                      <th className="text-start px-2 py-2 text-[10px] uppercase tracking-wide font-medium text-[var(--muted)]">
                        {t('teacherPayments.details.groupName')}
                      </th>
                      <th className="text-end px-2 py-2 text-[10px] uppercase tracking-wide font-medium text-[var(--muted)]">
                        {t('teacherPayments.details.groupSessions')}
                      </th>
                      <th className="text-end px-2 py-2 text-[10px] uppercase tracking-wide font-medium text-[var(--muted)]">
                        {t('teacherPayments.details.groupTotal')}
                      </th>
                      <th className="text-end px-2 py-2 text-[10px] uppercase tracking-wide font-medium text-[var(--muted)]">
                        {t('teacherPayments.details.groupOwed')}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {groups.map((group) => (
                      <tr
                        key={group.group_id ?? 'unassigned'}
                        className="border-b border-[var(--glass-border)]/30 last:border-b-0"
                      >
                        <td className="px-2 py-2 text-[var(--text)]/85 truncate">
                          {group.group_name || t('teacherPayments.group.unnamed')}
                        </td>
                        <td className="px-2 py-2 text-end tabular-nums text-[var(--muted)]">
                          {formatNumber(group.session_count ?? 0)}
                        </td>
                        <td className="px-2 py-2 text-end tabular-nums font-medium text-[var(--text)]">
                          {formatCurrency(group.teacher_cut_da ?? 0)}
                        </td>
                        <td className="px-2 py-2 text-end tabular-nums text-[var(--gold)]">
                          {moneyOrDash(group.pending_da ?? 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-[var(--glass-border)]/50">
                      <td className="px-2 py-2 text-xs font-semibold text-[var(--muted)]">
                        {t('teacherPayments.group.total')}
                      </td>
                      <td className="px-2 py-2 text-end tabular-nums text-[var(--muted)]">
                        {formatNumber(groupSessions)}
                      </td>
                      <td className="px-2 py-2 text-end tabular-nums font-semibold text-[var(--text)]">
                        {formatCurrency(details.teacher_cut_da)}
                      </td>
                      <td className="px-2 py-2 text-end tabular-nums font-semibold text-[var(--gold)]">
                        {moneyOrDash(details.pending_da)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              )}
            </div>

            {/* ── Export ── */}
            <div className="flex flex-col gap-2 border-t border-[var(--glass-border)]/50 pt-3">
              <span className="text-xs font-medium text-[var(--muted)] uppercase tracking-wide">
                {t('teacherPayments.details.export')}
              </span>
              <div className="flex items-center gap-2">
                {(['csv', 'pdf'] as const).map((format) => {
                  const busy = exporting === format
                  const blocked = exporting !== null
                  return (
                    <button
                      key={format}
                      type="button"
                      onClick={() => void handleExport(format)}
                      disabled={blocked}
                      className={cn(
                        'flex items-center gap-2 px-3 py-2 rounded-[var(--radius-sm)]',
                        'text-xs font-semibold border transition-all duration-150',
                        blocked
                          ? 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)] cursor-not-allowed'
                          : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--text)] hover:border-[var(--gold)] hover:text-[var(--gold)]',
                      )}
                    >
                      {busy ? (
                        <div className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <Download size={14} />
                      )}
                      {format === 'csv'
                        ? t('teacherPayments.details.exportCsv')
                        : t('teacherPayments.details.exportPdf')}
                    </button>
                  )
                })}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </Modal>
  )
}

export default PayoutDetailsCard
