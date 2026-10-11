/**
 * Vinta School OS — Permission Mirror
 *
 * The client-side twin of `Backend/vinta-academy-backend/app/permissions.py`,
 * and the second half of "the owner's decision is enforced, not merely
 * presented". The server refuses what it refuses; this file decides what the
 * app *offers*, so a person is not shown a door that will not open.
 *
 * ── Why this is a mirror, and why that is a maintenance cost worth paying ──
 *
 * The alternative — reading the served catalogue (`GET /settings/permissions`)
 * at boot — would mean the navigation could not be drawn until a request
 * finished, and would be empty for anyone the request fails for. A signed-in
 * user's own permissions, by contrast, are already in hand: they arrive on the
 * token's identity (`user.permissions`). So the *steering* is done from a
 * local copy, and the catalogue is used only to draw the editor in Settings.
 *
 * The cost is that this table can drift from the server's. That is what
 * `scratch_permissions_check.py` is for: it fetches the served catalogue and
 * fails if the two no longer agree. Adding an area or an action on the server
 * without adding it here is therefore caught, not shipped.
 *
 * ── The rule that matters most here ──
 *
 * A grant that is *missing* is not a grant of nothing. The server reads a
 * null column as the documented staff default, and it never reads an owner's
 * column at all — the owner holds everything by virtue of the role. This file
 * has to answer identically, or a client holding a token from before the
 * feature shipped would hide the owner's own Billing page from them.
 */

// ============================================
// The catalogue
// ============================================

export type PermissionLevel = 'none' | 'view' | 'manage'

export type PermissionArea =
  | 'students'
  | 'teachers'
  | 'classes'
  | 'calendar'
  | 'attendance'
  | 'billing'
  | 'settings'

/** Weakest first — the order the dropdown lists them in. */
export const PERMISSION_LEVELS: PermissionLevel[] = ['none', 'view', 'manage']

/** The order the editor lists areas in. The server's order, so the two agree. */
export const PERMISSION_AREA_ORDER: PermissionArea[] = [
  'students',
  'teachers',
  'classes',
  'calendar',
  'attendance',
  'billing',
  'settings',
]

/**
 * The named actions inside each area — the "big ones", as few as can be got
 * away with. Everything that is merely *work* belongs in the level instead.
 */
export const PERMISSION_AREA_ACTIONS: Record<PermissionArea, string[]> = {
  students: [],
  teachers: ['commission'],
  classes: [],
  calendar: ['cancel'],
  attendance: [],
  billing: ['payments', 'payouts', 'expenses', 'reports'],
  settings: ['staff', 'danger'],
}

/** What a staff account gets before its owner has decided anything. */
export const DEFAULT_STAFF_PERMISSIONS: Record<PermissionArea, PermissionLevel> = {
  students: 'manage',
  teachers: 'manage',
  classes: 'manage',
  calendar: 'manage',
  attendance: 'manage',
  billing: 'none',
  settings: 'none',
}

// ============================================
// Shapes
// ============================================

/** What the server sends as `user.permissions` — already resolved. */
export interface PermissionGrant {
  role: 'owner' | 'staff' | null
  levels: Record<string, PermissionLevel>
  actions: Record<string, string[]>
}

/** A nav key, mapped to the area that governs it. */
const PAGE_AREA: Record<string, PermissionArea> = {
  students: 'students',
  teachers: 'teachers',
  classes: 'classes',
  // 'classrooms' is the same page under its display name.
  classrooms: 'classes',
  calendar: 'calendar',
  billing: 'billing',
  settings: 'settings',
}

/**
 * The catalogue as `GET /settings/permissions` serves it.
 *
 * The editor draws itself from this rather than from the table above, so a
 * switch the server honours can never be missing from the screen. The table
 * above remains the fallback for the moment before the read lands, and the
 * source of the level names when the response is unavailable.
 */
export interface PermissionsCatalogue {
  areas: { key: string; actions: string[] }[]
  levels: string[]
  default: Record<string, PermissionLevel>
}

/** A catalogue-shaped value from the local mirror, for when the read fails. */
export function localCatalogue(): PermissionsCatalogue {
  return {
    areas: PERMISSION_AREA_ORDER.map((key) => ({
      key,
      actions: [...PERMISSION_AREA_ACTIONS[key]],
    })),
    levels: [...PERMISSION_LEVELS],
    default: { ...DEFAULT_STAFF_PERMISSIONS },
  }
}

/**
 * A trustworthy catalogue from whatever the endpoint returned.
 *
 * Anything unreadable falls back to the local mirror, which is the same list
 * the server was built from — so a failed read degrades to a correct editor
 * rather than to an empty one. A level list that arrives empty is treated as
 * unreadable for the same reason: a dropdown with no options is not a state
 * this screen should ever be able to reach.
 */
export function normalizeCatalogue(raw: unknown): PermissionsCatalogue {
  const source = (raw ?? {}) as Partial<PermissionsCatalogue>
  if (!Array.isArray(source.areas) || !Array.isArray(source.levels) || !source.levels.length) {
    return localCatalogue()
  }
  const areas = source.areas
    .filter((a): a is { key: string; actions: string[] } => !!a && typeof a.key === 'string')
    .map((a) => ({ key: a.key, actions: Array.isArray(a.actions) ? a.actions : [] }))
  if (!areas.length) return localCatalogue()
  return {
    areas,
    levels: source.levels,
    default: (source.default ?? DEFAULT_STAFF_PERMISSIONS) as Record<string, PermissionLevel>,
  }
}

// ============================================
// Building a grant
// ============================================

const OWNER_LEVELS: Record<string, PermissionLevel> = PERMISSION_AREA_ORDER.reduce(
  (acc, area) => { acc[area] = 'manage'; return acc },
  {} as Record<string, PermissionLevel>,
)

const OWNER_ACTIONS: Record<string, string[]> = PERMISSION_AREA_ORDER.reduce(
  (acc, area) => { acc[area] = [...PERMISSION_AREA_ACTIONS[area]]; return acc },
  {} as Record<string, string[]>,
)

/** Everything held — an owner's grant. */
export function ownerGrant(): PermissionGrant {
  return { role: 'owner', levels: { ...OWNER_LEVELS }, actions: { ...OWNER_ACTIONS } }
}

/**
 * A complete, valid grant from whatever arrived.
 *
 * A missing or unreadable map reads as the staff default rather than as
 * nothing at all, matching `permissions.normalize` on the server: the two have
 * to give the same answer for the same account, or the app would hide work the
 * server would allow (or, worse, offer work it would refuse).
 *
 * An unknown level becomes `none`. That direction matters — a value this
 * release cannot reason about is a value it cannot honour.
 */
export function normalizeGrant(raw: unknown, role: 'owner' | 'staff' | null = 'staff'): PermissionGrant {
  const source = (raw ?? {}) as { levels?: unknown; actions?: unknown }
  const rawLevels = source.levels

  if (!rawLevels || typeof rawLevels !== 'object') {
    return {
      role,
      levels: { ...DEFAULT_STAFF_PERMISSIONS },
      actions: {},
    }
  }

  const levels: Record<string, PermissionLevel> = {}
  for (const area of PERMISSION_AREA_ORDER) {
    const value = (rawLevels as Record<string, unknown>)[area]
    levels[area] = PERMISSION_LEVELS.includes(value as PermissionLevel)
      ? (value as PermissionLevel)
      : 'none'
  }

  const actions: Record<string, string[]> = {}
  const rawActions = (source.actions ?? {}) as Record<string, unknown>
  for (const area of PERMISSION_AREA_ORDER) {
    const chosen = rawActions[area]
    if (!Array.isArray(chosen)) continue
    // Ordered by the catalogue, not by the payload, so two accounts holding
    // the same permissions compare equal and "has this changed?" is a
    // comparison rather than a diff.
    const kept = PERMISSION_AREA_ACTIONS[area].filter((action) => chosen.includes(action))
    if (kept.length) actions[area] = kept
  }

  return { role, levels, actions }
}

/**
 * The grant belonging to a signed-in user.
 *
 * Prefers what the server sent, and falls back on the role alone when nothing
 * did. That fallback is deliberate and asymmetric: an owner without a grant is
 * still the owner and keeps everything, while a staff member without one gets
 * the documented default. Sending the owner an empty grant would lock them out
 * of their own academy, which is a worse failure than any permission this
 * feature could withhold.
 */
export function grantFor(user: { role?: string; permissions?: unknown } | null | undefined): PermissionGrant {
  if (!user) return { role: null, levels: { ...DEFAULT_STAFF_PERMISSIONS }, actions: {} }
  const role = user.role === 'owner' ? 'owner' : 'staff'
  if (role === 'owner' && !user.permissions) return ownerGrant()
  return normalizeGrant(user.permissions, role)
}

// ============================================
// Asking the question
// ============================================

export function isOwner(grant: PermissionGrant | null | undefined): boolean {
  return grant?.role === 'owner'
}

export function levelOf(grant: PermissionGrant | null | undefined, area: PermissionArea): PermissionLevel {
  if (!grant) return 'none'
  return grant.levels?.[area] ?? 'none'
}

/**
 * Whether `grant` allows `need` in `area`.
 *
 * Mirrors `permissions.allowed` exactly, including the two easy-to-miss rules:
 * an action is granted by its own tick and is inert while its area is `none`,
 * and a requirement this release does not know is refused rather than ignored.
 */
export function can(
  grant: PermissionGrant | null | undefined,
  area: PermissionArea,
  need: string = 'view',
): boolean {
  if (!grant) return false
  if (isOwner(grant)) return true

  const level = levelOf(grant, area)
  if (level === 'none') return false
  if (need === 'view') return true
  if (need === 'manage') return level === 'manage'
  if (!PERMISSION_AREA_ACTIONS[area]?.includes(need)) return false
  return (grant.actions?.[area] ?? []).includes(need)
}

/** Whether any of the given requirements is satisfied. */
export function canAny(
  grant: PermissionGrant | null | undefined,
  requirements: [PermissionArea, string][],
): boolean {
  return requirements.some(([area, need]) => can(grant, area, need))
}

/**
 * Pages that carry no single area, and so are never withheld by one.
 *
 * `dashboard` has no area behind it — it is the landing page, and hiding it
 * would leave a refused route with nowhere to send anyone.
 *
 * `settings` is the same kind of page, which is easy to get wrong. It is not
 * one screen but a shelf of them, and three of those — appearance, the
 * person's own account, and the academy profile in read-only form — belong to
 * whoever is signed in. Gating the page on `settings: view` would take the
 * language switch and the password field away from exactly the staff member
 * they are meant for, and would leave the sections below unable to be reached
 * at all. The sections are filtered individually in `SettingsPage`; the page
 * itself is always offered.
 *
 * Every other page answers to the area it belongs to.
 */
const PAGES_WITHOUT_AN_AREA = new Set(['dashboard', 'settings'])

export function canSeePage(grant: PermissionGrant | null | undefined, pageKey: string): boolean {
  if (PAGES_WITHOUT_AN_AREA.has(pageKey)) return true
  const area = PAGE_AREA[pageKey]
  if (!area) return true
  return can(grant, area, 'view')
}

// ============================================
// Editing
// ============================================

/**
 * A grant the editor can hold as form state.
 *
 * Always complete: every area carries a level, because a dropdown with a blank
 * row would read as a value the server had sent rather than one nobody had
 * chosen yet.
 */
export function editableGrant(grant: PermissionGrant): PermissionGrant {
  return {
    role: grant.role,
    levels: { ...grant.levels },
    actions: Object.fromEntries(
      Object.entries(grant.actions ?? {}).map(([area, list]) => [area, [...list]]),
    ),
  }
}

/** The staff default, as an editable form value. */
export function defaultGrant(): PermissionGrant {
  return { role: 'staff', levels: { ...DEFAULT_STAFF_PERMISSIONS }, actions: {} }
}

/** Whether two grants are the same — used to leave a save button disabled. */
export function sameGrant(a: PermissionGrant, b: PermissionGrant): boolean {
  for (const area of PERMISSION_AREA_ORDER) {
    if (levelOf(a, area) !== levelOf(b, area)) return false
    const left = [...(a.actions?.[area] ?? [])].sort().join(',')
    const right = [...(b.actions?.[area] ?? [])].sort().join(',')
    if (left !== right) return false
  }
  return true
}
