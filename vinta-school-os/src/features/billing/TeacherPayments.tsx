import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import { formatCurrency, formatDateShort, formatNumber } from '../../lib/formatters'
import { Badge } from '../../components/ui/Badge'
import { Card, CardBody } from '../../components/ui/Card'
import { ChevronDown, RefreshCw, Users, Layers, CalendarCheck } from 'lucide-react'
import { fetchDueTeachers, type DueTeacher } from '../../lib/payoutSchedule'
import { PayoutDetailsCard } from './PayoutDetailsCard'
import type { TeacherPayment, TeacherPaymentGroup } from '../../types/billing'

/* ─── Props ─── */

export interface TeacherPaymentsProps {
  /** Bump to refetch — raised after a payout is confirmed below. */
  refreshKey?: number
  className?: string
}

/* ─── Small labelled figure ───
 *
 * Exported because the details card renders the same figure and a second copy
 * of it would be a second place for the label/value styling to drift. */

export function Figure({
  label,
  value,
  color,
  strong = false,
}: {
  label: string
  value: string
  color?: string
  strong?: boolean
}) {
  return (
    <div className="flex flex-col min-w-0">
      <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">{label}</span>
      <span
        className={cn('text-sm tabular-nums', strong && 'font-semibold')}
        style={{ color: color ?? 'var(--text)' }}
      >
        {value}
      </span>
    </div>
  )
}

/* ─── Component ─── */

export function TeacherPayments({ refreshKey = 0, className }: TeacherPaymentsProps) {
  const { t } = useTranslation('billing')
  const [teachers, setTeachers] = useState<TeacherPayment[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  /* Who has come due, keyed by teacher, so a row can look up its own badge in
     one step. Empty whenever nobody is due. */
  const [dueTeachers, setDueTeachers] = useState<Map<string, DueTeacher>>(new Map())

  /* The teacher whose details card is open, if any. Held here rather than in
     the card so the card can be mounted fresh per teacher (see the `key` on it
     below). */
  const [detailsFor, setDetailsFor] = useState<{ id: string; name: string } | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const { data } = await api.get('/billing/teacher-payments')
      setTeachers(data.teachers ?? [])
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      const msgKey = (status ?? 0) >= 500
        ? 'teacherPayments.error.server'
        : 'teacherPayments.error.load'
      setLoadError(msgKey)
      setTeachers([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  /* ── Who has come due ──
   *
   * A request of its own, and deliberately with no error state. An academy that
   * has never set a payout cadence has no paydays at all, so an empty list is
   * the ordinary answer rather than a fault — and this screen's real job is
   * showing earnings, which a banner about a badge would get in the way of. A
   * failure is therefore swallowed into the same empty list, exactly as
   * `fetchDueTeachers` documents. */
  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const due = await fetchDueTeachers()
        if (cancelled) return
        setDueTeachers(new Map(due.map((row) => [row.teacher_id, row])))
      } catch {
        // Silent by design — see above.
        if (!cancelled) setDueTeachers(new Map())
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  /* ── Totals across every teacher ── */
  const totals = teachers.reduce(
    (acc, teacher) => ({
      owed: acc.owed + (teacher.owed_da ?? 0),
      settled: acc.settled + (teacher.settled_da ?? 0),
      gross: acc.gross + (teacher.gross_revenue_da ?? 0),
    }),
    { owed: 0, settled: 0, gross: 0 },
  )

  if (isLoading) {
    return (
      <div className={cn('flex items-center justify-center py-16', className)}>
        <div className="flex flex-col items-center gap-3 text-[var(--muted)]">
          <div className="w-6 h-6 border-2 border-[var(--gold)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">{t('teacherPayments.loading')}</span>
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className={cn('flex flex-col items-center justify-center py-16 gap-3', className)}>
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
    )
  }

  if (teachers.length === 0) {
    return (
      <div className={cn('flex flex-col items-center justify-center py-12 gap-3', className)}>
        <p className="text-sm font-medium text-[var(--muted)]">{t('teacherPayments.empty.title')}</p>
        <p className="text-xs text-[var(--muted)]/60">{t('teacherPayments.empty.body')}</p>
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {/* Totals rail — the three figures §5 asks to be told apart, summed. */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Card>
          <CardBody>
            <Figure
              label={t('teacherPayments.total.owed')}
              value={formatCurrency(totals.owed)}
              color="var(--gold)"
              strong
            />
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <Figure
              label={t('teacherPayments.total.settled')}
              value={formatCurrency(totals.settled)}
              color="var(--emerald)"
              strong
            />
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <Figure
              label={t('teacherPayments.total.gross')}
              value={formatCurrency(totals.gross)}
              strong
            />
          </CardBody>
        </Card>
      </div>

      {/* Per-teacher rows. Every figure below is the sum over ALL of that
          teacher's groups — reading one group is how the totals drifted. */}
      <div className="flex flex-col gap-3">
        {teachers.map((teacher) => {
          const isOpen = expanded === teacher.teacher_id
          const name = teacher.teacher_name || t('teacherPayments.unknownTeacher')
          const due = dueTeachers.get(teacher.teacher_id)
          return (
            <div
              key={teacher.teacher_id}
              className="rounded-[var(--radius-md)] border border-[var(--glass-border)] bg-[var(--glass)] backdrop-blur-[22px] overflow-hidden"
            >
              {/* The row is a wrapper around the toggle rather than one big
                  button: a due teacher has a second control in it, and a button
                  inside a button is invalid HTML — the inner one never receives
                  the click. */}
              <div className="flex items-center gap-2 px-4 py-3 hover:bg-[var(--glass-strong)] transition-colors">
                <button
                  type="button"
                  onClick={() => setExpanded(isOpen ? null : teacher.teacher_id)}
                  aria-expanded={isOpen}
                  className="flex-1 min-w-0 flex items-center gap-4 text-start"
                >
                  <ChevronDown
                    size={15}
                    className={cn(
                      'shrink-0 text-[var(--muted)] transition-transform duration-200',
                      isOpen && 'rotate-180 text-[var(--gold)]',
                    )}
                  />

                  <span className="text-sm font-semibold text-[var(--text)] font-[family-name:var(--font-heading)] truncate">
                    {name}
                  </span>

                  {/* Roster context: distinct students across all their groups. */}
                  <span className="flex items-center gap-1 text-xs text-[var(--muted)] shrink-0">
                    <Users size={12} />
                    {formatNumber(teacher.student_count ?? 0)}
                  </span>
                  <span className="flex items-center gap-1 text-xs text-[var(--muted)] shrink-0">
                    <Layers size={12} />
                    {formatNumber(teacher.group_count ?? 0)}
                  </span>
                  <span className="flex items-center gap-1 text-xs text-[var(--muted)] shrink-0">
                    <CalendarCheck size={12} />
                    {formatNumber(teacher.session_count ?? 0)}
                  </span>

                  <span className="flex-1" />

                  {/* Owed vs settled — the distinction the confirmation flow exists for. */}
                  <Badge
                    variant={(teacher.owed_da ?? 0) > 0 ? 'warning' : 'success'}
                    size="sm"
                    className="shrink-0"
                  >
                    {(teacher.owed_da ?? 0) > 0
                      ? t('teacherPayments.badge.owed', { amount: formatCurrency(teacher.owed_da ?? 0) })
                      : t('teacherPayments.badge.allSettled')}
                  </Badge>

                  {/* Due — a third state, not a second owed badge: it is about a
                      payday having passed, not about how much is owed. Sits next
                      to the badge above, and takes the gold "attention"
                      treatment rather than the warning one.

                      The label stays one short word. The row already carries an
                      owed badge, a session count and an amount, and a "since"
                      phrase at this width would push one of them off the line —
                      so the date the due list does send goes in the tooltip,
                      where the same sentence the details card shows costs no
                      space. */}
                  {due && (
                    <Badge
                      size="sm"
                      title={
                        due.oldest_pending_date
                          ? t('teacherPayments.due.since', {
                              date: formatDateShort(due.oldest_pending_date),
                            })
                          : t('teacherPayments.due.title')
                      }
                      className="shrink-0 border border-[var(--gold)] bg-[var(--gold-soft)] text-[var(--gold)]"
                    >
                      {t('teacherPayments.due.badge')}
                    </Badge>
                  )}

                  <span className="text-sm font-bold tabular-nums text-[var(--text)] shrink-0 w-28 text-end">
                    {formatCurrency(teacher.teacher_cut_da ?? 0)}
                  </span>
                </button>

                {due && (
                  <button
                    type="button"
                    onClick={() => setDetailsFor({ id: teacher.teacher_id, name })}
                    className={cn(
                      'shrink-0 px-3 py-1.5 rounded-[var(--radius-sm)]',
                      'text-xs font-semibold',
                      'border border-[var(--gold)] bg-[var(--gold-soft)] text-[var(--gold)]',
                      'hover:shadow-[0_4px_14px_rgba(179,135,42,.28)] active:scale-[0.97] transition-all',
                    )}
                  >
                    {t('teacherPayments.details.action')}
                  </button>
                )}
              </div>

              {/* Group breakdown (§6) */}
              {isOpen && (
                <div className="border-t border-[var(--glass-border)]/50 px-4 py-3">
                  {teacher.groups.length === 0 ? (
                    <p className="text-xs text-[var(--muted)]">{t('teacherPayments.noGroups')}</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[var(--glass-border)]/50">
                          <th className="text-start px-2 py-2 text-[10px] uppercase tracking-wide font-medium text-[var(--muted)]">
                            {t('teacherPayments.group.name')}
                          </th>
                          <th className="text-end px-2 py-2 text-[10px] uppercase tracking-wide font-medium text-[var(--muted)]">
                            {t('teacherPayments.group.sessions')}
                          </th>
                          <th className="text-end px-2 py-2 text-[10px] uppercase tracking-wide font-medium text-[var(--muted)]">
                            {t('teacherPayments.group.owed')}
                          </th>
                          <th className="text-end px-2 py-2 text-[10px] uppercase tracking-wide font-medium text-[var(--muted)]">
                            {t('teacherPayments.group.settled')}
                          </th>
                          <th className="text-end px-2 py-2 text-[10px] uppercase tracking-wide font-medium text-[var(--muted)]">
                            {t('teacherPayments.group.total')}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {teacher.groups.map((group: TeacherPaymentGroup) => (
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
                            <td className="px-2 py-2 text-end tabular-nums text-[var(--gold)]">
                              {group.pending_da > 0 ? formatCurrency(group.pending_da) : t('common:dash')}
                            </td>
                            <td className="px-2 py-2 text-end tabular-nums text-[var(--emerald)]">
                              {group.paid_da > 0 ? formatCurrency(group.paid_da) : t('common:dash')}
                            </td>
                            <td className="px-2 py-2 text-end tabular-nums font-medium text-[var(--text)]">
                              {formatCurrency(group.teacher_cut_da ?? 0)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* The details card for whichever due teacher was opened. Keyed by
          teacher so opening a second one mounts a fresh card — a range picked
          for the first teacher cannot silently apply to the second, and no
          stale figures can flash while the new ones load. */}
      <PayoutDetailsCard
        key={detailsFor?.id ?? 'closed'}
        teacherId={detailsFor?.id ?? ''}
        teacherName={detailsFor?.name ?? ''}
        isOpen={detailsFor !== null}
        onClose={() => setDetailsFor(null)}
      />
    </div>
  )
}

export default TeacherPayments
