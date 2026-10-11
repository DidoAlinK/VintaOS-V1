import { useState, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import { Card, CardHeader, CardBody } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Download, FileText, ListFilter, Package } from 'lucide-react'
import api from '../../lib/api'
import { toast } from '../../stores/uiStore'
import { triggerDownload } from '../../lib/download'
import { usePermissions } from '../../hooks/usePermissions'
import BillingExportModal from '../billing/BillingExportModal'
import DataImport from './DataImport'

/* ─── Export items config ───
   Key names rather than sentences: the map is read at module scope, where the
   active language is not yet the one the desk is looking at.

   Billing records are `kind: 'billing'` rather than a plain `csv` row because
   they are not a single canned file: they are filtered and can be CSV *or* PDF,
   so that row opens the filters popup instead of downloading immediately.

   It replaces the old `/settings/export/billing` row, which exported the legacy
   `StudentBilling` table — a table the current payment flow never writes, so the
   file it produced was empty or stale for any academy that had been using the
   app. Two "export billing" buttons that disagree is worse than one. */

type ExportItem =
  | { kind: 'csv'; labelKey: string; endpoint: string; file: string }
  | { kind: 'billing'; labelKey: string }

const EXPORT_ITEMS: ExportItem[] = [
  { kind: 'csv', labelKey: 'export.items.students', endpoint: '/settings/export/students', file: 'students.csv' },
  { kind: 'csv', labelKey: 'export.items.teachers', endpoint: '/settings/export/teachers', file: 'teachers.csv' },
  { kind: 'csv', labelKey: 'export.items.classes', endpoint: '/settings/export/classes', file: 'classes.csv' },
  { kind: 'billing', labelKey: 'export.items.billing' },
  { kind: 'csv', labelKey: 'export.items.activityLog', endpoint: '/settings/export/activity-log', file: 'activity-log.csv' },
]

/* ─── Component ─── */

export function DataExport() {
  const { t } = useTranslation('settings')
  const [exporting, setExporting] = useState<string | null>(null)
  const [billingOpen, setBillingOpen] = useState(false)
  const { can, isOwner } = usePermissions()

  // The billing ledger is the one dataset the export route gates, on the same
  // `reports` action that guards the financial screens. Offering the row to
  // someone the server will refuse would be a button whose only outcome is an
  // error toast, so it is left out rather than shown and failed.
  const items = useMemo(
    () => EXPORT_ITEMS.filter((item) => item.kind !== 'billing' || can('billing', 'reports')),
    [can],
  )

  const handleExport = useCallback(async (labelKey: string, endpoint: string, filename: string) => {
    setExporting(labelKey)
    const label = t(labelKey)
    try {
      const response = await api.get(endpoint, { responseType: 'blob' })
      const blob = response.data instanceof Blob ? response.data : new Blob([JSON.stringify(response.data)], { type: 'text/csv' })
      triggerDownload(blob, filename)
      toast.success(t('export.toast.success', { label }))
    } catch {
      toast.error(t('export.toast.failed', { label }))
    } finally {
      setExporting(null)
    }
  }, [t])

  /* Everything, in one archive.
     Owner-only, and not for symmetry with the import box below: the archive
     carries a copy of the database itself, so handing it to a staff member
     would be handing them the academy rather than a report about it. The
     server says the same thing — this row would only ever produce a refusal. */
  const handleSchoolExport = useCallback(async () => {
    setExporting('export.items.school')
    try {
      // A whole database takes longer than a single table; the default
      // half-minute is not a promise this request can keep.
      const response = await api.get('/settings/export/school', {
        responseType: 'blob',
        timeout: 180000,
      })
      const blob = response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: 'application/zip' })
      const today = new Date().toISOString().slice(0, 10)
      triggerDownload(blob, `vinta-school-${today}.zip`)
      toast.success(t('export.school.toast'))
    } catch {
      toast.error(t('export.toast.failed', { label: t('export.school.title') }))
    } finally {
      setExporting(null)
    }
  }, [t])

  return (
    <div className="flex flex-col gap-5 max-w-xl">
      {isOwner && (
        <Card>
          <CardHeader
            title={t('export.school.title')}
            actions={<Package className="w-4 h-4 text-[var(--muted)]" />}
          />
          <CardBody>
            <p className="text-sm text-[var(--muted)] mb-4">{t('export.school.description')}</p>
            <Button
              variant="secondary"
              size="sm"
              loading={exporting === 'export.items.school'}
              onClick={handleSchoolExport}
            >
              <Download className="w-3.5 h-3.5" />
              {t('export.school.action')}
            </Button>
          </CardBody>
        </Card>
      )}

      {/* Export options */}
      <Card>
        <CardHeader title={t('export.title')} actions={<Download className="w-4 h-4 text-[var(--muted)]" />} />
        <CardBody>
          <p className="text-sm text-[var(--muted)] mb-4">
            {t('export.description')}
          </p>
          <div className="flex flex-col gap-3">
            {items.map((item) => (
              <div
                key={item.labelKey}
                className={cn(
                  'flex items-center justify-between px-4 py-3 rounded-[var(--radius-sm)]',
                  'bg-[var(--input-bg)] border border-[var(--glass-border)]',
                )}
              >
                <div className="flex items-center gap-2.5">
                  {item.kind === 'billing' ? (
                    <ListFilter className="w-4 h-4 text-[var(--muted)]" />
                  ) : (
                    <FileText className="w-4 h-4 text-[var(--muted)]" />
                  )}
                  <span className="text-sm font-medium text-[var(--text)]">{t(item.labelKey)}</span>
                </div>

                {item.kind === 'billing' ? (
                  <Button variant="ghost" size="sm" onClick={() => setBillingOpen(true)}>
                    <Download className="w-3.5 h-3.5" />
                    {t('export.choose')}
                  </Button>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    loading={exporting === item.labelKey}
                    onClick={() => handleExport(item.labelKey, item.endpoint, item.file)}
                  >
                    <Download className="w-3.5 h-3.5" />
                    {t('export.action')}
                  </Button>
                )}
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Import. The mirror of the archive above, and gated the same way: it
          writes to every table the academy owns, which is more of the academy
          than a staff role is trusted with. */}
      {isOwner && <DataImport />}

      {/* Billing records: filters + format, then server-side CSV or PDF. */}
      <BillingExportModal open={billingOpen} onClose={() => setBillingOpen(false)} />
    </div>
  )
}

export default DataExport
