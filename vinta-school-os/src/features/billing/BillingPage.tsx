import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import { Toggle } from '../../components/ui/Toggle'
import { useAuthStore } from '../../stores/authStore'
import { isGrossProfitEnabled, setGrossProfitEnabled } from '../../lib/grossProfit'
import { formatCurrency, formatNumber } from '../../lib/formatters'
import type { BillingStats, RevenueDataPoint, BillingRingData } from '../../types/billing'
import { Card, CardBody } from '../../components/ui/Card'
import DonutCards from './DonutCards'
import RevenueChart from './RevenueChart'
import WeeklyIncomeChart from './WeeklyIncomeChart'
import FinanceBreakdown from './FinanceBreakdown'
import SubscriptionsPanel from './SubscriptionsPanel'
import TeacherPayments from './TeacherPayments'
import PayoutDashboard from './PayoutDashboard'
import SchoolExpensesPanel from './SchoolExpensesPanel'
import FinancialReportsPanel from './FinancialReportsPanel'
import MultiPayModal from './MultiPayModal'
import AddPayoutModal from './AddPayoutModal'
import {
  TrendingUp,
  Users,
  Receipt,
  Banknote,
  CreditCard,
  Wallet,
  HandCoins,
  LayoutDashboard,
  ShieldAlert,
} from 'lucide-react'

/* ─── Tab config (§17) ───
 *
 * Five sections, one per question the owner opens Billing to ask: what is the
 * state of the school, what did students pay, what do teachers earn, what did
 * the school spend, and what is left. The old Subscription/Payout pair was
 * replaced rather than kept alongside: both labels named a *mechanism*, and the
 * tabs now name the *thing being looked at*, with the mechanism living inside
 * the relevant one.
 *
 * Keys, not sentences: this array is built once at import, in whatever language
 * happened to be active then, so it holds the key and the render body looks it
 * up — a translated label here would survive a language switch untouched. */
type BillingTab = 'overview' | 'students' | 'teachers' | 'expenses' | 'reports'

const TABS: { key: BillingTab; labelKey: string; icon: React.ElementType }[] = [
  { key: 'overview', labelKey: 'tabs.overview', icon: LayoutDashboard },
  { key: 'students', labelKey: 'tabs.students', icon: CreditCard },
  { key: 'teachers', labelKey: 'tabs.teachers', icon: Wallet },
  { key: 'expenses', labelKey: 'tabs.expenses', icon: Receipt },
  { key: 'reports', labelKey: 'tabs.reports', icon: TrendingUp },
]

/* ─── Component ─── */

export function BillingPage() {
  const { t } = useTranslation('billing')
  const user = useAuthStore((s) => s.user)

  const [stats, setStats] = useState<BillingStats | null>(null)
  const [revenueData, setRevenueData] = useState<RevenueDataPoint[]>([])
  const [revenueProperty, setRevenueProperty] = useState('income')
  const [isLoading, setIsLoading] = useState(true)
  const [breakdownOpen, setBreakdownOpen] = useState(false)
  const [breakdownType, setBreakdownType] = useState<'students' | 'teachers'>('students')

  const [activeTab, setActiveTab] = useState<BillingTab>('overview')
  const [multiPayOpen, setMultiPayOpen] = useState(false)
  const [addPayoutOpen, setAddPayoutOpen] = useState(false)
  /* ── Gross-profit opt-in (academy-level, frontend registry) ── */
  const [grossOn, setGrossOn] = useState(() => isGrossProfitEnabled())

  /* One counter for "money changed somewhere in this section". Every panel that
   * reads money takes it as `refreshKey`, so recording a payment, confirming a
   * payout, adding an expense or saving the split updates the others without a
   * page reload — which is what keeps the charts honest (§9). */
  const [dataVersion, setDataVersion] = useState(0)
  const notifyChanged = useCallback(() => setDataVersion((v) => v + 1), [])

  /* ── Fetch summary figures ──
   *
   * Both come from owner-gated billing endpoints. `/analytics/revenue-chart`
   * was the old source and is a staff-visible surface — it could not be the
   * backing for a section staff cannot open, and it only ever returned income.
   *
   * The response is one payload per month carrying every property the chart
   * offers, so switching property re-reads the same rows and needs no refetch. */
  useEffect(() => {
    let cancelled = false

    async function load() {
      setIsLoading(true)
      try {
        const [statsRes, revenueRes] = await Promise.all([
          api.get('/billing/stats'),
          api.get('/billing/revenue-chart', { params: { months: 6 } }),
        ])
        if (!cancelled) {
          setStats(statsRes.data)
          setRevenueData(revenueRes.data.chart_data ?? [])
        }
      } catch {
        // The rings and tiles render their own empty state; a partially
        // unavailable section is still navigable.
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [dataVersion])

  /* ── Permissions (§15) ──
   *
   * The sidebar already hides Billing from staff and every summary endpoint is
   * @owner_only, so a staff session that reaches this URL by typing it would
   * otherwise render the whole page and then fail every request. Saying so once
   * is clearer than a dozen red banners, and it weakens nothing: the API is
   * still the thing that decides. */
  if (user?.role === 'staff') {
    return (
      <div className="flex items-center justify-center h-full p-4">
        <Card className="max-w-md">
          <CardBody>
            <div className="flex flex-col items-center text-center gap-3 py-4">
              <div
                className="flex items-center justify-center w-12 h-12 rounded-full"
                style={{ backgroundColor: 'var(--red-soft)', color: 'var(--red)' }}
              >
                <ShieldAlert className="w-6 h-6" />
              </div>
              <h2 className="text-base font-bold text-[var(--text)] font-[family-name:var(--font-heading)]">
                {t('page.ownerOnly.title')}
              </h2>
              <p className="text-sm text-[var(--muted)]">{t('page.ownerOnly.body')}</p>
              <Link
                to="/app/dashboard"
                className="mt-1 inline-flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] text-sm font-semibold text-white bg-gradient-to-r from-[var(--gold)] to-[var(--gold-dark, #9a7520)] hover:opacity-90 transition-opacity"
              >
                {t('page.ownerOnly.back')}
              </Link>
            </div>
          </CardBody>
        </Card>
      </div>
    )
  }

  /* ── Derived data ── */
  const studentRing: BillingRingData[] = stats
    ? [
        { name: t('donut.paid'), value: stats.student_paid, color: 'var(--emerald)' },
        { name: t('donut.due'), value: stats.student_due, color: 'var(--gold)' },
        { name: t('donut.overdue'), value: stats.student_overdue, color: 'var(--red)' },
      ]
    : []

  const teacherRing: BillingRingData[] = stats
    ? [
        { name: t('donut.settled'), value: stats.teacher_settled, color: 'var(--emerald)' },
        { name: t('donut.pending'), value: stats.teacher_pending, color: 'var(--gold)' },
        { name: t('donut.overdue'), value: stats.teacher_overdue, color: 'var(--red)' },
      ]
    : []

  /* ── Handlers ── */
  const handleOpenBreakdown = (type: 'students' | 'teachers') => {
    setBreakdownType(type)
    setBreakdownOpen(true)
  }

  /* ── Render ── */
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3 text-[var(--muted)]">
          <div className="w-8 h-8 border-2 border-[var(--gold)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">{t('page.loading')}</span>
        </div>
      </div>
    )
  }

  return (
    /* The single scroll container for this page is `<main>` in AppShell. This
       root deliberately has no `h-full` and no `overflow-y-auto` of its own.

       It used to have both, and that was the Overview-clipping bug: `h-full`
       pinned the page to exactly `<main>`'s height, the tabs card below ends in
       `overflow-hidden` (so as a flex item its automatic minimum size resolves
       to 0 and it gets *squeezed* rather than overflowing), and the Overview
       panel inside had no scroll region of its own. Content past the fold was
       simply cut off with no scrollbar that could reach it. Growing to content
       height hands the whole page back to the one scroller. */
    <div className="flex flex-col gap-5 p-4">
      {/* ── Header with the two money-in / money-out actions ──────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[var(--text)] font-[family-name:var(--font-heading)]">
            {t('page.title')}
          </h1>
          <p className="text-xs text-[var(--muted)] mt-0.5">
            {t('page.subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Record a teacher payout by hand — the complement to Multi-Pay.
              Multi-Pay is money in (a student pays); this is money out (the
              academy pays a teacher), and until now there was no way to write
              one down at all. */}
          <button
            type="button"
            onClick={() => setAddPayoutOpen(true)}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2.5 rounded-[var(--radius-sm)]',
              'text-sm font-semibold',
              'bg-[var(--glass-strong)] backdrop-blur-[22px]',
              'border border-[var(--glass-border)]',
              'text-[var(--text)]',
              'hover:border-[var(--gold)]/40 hover:scale-[1.02]',
              'active:scale-[0.98]',
              'transition-all duration-200',
            )}
          >
            <HandCoins className="w-4 h-4" />
            {t('page.addPayout')}
          </button>

          {/* Multi-student payment button */}
          <button
            type="button"
            onClick={() => setMultiPayOpen(true)}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2.5 rounded-[var(--radius-sm)]',
              'text-sm font-semibold',
              'bg-gradient-to-r from-[var(--gold)] to-[var(--gold-dark, #9a7520)]',
              'text-white',
              'shadow-[0_4px_20px_rgba(179,135,42,.3)]',
              'hover:shadow-[0_6px_28px_rgba(179,135,42,.5)]',
              'hover:scale-[1.02]',
              'active:scale-[0.98]',
              'transition-all duration-200',
            )}
          >
            <Banknote className="w-4 h-4" />
            {t('page.multiPay')}
          </button>
        </div>
      </div>

      {/* ── Section tabs (§17) ─── */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--glass)] backdrop-blur-[22px] shadow-[var(--glass-shadow)] overflow-hidden">
        <div className="flex items-center border-b border-[var(--glass-border)] overflow-x-auto">
          {TABS.map(({ key, labelKey, icon: Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveTab(key)}
              aria-current={activeTab === key ? 'page' : undefined}
              className={cn(
                'relative flex items-center gap-2 px-5 py-3.5 text-sm font-medium shrink-0',
                'transition-colors duration-150 whitespace-nowrap',
                activeTab === key
                  ? 'text-[var(--gold)]'
                  : 'text-[var(--muted)] hover:text-[var(--text)]',
              )}
            >
              <Icon className="w-4 h-4" />
              {t(labelKey)}
              {/* Gold underline for active tab */}
              {activeTab === key && (
                <span className="absolute bottom-0 start-0 end-0 h-[2px] bg-[var(--gold)] rounded-full" />
              )}
            </button>
          ))}
        </div>

        <div className="p-4">
          {/* ── Overview ───────────────────────────────── */}
          {activeTab === 'overview' && (
            <div className="flex flex-col gap-5">
              {/* Donut ring cards — each centre figure is a count of unique
                  students / teachers, and the segments partition it. */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div
                  className="cursor-pointer hover:scale-[1.01] transition-transform"
                  onClick={() => handleOpenBreakdown('students')}
                >
                  <DonutCards
                    title={t('donut.studentTuition')}
                    data={studentRing}
                    centerLabel={t('common:label.total')}
                    centerValue={formatNumber(stats?.student_total ?? 0)}
                  />
                </div>
                <div
                  className="cursor-pointer hover:scale-[1.01] transition-transform"
                  onClick={() => handleOpenBreakdown('teachers')}
                >
                  <DonutCards
                    title={t('donut.teacherPayroll')}
                    data={teacherRing}
                    centerLabel={t('common:label.total')}
                    centerValue={formatNumber(stats?.teacher_total ?? 0)}
                  />
                </div>
              </div>

              {/* Stat tiles + breakdown */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Card>
                  <CardBody>
                    <div className="flex items-center gap-3">
                      <div
                        className="flex items-center justify-center w-10 h-10 rounded-[var(--radius-sm)] shrink-0"
                        style={{ backgroundColor: 'var(--emerald-soft)', color: 'var(--emerald)' }}
                      >
                        <TrendingUp className="w-5 h-5" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="text-xs text-[var(--muted)] font-medium">
                          {t('kpi.monthIncome')}
                        </span>
                        <span className="text-lg font-bold text-[var(--text)] font-[family-name:var(--font-heading)] tabular-nums">
                          {formatCurrency(stats?.month_income ?? 0)}
                        </span>
                      </div>
                    </div>
                  </CardBody>
                </Card>

                <Card>
                  <CardBody>
                    <div className="flex items-center gap-3">
                      <div
                        className="flex items-center justify-center w-10 h-10 rounded-[var(--radius-sm)] shrink-0"
                        style={{ backgroundColor: 'var(--gold-soft)', color: 'var(--gold)' }}
                      >
                        <Users className="w-5 h-5" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="text-xs text-[var(--muted)] font-medium">
                          {t('kpi.totalEnrolled')}
                        </span>
                        <span className="text-lg font-bold text-[var(--text)] font-[family-name:var(--font-heading)] tabular-nums">
                          {formatNumber(stats?.total_enrolled ?? 0)}
                        </span>
                      </div>
                    </div>
                  </CardBody>
                </Card>

                {/* Finance breakdown button */}
                <button
                  type="button"
                  onClick={() => handleOpenBreakdown('students')}
                  className={cn(
                    'flex items-center gap-3 p-4 rounded-[var(--radius-md)] text-start',
                    'bg-[var(--glass)] backdrop-blur-[22px]',
                    'border border-[var(--glass-border)]',
                    'hover:bg-[var(--glass-strong)] hover:scale-[1.01]',
                    'transition-all duration-200',
                  )}
                >
                  <div
                    className="flex items-center justify-center w-10 h-10 rounded-[var(--radius-sm)] shrink-0"
                    style={{ backgroundColor: 'var(--red-soft)', color: 'var(--red)' }}
                  >
                    <Receipt className="w-5 h-5" />
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs text-[var(--muted)] font-medium">
                      {t('kpi.financeBreakdown')}
                    </span>
                    <span className="text-sm font-semibold text-[var(--text)] font-[family-name:var(--font-heading)]">
                      {t('kpi.viewDetails')}
                    </span>
                  </div>
                </button>
              </div>

              {/* Weekly income (§9) — real payment rows, bucketed by week. */}
              <WeeklyIncomeChart refreshKey={dataVersion} />

              {/* Monthly revenue (§10) */}
              <RevenueChart
                data={revenueData}
                property={revenueProperty}
                onPropertyChange={setRevenueProperty}
              />

              {/* Gross-profit opt-in */}
              <div className="flex items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--glass)] backdrop-blur-[22px] px-4 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[var(--text)]">{t('grossProfit.label')}</p>
                  <p className="text-xs text-[var(--muted)] mt-0.5">
                    {grossOn ? t('grossProfit.on') : t('grossProfit.off')}
                  </p>
                </div>
                <Toggle
                  checked={grossOn}
                  onCheckedChange={(v) => { setGrossProfitEnabled(v); setGrossOn(v) }}
                />
              </div>
            </div>
          )}

          {/* ── Student Payments ───────────────────────── */}
          {activeTab === 'students' && <SubscriptionsPanel refreshKey={dataVersion} />}

          {/* ── Teacher Payments ───────────────────────── */}
          {activeTab === 'teachers' && (
            <div className="flex flex-col gap-6">
              {/* What is owed, per teacher, across all their groups (§5, §6). */}
              <TeacherPayments refreshKey={dataVersion} />

              {/* The confirmation mechanism itself (§5): settling a pending
                  payout moves it from owed to settled in the figures above. */}
              <div className="border-t border-[var(--glass-border)] pt-5">
                <p className="text-sm font-semibold text-[var(--text)] mb-1">
                  {t('payouts.sectionTitle')}
                </p>
                <p className="text-xs text-[var(--muted)] mb-4">{t('payouts.sectionHint')}</p>
                <PayoutDashboard refreshKey={dataVersion} onChanged={notifyChanged} />
              </div>
            </div>
          )}

          {/* ── School Expenses (§11, §13) ─────────────── */}
          {activeTab === 'expenses' && (
            <SchoolExpensesPanel refreshKey={dataVersion} onChanged={notifyChanged} />
          )}

          {/* ── Financial Reports (§7, §12, §13) ───────── */}
          {activeTab === 'reports' && (
            <FinancialReportsPanel refreshKey={dataVersion} onChanged={notifyChanged} />
          )}
        </div>
      </div>

      {/* ── Finance breakdown modal ────────────── */}
      <FinanceBreakdown
        isOpen={breakdownOpen}
        onClose={() => setBreakdownOpen(false)}
        type={breakdownType}
      />

      {/* ── Multi-Teacher Payment modal ────────── */}
      <MultiPayModal
        isOpen={multiPayOpen}
        onClose={() => setMultiPayOpen(false)}
        onSuccess={notifyChanged}
      />

      {/* ── Record a payout by hand ────────────── */}
      <AddPayoutModal
        isOpen={addPayoutOpen}
        onClose={() => setAddPayoutOpen(false)}
        onSuccess={notifyChanged}
      />
    </div>
  )
}

export default BillingPage
