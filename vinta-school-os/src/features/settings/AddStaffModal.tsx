/**
 * Vinta School OS — Add Staff Modal
 *
 * Creates a staff profile: who they are, how they sign in, and what they may
 * do.
 *
 * ── How they sign in ──
 *
 * A PIN alone, chosen at the profile picker, is what every staff profile used
 * to be and is still the default. An address and a password are the optional
 * second way in, and they go together — the server refuses one without the
 * other, and this form refuses it first so the two cannot disagree about which
 * was meant.
 *
 * ── What they may do ──
 *
 * The editor opens on the documented staff default: day-to-day work — students,
 * classes, attendance, the calendar — and no money and no settings. The owner
 * widens it deliberately rather than narrowing it, so a profile created in a
 * hurry is never accidentally powerful.
 */

import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, UserPlus, KeyRound } from 'lucide-react'
import { cn } from '../../lib/cn'
import { useAuthStore } from '../../stores/authStore'
import PermissionEditor from './PermissionEditor'
import {
  defaultGrant,
  localCatalogue,
  type PermissionGrant,
  type PermissionsCatalogue,
} from '../../lib/permissions'

// ============================================
// Props
// ============================================

export interface AddStaffModalProps {
  isOpen: boolean
  onClose: () => void
  onAdded: () => void
  /** Served catalogue; the local mirror stands in when absent. */
  catalogue?: PermissionsCatalogue
}

// ============================================
// Component
// ============================================

export default function AddStaffModal({ isOpen, onClose, onAdded, catalogue }: AddStaffModalProps) {
  const { t } = useTranslation('settings')
  const createProfile = useAuthStore((s) => s.createProfile)

  const [name, setName] = useState('')
  const [pin, setPin] = useState('')
  const [confirmPin, setConfirmPin] = useState('')
  const [phone, setPhone] = useState('')
  const [ownerPin, setOwnerPin] = useState('')
  const [role, setRole] = useState<'owner' | 'staff'>('staff')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [grant, setGrant] = useState<PermissionGrant>(() => defaultGrant())
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const effectiveCatalogue = useMemo(() => catalogue ?? localCatalogue(), [catalogue])

  const resetForm = useCallback(() => {
    setName('')
    setPin('')
    setConfirmPin('')
    setPhone('')
    setOwnerPin('')
    setRole('staff')
    setEmail('')
    setPassword('')
    setConfirmPassword('')
    setGrant(defaultGrant())
    setError('')
  }, [])

  const handleClose = useCallback(() => {
    resetForm()
    onClose()
  }, [onClose, resetForm])

  /** The login pair, checked as a pair — the server's rule, said earlier. */
  const loginProblem = useCallback((): string | null => {
    const hasEmail = email.trim().length > 0
    const hasPassword = password.length > 0
    if (hasEmail && !hasPassword) return t('addStaff.error.passwordRequiredWithEmail')
    if (!hasEmail && hasPassword) return t('addStaff.error.emailRequiredWithPassword')
    if (hasPassword && (password.length < 8 || password.length > 72)) {
      return t('addStaff.error.passwordLength')
    }
    if (hasPassword && password !== confirmPassword) return t('addStaff.error.passwordMismatch')
    return null
  }, [email, password, confirmPassword, t])

  const handleSubmit = useCallback(async () => {
    setError('')

    if (!name.trim()) {
      setError(t('addStaff.error.nameRequired'))
      return
    }
    if (pin.length !== 4) {
      setError(t('addStaff.error.pinLength'))
      return
    }
    if (pin !== confirmPin) {
      setError(t('addStaff.error.pinMismatch'))
      return
    }
    const loginIssue = loginProblem()
    if (loginIssue) {
      setError(loginIssue)
      return
    }
    if (!ownerPin || ownerPin.length !== 4) {
      setError(t('addStaff.error.ownerPinRequired'))
      return
    }

    setIsSubmitting(true)
    try {
      await createProfile({
        name: name.trim(),
        role,
        pin,
        phone: phone.trim() || undefined,
        avatar_color_1: '#b3872a',
        avatar_color_2: '#0f6b4d',
        owner_pin: ownerPin,
        email: email.trim() || undefined,
        password: password || undefined,
        // Not sent for an owner: the role already holds everything and the
        // server refuses a grant on one, so sending it would only turn a
        // successful creation into a 400.
        permissions: role === 'owner' ? undefined : grant,
      })
      resetForm()
      onAdded()
      onClose()
    } catch (err: unknown) {
      const e = err as { message?: string; response?: { data?: { error?: string } } }
      setError(e.response?.data?.error || e.message || t('addStaff.error.failed'))
    } finally {
      setIsSubmitting(false)
    }
  }, [
    t, name, pin, confirmPin, phone, ownerPin, role, email, password,
    grant, loginProblem, createProfile, resetForm, onAdded, onClose,
  ])

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(10,10,10,.6)', backdropFilter: 'blur(8px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}
    >
      <div
        className={cn(
          'w-full max-w-lg max-h-[90vh] overflow-y-auto p-6 rounded-2xl',
          'bg-[var(--card-bg)] border border-[var(--glass-border)]',
          'shadow-2xl animate-fade-in',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[var(--emerald-soft)] flex items-center justify-center">
              <UserPlus size={16} className="text-[var(--emerald)]" />
            </div>
            <h2
              className="text-lg font-bold text-[var(--text)]"
              style={{ fontFamily: 'var(--font-heading)' }}
            >
              {t('addStaff.title')}
            </h2>
          </div>
          <button
            onClick={handleClose}
            aria-label={t('common:action.close')}
            className={cn(
              'p-1.5 rounded-lg text-[var(--muted)]',
              'hover:bg-[var(--glass)] hover:text-[var(--text)]',
              'transition-colors duration-150',
            )}
          >
            <X size={16} />
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 text-red-500 text-sm font-medium animate-fade-in">
            {error}
          </div>
        )}

        {/* Form */}
        <div className="space-y-4">
          {/* Name */}
          <Field label={t('common:label.name')} required>
            <input
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); setError('') }}
              placeholder={t('addStaff.namePlaceholder')}
              className={inputCls}
            />
          </Field>

          {/* Phone */}
          <Field label={t('common:label.phone')}>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+213 5## ## ## ##"
              className={inputCls}
            />
          </Field>

          {/* Role */}
          <Field label={t('addStaff.role')} required>
            <div className="flex gap-2">
              {(['staff', 'owner'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRole(r)}
                  className={cn(
                    'flex-1 py-2 rounded-xl text-sm font-medium transition-all duration-150',
                    role === r
                      ? r === 'owner'
                        ? 'bg-[var(--gold-soft)] text-[var(--gold)] border border-[var(--gold)]/30'
                        : 'bg-[var(--emerald-soft)] text-[var(--emerald)] border border-[var(--emerald)]/30'
                      : 'bg-[var(--input-bg)] text-[var(--muted)] border border-[var(--glass-border)] hover:border-[var(--muted)]/30',
                  )}
                >
                  {r === 'owner' ? t('addStaff.roleOwner') : t('addStaff.roleStaff')}
                </button>
              ))}
            </div>
          </Field>

          {/* PIN */}
          <div className="grid grid-cols-2 gap-3">
            <Field label={t('addStaff.pin')} required>
              <input
                type="password"
                value={pin}
                onChange={(e) => { setPin(e.target.value.replace(/\D/g, '').slice(0, 4)); setError('') }}
                placeholder="••••"
                maxLength={4}
                className={inputCls}
              />
            </Field>
            <Field label={t('addStaff.confirmPin')} required>
              <input
                type="password"
                value={confirmPin}
                onChange={(e) => { setConfirmPin(e.target.value.replace(/\D/g, '').slice(0, 4)); setError('') }}
                placeholder="••••"
                maxLength={4}
                className={inputCls}
              />
            </Field>
          </div>

          {/* ── Optional second way in ── */}
          <div className="pt-4 border-t border-[var(--glass-border)]">
            <div className="flex items-center gap-2 mb-1">
              <KeyRound className="w-3.5 h-3.5 text-[var(--muted)]" />
              <span className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider">
                {t('addStaff.login.title')}
              </span>
            </div>
            <p className="text-[11px] text-[var(--muted)] mb-3">
              {t('addStaff.login.hint')}
            </p>

            <div className="space-y-3">
              <Field label={t('addStaff.login.email')}>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setError('') }}
                  placeholder="name@example.com"
                  className={inputCls}
                  dir="ltr"
                />
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field label={t('addStaff.login.password')}>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setError('') }}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    className={inputCls}
                  />
                </Field>
                <Field label={t('addStaff.login.confirmPassword')}>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => { setConfirmPassword(e.target.value); setError('') }}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    className={inputCls}
                  />
                </Field>
              </div>
            </div>
          </div>

          {/* ── What they may do ── */}
          <div className="pt-4 border-t border-[var(--glass-border)]">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider">
                {t('permissions.title')}
              </span>
              {role !== 'owner' && (
                <button
                  type="button"
                  onClick={() => setGrant(defaultGrant())}
                  className="text-[11px] font-medium text-[var(--gold)] hover:underline"
                >
                  {t('permissions.resetToDefault')}
                </button>
              )}
            </div>

            {role === 'owner' ? (
              <p className="text-[11px] text-[var(--muted)] mt-2">
                {t('permissions.ownerFullAccess')}
              </p>
            ) : (
              <>
                <p className="text-[11px] text-[var(--muted)] mb-3">{t('permissions.hint')}</p>
                <PermissionEditor value={grant} onChange={setGrant} catalogue={effectiveCatalogue} />
              </>
            )}
          </div>

          {/* Owner PIN */}
          <Field label={t('addStaff.ownerPin')} required>
            <input
              type="password"
              value={ownerPin}
              onChange={(e) => { setOwnerPin(e.target.value.replace(/\D/g, '').slice(0, 4)); setError('') }}
              placeholder={t('addStaff.ownerPinPlaceholder')}
              maxLength={4}
              className={inputCls}
            />
          </Field>
        </div>

        {/* Actions */}
        <div className="flex gap-3 mt-6">
          <button
            onClick={handleClose}
            className={cn(
              'flex-1 py-2.5 rounded-xl text-sm font-medium',
              'bg-[var(--input-bg)] text-[var(--muted)] border border-[var(--glass-border)]',
              'hover:bg-[var(--glass)] transition-colors duration-150',
            )}
          >
            {t('common:action.cancel')}
          </button>
          <button
            onClick={handleSubmit}
            disabled={!name.trim() || pin.length !== 4 || pin !== confirmPin || ownerPin.length !== 4 || isSubmitting}
            className={cn(
              'flex-1 py-2.5 rounded-xl text-sm font-semibold text-white',
              'bg-gradient-to-r from-[#b3872a] to-[#0f6b4d]',
              'hover:opacity-90 active:scale-[0.98]',
              'disabled:opacity-40 disabled:cursor-not-allowed',
              'transition-all duration-150',
            )}
          >
            {isSubmitting ? t('addStaff.submitting') : t('addStaff.submit')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ============================================
// Field wrapper
// ============================================

function Field({
  label,
  required,
  children,
}: {
  label: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="flex items-center gap-1 text-xs font-medium text-[var(--muted)] mb-1.5">
        {label}
        {required && <span className="text-[var(--red)]">*</span>}
      </label>
      {children}
    </div>
  )
}

// ============================================
// Input class
// ============================================

const inputCls = cn(
  'w-full px-3 py-2 rounded-xl text-sm text-[var(--text)]',
  'bg-[var(--input-bg)] border border-[var(--glass-border)]',
  'outline-none focus:ring-2 focus:ring-[var(--gold)]/30',
  'placeholder:text-[var(--muted)]/50',
  'transition-shadow duration-150',
)
