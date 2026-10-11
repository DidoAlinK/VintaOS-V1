/**
 * Vinta School OS — browser file download
 *
 * The blob→anchor→click dance, in one place. It has to exist as a real
 * `<a download>`: `window.open` on a blob URL is blocked as a popup in most
 * browsers, and `location.href = url` navigates away from the app, which loses
 * whatever the user was in the middle of.
 *
 * The object URL is revoked immediately after the click. The click is
 * synchronous, so the browser has already taken its reference by the time the
 * URL is released — leaving it un-revoked would pin the whole file in memory
 * for the life of the page, which on a large export is the entire dataset.
 */
export function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * A filename that says what is inside it.
 *
 * Someone who exports a term, then a year, then a single month ends up with
 * three files in one Downloads folder; `billing-records.csv` three times tells
 * them nothing about which is which.
 */
export function describeRange(from: string, to: string): string {
  if (from && to) return `${from}_to_${to}`
  if (from) return `from_${from}`
  if (to) return `up_to_${to}`
  return 'all'
}
