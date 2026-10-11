import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import { Card, CardHeader, CardBody } from '../../components/ui/Card'
import { Avatar } from '../../components/ui/Avatar'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Toggle } from '../../components/ui/Toggle'
import {
  PERMISSION_AREA_ORDER,
  normalizeGrant,
  type PermissionGrant,
} from '../../lib/permissions'
import type { StaffMember } from '../../types/settings'
import { UserPlus, Shield, Users, Pencil, KeyRound } from 'lucide-react'

/* ─── Props ─── */

export interface StaffRolesProps {
  staff: StaffMember[]
  onAdd: () => void
  onDeactivate: (id: string) => void
  onReactivate: (id: string) => void
  /** Opens the edit modal. Absent means this account cannot manage staff. */
  onEdit?: (member: StaffMember) => void
}

/* ─── Grant summary ───
   Reads a resolved grant as one short line of chips. Only the areas that are
   not `none` are listed: a person's access is what they hold, and printing
   seven rows of "None" would bury it. An area with named actions carries their
   count, so "Billing · Manage · 2" says the reports and the payouts are on
   without spending a line on which two. */

export function GrantSummary({ grant }: { grant: PermissionGrant }) {
  const { t } = useTranslation('settings')

  if (grant.role === 'owner') {
    return (
      <span className="text-[11px] font-medium text-[var(--gold)]">
        {t('permissions.fullAccess')}
      </span>
    )
  }

  const held = PERMISSION_AREA_ORDER.filter((area) => (grant.levels[area] ?? 'none') !== 'none')
  if (!held.length) {
    return (
      <span className="text-[11px] text-[var(--muted)]">{t('permissions.noAccess')}</span>
    )
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {held.map((area) => {
        const actions = grant.actions[area] ?? []
        return (
          <span
            key={area}
            className={cn(
              'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md',
              'text-[10px] font-medium',
              'bg-[var(--glass)] text-[var(--muted)] border border-[var(--glass-border)]',
            )}
          >
            {t(`permissions.area.${area}`, { defaultValue: area })}
            <span className="text-[var(--text)]">
              {t(`permissions.levelShort.${grant.levels[area]}`)}
            </span>
            {actions.length > 0 && (
              <span className="text-[var(--gold)]">
                +{t('permissions.actionCount', { count: actions.length })}
              </span>
            )}
          </span>
        )
      })}
    </div>
  )
}

/* ─── Component ─── */

export function StaffRoles({ staff, onAdd, onDeactivate, onReactivate, onEdit }: StaffRolesProps) {
  const { t } = useTranslation('settings')
  const activeStaff = staff.filter((s) => s.is_active)
  const inactiveStaff = staff.filter((s) => !s.is_active)

  return (
    <div className="flex flex-col gap-5 max-w-xl">
      {/* Header card */}
      <Card>
        <CardHeader
          title={t('staff.title')}
          actions={
            <Button variant="primary" size="sm" onClick={onAdd}>
              <UserPlus className="w-4 h-4" />
              {t('staff.addProfile')}
            </Button>
          }
        />
        <CardBody>
          <p className="text-sm text-[var(--muted)]">
            {t('staff.description')}
          </p>
        </CardBody>
      </Card>

      {/* Active staff */}
      {activeStaff.length > 0 && (
        <Card>
          <CardHeader title={t('staff.active', { count: activeStaff.length })} />
          <CardBody>
            <div className="flex flex-col gap-1">
              {activeStaff.map((member) => (
                <div
                  key={member.id}
                  className={cn(
                    'flex items-start gap-3 px-3 py-3',
                    'rounded-[var(--radius-sm)]',
                    'hover:bg-[var(--glass)] transition-colors',
                  )}
                >
                  <Avatar
                    name={member.name}
                    src={member.picture?.dataUrl}
                    size="md"
                  />

                  <div className="flex flex-col min-w-0 flex-1 gap-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-medium text-[var(--text)] truncate">
                        {member.name}
                      </span>
                      {/* A member with their own login is a distinct thing
                          from one who only has a PIN — worth seeing at a
                          glance, because it is what lets them in from a
                          browser that has never met this academy. */}
                      {member.email && (
                        <KeyRound className="w-3 h-3 shrink-0 text-[var(--gold)]" />
                      )}
                    </div>
                    {member.phone && (
                      <span className="text-xs text-[var(--muted)] truncate">
                        {member.phone}
                      </span>
                    )}
                    {member.permissions && (
                      <GrantSummary
                        grant={normalizeGrant(member.permissions, member.role === 'owner' ? 'owner' : 'staff')}
                      />
                    )}
                  </div>

                  {/* Role badge */}
                  <Badge
                    variant={member.role === 'owner' ? 'gold' : 'emerald'}
                    size="sm"
                  >
                    <Shield className="w-3 h-3 me-1" />
                    {member.role === 'owner' ? t('staff.role.owner') : t('staff.role.staff')}
                  </Badge>

                  {/* Edit */}
                  {onEdit && (
                    <button
                      type="button"
                      onClick={() => onEdit(member)}
                      aria-label={t('staff.edit')}
                      title={t('staff.edit')}
                      className={cn(
                        'p-1.5 rounded-lg text-[var(--muted)] shrink-0',
                        'hover:bg-[var(--glass)] hover:text-[var(--text)]',
                        'transition-colors duration-150',
                      )}
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                  )}

                  {/* Deactivate toggle (only for staff, not owner) */}
                  {member.role !== 'owner' && (
                    <Toggle
                      checked={member.is_active}
                      onCheckedChange={() => onDeactivate(member.id)}
                    />
                  )}
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {/* Inactive staff */}
      {inactiveStaff.length > 0 && (
        <Card>
          <CardHeader title={t('staff.deactivated', { count: inactiveStaff.length })} />
          <CardBody>
            <div className="flex flex-col gap-1">
              {inactiveStaff.map((member) => (
                <div
                  key={member.id}
                  className={cn(
                    'flex items-center gap-3 px-3 py-3',
                    'rounded-[var(--radius-sm)]',
                    'opacity-60',
                  )}
                >
                  <Avatar name={member.name} src={member.picture?.dataUrl} size="md" />

                  <div className="flex flex-col min-w-0 flex-1">
                    <span className="text-sm font-medium text-[var(--text)] truncate">
                      {member.name}
                    </span>
                    {member.phone && (
                      <span className="text-xs text-[var(--muted)] truncate">
                        {member.phone}
                      </span>
                    )}
                  </div>

                  <Badge variant="grey" size="sm">
                    {t('staff.deactivatedBadge')}
                  </Badge>

                  <button
                    onClick={() => onReactivate(member.id)}
                    className={cn(
                      'px-2.5 py-1 rounded-lg text-[11px] font-medium',
                      'bg-[var(--emerald-soft)] text-[var(--emerald)]',
                      'hover:opacity-80 transition-opacity',
                    )}
                  >
                    {t('staff.reactivate')}
                  </button>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {staff.length === 0 && (
        <Card>
          <CardBody>
            <div className="flex flex-col items-center gap-3 py-8 text-center">
              <Users className="w-10 h-10 text-[var(--muted)]" />
              <p className="text-sm text-[var(--muted)]">
                {t('staff.empty')}
              </p>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}

export default StaffRoles
