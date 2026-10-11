import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import { toast } from '../../stores/uiStore'
import { usePermissions } from '../../hooks/usePermissions'
import { normalizeCatalogue, type PermissionArea, type PermissionsCatalogue } from '../../lib/permissions'
import type { Academy, AcademySettings, StaffMember } from '../../types/settings'
import Appearance from './Appearance'
import MyAccount from './MyAccount'
import AcademyProfile from './AcademyProfile'
import StaffRoles from './StaffRoles'
import AddStaffModal from './AddStaffModal'
import EditStaffModal from './EditStaffModal'
import BillingConfig from './BillingConfig'
import Automations from './Automations'
import DataExport from './DataExport'
import DangerZone from './DangerZone'
import SubjectsSettings from './SubjectsSettings'
import {
  Palette,
  User,
  Building2,
  Users,
  CreditCard,
  Zap,
  Download,
  AlertTriangle,
  BookOpen,
  ChevronRight,
  Menu,
  X,
} from 'lucide-react'

/* ─── Section definitions ───
   `labelKey` rather than `label`: this table is built at module scope, before
   any language is in play, and the running language can change under it.

   `requires` is the permission a section answers to, or `null` for the three
   that are self-service — a person's own display preferences, their own name
   and PIN, and the academy profile shown read-only. Those stay open to
   everyone, which is what keeps `settings: none` meaning "no academy
   configuration" rather than "no way to change your own password".

   A staff account opens Settings on exactly those three: Appearance and My
   account editable, Academy profile read-only. Everything else is reached by
   granting `settings` a level, so the section list a staff member sees is
   three rows until the owner decides otherwise. */

interface SettingsSection {
  id: string
  labelKey: string
  icon: React.ReactNode
  /** Permission needed to see the section at all; `null` = everyone who is signed in. */
  requires: [PermissionArea, string] | null
  /**
   * Permission needed to *change* anything in the section. Absent means it is
   * always editable.
   *
   * Only the academy profile uses this. Its read is open to everyone and its
   * write is owner-only (`PUT /settings/academy`), so the section can be shown
   * to staff truthfully as a read-only view of the school rather than hidden
   * from them — which is what "the academy is read-only for staff" has to mean
   * on a page that is otherwise theirs.
   */
  editableWith?: [PermissionArea, string]
}

const SECTIONS: SettingsSection[] = [
  // Self-service: every signed-in person's own display preferences and their
  // own account. Never gated — hiding these would leave a staff member unable
  // to change the language they read or the password they sign in with.
  { id: 'appearance', labelKey: 'section.appearance', icon: <Palette className="w-4 h-4" />, requires: null },
  { id: 'account', labelKey: 'section.account', icon: <User className="w-4 h-4" />, requires: null },
  // Visible to all, editable only with `settings: manage`.
  { id: 'academy', labelKey: 'section.academy', icon: <Building2 className="w-4 h-4" />, requires: null, editableWith: ['settings', 'manage'] },
  // Academy configuration. Everything below answers to `settings`, so a staff
  // member with `settings: none` opens Settings on the three sections above and
  // nothing else.
  { id: 'subjects', labelKey: 'section.subjects', icon: <BookOpen className="w-4 h-4" />, requires: ['settings', 'manage'] },
  { id: 'staff', labelKey: 'section.staff', icon: <Users className="w-4 h-4" />, requires: ['settings', 'staff'] },
  { id: 'billing', labelKey: 'section.billing', icon: <CreditCard className="w-4 h-4" />, requires: ['settings', 'manage'] },
  { id: 'automations', labelKey: 'section.automations', icon: <Zap className="w-4 h-4" />, requires: ['settings', 'manage'] },
  { id: 'export', labelKey: 'section.export', icon: <Download className="w-4 h-4" />, requires: ['settings', 'manage'] },
  { id: 'danger', labelKey: 'section.danger', icon: <AlertTriangle className="w-4 h-4" />, requires: ['settings', 'danger'] },
]

/* ─── Component ─── */

export function SettingsPage() {
  const { t } = useTranslation('settings')
  const [activeSection, setActiveSection] = useState('appearance')
  const [academy, setAcademy] = useState<Academy | null>(null)
  const [settings, setSettings] = useState<AcademySettings | null>(null)
  const [staff, setStaff] = useState<StaffMember[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [showAddStaff, setShowAddStaff] = useState(false)
  const [editingStaff, setEditingStaff] = useState<StaffMember | null>(null)
  const [catalogue, setCatalogue] = useState<PermissionsCatalogue | null>(null)

  const { can } = usePermissions()
  const canManageStaff = can('settings', 'staff')
  /** Whether the academy profile may be edited, or only read. */
  const canEditAcademy = can('settings', 'manage')

  const visibleSections = useMemo(
    () => SECTIONS.filter((s) => s.requires === null || can(s.requires[0], s.requires[1])),
    [can],
  )

  /**
   * The section actually shown — derived, not stored.
   *
   * A section that is not offered must not stay selected, or a person whose
   * access was narrowed while the page was open would be left staring at a
   * panel they can no longer reach. Deriving that during render rather than
   * correcting it in an effect means there is never a frame in which the wrong
   * panel is on screen, and no second render to produce the right one.
   */
  const shownSection = useMemo(() => {
    if (visibleSections.some((s) => s.id === activeSection)) return activeSection
    return visibleSections[0]?.id ?? 'account'
  }, [visibleSections, activeSection])

  /* ── Fetch all settings data ──
     The staff list and the permission catalogue are read separately from the
     two reads every account may make. They are gated on `settings.staff`, so a
     staff member without it gets a 403 here — and inside the shared
     `Promise.all` that refusal would have rejected the whole group, blanking
     the page over a list they were never meant to see. Read on their own, the
     refusal costs them nothing. */
  useEffect(() => {
    let cancelled = false

    async function load() {
      setIsLoading(true)
      try {
        const [academyRes, settingsRes] = await Promise.all([
          api.get('/settings/academy'),
          api.get('/settings/appearance'),
        ])
        if (!cancelled) {
          setAcademy(academyRes.data)
          setSettings(settingsRes.data)
        }
      } catch {
        // Backend unavailable
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    async function loadStaff() {
      try {
        const { data } = await api.get('/settings/staff')
        if (!cancelled) setStaff(data.staff ?? data ?? [])
      } catch {
        // Refused, or backend unavailable — the section is not offered to
        // someone who cannot read it, so there is nothing to report.
      }
    }

    async function loadCatalogue() {
      try {
        const { data } = await api.get('/settings/permissions')
        if (!cancelled) setCatalogue(normalizeCatalogue(data))
      } catch {
        // The editor falls back to the compiled mirror.
      }
    }

    load()
    if (canManageStaff) {
      loadStaff()
      loadCatalogue()
    }
    return () => { cancelled = true }
  }, [canManageStaff])

  /* ── Handlers ── */
  const handleUpdateAcademy = async (data: Partial<Academy>) => {
    try {
      await api.put('/settings/academy', data)
      // Backend returns {message} only — merge updates into local state
      setAcademy(prev => prev ? { ...prev, ...data } : prev)
      toast.success(t('page.toast.academyUpdated'))
    } catch {
      toast.error(t('page.toast.saveFailed'))
    }
  }

  const handleUpdateSettings = async (data: Partial<AcademySettings>) => {
    try {
      await api.put('/settings/appearance', data)
      // Backend returns {message} only — merge updates into local state
      setSettings(prev => prev ? { ...prev, ...data } : prev)
      toast.success(t('page.toast.settingsUpdated'))
    } catch {
      toast.error(t('page.toast.saveFailed'))
    }
  }

  const handleAddStaff = () => {
    setShowAddStaff(true)
  }

  const handleStaffAdded = async () => {
    // Refresh staff list
    try {
      const { data } = await api.get('/settings/staff')
      setStaff(data.staff ?? data ?? [])
    } catch {
      // Backend unavailable
    }
  }

  /** Re-read a single row's saved state, or fall back to the whole list. */
  const handleStaffSaved = handleStaffAdded

  const handleDeactivateStaff = async (id: string) => {
    try {
      await api.post(`/settings/staff/${id}/deactivate`)
      setStaff((prev) =>
        prev.map((s) => (s.id === id ? { ...s, is_active: false } : s)),
      )
      toast.success(t('page.toast.staffDeactivated'))
    } catch {
      toast.error(t('page.toast.deactivateFailed'), t('page.toast.tryAgain'))
    }
  }

  const handleReactivateStaff = async (id: string) => {
    try {
      await api.post(`/settings/staff/${id}/reactivate`)
      setStaff((prev) =>
        prev.map((s) => (s.id === id ? { ...s, is_active: true } : s)),
      )
      toast.success(t('page.toast.staffReactivated'))
    } catch {
      toast.error(t('page.toast.reactivateFailed'), t('page.toast.tryAgain'))
    }
  }

  const handleSectionSelect = (id: string) => {
    setActiveSection(id)
    setMobileNavOpen(false)
  }

  /* ── Default data when backend is unavailable ── */
  const defaultSettings: AcademySettings = {
    id: '1',
    academy_id: '1',
    currency: 'DZD',
    default_plan_duration: 30,
    billing_reminder_days_before: 3,
    due_date_reminder_timing: 'same_day',
    whatsapp_template: '',
    auto_checkout_enabled: false,
    end_class_popup_enabled: false,
    default_theme: 'dark',
    default_font_size: 'normal',
    default_language: 'fr',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }

  const defaultAcademy: Academy = {
    id: '1',
    name: '',
    address: '',
    phone: '',
    email: '',
    weekend_day: 6,
    current_term: 'Term 1',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }

  const effectiveSettings = settings ?? defaultSettings
  const effectiveAcademy = academy ?? defaultAcademy

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
    <div className="flex h-full overflow-hidden p-4 gap-4">
      {/* ── Left rail navigation (desktop) ─────── */}
      <nav
        className={cn(
          'hidden md:flex w-[220px] shrink-0 flex-col gap-0.5',
          'rounded-[var(--radius-lg)]',
          'bg-[var(--glass)] backdrop-blur-[22px] backdrop-saturate-[180%]',
          'border border-[var(--glass-border)]',
          'shadow-[var(--glass-shadow)]',
          'p-2 h-fit',
        )}
      >
        <span className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider px-3 pb-2 pt-1">
          {t('page.navTitle')}
        </span>
        {visibleSections.map((section) => {
          const isActive = shownSection === section.id
          return (
            <button
              key={section.id}
              type="button"
              onClick={() => handleSectionSelect(section.id)}
              className={cn(
                'flex items-center gap-2.5 w-full px-3 py-2.5 rounded-[var(--radius-sm)]',
                'text-sm font-medium text-start transition-all duration-200',
                isActive
                  ? 'bg-[var(--gold-soft)] text-[var(--gold)] border-s-2 border-[var(--gold)]'
                  : 'text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--glass)] border-s-2 border-transparent',
              )}
            >
              {section.icon}
              <span className="flex-1 truncate">{t(section.labelKey)}</span>
              {isActive && (
                // Points "forward" — which is left in Arabic, so the glyph
                // mirrors rather than the meaning.
                <ChevronRight className="w-3.5 h-3.5 opacity-60 rtl:-scale-x-100" />
              )}
            </button>
          )
        })}
      </nav>

      {/* ── Mobile nav toggle ──────────────────── */}
      <button
        type="button"
        onClick={() => setMobileNavOpen(true)}
        aria-label={t('page.openNav')}
        className={cn(
          'md:hidden fixed bottom-4 start-4 z-40',
          'w-12 h-12 rounded-full',
          'bg-[var(--gold)] text-white',
          'shadow-lg',
          'flex items-center justify-center',
          'hover:opacity-90 active:scale-95',
          'transition-all duration-150',
        )}
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* ── Mobile nav overlay ─────────────────── */}
      {mobileNavOpen && (
        <div className="md:hidden fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/30 backdrop-blur-sm"
            onClick={() => setMobileNavOpen(false)}
          />
          <nav
            className={cn(
              // Anchored to the inline start and mirrored with it — in Arabic
              // the panel is on the right and therefore slides in from there.
              'absolute start-0 top-0 bottom-0 w-[280px]',
              'bg-[var(--bg)] border-e border-[var(--glass-border)]',
              'flex flex-col gap-0.5 p-4',
              'animate-slide-in-left rtl:animate-slide-in-right',
            )}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider">
                {t('page.navTitle')}
              </span>
              <button
                type="button"
                onClick={() => setMobileNavOpen(false)}
                aria-label={t('common:action.close')}
                className="p-1 rounded-lg hover:bg-[var(--glass)]"
              >
                <X className="w-4 h-4 text-[var(--muted)]" />
              </button>
            </div>
            {visibleSections.map((section) => {
              const isActive = shownSection === section.id
              return (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => handleSectionSelect(section.id)}
                  className={cn(
                    'flex items-center gap-2.5 w-full px-3 py-2.5 rounded-[var(--radius-sm)]',
                    'text-sm font-medium text-start transition-all duration-200',
                    isActive
                      ? 'bg-[var(--gold-soft)] text-[var(--gold)] border-s-2 border-[var(--gold)]'
                      : 'text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--glass)] border-s-2 border-transparent',
                  )}
                >
                  {section.icon}
                  <span className="flex-1 truncate">{t(section.labelKey)}</span>
                </button>
              )
            })}
          </nav>
        </div>
      )}

      {/* ── Content area ──────────────────────── */}
      <div className="flex-1 min-w-0 overflow-y-auto">
        <div className="animate-fade-in">
          {shownSection === 'appearance' && (
            <Appearance settings={effectiveSettings} onUpdate={handleUpdateSettings} />
          )}
          {shownSection === 'account' && (
            <MyAccount />
          )}
          {shownSection === 'academy' && (
            <AcademyProfile
              key={canEditAcademy ? 'edit' : 'read'}
              academy={effectiveAcademy}
              onUpdate={handleUpdateAcademy}
              readOnly={!canEditAcademy}
            />
          )}
          {shownSection === 'subjects' && (
            <SubjectsSettings />
          )}
          {shownSection === 'staff' && (
            <StaffRoles
              staff={staff}
              onAdd={handleAddStaff}
              onDeactivate={handleDeactivateStaff}
              onReactivate={handleReactivateStaff}
              onEdit={canManageStaff ? setEditingStaff : undefined}
            />
          )}
          {shownSection === 'billing' && (
            <BillingConfig settings={effectiveSettings} onUpdate={handleUpdateSettings} />
          )}
          {shownSection === 'automations' && (
            <Automations />
          )}
          {shownSection === 'export' && (
            <DataExport />
          )}
          {shownSection === 'danger' && (
            <DangerZone />
          )}
        </div>
      </div>

      {/* Add Staff Modal */}
      <AddStaffModal
        isOpen={showAddStaff}
        onClose={() => setShowAddStaff(false)}
        onAdded={handleStaffAdded}
        catalogue={catalogue ?? undefined}
      />

      {/* Edit Staff Modal.
          Keyed by the person: opening a different one remounts the form, so the
          fields cannot carry the previous member's details across. */}
      <EditStaffModal
        key={editingStaff?.id ?? 'none'}
        member={editingStaff}
        onClose={() => setEditingStaff(null)}
        onSaved={handleStaffSaved}
        catalogue={catalogue ?? undefined}
      />
    </div>
  )
}

export default SettingsPage
