"""Ground elevation from public terrain tiles, used only to stand symbols on the 3D surface.

The 3D view draws AWS Terrain Tiles (Terrarium encoding, metres above sea level). Symbols need the same
surface height so they sit on it rather than inside it; this module samples those tiles. The values are
for drawing only and are never written into the data.
"""
import io
import math
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np

TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ZOOM = 12
TIMEOUT_S = 5
RETRY_AFTER_S = 300  # a tile that could not be read is tried again after this, not on every rerun
_failed_at = {}


@lru_cache(maxsize=256)
def _read_tile(z, x, y):
    """Heights (m) of one tile. Raises when the tile cannot be read, so a failure is never cached."""
    from PIL import Image
    with urllib.request.urlopen(TERRARIUM_URL.format(z=z, x=x, y=y), timeout=TIMEOUT_S) as r:
        rgb = np.asarray(Image.open(io.BytesIO(r.read())).convert("RGB"), dtype=np.float64)
    return rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768


def _tile(z, x, y):
    if time.monotonic() - _failed_at.get((z, x, y), -math.inf) < RETRY_AFTER_S:
        return None
    try:
        return _read_tile(z, x, y)
    except Exception:  # offline, blocked or slow: symbols fall back to sea level until the tile is tried again
        _failed_at[(z, x, y)] = time.monotonic()
        return None


def elevation(lon, lat, z=ZOOM):
    """Ground elevation (m) at each lon/lat; NaN where tiles cannot be read."""
    lon, lat = np.atleast_1d(np.asarray(lon, float)), np.atleast_1d(np.asarray(lat, float))
    n = 2 ** z
    fx = (lon + 180) / 360 * n
    lat_r = np.radians(lat)
    fy = (1 - np.log(np.tan(lat_r) + 1 / np.cos(lat_r)) / math.pi) / 2 * n
    out = np.full(lon.shape, np.nan)
    ok = np.isfinite(fx) & np.isfinite(fy)
    needed = sorted({(int(a), int(b)) for a, b in zip(fx[ok], fy[ok])})
    with ThreadPoolExecutor(max_workers=8) as pool:  # read the tiles side by side, not one after another
        tiles = dict(zip(needed, pool.map(lambda t: _tile(z, *t), needed)))
    for i in np.flatnonzero(ok):
        a, b = fx[i], fy[i]
        t = tiles[(int(a), int(b))]
        if t is not None:
            out[i] = t[min(int((b % 1) * 256), 255), min(int((a % 1) * 256), 255)]
    return out
