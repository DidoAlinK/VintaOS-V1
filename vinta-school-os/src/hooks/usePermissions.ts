/**
 * Vinta School OS — usePermissions
 *
 * The single way a component asks what the signed-in person may do.
 *
 * It reads the identity out of the auth store and hands back the same answers
 * the server will give, through `lib/permissions`. Components never reach into
 * `user.permissions` themselves: the grant on the wire is the raw one, and the
 * rules that make it meaningful — the owner holds everything, a missing map
 * reads as the staff default, an unknown level reads as none — live in one
 * place so that a screen cannot accidentally apply a different reading.
 */

import { useMemo } from 'react'
import { useAuthStore } from '../stores/authStore'
import {
  can,
  canAny,
  canSeePage,
  grantFor,
  isOwner,
  levelOf,
  type PermissionArea,
  type PermissionGrant,
} from '../lib/permissions'

export interface Permissions {
  /** The resolved grant — for passing to the editor, not for reading directly. */
  grant: PermissionGrant
  /** Whether this account is the academy owner. */
  isOwner: boolean
  /** `can(grant, area, need)` — `need` is a level or a named action. */
  can: (area: PermissionArea, need?: string) => boolean
  /** True when *any* of the requirements is met. */
  canAny: (requirements: [PermissionArea, string][]) => boolean
  /** Whether a nav key / route key should be offered at all. */
  canSeePage: (pageKey: string) => boolean
  /** The level held in an area, for drawing a read-only summary. */
  levelOf: (area: PermissionArea) => ReturnType<typeof levelOf>
}

export function usePermissions(): Permissions {
  const user = useAuthStore((s) => s.user)

  return useMemo<Permissions>(() => {
    const grant = grantFor(user)
    return {
      grant,
      isOwner: isOwner(grant),
      can: (area, need) => can(grant, area, need),
      canAny: (requirements) => canAny(grant, requirements),
      canSeePage: (pageKey) => canSeePage(grant, pageKey),
      levelOf: (area) => levelOf(grant, area),
    }
  }, [user])
}

export default usePermissions
