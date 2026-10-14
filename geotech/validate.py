"""Checks run on every upload before a curator sees it.

Each check returns (level, message): level is "block", "warn" or "ok".
Blocked uploads are not stored; warnings go to the curator with the file.
"""
import hashlib
import io

import numpy as np
import pandas as pd

from . import config, geo
from .data import _normalise

# Tables are checked on their first rows only, so one large upload cannot use up the app's memory.
CHECK_ROWS = 200_000


def _n(count, one, many):
    """'1 row' / '3 rows'."""
    return f"{count:,} {one if count == 1 else many}"


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

    if footprint_mtm8 is None:
        results.append(("block", "No map location given."))
    else:
        inside, how = geo.island_intersects(footprint_mtm8)
        results.append(("ok", f"Location is on the island ({how}).") if inside else
                       ("block", f"Location is off the island ({how})."))

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
        read = f"Table read: {len(df):,} rows, {len(df.columns)} columns."
        if len(df) > CHECK_ROWS:
            df = df.head(CHECK_ROWS)
            read = (f"Table read: more than {CHECK_ROWS:,} rows, {len(df.columns)} columns. The checks below cover "
                    f"its first {CHECK_ROWS:,} rows; the curator checks the rest.")
        return [("ok", read)] + check_table(df)
    return [("ok", "Stored as an original file; contents not checked.")]


def _read_table(data, name):
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data), nrows=CHECK_ROWS + 1)  # one more row tells whether there are more
    first = data[:65536].split(b"\n", 1)[0].decode("utf-8-sig", errors="replace")
    sep = ";" if first.count(";") > first.count(",") else ","  # French Excel
    df = pd.read_csv(io.BytesIO(data), sep=sep, nrows=CHECK_ROWS + 1, encoding="utf-8-sig", encoding_errors="replace")
    if sep == ";":
        for c in df.columns:  # decimal commas
            if df[c].dtype == object or isinstance(df[c].dtype, pd.StringDtype):  # text columns in pandas 2 and 3
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
            out.append(("warn", f"{_n(len(dup), 'hole ID repeats', 'hole IDs repeat')}: {', '.join(dup[:10])}"))
        else:
            out.append(("ok", "Hole IDs are unique."))

    if {"x_mtm8", "y_mtm8"} <= set(df.columns):
        xy = df[["x_mtm8", "y_mtm8"]].apply(pd.to_numeric, errors="coerce")
        x, y = xy["x_mtm8"].to_numpy(dtype=float), xy["y_mtm8"].to_numpy(dtype=float)
        bad_xy = xy.isna().any(axis=1)
        off = np.zeros(len(xy), dtype=bool)
        off[~bad_xy.to_numpy()] = ~geo.on_island_many(x[~bad_xy.to_numpy()], y[~bad_xy.to_numpy()])
        swapped = np.zeros(len(xy), dtype=bool)
        swapped[off] = geo.on_island_many(y[off], x[off])
        if bad_xy.any():
            out.append(("warn", f"{_n(int(bad_xy.sum()), 'row has', 'rows have')} missing or unreadable coordinates."))
        if off.any():
            msg = f"{_n(int(off.sum()), 'row is', 'rows are')} off the island (MTM 8)"
            n_sw = int(swapped.sum())
            out.append(("warn", msg + (f"; {n_sw:,} {'looks' if n_sw == 1 else 'look'} like X and Y swapped."
                                       if n_sw else ".")))
        if not off.any() and not bad_xy.any():
            out.append(("ok", "All coordinates are on the island (MTM 8)."))

    if has_depths:
        top = pd.to_numeric(df["depth_top_m"], errors="coerce")
        bot = pd.to_numeric(df["depth_bot_m"], errors="coerce")
        bad = (top < 0) | (bot <= top)
        if bad.any():
            out.append(("warn", f"{_n(int(bad.sum()), 'row has', 'rows have')} negative depth or bottom not below top."))
        if "hole_id" in df.columns:
            d = pd.DataFrame({"h": df["hole_id"], "t": top, "b": bot}).dropna().sort_values(["h", "t"])
            overlap = (d.groupby("h")["b"].shift() > d["t"] + 1e-6).sum()
            if overlap:
                out.append(("warn", f"{_n(int(overlap), 'sample or layer overlaps', 'samples or layers overlap')} the one above in the same hole."))
        if not bad.any():
            out.append(("ok", "Depths are consistent."))

    if "n_field" in df.columns:
        n = pd.to_numeric(df["n_field"], errors="coerce")
        if (n >= 999).any():
            out.append(("warn", f"{_n(int((n >= 999).sum()), 'N-value', 'N-values')} of 999 or more: code refusals in a refusal column, not as N = 999."))
        if "refusal" not in df.columns:
            out.append(("warn", "No refusal column: refusals cannot be told apart from N-values."))
        if n.isin([50, 100]).sum() > 0.05 * n.notna().sum() and n.notna().sum() >= 20:
            out.append(("warn", "Many N = 50 or 100: these may be refusals typed as numbers."))

    if "vs30_ms" in df.columns:
        v = pd.to_numeric(df["vs30_ms"], errors="coerce")
        outside = v.notna() & ((v < config.VS30_MIN) | (v > config.VS30_MAX))
        if outside.any():
            out.append(("warn", f"{_n(int(outside.sum()), 'Vs30 value', 'Vs30 values')} outside {config.VS30_MIN}-{config.VS30_MAX} m/s."))
        if "vs30_status" not in df.columns:
            out.append(("warn", "Vs30 given without vs30_status: say whether it is measured or estimated."))

    if "year" in df.columns:
        y = pd.to_numeric(df["year"], errors="coerce")
        if (y < config.PRE_MODERN_YEAR).any():
            out.append(("warn", f"{_n(int((y < config.PRE_MODERN_YEAR).sum()), 'row', 'rows')} dated before 1960 (flag pre-1960)."))
    return out
