"""Geometry for the 3D view: measurements drawn below the ground, to the depth they describe.

Depths stay in metres below the ground surface. The page decides how much to stretch them for display.
"""
import numpy as np
import pandas as pd

from . import geo

VS30_DEPTH_M = 30  # Vs30 is the time-averaged shear-wave velocity over the top 30 m


PROFILE = ["site_id", "x_mtm8", "y_mtm8"]  # a profile is one site_id at one location
MAX_REACH_M = 2.5  # a reading speaks for at most this far above and below it; wider gaps stay visible as gaps


def profile_segments(prof):
    """One row per Vs reading, as a depth interval [top_m, bot_m] around the reading.

    Each reading covers the ground halfway to its neighbours above and below, but never more than MAX_REACH_M, so a
    gap in the readings stays a gap. The first and last readings are mirrored, and nothing goes above the surface.
    Readings without a location, or marked as duplicates of an earlier sheet, are left out; readings at the same depth
    of one profile are merged into one, at their median velocity."""
    cols = ["top_m", "bot_m"]
    if prof.empty:
        return prof.assign(**{c: pd.Series(dtype=float) for c in cols})
    p = prof.dropna(subset=["x_mtm8", "y_mtm8", "depth_m", "vs_ms"])
    if "duplicate_of_earlier_sheet" in p.columns:
        p = p[~p["duplicate_of_earlier_sheet"].fillna(False).astype(bool)]
    if p.empty:
        return p.assign(**{c: pd.Series(dtype=float) for c in cols})
    keys = PROFILE + ["depth_m"]
    p = p.groupby(keys, as_index=False, sort=True).agg(
        {**{c: "first" for c in p.columns if c not in keys and c != "vs_ms"}, "vs_ms": "median"})
    by = p.groupby(PROFILE, sort=False)["depth_m"]
    up = (p["depth_m"] - by.shift(1)) / 2
    down = (by.shift(-1) - p["depth_m"]) / 2
    up, down = up.fillna(down), down.fillna(up)  # mirror at the ends
    up, down = up.fillna(0.25), down.fillna(0.25)  # a profile of one reading
    p["top_m"] = (p["depth_m"] - up.clip(upper=MAX_REACH_M)).clip(lower=0)
    p["bot_m"] = p["depth_m"] + down.clip(upper=MAX_REACH_M)
    return p


def fan_out(df, key, spacing_m=260.0):
    """Spread items that share a position on a small ring around it, so each can be seen and hovered.

    `key` names the column that tells the items apart (one profile per site_id). Rows of the same item move together.
    Returns a copy with lon/lat recomputed from the shifted MTM 8 position; x_mtm8 and y_mtm8 keep the true position."""
    if df.empty:
        return df.assign(lon=df.get("lon"), lat=df.get("lat"))
    out = df.copy()
    items = out[[key, "x_mtm8", "y_mtm8"]].drop_duplicates()
    items["n"] = items.groupby(["x_mtm8", "y_mtm8"])[key].transform("size")
    items["i"] = items.groupby(["x_mtm8", "y_mtm8"]).cumcount()
    angle = 2 * np.pi * items["i"] / items["n"].clip(lower=1)
    # a ring whose circumference leaves about `spacing_m` between neighbours, never tighter than one spacing
    ring = np.where(items["n"] > 1, np.clip(spacing_m * items["n"] / (2 * np.pi), spacing_m, 1200), 0.0)
    items["dx"], items["dy"] = ring * np.sin(angle), ring * np.cos(angle)
    out = out.merge(items[[key, "x_mtm8", "y_mtm8", "dx", "dy"]], on=[key, "x_mtm8", "y_mtm8"], how="left")
    lon, lat = geo.mtm8_to_wgs84((out["x_mtm8"] + out["dx"]).to_numpy(), (out["y_mtm8"] + out["dy"]).to_numpy())
    out["lon"], out["lat"] = np.asarray(lon), np.asarray(lat)
    out["shared_position"] = (out["dx"] != 0) | (out["dy"] != 0)
    return out.drop(columns=["dx", "dy"])


def borehole_depths(bh, samples):
    """Each borehole's depth in metres: its recorded depth, else the bottom of its deepest sample, else NaN."""
    depth = pd.to_numeric(bh["depth_m"], errors="coerce") if "depth_m" in bh.columns else pd.Series(np.nan, index=bh.index)
    if not samples.empty and {"hole_id", "depth_bot_m"} <= set(samples.columns):
        deepest = samples.groupby("hole_id")["depth_bot_m"].max()
        depth = depth.fillna(bh["hole_id"].map(deepest))
    return depth.where(depth > 0)


def vs_band(vs):
    """The NBCC class band a shear-wave velocity falls in (same limits as for Vs30: 180, 360, 760, 1500 m/s)."""
    from .insight import nbcc_class
    return nbcc_class(vs)


VS_BAND_LABELS = {"E": "under 180", "D": "180–360", "C": "360–760", "B": "760–1500", "A": "over 1500"}
