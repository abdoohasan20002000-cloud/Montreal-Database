"""Ground elevation from public terrain tiles, used only to stand symbols on the 3D surface.

The 3D view draws AWS Terrain Tiles (Terrarium encoding, metres above sea level). Symbols need the same
surface height so they sit on it rather than inside it; this module samples those tiles. The values are
for drawing only and are never written into the data.
"""
import io
import math
import urllib.request
from functools import lru_cache

import numpy as np

TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ZOOM = 12


@lru_cache(maxsize=256)
def _tile(z, x, y):
    from PIL import Image
    try:
        with urllib.request.urlopen(TERRARIUM_URL.format(z=z, x=x, y=y), timeout=10) as r:
            rgb = np.asarray(Image.open(io.BytesIO(r.read())).convert("RGB"), dtype=np.float64)
    except Exception:  # offline or blocked: symbols fall back to sea level
        return None
    return rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768


def elevation(lon, lat, z=ZOOM):
    """Ground elevation (m) at each lon/lat; NaN where tiles cannot be read."""
    lon, lat = np.atleast_1d(np.asarray(lon, float)), np.atleast_1d(np.asarray(lat, float))
    n = 2 ** z
    fx = (lon + 180) / 360 * n
    lat_r = np.radians(lat)
    fy = (1 - np.log(np.tan(lat_r) + 1 / np.cos(lat_r)) / math.pi) / 2 * n
    out = np.full(lon.shape, np.nan)
    for i, (a, b) in enumerate(zip(fx, fy)):
        if not (np.isfinite(a) and np.isfinite(b)):
            continue
        t = _tile(z, int(a), int(b))
        if t is not None:
            out[i] = t[min(int((b % 1) * 256), 255), min(int((a % 1) * 256), 255)]
    return out
