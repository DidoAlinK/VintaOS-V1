"""
Generate the Vinta OS application icon (a multi-resolution .ico).

Reproduces the mark from ``vinta-school-os/public/favicon.svg``: a rounded
square filled with the brand's gold -> emerald diagonal gradient, carrying a
white "V". The SVG is what the web app shows in a browser tab; Windows needs a
real .ico for the executable, the Start Menu entry and the taskbar, so it is
drawn here at every size Windows asks for rather than being upscaled from one
bitmap.

Run:
    python usb-kit/make_icon.py --out usb-kit/assets/vinta.ico
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

#: Matches the gradient stops in the brand favicon.
GOLD = (179, 135, 42)      # #b3872a
EMERALD = (15, 107, 77)    # #0f6b4d

#: Windows picks from these depending on where the icon is drawn: 16 in the
#: title bar and taskbar, 32 in the Alt-Tab list, 48 in Explorer's medium view,
#: 256 in the large-tile and Add/Remove Programs views.
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

#: Drawn large and downsampled, which is what gives the curved edges and the
#: letter their antialiasing.
MASTER = 1024

#: The squircle radius in the source SVG: 16 of 52.
CORNER_RATIO = 16 / 52

FONT_CANDIDATES = (
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
)


def gradient(size: int) -> Image.Image:
    """A top-left gold to bottom-right emerald diagonal gradient."""
    # Built small and scaled up: the ramp is smooth, so interpolating it costs
    # nothing visually and saves a million Python-level pixel writes.
    small = 256
    img = Image.new("RGB", (small, small))
    px = img.load()
    span = 2 * (small - 1)
    for y in range(small):
        for x in range(small):
            t = (x + y) / span
            px[x, y] = (
                round(GOLD[0] + (EMERALD[0] - GOLD[0]) * t),
                round(GOLD[1] + (EMERALD[1] - GOLD[1]) * t),
                round(GOLD[2] + (EMERALD[2] - GOLD[2]) * t),
            )
    return img.resize((size, size), Image.LANCZOS)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def build_master() -> Image.Image:
    """One large, antialiased copy of the mark."""
    base = gradient(MASTER)

    # Rounded-square mask -> the squircle silhouette.
    mask = Image.new("L", (MASTER, MASTER), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, MASTER - 1, MASTER - 1),
        radius=round(MASTER * CORNER_RATIO),
        fill=255,
    )

    tile = Image.new("RGBA", (MASTER, MASTER), (0, 0, 0, 0))
    tile.paste(base, (0, 0), mask)

    # The "V", optically centred: text bbox is measured so the glyph sits in the
    # middle of the tile rather than on its baseline.
    draw = ImageDraw.Draw(tile)
    font = load_font(round(MASTER * 0.46))
    text = "V"
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(
        ((MASTER - (right - left)) / 2 - left, (MASTER - (bottom - top)) / 2 - top),
        text,
        font=font,
        fill=(255, 255, 255, 255),
    )
    return tile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True,
                        help="path of the .ico to write")
    args = parser.parse_args()

    master = build_master()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Pillow writes every requested size into the one .ico container, which is
    # what makes Windows pick a crisp bitmap at each of its display scales.
    master.save(args.out, format="ICO", sizes=[(s, s) for s in ICON_SIZES])
    print(f"  Wrote {args.out} ({', '.join(str(s) for s in ICON_SIZES)} px)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
