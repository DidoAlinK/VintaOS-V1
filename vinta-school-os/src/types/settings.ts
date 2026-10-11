/**
 * Vinta School OS — Settings Types
 */

import type { PermissionGrant } from '../lib/permissions'
import type { PayoutSchedule } from '../lib/payoutSchedule'

// ============================================
// Academy Settings
// ============================================

export interface AcademySettings {
  id: string
  academy_id: string
  currency: string
  default_plan_duration: number
  billing_reminder_days_before: number
  due_date_reminder_timing: 'same_day' | 'custom'
  whatsapp_template: string
  auto_checkout_enabled: boolean
  end_class_popup_enabled: boolean
  default_theme: 'light' | 'dark'
  default_font_size: 'small' | 'normal' | 'large'
  default_language: 'fr' | 'ar' | 'en'
  created_at: string
  updated_at: string

  // ── Owner-configurable money model (optional for back-compat) ──
  default_credits_per_cycle?: number // 1-12
  allow_rollover_default?: boolean
  allow_makeups_default?: boolean
  default_access_weeks?: number | null
  default_max_groups?: number
  default_commission_note?: string
}

// ============================================
// Academy Profile
// ============================================

export interface Academy {
  id: string
  name: string
  phone: string
  email: string
  address: string
  weekend_day: number
  current_term: string
  created_at: string
  updated_at: string
}

// ============================================
// Subscription
// ============================================

export interface Subscription {
  id: string
  academy_id: string
  tier: 'starter' | 'pro' | 'scaler'
  status: 'active' | 'inactive' | 'trialing'
  invoicing_method: string
  started_at: string
  expires_at?: string
  created_at: string
}

// ============================================
// Staff Management
// ============================================

export interface StaffMember {
  id: string
  name: string
  email?: string
  phone?: string
  role: 'owner' | 'staff'
  is_active: boolean
  /**
   * What this profile may do, as `GET /settings/staff` resolves it — the map
   * actually in force, not the stored column. An owner's row reads as
   * everything held. Optional so a row from an older server still parses.
   */
  permissions?: PermissionGrant
  picture?: {
    type: 'preset' | 'upload'
    colors?: [string, string]
    dataUrl?: string
  }
  avatar_color_1?: string
  avatar_color_2?: string
  created_at: string
}

// ============================================
// Settings Requests
// ============================================

export interface UpdateAcademyRequest {
  name?: string
  phone?: string
  email?: string
  address?: string
  weekend_day?: number
  current_term?: string
}

export interface UpdateSettingsRequest {
  currency?: string
  default_plan_duration?: number
  billing_reminder_days_before?: number
  due_date_reminder_timing?: 'same_day' | 'custom'
  whatsapp_template?: string
  auto_checkout_enabled?: boolean
  end_class_popup_enabled?: boolean
  default_theme?: 'light' | 'dark'
  default_font_size?: 'small' | 'normal' | 'large'
  default_language?: 'fr' | 'ar' | 'en'
  default_credits_per_cycle?: number
  allow_rollover_default?: boolean
  allow_makeups_default?: boolean
  default_access_weeks?: number | null
  default_max_groups?: number
  default_commission_note?: string
}

// ============================================
// Billing configuration
// ============================================

/**
 * What `GET /settings/billing-config` answers.
 *
 * The payroll cadence is deliberately **not** a field on `AcademySettings`. It
 * lives in its own `payout_schedules` table rather than on the settings row,
 * and `PUT /settings` has never carried it — so folding it into
 * `AcademySettings` would invite somebody to send it to an endpoint that
 * silently drops it. It is read and written through `lib/payoutSchedule.ts`,
 * which owns both halves.
 *
 * The billing-rule booleans this endpoint also returns are enumerated inside
 * `lib/billingRules.ts` instead of here, because that module is what reads them.
 */
export interface BillingConfigResponse {
  payout_schedule?: PayoutSchedule
  [key: string]: unknown
}

export interface AddStaffRequest {
  name: string
  pin: string
  phone?: string
  role?: 'staff'
  owner_pin: string
  /** Optional sign-in address. Goes with `password` — both, or neither. */
  email?: string
  /** Optional sign-in password (8–72 characters). Goes with `email`. */
  password?: string
  permissions?: PermissionGrant
}

// ============================================
// Notification
// ============================================

export interface Notification {
  id: string
  academy_id: string
  user_id?: string
  type: 'payment_reminder' | 'class_ending' | 'enrollment_request' | 'overdue_alert' | 'general'
  title: string
  message: string
  detail?: string
  actions?: { label: string; variant: string }[]
  is_read: boolean
  created_at: string
}

// ============================================
// Settings State
// ============================================

export interface SettingsState {
  academy: Academy | null
  settings: AcademySettings | null
  subscription: Subscription | null
  staff: StaffMember[]
  notifications: Notification[]
  unreadCount: number
  isLoading: boolean
  error: string | null

  // Actions
  fetchAcademy: () => Promise<void>
  updateAcademy: (data: UpdateAcademyRequest) => Promise<void>
  fetchSettings: () => Promise<void>
  updateSettings: (data: UpdateSettingsRequest) => Promise<void>
  fetchStaff: () => Promise<void>
  addStaff: (data: AddStaffRequest) => Promise<StaffMember>
  deactivateStaff: (id: string) => Promise<void>
  fetchNotifications: () => Promise<void>
  markNotificationRead: (id: string) => Promise<void>
  markAllNotificationsRead: () => Promise<void>
}
