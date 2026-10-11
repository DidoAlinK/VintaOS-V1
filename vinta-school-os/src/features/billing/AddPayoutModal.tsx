import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import { toast } from '../../stores/uiStore'
import { formatCurrency, formatNumber } from '../../lib/formatters'
import { Modal } from '../../components/ui/Modal'
import { Select } from '../../components/ui/Select'
import { Input } from '../../components/ui/Input'
import { DayPicker } from '../../components/ui/DayPicker'
import type { CreatePayoutRequest, PayoutBasis, TeacherPayment } from '../../types/billing'
import type { Teacher } from '../../types/teacher'
import { Check, Percent, Clock3, CalendarCheck, PenLine, CircleCheck, CircleDashed } from 'lucide-react'

/* ─── Record a payout by hand ───
 *
 * Until now a payout could only be *marked paid* — never created. Only the
 * session-finalisation flow could write one, which meant a bonus, a correction,
 * an advance, or pay for a lesson never marked conducted had nowhere to go. This
 * is that missing door.
 *
 * The four bases are not four ways of typing a number. The first three are the
 * teacher's own commission models, so the amount is *derived* — and the preview
 * here applies the same three rules the server applies (`_compute_teacher_cut`),
 * so what the owner reads before pressing the button is what gets written.
 * `CUSTOM` is the exception by definition: there is no rate to derive from, so
 * the stated amount is the amount.
 *
 * The preview is labelled as a preview, and is not authoritative: the server
 * recomputes on submit and rejects a zero with an explanation. That is
 * deliberate — a client that decided the amount and posted it would be a second
 * calculation path, and a second calculation path is how two numbers start
 * disagreeing. */

interface AddPayoutModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

/* ─── Bases ─── */

const BASES: { key: PayoutBasis; labelKey: string; icon: React.ElementType }[] = [
  { key: 'PERCENTAGE', labelKey: 'payouts.basis.percentage', icon: Percent },
  { key: 'FLAT_HOURLY', labelKey: 'payouts.basis.hourly', icon: Clock3 },
  { key: 'FIXED_SESSION', labelKey: 'payouts.basis.fixedSession', icon: CalendarCheck },
  { key: 'CUSTOM', labelKey: 'payouts.basis.custom', icon: PenLine },
]

/* Which dictionary key names a commission type. Read out of the buttons above
 * rather than restated, so a type cannot be called one thing on a button and
 * another in the line beneath the teacher picker.
 *
 * The lookup this replaced listed only three of the four types, so a teacher
 * whose commission is a custom amount was described on screen as
 * `payouts.basis.undefined`. Deriving it from BASES makes that impossible. */
const BASIS_LABEL_KEY = new Map<PayoutBasis, string>(BASES.map((b) => [b.key, b.labelKey]))

/* ─── PIN input ───
 *
 * Same four-box step-up as MultiPayModal. Kept local rather than shared: the
 * two modals disagree about their error copy and about whether a rejection
 * clears the field, and a shared component would need flags for both. */

function PinInput({
  value,
  onChange,
  error,
  errorText,
}: {
  value: string[]
  onChange: (pin: string[]) => void
  error: boolean
  errorText?: string | null
}) {
  const { t } = useTranslation('billing')
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    inputRefs.current[0]?.focus()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = (index: number, char: string) => {
    if (char && !/^\d$/.test(char)) return
    const next = [...value]
    next[index] = char
    onChange(next)
    if (char && index < 3) inputRefs.current[index + 1]?.focus()
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace') {
      if (!value[index] && index > 0) {
        const next = [...value]
        next[index - 1] = ''
        onChange(next)
        inputRefs.current[index - 1]?.focus()
      } else {
        const next = [...value]
        next[index] = ''
        onChange(next)
      }
    }
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <div className={cn('flex gap-2.5 justify-center', error && 'animate-shake')}>
        {value.map((digit, i) => (
          <input
            key={i}
            ref={(el) => { inputRefs.current[i] = el }}
            type="password"
            inputMode="numeric"
            maxLength={1}
            value={digit}
            onChange={(e) => handleChange(i, e.target.value)}
            onKeyDown={(e) => handleKeyDown(i, e)}
            className="w-11 h-11 rounded-xl text-center text-lg font-bold outline-none transition-all duration-200"
            style={{
              background: 'var(--input-bg)',
              color: 'var(--text)',
              border: digit
                ? error ? '2px solid var(--red)' : '2px solid var(--gold)'
                : '2px solid var(--glass-border)',
              boxShadow: digit && !error ? '0 4px 16px rgba(179,135,42,.15)' : 'none',
            }}
            aria-label={t('payouts.pin.digit', { index: i + 1 })}
          />
        ))}
      </div>
      {errorText ? (
        <p role="alert" className="text-xs font-medium text-[var(--red)]">
          {errorText}
        </p>
      ) : null}
    </div>
  )
}

/* ─── Main component ─── */

export function AddPayoutModal({ isOpen, onClose, onSuccess }: AddPayoutModalProps) {
  const { t } = useTranslation('billing')

  /* ── Teachers ── */
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [teachersLoading, setTeachersLoading] = useState(false)

  /* The chosen teacher's own totals, pulled from `GET /billing/teacher-payments`
     so the owner reads what the teacher has actually taught instead of going to
     look it up. Shown under the teacher picker; shown only, never typed into a
     field — see `pickTeacher` for why. */
  const [stats, setStats] = useState<TeacherPayment | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)

  /* ── Form ── */
  const [teacherId, setTeacherId] = useState('')
  const [basis, setBasis] = useState<PayoutBasis>('PERCENTAGE')
  const [gross, setGross] = useState('')
  const [rate, setRate] = useState('')
  const [hours, setHours] = useState('')
  const [amount, setAmount] = useState('')
  const [payoutDate, setPayoutDate] = useState('')
  const [notes, setNotes] = useState('')
  const [status, setStatus] = useState<'PENDING' | 'PAID'>('PAID')

  /* ── Step-up ── */
  const [pin, setPin] = useState<string[]>(['', '', '', ''])
  const [pinError, setPinError] = useState(false)
  const [pinMessage, setPinMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  /* Whether the basis was chosen by us from the teacher's own settings, so a
     later teacher change may re-seed it — but a basis the owner picked by hand
     is theirs and is never overwritten. */
  const basisSeeded = useRef(false)

  /* The teacher last picked. Two jobs, both about identity rather than content:
     it marks a stats response from an earlier pick as stale, and it says whether
     this pick is a *change* of teacher — a change re-seeds the rate, re-picking
     the same one leaves an owner's own edit alone. */
  const statsFor = useRef<string | null>(null)

  const selectedTeacher = teachers.find((tt) => tt.id === teacherId) ?? null

  /* Their configured commission model, named. `undefined` when the profile has
     no default set — the line below says so in words instead. */
  const basisLabelKey = selectedTeacher?.commission_type
    ? BASIS_LABEL_KEY.get(selectedTeacher.commission_type as PayoutBasis)
    : undefined

  /* ── Load teachers on open ── */
  useEffect(() => {
    if (!isOpen) return
    let cancelled = false
    async function load() {
      setTeachersLoading(true)
      try {
        const { data } = await api.get('/teachers')
        if (!cancelled) setTeachers(data.teachers ?? data ?? [])
      } catch {
        if (!cancelled) setTeachers([])
      } finally {
        if (!cancelled) setTeachersLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [isOpen])

  /* ── Reset on close ── */
  useEffect(() => {
    if (!isOpen) {
      setTeacherId('')
      setBasis('PERCENTAGE')
      setGross('')
      setRate('')
      setHours('')
      setAmount('')
      setPayoutDate('')
      setNotes('')
      setStatus('PAID')
      setPin(['', '', '', ''])
      setPinError(false)
      setPinMessage(null)
      setSubmitting(false)
      setSubmitError(null)
      basisSeeded.current = false
      setStats(null)
      setStatsLoading(false)
      statsFor.current = null
    }
  }, [isOpen])

  /* ── Seed the basis and rate from the teacher's own settings ──
   *
   * Paying a teacher their configured commission is the common case; making the
   * owner re-select "percentage" and re-type the rate every time is how a wrong
   * rate gets entered. Picking a teacher fills both in, and the owner can still
   * override either. */
  const pickTeacher = useCallback(
    (id: string) => {
      setTeacherId(id)
      const tt = teachers.find((row) => row.id === id)
      if (!tt) return

      /* Read before the ref is advanced: this is what tells a *change* of
         teacher apart from re-picking the one already selected. */
      const isNewTeacher = statsFor.current !== id
      statsFor.current = id

      // A basis the owner chose by hand outranks the teacher's default.
      if (!basisSeeded.current && tt.commission_type) {
        setBasis(tt.commission_type as PayoutBasis)
      }
      /* Seeded on every change of teacher, not only when the field is empty:
         the rate belongs to the teacher, so carrying the previous one across
         would silently price the new teacher's sessions at the old rate. An
         edit made after picking is kept — re-picking the same teacher is not a
         change. */
      if (tt.commission_value != null && (rate === '' || isNewTeacher)) {
        setRate(String(tt.commission_value))
      }

      /* What they have actually taught, shown under the picker so the owner can
         see the figures without leaving the form. Displayed, deliberately not
         typed into the fields below: those are this payout's gross and hours,
         while these totals are the teacher's whole history. Copying a career
         total into a per-session field would compute a payout for work that has
         already been paid for once. The rate is the one figure that means the
         same thing over any period, and that one is seeded above. */
      setStats(null)
      setStatsLoading(true)
      void (async () => {
        try {
          const { data } = await api.get('/billing/teacher-payments', {
            params: { teacher_id: id },
          })
          // A response for a teacher no longer selected would otherwise land on
          // the current one's form.
          if (statsFor.current !== id) return
          const row: TeacherPayment | undefined = (data?.teachers ?? [])[0]
          setStats(row ?? null)
        } catch {
          /* Silent by design. The figures are context, not input, and the form
             is perfectly usable without them — an error banner for a fetch the
             owner never asked for would be noise. */
          if (statsFor.current === id) setStats(null)
        } finally {
          if (statsFor.current === id) setStatsLoading(false)
        }
      })()
    },
    [teachers, rate],
  )

  /* ── Cleared when a teacher is picked: the fields the previous basis used
     must not survive into the new one and be silently submitted. ── */
  const chooseBasis = (next: PayoutBasis) => {
    basisSeeded.current = true
    setBasis(next)
    setSubmitError(null)
  }

  /* ── Preview ──
   * The same three rules as the server, stated once more. Kept as integers
   * throughout so the preview and the stored amount round identically. */
  const previewCut = ((): number => {
    const grossN = parseInt(gross, 10) || 0
    const rateN = parseInt(rate, 10) || 0
    const hoursN = parseFloat(hours) || 0
    switch (basis) {
      case 'PERCENTAGE':
        return Math.trunc((grossN * rateN) / 100)
      case 'FLAT_HOURLY':
        return Math.trunc(hoursN * rateN)
      case 'FIXED_SESSION':
        return rateN
      case 'CUSTOM':
        return parseInt(amount, 10) || 0
      default:
        return 0
    }
  })()

  /* ── Can submit? ── */
  const formComplete = (() => {
    if (!teacherId) return false
    switch (basis) {
      case 'PERCENTAGE':
        return (parseInt(gross, 10) || 0) > 0 && (parseInt(rate, 10) || 0) > 0
      case 'FLAT_HOURLY':
        return (parseFloat(hours) || 0) > 0 && (parseInt(rate, 10) || 0) > 0
      case 'FIXED_SESSION':
        return (parseInt(rate, 10) || 0) > 0
      case 'CUSTOM':
        return (parseInt(amount, 10) || 0) > 0
      default:
        return false
    }
  })()

  const canSubmit = formComplete && pin.every((d) => d) && !submitting

  /* ── Submit ── */
  const handleSubmit = async () => {
    if (!formComplete) return
    if (pin.some((d) => !d)) {
      setPinError(true)
      setPinMessage(t('payouts.form.pinIncomplete'))
      return
    }

    setSubmitting(true)
    setSubmitError(null)
    setPinError(false)
    setPinMessage(null)

    try {
      const payload: CreatePayoutRequest = {
        teacher_id: teacherId,
        basis,
        status,
        pin: pin.join(''),
      }
      if (basis === 'PERCENTAGE') {
        payload.gross_revenue_da = parseInt(gross, 10) || 0
        payload.commission_value = parseInt(rate, 10) || 0
      } else if (basis === 'FLAT_HOURLY') {
        payload.duration_hours = parseFloat(hours) || 0
        payload.commission_value = parseInt(rate, 10) || 0
      } else if (basis === 'FIXED_SESSION') {
        payload.commission_value = parseInt(rate, 10) || 0
      } else {
        payload.amount_da = parseInt(amount, 10) || 0
      }
      if (payoutDate) payload.payout_date = payoutDate
      if (notes.trim()) payload.notes = notes.trim()

      const { data } = await api.post('/billing/payouts', payload)

      toast.success(
        status === 'PAID'
          ? t('payouts.form.toast.paid.title')
          : t('payouts.form.toast.pending.title'),
        t('payouts.form.toast.body', {
          teacher: data?.teacher_name ?? selectedTeacher?.full_name ?? '',
          amount: formatCurrency(data?.teacher_cut_da ?? previewCut),
        }),
      )
      onSuccess?.()
      onClose()
    } catch (err: unknown) {
      const res = (
        err as { response?: { status?: number; data?: { error?: string; message?: string } } }
      )?.response
      const statusCode = res?.status
      const msg = res?.data?.error || res?.data?.message || t('payouts.form.error.failed')

      /* Wrong PIN answers 403, never 401 — a 401 is read as an expired session
         by the axios interceptor, which would sign the owner out mid-form. */
      const isPinError = statusCode === 403 || msg.toLowerCase().includes('pin')
      if (isPinError) {
        setPinError(true)
        setPinMessage(t('payouts.form.pinIncorrect'))
        setPin(['', '', '', ''])
      } else if (statusCode === 401) {
        setSubmitError(t('payouts.form.error.sessionExpired'))
      } else {
        /* The server's own explanation for a rejected amount ("that works out
           to a payout of zero — check the gross…") is more useful than a
           generic failure, so it is shown verbatim. */
        setSubmitError(msg)
      }
    } finally {
      setSubmitting(false)
    }
  }

  const teacherOptions = teachers.map((tt) => ({
    value: tt.id,
    label: tt.full_name,
  }))

  return (
    <Modal open={isOpen} onClose={onClose} title={t('payouts.form.title')} size="lg">
      <div className="flex flex-col gap-5">
        <p className="text-sm text-[var(--muted)]">{t('payouts.form.subtitle')}</p>

        {/* ── Teacher ── */}
        <Select
          label={t('payouts.form.teacher')}
          value={teacherId}
          onChange={pickTeacher}
          options={teacherOptions}
          placeholder={
            teachersLoading ? t('payouts.form.teachersLoading') : t('payouts.form.teacherPlaceholder')
          }
          disabled={teachersLoading}
          searchPlaceholder={t('payouts.form.teacherSearch')}
          emptyText={t('payouts.form.noTeachers')}
        />

        {selectedTeacher && (
          <div className="-mt-3 flex flex-col gap-1 text-[11px] leading-snug text-[var(--muted)]">
            <p>
              {t('payouts.form.teacherDefault', {
                basis: basisLabelKey
                  ? t(basisLabelKey)
                  : t('payouts.form.teacherNoDefault'),
                value: selectedTeacher.commission_value ?? 0,
              })}
            </p>

            {/* What the teacher has actually taught, across every session on
                record — context for the owner, not an input. The fields below
                ask about *this* payout; these are the teacher's whole history,
                and the two are different quantities. */}
            {statsLoading ? (
              <p className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full border-2 border-current border-t-transparent opacity-60 animate-spin" />
                {t('payouts.form.stats.loading')}
              </p>
            ) : stats && stats.session_count > 0 ? (
              <p className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
                <span className="font-medium text-[var(--text)]">
                  {t('payouts.form.stats.label')}
                </span>
                <span>{t('payouts.form.stats.sessions', { count: stats.session_count })}</span>
                <span aria-hidden="true">·</span>
                <span>
                  {t('payouts.form.stats.hours', { hours: formatNumber(stats.duration_hours) })}
                </span>
                <span aria-hidden="true">·</span>
                <span className="font-medium text-[var(--gold)]">
                  {t('payouts.form.stats.revenue', { amount: formatCurrency(stats.gross_revenue_da) })}
                </span>
              </p>
            ) : (
              <p>{t('payouts.form.stats.none')}</p>
            )}
          </div>
        )}

        {/* ── Basis ── */}
        <div>
          <label className="block text-xs font-medium text-[var(--muted)] uppercase tracking-wide mb-2">
            {t('payouts.form.basis')}
          </label>
          <div className="grid grid-cols-2 gap-2">
            {BASES.map(({ key, labelKey, icon: Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => chooseBasis(key)}
                aria-pressed={basis === key}
                className={cn(
                  'flex items-center gap-2 px-3 py-2.5 rounded-[var(--radius-sm)]',
                  'text-sm font-medium border transition-all duration-150',
                  basis === key
                    ? 'bg-[var(--gold-soft)] border-[var(--gold)] text-[var(--gold)] shadow-sm'
                    : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)]',
                )}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{t(labelKey)}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ── Amount, per basis ──
            Only the fields the chosen basis actually reads are shown. A grid of
            every possible input would invite an owner to fill in the gross on a
            flat-session payout, where it changes nothing. */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {basis === 'PERCENTAGE' && (
            <>
              <Input
                label={t('payouts.form.gross')}
                type="number"
                min={0}
                inputMode="numeric"
                value={gross}
                onChange={(e) => setGross(e.target.value)}
                helperText={t('payouts.form.grossHint')}
              />
              <Input
                label={t('payouts.form.ratePercent')}
                type="number"
                min={0}
                max={100}
                inputMode="numeric"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
                helperText={t('payouts.form.ratePercentHint')}
              />
            </>
          )}

          {basis === 'FLAT_HOURLY' && (
            <>
              <Input
                label={t('payouts.form.hours')}
                type="number"
                min={0}
                step="0.5"
                inputMode="decimal"
                value={hours}
                onChange={(e) => setHours(e.target.value)}
                helperText={t('payouts.form.hoursHint')}
              />
              <Input
                label={t('payouts.form.rateHour')}
                type="number"
                min={0}
                inputMode="numeric"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
                helperText={t('payouts.form.rateHourHint')}
              />
            </>
          )}

          {basis === 'FIXED_SESSION' && (
            <div className="sm:col-span-2">
              <Input
                label={t('payouts.form.rateSession')}
                type="number"
                min={0}
                inputMode="numeric"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
                helperText={t('payouts.form.rateSessionHint')}
              />
            </div>
          )}

          {basis === 'CUSTOM' && (
            <div className="sm:col-span-2">
              <Input
                label={t('payouts.form.amount')}
                type="number"
                min={0}
                inputMode="numeric"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                helperText={t('payouts.form.amountHint')}
              />
            </div>
          )}
        </div>

        {/* ── Preview ── */}
        {formComplete && (
          <div className="flex items-center justify-between px-3 py-2.5 rounded-[var(--radius-sm)] bg-[var(--gold-soft)]/50 border border-[var(--gold)]/30">
            <span className="text-xs font-medium text-[var(--muted)] uppercase tracking-wide">
              {t('payouts.form.preview')}
            </span>
            <span className="text-lg font-bold text-[var(--gold)] tabular-nums font-[family-name:var(--font-heading)]">
              {formatCurrency(previewCut)}
            </span>
          </div>
        )}

        {/* ── Date + note ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <DayPicker
            label={t('payouts.form.date')}
            value={payoutDate}
            onChange={setPayoutDate}
            placeholder={t('payouts.form.datePlaceholder')}
            allowPast
          />
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="payout-notes"
              className="text-sm font-medium text-[var(--text)] font-[family-name:var(--font-heading)]"
            >
              {t('payouts.form.notes')}
            </label>
            <textarea
              id="payout-notes"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('payouts.form.notesPlaceholder')}
              className={cn(
                'w-full px-3 py-2 rounded-[var(--radius-sm)] resize-none',
                'text-sm text-[var(--text)] placeholder:text-[var(--muted)]/50',
                'bg-[var(--input-bg)] border border-[var(--glass-border)]',
                'outline-none focus:border-[var(--gold)] focus:ring-1 focus:ring-[var(--gold)]/30',
                'transition-colors',
              )}
            />
            <p className="text-xs text-[var(--muted)]">{t('payouts.form.notesHint')}</p>
          </div>
        </div>

        {/* ── Status ──
            Both outcomes are legitimate, so neither is a default the owner has
            to notice and undo: they choose, and the two options say what each
            one does to the payout list. */}
        <div>
          <label className="block text-xs font-medium text-[var(--muted)] uppercase tracking-wide mb-2">
            {t('payouts.form.status')}
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {(
              [
                { key: 'PAID' as const, labelKey: 'payouts.form.statusPaid', hintKey: 'payouts.form.statusPaidHint', icon: CircleCheck },
                { key: 'PENDING' as const, labelKey: 'payouts.form.statusPending', hintKey: 'payouts.form.statusPendingHint', icon: CircleDashed },
              ]
            ).map(({ key, labelKey, hintKey, icon: Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => setStatus(key)}
                aria-pressed={status === key}
                className={cn(
                  'flex items-start gap-2.5 p-3 rounded-[var(--radius-sm)] text-start',
                  'border transition-all duration-150',
                  status === key
                    ? 'bg-[var(--gold-soft)] border-[var(--gold)]'
                    : 'bg-[var(--input-bg)] border-[var(--glass-border)] hover:border-[var(--glass-border)]',
                )}
              >
                <Icon
                  className={cn(
                    'w-4 h-4 shrink-0 mt-0.5',
                    status === key ? 'text-[var(--gold)]' : 'text-[var(--muted)]',
                  )}
                />
                <span className="flex flex-col gap-0.5 min-w-0">
                  <span
                    className={cn(
                      'text-sm font-semibold',
                      status === key ? 'text-[var(--gold)]' : 'text-[var(--text)]',
                    )}
                  >
                    {t(labelKey)}
                  </span>
                  <span className="text-[11px] leading-snug text-[var(--muted)]">
                    {t(hintKey)}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* ── PIN ── */}
        {formComplete && (
          <div>
            <label className="block text-xs font-medium text-[var(--muted)] uppercase tracking-wide mb-3">
              {t('payouts.form.pinStep')}
            </label>
            <PinInput
              value={pin}
              onChange={(next) => {
                setPin(next)
                if (pinMessage) {
                  setPinMessage(null)
                  setPinError(false)
                }
              }}
              error={pinError}
              errorText={pinMessage}
            />
          </div>
        )}

        {submitError && (
          <p role="alert" className="text-xs font-medium text-[var(--red)] text-center">
            {submitError}
          </p>
        )}

        {/* ── Submit ── */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onClose}
            className={cn(
              'px-4 py-3 rounded-[var(--radius-sm)] text-sm font-medium',
              'text-[var(--muted)] bg-[var(--input-bg)] border border-[var(--glass-border)]',
              'hover:text-[var(--text)] transition-colors',
            )}
          >
            {t('payouts.form.cancel')}
          </button>

          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={!canSubmit}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 py-3 rounded-[var(--radius-sm)]',
              'text-sm font-semibold transition-all duration-200',
              canSubmit
                ? 'bg-gradient-to-r from-[var(--gold)] to-[var(--gold-dark, #9a7520)] text-white shadow-[0_4px_20px_rgba(179,135,42,.35)] hover:shadow-[0_6px_28px_rgba(179,135,42,.5)]'
                : 'bg-[var(--input-bg)] text-[var(--muted)] border border-[var(--glass-border)] cursor-not-allowed',
            )}
          >
            {submitting ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Check className="w-4 h-4" />
            )}
            {submitting ? t('payouts.form.submitting') : t('payouts.form.submit')}
          </button>
        </div>
      </div>
    </Modal>
  )
}

export default AddPayoutModal
