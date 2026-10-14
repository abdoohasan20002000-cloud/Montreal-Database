"""Draw the decorative header art: contour lines of the island's terrain with the measured Vs sites as points.

Elevation comes from the public AWS Terrain Tiles (Terrarium encoding, the same source as the 3D view).
The picture is decoration only; nothing in it is used as data.

    python scripts/make_hero_art.py          # light theme (default): writes static/hero_contours.webp
    python scripts/make_hero_art.py --dark   # cyan lines for a dark theme
"""
import io
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from geotech import config  # noqa: E402

URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
Z = 12
LON0, LON1, LAT0, LAT1 = -73.99, -73.45, 45.40, 45.72
OUT = ROOT / "static" / "hero_contours.webp"


def tile_xy(lon, lat, z=Z):
    n = 2 ** z
    lat_r = math.radians(lat)
    return (lon + 180) / 360 * n, (1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n


def fetch(z, x, y):
    with urllib.request.urlopen(URL.format(z=z, x=x, y=y), timeout=20) as r:
        rgb = np.asarray(Image.open(io.BytesIO(r.read())).convert("RGB"), dtype=np.float64)
    return rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768


def mosaic():
    fx0, fy0 = tile_xy(LON0, LAT1)
    fx1, fy1 = tile_xy(LON1, LAT0)
    xs, ys = range(int(fx0), int(fx1) + 1), range(int(fy0), int(fy1) + 1)
    rows = [np.hstack([fetch(Z, x, y) for x in xs]) for y in ys]
    dem = np.vstack(rows)
    # crop to the requested box (pixel coordinates inside the mosaic)
    px = lambda f, base: int(round((f - base) * 256))  # noqa: E731
    return dem[px(fy0, ys[0]):px(fy1, ys[0]), px(fx0, xs[0]):px(fx1, xs[0])], (fx0, fy0, fx1, fy1)


def smooth(a, passes=3, k=5):
    """Repeated box blur (close to a Gaussian) to soften building and quarry artefacts in the DEM."""
    pad = k // 2
    for _ in range(passes):
        for axis in (0, 1):
            b = np.pad(a, [(pad, pad) if i == axis else (0, 0) for i in (0, 1)], mode="edge")
            c = np.cumsum(b, axis=axis, dtype=float)
            c = np.concatenate([np.zeros_like(c.take([0], axis=axis)), c], axis=axis)
            a = (c.take(range(k, c.shape[axis]), axis=axis) - c.take(range(0, c.shape[axis] - k), axis=axis)) / k
    return a


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgba

    dem, (fx0, fy0, fx1, fy1) = mosaic()
    dem = smooth(np.clip(dem, 0, None))
    h, w = dem.shape
    scale = 2.0
    fig = plt.figure(figsize=(w * scale / 100, h * scale / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis("off")
    fig.patch.set_alpha(0)

    dark = "--dark" in sys.argv
    line, glow = ("#22d3ee", "#22d3ee") if dark else ("#0e7490", "#22d3ee")
    dot, halo = ("#fde68a", "#fbbf24") if dark else ("#b45309", "#f59e0b")
    # faint graticule every 0.05 degrees
    for lon in np.arange(-74.0, -73.40, 0.05):
        x = (tile_xy(lon, 45.5)[0] - fx0) * 256
        ax.axvline(x, color=to_rgba(line, 0.05), lw=0.6)
    for lat in np.arange(45.40, 45.75, 0.05):
        y = (tile_xy(-73.7, lat)[1] - fy0) * 256
        ax.axhline(y, color=to_rgba(line, 0.05), lw=0.6)

    levels = np.arange(30, 240, 10)
    for lw, a in ((4.0, 0.07), (2.0, 0.14)):  # glow
        ax.contour(dem, levels=levels, colors=[to_rgba(glow, a)], linewidths=lw)
    alphas = np.interp(levels, [30, 230], [0.45, 1.0] if dark else [0.55, 1.0])
    ax.contour(dem, levels=levels, colors=[to_rgba(line, a) for a in alphas], linewidths=0.9 if dark else 1.2)

    sites = pd.read_csv(config.VS30_SITES_CSV)
    sites = sites.dropna(subset=["lon", "lat"])
    pts = np.array([tile_xy(lo, la) for lo, la in zip(sites["lon"], sites["lat"])])
    px, py = (pts[:, 0] - fx0) * 256, (pts[:, 1] - fy0) * 256
    ax.scatter(px, py, s=260, color=to_rgba(halo, 0.10), linewidths=0)
    ax.scatter(px, py, s=60, color=to_rgba(halo, 0.30), linewidths=0)
    ax.scatter(px, py, s=10, color=to_rgba(dot, 1.0), linewidths=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True)
    img = Image.open(io.BytesIO(buf.getvalue())).convert("RGBA")
    img = img.resize((1200, round(1200 * img.height / img.width)), Image.LANCZOS)
    OUT.parent.mkdir(exist_ok=True)
    img.save(OUT, "WEBP", quality=75, method=6)
    print(f"wrote {OUT.relative_to(ROOT)} ({img.width}x{img.height}, {OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
