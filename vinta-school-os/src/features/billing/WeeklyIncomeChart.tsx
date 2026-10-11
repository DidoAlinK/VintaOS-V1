import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import { formatCurrency } from '../../lib/formatters'
import { Card, CardHeader, CardBody } from '../../components/ui/Card'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from 'recharts'
import { RefreshCw } from 'lucide-react'

/* ─── Types ─── */

/** One bucket as the server sends it — see `IncomePoint` in types/billing.ts. */
interface IncomePoint {
  label: string
  income: number
  has_data: boolean
  week_start?: string
  week_end?: string
}

type Period = 'weekly' | 'monthly'

/* ─── Props ─── */

export interface WeeklyIncomeChartProps {
  /**
   * Bump to force a refetch. The parent raises it after a payment is added,
   * confirmed or cancelled, which is what keeps the chart honest without a
   * page reload (§9).
   */
  refreshKey?: number
  className?: string
}

/* ─── Tooltip ─── */

function IncomeTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload as IncomePoint & { drawn: number | null }
  return (
    <div
      className={cn(
        'rounded-[var(--radius-sm)] px-3 py-2',
        'bg-[var(--glass-strong)] backdrop-blur-md',
        'border border-[var(--glass-border)]',
        'shadow-lg text-sm',
      )}
    >
      <p className="text-[var(--muted)] text-xs mb-1">{point.label}</p>
      {/* A bucket with no history is named as such rather than shown as 0 DA —
          the two mean different things and only one of them is a fact about
          money. */}
      <p className="font-semibold text-[var(--text)] font-[family-name:var(--font-heading)] tabular-nums">
        {point.drawn === null ? '—' : formatCurrency(point.income)}
      </p>
    </div>
  )
}

/* ─── Component ─── */

export function WeeklyIncomeChart({ refreshKey = 0, className }: WeeklyIncomeChartProps) {
  const { t } = useTranslation('billing')
  const [period, setPeriod] = useState<Period>('weekly')
  const [points, setPoints] = useState<IncomePoint[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const { data } = await api.get('/billing/income-chart', {
        params: { period, buckets: period === 'weekly' ? 12 : 6 },
      })
      setPoints(data.points ?? [])
    } catch {
      // Never silent: the card says it could not load and offers Retry.
      setLoadError('income.error.load')
      setPoints([])
    } finally {
      setIsLoading(false)
    }
  }, [period])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  /* Weeks before the academy's first payment carry `has_data: false`. They are
     drawn as gaps (a null dataKey) rather than as zero bars, because a row of
     zeroes reads as "we earned nothing that week" — a claim the server never
     made. */
  const chartData = points.map((p) => ({
    ...p,
    drawn: p.has_data ? p.income : null,
  }))

  const hasAnyData = points.some((p) => p.has_data)

  return (
    <Card className={className}>
      <CardHeader
        title={t('income.title')}
        actions={
          <div className="flex items-center gap-2">
            {/* Period switch — weekly is the brief's default (§9). */}
            <div className="flex items-center gap-1 p-0.5 rounded-[var(--radius-xs)] bg-[var(--input-bg)] border border-[var(--glass-border)]">
              {(['weekly', 'monthly'] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPeriod(p)}
                  className={cn(
                    'px-2.5 py-1 text-xs font-medium rounded-[var(--radius-xs)] transition-colors',
                    period === p
                      ? 'bg-[var(--glass-strong)] text-[var(--text)] shadow-sm'
                      : 'text-[var(--muted)] hover:text-[var(--text)]',
                  )}
                >
                  {t(`income.period.${p}`)}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => void load()}
              disabled={isLoading}
              aria-label={t('common:action.retry')}
              className="flex items-center justify-center w-8 h-8 rounded-[var(--radius-xs)] bg-[var(--input-bg)] border border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)] transition-colors disabled:opacity-50"
            >
              <RefreshCw size={13} className={cn(isLoading && 'animate-spin')} />
            </button>
          </div>
        }
      />

      <CardBody>
        <div className="h-[240px] w-full">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="w-6 h-6 border-2 border-[var(--gold)] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : loadError ? (
            <div className="flex flex-col items-center justify-center h-full gap-3">
              <p className="text-sm font-semibold text-[var(--red)]">{t(loadError)}</p>
              <button
                type="button"
                onClick={() => void load()}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-white bg-gradient-to-r from-[#b3872a] to-[#0f6b4d] hover:opacity-90 active:scale-[0.98] transition-all"
              >
                <RefreshCw size={13} />
                {t('common:action.retry')}
              </button>
            </div>
          ) : !hasAnyData ? (
            <div className="flex flex-col items-center justify-center h-full gap-2">
              <div className="w-16 h-16 rounded-full bg-[var(--input-bg)] flex items-center justify-center">
                <div className="w-8 h-8 rounded-full border-2 border-dashed border-[var(--muted)]/30" />
              </div>
              <p className="text-sm text-[var(--muted)]">{t('income.empty.title')}</p>
              <p className="text-xs text-[var(--muted)]/60">{t('income.empty.body')}</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <defs>
                  <linearGradient id="incomeBarGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#b3872a" stopOpacity={0.95} />
                    <stop offset="100%" stopColor="#b3872a" stopOpacity={0.45} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--divider)" vertical={false} />
                <XAxis
                  dataKey="label"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: 'var(--muted)', fontSize: 11 }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: 'var(--muted)', fontSize: 12 }}
                  tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v))}
                />
                <Tooltip content={<IncomeTooltip />} cursor={{ fill: 'var(--glass)' }} />
                <Bar dataKey="drawn" radius={[4, 4, 0, 0]} maxBarSize={44}>
                  {chartData.map((entry, i) => (
                    <Cell
                      key={i}
                      /* The most recent bucket is the live one, so it is drawn
                         in gold; settled weeks are muted so the eye lands on
                         "this week" without a legend. */
                      fill={i === chartData.length - 1 ? '#b3872a' : 'url(#incomeBarGradient)'}
                      opacity={entry.drawn === null ? 0 : 1}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardBody>
    </Card>
  )
}

export default WeeklyIncomeChart
