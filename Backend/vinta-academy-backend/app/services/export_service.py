"""
Vinta School OS — Export Service
CSV generators for Student Roster, Billing History, Teacher Hours.
"""
import csv
import io
import os
import re
from datetime import date, datetime
from xml.sax.saxutils import escape
from sqlalchemy import desc
from app.extensions import db
from app.i18n import translator
from app.models.academy import Academy
from app.models.student import Student, Guardian, Enrollment
from app.models.billing import StudentBilling, PaymentLog
from app.models.teacher import Teacher, TeacherHoursLog
from app.models.scheduling import Session
from app.utils.formatters import format_dzd


# ── Billing-records export ─────────────────────────────────────────────
#
# CSV and PDF share their headers, their row builder and their totals, so the
# two formats can never drift into meaning different things.

#: Column headers for a billing-records export, in order.
BILLING_RECORD_HEADERS = (
    "Date", "Type", "Direction", "Profile", "Label",
    "Amount (DA)", "Status", "Method", "Notes",
)

#: Base font for the PDF. Arabic needs a real TTF — the built-in PDF fonts carry
#: Latin only and would draw Arabic as blanks — so an Arabic-capable font is
#: registered on first use. This matches what the review build already
#: documents for the UI: "Arabic text uses your computer's own Arabic font
#: rather than the app's font" (packaging/README-FIRST.txt).
_BASE_FONT = "Helvetica"

#: The font the application ships with, for machines that have none of the
#: system fonts below. Amiri (SIL Open Font License — see
#: `app/assets/fonts/OFL.txt`) carries Arabic *and* Latin in one file, which is
#: what a billing table needs in either direction: a French export still holds
#: Arabic names, and an Arabic one still holds "DA" and Western digits.
_BUNDLED_FONT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "fonts", "Amiri-Regular.ttf",
)

#: Tried in order. The bundled font comes last so a desktop install keeps
#: rendering exactly as it did before it was bundled, and is present at all so
#: that a Linux server or the packaged review build produces Arabic instead of
#: a page of blank glyphs.
_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    _BUNDLED_FONT,
)


def _ensure_font() -> str:
    """Register an Arabic-capable TTF if one exists. Returns the font name.

    Idempotent — reportlab holds one font registry per process, and registering
    the same name twice would raise.
    """
    global _BASE_FONT
    if _BASE_FONT != "Helvetica":
        return _BASE_FONT

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path in _FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            pdfmetrics.registerFont(TTFont("VintaArabic", path))
            _BASE_FONT = "VintaArabic"
            return _BASE_FONT
        except Exception:
            # A font that will not register is not worth failing an export over.
            continue
    return _BASE_FONT


def shape_arabic(text: str) -> str:
    """Reshape and reorder Arabic so a PDF font draws it correctly.

    Arabic letters change shape depending on their neighbours and run
    right-to-left. A PDF font knows none of that, so unshaped Arabic comes out
    as disconnected letters in the wrong order.
    """
    if not text:
        return text
    if not any("\u0600" <= ch <= "\u06ff" for ch in text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        # Shaping is a nicety. Losing it must never lose the export.
        return text


def _word(t, key: str, fallback: str) -> str:
    """A translated word, or `fallback` when the catalogue has no such key.

    The translator answers an unknown key with the key itself, which is the
    right default for a sentence but the wrong one for a record's kind: a kind
    added to the database later has to print as itself, not as
    ``export.billing.kind.WHATEVER`` down a column of a financial document.
    """
    text = t(key)
    return fallback if text == key else text


def _record_row(record: dict, t) -> list:
    """One billing record as export cells, matching BILLING_RECORD_HEADERS.

    The row builder is shared with the CSV so the two formats cannot drift into
    meaning different things, which is why the translator is passed in rather
    than chosen here. The CSV hands it English on purpose: a spreadsheet is
    data, its headers get read by formulas and scripts, and the export the
    request named was the PDF.
    """
    # `direction` is set by the service for every record. If it were ever
    # missing, defaulting to "Out" would quietly understate the academy's
    # income in a financial file — so fall back to the record's kind, which is
    # the structural fact the direction is derived from anyway.
    direction = record.get("direction")
    if direction not in ("IN", "OUT"):
        direction = "IN" if record.get("kind") == "STUDENT_PAYMENT" else "OUT"

    kind = record.get("kind") or ""

    return [
        record.get("date") or "",
        _word(t, f"export.billing.kind.{kind}", kind) if kind else "",
        t("export.billing.direction.in") if direction == "IN"
        else t("export.billing.direction.out"),
        record.get("profile_name") or "",
        record.get("label") or record.get("detail") or "",
        record.get("amount_da") or 0,
        record.get("status") or "",
        record.get("method") or "",
        record.get("notes") or "",
    ]


def _export_meta(academy_id: str, totals: dict) -> dict:
    """The header block printed on top of an export.

    Currency is not read from settings and rendered here: it is locked to DZD
    (see `app/routes/settings.py`, which refuses any other value), and the
    frontend contract is that "DA" is never translated.
    """
    # Guarded, because `db.session.get(Model, None)` is not the harmless
    # no-op it looks like: SQLAlchemy 2.0 warns that a fully-NULL identity
    # cannot load anything and that a future release may raise instead. The
    # name is decoration on a header — a missing one must not cost the owner
    # their document.
    academy = db.session.get(Academy, academy_id) if academy_id else None
    return {
        "academy": (getattr(academy, "name", "") or ""),
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "totals": totals,
    }


def billing_records_csv(records: list, meta: dict) -> str:
    """The billing-records export as CSV text, with footer totals.

    Written in English whatever the interface language is, and not by
    accident: a CSV is read by formulas and scripts far more often than by a
    person, and its column names are the contract those were written against.
    Renaming a column because the desk switched to French would break the
    spreadsheet somebody built last month. The PDF is the format that follows
    the interface language; this one stays still.
    """
    t = translator("en")

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Academy", meta["academy"]])
    writer.writerow(["Generated", meta["generated"]])
    writer.writerow([])
    writer.writerow(list(BILLING_RECORD_HEADERS))
    for record in records:
        writer.writerow(_record_row(record, t))

    totals = meta["totals"]
    writer.writerow([])
    writer.writerow(["Money in (DA)", totals["money_in_da"]])
    writer.writerow(["Money out (DA)", totals["money_out_da"]])
    writer.writerow(["Net (DA)", totals["net_da"]])

    return output.getvalue()


def billing_records_pdf(records: list, meta: dict, language: str = "en") -> bytes:
    """The billing-records export as PDF bytes, written in `language`.

    Why a server-side PDF at all — the brief was that this must never break in
    the hands of a non-technical user:

      * A browser "print to PDF" renders fonts perfectly, but the user then has
        to pick a printer, pick "Save as PDF", and pick a folder. Three
        decisions, and that is where non-technical users get lost.
      * jsPDF would keep a dependency out of the backend, but it cannot shape
        Arabic without an embedded font and extra machinery, so an Algerian
        academy's Arabic names and notes would come out as disconnected or blank
        glyphs.

    Generating it here means one click and the file downloads, identical on
    every machine, with Arabic handled properly.

    `language` is whatever the browser sent — ``"ar"``, or the full
    ``"ar-DZ,ar;q=0.9"`` — and is resolved by `app.i18n`. Translating the words
    is only half of matching the interface: a right-to-left language also
    mirrors the column order and sets the text against the other margin,
    because a table that reads right to left while its columns still run left
    to right is not an Arabic document, it is an English one with Arabic words
    in it.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    t = translator(language)
    font = _ensure_font()

    # Columns in reading order, each with the width its contents need: a date
    # and a direction are narrow; a profile name and a note are not.
    #
    # Widths live in the same list as the headings rather than in a second one,
    # because a right-to-left document reverses the table. Two lists that have
    # to be reversed together are two lists that eventually get reversed
    # separately, and then every column sits under its neighbour's heading.
    columns = [
        (20 * mm, "export.billing.col.date"),
        (26 * mm, "export.billing.col.type"),
        (15 * mm, "export.billing.col.direction"),
        (38 * mm, "export.billing.col.profile"),
        (34 * mm, "export.billing.col.label"),
        (22 * mm, "export.billing.col.amount"),
        (18 * mm, "export.billing.col.status"),
        (20 * mm, "export.billing.col.method"),
        (52 * mm, "export.billing.col.notes"),
    ]
    money_column = [key for _, key in columns].index("export.billing.col.amount")
    if t.rtl:
        columns.reverse()
        money_column = len(columns) - 1 - money_column

    widths = [width for width, _ in columns]
    headings = [t(key) for _, key in columns]

    def paragraph(text, style):
        """Every string in this document passes through here.

        Shaping only the data cells is not enough once the headings, the title
        and the totals around them are Arabic too: unshaped Arabic draws as
        disconnected letters in the wrong order, and it does so just as
        convincingly in a heading as in a name.
        """
        return Paragraph(escape(shape_arabic(str(text))), style)

    rows = []
    for record in records:
        cells = _record_row(record, t)
        if t.rtl:
            cells.reverse()
        rows.append(cells)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title=t("export.billing.title"),
        author=meta["academy"] or "Vinta School OS",
    )

    # Text runs against the inline start: the left margin in English and
    # French, the right one in Arabic.
    start = TA_RIGHT if t.rtl else TA_LEFT

    body = ParagraphStyle(
        "cell", fontName=font, fontSize=7.5, leading=9.5,
        textColor=colors.HexColor("#1f2937"), alignment=start,
    )
    # Money carries its own style instead of a TableStyle ALIGN rule, because a
    # Paragraph fills the cell it is given: aligning the flowable inside the
    # cell moves nothing, and the alignment has to sit on the paragraph.
    money = ParagraphStyle("cellMoney", parent=body, alignment=TA_RIGHT)
    head = ParagraphStyle(
        "head", parent=body, fontSize=7.5, leading=9.5, textColor=colors.white,
    )
    title_style = ParagraphStyle(
        "title", fontName=font, fontSize=14, leading=17,
        textColor=colors.HexColor("#111827"), alignment=start,
    )
    meta_style = ParagraphStyle(
        "meta", fontName=font, fontSize=8.5, leading=11,
        textColor=colors.HexColor("#6b7280"), alignment=start,
    )

    totals = meta["totals"]
    summary = "   ·   ".join([
        f"{t('export.billing.totals.in')}: {format_dzd(totals['money_in_da'])}",
        f"{t('export.billing.totals.out')}: {format_dzd(totals['money_out_da'])}",
        f"{t('export.billing.totals.net')}: {format_dzd(totals['net_da'])}",
    ])

    story = [
        paragraph(t("export.billing.title"), title_style),
        paragraph(
            t(
                "export.billing.meta",
                academy=meta["academy"],
                when=meta["generated"],
            ),
            meta_style,
        ),
        paragraph(summary, meta_style),
        Spacer(1, 6 * mm),
    ]

    data = [[paragraph(heading, head) for heading in headings]]
    for cells in rows:
        data.append([
            paragraph(value, money if index == money_column else body)
            for index, value in enumerate(cells)
        ])

    empty = not rows
    if empty:
        data.append(
            [paragraph(t("export.billing.empty"), body)]
            + [""] * (len(headings) - 1)
        )

    rules = []
    if empty:
        # One sentence, not a date. Left inside the first column it would wrap
        # in a 20 mm cell, a word to a line, so the row is merged across the
        # table before anything else is asked of it.
        rules.append(("SPAN", (0, -1), (-1, -1)))
    rules += [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f6b4d")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        # Zebra striping: the cheapest thing that makes a wide table readable
        # without drawing a rule for every column.
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f9fafb")]),
    ]

    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle(rules))
    story.append(table)

    doc.build(story)
    return buffer.getvalue()


def export_billing_records(
    academy_id: str, filters: dict = None, fmt: str = "csv",
    language: str = None,
) -> tuple:
    """The billing-records export, ready to hand to a response.

    Returns ``(payload, mimetype, filename)`` so the route stays a route: it
    reads the request, calls this, and writes the bytes out. Raises ValueError
    for a bad filter, which the caller turns into a 400.

    The record set comes from ``billing_service.list_billing_records`` — the
    same function behind the on-screen archive — so the file and the screen can
    never disagree about what the filters selected.

    `language` is the request's ``Accept-Language``, and only the PDF uses it:
    see `billing_records_csv` for why the CSV is deliberately left in English.
    """
    from app.services.billing_service import list_billing_records

    result = list_billing_records(academy_id, filters)
    meta = _export_meta(academy_id, result["totals"])

    if fmt == "pdf":
        return (
            billing_records_pdf(result["records"], meta, language),
            "application/pdf",
            "billing-records.pdf",
        )
    return (
        billing_records_csv(result["records"], meta),
        "text/csv",
        "billing-records.csv",
    )


# ── Teacher statement export ───────────────────────────────────────────
#
# One teacher's finances: what their students brought in, what share of it is
# theirs, what has been settled and what has not, which groups it came from,
# and the individual payouts it is made of.
#
# Built exactly like the billing-records export above, and for the same reason:
# the CSV and the PDF share their row builders, so the two formats cannot drift
# into meaning different things. The CSV stays English (see
# `billing_records_csv` for why); the PDF follows the interface language and
# mirrors itself for Arabic.

#: Column headers for a teacher statement's line items, in order.
TEACHER_PAYOUT_HEADERS = (
    "Date", "Group", "Source", "Gross (DA)", "Teacher cut (DA)",
    "Status", "Hours", "Notes",
)

#: Column headers for the per-group summary that follows the lines.
TEACHER_GROUP_HEADERS = (
    "Group", "Sessions", "Gross (DA)", "Teacher cut (DA)", "Still owed (DA)",
)


def _ascii_slug(text: str, fallback: str = "teacher") -> str:
    """A filename-safe ASCII slug.

    The ``Content-Disposition`` header is bytes, and a browser that disagrees
    with our encoding is exactly how a download arrives named
    ``Ø£Ù…ÙŠÙ†.pdf`` or, worse, not at all. So the name is transliterated down
    to ``[a-z0-9-]``; a teacher whose name has no Latin characters in it gets a
    file named after the document instead of after themselves. The bytes inside
    the file still carry the real name — only the filename on disk is dumbed
    down, because the filename is the one part that has no encoding of its own.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-").lower()
    return slug[:48] or fallback


def _payout_source(line: dict, t) -> str:
    """Where a payout line came from — a session, or someone typing it in."""
    source = line.get("source") or "SESSION"
    return _word(t, f"export.teacher.source.{source}", source)


def _teacher_payout_row(line: dict, t) -> list:
    """One payout line as export cells, matching TEACHER_PAYOUT_HEADERS.

    ``status`` is deliberately *not* translated: ``PAID`` and ``PENDING`` are
    the enum values the rest of the system matches on, and a financial file is
    not the place to start spelling them differently.
    """
    return [
        line.get("date") or "",
        line.get("group_name") or "",
        _payout_source(line, t),
        int(line.get("gross_revenue_da") or 0),
        int(line.get("teacher_cut_da") or 0),
        line.get("status") or "",
        line.get("duration_hours") or 0,
        line.get("notes") or "",
    ]


def _teacher_payout_lines(details: dict) -> list:
    """The statement's line items as a list, never None.

    The details payload only carries ``lines`` when the caller asked for them —
    the on-screen card does not, because a few thousand rows is a heavy way to
    say four numbers. An export is the caller that always wants them, so an
    export built from a payload that skipped them would silently produce a
    summary-only file that still claims to be a statement. The route asks with
    ``include_lines=True``; this guards the shape either way.
    """
    return details.get("lines") or []


def _payout_period_span(details: dict, t) -> str:
    """The window the statement covers, as a value with no label on it.

    Kept apart from `_payout_period` because the two formats need it in two
    shapes. The CSV has a label column of its own, so a value that announced
    itself would print as ``Period,Period: 2026-09-01 to 2026-09-30`` — the
    label said twice, which is what a mechanically-built file looks like. The
    PDF has no label column, so it wants the whole sentence.
    """
    window = details.get("window") or {}
    start, end = window.get("from"), window.get("to")
    if start and end:
        return t("export.teacher.period.spans.range", start=start, end=end)
    if start:
        return t("export.teacher.period.spans.from", start=start)
    if end:
        return t("export.teacher.period.spans.until", end=end)
    return t("export.teacher.period.spans.all")


def _payout_period(details: dict, t) -> str:
    """The window the statement covers, as a sentence for the PDF.

    The separator lives in the catalogue key rather than in a format string
    here, because French puts a space before its colon and English does not —
    a detail that belongs with the words, not with the code that joins them.
    """
    return t("export.teacher.period.line", span=_payout_period_span(details, t))


def _cadence_phrase(t, schedule: dict) -> str:
    """The payroll cadence as a sentence.

    ``format_cadence`` returns a machine phrase (``weekly:sunday``,
    ``monthly:5``, ``none``) because it is written for the activity log. Here it
    is unpacked into the catalogue's words, so the phrase is translated rather
    than pasted through — and an unrecognised weekday degrades to "by hand"
    rather than printing a stray key down a financial document.
    """
    from app.services.payout_schedule_service import WEEKDAY_NAMES, format_cadence

    schedule = schedule or {}
    key = format_cadence(
        schedule.get("cadence"),
        schedule.get("day_of_week"),
        schedule.get("day_of_month"),
    )
    if key.startswith("weekly:"):
        name = key.split(":", 1)[1]
        if name in WEEKDAY_NAMES:
            return t("export.teacher.cadence.weekly",
                     day=t(f"export.teacher.weekday.{name}"))
    elif key.startswith("monthly:"):
        return t("export.teacher.cadence.monthly", day=key.split(":", 1)[1])
    return t("export.teacher.cadence.none")


def _summary_pairs(details: dict, t) -> list:
    """The teacher's totals as ``(label, value)`` pairs, in reading order.

    One list feeds both formats, so the CSV and the PDF cannot disagree about
    what the teacher earned. Money goes through ``format_dzd`` for the same
    reason the rest of the app does: the currency code is never translated and
    the thousands separator should not depend on who is reading.
    """
    return [
        (t("export.teacher.summary.gross"),
         format_dzd(details.get("gross_revenue_da") or 0)),
        (t("export.teacher.summary.cut"),
         format_dzd(details.get("teacher_cut_da") or 0)),
        (t("export.teacher.summary.pending"),
         format_dzd(details.get("pending_da") or 0)),
        (t("export.teacher.summary.paid"),
         format_dzd(details.get("paid_da") or 0)),
        (t("export.teacher.summary.average"),
         format_dzd(details.get("average_class_revenue_da") or 0)),
        (t("export.teacher.summary.sessions"), str(details.get("session_count") or 0)),
        (t("export.teacher.summary.manual"), str(details.get("manual_count") or 0)),
        (t("export.teacher.summary.hours"), f"{details.get('duration_hours') or 0:g}"),
        (t("export.teacher.summary.students"), str(details.get("students_taught") or 0)),
        (t("export.teacher.summary.groups"), str(details.get("group_count") or 0)),
    ]


def teacher_payout_csv(details: dict, meta: dict) -> str:
    """One teacher's statement as CSV text, in English like its sibling.

    Same contract as `billing_records_csv`: the headings stay English so a
    spreadsheet or a script built against them keeps working when the desk
    switches the interface to French. The PDF is the format that follows the
    interface language; this one stays still.

    The layout is a header block, the totals, the payout lines, then the
    per-group summary — the order the card on screen reads in, so the file and
    the screen can be checked against each other line by line.
    """
    t = translator("en")
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Teacher", details.get("teacher_name") or ""])
    writer.writerow(["Academy", meta["academy"]])
    writer.writerow(["Generated", meta["generated"]])
    writer.writerow([
        t("export.teacher.period.label"), _payout_period_span(details, t),
    ])
    writer.writerow(["Payroll", _cadence_phrase(t, details.get("schedule"))])
    writer.writerow([])

    for label, value in _summary_pairs(details, t):
        writer.writerow([label, value])

    writer.writerow([])
    writer.writerow(list(TEACHER_PAYOUT_HEADERS))
    for line in _teacher_payout_lines(details):
        writer.writerow(_teacher_payout_row(line, t))

    writer.writerow([])
    writer.writerow(list(TEACHER_GROUP_HEADERS))
    for group in details.get("groups") or []:
        writer.writerow([
            group.get("group_name") or "",
            group.get("session_count") or 0,
            group.get("gross_revenue_da") or 0,
            group.get("teacher_cut_da") or 0,
            group.get("pending_da") or 0,
        ])

    return output.getvalue()


def teacher_payout_pdf(details: dict, meta: dict, language: str = "en") -> bytes:
    """One teacher's statement as PDF bytes, written in `language`.

    The same reasoning as `billing_records_pdf` applies, plus one of its own:
    this is the document an academy hands a teacher, and in Algeria that
    document is as likely to be read in Arabic as in French. A statement that
    prints a person's own name as disconnected letters is not a statement they
    can be asked to check.

    `language` is whatever the browser sent — ``"ar"``, or the full
    ``"ar-DZ,ar;q=0.9"`` — and is resolved by `app.i18n`. Matching the interface
    means more than the words: a right-to-left language mirrors the tables and
    sets the text against the other margin, and every string in the document —
    headings, totals, group names, notes — passes through the Arabic shaper,
    because an unshaped heading is exactly as unreadable as an unshaped name.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    t = translator(language)
    font = _ensure_font()

    def paragraph(text, style):
        return Paragraph(escape(shape_arabic(str(text))), style)

    # Text runs against the inline start: the left margin in English and
    # French, the right one in Arabic.
    start = TA_RIGHT if t.rtl else TA_LEFT

    body = ParagraphStyle(
        "cell", fontName=font, fontSize=8, leading=10,
        textColor=colors.HexColor("#1f2937"), alignment=start,
    )
    # Money carries its own style instead of a TableStyle ALIGN rule, because a
    # Paragraph fills the cell it is given: aligning the flowable inside the
    # cell moves nothing, and the alignment has to sit on the paragraph.
    money = ParagraphStyle("cellMoney", parent=body, alignment=TA_RIGHT)
    head = ParagraphStyle(
        "head", parent=body, fontSize=8, leading=10, textColor=colors.white,
    )
    title_style = ParagraphStyle(
        "title", fontName=font, fontSize=14, leading=17,
        textColor=colors.HexColor("#111827"), alignment=start,
    )
    meta_style = ParagraphStyle(
        "meta", fontName=font, fontSize=8.5, leading=11,
        textColor=colors.HexColor("#6b7280"), alignment=start,
    )
    section_style = ParagraphStyle(
        "section", parent=meta_style, fontSize=9.5, leading=12,
        textColor=colors.HexColor("#111827"),
    )

    def build_table(column_defs, rows, money_keys=(), empty_key=None):
        """A table whose column order follows the text direction.

        Widths live in the same list as the headings rather than in a second
        one, because a right-to-left document reverses the table. Two lists that
        have to be reversed together are two lists that eventually get reversed
        separately, and then every column sits under its neighbour's heading.
        """
        columns = list(column_defs)
        if t.rtl:
            columns.reverse()
        widths = [width for width, _ in columns]
        headings = [t(key) for _, key in columns]
        money_at = {i for i, (_, key) in enumerate(columns) if key in money_keys}

        cells = []
        for row in rows:
            values = list(row)
            if t.rtl:
                values.reverse()
            cells.append([
                paragraph(value, money if i in money_at else body)
                for i, value in enumerate(values)
            ])

        data = [[paragraph(heading, head) for heading in headings]] + cells
        rules = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f6b4d")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
            # Zebra striping: the cheapest thing that makes a wide table
            # readable without drawing a rule for every column.
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f9fafb")]),
        ]
        if empty_key and not rows:
            # One sentence, not a date. Left inside the first column it would
            # wrap in a 20 mm cell, a word to a line, so the row is merged
            # across the table before anything else is asked of it.
            data.append(
                [paragraph(t(empty_key), body)] + [""] * (len(headings) - 1)
            )
            rules.append(("SPAN", (0, -1), (-1, -1)))

        table = Table(data, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle(rules))
        return table

    line_columns = [
        (20 * mm, "export.teacher.col.date"),
        (38 * mm, "export.teacher.col.group"),
        (22 * mm, "export.teacher.col.source"),
        (26 * mm, "export.teacher.col.gross"),
        (28 * mm, "export.teacher.col.cut"),
        (20 * mm, "export.teacher.col.status"),
        (16 * mm, "export.teacher.col.hours"),
        (74 * mm, "export.teacher.col.notes"),
    ]
    group_columns = [
        (70 * mm, "export.teacher.groups.name"),
        (26 * mm, "export.teacher.groups.sessions"),
        (32 * mm, "export.teacher.groups.gross"),
        (34 * mm, "export.teacher.groups.cut"),
        (34 * mm, "export.teacher.groups.pending"),
    ]

    schedule = details.get("schedule") or {}
    # An em dash rather than a blank: "next:" followed by nothing reads as a
    # rendering fault, while "next: —" reads as "there isn't one", which for a
    # teacher on a manual payroll is the honest answer.
    next_payout = schedule.get("next_payout_date") or "—"
    last_payout = schedule.get("last_payout_date") or "—"

    story = [
        paragraph(t("export.teacher.title"), title_style),
        paragraph(
            t(
                "export.teacher.meta",
                teacher=details.get("teacher_name") or "",
                when=meta["generated"],
            ),
            meta_style,
        ),
        paragraph(_payout_period(details, t), meta_style),
        paragraph(
            t(
                "export.teacher.schedule.line",
                cadence=_cadence_phrase(t, schedule),
                next=next_payout,
                last=last_payout,
            ),
            meta_style,
        ),
        Spacer(1, 5 * mm),
    ]

    # The totals in rows of three, rather than one long run-on line: ten labelled
    # figures separated by dots wrap somewhere unpredictable, and a wrapped
    # label reads as belonging to the figure above it.
    pairs = _summary_pairs(details, t)
    for index in range(0, len(pairs), 3):
        chunk = pairs[index:index + 3]
        story.append(paragraph(
            "   ·   ".join(f"{label}: {value}" for label, value in chunk),
            meta_style,
        ))

    story += [
        Spacer(1, 6 * mm),
        paragraph(t("export.teacher.lines.title"), section_style),
        Spacer(1, 2 * mm),
        build_table(
            line_columns,
            [_teacher_payout_row(line, t) for line in _teacher_payout_lines(details)],
            money_keys=(
                "export.teacher.col.gross",
                "export.teacher.col.cut",
                "export.teacher.col.hours",
            ),
            empty_key="export.teacher.lines.empty",
        ),
        Spacer(1, 6 * mm),
        paragraph(t("export.teacher.groups.title"), section_style),
        Spacer(1, 2 * mm),
        build_table(
            group_columns,
            [
                [
                    group.get("group_name") or "",
                    group.get("session_count") or 0,
                    group.get("gross_revenue_da") or 0,
                    group.get("teacher_cut_da") or 0,
                    group.get("pending_da") or 0,
                ]
                for group in details.get("groups") or []
            ],
            money_keys=(
                "export.teacher.groups.sessions",
                "export.teacher.groups.gross",
                "export.teacher.groups.cut",
                "export.teacher.groups.pending",
            ),
            empty_key="export.teacher.groups.empty",
        ),
    ]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title=t("export.teacher.title"),
        author=meta["academy"] or "Vinta School OS",
    )
    doc.build(story)
    return buffer.getvalue()


def export_teacher_payout(
    details: dict, fmt: str = "csv", language: str = None,
    academy_id: str = None,
) -> tuple:
    """One teacher's statement, ready to hand to a response.

    Returns ``(payload, mimetype, filename)`` so the route stays a route: it
    reads the request, calls this, and writes the bytes out. Raises ValueError
    for a format it does not know, which the caller turns into a 400.

    ``details`` is ``payout_schedule_service.get_teacher_payout_details``'s
    payload, requested with ``include_lines=True`` — the same numbers the card
    on screen shows, so the file and the screen can never disagree about what an
    academy owes.

    The filename is ASCII by construction (see `_ascii_slug`); the teacher's own
    name, in whatever script it is written in, is inside the file rather than in
    the name of the file.
    """
    fmt = (fmt or "csv").strip().lower()
    if fmt not in ("csv", "pdf"):
        raise ValueError("format must be csv or pdf")

    meta = _export_meta(academy_id, {
        "gross_revenue_da": details.get("gross_revenue_da") or 0,
        "teacher_cut_da": details.get("teacher_cut_da") or 0,
        "pending_da": details.get("pending_da") or 0,
        "paid_da": details.get("paid_da") or 0,
    })

    stem = "teacher-statement-" + _ascii_slug(details.get("teacher_name"))
    if fmt == "pdf":
        return (
            teacher_payout_pdf(details, meta, language),
            "application/pdf",
            stem + ".pdf",
        )
    return (
        teacher_payout_csv(details, meta),
        "text/csv",
        stem + ".csv",
    )


def export_student_roster(academy_id: str) -> str:
    """
    Generate CSV for student roster.
    Columns: Name, Phone, Parent, Classes, Status, Plan
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Phone", "Parent Phone", "Classes", "Status", "Plan"])

    students = Student.query.filter_by(academy_id=academy_id, is_active=True).all()

    for student in students:
        # Get enrollments
        enrollments = Enrollment.query.filter_by(
            student_id=student.id, status="active"
        ).all()
        classes = ", ".join([e.class_.name for e in enrollments if e.class_])

        # Get latest billing
        latest_billing = (
            StudentBilling.query.filter_by(student_id=student.id)
            .order_by(desc(StudentBilling.created_at))
            .first()
        )
        status = latest_billing.status if latest_billing else "paid"
        plan = latest_billing.payment_plan.name if latest_billing and latest_billing.payment_plan else "N/A"

        writer.writerow([
            f"{student.first_name} {student.last_name}",
            student.phone or "",
            student.parent_phone or "",
            classes,
            status,
            plan,
        ])

    return output.getvalue()


def export_billing_history(academy_id: str) -> str:
    """
    Generate CSV for billing history.
    Columns: Student, Status, Amount, Paid, Date, Days Overdue
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student", "Status", "Amount (DA)", "Paid (DA)", "Date", "Days Overdue"])

    from app.models.student import Student as StudentModel
    billings = (
        StudentBilling.query.join(StudentModel)
        .filter(StudentModel.academy_id == academy_id)
        .order_by(desc(StudentBilling.created_at))
        .all()
    )

    today = date.today()
    for billing in billings:
        student = billing.student
        student_name = f"{student.first_name} {student.last_name}" if student else "Unknown"
        days_overdue = max(0, (today - billing.due_date).days) if billing.status == "overdue" else 0

        writer.writerow([
            student_name,
            billing.status,
            billing.amount_da,
            billing.paid_amount or 0,
            billing.cycle_start.isoformat(),
            days_overdue,
        ])

    return output.getvalue()


def export_teacher_hours(academy_id: str) -> str:
    """
    Generate CSV for teacher hours.
    Columns: Teacher, Session, Date, Hours, Subject
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Teacher", "Session", "Date", "Hours", "Subject"])

    logs = (
        TeacherHoursLog.query.join(Teacher)
        .filter(Teacher.academy_id == academy_id)
        .all()
    )

    for log in logs:
        teacher = log.teacher
        session = log.session
        teacher_name = f"{teacher.first_name} {teacher.last_name}" if teacher else "Unknown"
        session_info = f"{session.class_.name}" if session and session.class_ else "N/A"
        session_date = session.date.isoformat() if session else ""
        subject = session.subject if session else "N/A"

        writer.writerow([
            teacher_name,
            session_info,
            session_date,
            float(log.hours),
            subject,
        ])

    return output.getvalue()


def export_chart_data(academy_id: str, chart_type: str = "income") -> str:
    """
    Generate CSV for chart data based on chart type.
    Supports: income, enrollments, teacher_hours, overdue, income_by_subject
    """
    output = io.StringIO()
    writer = csv.writer(output)

    if chart_type == "income":
        writer.writerow(["Month", "Income (DA)"])
        # Implementation from billing_service.get_revenue_chart
        from app.services.billing_service import get_revenue_chart
        data = get_revenue_chart(academy_id)
        for row in data:
            writer.writerow([row["month"], row["income"]])

    elif chart_type == "teacher_hours":
        writer.writerow(["Teacher", "Total Hours"])
        from sqlalchemy import func
        results = (
            db.session.query(
                Teacher.first_name,
                Teacher.last_name,
                func.sum(TeacherHoursLog.hours).label("total_hours"),
            )
            .join(TeacherHoursLog, TeacherHoursLog.teacher_id == Teacher.id)
            .filter(Teacher.academy_id == academy_id)
            .group_by(Teacher.id)
            .all()
        )
        for r in results:
            writer.writerow([f"{r.first_name} {r.last_name}", float(r.total_hours)])

    else:
        writer.writerow(["No data available for this chart type"])

    return output.getvalue()
