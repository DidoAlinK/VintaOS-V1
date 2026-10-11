"""
Backend string catalogue.

One entry per language, one entry per key, English complete by definition —
it is the language the code was written in, so a key that only exists in
``en`` is a key somebody forgot rather than a key that means nothing.

Wording is taken from the interface's own dictionaries rather than invented
here, so the file a user exports uses the same words as the screen they
exported it from. The three phrases worth checking against
``src/i18n/locales/*/billing.json`` are ``title``, ``totals.*`` and
``kind.*``.

Two rules carried over from ``src/i18n/CONVENTIONS.md``:

  * ``DA`` is a currency code and is never translated. The amounts beside it
    are formatted by ``app/utils/formatters.py``, which appends ``DA`` and is
    not language-aware, so translating the code in the header alone would put
    two different currency names in one column.
  * Values that came out of the database — a status, a payment method, a
    person's name — are not translated. ``PAID`` and ``CASH`` are enum values
    the rest of the system matches on, and a PDF is not the place to start
    rewriting them.
"""

from __future__ import annotations

from typing import Dict

CATALOGUE: Dict[str, Dict[str, str]] = {
    # ── English — the source of truth ──────────────────────────────────
    "en": {
        "export.billing.title": "Billing Records",
        "export.billing.meta": "{academy}   ·   generated {when}",
        "export.billing.empty": "No records matched these filters.",

        "export.billing.totals.in": "Money in",
        "export.billing.totals.out": "Money out",
        "export.billing.totals.net": "Net",

        "export.billing.col.date": "Date",
        "export.billing.col.type": "Type",
        "export.billing.col.direction": "Direction",
        "export.billing.col.profile": "Profile",
        "export.billing.col.label": "Label",
        "export.billing.col.amount": "Amount (DA)",
        "export.billing.col.status": "Status",
        "export.billing.col.method": "Method",
        "export.billing.col.notes": "Notes",

        "export.billing.direction.in": "In",
        "export.billing.direction.out": "Out",

        "export.billing.kind.STUDENT_PAYMENT": "Student payment",
        "export.billing.kind.TEACHER_PAYOUT": "Teacher payout",
        "export.billing.kind.EXPENSE": "Expense",

        # ── One teacher's statement ────────────────────────────────────
        "export.teacher.title": "Teacher Statement",
        "export.teacher.meta": "{teacher}   ·   generated {when}",
        "export.teacher.period.label": "Period",
        "export.teacher.period.line": "Period: {span}",
        "export.teacher.period.spans.range": "{start} to {end}",
        "export.teacher.period.spans.from": "from {start}",
        "export.teacher.period.spans.until": "up to {end}",
        "export.teacher.period.spans.all": "all time",
        "export.teacher.schedule.line":
            "Payroll: {cadence}   ·   next {next}   ·   last {last}",

        "export.teacher.cadence.none": "settled by hand",
        "export.teacher.cadence.weekly": "every {day}",
        "export.teacher.cadence.monthly": "day {day} of each month",

        "export.teacher.weekday.monday": "Monday",
        "export.teacher.weekday.tuesday": "Tuesday",
        "export.teacher.weekday.wednesday": "Wednesday",
        "export.teacher.weekday.thursday": "Thursday",
        "export.teacher.weekday.friday": "Friday",
        "export.teacher.weekday.saturday": "Saturday",
        "export.teacher.weekday.sunday": "Sunday",

        "export.teacher.summary.gross": "Revenue generated",
        "export.teacher.summary.cut": "Teacher's share",
        "export.teacher.summary.pending": "Still owed",
        "export.teacher.summary.paid": "Already settled",
        "export.teacher.summary.average": "Average per session",
        "export.teacher.summary.sessions": "Sessions taught",
        "export.teacher.summary.manual": "Manual entries",
        "export.teacher.summary.hours": "Hours taught",
        "export.teacher.summary.students": "Students",
        "export.teacher.summary.groups": "Groups",

        "export.teacher.lines.title": "Payouts",
        "export.teacher.lines.empty": "No payouts in this period.",
        "export.teacher.col.date": "Date",
        "export.teacher.col.group": "Group",
        "export.teacher.col.source": "Source",
        "export.teacher.col.gross": "Gross (DA)",
        "export.teacher.col.cut": "Teacher cut (DA)",
        "export.teacher.col.status": "Status",
        "export.teacher.col.hours": "Hours",
        "export.teacher.col.notes": "Notes",

        "export.teacher.source.SESSION": "Session",
        "export.teacher.source.MANUAL": "Manual",

        "export.teacher.groups.title": "By group",
        "export.teacher.groups.name": "Group",
        "export.teacher.groups.sessions": "Sessions",
        "export.teacher.groups.gross": "Gross (DA)",
        "export.teacher.groups.cut": "Teacher cut (DA)",
        "export.teacher.groups.pending": "Still owed (DA)",
        "export.teacher.groups.empty": "No groups in this period.",

        # ── The note that travels inside the full-school archive ───────
        "export.school.readme.title": "Vinta School OS — Full Export",
        "export.school.readme.academy": "Academy: {academy}",
        "export.school.readme.generated": "Generated: {when}",
        "export.school.readme.intro": "This archive holds everything the academy owns:",
        "export.school.readme.csv": "  csv/       one file per table ({tables} files, {rows} rows)",
        "export.school.readme.json": "  json/      the same rows as JSON",
        "export.school.readme.database": "  database/  a copy of the database itself",
        "export.school.readme.nodb":
            "  database/  not included — this installation does not use a file database",
        "export.school.readme.note_logs":
            "The activity log is not in the csv/ and json/ folders. It is inside the database copy.",
        "export.school.readme.note_secrets":
            "No passwords or PINs are included — the password and PIN columns are left out.",
        "export.school.readme.note_import":
            "To bring this back: Settings → Export → Import, and drop any of these files.",
    },

    # ── French ─────────────────────────────────────────────────────────
    "fr": {
        "export.billing.title": "Écritures de paiement",
        "export.billing.meta": "{academy}   ·   généré le {when}",
        "export.billing.empty": "Aucune écriture ne correspond à ces filtres.",

        "export.billing.totals.in": "Entrées",
        "export.billing.totals.out": "Sorties",
        "export.billing.totals.net": "Net",

        "export.billing.col.date": "Date",
        "export.billing.col.type": "Type",
        "export.billing.col.direction": "Sens",
        "export.billing.col.profile": "Profil",
        "export.billing.col.label": "Libellé",
        "export.billing.col.amount": "Montant (DA)",
        "export.billing.col.status": "Statut",
        "export.billing.col.method": "Moyen",
        "export.billing.col.notes": "Remarques",

        "export.billing.direction.in": "Entrée",
        "export.billing.direction.out": "Sortie",

        "export.billing.kind.STUDENT_PAYMENT": "Paiement d'élève",
        "export.billing.kind.TEACHER_PAYOUT": "Versement enseignant",
        "export.billing.kind.EXPENSE": "Dépense",

        # ── Relevé d'un enseignant ─────────────────────────────────────
        "export.teacher.title": "Relevé d'enseignant",
        "export.teacher.meta": "{teacher}   ·   généré le {when}",
        "export.teacher.period.label": "Période",
        "export.teacher.period.line": "Période : {span}",
        "export.teacher.period.spans.range": "du {start} au {end}",
        "export.teacher.period.spans.from": "à partir du {start}",
        "export.teacher.period.spans.until": "jusqu'au {end}",
        "export.teacher.period.spans.all": "tout l'historique",
        "export.teacher.schedule.line":
            "Paie : {cadence}   ·   prochaine {next}   ·   dernière {last}",

        "export.teacher.cadence.none": "réglée à la main",
        "export.teacher.cadence.weekly": "chaque {day}",
        "export.teacher.cadence.monthly": "le {day} de chaque mois",

        "export.teacher.weekday.monday": "lundi",
        "export.teacher.weekday.tuesday": "mardi",
        "export.teacher.weekday.wednesday": "mercredi",
        "export.teacher.weekday.thursday": "jeudi",
        "export.teacher.weekday.friday": "vendredi",
        "export.teacher.weekday.saturday": "samedi",
        "export.teacher.weekday.sunday": "dimanche",

        "export.teacher.summary.gross": "Revenus générés",
        "export.teacher.summary.cut": "Part de l'enseignant",
        "export.teacher.summary.pending": "Reste à verser",
        "export.teacher.summary.paid": "Déjà réglé",
        "export.teacher.summary.average": "Moyenne par séance",
        "export.teacher.summary.sessions": "Séances assurées",
        "export.teacher.summary.manual": "Écritures manuelles",
        "export.teacher.summary.hours": "Heures assurées",
        "export.teacher.summary.students": "Élèves",
        "export.teacher.summary.groups": "Groupes",

        "export.teacher.lines.title": "Versements",
        "export.teacher.lines.empty": "Aucun versement sur cette période.",
        "export.teacher.col.date": "Date",
        "export.teacher.col.group": "Groupe",
        "export.teacher.col.source": "Origine",
        "export.teacher.col.gross": "Brut (DA)",
        "export.teacher.col.cut": "Part enseignant (DA)",
        "export.teacher.col.status": "Statut",
        "export.teacher.col.hours": "Heures",
        "export.teacher.col.notes": "Remarques",

        "export.teacher.source.SESSION": "Séance",
        "export.teacher.source.MANUAL": "Manuel",

        "export.teacher.groups.title": "Par groupe",
        "export.teacher.groups.name": "Groupe",
        "export.teacher.groups.sessions": "Séances",
        "export.teacher.groups.gross": "Brut (DA)",
        "export.teacher.groups.cut": "Part enseignant (DA)",
        "export.teacher.groups.pending": "Reste à verser (DA)",
        "export.teacher.groups.empty": "Aucun groupe sur cette période.",

        # ── The note that travels inside the full-school archive ───────
        "export.school.readme.title": "Vinta School OS — Exportation complète",
        "export.school.readme.academy": "Académie : {academy}",
        "export.school.readme.generated": "Généré le : {when}",
        "export.school.readme.intro": "Cette archive contient tout ce que possède l'académie :",
        "export.school.readme.csv": "  csv/       un fichier par table ({tables} fichiers, {rows} lignes)",
        "export.school.readme.json": "  json/      les mêmes lignes en JSON",
        "export.school.readme.database": "  database/  une copie de la base de données elle-même",
        "export.school.readme.nodb":
            "  database/  non incluse — cette installation n'utilise pas de base de données fichier",
        "export.school.readme.note_logs":
            "Le journal d'activité n'est pas dans les dossiers csv/ et json/. Il se trouve dans la copie de la base.",
        "export.school.readme.note_secrets":
            "Aucun mot de passe ni code PIN n'est inclus — les colonnes correspondantes sont retirées.",
        "export.school.readme.note_import":
            "Pour le réimporter : Paramètres → Exportation → Importer, puis déposez l'un de ces fichiers.",
    },

    # ── Arabic ─────────────────────────────────────────────────────────
    "ar": {
        "export.billing.title": "سجلات المدفوعات",
        "export.billing.meta": "{academy}   ·   صدر في {when}",
        "export.billing.empty": "لا توجد سجلات مطابقة لعوامل التصفية هذه.",

        "export.billing.totals.in": "المقبوضات",
        "export.billing.totals.out": "المدفوعات",
        "export.billing.totals.net": "الصافي",

        "export.billing.col.date": "التاريخ",
        "export.billing.col.type": "النوع",
        "export.billing.col.direction": "الاتجاه",
        "export.billing.col.profile": "الحساب",
        "export.billing.col.label": "البيان",
        "export.billing.col.amount": "المبلغ (DA)",
        "export.billing.col.status": "الحالة",
        "export.billing.col.method": "الوسيلة",
        "export.billing.col.notes": "ملاحظات",

        "export.billing.direction.in": "وارد",
        "export.billing.direction.out": "صادر",

        "export.billing.kind.STUDENT_PAYMENT": "دفعة طالب",
        "export.billing.kind.TEACHER_PAYOUT": "مدفوعات أستاذ",
        "export.billing.kind.EXPENSE": "مصروف",

        # ── كشف حساب أستاذ ─────────────────────────────────────────────
        "export.teacher.title": "كشف حساب الأستاذ",
        "export.teacher.meta": "{teacher}   ·   صدر في {when}",
        "export.teacher.period.label": "الفترة",
        "export.teacher.period.line": "الفترة: {span}",
        "export.teacher.period.spans.range": "من {start} إلى {end}",
        "export.teacher.period.spans.from": "من {start}",
        "export.teacher.period.spans.until": "حتى {end}",
        "export.teacher.period.spans.all": "كل السجلات",
        "export.teacher.schedule.line":
            "الأجر: {cadence}   ·   التالي {next}   ·   الأخير {last}",

        "export.teacher.cadence.none": "يُسوَّى يدويًا",
        "export.teacher.cadence.weekly": "كل {day}",
        "export.teacher.cadence.monthly": "يوم {day} من كل شهر",

        "export.teacher.weekday.monday": "الاثنين",
        "export.teacher.weekday.tuesday": "الثلاثاء",
        "export.teacher.weekday.wednesday": "الأربعاء",
        "export.teacher.weekday.thursday": "الخميس",
        "export.teacher.weekday.friday": "الجمعة",
        "export.teacher.weekday.saturday": "السبت",
        "export.teacher.weekday.sunday": "الأحد",

        "export.teacher.summary.gross": "الإيرادات المحققة",
        "export.teacher.summary.cut": "نصيب الأستاذ",
        "export.teacher.summary.pending": "المتبقي",
        "export.teacher.summary.paid": "المسوَّى",
        "export.teacher.summary.average": "المتوسط لكل حصة",
        "export.teacher.summary.sessions": "الحصص المنجزة",
        "export.teacher.summary.manual": "قيود يدوية",
        "export.teacher.summary.hours": "الساعات المنجزة",
        "export.teacher.summary.students": "الطلاب",
        "export.teacher.summary.groups": "الأفواج",

        "export.teacher.lines.title": "المدفوعات",
        "export.teacher.lines.empty": "لا توجد مدفوعات في هذه الفترة.",
        "export.teacher.col.date": "التاريخ",
        "export.teacher.col.group": "الفوج",
        "export.teacher.col.source": "المصدر",
        "export.teacher.col.gross": "الإجمالي (DA)",
        "export.teacher.col.cut": "نصيب الأستاذ (DA)",
        "export.teacher.col.status": "الحالة",
        "export.teacher.col.hours": "الساعات",
        "export.teacher.col.notes": "ملاحظات",

        "export.teacher.source.SESSION": "حصة",
        "export.teacher.source.MANUAL": "يدوي",

        "export.teacher.groups.title": "حسب الفوج",
        "export.teacher.groups.name": "الفوج",
        "export.teacher.groups.sessions": "الحصص",
        "export.teacher.groups.gross": "الإجمالي (DA)",
        "export.teacher.groups.cut": "نصيب الأستاذ (DA)",
        "export.teacher.groups.pending": "المتبقي (DA)",
        "export.teacher.groups.empty": "لا توجد أفواج في هذه الفترة.",

        # ── The note that travels inside the full-school archive ───────
        "export.school.readme.title": "Vinta School OS — تصدير كامل",
        "export.school.readme.academy": "الأكاديمية: {academy}",
        "export.school.readme.generated": "أُنشئ في: {when}",
        "export.school.readme.intro": "يحتوي هذا الأرشيف على كل ما تملكه الأكاديمية:",
        "export.school.readme.csv": "  csv/       ملف لكل جدول ({tables} ملفًا، {rows} سطرًا)",
        "export.school.readme.json": "  json/      السطور نفسها بصيغة JSON",
        "export.school.readme.database": "  database/  نسخة من قاعدة البيانات نفسها",
        "export.school.readme.nodb":
            "  database/  غير مضمّنة — هذا التثبيت لا يستخدم قاعدة بيانات ملفية",
        "export.school.readme.note_logs":
            "سجل النشاط ليس في مجلدي csv/ و json/. إنه داخل نسخة قاعدة البيانات.",
        "export.school.readme.note_secrets":
            "لا تُضمَّن كلمات المرور ولا رموز PIN — يُستبعد العمودان المخصصان لهما.",
        "export.school.readme.note_import":
            "لإعادة الاستيراد: الإعدادات → التصدير → استيراد، ثم أفلِت أيًا من هذه الملفات.",
    },
}
