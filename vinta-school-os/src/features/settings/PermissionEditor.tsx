/**
 * Vinta School OS — Permission Editor
 *
 * The control an owner uses to decide what one staff member may do.
 *
 * Two axes, as decided: an **area** — Students, Billing, Settings and the rest
 * — carries a level of *none / view / manage*, and the handful of large actions
 * inside an area (taking a payment, running a payout, reading the reports,
 * touching staff or the danger zone) are toggled on and off individually.
 *
 * ── Why the areas come from the server ──
 *
 * The rows are drawn from the catalogue the server serves, not from the table
 * compiled into this bundle. A switch the server would honour must never be
 * absent from this screen, because the owner would then be unable to grant it
 * and would have no way to tell the difference between "not permitted" and
 * "not implemented". If the read fails, the local mirror — the same list the
 * server was built from — stands in, so the editor is never empty.
 *
 * ── The one rule the UI has to teach ──
 *
 * An action is inert while its area is `none`. Rather than let the owner tick
 * "Take payments" and watch nothing happen, the action list is hidden at that
 * level and the row says why. The server enforces the same thing; this is the
 * screen refusing to promise otherwise.
 */

import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import {
  PERMISSION_AREA_ACTIONS,
  type PermissionGrant,
  type PermissionLevel,
  type PermissionsCatalogue,
} from '../../lib/permissions'

// ============================================
// Props
// ============================================

export interface PermissionEditorProps {
  value: PermissionGrant
  onChange: (next: PermissionGrant) => void
  catalogue: PermissionsCatalogue
  /** Rendered disabled, for showing what someone else holds without letting it be changed. */
  readOnly?: boolean
}

// ============================================
// Component
// ============================================

export function PermissionEditor({ value, onChange, catalogue, readOnly = false }: PermissionEditorProps) {
  const { t } = useTranslation('settings')

  const setLevel = (area: string, level: PermissionLevel) => {
    const levels = { ...value.levels, [area]: level }
    const actions = { ...value.actions }
    // An action cannot outlive its area. Clearing them here keeps the saved map
    // honest — a grant that says "billing: none" while still listing "payouts"
    // is a grant whose meaning depends on which half you read first.
    if (level === 'none') delete actions[area]
    onChange({ ...value, levels, actions })
  }

  const toggleAction = (area: string, action: string) => {
    const current = value.actions[area] ?? []
    const next = current.includes(action)
      ? current.filter((a) => a !== action)
      : [...current, action]
    const actions = { ...value.actions }
    if (next.length) actions[area] = next
    else delete actions[area]
    onChange({ ...value, actions })
  }

  return (
    <div className="flex flex-col gap-3" data-testid="permission-editor">
      {catalogue.areas.map(({ key: area, actions }) => {
        const level = (value.levels[area] ?? 'none') as PermissionLevel
        const areaLabel = t(`permissions.area.${area}`, { defaultValue: area })
        // The catalogue's own list wins; the mirror covers an area whose
        // actions the response did not describe.
        const knownActions = actions.length ? actions : PERMISSION_AREA_ACTIONS[area as keyof typeof PERMISSION_AREA_ACTIONS] ?? []
        const chosen = value.actions[area] ?? []

        return (
          <div
            key={area}
            className={cn(
              'rounded-[var(--radius-md,12px)] border p-3 transition-colors',
              level === 'none'
                ? 'border-[var(--glass-border)] bg-[var(--input-bg)]'
                : 'border-[var(--gold)]/25 bg-[var(--gold-soft)]/40',
            )}
          >
            {/* Area + level */}
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-semibold text-[var(--text)] flex-1 min-w-[120px]">
                {areaLabel}
              </span>

              {/* Level selector.
                  One segmented track rather than three loose buttons: equal
                  widths on a shared track read as a single control with three
                  states, where three differently-sized buttons read as three
                  unrelated things. The words carry it — at 11px a lock or a
                  shield crowds the label without adding meaning the word does
                  not already give, and the icon was what made the row look
                  busy. Radio-style rather than a native select: all three
                  options stay visible, and a select would hide the two that
                  were not chosen. */}
              <div
                role="radiogroup"
                aria-label={areaLabel}
                className={cn(
                  'inline-flex items-center gap-0.5 p-[3px] rounded-full',
                  'bg-[var(--input-bg)] border border-[var(--glass-border)]',
                )}
              >
                {catalogue.levels.map((lvl) => {
                  const active = level === lvl
                  return (
                    <button
                      key={lvl}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      disabled={readOnly}
                      onClick={() => setLevel(area, lvl as PermissionLevel)}
                      className={cn(
                        'min-w-[66px] h-7 px-3 rounded-full border',
                        'inline-flex items-center justify-center whitespace-nowrap',
                        'text-[11px] font-semibold tracking-wide',
                        'transition-colors duration-150',
                        active
                          ? lvl === 'none'
                            // `muted-soft` is a translucent neutral defined for
                            // both themes, so "no access" reads as a filled but
                            // colourless chip. `--glass` was the old choice and
                            // is white-on-white in light mode, which is why the
                            // selected "None" looked like nothing at all.
                            ? 'bg-[var(--muted-soft)] text-[var(--text)] border-[var(--glass-border)]'
                            // Soft gold fill with full-strength gold text and
                            // border: legible in both themes without white on
                            // a light gold, which is what the filled pill did
                            // in dark mode.
                            : 'bg-[var(--gold-soft)] text-[var(--gold)] border-[var(--gold)]'
                          : 'text-[var(--muted)] border-transparent',
                        !readOnly && !active && 'hover:text-[var(--text)]',
                        readOnly ? 'cursor-default opacity-70' : 'cursor-pointer',
                      )}
                    >
                      {t(`permissions.level.${lvl}`, { defaultValue: lvl })}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Actions inside the area */}
            {knownActions.length > 0 && (
              level === 'none' ? (
                <p className="mt-2 text-[11px] text-[var(--muted)]">
                  {t('permissions.actionsNeedArea')}
                </p>
              ) : (
                <div className="mt-3 pt-3 border-t border-[var(--glass-border)] flex flex-col gap-2">
                  {knownActions.map((action) => (
                    <label
                      key={action}
                      className={cn(
                        'flex items-start gap-2.5',
                        readOnly ? 'cursor-default' : 'cursor-pointer',
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={chosen.includes(action)}
                        disabled={readOnly}
                        onChange={() => toggleAction(area, action)}
                        className="mt-0.5 w-4 h-4 rounded accent-[var(--gold)]"
                      />
                      <span className="flex flex-col">
                        <span className="text-xs font-medium text-[var(--text)]">
                          {t(`permissions.action.${area}.${action}`, { defaultValue: action })}
                        </span>
                        <span className="text-[11px] text-[var(--muted)]">
                          {t(`permissions.actionHint.${area}.${action}`, { defaultValue: '' })}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
              )
            )}
          </div>
        )
      })}
    </div>
  )
}

export default PermissionEditor
