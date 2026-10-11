import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../../lib/cn'
import api from '../../lib/api'
import { toast } from '../../stores/uiStore'
import { Modal } from '../../components/ui/Modal'
import { triggerDownload, describeRange } from '../../lib/download'
import { BillingRecordFilters } from './BillingRecordFilters'
import { EMPTY_FILTERS, toParams } from './recordFilterState'
import type { BillingRecordFilters as Filters } from '../../types/billing'
import { Check, FileSpreadsheet, FileText, Download } from 'lucide-react'

/* ─── Export billing records ───
 *
 * The filters popup behind both "Data & Export → Billing records" and the
 * export button inside the payment-records archive. Built once and used twice
 * so the two entry points cannot offer different filters.
 *
 * The file is produced **server-side** and this only receives the bytes. That
 * is deliberate: a browser "print to PDF" would render fonts perfectly but
 * forces the user through a print dialog — choose a printer, choose "Save as
 * PDF", choose a folder — which is exactly where a non-technical user gets
 * lost, and its output varies with their browser. A client-side PDF generator
 * would need an embedded font and Arabic shaping it does not do out of the box,
 * so an Algerian academy's Arabic names would come out as blank glyphs.
 */

type Format = 'csv' | 'pdf'

const FORMATS: { value: Format; labelKey: string; hintKey: string; icon: React.ElementType }[] = [
  { value: 'csv', labelKey: 'records.format.csv', hintKey: 'records.format.csvHint', icon: FileSpreadsheet },
  { value: 'pdf', labelKey: 'records.format.pdf', hintKey: 'records.format.pdfHint', icon: FileText },
]

interface BillingExportModalProps {
  open: boolean
  onClose: () => void
  /** Seed the filters — the archive passes what is on screen so the file
   *  matches the table the user is looking at. */
  initialFilters?: Filters
}

export function BillingExportModal({
  open,
  onClose,
  initialFilters,
}: BillingExportModalProps) {
  const { t } = useTranslation('billing')

  const [filters, setFilters] = useState<Filters>(initialFilters ?? EMPTY_FILTERS)
  const [format, setFormat] = useState<Format>('csv')
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /* Re-seed on open: the caller may have changed the on-screen filters since
     the last time this was dismissed, and a stale copy of them would quietly
     export the wrong rows. */
  useEffect(() => {
    if (open) {
      setFilters(initialFilters ?? EMPTY_FILTERS)
      setError(null)
    }
    // `initialFilters` is intentionally not a dependency beyond open: re-seeding
    // while the user is editing the form would fight their typing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open) setExporting(false)
  }, [open])

  const handleExport = async () => {
    setExporting(true)
    setError(null)
    try {
      const response = await api.get('/billing/records/export', {
        params: { ...toParams(filters), format },
        responseType: 'blob',
      })
      const blob =
        response.data instanceof Blob
          ? response.data
          : new Blob([response.data], { type: format === 'pdf' ? 'application/pdf' : 'text/csv' })
      const filename = `billing-records_${describeRange(filters.from, filters.to)}.${format}`
      triggerDownload(blob, filename)
      toast.success(t('records.toast.exported.title'), filename)
      onClose()
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 400) {
        setError(t('records.error.invalidFilters'))
      } else {
        setError(t('records.error.exportFailed'))
      }
      toast.error(t('records.toast.exportFailed.title'), t('records.toast.exportFailed.body'))
    } finally {
      setExporting(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={t('records.exportTitle')} size="md">
      <div className="flex flex-col gap-5">
        <p className="text-sm text-[var(--muted)]">{t('records.exportHint')}</p>

        <BillingRecordFilters filters={filters} onChange={setFilters} compact />

        {/* ── Format ── */}
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-[var(--muted)] uppercase tracking-wide">
            {t('records.format.label')}
          </span>
          <div className="grid grid-cols-2 gap-2">
            {FORMATS.map(({ value, labelKey, hintKey, icon: Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => setFormat(value)}
                aria-pressed={format === value}
                className={cn(
                  'flex flex-col items-start gap-1 p-3 rounded-[var(--radius-sm)] text-start',
                  'border transition-all duration-150',
                  format === value
                    ? 'bg-[var(--gold-soft)] border-[var(--gold)]'
                    : 'bg-[var(--input-bg)] border-[var(--glass-border)] hover:border-[var(--glass-border)]',
                )}
              >
                <span className="flex items-center gap-2">
                  <Icon
                    className={cn(
                      'w-4 h-4',
                      format === value ? 'text-[var(--gold)]' : 'text-[var(--muted)]',
                    )}
                  />
                  <span
                    className={cn(
                      'text-sm font-semibold',
                      format === value ? 'text-[var(--gold)]' : 'text-[var(--text)]',
                    )}
                  >
                    {t(labelKey)}
                  </span>
                  {format === value && <Check className="w-3.5 h-3.5 text-[var(--gold)] ms-auto" />}
                </span>
                <span className="text-[11px] leading-snug text-[var(--muted)]">{t(hintKey)}</span>
              </button>
            ))}
          </div>
        </div>

        {error && (
          <p role="alert" className="text-xs font-medium text-[var(--red)] text-center">
            {error}
          </p>
        )}

        <button
          type="button"
          onClick={() => void handleExport()}
          disabled={exporting}
          className={cn(
            'w-full flex items-center justify-center gap-2 py-3 rounded-[var(--radius-sm)]',
            'text-sm font-semibold transition-all duration-200',
            exporting
              ? 'bg-[var(--input-bg)] text-[var(--muted)] border border-[var(--glass-border)] cursor-not-allowed'
              : 'bg-gradient-to-r from-[var(--gold)] to-[var(--gold-dark, #9a7520)] text-white shadow-[0_4px_20px_rgba(179,135,42,.35)] hover:shadow-[0_6px_28px_rgba(179,135,42,.5)]',
          )}
        >
          {exporting ? (
            <div className="w-4 h-4 border-2 border-[var(--gold)] border-t-transparent rounded-full animate-spin" />
          ) : (
            <Download className="w-4 h-4" />
          )}
          {exporting ? t('records.exporting') : t('records.export')}
        </button>
      </div>
    </Modal>
  )
}

export default BillingExportModal
