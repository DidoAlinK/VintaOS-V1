import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import { Card, CardHeader, CardBody } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import type { AcademySettings } from '../../types/settings'
import { useAuthStore } from '../../stores/authStore'
import { toast } from '../../stores/uiStore'
import api from '../../lib/api'
import {
  BILLING_RULE_DEFAULTS,
  BILLING_RULE_FIELDS,
  getSwapWindow,
  hydrateBillingRules,
  setBillingRule,
  setSwapWindow,
  snapshotBillingRules,
  type BillingRuleField,
  type SwapLinkWindow,
} from '../../lib/billingRules'
import {
  PAYOUT_CADENCES,
  WEEKDAYS,
  describeCadence,
  describeDraft,
  draftFrom,
  fetchAcademyPayoutSchedule,
  isDraftComplete,
  isDraftDirty,
  mayClampToMonthEnd,
  saveAcademyPayoutSchedule,
  type PayoutCadence,
  type PayoutDraft,
  type PayoutSchedule,
} from '../../lib/payoutSchedule'
import { formatDateFull } from '../../lib/formatters'
import { Toggle } from '../../components/ui/Toggle'
import { isGrossProfitEnabled, setGrossProfitEnabled } from '../../lib/grossProfit'
import { Save, Plus, X, Trash2, Coins, Clock, Users, Lock, RefreshCw } from 'lucide-react'

/**
 * The cadence → key-fragment map, in keys rather than in words.
 *
 * A module-level map of resolved labels would be resolved once, at import, in
 * whichever language happened to be loaded then and would never follow a
 * switch — the mistake the commission vocabulary in `TeacherDrawer` documents.
 */
const CADENCE_KEY: Record<PayoutCadence, string> = {
  NONE: 'none',
  WEEKLY: 'weekly',
  MONTHLY: 'monthly',
}

/* ─── The Billing Rules, and the question each one answers ─── */

/**
 * Every rule the server stores, in the order the desk meets them.
 *
 * Data rather than seven hand-written blocks: they are identical in shape and
 * the only thing that varies is the sentence. The old markup repeated the
 * switch three times and the three copies had already drifted — one said its
 * change applied "next Monday" while the server had no such notion.
 *
 * `labelKey` / `hintKey` rather than the sentences themselves: `field` is the
 * column name the server reads, and the wording has to follow the interface
 * language, which module scope knows nothing about.
 */
const RULE_ROWS: Array<{ field: BillingRuleField; labelKey: string; hintKey: string }> = [
  {
    field: 'absence_consumes_credit',
    labelKey: 'billing.rules.absence.label',
    hintKey: 'billing.rules.absence.hint',
  },
  {
    field: 'allow_makeups_default',
    labelKey: 'billing.rules.makeups.label',
    hintKey: 'billing.rules.makeups.hint',
  },
  {
    field: 'count_gap_sessions',
    labelKey: 'billing.rules.gapSessions.label',
    hintKey: 'billing.rules.gapSessions.hint',
  },
  {
    field: 'restore_credits_on_cancellation',
    labelKey: 'billing.rules.restoreCredits.label',
    hintKey: 'billing.rules.restoreCredits.hint',
  },
  {
    field: 'free_session_auto_present',
    labelKey: 'billing.rules.freeSession.label',
    hintKey: 'billing.rules.freeSession.hint',
  },
  {
    field: 'share_credits_across_groups',
    labelKey: 'billing.rules.shareCredits.label',
    hintKey: 'billing.rules.shareCredits.hint',
  },
  {
    field: 'early_payment_on_extra_sessions',
    labelKey: 'billing.rules.earlyPayment.label',
    hintKey: 'billing.rules.earlyPayment.hint',
  },
]

/** The server's own words when it refuses a write. */
function serverMessage(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: { error?: string; message?: string } } })
    ?.response?.data
  return data?.error || data?.message || fallback
}

/* ─── Props ─── */

export interface BillingConfigProps {
  settings: AcademySettings
  onUpdate: (data: Partial<AcademySettings>) => void
}

/* ─── Types ─── */

interface BillingPreset {
  id: string
  label: string
  days: number
}

/* ─── Constants ─── */

const PRESETS_STORAGE_KEY = 'vinta_billing_presets'

const DEFAULT_PRESETS: BillingPreset[] = [
  { id: 'default-1m', label: '1 Month', days: 30 },
  { id: 'default-3m', label: '3 Months', days: 90 },
  { id: 'default-6m', label: '6 Months', days: 180 },
]

/**
 * The three seeded presets carry a key rather than a translated label.
 *
 * They are persisted to localStorage on first load, so translating at seed
 * time would freeze whichever language happened to be active that day and the
 * chip would stay English after a switch to Arabic. The stored `label` stays
 * as the fallback and as the row's own text for presets the desk creates,
 * which are user copy and never translated.
 */
const BUILT_IN_PRESET_KEYS: Record<string, string> = {
  'default-1m': 'billing.preset.oneMonth',
  'default-3m': 'billing.preset.threeMonths',
  'default-6m': 'billing.preset.sixMonths',
}

// Currency codes and symbols — the same three letters and the same glyph in
// every language, so nothing here is translated. The code is what the server
// stores; the symbol is what the desk recognises.
const CURRENCY_OPTIONS = [
  { value: 'DZD', label: 'DZD (د.ج)' },
  { value: 'EUR', label: 'EUR (€)' },
  { value: 'USD', label: 'USD ($)' },
]

const REMINDER_PRESETS = [1, 2, 3, 5, 7]

/**
 * The WhatsApp template's merge fields, fed to `t()` as *values* so the
 * dictionary can show them and the rendered hint keeps them literal.
 */
const WHATSAPP_PLACEHOLDERS = {
  name: '{{name}}',
  amount: '{{amount}}',
  date: '{{date}}',
}

/* ─── Helpers ─── */

function loadPresets(): BillingPreset[] {
  try {
    const raw = localStorage.getItem(PRESETS_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    }
  } catch {
    // corrupt storage
  }
  // First load → seed defaults
  localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(DEFAULT_PRESETS))
  return DEFAULT_PRESETS
}

function savePresets(presets: BillingPreset[]) {
  localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(presets))
}

/* ─── Component ─── */

export function BillingConfig({ settings, onUpdate }: BillingConfigProps) {
  const { t } = useTranslation('settings')
  const [form, setForm] = useState({
    currency: settings.currency,
    default_plan_duration: settings.default_plan_duration,
    billing_reminder_days_before: settings.billing_reminder_days_before,
    whatsapp_template: settings.whatsapp_template,
    // New money model defaults
    default_credits_per_cycle: (settings as any).default_credits_per_cycle ?? 4,
    allow_rollover_default: (settings as any).allow_rollover_default ?? false,
    allow_makeups_default: (settings as any).allow_makeups_default ?? true,
    default_access_weeks: (settings as any).default_access_weeks ?? null,
    default_max_groups: (settings as any).default_max_groups ?? 1,
  })
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Preset system
  const [presets, setPresets] = useState<BillingPreset[]>(loadPresets)
  const [showAddPreset, setShowAddPreset] = useState(false)
  const [newPresetLabel, setNewPresetLabel] = useState('')
  const [newPresetDays, setNewPresetDays] = useState('')

  // Academy gross-profit opt-in (frontend registry, OFF by default)
  const [grossAcademy, setGrossAcademy] = useState(() => isGrossProfitEnabled())

  /** A preset's own label, or the dictionary's wording for a seeded one. */
  const presetLabel = (preset: BillingPreset) => {
    const key = BUILT_IN_PRESET_KEYS[preset.id]
    return key ? t(key) : preset.label
  }

  /* ── The Billing Rules, read from and written to the server ──
   *
   * These were localStorage preferences with a Monday version log, which
   * meant the screen agreed with itself and disagreed with the columns that
   * actually decide who is charged. See lib/billingRules.ts. The values here
   * mirror the last answer the server gave; every change is a PUT.
   */
  const [rules, setRules] = useState(() => snapshotBillingRules())
  const [rulesLoaded, setRulesLoaded] = useState(false)
  const [rulesError, setRulesError] = useState<string | null>(null)
  const [savingRule, setSavingRule] = useState<BillingRuleField | null>(null)

  const loadRules = useCallback(async () => {
    setRulesError(null)
    try {
      setRules(await hydrateBillingRules())
      setRulesLoaded(true)
    } catch (err) {
      // 403 here means a staff login on an owner-only endpoint. Saying
      // "defaults" is honest; showing the defaults as if they were the
      // academy's own rules would not be.
      setRulesError(serverMessage(err, t('billing.rules.loadFailed')))
    }
  }, [t])

  useEffect(() => { void loadRules() }, [loadRules])

  /* ── The payroll cadence, read from the same endpoint ──
   *
   * This is the academy-wide default: the day a teacher is paid unless they
   * have been given a cadence of their own in their profile. It lives in its
   * own `payout_schedules` table rather than on `academy_settings`, and it is
   * written through `PUT /settings/billing-config` — deliberately **not**
   * through `onUpdate`, because that prop is bound to the appearance endpoint
   * and would report success while dropping the change. See the note on
   * `handleSave`.
   */
  const [sched, setSched] = useState<PayoutSchedule | null>(null)
  const [schedDraft, setSchedDraft] = useState<PayoutDraft>(() => draftFrom(null))
  const [schedLoaded, setSchedLoaded] = useState(false)
  const [schedError, setSchedError] = useState<string | null>(null)
  const [savingSched, setSavingSched] = useState(false)
  /**
   * Whether a person has touched the controls since the last fetch.
   *
   * A ref rather than a piece of state, because the loader must not re-run when
   * it flips — and needed at all because `loadSchedule` depends on `t` and so
   * re-runs on a language switch. Without this, changing language mid-edit would
   * silently revert the cadence to whatever the server last held.
   */
  const schedTouched = useRef(false)

  const loadSchedule = useCallback(async () => {
    setSchedError(null)
    try {
      const fresh = await fetchAcademyPayoutSchedule()
      setSched(fresh)
      if (!schedTouched.current) setSchedDraft(draftFrom(fresh))
      setSchedLoaded(true)
    } catch (err) {
      // A staff login is refused here; the card is dimmed for them anyway, but
      // saying so beats rendering a cadence nobody could have set.
      setSchedError(serverMessage(err, t('billing.payoutSchedule.loadFailed')))
    }
  }, [t])

  useEffect(() => { void loadSchedule() }, [loadSchedule])

  const setCadence = (cadence: PayoutCadence) => {
    schedTouched.current = true
    setSchedDraft((prev) => ({ ...prev, cadence }))
  }

  // Persist presets whenever they change (but not on first render)
  const [initialized, setInitialized] = useState(false)
  useEffect(() => {
    if (initialized) {
      savePresets(presets)
    } else {
      setInitialized(true)
    }
  }, [presets, initialized])

  const handleChange = (field: string, value: string | number | boolean | null) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    setSaved(false)
  }

  const handleAddPreset = () => {
    const days = parseInt(newPresetDays, 10)
    const label = newPresetLabel.trim()
    if (!days || days <= 0 || !label) return

    const newPreset: BillingPreset = {
      id: `preset-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      label,
      days,
    }

    setPresets((prev) => [...prev, newPreset])
    setForm((prev) => ({ ...prev, default_plan_duration: days }))
    setNewPresetLabel('')
    setNewPresetDays('')
    setShowAddPreset(false)
    setSaved(false)
  }

  const handleRemovePreset = (id: string) => {
    setPresets((prev) => prev.filter((p) => p.id !== id))
    setSaved(false)
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await onUpdate(form)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setIsSaving(false)
    }
  }

  // ── Owner PIN gate ──
  const userRole = useAuthStore((s) => s.user?.role ?? 'staff')
  const [pinOpen, setPinOpen] = useState(false)
  const [pin, setPin] = useState('')
  const [pinError, setPinError] = useState<string | null>(null)
  const [pinChecking, setPinChecking] = useState(false)
  const [pinOk, setPinOk] = useState(false)
  /** The rule whose flip is waiting on the PIN. */
  const [pendingField, setPendingField] = useState<BillingRuleField | null>(null)
  /** The cadence save waiting on the PIN, when the press came from that card. */
  const [pendingSchedule, setPendingSchedule] = useState<PayoutDraft | null>(null)

  const [swapWindow, setSwapWindowState] = useState<SwapLinkWindow>(() => getSwapWindow())

  /**
   * Write one rule to the server.
   *
   * The server is owner-only on this endpoint as well, so a refusal is shown
   * rather than swallowed: a flip that silently did nothing would leave this
   * screen claiming a change the money paths never heard about — which is the
   * bug this replaced.
   *
   * This is the write, not the gate. The PIN is checked by the caller before it
   * gets here: `requestFlip` for a direct press, `handleVerifyPin` for the flip
   * that was waiting on the modal. Reading `pinOk` here instead would have been
   * a closure bug — the flip that follows a successful verify runs in the render
   * where the PIN was still unverified, so the gate would have refused the very
   * change it was opened to allow.
   */
  const flipRule = useCallback(async (field: BillingRuleField) => {
    if (userRole !== 'owner') {
      toast.error(t('billing.toast.ownerPinOnly'), t('billing.toast.ownerRoleRequired'))
      return
    }
    setSavingRule(field)
    try {
      await setBillingRule(field, !snapshotBillingRules()[field])
      setRules(snapshotBillingRules())
      const labelKey = RULE_ROWS.find((r) => r.field === field)?.labelKey
      const label = labelKey ? t(labelKey) : field
      toast.success(t('billing.toast.ruleUpdated'), t('billing.toast.ruleUpdatedBody', { label }))
    } catch (err) {
      toast.error(t('billing.toast.ruleChangeFailed'), serverMessage(err, t('billing.rules.changeRefused')))
    } finally {
      setSavingRule(null)
    }
  }, [t, userRole])

  /**
   * Write the academy-wide cadence.
   *
   * The server is owner-only, so a refusal is surfaced rather than swallowed —
   * the same reasoning as `flipRule`. After a successful write the schedule is
   * re-read rather than assumed: `next_payout_date` is the server's own
   * arithmetic (month lengths, month-end clamping), and recomputing it here
   * would be a second answer to a question that already has one.
   */
  const saveSchedule = useCallback(async (draft: PayoutDraft) => {
    if (userRole !== 'owner') {
      toast.error(t('billing.toast.ownerPinOnly'), t('billing.toast.ownerRoleRequired'))
      return
    }
    setSavingSched(true)
    try {
      await saveAcademyPayoutSchedule(draft)
      const fresh = await fetchAcademyPayoutSchedule()
      setSched(fresh)
      setSchedDraft(draftFrom(fresh))
      schedTouched.current = false
      toast.success(t('billing.payoutSchedule.saved'), t('billing.payoutSchedule.savedBody'))
    } catch (err) {
      toast.error(
        t('billing.payoutSchedule.saveFailed'),
        serverMessage(err, t('billing.payoutSchedule.saveFailed')),
      )
    } finally {
      setSavingSched(false)
    }
  }, [t, userRole])

  const requestScheduleSave = (draft: PayoutDraft) => {
    if (userRole !== 'owner') {
      toast.error(t('billing.toast.ownerPinOnly'), t('billing.toast.ownerRoleRequired'))
      return
    }
    if (pinOk) {
      // Already verified this session — apply immediately.
      void saveSchedule(draft)
      return
    }
    // Held until the PIN lands; handleVerifyPin reads it back.
    setPendingSchedule(draft)
    setPin('')
    setPinError(null)
    setPinOpen(true)
  }

  const requestFlip = (field: BillingRuleField) => {
    if (userRole !== 'owner') {
      toast.error(t('billing.toast.ownerPinOnly'), t('billing.toast.ownerRoleRequired'))
      return
    }
    if (pinOk) {
      // Already verified this session — apply immediately.
      void flipRule(field)
      return
    }
    // Held here until the PIN lands; handleVerifyPin reads it back.
    setPendingField(field)
    setPin('')
    setPinError(null)
    setPinOpen(true)
  }

  const handleVerifyPin = async () => {
    if (pin.length !== 4) return
    setPinError(null)
    setPinChecking(true)
    try {
      const staff = await api.get('/settings/staff')
      const owner = (staff.data.staff ?? []).find((u: any) => u.role === 'owner')
      if (!owner) {
        const msg = t('billing.toast.ownerNotSet')
        setPinError(msg)
        toast.error(t('billing.toast.pinBlocked'), msg)
        return
      }
      await api.post('/auth/verify-pin', { user_id: owner.id, pin: pin.trim() })
      setPinOk(true)
      setPinOpen(false)
      if (pendingField) {
        void flipRule(pendingField)
        setPendingField(null)
      }
      if (pendingSchedule) {
        void saveSchedule(pendingSchedule)
        setPendingSchedule(null)
      }
      setPin('')
      toast.success(t('billing.toast.ownerVerified'), t('billing.toast.unlocked'))
    } catch (err: any) {
      const msg = err?.response?.status === 401 ? t('billing.toast.invalidPin') : t('billing.toast.verificationFailed')
      setPinError(msg)
      toast.error(t('billing.toast.pinBlocked'), msg)
    } finally {
      setPinChecking(false)
    }
  }

  /**
   * Whether the payout schedule on this screen may be changed.
   *
   * Owner-only, matching the billing rules beside it and the `settings.manage`
   * requirement on the endpoint. A staff login that reached this card sees the
   * stored cadence and cannot move it.
   */
  const canEditSchedule = userRole === 'owner'
  /** True while the controls hold a cadence the server has not been told about. */
  const scheduleDirty = isDraftDirty(schedDraft, sched)
  /** The payday the server reports for what is stored — never for a draft. */
  const storedNext = sched?.next_payout_date ?? null

  return (
    <div className="flex flex-col gap-5 max-w-xl">
      {/* The money rules, as the server holds them. Every one of these is a
          column on academy_settings that the money paths read live, so this
          card is a view onto that row and nothing else. */}
      <Card>
        <CardHeader title={t('billing.rules.title')} />
        <CardBody>
          {/* Academy gross-profit opt-in */}
          <div className="flex items-center justify-between gap-3 pb-4 mb-4 border-b border-[var(--glass-border)]">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[var(--text)]">
                {t('billing.grossProfit.label')}
              </p>
              <p className="text-xs text-[var(--muted)] mt-1 leading-relaxed">
                {t('billing.grossProfit.hint')}
              </p>
            </div>
            <Toggle
              checked={grossAcademy}
              onCheckedChange={(v) => { setGrossProfitEnabled(v); setGrossAcademy(v) }}
            />
          </div>

          {/* Every rule the server stores, written straight to it. Owner PIN only. */}
          <div className="flex items-center justify-between gap-2 mb-3">
            <p className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider">
              {t('billing.rules.ownerOnlyHeader')}
            </p>
            {pinOk ? (
              <span className="text-[10px] font-semibold text-[var(--emerald)] bg-[var(--emerald-soft)] px-2 py-0.5 rounded-full">
                {t('billing.rules.ownerVerified')}
              </span>
            ) : (
              <button
                type="button"
                onClick={() => { setPendingField(null); setPin(''); setPinError(null); setPinOpen(true) }}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--gold)] hover:underline"
              >
                <Lock size={11} />
                {t('billing.rules.verifyOwnerPin')}
              </button>
            )}
          </div>

          {rulesError && (
            <div className="flex items-start gap-2 rounded-xl bg-[var(--red-soft)]/30 px-3 py-2.5 mb-3">
              <p className="text-[11px] text-[var(--red)] leading-relaxed flex-1">
                {rulesError} {t('billing.rules.defaultsNotice')}
              </p>
              <button
                type="button"
                onClick={() => void loadRules()}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--gold)] hover:underline shrink-0"
              >
                <RefreshCw size={11} />
                {t('common:action.retry')}
              </button>
            </div>
          )}

          <div className="space-y-3">
            {RULE_ROWS.map((row) => {
              const on = rules[row.field]
              const busy = savingRule === row.field
              return (
                <div key={row.field} className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-[var(--text)]">{t(row.labelKey)}</p>
                    <p className="text-xs text-[var(--muted)] mt-0.5 leading-relaxed">{t(row.hintKey)}</p>
                    <p className="text-[11px] text-[var(--muted)] mt-1">
                      {busy
                        ? t('common:state.saving')
                        : rulesLoaded
                          ? t('billing.rules.stateServer', { state: on ? t('billing.rules.onUpper') : t('billing.rules.offUpper') })
                          : t('billing.rules.stateDefault', { state: on ? t('billing.rules.onUpper') : t('billing.rules.offUpper') })}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => requestFlip(row.field)}
                    disabled={busy}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium shrink-0',
                      'border transition-all duration-150 disabled:opacity-50',
                      on
                        ? 'bg-[var(--emerald-soft)] border-[var(--emerald)]/30 text-[var(--emerald)]'
                        : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)]',
                    )}
                    // The tooltip names the rule in the desk's own words. It used
                    // to print `row.field`, which is the column name the server
                    // reads (`absence_consumes_credit`) — correct for a log, not
                    // for a label someone reads in Arabic.
                    title={t('billing.rules.toggleTitle', { field: t(row.labelKey) })}
                  >
                    <span className={cn(
                      'w-8 h-4 rounded-full relative transition-colors duration-200',
                      on ? 'bg-[var(--emerald)]' : 'bg-[var(--muted)]/30',
                    )}>
                      {/* The knob travels along the inline axis, so the track
                          fills from the start edge in Arabic too. */}
                      <span className={cn(
                        'absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all duration-200',
                        on ? 'start-4.5' : 'start-0.5',
                      )} />
                    </span>
                    {on ? t('billing.rules.on') : t('billing.rules.off')}
                  </button>
                </div>
              )
            })}
          </div>

          <p className="text-[11px] text-[var(--muted)] mt-3 leading-relaxed">
            {t('billing.rules.footnote')}
          </p>

          {/* Guest swap window — the server has no column for this one. */}
          <div className="mt-4 pt-4 border-t border-[var(--glass-border)]">
            <p className="text-sm font-semibold text-[var(--text)]">{t('billing.swap.title')}</p>
            <p className="text-xs text-[var(--muted)] mt-0.5 leading-relaxed">
              {t('billing.swap.hint')}
            </p>
            <div className="flex rounded-xl overflow-hidden border border-[var(--glass-border)] mt-2">
              {(['SAME_DAY', 'OPEN'] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => { setSwapWindow(v); setSwapWindowState(v) }}
                  className={cn(
                    'flex-1 py-2 text-xs font-semibold transition-all duration-150',
                    swapWindow === v
                      ? 'bg-gradient-to-r from-[#b3872a] to-[#0f6b4d] text-white'
                      : 'bg-[var(--input-bg)] text-[var(--muted)] hover:bg-[var(--glass)]',
                  )}
                >
                  {v === 'SAME_DAY' ? t('billing.swap.sameDay') : t('billing.swap.open7d')}
                </button>
              ))}
            </div>
          </div>

          {/* Owner PIN gate */}
          {pinOpen && (
            <div
              className="fixed inset-0 z-[80] flex items-center justify-center"
              style={{ background: 'rgba(10,10,10,.6)', backdropFilter: 'blur(8px)' }}
              onClick={(e) => { if (e.target === e.currentTarget) { setPinOpen(false); setPendingField(null) } }}
            >
              <div className="w-full max-w-xs mx-4 rounded-2xl bg-[var(--card-bg)] border border-[var(--glass-border)] shadow-2xl p-5">
                <p className="text-sm font-bold text-[var(--text)] mb-1">{t('billing.pin.title')}</p>
                <p className="text-[11px] text-[var(--muted)] mb-3">{t('billing.pin.hint')}</p>
                <input
                  type="password"
                  inputMode="numeric"
                  maxLength={4}
                  value={pin}
                  onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
                  placeholder="••••"
                  className={cn(inputCls, 'text-center tracking-[0.3em]')}
                />
                {pinError && <p className="text-xs text-[var(--red)] mt-2">{pinError}</p>}
                <button
                  type="button"
                  onClick={() => void handleVerifyPin()}
                  disabled={pin.length !== 4 || pinChecking}
                  className="mt-3 w-full py-2.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-[#b3872a] to-[#0f6b4d] hover:opacity-90 disabled:opacity-40 transition-all"
                >
                  {pinChecking ? t('billing.pin.verifying') : t('billing.pin.verify')}
                </button>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Currency */}
      <Card>
        <CardHeader title={t('billing.currency.title')} />
        <CardBody>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-[var(--text)] font-[family-name:var(--font-heading)]">
              {t('billing.currency.label')}
            </label>
            <div className="flex gap-2 flex-wrap">
              {CURRENCY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => handleChange('currency', opt.value)}
                  className={cn(
                    'px-4 py-2 text-sm font-medium rounded-[var(--radius-xs)]',
                    'border transition-all duration-200',
                    form.currency === opt.value
                      ? 'bg-[var(--gold-soft)] border-[var(--gold)] text-[var(--gold)]'
                      : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)]',
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Money Model Defaults */}
      <Card>
        <CardHeader title={t('billing.moneyModel.title')} />
        <CardBody>
          <p className="text-sm text-[var(--muted)] mb-4">
            {t('billing.moneyModel.hint')}
          </p>
          <div className="grid grid-cols-2 gap-4">
            {/* Credits per cycle */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-[var(--muted)] flex items-center gap-1.5">
                <Coins size={12} />
                {t('billing.moneyModel.creditsPerCycle')}
              </label>
              <input
                type="number"
                value={form.default_credits_per_cycle}
                onChange={(e) => handleChange('default_credits_per_cycle', Number(e.target.value))}
                min={1}
                className={cn(inputCls)}
              />
              {/* CREDIT_BASED is the server's own word for the group type; the
                  desk reads a label for it, not the enum. */}
              <span className="text-[10px] text-[var(--muted)]">
                {t('billing.moneyModel.forCreditBased', { type: t('billing.groupType.creditBased') })}
              </span>
            </div>

            {/* Max groups included */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-[var(--muted)] flex items-center gap-1.5">
                <Users size={12} />
                {t('billing.moneyModel.maxGroups')}
              </label>
              <input
                type="number"
                value={form.default_max_groups}
                onChange={(e) => handleChange('default_max_groups', Number(e.target.value))}
                min={1}
                max={10}
                className={cn(inputCls)}
              />
            </div>

            {/* Default access weeks */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-[var(--muted)] flex items-center gap-1.5">
                <Clock size={12} />
                {t('billing.moneyModel.accessDuration')}
              </label>
              <input
                type="number"
                value={form.default_access_weeks ?? ''}
                onChange={(e) => handleChange('default_access_weeks', e.target.value ? Number(e.target.value) : null)}
                min={1}
                placeholder={t('billing.moneyModel.notSet')}
                className={cn(inputCls)}
              />
              <span className="text-[10px] text-[var(--muted)]">
                {t('billing.moneyModel.forTimeBased', { type: t('billing.groupType.timeBased') })}
              </span>
            </div>

            {/* Allow Rollover */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-[var(--muted)]">{t('billing.moneyModel.creditRollover')}</label>
              <button
                type="button"
                onClick={() => handleChange('allow_rollover_default', !form.allow_rollover_default)}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium',
                  'border transition-all duration-150 text-start',
                  form.allow_rollover_default
                    ? 'bg-[var(--emerald-soft)] border-[var(--emerald)]/30 text-[var(--emerald)]'
                    : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)]',
                )}
              >
                <span className={cn(
                  'w-8 h-4 rounded-full relative transition-colors duration-200',
                  form.allow_rollover_default ? 'bg-[var(--emerald)]' : 'bg-[var(--muted)]/30',
                )}>
                  <span className={cn(
                    'absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all duration-200',
                    form.allow_rollover_default ? 'start-4.5' : 'start-0.5',
                  )} />
                </span>
                {form.allow_rollover_default ? t('billing.rules.on') : t('billing.rules.off')}
              </button>
            </div>

            {/* Allow Makeups */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-[var(--muted)]">{t('billing.moneyModel.makeupSessions')}</label>
              <button
                type="button"
                onClick={() => handleChange('allow_makeups_default', !form.allow_makeups_default)}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium',
                  'border transition-all duration-150 text-start',
                  form.allow_makeups_default
                    ? 'bg-[var(--emerald-soft)] border-[var(--emerald)]/30 text-[var(--emerald)]'
                    : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)]',
                )}
              >
                <span className={cn(
                  'w-8 h-4 rounded-full relative transition-colors duration-200',
                  form.allow_makeups_default ? 'bg-[var(--emerald)]' : 'bg-[var(--muted)]/30',
                )}>
                  <span className={cn(
                    'absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all duration-200',
                    form.allow_makeups_default ? 'start-4.5' : 'start-0.5',
                  )} />
                </span>
                {form.allow_makeups_default ? t('billing.rules.on') : t('billing.rules.off')}
              </button>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Plan Duration — Preset System */}
      <Card>
        <CardHeader title={t('billing.planDuration.title')} />
        <CardBody>
          <p className="text-sm text-[var(--muted)] mb-3">
            {t('billing.planDuration.hint')}
          </p>

          {/* Preset grid */}
          <div className="flex gap-2 flex-wrap mb-3">
            {presets.map((preset) => (
              <div
                key={preset.id}
                className={cn(
                  'group relative flex items-center gap-1.5',
                  'px-4 py-2 text-sm font-medium rounded-[var(--radius-xs)]',
                  'border transition-all duration-200',
                  form.default_plan_duration === preset.days
                    ? 'bg-[var(--gold-soft)] border-[var(--gold)] text-[var(--gold)]'
                    : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)]',
                )}
              >
                <button
                  type="button"
                  onClick={() => handleChange('default_plan_duration', preset.days)}
                  className="flex-1 text-start"
                >
                  {presetLabel(preset)} <span className="opacity-50 text-xs">{t('billing.preset.daysShort', { count: preset.days })}</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleRemovePreset(preset.id)}
                  className={cn(
                    'shrink-0 p-0.5 rounded',
                    'opacity-0 group-hover:opacity-100',
                    'hover:bg-[var(--red-soft)] text-[var(--muted)] hover:text-[var(--red)]',
                    'transition-all duration-150',
                  )}
                  aria-label={t('billing.preset.remove', { label: presetLabel(preset) })}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>

          {/* Create Preset */}
          {!showAddPreset ? (
            <button
              type="button"
              onClick={() => setShowAddPreset(true)}
              className={cn(
                'px-3 py-2 text-sm font-medium rounded-[var(--radius-xs)]',
                'border border-dashed border-[var(--muted)]/30',
                'text-[var(--muted)] hover:text-[var(--text)]',
                'hover:border-[var(--muted)]/60 hover:bg-[var(--input-bg)]',
                'transition-all duration-200',
              )}
            >
              <Plus size={14} className="inline me-1" />
              {t('billing.planDuration.create')}
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newPresetLabel}
                onChange={(e) => setNewPresetLabel(e.target.value)}
                placeholder={t('billing.planDuration.labelPlaceholder')}
                className={cn(
                  'px-3 py-1.5 text-sm rounded-[var(--radius-xs)]',
                  'bg-[var(--input-bg)] border border-[var(--glass-border)]',
                  'text-[var(--text)] placeholder:text-[var(--muted)]/50',
                  'outline-none focus:ring-1 focus:ring-[var(--gold)]/30',
                  'w-36',
                )}
              />
              <input
                type="number"
                value={newPresetDays}
                onChange={(e) => setNewPresetDays(e.target.value)}
                placeholder={t('billing.planDuration.daysPlaceholder')}
                min={1}
                className={cn(
                  'px-3 py-1.5 text-sm rounded-[var(--radius-xs)]',
                  'bg-[var(--input-bg)] border border-[var(--glass-border)]',
                  'text-[var(--text)] placeholder:text-[var(--muted)]/50',
                  'outline-none focus:ring-1 focus:ring-[var(--gold)]/30',
                  'w-20',
                )}
              />
              <button
                type="button"
                onClick={handleAddPreset}
                disabled={!newPresetLabel.trim() || !newPresetDays}
                className={cn(
                  'px-2.5 py-1.5 text-sm font-medium rounded-[var(--radius-xs)]',
                  'bg-[var(--gold)] text-white',
                  'hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed',
                  'transition-all duration-200',
                )}
              >
                {t('common:action.add')}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowAddPreset(false)
                  setNewPresetLabel('')
                  setNewPresetDays('')
                }}
                className="p-1.5 rounded-[var(--radius-xs)] hover:bg-[var(--input-bg)] text-[var(--muted)] transition-colors"
              >
                <X size={14} />
              </button>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Payout Schedule — the day teachers are paid, and what starts the clock */}
      <Card>
        <CardHeader title={t('billing.payoutSchedule.title')} />
        <CardBody>
          <p className="text-sm text-[var(--muted)] mb-3">
            {t('billing.payoutSchedule.hint')}
          </p>

          {schedError ? (
            <div className="flex items-start gap-2">
              <p className="text-sm text-[var(--muted)] flex-1">{schedError}</p>
              <button
                type="button"
                onClick={() => void loadSchedule()}
                className="shrink-0 text-sm font-medium text-[var(--gold)] hover:underline"
              >
                {t('common:action.retry')}
              </button>
            </div>
          ) : (
            <>
              {/* How often the payday comes round */}
              <div className="flex gap-2 flex-wrap mb-3">
                {PAYOUT_CADENCES.map((cadence) => (
                  <button
                    key={cadence}
                    type="button"
                    disabled={!canEditSchedule}
                    onClick={() => setCadence(cadence)}
                    className={cn(
                      'flex-1 px-4 py-2 text-sm font-medium rounded-[var(--radius-xs)]',
                      'border transition-all duration-200 text-start',
                      schedDraft.cadence === cadence
                        ? 'bg-[var(--gold-soft)] border-[var(--gold)] text-[var(--gold)]'
                        : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)]',
                      !canEditSchedule && 'opacity-60 cursor-default',
                    )}
                  >
                    <span className="block">
                      {t(`billing.payoutSchedule.cadence.${CADENCE_KEY[cadence]}`)}
                    </span>
                    <span
                      className={cn(
                        'block text-[11px] mt-0.5',
                        schedDraft.cadence === cadence
                          ? 'text-[var(--gold)]/70'
                          : 'text-[var(--muted)]/60',
                      )}
                    >
                      {t(`billing.payoutSchedule.cadence.${CADENCE_KEY[cadence]}Hint`)}
                    </span>
                  </button>
                ))}
              </div>

              {/* Which weekday, for a weekly cadence */}
              {schedDraft.cadence === 'WEEKLY' && (
                <div className="mb-3">
                  <p className="text-xs font-medium text-[var(--muted)] mb-1.5">
                    {t('billing.payoutSchedule.weekdayLabel')}
                  </p>
                  <div className="flex gap-1.5 flex-wrap">
                    {WEEKDAYS.map((day) => (
                      <button
                        key={day.value}
                        type="button"
                        disabled={!canEditSchedule}
                        onClick={() => {
                          schedTouched.current = true
                          setSchedDraft((prev) => ({ ...prev, day_of_week: day.value }))
                        }}
                        className={cn(
                          'px-3 py-1.5 text-sm font-medium rounded-[var(--radius-xs)]',
                          'border transition-all duration-200',
                          schedDraft.day_of_week === day.value
                            ? 'bg-[var(--gold-soft)] border-[var(--gold)] text-[var(--gold)]'
                            : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)]',
                          !canEditSchedule && 'opacity-60 cursor-default',
                        )}
                      >
                        {/* The short form from the academy's own day names,
                            not the long one: seven full weekday names in the
                            app's language do not fit on one row, and a payday
                            picker that wraps is a payday picker nobody reads. */}
                        {t(`academy.day.${day.key}`)}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Which date, for a monthly cadence */}
              {schedDraft.cadence === 'MONTHLY' && (
                <div className="mb-3">
                  <p className="text-xs font-medium text-[var(--muted)] mb-1.5">
                    {t('billing.payoutSchedule.dayOfMonthLabel')}
                  </p>
                  <input
                    type="number"
                    min={1}
                    max={31}
                    disabled={!canEditSchedule}
                    value={schedDraft.day_of_month ?? ''}
                    placeholder={t('billing.payoutSchedule.dayOfMonthPlaceholder')}
                    onChange={(e) => {
                      const raw = e.target.value
                      schedTouched.current = true
                      if (raw === '') {
                        setSchedDraft((prev) => ({ ...prev, day_of_month: null }))
                        return
                      }
                      const n = Number(raw)
                      // Refused rather than clamped: silently turning a typed
                      // 45 into 31 would put a payday on the screen that nobody
                      // asked for, and the person would have no way to tell.
                      if (Number.isInteger(n) && n >= 1 && n <= 31) {
                        setSchedDraft((prev) => ({ ...prev, day_of_month: n }))
                      }
                    }}
                    className={cn(inputCls, 'w-24', !canEditSchedule && 'opacity-60 cursor-default')}
                  />
                  {mayClampToMonthEnd(schedDraft) && (
                    <p className="text-[11px] text-[var(--muted)] mt-1">
                      {t('billing.payoutSchedule.clampNote')}
                    </p>
                  )}
                </div>
              )}

              <div className="pt-3 border-t border-[var(--glass-border)]">
                {scheduleDirty ? (
                  /* The unsaved choice, said back in words so the sentence is
                     read before the button is pressed rather than after. */
                  <p className="text-sm text-[var(--gold)] mb-3">
                    {describeDraft(t, schedDraft)}
                  </p>
                ) : schedLoaded ? (
                  <div className="mb-3">
                    <p className="text-sm text-[var(--text)]">
                      {t('billing.payoutSchedule.current', {
                        cadence: describeCadence(t, sched),
                      })}
                    </p>
                    <p className="text-[11px] text-[var(--muted)] mt-0.5">
                      {storedNext
                        ? t('billing.payoutSchedule.next', { date: formatDateFull(storedNext) })
                        : t('billing.payoutSchedule.nextNone')}
                    </p>
                  </div>
                ) : null}

                {!canEditSchedule && (
                  <p className="text-[11px] text-[var(--muted)] mb-2">
                    {t('billing.payoutSchedule.ownerNote')}
                  </p>
                )}

                <button
                  type="button"
                  disabled={
                    !canEditSchedule || !scheduleDirty || !isDraftComplete(schedDraft) || savingSched
                  }
                  onClick={() => requestScheduleSave(schedDraft)}
                  className={cn(
                    'px-4 py-2 text-sm font-medium rounded-[var(--radius-xs)]',
                    'bg-[var(--gold)] text-white',
                    'hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed',
                    'transition-all duration-200',
                  )}
                >
                  {savingSched ? t('common:state.saving') : t('billing.payoutSchedule.save')}
                </button>
              </div>
            </>
          )}
        </CardBody>
      </Card>

      {/* Reminder Days */}
      <Card>
        <CardHeader title={t('billing.reminders.title')} />
        <CardBody>
          <p className="text-sm text-[var(--muted)] mb-3">
            {t('billing.reminders.hint')}
          </p>
          <div className="flex gap-2 flex-wrap">
            {REMINDER_PRESETS.map((days) => (
              <button
                key={days}
                type="button"
                onClick={() => handleChange('billing_reminder_days_before', days)}
                className={cn(
                  'px-4 py-2 text-sm font-medium rounded-[var(--radius-xs)]',
                  'border transition-all duration-200',
                  form.billing_reminder_days_before === days
                    ? 'bg-[var(--gold-soft)] border-[var(--gold)] text-[var(--gold)]'
                    : 'bg-[var(--input-bg)] border-[var(--glass-border)] text-[var(--muted)] hover:text-[var(--text)]',
                )}
              >
                {t('billing.reminders.days', { count: days })}
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* WhatsApp Template */}
      <Card>
        <CardHeader title={t('billing.whatsapp.title')} />
        <CardBody>
          {/* The template's own placeholders are passed back in as values so
              i18next hands them through untouched instead of interpolating
              them away — they are WhatsApp's syntax, not ours. */}
          <p className="text-sm text-[var(--muted)] mb-3">
            {t('billing.whatsapp.hint', WHATSAPP_PLACEHOLDERS)}
          </p>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <textarea
                value={form.whatsapp_template}
                onChange={(e) => handleChange('whatsapp_template', e.target.value)}
                rows={5}
                className={cn(
                  'w-full px-4 py-3 text-sm rounded-[var(--radius-sm)]',
                  'bg-[var(--input-bg)] backdrop-blur-sm',
                  'border border-[var(--glass-border)]',
                  'text-[var(--text)] placeholder:text-[var(--muted)]',
                  'font-[family-name:var(--font-body)]',
                  'resize-none',
                  'transition-shadow duration-200',
                  'focus:outline-none focus:ring-2 focus:ring-[var(--gold-soft)] focus:border-[var(--gold)]',
                )}
                placeholder={t('billing.whatsapp.placeholder', WHATSAPP_PLACEHOLDERS)}
              />
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Save */}
      <div className="flex items-center gap-3">
        <Button
          onClick={handleSave}
          loading={isSaving}
          variant="primary"
        >
          <Save className="w-4 h-4" />
          {t('billing.action.save')}
        </Button>
        {saved && (
          <span className="text-sm text-[var(--emerald)] font-medium animate-fade-in">
            {t('billing.saved')}
          </span>
        )}
      </div>
    </div>
  )
}

const inputCls = cn(
  'w-full px-3 py-2 rounded-xl text-sm text-[var(--text)]',
  'bg-[var(--input-bg)] border border-[var(--glass-border)]',
  'outline-none focus:ring-2 focus:ring-[var(--gold)]/30',
  'placeholder:text-[var(--muted)]/50',
  'transition-shadow duration-150',
)

export default BillingConfig
