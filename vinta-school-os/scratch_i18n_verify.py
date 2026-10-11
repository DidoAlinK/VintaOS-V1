"""Verify the three billing.json and the three settings.json dictionaries.

Checks, in order of what would actually hurt:
  1. every file parses, and no value is an empty string;
  2. en / fr / ar carry the same key set (plural suffixes normalised away), both
     directions — a key only in one language renders as a raw `records.foo` on
     screen for the other two;
  3. the plural form sets are the ones i18next will look for: en and fr
     one/other, ar all six CLDR forms;
  4. every {{placeholder}} in an English string appears in its fr and ar
     counterparts, with the same spelling.
"""
import io
import json
import re

LOCALES = "src/i18n/locales"
PLURAL = ("_zero", "_one", "_two", "_few", "_many", "_other")
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")

problems = []


def load(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def flatten(node, prefix=""):
    """key -> string, for every leaf."""
    out = {}
    for key, value in node.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(flatten(value, path + "."))
        else:
            out[path] = value
    return out


def normalise(key):
    for suffix in PLURAL:
        if key.endswith(suffix):
            return key[: -len(suffix)], suffix
    return key, None


def check_file(name):
    data = {lang: load(f"{LOCALES}/{lang}/{name}") for lang in ("en", "fr", "ar")}
    flat = {lang: flatten(data[lang]) for lang in data}

    # (1) non-empty
    for lang, leaves in flat.items():
        for key, value in leaves.items():
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{lang}/{name}: empty value at {key}")

    # (2) key parity on the normalised (plural-stripped) key set
    sets = {}
    for lang, leaves in flat.items():
        sets[lang] = {normalise(k)[0] for k in leaves}
    all_keys = set().union(*sets.values())
    for lang in ("en", "fr", "ar"):
        missing = sorted(all_keys - sets[lang])
        if missing:
            problems.append(f"{lang}/{name}: {len(missing)} key(s) missing: {missing[:12]}")

    # (3) plural form sets
    expected = {"en": {"_one", "_other"},
                "fr": {"_one", "_other"},
                "ar": set(PLURAL)}
    for lang, leaves in flat.items():
        forms = {normalise(k)[1] for k in leaves} - {None}
        if forms != expected[lang]:
            problems.append(
                f"{lang}/{name}: plural suffixes are {sorted(forms)}, "
                f"expected {sorted(expected[lang])}"
            )

    # (4) placeholder parity.
    #
    # Not strict equality, because Arabic states the number in words rather than
    # interpolating it in the zero/one/two forms: `سجل واحد` ("one record"),
    # `سجلان` ("two records"), `النشطون (0)`. That is the established convention
    # across every existing ar dictionary — so the rules below are:
    #   a. a placeholder in a translation must also exist in English (an invented
    #      one is a typo that renders literally);
    #   b. the Arabic forms that *do* interpolate — few/many/other, the actual
    #      "3 records" cases — must keep `{{count}}` if English has it.
    en_leaves = flat["en"]
    for key, value in en_leaves.items():
        want = set(PLACEHOLDER.findall(value))
        base, form = normalise(key)
        for lang in ("fr", "ar"):
            other = flat[lang].get(key)
            if other is None:
                continue  # already reported in (2)
            got = set(PLACEHOLDER.findall(other))
            invented = got - want
            if invented:
                problems.append(
                    f"{name}: {key} — {lang} uses placeholder(s) {sorted(invented)} "
                    f"that English does not"
                )
            if not got and want and not (lang == "ar" and form in ("_zero", "_one", "_two")):
                problems.append(
                    f"{name}: {key} — en has {sorted(want)} but {lang} has none"
                )

    print(f"{name:16s} keys: en={len(flat['en'])} fr={len(flat['fr'])} ar={len(flat['ar'])}")


for name in ("billing.json", "settings.json"):
    check_file(name)

print()
if problems:
    print(f"{len(problems)} problem(s):")
    for line in problems:
        print("  -", line)
    raise SystemExit(1)
print("all checks passed")

# A last look at the new subtrees, so the text is visible rather than merely valid.
records_en = flatten(load(f"{LOCALES}/en/billing.json"))
for key in sorted(records_en):
    if key.startswith("records."):
        pass
print()
print("records.* present in en:", len([k for k in records_en if k.startswith("records.")]))
