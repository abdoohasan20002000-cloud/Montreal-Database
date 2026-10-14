"""Site-level estimates and plain-language summaries.

Everything here is DERIVED or INTERPOLATED from the measured tables and is labelled so wherever it is shown.
Nothing computed here is written back into the data files.
"""
from datetime import date

import numpy as np
import pandas as pd

from . import config

IDW_METHOD = ("Inverse-distance weighting (power 2) of measured Vs30 at the nearest sites within the search "
              "radius; ignores geology between sites")


def load_regressions():
    if not (config.DATA_DIR / "vs_regressions.csv").exists():
        return pd.DataFrame()
    return pd.read_csv(config.DATA_DIR / "vs_regressions.csv")


def regression_curves(reg, depths=np.linspace(0.5, 30, 60)):
    """Vs-depth curves for the fits whose equation form is known (sand, clay)."""
    rows = []
    for fit, g in reg.groupby("fit"):
        form = str(g["equation"].iloc[0])
        p = dict(zip(g["parameter"], g["value"]))
        if form.startswith("Vs = a + b*z^c") and {"a", "b", "c"} <= set(p):
            vs = p["a"] + p["b"] * depths ** p["c"]
        elif form.startswith("Vs = a + b*z^0.5") and {"a", "b"} <= set(p):
            vs = p["a"] + p["b"] * depths ** 0.5
        else:
            continue
        label = {"reg_sand": "sand (Rosset fit)", "reg_clay": "clay (Rosset fit)"}.get(fit, f"{fit} fit")
        rows += [{"fit": label, "depth_m": d, "vs_ms": v, "equation": form} for d, v in zip(depths, vs)]
    return pd.DataFrame(rows)


def neighbours(sites, x, y, radius_m):
    """Measured sites with a Vs30, sorted by distance from (x, y) in MTM 8, within radius_m."""
    s = sites.dropna(subset=["vs30_ms"]).copy()
    s["distance_m"] = np.hypot(s["x_mtm8"] - x, s["y_mtm8"] - y)
    return s[s["distance_m"] <= radius_m].sort_values("distance_m")


def idw_vs30(near, k=6, power=2):
    """IDW estimate from the k nearest rows of `near`. Returns (estimate, n_used) or (None, 0)."""
    use = near.head(k)
    if use.empty:
        return None, 0
    d = np.maximum(use["distance_m"].to_numpy(float), 1.0)
    w = 1 / d ** power
    return float((w * use["vs30_ms"].to_numpy(float)).sum() / w.sum()), len(use)


def nbcc_class(vs30):
    if vs30 is None or vs30 != vs30:
        return None
    return "A" if vs30 > 1500 else "B" if vs30 > 760 else "C" if vs30 > 360 else "D" if vs30 >= 180 else "E"


CLASS_WORDS = {"A": "hard rock", "B": "rock", "C": "very dense soil or soft rock", "D": "stiff soil", "E": "soft soil"}


def _sites(n, words=""):
    return f"{n} {words + ' ' if words else ''}site{'' if n == 1 else 's'}"


def summary(lat, lon, radius_m, near, est, n_used, n_prof_rows, n_prof_sites, bh_near, on_island, region=""):
    """A short plain-language paragraph for a site report."""
    parts = []
    place = f" in {region}" if region and on_island and region != config.OFF_ISLAND else ""
    where = f"Around {lat:.5f}, {lon:.5f}{place}" + ("" if on_island else " (outside the island)")
    if near.empty:
        parts.append(f"{where} there is no measured Vs30 within {radius_m / 1000:.1f} km. "
                     "Widen the search radius, or treat this location as unmeasured.")
    else:
        n0 = near.iloc[0]
        if n0["distance_m"] < 25:
            parts.append(f"{where} you are on measured site {n0['site_id']} ({n0['area']}): Vs30 "
                         f"{n0['vs30_ms']:.0f} m/s, measured. Use that value; the estimate below is only a "
                         "cross-check against the neighbours.")
        else:
            parts.append(f"{where}, the closest measured Vs30 is {n0['vs30_ms']:.0f} m/s at site {n0['site_id']} "
                         f"({n0['area']}), {n0['distance_m']:.0f} m away.")
        if est is not None:
            c = nbcc_class(est)
            spread = near.head(n_used)["vs30_ms"]
            parts.append(f"Weighting the {_sites(n_used, 'nearest measured')} by distance gives about {est:.0f} m/s "
                         f"(range of those sites {spread.min():.0f}–{spread.max():.0f} m/s). This is an "
                         f"INTERPOLATED value, not a measurement; it would fall in NBCC class {c} "
                         f"({CLASS_WORDS.get(c, '')}).")
            if spread.max() - spread.min() > 250:
                parts.append("The nearby sites disagree strongly, so ground conditions probably change over "
                             "short distances here; do not rely on the estimate.")
    if n_prof_rows:
        parts.append(f"{n_prof_sites} Vs-depth profile(s) with {n_prof_rows} readings lie inside the radius.")
    if bh_near is not None and not bh_near.empty:
        pre = int((bh_near["data_era"] == "pre-1960").sum())
        parts.append(f"The archive has {len(bh_near)} borehole(s) inside the radius"
                     + (f", {pre} of them before 1960 (their SPT N reads about half of modern values)." if pre else "."))
    parts.append("For design, measure Vs30 at the site.")
    return " ".join(parts)


def report_table(lat, lon, x, y, radius_m, near, est, n_used, region=""):
    """One row per value in the report, with status, method, source and date."""
    today = date.today().isoformat()
    rows = [{"item": "location (WGS84)", "value": f"{lat:.6f}, {lon:.6f}", "status": "input", "method": "picked by user",
             "source": "", "date": today},
            {"item": "location (MTM 8, EPSG:32188)", "value": f"{x:.1f} E, {y:.1f} N", "status": "derived",
             "method": "pyproj transform", "source": "", "date": today}]
    if region:
        rows.append({"item": "region (borough or linked city)", "value": region, "status": "derived",
                     "method": "point in polygon, MTM 8", "source": "City of Montréal administrative limits (CC BY 4.0)",
                     "date": today})
    for _, r in near.head(n_used or 5).iterrows():
        rows.append({"item": f"Vs30 at site {r['site_id']} ({r['distance_m']:.0f} m)", "value": f"{r['vs30_ms']:.0f} m/s",
                     "status": "measured", "method": r.get("survey_type", ""), "source": r.get("source", ""),
                     "date": r.get("processed_on", "")})
    if est is not None:
        rows.append({"item": "Vs30 at this location", "value": f"{est:.0f} m/s", "status": "interpolated",
                     "method": f"{IDW_METHOD}; {n_used} sites; radius {radius_m:.0f} m", "source": "sites above",
                     "date": today})
        rows.append({"item": "NBCC site class at this location", "value": nbcc_class(est), "status": "interpolated",
                     "method": "NBCC Vs30 limits applied to the interpolated Vs30", "source": "", "date": today})
    return pd.DataFrame(rows)
