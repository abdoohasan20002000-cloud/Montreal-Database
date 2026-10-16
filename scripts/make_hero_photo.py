"""Make the header photos: strips of McGill's campus cut from a photo by the app's author.

    python scripts/make_hero_photo.py PHOTO.jpg LEFT TOP RIGHT BOTTOM [NAME]

The crop box is in the photo's own pixels; keep people out of it. The strip is resized to 1600 px wide, lifted a
little so it sits on the light theme, and written to static/NAME (default hero_mcgill.webp). The original photo is not
kept in the repository.

Both photos in use were cut from the author's photo of the Arts Building (1200 x 1600 px), above the person in it:
    hero_mcgill.webp       the header of every page     box 0 245 1200 695
    hero_mcgill_full.webp  the full-screen Home header  box 0 20 1200 695  (16:9)
"""
import sys
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
WIDTH = 1600


def main(photo, left, top, right, bottom, name="hero_mcgill.webp"):
    out = ROOT / "static" / name
    im = Image.open(photo).convert("RGB").crop((left, top, right, bottom))
    im = im.resize((WIDTH, round(WIDTH * im.height / im.width)), Image.LANCZOS)
    im = ImageEnhance.Brightness(im).enhance(1.12)
    im = ImageEnhance.Color(im).enhance(0.9)
    im.save(out, "WEBP", quality=80, method=6)
    print(f"wrote {out.relative_to(ROOT)} ({im.width} x {im.height}, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) not in (6, 7):
        sys.exit(__doc__)
    main(sys.argv[1], *map(int, sys.argv[2:6]), *sys.argv[6:])
