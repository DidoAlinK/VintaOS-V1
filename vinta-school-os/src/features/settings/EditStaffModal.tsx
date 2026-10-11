/**
 * Vinta School OS — Edit Staff Modal
 *
 * Changes one person's details, their way in, and what they may do.
 *
 * ── Why the password is blank unless it is being replaced ──
 *
 * The server never sends a password back — it only holds a hash, and it always
 * will. So the field opens empty and *staying* empty means "leave it alone".
 * Typing into it means "replace it", which is why an unchanged form sends no
 * `password` key at all rather than sending an empty string: one is a no-op and
 * the other would be a refusal, or worse, a blank password.
 *
 * ── Why the owner's row has no editor ──
 *
 * An owner holds everything by virtue of the role; nothing written to a
 * permission column can add to or take from it. The server refuses the write
 * for that reason, so the screen shows what the role means rather than offering
 * switches that could not change anything.
 */

import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Pencil, KeyRound } from 'lucide-react'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import PermissionEditor from './PermissionEditor'
import {
  defaultGrant,
  normalizeGrant,
  localCatalogue,
  type PermissionGrant,
  type PermissionsCatalogue,
} from '../../lib/permissions'
import type { StaffMember } from '../../types/settings'

// ============================================
// Props
// ============================================

export interface EditStaffModalProps {
  member: StaffMember | null
  onClose: () => void
  onSaved: () => void
  catalogue?: PermissionsCatalogue
}

// ============================================
// Component
// ============================================

export default function EditStaffModal({ member, onClose, onSaved, catalogue }: EditStaffModalProps) {
  const { t } = useTranslation('settings')

  // Seeded from the member being edited, and re-seeded by the `key` the caller
  // sets on this component rather than by an effect: opening a different person
  // remounts the form, which is the one thing that guarantees one member's
  // details are never left sitting under another's name.
  const [name, setName] = useState(member?.name ?? '')
  const [phone, setPhone] = useState(member?.phone ?? '')
  const [email, setEmail] = useState(member?.email ?? '')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [grant, setGrant] = useState<PermissionGrant>(() =>
    member?.permissions ? normalizeGrant(member.permissions, 'staff') : defaultGrant(),
  )
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const effectiveCatalogue = catalogue ?? localCatalogue()
  const isOwnerRow = member?.role === 'owner'

  const handleClose = useCallback(() => {
    setPassword('')
    setConfirmPassword('')
    setError('')
    onClose()
  }, [onClose])

  const handleSubmit = useCallback(async () => {
    if (!member) return
    setError('')

    if (!name.trim()) {
      setError(t('addStaff.error.nameRequired'))
      return
    }
    // Only checked when something was typed: an untouched field means "leave
    // the password as it is", not "set it to empty".
    if (password) {
      if (password.length < 8 || password.length > 72) {
        setError(t('addStaff.error.passwordLength'))
        return
      }
      if (password !== confirmPassword) {
        setError(t('addStaff.error.passwordMismatch'))
        return
      }
      if (!email.trim()) {
        setError(t('addStaff.error.emailRequiredWithPassword'))
        return
      }
    }

    setIsSubmitting(true)
    try {
      const body: Record<string, unknown> = {
        name: name.trim(),
        phone: phone.trim(),
        email: email.trim(),
      }
      if (password) body.password = password
      // The owner's grant is not sent: the server refuses it, and the editor
      // is not shown for that row anyway.
      if (!isOwnerRow) body.permissions = grant

      await api.put(`/settings/staff/${member.id}`, body)
      onSaved()
      handleClose()
    } catch (err: unknown) {
      const e = err as { message?: string; response?: { data?: { error?: string } } }
      setError(e.response?.data?.error || e.message || t('editStaff.error.failed'))
    } finally {
      setIsSubmitting(false)
    }
  }, [member, name, phone, email, password, confirmPassword, grant, isOwnerRow, t, onSaved, handleClose])

  if (!member) return null

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
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 shrink-0 rounded-lg bg-[var(--gold-soft)] flex items-center justify-center">
              <Pencil size={16} className="text-[var(--gold)]" />
            </div>
            <div className="min-w-0">
              <h2
                className="text-lg font-bold text-[var(--text)] truncate"
                style={{ fontFamily: 'var(--font-heading)' }}
              >
                {t('editStaff.title')}
              </h2>
              <p className="text-xs text-[var(--muted)] truncate">{member.name}</p>
            </div>
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

        <div className="space-y-4">
          {/* Name */}
          <Field label={t('common:label.name')} required>
            <input
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); setError('') }}
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

          {/* Login address */}
          <div className="pt-4 border-t border-[var(--glass-border)]">
            <div className="flex items-center gap-2 mb-1">
              <KeyRound className="w-3.5 h-3.5 text-[var(--muted)]" />
              <span className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider">
                {t('editStaff.login.title')}
              </span>
            </div>
            <p className="text-[11px] text-[var(--muted)] mb-3">
              {t('editStaff.login.hint')}
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
                <Field label={t('editStaff.login.newPassword')}>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setError('') }}
                    placeholder={t('editStaff.login.passwordPlaceholder')}
                    autoComplete="new-password"
                    className={inputCls}
                  />
                </Field>
                <Field label={t('addStaff.login.confirmPassword')}>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => { setConfirmPassword(e.target.value); setError('') }}
                    placeholder={t('editStaff.login.passwordPlaceholder')}
                    autoComplete="new-password"
                    className={inputCls}
                  />
                </Field>
              </div>
            </div>
          </div>

          {/* Permissions */}
          <div className="pt-4 border-t border-[var(--glass-border)]">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider">
                {t('permissions.title')}
              </span>
              {!isOwnerRow && (
                <button
                  type="button"
                  onClick={() => setGrant(defaultGrant())}
                  className="text-[11px] font-medium text-[var(--gold)] hover:underline"
                >
                  {t('permissions.resetToDefault')}
                </button>
              )}
            </div>

            {isOwnerRow ? (
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
            disabled={!name.trim() || isSubmitting}
            className={cn(
              'flex-1 py-2.5 rounded-xl text-sm font-semibold text-white',
              'bg-gradient-to-r from-[#b3872a] to-[#0f6b4d]',
              'hover:opacity-90 active:scale-[0.98]',
              'disabled:opacity-40 disabled:cursor-not-allowed',
              'transition-all duration-150',
            )}
          >
            {isSubmitting ? t('editStaff.saving') : t('editStaff.save')}
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

const inputCls = cn(
  'w-full px-3 py-2 rounded-xl text-sm text-[var(--text)]',
  'bg-[var(--input-bg)] border border-[var(--glass-border)]',
  'outline-none focus:ring-2 focus:ring-[var(--gold)]/30',
  'placeholder:text-[var(--muted)]/50',
  'transition-shadow duration-150',
)
