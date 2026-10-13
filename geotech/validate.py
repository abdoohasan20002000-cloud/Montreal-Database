"""Checks run on every upload before a curator sees it.

Each check returns (level, message): level is "block", "warn" or "ok".
Blocked uploads are not stored; warnings go to the curator with the file.
"""
import hashlib
import io

import pandas as pd

from . import config, geo
from .data import _normalise


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_upload(data: bytes, file_name: str, footprint_mtm8, work_year, existing_hashes):
    """Run all checks. footprint_mtm8 is a shapely geometry in MTM 8."""
    results = []
    digest = sha256(data)
    if digest in existing_hashes:
        results.append(("block", f"Same file already stored (upload {existing_hashes[digest]})."))
    if not data:
        results.append(("block", "File is empty."))

    shp, how = geo.island_shape_mtm8()
    if footprint_mtm8 is None:
        results.append(("block", "No map location given."))
    elif not shp.intersects(footprint_mtm8):
        results.append(("block", f"Location is off the island ({how})."))
    else:
        results.append(("ok", f"Location is on the island ({how})."))

    if work_year and int(work_year) < config.PRE_MODERN_YEAR:
        results.append(("warn", "Work date before 1960: flagged pre-1960 (SPT N about half of modern values)."))

    results += _check_content(data, file_name.lower())
    return results, digest


def _check_content(data, name):
    if name.endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            return [("block", "File is named .pdf but is not a PDF.")]
        if b"/Encrypt" in data[:200000] or b"/Encrypt" in data[-200000:]:
            return [("block", "PDF is password protected or encrypted.")]
        return [("ok", "PDF opens.")]
    if name.endswith((".csv", ".txt", ".xlsx", ".xls")):
        try:
            df = _read_table(data, name)
        except Exception as e:  # unreadable table
            return [("block", f"Table could not be read: {e}")]
        return [("ok", f"Table read: {len(df)} rows, {len(df.columns)} columns.")] + check_table(df)
    return [("ok", "Stored as an original file; contents not checked.")]


def _read_table(data, name):
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data))
    text = data.decode("utf-8-sig", errors="replace")
    sep = ";" if text.split("\n", 1)[0].count(";") > text.split("\n", 1)[0].count(",") else ","  # French Excel
    df = pd.read_csv(io.StringIO(text), sep=sep)
    if sep == ";":
        for c in df.columns:  # decimal commas
            if df[c].dtype == object:
                conv = pd.to_numeric(df[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")
                if conv.notna().sum() >= 0.9 * df[c].notna().sum() > 0:
                    df[c] = conv
    return df


def check_table(df):
    """Project rules for borehole-type tables. Only the columns present are checked."""
    out = []
    df = _normalise(_normalise(df, config.BOREHOLE_COLUMNS), config.SAMPLE_COLUMNS)
    has_depths = {"depth_top_m", "depth_bot_m"} <= set(df.columns)

    if "hole_id" in df.columns and not has_depths:
        dup = df["hole_id"][df["hole_id"].duplicated()].astype(str).unique()
        if len(dup):
            out.append(("warn", f"{len(dup)} hole IDs repeat: {', '.join(dup[:10])}"))
        else:
            out.append(("ok", "Hole IDs are unique."))

    if {"x_mtm8", "y_mtm8"} <= set(df.columns):
        xy = df[["x_mtm8", "y_mtm8"]].apply(pd.to_numeric, errors="coerce")
        bad_xy = xy.isna().any(axis=1)
        off = [i for i, r in xy[~bad_xy].iterrows() if not geo.on_island(r.x_mtm8, r.y_mtm8)]
        swapped = [i for i in off if geo.on_island(xy.at[i, "y_mtm8"], xy.at[i, "x_mtm8"])]
        if bad_xy.any():
            out.append(("warn", f"{int(bad_xy.sum())} rows have missing or unreadable coordinates."))
        if off:
            msg = f"{len(off)} rows are off the island (MTM 8)"
            out.append(("warn", msg + (f"; {len(swapped)} look like X and Y swapped." if swapped else ".")))
        if not off and not bad_xy.any():
            out.append(("ok", "All coordinates are on the island (MTM 8)."))

    if has_depths:
        top = pd.to_numeric(df["depth_top_m"], errors="coerce")
        bot = pd.to_numeric(df["depth_bot_m"], errors="coerce")
        bad = (top < 0) | (bot <= top)
        if bad.any():
            out.append(("warn", f"{int(bad.sum())} rows have negative depth or bottom not below top."))
        if "hole_id" in df.columns:
            d = pd.DataFrame({"h": df["hole_id"], "t": top, "b": bot}).dropna().sort_values(["h", "t"])
            overlap = (d.groupby("h")["b"].shift() > d["t"] + 1e-6).sum()
            if overlap:
                out.append(("warn", f"{int(overlap)} samples or layers overlap the one above in the same hole."))
        if not bad.any():
            out.append(("ok", "Depths are consistent."))

    if "n_field" in df.columns:
        n = pd.to_numeric(df["n_field"], errors="coerce")
        if (n >= 999).any():
            out.append(("warn", f"{int((n >= 999).sum())} N-values of 999 or more: code refusals in a refusal column, not as N = 999."))
        if "refusal" not in df.columns:
            out.append(("warn", "No refusal column: refusals cannot be told apart from N-values."))
        if n.isin([50, 100]).sum() > 0.05 * n.notna().sum() and n.notna().sum() >= 20:
            out.append(("warn", "Many N = 50 or 100: these may be refusals typed as numbers."))

    if "vs30_ms" in df.columns:
        v = pd.to_numeric(df["vs30_ms"], errors="coerce")
        outside = v.notna() & ((v < config.VS30_MIN) | (v > config.VS30_MAX))
        if outside.any():
            out.append(("warn", f"{int(outside.sum())} Vs30 values outside {config.VS30_MIN}-{config.VS30_MAX} m/s."))
        if "vs30_status" not in df.columns:
            out.append(("warn", "Vs30 given without vs30_status: say whether it is measured or estimated."))

    if "year" in df.columns:
        y = pd.to_numeric(df["year"], errors="coerce")
        if (y < config.PRE_MODERN_YEAR).any():
            out.append(("warn", f"{int((y < config.PRE_MODERN_YEAR).sum())} rows dated before 1960 (flag pre-1960)."))
    return out
