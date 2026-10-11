"""Writes one billing-records PDF per language, for eyeballing the layout."""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.services.export_service import billing_records_pdf  # noqa: E402

META = {
    "academy": "أكاديمية الفتح",
    "generated": "2026-10-09 15:20",
    "totals": {"money_in_da": 123456, "money_out_da": 45000, "net_da": 78456},
}

RECORDS = [
    {
        "date": "2026-10-01", "kind": "STUDENT_PAYMENT", "direction": "IN",
        "profile_name": "أمين بلقاسم", "label": "اشتراك أكتوبر",
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

for lang in ("en", "fr", "ar"):
    path = f"scratch_preview_{lang}.pdf"
    with open(path, "wb") as handle:
        handle.write(billing_records_pdf(RECORDS, META, lang))
    print("wrote", path)

with open("scratch_preview_ar_empty.pdf", "wb") as handle:
    handle.write(billing_records_pdf([], META, "ar"))
print("wrote scratch_preview_ar_empty.pdf")
