"""Checks that the billing-records PDF follows the language the app is read in.

Standalone: no server, no database. `billing_records_pdf` takes its heading
block as an argument and never touches the session, so the whole string and
layout path can be exercised from a dict.

Run from the backend root:  python scratch_pdf_language_check.py
"""
import re
import sys
import zlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.i18n import CATALOGUE, resolve_language, translator             # noqa: E402
from app.services.export_service import (                            # noqa: E402
    billing_records_pdf, shape_arabic, _ensure_font,
)

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(("  PASS  " if ok else "  FAIL  ") + label)


def note(label, value):
    print(f"  ..    {label}: {value}")


# ── Which language does a request resolve to? ──────────────────────────────
print("\nresolve_language")
check("bare code", resolve_language("fr"), "fr")
check("regional tag", resolve_language("ar-DZ"), "ar")
check("mixed case", resolve_language("AR-dz"), "ar")
check("full header", resolve_language("ar-DZ,ar;q=0.9,fr;q=0.8"), "ar")
check("preference beats order", resolve_language("en;q=0.5,ar"), "ar")
check("q=0 is not wanted", resolve_language("ar;q=0,fr"), "fr")
check("unsupported -> en", resolve_language("de-DE,de;q=0.9"), "en")
check("wildcard -> en", resolve_language("*"), "en")
check("empty -> en", resolve_language(""), "en")
check("None -> en", resolve_language(None), "en")

# ── The catalogue ──────────────────────────────────────────────────────────
print("\ntranslator")
en, fr, ar = translator("en"), translator("fr"), translator("ar")
check("en title", en("export.billing.title"), "Billing Records")
check("fr title", fr("export.billing.title"), "Écritures de paiement")
check("ar title", ar("export.billing.title"), "سجلات المدفوعات")
check("en is not rtl", en.rtl, False)
check("fr is not rtl", fr.rtl, False)
check("ar is rtl", ar.rtl, True)
check(
    "interpolation",
    fr("export.billing.meta", academy="X", when="Y"),
    "X   ·   généré le Y",
)
check("unknown key returns the key", en("nope.nope"), "nope.nope")
check("no catalogue out of range", translator("de")("export.billing.title"),
      "Billing Records")

# Both non-English catalogues must cover every English key, or the fallback
# quietly turns part of a French PDF back into English.
english_keys = set(CATALOGUE["en"])
for lang in ("fr", "ar"):
    check(f"{lang} covers every english key",
          sorted(english_keys - set(CATALOGUE[lang])), [])

# ── Shaping ────────────────────────────────────────────────────────────────
print("\nshape_arabic")
raw = "سجلات"
shaped = shape_arabic(raw)
check("arabic is reshaped", shaped != raw, True)
check(
    "output is presentation forms",
    any("ﹰ" <= ch <= "﻿" for ch in shaped),
    True,
)
check("latin untouched", shape_arabic("Payment Records"), "Payment Records")
check("empty untouched", shape_arabic(""), "")

# ── Building the documents ─────────────────────────────────────────────────
print("\nbilling_records_pdf")

META = {
    "academy": "أكاديمية الفتح",
    "generated": "2026-10-09 15:20",
    "totals": {"money_in_da": 123456, "money_out_da": 45000, "net_da": 78456},
}

RECORDS = [
    {
        "date": "2026-10-01", "kind": "STUDENT_PAYMENT", "direction": "IN",
        "profile_name": "أمين بلقاسم",
        "label": "اشتراك أكتوبر",
        "amount_da": 12000, "status": "PAID", "method": "CASH", "notes": "",
    },
    {
        "date": "2026-10-02", "kind": "TEACHER_PAYOUT", "direction": "OUT",
        "profile_name": "Nadia Meziane", "label": "Séance du 2",
        "amount_da": 3000, "status": "PAID", "method": "CASH", "notes": "ok",
    },
    {
        "date": "2026-10-03", "kind": "EXPENSE", "direction": "OUT",
        "profile_name": "Fournitures", "label": "Ramettes",
        "amount_da": 1500, "status": "PAID", "method": "CASH", "notes": "",
    },
]


def text_runs(pdf: bytes) -> set:
    """Every 4-hex-digit code in the document's ToUnicode maps.

    reportlab subsets the TTF and writes glyph ids into the page, not
    characters, so the page bytes say nothing about the words that were drawn.
    The ToUnicode CMap is the translation table it writes alongside, and that
    is where the actual codepoints can be read back.
    """
    found = set()
    for match in re.finditer(rb"stream\r?\n", pdf):
        end = pdf.find(b"endstream", match.end())
        if end == -1:
            continue
        try:
            chunk = zlib.decompress(pdf[match.end():end])
        except zlib.error:
            continue
        for code in re.findall(rb"<([0-9A-Fa-f]{4})>", chunk):
            found.add(int(code, 16))
    return found


font = _ensure_font()
note("font", font)
check("a font was registered", font != "", True)

for lang in ("en", "fr", "ar"):
    data = billing_records_pdf(RECORDS, META, lang)
    check(f"{lang}: is a PDF", data[:5], b"%PDF-")
    note(f"{lang}: size", f"{len(data)} bytes")

check("empty range still builds",
      billing_records_pdf([], META, "ar")[:5], b"%PDF-")
check("unknown language falls back to English",
      billing_records_pdf(RECORDS, META, "sv")[:5], b"%PDF-")
check("language may be omitted",
      billing_records_pdf(RECORDS, META)[:5], b"%PDF-")
check("full header accepted",
      billing_records_pdf(RECORDS, META, "ar-DZ,ar;q=0.9")[:5], b"%PDF-")

# The proof that Arabic is drawn as Arabic: presentation forms (FE70–FEFF) can
# only be in the document if reshape() ran over the text that was drawn, and
# only the Arabic document should contain any.
codes_ar = text_runs(billing_records_pdf(RECORDS, META, "ar"))
codes_fr = text_runs(billing_records_pdf(RECORDS, META, "fr"))
note("ar presentation forms", sum(1 for c in codes_ar if 0xFE70 <= c <= 0xFEFF))
note("fr presentation forms", sum(1 for c in codes_fr if 0xFE70 <= c <= 0xFEFF))
check("arabic pdf contains shaped glyphs",
      any(0xFE70 <= c <= 0xFEFF for c in codes_ar), True)

# Nothing should be left unshaped. Every Arabic string in the document goes
# through `paragraph()`, so an isolated Arabic letter surviving into the output
# means some path skipped it — which is exactly the regression worth catching,
# and it is what a heading left untranslated and unshaped would look like.
check("no unshaped arabic left in the arabic pdf",
      sorted(c for c in codes_ar if 0x0600 <= c <= 0x06FF), [])

# A French export from an Algerian academy still holds Arabic names; those have
# to be shaped too, or the one document that mixes scripts is the one that
# breaks.
check("french pdf shapes the arabic it contains",
      any(0xFE70 <= c <= 0xFEFF for c in codes_fr), True)

# ── Report ─────────────────────────────────────────────────────────────────
print()
if FAILED:
    print(f"{len(FAILED)} FAILED")
    for line in FAILED:
        print("  - " + line)
    sys.exit(1)
print("all checks passed")
