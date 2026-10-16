"""Make the header photo: a strip of McGill's campus cut from a photo by the app's author.

    python scripts/make_hero_photo.py PHOTO.jpg LEFT TOP RIGHT BOTTOM

The crop box is in the photo's own pixels; keep people out of it. The strip is resized to 1600 px wide, lifted a
little so it sits on the light theme, and written to static/hero_mcgill.webp. The original photo is not kept in the
repository.

The strip in use was cut from the author's photo of the Arts Building (1200 x 1600 px) with the box 0 245 1200 695.
"""
import sys
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "hero_mcgill.webp"
WIDTH = 1600


def main(photo, left, top, right, bottom):
    im = Image.open(photo).convert("RGB").crop((left, top, right, bottom))
    im = im.resize((WIDTH, round(WIDTH * im.height / im.width)), Image.LANCZOS)
    im = ImageEnhance.Brightness(im).enhance(1.12)
    im = ImageEnhance.Color(im).enhance(0.9)
    im.save(OUT, "WEBP", quality=80, method=6)
    print(f"wrote {OUT.relative_to(ROOT)} ({im.width} x {im.height}, {OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    main(sys.argv[1], *map(int, sys.argv[2:]))
