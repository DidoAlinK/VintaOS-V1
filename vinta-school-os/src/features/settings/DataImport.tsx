import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, CheckCircle2, FileSpreadsheet, Upload } from 'lucide-react'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { cn } from '../../lib/cn'
import api, { type ApiError } from '../../lib/api'
import { toast } from '../../stores/uiStore'

/* ─── The shape the server answers with ───
   `import_service.Report.as_dict()` for one file, or `import_zip()`'s
   `{archive, files}` when an Export-School ZIP was dropped. Kept as a local
   type rather than imported from a shared one because nothing else in the
   interface has ever needed to describe an import. */

type RowError = { row: number; code: string; message: string }

type FileReport = {
  /** Present only when the entry came out of an archive. */
  file?: string
  dataset: string | null
  dry_run: boolean
  total: number
  created: number
  updated: number
  skipped: number
  failed: number
  errors: RowError[]
  errors_truncated: boolean
  notes: string[]
  candidates?: string[]
}

type ArchiveReport = { archive: true; dry_run: boolean; files: FileReport[] }

type Report = FileReport | ArchiveReport

function isArchive(report: Report): report is ArchiveReport {
  return (report as ArchiveReport).archive === true
}

/** What the server says when it cannot tell what a file is. */
type DetectionFailure = { code: string; candidates?: string[] }

/**
 * The upload itself, shared by the preview and the commit.
 *
 * `dataset` is only sent when the owner has resolved an ambiguity — the server
 * otherwise detects, and sending an empty string would be the same as sending
 * nothing but would read as a deliberate choice.
 */
async function postFile(file: File, dryRun: boolean, dataset?: string | null): Promise<Report> {
  const form = new FormData()
  form.append('file', file)
  if (dryRun) form.append('dry_run', '1')
  if (dataset) form.append('dataset', dataset)

  // `multipart/form-data` without a boundary in the string: axios leaves the
  // boundary to the browser, which is the only thing that knows it.
  const response = await api.post<Report>('/settings/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return response.data
}

/** Turn an axios failure into the machine-readable code the screen translates. */
function failureOf(error: unknown): DetectionFailure {
  const data = (error as { response?: { data?: ApiError & DetectionFailure } })?.response?.data
  if (data?.code) return { code: data.code, candidates: data.candidates }
  return { code: 'server_error' }
}

/* ─── One file's outcome ─── */

function ReportRow({ report, datasetLabel }: {
  report: FileReport
  datasetLabel: (key: string | null) => string
}) {
  const { t } = useTranslation('settings')
  const [open, setOpen] = useState(false)

  const hasErrors = report.errors.length > 0

  return (
    <div className="rounded-[var(--radius-sm)] bg-[var(--input-bg)] border border-[var(--glass-border)]">
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <FileSpreadsheet className="w-4 h-4 shrink-0 text-[var(--muted)]" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-[var(--text)] truncate">
              {report.file || datasetLabel(report.dataset)}
            </p>
            <p className="text-xs text-[var(--muted)] truncate">
              {report.dataset ? datasetLabel(report.dataset) : t('import.error.unknown_dataset')}
              {' · '}
              {t('import.summary', {
                created: report.created,
                updated: report.updated,
                skipped: report.skipped,
                failed: report.failed,
              })}
            </p>
          </div>
        </div>

        {hasErrors && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="shrink-0 inline-flex items-center gap-1.5 text-xs font-medium text-[var(--red)] hover:underline"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            {report.failed}
          </button>
        )}
      </div>

      {/* Why the notes are worth a line of their own: they are not failures,
          they are things the format cannot carry — a weekly schedule, a
          payment — and saying so is what stops the count from reading as a
          silent loss. */}
      {report.notes.length > 0 && (
        <ul className="px-4 pb-2 flex flex-col gap-1">
          {report.notes.map((note) => (
            <li key={note} className="text-xs text-[var(--muted)]">
              {t(`import.note.${note}`, { defaultValue: note })}
            </li>
          ))}
        </ul>
      )}

      {hasErrors && open && (
        <ul className="px-4 pb-3 flex flex-col gap-1 border-t border-[var(--glass-border)] pt-2">
          {report.errors.map((error, index) => (
            <li key={`${error.row}-${index}`} className="text-xs text-[var(--muted)]">
              {t('import.rowError', {
                row: error.row,
                message: t(`import.row.${error.code}`, {
                  name: error.message,
                  defaultValue: error.message || error.code,
                }),
              })}
            </li>
          ))}
          {report.errors_truncated && (
            <li className="text-xs text-[var(--muted)] italic">
              {t('import.errorsTruncated', { count: report.errors.length })}
            </li>
          )}
        </ul>
      )}
    </div>
  )
}

/* ─── Component ─── */

export function DataImport() {
  const { t } = useTranslation('settings')
  const inputRef = useRef<HTMLInputElement>(null)

  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  /** Set when detection tied: the datasets it might be, waiting for a choice. */
  const [candidates, setCandidates] = useState<string[] | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  /** True once the shown report is the result of a real write, not a preview. */
  const [committed, setCommitted] = useState(false)

  const datasetLabel = useCallback(
    (key: string | null) => (key ? t(`import.datasets.${key}`, { defaultValue: key }) : ''),
    [t],
  )

  /* A file dropped anywhere but the zone would otherwise navigate the page to
     it, replacing the app with a CSV. Swallowing the default at the window
     means a near-miss is a no-op rather than a lost session. */
  useEffect(() => {
    const swallow = (event: DragEvent) => event.preventDefault()
    window.addEventListener('dragover', swallow)
    window.addEventListener('drop', swallow)
    return () => {
      window.removeEventListener('dragover', swallow)
      window.removeEventListener('drop', swallow)
    }
  }, [])

  const reset = useCallback(() => {
    setFile(null)
    setReport(null)
    setCandidates(null)
    setFailure(null)
    setCommitted(false)
    setBusy(false)
    if (inputRef.current) inputRef.current.value = ''
  }, [])

  /** Preview: detect and count, write nothing. */
  const preview = useCallback(async (chosen: File, dataset?: string | null) => {
    setBusy(true)
    setFailure(null)
    setCandidates(null)
    setCommitted(false)
    try {
      setReport(await postFile(chosen, true, dataset))
    } catch (error) {
      const { code, candidates: options } = failureOf(error)
      // Two datasets scored the same. Rather than guess, offer the choice —
      // a pick re-runs the preview, so the confirm step is still in front of
      // the write.
      if (options && options.length > 1) setCandidates(options)
      else setFailure(code)
      setReport(null)
    } finally {
      setBusy(false)
    }
  }, [])

  const accept = useCallback((chosen: File | undefined | null) => {
    // A second drop while the first is still being read or written would race
    // the answer against itself.
    if (!chosen || busy) return
    reset()
    setFile(chosen)
    void preview(chosen)
  }, [busy, preview, reset])

  /** Commit: the same file, this time written. */
  const confirm = useCallback(async () => {
    if (!file) return
    // An archive is re-detected member by member; only a single file carries
    // the dataset the owner may have had to choose.
    const dataset = report && !isArchive(report) ? report.dataset : null
    setBusy(true)
    try {
      const result = await postFile(file, false, dataset)
      setReport(result)
      setCommitted(true)
      setCandidates(null)
      const totals = isArchive(result)
        ? result.files.reduce(
            (acc, f) => ({
              created: acc.created + f.created,
              updated: acc.updated + f.updated,
              failed: acc.failed + f.failed,
            }),
            { created: 0, updated: 0, failed: 0 },
          )
        : result
      toast.success(
        t('import.summary', {
          created: totals.created,
          updated: totals.updated,
          skipped: isArchive(result) ? 0 : result.skipped,
          failed: totals.failed,
        }),
      )
    } catch (error) {
      const { code } = failureOf(error)
      toast.error(t(`import.error.${code}`, { defaultValue: t('import.fail') }))
    } finally {
      setBusy(false)
    }
  }, [candidates, file, report, t])

  const files: FileReport[] = useMemo(
    () => (report ? (isArchive(report) ? report.files : [report]) : []),
    [report],
  )

  return (
    <Card>
      <CardHeader
        title={t('import.title')}
        actions={<Upload className="w-4 h-4 text-[var(--muted)]" />}
      />
      <CardBody>
        <p className="text-sm text-[var(--muted)] mb-4">{t('import.description')}</p>

        <div
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={(event) => {
            // Only when the pointer has left the zone itself, not stepped onto
            // one of its children.
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
              setDragging(false)
            }
          }}
          onDrop={(event) => {
            event.preventDefault()
            setDragging(false)
            accept(event.dataTransfer.files?.[0])
          }}
          className={cn(
            'flex flex-col items-center justify-center gap-3 text-center',
            'px-6 py-8 rounded-[var(--radius-md)] border-2 border-dashed',
            'transition-colors duration-200',
            dragging
              ? 'border-[var(--gold)] bg-[var(--glass-strong)]'
              : 'border-[var(--glass-border)] bg-[var(--input-bg)]',
          )}
        >
          <Upload className={cn('w-7 h-7', dragging ? 'text-[var(--gold)]' : 'text-[var(--muted)]')} />
          <p className="text-sm font-medium text-[var(--text)]">
            {dragging ? t('import.dragActive') : t('import.drop')}
          </p>
          <p className="text-xs text-[var(--muted)]">{t('import.or')}</p>

          {/* The picker is a real file dialog, which is the only thing that
              works once this ships as a packaged .exe — there is no browser
              chrome to drop onto. */}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.zip,.txt,text/csv,application/zip"
            className="hidden"
            onChange={(event) => accept(event.target.files?.[0])}
          />
          <Button
            variant="secondary"
            size="sm"
            loading={busy && !report}
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            {t('import.browse')}
          </Button>

          {file && (
            <p className="text-xs text-[var(--muted)] truncate max-w-full">{file.name}</p>
          )}
        </div>

        {/* Detection tied: the file could be read two ways, so the owner picks
            rather than the server guessing. */}
        {candidates && (
          <div className="mt-4 flex flex-col gap-3">
            <p className="text-sm text-[var(--text)]">{t('import.pick')}</p>
            <div className="flex flex-wrap gap-2">
              {candidates.map((key) => (
                <Button
                  key={key}
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => file && void preview(file, key)}
                >
                  {datasetLabel(key)}
                </Button>
              ))}
            </div>
          </div>
        )}

        {failure && (
          <p className="mt-4 flex items-center gap-2 text-sm text-[var(--red)]">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {t(`import.error.${failure}`, { defaultValue: t('import.fail') })}
          </p>
        )}

        {/* The report. Before the confirm it is a preview — the counts are what
            *would* happen — so the note says so and the only button offered is
            the one that writes. */}
        {report && (
          <div className="mt-4 flex flex-col gap-3">
            {files.length > 1 && (
              <p className="text-xs font-medium text-[var(--muted)] uppercase tracking-wide">
                {t('import.filesTitle')}
              </p>
            )}

            <div className="flex flex-col gap-2">
              {files.map((entry, index) => (
                <ReportRow
                  key={entry.file ?? `${entry.dataset}-${index}`}
                  report={entry}
                  datasetLabel={datasetLabel}
                />
              ))}
            </div>

            {!committed && (
              <>
                <p className="text-xs text-[var(--muted)]">{t('import.previewNote')}</p>
                <div className="flex items-center gap-2">
                  <Button size="sm" loading={busy} disabled={busy} onClick={confirm}>
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {t('import.confirm')}
                  </Button>
                  <Button variant="ghost" size="sm" disabled={busy} onClick={reset}>
                    {t('import.cancel')}
                  </Button>
                </div>
              </>
            )}

            {committed && (
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={reset}>
                  {t('import.close')}
                </Button>
              </div>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}

export default DataImport
