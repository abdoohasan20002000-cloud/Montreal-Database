"""Site-level estimates and plain-language summaries.

Everything here is DERIVED or INTERPOLATED from the measured tables and is labelled so wherever it is shown.
Nothing computed here is written back into the data files.
"""

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
    today = config.today().isoformat()
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


SQRT3 = np.sqrt(3.0)


def hex_cells(points, radius_m=600.0):
    """Count points in flat hexagonal cells laid out in MTM 8 metres.

    `points` has x_mtm8, y_mtm8 and kind. Cells are pointy-topped, `radius_m` from centre to corner. Returns one row per
    cell with any point in it: the count of each kind, the total, and the cell's corners as [lon, lat] pairs for the
    web map (closed ring)."""
    pts = points.dropna(subset=["x_mtm8", "y_mtm8"])
    if pts.empty:
        return pd.DataFrame(columns=["q", "r", "n", "ring"])
    x, y = pts["x_mtm8"].to_numpy(float), pts["y_mtm8"].to_numpy(float)
    # axial coordinates, then rounding in cube coordinates to the nearest cell
    qf, rf = (SQRT3 / 3 * x - y / 3) / radius_m, (2 / 3 * y) / radius_m
    sf = -qf - rf
    q, r, s = np.round(qf), np.round(rf), np.round(sf)
    dq, dr, ds = np.abs(q - qf), np.abs(r - rf), np.abs(s - sf)
    fix_q = (dq > dr) & (dq > ds)
    fix_r = ~fix_q & (dr > ds)
    q = np.where(fix_q, -r - s, q)
    r = np.where(fix_r, -q - s, r)
    cells = pts.assign(q=q.astype(int), r=r.astype(int))
    counts = cells.pivot_table(index=["q", "r"], columns="kind", aggfunc="size", fill_value=0)
    counts.columns = [str(c) for c in counts.columns]
    counts["n"] = counts.sum(axis=1)
    counts = counts.reset_index()
    cx = radius_m * SQRT3 * (counts["q"] + counts["r"] / 2)
    cy = radius_m * 1.5 * counts["r"]
    angles = np.deg2rad(30 + 60 * np.arange(7))  # six corners and back to the first
    ring_x = cx.to_numpy()[:, None] + radius_m * np.cos(angles)[None, :]
    ring_y = cy.to_numpy()[:, None] + radius_m * np.sin(angles)[None, :]
    from . import geo
    lon, lat = geo.mtm8_to_wgs84(ring_x.ravel(), ring_y.ravel())
    lon, lat = np.asarray(lon).reshape(ring_x.shape), np.asarray(lat).reshape(ring_y.shape)
    counts["ring"] = [np.column_stack([lo, la]).round(6).tolist() for lo, la in zip(lon, lat)]
    return counts


def count_classes(most):
    """Lower edges of up to five count classes, growing by a round factor (2, 3, 5 or 10) chosen so five classes
    reach `most`, and none starting above it: 1, 2, 4, 8 for up to 15 points per cell; 1, 10, 100, 1000 for
    thousands. The last class is open-ended."""
    for f in (2, 3, 5, 10, 100):
        if f ** 4 >= most:
            break
    return [f ** i for i in range(5) if f ** i <= max(most, 1)]  # no class above the largest count


def count_class_label(edges, i):
    lo = edges[i]
    if i == len(edges) - 1:
        return f"{lo:,}" if lo == 1 else f"{lo:,} or more"
    hi = edges[i + 1] - 1
    return f"{lo:,}" if hi == lo else f"{lo:,}–{hi:,}"
