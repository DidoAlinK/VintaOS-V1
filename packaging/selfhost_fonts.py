"""
Bundle the frontend's webfonts into the app so it renders identically offline.

The app's index.html currently pulls Inter and Space Grotesk from Google Fonts.
On a machine with no internet that request fails and the browser silently
substitutes system fonts — which makes a packaging decision look like a styling
bug during review. This downloads the same font files once, at build time, and
rewrites the *built* index.html to use them from the bundle.

Deliberately operates on the build output rather than the source tree: the
Vercel deployment keeps loading from the CDN, so nothing about production
changes. Only the review build is made self-contained.

Coverage note: only the `latin` and `latin-ext` subsets are fetched. The fonts
themselves have no Arabic glyphs, so Arabic text already falls back to system
fonts on the live site too — bundling cannot change that, and pulling the other
subsets would add megabytes for no visible difference.

Run:
    python packaging/selfhost_fonts.py --dist path/to/dist
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# A modern browser UA is required: Google serves woff2 only to clients that
# advertise support, and falls back to much larger ttf/woff otherwise.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

FAMILIES = [
    ("Inter", "wght@400;500;600"),
    ("Space Grotesk", "wght@500;600;700"),
]

KEEP_SUBSETS = {"latin", "latin-ext"}

CSS_URL = (
    "https://fonts.googleapis.com/css2?"
    + "&".join(f"family={name.replace(' ', '+')}:{spec}" for name, spec in FAMILIES)
    + "&display=swap"
)

BLOCK_RE = re.compile(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{[^}]*\})", re.S)
FAMILY_RE = re.compile(r"font-family:\s*'([^']+)'")
WEIGHT_RE = re.compile(r"font-weight:\s*(\d+)")
STYLE_RE = re.compile(r"font-style:\s*(\w+)")
URL_RE = re.compile(r"url\((https://[^)]+?\.woff2)\)")
RANGE_RE = re.compile(r"unicode-range:\s*([^;]+);")

# The <link> tags and the CSP meta that reference Google Fonts.
GFONT_LINK_RE = re.compile(
    r"\s*<link[^>]*fonts\.(?:googleapis|gstatic)\.com[^>]*>", re.I
)
PRECONNECT_RE = re.compile(
    r"\s*<link[^>]*rel=[\"']preconnect[\"'][^>]*fonts\.[^>]*>", re.I
)
CSP_META_RE = re.compile(
    r"<meta\s+http-equiv=[\"']Content-Security-Policy[\"'][^>]*>", re.I
)

SELF_CONTAINED_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'"
)


def fetch(url: str, *, binary: bool) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build_fonts(dist: Path) -> int:
    print("  Fetching font CSS from Google Fonts...")
    try:
        css = fetch(CSS_URL, binary=False).decode("utf-8")
    except (urllib.error.URLError, OSError) as exc:
        print(f"  ! Could not reach Google Fonts: {exc}")
        print("  ! Leaving the CDN links in place (offline it will use system fonts).")
        return 0

    fonts_dir = dist / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    rules: list[str] = []
    downloaded = 0
    total_bytes = 0

    for subset, block in BLOCK_RE.findall(css):
        if subset not in KEEP_SUBSETS:
            continue

        url_match = URL_RE.search(block)
        family_match = FAMILY_RE.search(block)
        weight_match = WEIGHT_RE.search(block)
        if not (url_match and family_match and weight_match):
            continue

        family = family_match.group(1)
        weight = weight_match.group(1)
        style = STYLE_RE.search(block)
        style = style.group(1) if style else "normal"
        url = url_match.group(1)

        filename = f"{slug(family)}-{weight}-{subset}.woff2"
        target = fonts_dir / filename

        if not target.is_file():
            try:
                payload = fetch(url, binary=True)
            except (urllib.error.URLError, OSError) as exc:
                print(f"  ! Failed to download {filename}: {exc}")
                continue
            target.write_bytes(payload)
            downloaded += 1
            total_bytes += len(payload)

        unicode_range = RANGE_RE.search(block)
        rules.append(
            "@font-face {\n"
            f"  font-family: '{family}';\n"
            f"  font-style: {style};\n"
            f"  font-weight: {weight};\n"
            "  font-display: swap;\n"
            f"  src: url('/fonts/{filename}') format('woff2');\n"
            + (f"  unicode-range: {unicode_range.group(1).strip()};\n" if unicode_range else "")
            + "}"
        )

    if not rules:
        print("  ! No woff2 sources found in the response; leaving CDN links in place.")
        return 0

    (fonts_dir / "fonts.css").write_text("\n\n".join(rules) + "\n", encoding="utf-8")
    print(f"  Downloaded {downloaded} font files ({total_bytes / 1024:.0f} KB)")

    return patch_html(dist)


def patch_html(dist: Path) -> int:
    """Point the built index.html at the bundled fonts and tighten the CSP."""
    index = dist / "index.html"
    html = index.read_text(encoding="utf-8")
    original = html

    # Already self-contained (a previous run, or --skip-frontend reusing a
    # patched dist/). Report success rather than "nothing to do", so a re-run
    # does not look like a failure to the build script.
    if "/fonts/fonts.css" in html and "fonts.g" not in html:
        print("  index.html is already self-contained.")
        return 1

    html = GFONT_LINK_RE.sub("", html)
    html = PRECONNECT_RE.sub("", html)

    if "</head>" not in html:
        print("  ! Built index.html has no </head>; cannot inject the font stylesheet.")
        return 0

    # Guard against a second pass (e.g. --skip-frontend reusing a dist/ that was
    # already patched): without this the stylesheet link is injected again on
    # every run, and the list grows silently.
    if "/fonts/fonts.css" not in html:
        html = html.replace(
            "</head>",
            '  <link rel="stylesheet" href="/fonts/fonts.css" />\n  </head>',
            1,
        )
    else:
        print("  index.html already references the bundled fonts.")

    if CSP_META_RE.search(html):
        html = CSP_META_RE.sub(
            f'<meta http-equiv="Content-Security-Policy" content="{SELF_CONTAINED_CSP}" />',
            html,
        )
    else:
        print("  ! No CSP meta tag found; skipped the policy rewrite.")

    if html == original:
        print("  ! index.html was unchanged — check the rewrite patterns.")
        return 0

    index.write_text(html, encoding="utf-8")

    # Verify rather than assume: a silent no-op here would ship a build that
    # still phones home to Google and renders wrong offline.
    check = index.read_text(encoding="utf-8")
    if "fonts.g" in check:
        print("  ! index.html still references Google Fonts.")
        return 0
    print("  Rewrote index.html to use the bundled fonts.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", required=True, type=Path,
                        help="path to the built frontend (contains index.html)")
    args = parser.parse_args()

    if not (args.dist / "index.html").is_file():
        print(f"  ! {args.dist}/index.html not found. Build the frontend first.")
        return 1

    ok = build_fonts(args.dist)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
