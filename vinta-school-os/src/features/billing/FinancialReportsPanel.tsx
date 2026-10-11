import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import { toast } from '../../stores/uiStore'
import { formatCurrency, formatNumber } from '../../lib/formatters'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { RefreshCw, TrendingUp, TrendingDown, Save, Percent, Archive } from 'lucide-react'
import { PaymentRecordsModal } from './PaymentRecordsModal'
import type { FinancialSummary } from '../../types/billing'

/* ─── Props ─── */

export interface FinancialReportsPanelProps {
  /** Bump to refetch — after a payment, payout or expense changes. */
  refreshKey?: number
  /** Raised after the split is saved, so the overview's own figures refresh. */
  onChanged?: () => void
  className?: string
}

/* ─── Chart tooltip ─── */

/* Lists every series at the hovered month. A component rather than the chart's
   `formatter` prop, matching the other billing charts. `entry.name` is the
   already-translated `name` given to each Bar/Line at render, so this stays a
   module-level function and follows a language switch. */
function ReportTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div
      className={cn(
        'rounded-[var(--radius-sm)] px-3 py-2',
        'bg-[var(--glass-strong)] backdrop-blur-md',
        'border border-[var(--glass-border)]',
        'shadow-lg text-sm',
      )}
    >
      <p className="text-[var(--muted)] text-xs mb-1.5">{label}</p>
      <div className="flex flex-col gap-1">
        {payload.map((entry: any) => (
          <div key={entry.dataKey} className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-[var(--muted)] text-xs">{entry.name}</span>
            <span className="ms-auto ps-4 font-semibold tabular-nums text-[var(--text)]">
              {formatCurrency(entry.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ─── One headline figure ─── */

function Figure({
  label,
  value,
  color,
  hint,
}: {
  label: string
  value: string
  color?: string
  hint?: string
}) {
  return (
    <Card>
      <CardBody>
        <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">{label}</span>
        <p
          className="text-lg font-bold tabular-nums font-[family-name:var(--font-heading)]"
          style={{ color: color ?? 'var(--text)' }}
        >
          {value}
        </p>
        {hint && <p className="text-[11px] text-[var(--muted)] mt-0.5">{hint}</p>}
      </CardBody>
    </Card>
  )
}

/* ─── Component ─── */

export function FinancialReportsPanel({
  refreshKey = 0,
  onChanged,
  className,
}: FinancialReportsPanelProps) {
  const { t } = useTranslation('billing')

  const [summary, setSummary] = useState<FinancialSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  // The split editor's draft, kept as text so a half-typed "3" is not coerced
  // to 3 and re-rendered under the owner's cursor.
  const [shareDraft, setShareDraft] = useState('')
  const [shareError, setShareError] = useState<string | null>(null)
  const [isSavingShare, setIsSavingShare] = useState(false)
  /* The payment-records archive, opened from the split card's header. */
  const [recordsOpen, setRecordsOpen] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const { data } = await api.get('/billing/financial-summary', { params: { months: 6 } })
      setSummary(data)
      setShareDraft(String(data?.teacher_share_percentage ?? 0))
    } catch (err: any) {
      // This panel is the one place net profit is stated, so a failure is
      // said out loud rather than rendered as a confident row of zeroes.
      setLoadError(
        err?.response?.status >= 500 ? 'reports.error.server' : 'reports.error.load',
      )
      setSummary(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  /* ── Split: the teacher's share; the school's is the remainder ──
   *
   * Only the teacher's number is ever stored, so the two shares cannot drift
   * apart or sum to something other than 100 (§7).
   */
  const parsedShare = useMemo(() => {
    const text = shareDraft.trim()
    if (!text) return null
    if (!/^\d+$/.test(text)) return null
    const value = Number(text)
    if (value < 0 || value > 100) return null
    return value
  }, [shareDraft])

  const schoolShare = parsedShare === null ? null : 100 - parsedShare

  const shareIsDirty = parsedShare !== null && parsedShare !== summary?.teacher_share_percentage

  const saveShare = async () => {
    const text = shareDraft.trim()
    if (!text || !/^\d+$/.test(text)) {
      setShareError(t('split.error.whole'))
      return
    }
    const value = Number(text)
    if (value < 0 || value > 100) {
      setShareError(t('split.error.range'))
      return
    }
    setIsSavingShare(true)
    try {
      await api.put('/settings/billing-config', { default_teacher_share_percentage: value })
      setSummary((prev) => (prev ? { ...prev, teacher_share_percentage: value } : prev))
      setShareError(null)
      toast.success(t('split.saved'))
      onChanged?.()
    } catch (err: any) {
      setShareError(err?.response?.data?.error || t('split.error.save'))
    } finally {
      setIsSavingShare(false)
    }
  }

  /* ── States ── */

  if (isLoading) {
    return (
      <div className={cn('flex items-center justify-center py-16', className)}>
        <div className="flex flex-col items-center gap-3 text-[var(--muted)]">
          <div className="w-6 h-6 border-2 border-[var(--gold)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">{t('reports.loading')}</span>
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className={cn('flex flex-col items-center justify-center py-16 gap-3', className)}>
        <p className="text-sm font-semibold text-[var(--red)]">{t(loadError)}</p>
        <Button size="sm" onClick={() => void load()}>
          <RefreshCw size={13} />
          {t('common:action.retry')}
        </Button>
      </div>
    )
  }

  const net = summary?.net_profit_da ?? 0
  const isProfit = net >= 0
  const series = summary?.series ?? []
  const hasAnySeries = series.some((p) => p.revenue || p.teacher_cost || p.expense)

  return (
    <div className={cn('flex flex-col gap-5', className)}>
      {/* ── Headline: net profit and its three terms (§12) ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Figure
          label={t('reports.kpi.revenue')}
          value={formatCurrency(summary?.revenue_total_da ?? 0)}
          color="var(--emerald)"
        />
        <Figure
          label={t('reports.kpi.teacherCost')}
          value={formatCurrency(summary?.teacher_cost_total_da ?? 0)}
          color="var(--gold)"
          hint={t('reports.kpi.teacherCostHint', {
            pending: formatCurrency(summary?.teacher_pending_da ?? 0),
          })}
        />
        <Figure
          label={t('reports.kpi.expenses')}
          value={formatCurrency(summary?.expenses_total_da ?? 0)}
          color="var(--red)"
        />
        <Card>
          <CardBody>
            <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
              {t('reports.kpi.net')}
            </span>
            <div className="flex items-center gap-1.5">
              {isProfit ? (
                <TrendingUp size={15} className="text-[var(--emerald)] shrink-0" />
              ) : (
                <TrendingDown size={15} className="text-[var(--red)] shrink-0" />
              )}
              <p
                className="text-lg font-bold tabular-nums font-[family-name:var(--font-heading)]"
                style={{ color: isProfit ? 'var(--emerald)' : 'var(--red)' }}
              >
                {formatCurrency(net)}
              </p>
            </div>
            {/* The subtraction is spelled out, so the figure is auditable
                rather than a number the owner has to trust. */}
            <p className="text-[11px] text-[var(--muted)] mt-0.5">
              {t('reports.kpi.netFormula')}
            </p>
          </CardBody>
        </Card>
      </div>

      {/* ── Monthly breakdown (§13) ── */}
      <Card>
        <CardHeader
          title={t('reports.chart.title')}
          actions={
            <button
              type="button"
              onClick={() => void load()}
              aria-label={t('common:action.retry')}
              className="flex items-center justify-center w-8 h-8 rounded-[var(--radius-xs)] bg-[var(--input-bg)] border border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)] transition-colors"
            >
              <RefreshCw size={13} />
            </button>
          }
        />
        <CardBody>
          <div className="h-[280px] w-full">
            {!hasAnySeries ? (
              <div className="flex flex-col items-center justify-center h-full gap-2">
                <p className="text-sm text-[var(--muted)]">{t('reports.chart.empty.title')}</p>
                <p className="text-xs text-[var(--muted)]/60">{t('reports.chart.empty.body')}</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={series} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--divider)" vertical={false} />
                  <XAxis
                    dataKey="month"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'var(--muted)', fontSize: 11 }}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'var(--muted)', fontSize: 12 }}
                    tickFormatter={(v: number) =>
                      Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)
                    }
                  />
                  <Tooltip content={<ReportTooltip />} cursor={{ fill: 'var(--glass)' }} />
                  <Legend
                    wrapperStyle={{ fontSize: 12, color: 'var(--muted)' }}
                    iconType="circle"
                  />
                  <Bar
                    dataKey="revenue"
                    name={t('reports.series.revenue')}
                    fill="#0f6b4d"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={22}
                  />
                  <Bar
                    dataKey="teacher_cost"
                    name={t('reports.series.teacherCost')}
                    fill="#b3872a"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={22}
                  />
                  <Bar
                    dataKey="expense"
                    name={t('reports.series.expense')}
                    fill="#b3452a"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={22}
                  />
                  {/* Net is a line, not a fourth bar: it is a residue of the
                      other three, not another quantity of money coming in. */}
                  <Line
                    type="monotone"
                    dataKey="net"
                    name={t('reports.series.net')}
                    stroke="#7c5cbf"
                    strokeWidth={2.5}
                    dot={{ r: 3, fill: '#7c5cbf' }}
                    activeDot={{ r: 5 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>
        </CardBody>
      </Card>

      {/* ── Teacher / school split (§7) ── */}
      <Card>
        <CardHeader
          title={t('split.title')}
          actions={
            /* Payment records sit behind the split because that is the question
               they answer: "the teacher got this share — of what, exactly?".
               Icon-only to keep the header quiet, with a real label for anyone
               who cannot see the icon. */
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setRecordsOpen(true)}
              aria-label={t('records.openArchive')}
              title={t('records.openArchive')}
            >
              <Archive size={14} />
            </Button>
          }
        />
        <CardBody>
          <div className="flex flex-col lg:flex-row lg:items-end gap-5">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-[var(--muted)] leading-relaxed">{t('split.description')}</p>

              <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg">
                <Input
                  label={t('split.teacherLabel')}
                  type="number"
                  min={0}
                  max={100}
                  value={shareDraft}
                  onChange={(e) => {
                    setShareDraft(e.target.value)
                    setShareError(null)
                  }}
                  leftIcon={<Percent size={15} />}
                  error={
                    shareError ??
                    (shareDraft.trim() !== '' && parsedShare === null
                      ? t('split.error.range')
                      : undefined)
                  }
                  helperText={t('split.teacherHint')}
                />

                {/* The school's share is shown, never entered: it is
                    100 − the teacher's, so it cannot be set to a value that
                    makes the two disagree. */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-[var(--muted)]">
                    {t('split.schoolLabel')}
                  </label>
                  <div className="flex items-center h-10 px-3 rounded-[var(--radius-sm)] bg-[var(--input-bg)] border border-[var(--glass-border)]">
                    <span className="text-sm font-semibold tabular-nums text-[var(--text)]">
                      {schoolShare === null ? t('common:dash') : `${formatNumber(schoolShare)}%`}
                    </span>
                    <span className="ms-auto text-[11px] text-[var(--muted)]">
                      {t('split.derived')}
                    </span>
                  </div>
                  <span className="text-[11px] text-[var(--muted)]">{t('split.schoolHint')}</span>
                </div>
              </div>
            </div>

            {/* Today's stored split, so a change is visible against its own
                starting point. */}
            <div className="flex flex-col items-start lg:items-end gap-3 shrink-0">
              <div className="text-start lg:text-end">
                <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
                  {t('split.current')}
                </span>
                <p className="text-sm font-semibold tabular-nums text-[var(--text)]">
                  {t('split.currentValue', {
                    teacher: formatNumber(summary?.teacher_share_percentage ?? 0),
                    school: formatNumber(100 - (summary?.teacher_share_percentage ?? 0)),
                  })}
                </p>
              </div>
              <Button
                size="sm"
                onClick={() => void saveShare()}
                loading={isSavingShare}
                disabled={!shareIsDirty || parsedShare === null}
              >
                <Save size={13} />
                {t('split.save')}
              </Button>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* ── Payment records archive ──
          Every money record ever recorded for this academy: student payments,
          teacher payouts (manual ones with their notes) and school expenses. */}
      <PaymentRecordsModal open={recordsOpen} onClose={() => setRecordsOpen(false)} />
    </div>
  )
}

export default FinancialReportsPanel
