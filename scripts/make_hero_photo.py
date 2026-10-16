"""Make the header photos: views of McGill's Arts Building cut from a photo.

    python scripts/make_hero_photo.py PHOTO LEFT TOP RIGHT BOTTOM [--name NAME] [--width PX] [--lift]

The crop box is in the photo's own pixels; keep people out of it. The cut is resized to --width (default 1600) and
written to static/NAME (default hero_mcgill.webp). --lift brightens it a little and softens the colour, for a dull
photo. The original photo is not kept in the repository.

The photos in use were cut from "Arts Building, McGill University, Aug 31 2022" by D. Benjamin Miller (Wikimedia
Commons, 7512 x 5008 px; credited in the User guide), above the people at its entrance:
    python scripts/make_hero_photo.py arts.png 0 977 7512 3794
        hero_mcgill.webp, the header of every page (8:3, cupola to porch)
    python scripts/make_hero_photo.py arts.png 0 765 5691 3966 --name hero_mcgill_full.webp --width 1920
        the full-screen Home header (16:9, the building to the right of the title)
"""
import argparse
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]


def main(photo, box, name="hero_mcgill.webp", width=1600, lift=False):
    out = ROOT / "static" / name
    im = Image.open(photo).convert("RGB").crop(box)
    im = im.resize((width, round(width * im.height / im.width)), Image.LANCZOS)
    if lift:
        im = ImageEnhance.Color(ImageEnhance.Brightness(im).enhance(1.12)).enhance(0.9)
    im.save(out, "WEBP", quality=80, method=6)
    print(f"wrote {out.relative_to(ROOT)} ({im.width} x {im.height}, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo")
    ap.add_argument("box", nargs=4, type=int, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    ap.add_argument("--name", default="hero_mcgill.webp")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--lift", action="store_true")
    a = ap.parse_args()
    main(a.photo, tuple(a.box), a.name, a.width, a.lift)
