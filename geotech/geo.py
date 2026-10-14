"""Coordinate conversion, the island check and the regions (boroughs and linked cities)."""
import json
from functools import lru_cache

import numpy as np

from pyproj import Transformer
from shapely.geometry import Point, shape, box
import shapely

from . import config

_to_wgs = Transformer.from_crs(config.CRS_MTM8, config.CRS_WGS84, always_xy=True)
_to_mtm = Transformer.from_crs(config.CRS_WGS84, config.CRS_MTM8, always_xy=True)


def mtm8_to_wgs84(x, y):
    """Return (lon, lat). Works on scalars or arrays."""
    return _to_wgs.transform(x, y)


def wgs84_to_mtm8(lon, lat):
    """Return (x, y) in MTM zone 8 metres."""
    return _to_mtm.transform(lon, lat)


def shp_transform_to_wgs84(geom):
    return shapely.transform(geom, _to_wgs.transform, interleaved=False)


def geom_wgs84_to_mtm8(geom):
    return shapely.transform(geom, _to_mtm.transform, interleaved=False)


@lru_cache(maxsize=1)
def island_shape_mtm8():
    """Island outline in MTM 8 buffered by the shore tolerance, plus a label of which check is used."""
    if config.ISLAND_OUTLINE.exists():
        gj = json.loads(config.ISLAND_OUTLINE.read_text(encoding="utf-8"))
        feats = gj["features"] if gj.get("type") == "FeatureCollection" else [gj]
        from shapely.ops import unary_union
        outline = unary_union([shape(f["geometry"]) for f in feats])
        # Outline files from the portal package are WGS84; a file already in metres is used as is.
        if outline.bounds[0] > -180 and outline.bounds[2] < 180:
            outline = geom_wgs84_to_mtm8(outline)
        return outline.buffer(config.SHORE_TOLERANCE_M), "island outline + 250 m"
    b = config.ISLAND_BBOX
    rough = geom_wgs84_to_mtm8(box(b["lon_min"], b["lat_min"], b["lon_max"], b["lat_max"]))
    return rough, "rough island box (add data/island_outline.geojson for the precise check)"


def on_island(x_mtm8, y_mtm8):
    shp, _ = island_shape_mtm8()
    return shp.contains(Point(x_mtm8, y_mtm8))


# ---- regions -------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def regions_geojson():
    """The boroughs and linked cities as GeoJSON (WGS84), or None when data/regions.geojson is missing."""
    if not config.REGIONS_GEOJSON.exists():
        return None
    return json.loads(config.REGIONS_GEOJSON.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def regions():
    """[(name, kind, geometry in MTM 8)], boroughs first, then cities, each alphabetical."""
    gj = regions_geojson()
    if not gj:
        return []
    out = []
    for f in gj["features"]:
        g = geom_wgs84_to_mtm8(shape(f["geometry"]))
        shapely.prepare(g)
        out.append((f["properties"]["region"], f["properties"].get("kind", ""), g))
    return out


def region_names():
    return [n for n, _, _ in regions()]


def region_kinds():
    return {n: k for n, k, _ in regions()}


def region_of(x, y):
    """Region name for each MTM 8 point: the borough or city that contains it, config.OFF_ISLAND outside them all,
    and "" where the position is unknown. Derived from the City's administrative limits (data/regions.geojson)."""
    x = np.atleast_1d(np.asarray(x, dtype=float))
    y = np.atleast_1d(np.asarray(y, dtype=float))
    ok = np.isfinite(x) & np.isfinite(y)
    out = np.where(ok, config.OFF_ISLAND, "").astype(object)
    if not regions():
        out[ok] = ""
        return out
    todo = ok.copy()
    for name, _, g in regions():
        hit = todo & shapely.contains_xy(g, x, y)
        out[hit] = name
        todo &= ~hit
    # Points on the shore band the island check accepts (within SHORE_TOLERANCE_M) take the nearest region,
    # so a point is never "on the island" and "off the island" at once.
    for i in np.flatnonzero(todo):
        pt = Point(x[i], y[i])
        d, name = min((g.distance(pt), n) for n, _, g in regions())
        if d <= config.SHORE_TOLERANCE_M:
            out[i] = name
    return out


def regions_touching(geom_mtm8):
    """Names of the regions a footprint (point, line or area, MTM 8) touches; config.OFF_ISLAND if none."""
    names = [n for n, _, g in regions() if g.intersects(geom_mtm8)]
    if not names and regions():  # on the shore band: the regions within the island check's tolerance
        near = geom_mtm8.buffer(config.SHORE_TOLERANCE_M)
        names = [n for n, _, g in regions() if g.intersects(near)]
    return names or ([config.OFF_ISLAND] if regions() else [])


def region_shape(names):
    """Union of the named regions in MTM 8 (None if no names or no regions file)."""
    from shapely.ops import unary_union
    parts = [g for n, _, g in regions() if n in set(names)]
    return unary_union(parts) if parts else None
