"""Coordinate conversion and the island check."""
import json
from functools import lru_cache

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
