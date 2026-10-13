"""Load the borehole archive and select what falls in an area."""
import numpy as np
import pandas as pd
from shapely import wkt as shp_wkt
from shapely.geometry import Point
import shapely

from . import config, geo


def _normalise(df, mapping):
    """Rename known spellings to the app's names; keep every other column untouched."""
    rename = {}
    for target, options in mapping.items():
        for opt in options:
            if opt in df.columns and target not in df.columns:
                rename[opt] = target
                break
    return df.rename(columns=rename)


def era_label(year):
    if pd.isna(year):
        return "undated"
    return "pre-1960" if year < config.PRE_MODERN_YEAR else "1960 and later"


def load_archive(use_demo=False):
    """Return (boreholes, samples, label). Either frame may be empty if no file is present."""
    bh_path, s_path, label = config.BOREHOLES_CSV, config.SAMPLES_CSV, "archive"
    if use_demo or not bh_path.exists():
        bh_path, s_path, label = config.DEMO_BOREHOLES_CSV, config.DEMO_SAMPLES_CSV, "DEMO (synthetic, not real data)"
    if not bh_path.exists():
        return pd.DataFrame(), pd.DataFrame(), "none"

    bh = _normalise(pd.read_csv(bh_path, low_memory=False), config.BOREHOLE_COLUMNS)
    missing = [c for c in ("hole_id", "x_mtm8", "y_mtm8") if c not in bh.columns]
    if missing:
        raise ValueError(f"{bh_path.name} lacks columns {missing}; add the spelling to config.BOREHOLE_COLUMNS")
    bh["hole_id"] = bh["hole_id"].astype(str)
    lon, lat = geo.mtm8_to_wgs84(bh["x_mtm8"].to_numpy(float), bh["y_mtm8"].to_numpy(float))
    bh["lon"], bh["lat"] = np.round(lon, 6), np.round(lat, 6)
    if "data_era" not in bh.columns:
        bh["data_era"] = bh["year"].map(era_label) if "year" in bh.columns else "undated"
    if "vs30_ms" in bh.columns and "vs30_status" not in bh.columns:
        # Archive Vs30 comes from a lithology lookup (Rosset et al. 2023); never measured.
        bh["vs30_status"] = "estimated (lithology lookup, Rosset et al. 2023)"

    samples = pd.DataFrame()
    if s_path.exists():
        samples = _normalise(pd.read_csv(s_path, low_memory=False), config.SAMPLE_COLUMNS)
        samples["hole_id"] = samples["hole_id"].astype(str)
        if "refusal" in samples.columns:
            samples["refusal"] = samples["refusal"].map(_as_bool)
    return bh, samples, label


def _as_bool(v):
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if pd.isna(v):
        return False  # blank refusal means "not a refusal", never True
    return str(v).strip().lower() in {"1", "true", "yes", "y", "oui", "r", "refusal"}


# ---- selection -------------------------------------------------------------

def selection_from_inputs(mode, drawing=None, click=None, radius_m=500):
    """Build a selection geometry in MTM 8 (None means the whole island)."""
    if mode == "Whole island":
        return None
    if mode == "Point and radius" and click:
        x, y = geo.wgs84_to_mtm8(click["lng"], click["lat"])
        return Point(x, y).buffer(radius_m)
    if mode == "Draw an area" and drawing:
        g = shapely.geometry.shape(drawing["geometry"])
        if g.geom_type == "Point":
            x, y = geo.wgs84_to_mtm8(g.x, g.y)
            return Point(x, y).buffer(radius_m)
        return geo.geom_wgs84_to_mtm8(g)
    return "incomplete"


def points_in(df, area, xcol="x_mtm8", ycol="y_mtm8"):
    """Rows of df whose MTM 8 point lies in area (None = everything)."""
    if df.empty or area is None:
        return df
    inside = shapely.intersects_xy(area, df[xcol].to_numpy(float), df[ycol].to_numpy(float))
    return df[inside]


def uploads_in(records, area):
    """Uploaded files whose footprint touches area."""
    if area is None:
        return records
    out = []
    for r in records:
        fp = r.get("footprint_wkt_mtm8")
        if fp and shp_wkt.loads(fp).intersects(area):
            out.append(r)
    return out
