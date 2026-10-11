"""
Vinta School OS — backend translations.

Why the server translates anything at all
-----------------------------------------
Almost every word this application shows is translated in the browser, where
the dictionaries live and where changing the language takes effect without a
round trip to the server. This package exists for the one category that cannot
work that way: text the server writes **into a file**.

An exported PDF outlives the request that produced it. It has no preference
store to read from and no dictionary to look a word up in later, so its
language has to be decided while it is being built and baked into the bytes.
The browser states its language on every request it makes, in
``Accept-Language``, and that is where the decision is read from.

Scope
-----
Only strings the backend itself authors belong here — column headers, section
titles, the words for "money in" and "money out", the empty-state sentence.
Anything that came out of the database is data rather than prose and is
printed exactly as it was stored, in whatever language it was entered in.

Terminology is deliberately the same as the frontend's, word for word (see
``src/i18n/locales/*/billing.json`` under ``records``). Somebody who reads
"Écritures de paiement" on screen should not open the export and find
"Payment Records" at the top of it.

Lookup falls back **per key**, not per language: a catalogue that is missing
one sentence still produces a whole document rather than a page of raw key
paths.
"""

from __future__ import annotations

from .catalogue import CATALOGUE

__all__ = [
    "CATALOGUE",
    "DEFAULT_LANGUAGE",
    "RTL_LANGUAGES",
    "SUPPORTED_LANGUAGES",
    "Translator",
    "resolve_language",
    "translator",
]

#: The languages the application ships. Mirrors `src/i18n/index.ts`.
SUPPORTED_LANGUAGES = ("en", "fr", "ar")

#: English is the source of truth for every key, exactly as it is in the
#: frontend, so a key that has not been translated yet degrades to a real
#: sentence rather than a key path.
DEFAULT_LANGUAGE = "en"

#: Languages laid out right to left. Mirrors `DIRECTION` in `src/i18n/index.ts`
#: — kept as a second copy of that fact on purpose, because the two halves
#: cannot import each other and a wrong answer here mirrors a document that the
#: interface would have drawn the other way round.
RTL_LANGUAGES = frozenset({"ar"})


def _accepted_tags(header: str) -> list:
    """Language tags from an ``Accept-Language`` header, most wanted first.

    A browser sends something like ``ar-DZ,ar;q=0.9,fr;q=0.8``. Preference
    order is what the header is *for*, so it is honoured rather than reduced to
    "whichever tag appears first": a user who has French ahead of English must
    get French, even if English sorts earlier alphabetically.

    Tags are reduced to their primary subtag, so the regional ``ar-DZ`` an
    Algerian browser actually sends resolves to the ``ar`` catalogue. A quality
    of zero means "explicitly not wanted" and is dropped.
    """
    ranked = []
    for index, part in enumerate(header.split(",")):
        part = part.strip()
        if not part:
            continue

        tag, _, params = part.partition(";")
        tag = tag.strip().lower()
        if not tag:
            continue

        quality = 1.0
        for param in params.split(";"):
            name, _, value = param.partition("=")
            if name.strip().lower() == "q":
                try:
                    quality = float(value.strip())
                except ValueError:
                    quality = 1.0

        if quality <= 0:
            continue

        # `index` breaks ties by the order written, which is the header's own
        # statement of preference when no q-values were given at all.
        ranked.append((-quality, index, tag.split("-")[0]))

    ranked.sort()
    return [primary for _, _, primary in ranked]


def resolve_language(raw: str | None) -> str:
    """The language to write in, given a request's ``Accept-Language``.

    Accepts the full header, a bare tag (``"fr"``, ``"ar-DZ"``) or nothing at
    all, because callers differ: the export route passes the header through,
    while a script or a test naturally has a single code on hand. Anything
    unrecognised resolves to English rather than raising — a missing
    translation is a cosmetic problem, and failing an export over one would
    cost the user their data.
    """
    if not raw:
        return DEFAULT_LANGUAGE
    for tag in _accepted_tags(raw):
        if tag in SUPPORTED_LANGUAGES:
            return tag
    return DEFAULT_LANGUAGE


class Translator:
    """Looks up backend strings for one language.

    Callable rather than a ``get`` method so it reads like the frontend's
    ``t(...)`` at every call site.

    Interpolation uses ``str.format``-style ``{name}`` placeholders. A value
    that is missing from the call is left as the literal placeholder rather
    than raising: a half-filled sentence in a PDF beats a 500 with no PDF in
    it at all.
    """

    __slots__ = ("language", "rtl", "_table", "_fallback")

    def __init__(self, language: str | None = None):
        self.language = resolve_language(language)
        self.rtl = self.language in RTL_LANGUAGES
        self._table = CATALOGUE.get(self.language, {})
        self._fallback = CATALOGUE[DEFAULT_LANGUAGE]

    def __call__(self, key: str, **values) -> str:
        text = self._table.get(key) or self._fallback.get(key) or key
        if not values:
            return text
        try:
            return text.format(**values)
        except (KeyError, IndexError, ValueError):
            return text

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Translator {self.language!r}>"


def translator(language: str | None = None) -> Translator:
    """A translator for `language`, which may be a raw ``Accept-Language``."""
    return Translator(language)
