import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import { Modal } from '../../components/ui/Modal'
import { formatCurrency } from '../../lib/formatters'
import { formatDateISO } from '../../lib/formatters'
import { BillingRecordFilters } from './BillingRecordFilters'
import BillingExportModal from './BillingExportModal'
import {
  EMPTY_FILTERS,
  activeFilterCount,
  toParams,
} from './recordFilterState'
import type {
  BillingRecord,
  BillingRecordFilters as Filters,
  BillingRecordsResponse,
} from '../../types/billing'
import {
  ArrowDownLeft,
  ArrowUpRight,
  Download,
  ListFilter,
  RefreshCw,
  X,
} from 'lucide-react'

/* ─── Payment records — the archive ───
 *
 * Every money record the academy has ever recorded: student payments, teacher
 * payouts (including the ones entered by hand, with their notes) and school
 * expenses, in one date-sorted list.
 *
 * Laid out as rows rather than a nine-column table because the Modal caps at
 * 600px: a table that wide would either scroll horizontally — bad on a laptop
 * trackpad and worse on a phone — or crush the note, which is the one column a
 * reader actually needs to read. Two lines per row fit without either.
 *
 * The list is capped on screen. An academy can hold thousands of records and
 * rendering them all would lock the browser up for a file nobody is going to
 * read row by row; the honest thing is to say how many are shown and point at
 * the export for the rest. */

/** How many rows are rendered before the list says "showing N of M". */
const RENDER_CAP = 200

/* ─── Type styling ─── */

const KIND_STYLE: Record<
  BillingRecord['kind'],
  { bg: string; fg: string; labelKey: string }
> = {
  STUDENT_PAYMENT: { bg: 'var(--emerald-soft)', fg: 'var(--emerald)', labelKey: 'records.type.studentPayment' },
  TEACHER_PAYOUT: { bg: 'var(--gold-soft)', fg: 'var(--gold)', labelKey: 'records.type.teacherPayout' },
  EXPENSE: { bg: 'var(--red-soft)', fg: 'var(--red)', labelKey: 'records.type.expense' },
}

interface PaymentRecordsModalProps {
  open: boolean
  onClose: () => void
}

export function PaymentRecordsModal({ open, onClose }: PaymentRecordsModalProps) {
  const { t } = useTranslation('billing')

  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [data, setData] = useState<BillingRecordsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  /* Held as a translation key rather than as translated text, so the fetching
     effect below does not have to depend on `t`. FinancialReportsPanel in this
     same folder does the same. A dependency on `t` would re-run the fetch every
     time the language changes — and, if `t` were ever unstable per render, would
     turn this into a refetch loop. */
  const [errorKey, setErrorKey] = useState<string | null>(null)
  const [showFilters, setShowFilters] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)

  /* ── Load on open, and again whenever a filter changes ──
   *
   * The whole filter object is a dependency rather than a debounced copy:
   * every field here is a discrete choice (a picked date, a picked profile, a
   * chosen type) or a number the user types. Re-running the merge per keystroke
   * on the amount boxes is a real cost, so those are debounced below. */
  const [debounced, setDebounced] = useState<Filters>(EMPTY_FILTERS)
  useEffect(() => {
    const handle = setTimeout(() => setDebounced(filters), 250)
    return () => clearTimeout(handle)
  }, [filters])

  useEffect(() => {
    if (!open) return
    let cancelled = false

    async function load() {
      setLoading(true)
      setErrorKey(null)
      try {
        const { data: payload } = await api.get('/billing/records', {
          params: toParams(debounced),
        })
        if (!cancelled) setData(payload)
      } catch {
        if (!cancelled) {
          setErrorKey('records.error.load')
          setData(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => { cancelled = true }
  }, [open, debounced])

  /* Reset on close so the next open starts from "everything", not from
     whatever the last visit happened to be filtering by. */
  useEffect(() => {
    if (!open) {
      setFilters(EMPTY_FILTERS)
      setShowFilters(false)
      setExportOpen(false)
      setErrorKey(null)
    }
  }, [open])

  const records = data?.records ?? []
  const shown = records.slice(0, RENDER_CAP)
  const filterCount = activeFilterCount(filters)

  return (
    <>
      <Modal open={open} onClose={onClose} title={t('records.title')} size="lg">
        <div className="flex flex-col gap-4">
          <p className="text-sm text-[var(--muted)]">{t('records.subtitle')}</p>

          {/* ── Controls ── */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowFilters((v) => !v)}
              aria-expanded={showFilters}
              className={cn(
                'inline-flex items-center gap-2 px-3 py-2 rounded-[var(--radius-sm)]',
                'text-xs font-medium border transition-colors',
                showFilters || filterCount > 0
                  ? 'bg-[var(--gold-soft)] border-[var(--gold)] text-[var(--gold)]'
                  : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)]',
              )}
            >
              <ListFilter className="w-3.5 h-3.5" />
              {t('records.filters.toggle')}
              {filterCount > 0 && (
                <span className="inline-flex items-center justify-center min-w-[1.15rem] h-[1.15rem] px-1 rounded-full bg-[var(--gold)] text-white text-[10px] font-bold tabular-nums">
                  {filterCount}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setExportOpen(true)}
              className={cn(
                'inline-flex items-center gap-2 px-3 py-2 ms-auto rounded-[var(--radius-sm)]',
                'text-xs font-semibold transition-colors',
                'bg-gradient-to-r from-[var(--gold)] to-[var(--gold-dark, #9a7520)]',
                'text-white shadow-[0_4px_20px_rgba(179,135,42,.3)]',
                'hover:shadow-[0_6px_28px_rgba(179,135,42,.5)]',
              )}
            >
              <Download className="w-3.5 h-3.5" />
              {t('records.export')}
            </button>
          </div>

          {showFilters && (
            <div className="rounded-[var(--radius-sm)] border border-[var(--glass-border)] bg-[var(--input-bg)]/40 p-3">
              <BillingRecordFilters filters={filters} onChange={setFilters} compact />
            </div>
          )}

          {/* ── Totals ── */}
          {data && (
            <div className="grid grid-cols-3 gap-2">
              {(
                [
                  { key: 'in', value: data.totals.money_in_da, tone: 'var(--emerald)' },
                  { key: 'out', value: data.totals.money_out_da, tone: 'var(--red)' },
                  { key: 'net', value: data.totals.net_da, tone: data.totals.net_da >= 0 ? 'var(--text)' : 'var(--red)' },
                ] as const
              ).map(({ key, value, tone }) => (
                <div
                  key={key}
                  className="flex flex-col gap-0.5 px-3 py-2 rounded-[var(--radius-sm)] bg-[var(--input-bg)] border border-[var(--glass-border)]"
                >
                  <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
                    {t(`records.totals.${key}`)}
                  </span>
                  <span
                    className="text-sm font-bold tabular-nums font-[family-name:var(--font-heading)]"
                    style={{ color: tone }}
                  >
                    {formatCurrency(value)}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* ── Rows ── */}
          <div className="flex flex-col gap-2 max-h-[46vh] overflow-y-auto -mx-1 px-1">
            {loading && !data && (
              <div className="flex items-center justify-center gap-2 py-10 text-[var(--muted)]">
                <div className="w-4 h-4 border-2 border-[var(--gold)] border-t-transparent rounded-full animate-spin" />
                <span className="text-sm">{t('records.loading')}</span>
              </div>
            )}

            {errorKey && (
              <div className="flex flex-col items-center gap-2 py-10 text-center">
                <p role="alert" className="text-sm text-[var(--red)]">{t(errorKey)}</p>
                <button
                  type="button"
                  onClick={() => setDebounced({ ...debounced })}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--gold)] hover:underline"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  {t('records.retry')}
                </button>
              </div>
            )}

            {!loading && !errorKey && records.length === 0 && (
              <div className="flex flex-col items-center gap-1 py-10 text-center">
                <p className="text-sm font-semibold text-[var(--text)]">
                  {t('records.empty.title')}
                </p>
                <p className="text-xs text-[var(--muted)]">{t('records.empty.body')}</p>
              </div>
            )}

            {shown.map((record) => {
              const style = KIND_STYLE[record.kind] ?? KIND_STYLE.EXPENSE
              const isIn = record.direction === 'IN'
              return (
                <div
                  key={`${record.kind}-${record.id}`}
                  className="flex flex-col gap-1 px-3 py-2.5 rounded-[var(--radius-sm)] bg-[var(--input-bg)] border border-[var(--glass-border)]"
                >
                  <div className="flex items-center gap-2">
                    {/* Direction is carried by an arrow as well as the sign, so
                        it survives a glance and does not depend on colour. */}
                    <span
                      className="shrink-0 flex items-center justify-center w-6 h-6 rounded-full"
                      style={{ backgroundColor: style.bg, color: isIn ? 'var(--emerald)' : style.fg }}
                    >
                      {isIn ? <ArrowDownLeft className="w-3.5 h-3.5" /> : <ArrowUpRight className="w-3.5 h-3.5" />}
                    </span>

                    <span className="text-xs text-[var(--muted)] tabular-nums shrink-0">
                      {record.date ? formatDateISO(record.date) : t('records.noDate')}
                    </span>

                    <span
                      className="shrink-0 px-1.5 py-0.5 rounded-full text-[10px] font-medium"
                      style={{ backgroundColor: style.bg, color: style.fg }}
                    >
                      {t(style.labelKey)}
                    </span>

                    <span
                      className={cn(
                        'ms-auto shrink-0 text-sm font-bold tabular-nums font-[family-name:var(--font-heading)]',
                      )}
                      style={{ color: isIn ? 'var(--emerald)' : 'var(--text)' }}
                    >
                      {isIn ? '+' : '−'}{formatCurrency(record.amount_da)}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap ps-8">
                    <span className="text-xs font-medium text-[var(--text)]">
                      {record.profile_name || t('records.noProfile')}
                    </span>

                    {record.label && (
                      <span className="text-xs text-[var(--muted)] truncate">· {record.label}</span>
                    )}

                    {/* A hand-recorded payout is flagged: it is the one row the
                        owner cannot reconstruct from the session log. */}
                    {record.source === 'MANUAL' && (
                      <span className="px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-[var(--gold-soft)] text-[var(--gold)]">
                        {t('records.source.manual')}
                      </span>
                    )}

                    {record.status && (
                      <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
                        {record.status}
                      </span>
                    )}
                  </div>

                  {record.notes && (
                    <p className="text-[11px] text-[var(--muted)] ps-8 break-words">
                      {record.notes}
                    </p>
                  )}
                </div>
              )
            })}

            {records.length > RENDER_CAP && (
              <p className="text-[11px] text-[var(--muted)] text-center py-2">
                {t('records.showing', { shown: RENDER_CAP, total: records.length })}
              </p>
            )}
          </div>

          {data && records.length > 0 && records.length <= RENDER_CAP && (
            <p className="text-[11px] text-[var(--muted)] text-center">
              {t('records.count', { count: records.length })}
            </p>
          )}

          {/* ── Close ── */}
          <button
            type="button"
            onClick={onClose}
            className={cn(
              'w-full flex items-center justify-center gap-2 py-2.5 rounded-[var(--radius-sm)]',
              'text-sm font-medium text-[var(--muted)]',
              'bg-[var(--input-bg)] border border-[var(--glass-border)]',
              'hover:text-[var(--text)] transition-colors',
            )}
          >
            <X className="w-3.5 h-3.5" />
            {t('records.close')}
          </button>
        </div>
      </Modal>

      {/* The export carries the on-screen filters through, so "Export" from a
          filtered archive downloads the rows the user is looking at. */}
      <BillingExportModal
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        initialFilters={filters}
      />
    </>
  )
}

export default PaymentRecordsModal
