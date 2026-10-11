import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import { toast } from '../../stores/uiStore'
import { formatCurrency, formatDateShort, formatDateISO, formatNumber } from '../../lib/formatters'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Modal } from '../../components/ui/Modal'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { Plus, Pencil, Trash2, RefreshCw, Receipt, Inbox } from 'lucide-react'
import type {
  Expense,
  ExpenseCategories,
  ExpenseInput,
  ExpenseSummary,
} from '../../types/billing'

/* ─── Enum → dictionary key ───
 *
 * The API's category and method values are enum keys, never display text, so
 * the label is looked up from here at render and follows a language switch.
 * The *sets* themselves are not copied into this file: the form gets its
 * options from `GET /billing/expense-categories`, so it cannot offer a
 * category the server will reject.
 */

const CATEGORY_KEY: Record<string, string> = {
  SUPPLIES: 'expenses.category.supplies',
  RENT: 'expenses.category.rent',
  UTILITIES: 'expenses.category.utilities',
  SALARIES: 'expenses.category.salaries',
  MAINTENANCE: 'expenses.category.maintenance',
  EQUIPMENT: 'expenses.category.equipment',
  MARKETING: 'expenses.category.marketing',
  TRANSPORT: 'expenses.category.transport',
  TAXES: 'expenses.category.taxes',
  OTHER: 'expenses.category.other',
}

const METHOD_KEY: Record<string, string> = {
  CASH: 'expenses.method.cash',
  CCP: 'expenses.method.ccp',
  BARIDI_MOB: 'expenses.method.baridiMob',
  BANK: 'expenses.method.bank',
  OTHER: 'expenses.method.other',
}

/* Stable colours per category so the list badge and the chart wedge for the
 * same category are the same colour on every render and every reload. */
const CATEGORY_COLOR: Record<string, string> = {
  SUPPLIES: '#b3872a',
  RENT: '#0f6b4d',
  UTILITIES: '#7c5cbf',
  SALARIES: '#b3452a',
  MAINTENANCE: '#2a7fb3',
  EQUIPMENT: '#8a7a2a',
  MARKETING: '#b32a8a',
  TRANSPORT: '#2ab39a',
  TAXES: '#6b6b6b',
  OTHER: '#9a7520',
}

const EMPTY_FORM = {
  category: 'OTHER',
  label: '',
  amount: '',
  expense_date: '',
  quantity: '',
  vendor: '',
  payment_method: 'CASH',
  notes: '',
}

type FormState = typeof EMPTY_FORM

/* ─── Chart tooltip ─── */

/* A component rather than the chart's `formatter` prop, matching the rest of
   the billing charts — one place decides how money is written. */
function ExpenseTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const value = payload[0].value as number
  return (
    <div
      className={cn(
        'rounded-[var(--radius-sm)] px-3 py-2',
        'bg-[var(--glass-strong)] backdrop-blur-md',
        'border border-[var(--glass-border)]',
        'shadow-lg text-sm',
      )}
    >
      <p className="text-[var(--muted)] text-xs mb-1">{payload[0].payload?.month ?? label}</p>
      <p className="font-semibold text-[var(--text)] font-[family-name:var(--font-heading)] tabular-nums">
        {formatCurrency(value)}
      </p>
    </div>
  )
}

/* ─── Props ─── */

export interface SchoolExpensesPanelProps {
  /** Bump to refetch — e.g. after another panel writes an expense. */
  refreshKey?: number
  /** Raised when this panel changes expense data, so net profit elsewhere updates. */
  onChanged?: () => void
  className?: string
}

/* ─── Component ─── */

export function SchoolExpensesPanel({
  refreshKey = 0,
  onChanged,
  className,
}: SchoolExpensesPanelProps) {
  const { t } = useTranslation('billing')

  const [expenses, setExpenses] = useState<Expense[]>([])
  const [summary, setSummary] = useState<ExpenseSummary | null>(null)
  const [optionSets, setOptionSets] = useState<ExpenseCategories | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Expense | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const [deleting, setDeleting] = useState<Expense | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const [listRes, summaryRes, catRes] = await Promise.all([
        api.get('/billing/expenses'),
        api.get('/billing/expense-summary', { params: { months: 6 } }),
        api.get('/billing/expense-categories'),
      ])
      setExpenses(listRes.data.expenses ?? [])
      setSummary(summaryRes.data ?? null)
      setOptionSets({
        categories: catRes.data.categories ?? [],
        payment_methods: catRes.data.payment_methods ?? [],
      })
    } catch (err: any) {
      const msgKey = err?.response?.status >= 500
        ? 'expenses.error.server'
        : 'expenses.error.load'
      setLoadError(msgKey)
      setExpenses([])
      setSummary(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  const categoryLabel = useCallback(
    (value: string) => (CATEGORY_KEY[value] ? t(CATEGORY_KEY[value]) : t('expenses.category.unknown')),
    [t],
  )
  const methodLabel = useCallback(
    (value: string) => (METHOD_KEY[value] ? t(METHOD_KEY[value]) : t('expenses.method.unknown')),
    [t],
  )

  const categoryOptions = useMemo(
    () =>
      (optionSets?.categories ?? []).map((value) => ({
        value,
        label: CATEGORY_KEY[value] ? t(CATEGORY_KEY[value]) : value,
      })),
    [optionSets, t],
  )

  const methodOptions = useMemo(
    () =>
      (optionSets?.payment_methods ?? []).map((value) => ({
        value,
        label: METHOD_KEY[value] ? t(METHOD_KEY[value]) : value,
      })),
    [optionSets, t],
  )

  /* ── Form ── */

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY_FORM, expense_date: formatDateISO(new Date()) })
    setFormError(null)
    setFormOpen(true)
  }

  const openEdit = (expense: Expense) => {
    setEditing(expense)
    setForm({
      category: expense.category,
      label: expense.label,
      amount: String(expense.amount_da ?? ''),
      expense_date: expense.expense_date ?? formatDateISO(new Date()),
      quantity: expense.quantity != null ? String(expense.quantity) : '',
      vendor: expense.vendor ?? '',
      payment_method: expense.payment_method ?? 'CASH',
      notes: expense.notes ?? '',
    })
    setFormError(null)
    setFormOpen(true)
  }

  const setField = (field: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    setFormError(null)
  }

  const submitForm = async () => {
    const amount = Number(form.amount)
    if (!form.label.trim()) {
      setFormError(t('expenses.form.error.label'))
      return
    }
    if (!Number.isFinite(amount) || amount <= 0) {
      setFormError(t('expenses.form.error.amount'))
      return
    }
    if (!form.expense_date) {
      setFormError(t('expenses.form.error.date'))
      return
    }
    if (form.quantity.trim() && !/^\d+$/.test(form.quantity.trim())) {
      setFormError(t('expenses.form.error.quantity'))
      return
    }

    const payload: ExpenseInput = {
      category: form.category,
      label: form.label.trim(),
      amount_da: Math.round(amount),
      expense_date: form.expense_date,
      quantity: form.quantity.trim() ? Number(form.quantity.trim()) : null,
      vendor: form.vendor.trim() || null,
      payment_method: form.payment_method,
      notes: form.notes.trim() || null,
    }

    setIsSaving(true)
    try {
      if (editing) {
        await api.put(`/billing/expenses/${editing.id}`, payload)
        toast.success(t('expenses.toast.updated'))
      } else {
        await api.post('/billing/expenses', payload)
        toast.success(t('expenses.toast.created'))
      }
      setFormOpen(false)
      await load()
      onChanged?.()
    } catch (err: any) {
      // The server's own sentence is the actionable one ("amount_da must be
      // greater than zero"); fall back to a translated line only if it is absent.
      const message = err?.response?.data?.error
      setFormError(message || t('expenses.form.error.save'))
    } finally {
      setIsSaving(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleting) return
    setIsDeleting(true)
    try {
      await api.delete(`/billing/expenses/${deleting.id}`)
      toast.success(t('expenses.toast.deleted'))
      setDeleting(null)
      await load()
      onChanged?.()
    } catch {
      toast.error(t('expenses.toast.deleteFailed'))
    } finally {
      setIsDeleting(false)
    }
  }

  /* ── Loading / error / empty ── */

  if (isLoading) {
    return (
      <div className={cn('flex items-center justify-center py-16', className)}>
        <div className="flex flex-col items-center gap-3 text-[var(--muted)]">
          <div className="w-6 h-6 border-2 border-[var(--gold)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">{t('expenses.loading')}</span>
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

  const categoryRows = (summary?.by_category ?? []).map((row) => ({
    ...row,
    label: categoryLabel(row.category),
    color: CATEGORY_COLOR[row.category] ?? 'var(--gold)',
  }))
  const series = summary?.series ?? []
  const maxCategory = Math.max(1, ...categoryRows.map((r) => r.amount_da))

  return (
    <div className={cn('flex flex-col gap-5', className)}>
      {/* ── Header rail: Add expense ── */}
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--text)]">{t('expenses.heading')}</p>
          <p className="text-xs text-[var(--muted)] mt-0.5">{t('expenses.subheading')}</p>
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus size={14} />
          {t('expenses.add')}
        </Button>
      </div>

      {/* ── Summary figures ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Card>
          <CardBody>
            <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
              {t('expenses.kpi.window')}
            </span>
            <p className="text-lg font-bold tabular-nums text-[var(--red)] font-[family-name:var(--font-heading)]">
              {formatCurrency(summary?.window_total_da ?? 0)}
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
              {t('expenses.kpi.allTime')}
            </span>
            <p className="text-lg font-bold tabular-nums text-[var(--text)] font-[family-name:var(--font-heading)]">
              {formatCurrency(summary?.total_da ?? 0)}
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
              {t('expenses.kpi.count')}
            </span>
            <p className="text-lg font-bold tabular-nums text-[var(--text)] font-[family-name:var(--font-heading)]">
              {formatNumber(summary?.count ?? 0)}
            </p>
          </CardBody>
        </Card>
      </div>

      {/* ── Charts: by category, and over time (§13) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader title={t('expenses.chart.byCategory')} />
          <CardBody>
            {categoryRows.length === 0 ? (
              <p className="py-10 text-center text-xs text-[var(--muted)]">
                {t('expenses.chart.empty')}
              </p>
            ) : (
              <div className="flex flex-col gap-3">
                {categoryRows.map((row) => (
                  <div key={row.category} className="flex items-center gap-3 min-w-0">
                    <span className="w-24 shrink-0 truncate text-xs text-[var(--muted)]">
                      {row.label}
                    </span>
                    <div className="flex-1 h-2.5 rounded-full bg-[var(--input-bg)] overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${Math.round((row.amount_da / maxCategory) * 100)}%`,
                          backgroundColor: row.color,
                        }}
                      />
                    </div>
                    <span className="w-24 shrink-0 text-end text-xs font-semibold tabular-nums text-[var(--text)]">
                      {formatCurrency(row.amount_da)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title={t('expenses.chart.overTime')} />
          <CardBody>
            <div className="h-[220px] w-full">
              {series.length === 0 ? (
                <p className="py-10 text-center text-xs text-[var(--muted)]">
                  {t('expenses.chart.empty')}
                </p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={series} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
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
                        v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)
                      }
                    />
                    <Tooltip content={<ExpenseTooltip />} cursor={{ fill: 'var(--glass)' }} />
                    <Bar dataKey="expense" fill="#b3452a" radius={[4, 4, 0, 0]} maxBarSize={44} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardBody>
        </Card>
      </div>

      {/* ── Records table ── */}
      <div className="overflow-x-auto">
        {expenses.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <div className="w-16 h-16 rounded-full bg-[var(--input-bg)] flex items-center justify-center">
              <Inbox className="w-7 h-7 text-[var(--muted)]/40" />
            </div>
            <p className="text-sm font-medium text-[var(--muted)]">{t('expenses.empty.title')}</p>
            <p className="text-xs text-[var(--muted)]/60">{t('expenses.empty.body')}</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--glass-border)]">
                <th className="text-start px-3 py-2.5 text-xs font-medium text-[var(--muted)]">
                  {t('expenses.table.date')}
                </th>
                <th className="text-start px-3 py-2.5 text-xs font-medium text-[var(--muted)]">
                  {t('expenses.table.description')}
                </th>
                <th className="text-start px-3 py-2.5 text-xs font-medium text-[var(--muted)]">
                  {t('expenses.table.category')}
                </th>
                <th className="text-end px-3 py-2.5 text-xs font-medium text-[var(--muted)]">
                  {t('expenses.table.quantity')}
                </th>
                <th className="text-start px-3 py-2.5 text-xs font-medium text-[var(--muted)]">
                  {t('expenses.table.method')}
                </th>
                <th className="text-end px-3 py-2.5 text-xs font-medium text-[var(--muted)]">
                  {t('expenses.table.amount')}
                </th>
                <th className="text-end px-3 py-2.5 text-xs font-medium text-[var(--muted)]">
                  {t('common:label.actions')}
                </th>
              </tr>
            </thead>
            <tbody>
              {expenses.map((expense) => (
                <tr
                  key={expense.id}
                  className="border-b border-[var(--glass-border)]/50 hover:bg-[var(--glass)] transition-colors"
                >
                  <td className="px-3 py-3 text-[var(--muted)] whitespace-nowrap">
                    {expense.expense_date ? formatDateShort(expense.expense_date) : t('common:dash')}
                  </td>
                  <td className="px-3 py-3">
                    <span className="font-medium text-[var(--text)]">{expense.label}</span>
                    {expense.vendor && (
                      <span className="block text-xs text-[var(--muted)]">{expense.vendor}</span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <Badge
                      variant="default"
                      size="sm"
                      className="whitespace-nowrap"
                    >
                      {categoryLabel(expense.category)}
                    </Badge>
                  </td>
                  <td className="px-3 py-3 text-end tabular-nums text-[var(--muted)]">
                    {expense.quantity != null ? `×${formatNumber(expense.quantity)}` : t('common:dash')}
                  </td>
                  <td className="px-3 py-3 text-[var(--text)]/80 whitespace-nowrap">
                    {methodLabel(expense.payment_method)}
                  </td>
                  <td className="px-3 py-3 text-end tabular-nums font-semibold text-[var(--red)] whitespace-nowrap">
                    {formatCurrency(expense.amount_da)}
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => openEdit(expense)}
                        aria-label={t('common:action.edit')}
                        className="flex items-center justify-center w-7 h-7 rounded-[var(--radius-xs)] text-[var(--muted)] hover:text-[var(--gold)] hover:bg-[var(--gold-soft)] transition-colors"
                      >
                        <Pencil size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleting(expense)}
                        aria-label={t('common:action.delete')}
                        className="flex items-center justify-center w-7 h-7 rounded-[var(--radius-xs)] text-[var(--muted)] hover:text-[var(--red)] hover:bg-[var(--red-soft)] transition-colors"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Add / edit modal ── */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? t('expenses.form.editTitle') : t('expenses.form.createTitle')}
        size="md"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setFormOpen(false)} disabled={isSaving}>
              {t('common:action.cancel')}
            </Button>
            <Button size="sm" onClick={() => void submitForm()} loading={isSaving}>
              {editing ? t('common:action.save') : t('expenses.form.create')}
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-4">
          <Input
            label={t('expenses.form.description')}
            value={form.label}
            onChange={(e) => setField('label', e.target.value)}
            placeholder={t('expenses.form.descriptionPlaceholder')}
            leftIcon={<Receipt size={15} />}
          />

          <Select
            label={t('expenses.form.category')}
            value={form.category}
            onChange={(v) => setField('category', v)}
            options={categoryOptions}
            searchable={false}
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label={t('expenses.form.amount')}
              type="number"
              min={1}
              value={form.amount}
              onChange={(e) => setField('amount', e.target.value)}
              placeholder="0"
            />
            <Input
              label={t('expenses.form.date')}
              type="date"
              value={form.expense_date}
              onChange={(e) => setField('expense_date', e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label={t('expenses.form.quantity')}
              type="number"
              min={1}
              value={form.quantity}
              onChange={(e) => setField('quantity', e.target.value)}
              placeholder={t('expenses.form.quantityPlaceholder')}
            />
            <Select
              label={t('expenses.form.method')}
              value={form.payment_method}
              onChange={(v) => setField('payment_method', v)}
              options={methodOptions}
              searchable={false}
            />
          </div>

          <Input
            label={t('expenses.form.vendor')}
            value={form.vendor}
            onChange={(e) => setField('vendor', e.target.value)}
            placeholder={t('expenses.form.vendorPlaceholder')}
          />

          <Input
            label={t('expenses.form.notes')}
            value={form.notes}
            onChange={(e) => setField('notes', e.target.value)}
            helperText={t('expenses.form.notesHint')}
          />

          {formError && (
            <p role="alert" className="text-xs font-medium text-[var(--red)]">
              {formError}
            </p>
          )}
        </div>
      </Modal>

      {/* ── Delete confirmation ── */}
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={() => void confirmDelete()}
        title={t('expenses.delete.title')}
        message={
          deleting
            ? t('expenses.delete.body', {
                label: deleting.label,
                amount: formatCurrency(deleting.amount_da),
              })
            : ''
        }
        confirmLabel={isDeleting ? t('expenses.delete.deleting') : t('common:action.delete')}
        variant="danger"
      />
    </div>
  )
}

export default SchoolExpensesPanel
