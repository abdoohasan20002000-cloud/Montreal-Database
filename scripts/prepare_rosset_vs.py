"""Turn the Rosset measured-Vs workbook into the app's Vs tables.

Reads data/source/ROSSET_Vs_ALL_CONSOLIDATED.xlsx and writes:
  data/vs30_sites.csv      one row per site with a location (06b_SITE_VS30_2021), in MTM 8 and WGS84
  data/vs_profiles.csv     Vs-depth profiles (downhole, MASW, minivib), located where the site is known
  data/vs_regressions.csv  Vs-depth regression coefficients (sheet 04), with the equation form
  data/vs_prepare_report.txt   what was checked and what was left out

Usage: python scripts/prepare_rosset_vs.py
"""
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from geotech import config, geo  # noqa: E402

SRC = ROOT / "data" / "source" / "ROSSET_Vs_ALL_CONSOLIDATED.xlsx"
OUT = ROOT / "data"
SOURCE = "Rosset et al. measured-Vs compilation (ROSSET_Vs_ALL_CONSOLIDATED.xlsx)"
TODAY = date.today().isoformat()
report = []


def note(msg):
    report.append(msg)
    print(msg)


x = pd.ExcelFile(SRC)

# ---- sites ------------------------------------------------------------------------
s = pd.read_excel(x, "06b_SITE_VS30_2021", header=2)
s = s.rename(columns={"HV_name": "site_id", "Type": "survey_type", "Vs30": "vs30_ms", "f0": "f0_hz",
                      "Latitude": "lat", "Longitude": "lon", "Elevation": "elevation_m",
                      "LOCATION": "area", "PREFIX": "prefix", "Line_Name": "line_name"})
if not s["site_id"].is_unique:
    note(f"WARNING: duplicate site IDs: {s['site_id'][s['site_id'].duplicated()].tolist()}")
s["x_mtm8"], s["y_mtm8"] = geo.wgs84_to_mtm8(s["lon"].to_numpy(float), s["lat"].to_numpy(float))
s[["x_mtm8", "y_mtm8"]] = s[["x_mtm8", "y_mtm8"]].round(1)
s["on_island"] = [geo.on_island(a, b) for a, b in zip(s["x_mtm8"], s["y_mtm8"])]
s["vs30_status"] = s["vs30_ms"].map(lambda v: "measured (field seismic survey)" if pd.notna(v) else "no value")
s["qa_flags"] = ""
s.loc[~s["on_island"], "qa_flags"] += "off the island;"
s.loc[s["vs30_ms"].isna(), "qa_flags"] += "no Vs30;"
# The other Rougemont-area sites lie far east of the island; one with island coordinates is kept as given but flagged.
s.loc[s["area"].astype(str).str.startswith("Rougemont") & s["on_island"], "qa_flags"] += "Rougemont area but on the island;"
out_range = s["vs30_ms"].notna() & ~s["vs30_ms"].between(config.VS30_MIN, config.VS30_MAX)
s.loc[out_range, "qa_flags"] += f"Vs30 outside {config.VS30_MIN}-{config.VS30_MAX};"
s["source"] = SOURCE
s["method"] = "Vs30 from field seismic survey as compiled in source sheet 06b_SITE_VS30_2021 (Data_Vs_all_2021.csv); " \
              "coordinates are WGS84 as given, converted to MTM 8 here"
s["processed_on"] = TODAY
cols = ["site_id", "survey_type", "area", "prefix", "vs30_ms", "vs30_status", "f0_hz", "elevation_m",
        "lat", "lon", "x_mtm8", "y_mtm8", "on_island", "qa_flags", "source", "method", "processed_on"]
s[cols].to_csv(OUT / "vs30_sites.csv", index=False)
note(f"vs30_sites.csv: {len(s)} sites; {int(s['on_island'].sum())} on the island ({geo.island_shape_mtm8()[1]}), "
     f"{int((~s['on_island']).sum())} off it "
     f"({', '.join(sorted(s.loc[~s['on_island'], 'area'].dropna().unique()))}); "
     f"{int(s['vs30_ms'].isna().sum())} without a Vs30 value; {int(out_range.sum())} outside {config.VS30_MIN}-{config.VS30_MAX} m/s.")

# ---- profiles ---------------------------------------------------------------------
pts = pd.read_excel(x, "01_Vs_POINTS", header=2)
pts = pts.rename(columns={"SITE": "site_id", "Z": "depth_m", "VS": "vs_ms", "VS_MINUS_2SIG": "vs_lower_ms",
                          "VS_PLUS_2SIG": "vs_upper_ms", "TYPE": "soil_type", "METHOD": "method_raw",
                          "DUPLICATE_OF_EARLIER_SHEET": "duplicate_of_earlier_sheet"})
pts["profile_source"] = "01_Vs_POINTS"
pts["soil_type"] = pts["soil_type"].astype(str).str.lower()

masw = pd.read_excel(x, "03_MASW_PROFILES", header=2).rename(columns={
    "SITE": "site_id", "Z": "depth_m", "VS": "vs_ms", "VS_LOWER": "vs_lower_ms", "VS_UPPER": "vs_upper_ms"})
masw["method_raw"] = "MASW"
masw["profile_source"] = "03_MASW_PROFILES"
masw["duplicate_of_earlier_sheet"] = False

mini = pd.read_excel(x, "02_MINIVIB_PROFILES", header=2).rename(columns={
    "LINE": "site_id", "Z": "depth_m", "VS_INTERVAL": "vs_ms"})
mini["method_raw"] = "Minivib"
mini["profile_source"] = "02_MINIVIB_PROFILES"
mini["duplicate_of_earlier_sheet"] = False

keep = ["site_id", "method_raw", "soil_type", "depth_m", "vs_ms", "vs_lower_ms", "vs_upper_ms",
        "duplicate_of_earlier_sheet", "profile_source", "SOURCE_FILE", "SOURCE_SHEET"]
pr = pd.concat([d.reindex(columns=keep) for d in (pts, masw, mini)], ignore_index=True)
pr["site_id"] = pr["site_id"].astype(str).str.strip()
pr["method"] = pr["method_raw"].fillna("not stated")
pr["vs_status"] = pr["method"].map({
    "Downhole": "measured (downhole seismic)",
    "MASW": "derived (inversion of surface-wave dispersion)",
    "Minivib": "derived (interval velocity from two-way travel times)",
    "not stated": "method not stated in the source (do not call measured)"})
pr = pr.drop(columns="method_raw")

# Locate profiles: site base name (MM05-1 -> MM05) against the site table; line profiles against the
# centroid of their line's sites. Anything else stays unlocated rather than guessed.
LINE_GROUPS = {"Girouard": "Gi", "Jardin Bot": "BG", "ND East": "ND", "ND West": "ND", "Est NDE": "ND",
               "Ouest NDE": "ND", "Girouard_N": "Gi", "Girouard_S": "Gi", "Jardin Botanique": "BG"}
site_ll = s.set_index("site_id")[["lat", "lon"]]


def locate(site):
    base = re.sub(r"-\d+$", "", site)
    base = {"MM7": "MM07", "Rougemont": "ROU", "ROU": "ROU"}.get(base, base)
    if base in site_ll.index:
        return site_ll.at[base, "lat"], site_ll.at[base, "lon"], f"site {base}"
    if site in LINE_GROUPS:
        g = s[(s["prefix"] == LINE_GROUPS[site]) & s["on_island"]]
        return g["lat"].mean(), g["lon"].mean(), f"centroid of {len(g)} {LINE_GROUPS[site]} sites on the line"
    return None, None, "no location in the source"


loc = {k: locate(k) for k in pr["site_id"].unique()}
pr["lat"] = pr["site_id"].map(lambda k: loc[k][0])
pr["lon"] = pr["site_id"].map(lambda k: loc[k][1])
pr["location_basis"] = pr["site_id"].map(lambda k: loc[k][2])
ok = pr["lat"].notna()
xs, ys = geo.wgs84_to_mtm8(pr.loc[ok, "lon"].to_numpy(float), pr.loc[ok, "lat"].to_numpy(float))
pr.loc[ok, "x_mtm8"], pr.loc[ok, "y_mtm8"] = xs.round(1), ys.round(1)
pr["on_island"] = [bool(geo.on_island(a, b)) if pd.notna(a) else None for a, b in zip(pr["x_mtm8"], pr["y_mtm8"])]

pr["qa_flags"] = ""
bad_depth = pr["depth_m"].isna() | (pr["depth_m"] < 0)
pr.loc[bad_depth, "qa_flags"] += "bad depth;"
pr.loc[pr["vs_ms"].isna(), "qa_flags"] += "no Vs;"
vs_out = pr["vs_ms"].notna() & ~pr["vs_ms"].between(50, 3500)
pr.loc[vs_out, "qa_flags"] += "Vs outside 50-3500 m/s;"
pr.loc[pr["duplicate_of_earlier_sheet"].fillna(False).astype(bool), "qa_flags"] += "duplicate of an earlier sheet;"
pr.loc[pr["lat"].isna(), "qa_flags"] += "unlocated;"
pr.loc[pr["method"] == "not stated", "qa_flags"] += "method blank in source;"
pr["source"] = SOURCE
pr["processed_on"] = TODAY
pr.to_csv(OUT / "vs_profiles.csv", index=False)

uniq = pr[~pr["duplicate_of_earlier_sheet"].fillna(False).astype(bool)]
note(f"vs_profiles.csv: {len(pr)} rows ({len(uniq)} after dropping rows repeated between sheets), "
     f"{pr['site_id'].nunique()} sites/lines, methods {pr['method'].value_counts().to_dict()}.")
note(f"  located: {int(ok.sum())} rows; unlocated: {int((~ok).sum())} rows from sites "
     f"{sorted(pr.loc[~ok, 'site_id'].unique())}")
note(f"  method blank in source: {int((pr['method'] == 'not stated').sum())} rows (site MM09-2); labelled 'not stated', not guessed.")
note(f"  Vs outside 50-3500 m/s: {int(vs_out.sum())}; bad depth: {int(bad_depth.sum())} (LM04-1, depth -0.04 m, kept and flagged).")
note("Not used: UTM27 coordinates on sheet 06_SITE_METADATA (source notes LM04-1 easting 275,585 is impossible "
     "for UTM 18; only 9 sites have them). Location comes from the WGS84 coordinates on sheet 06b instead.")
# ---- regressions ------------------------------------------------------------------
rg = pd.read_excel(x, "04_REGRESSION_FITS", header=2).rename(columns=str.lower)
rg = rg.rename(columns={"source_sheet": "fit", "value": "value"})
# Sheet 04 names the TableCurve model but not always its equation. For reg_sand and reg_clay the form
# Vs = a + b * z^c reproduces the published Table 3 relations and fits the clay points (R² 0.45) far better
# than Vs = a * z^c, so it is recorded here as INFERRED. Minivib fits state y = a + b * x^0.5 where given.
FORMS = {"reg_sand": "Vs = a + b*z^c (inferred)", "reg_clay": "Vs = a + b*z^c (inferred)",
         "power_NDE": "Vs = a + b*z^0.5 (stated)", "power_NDW": "Vs = a + b*z^0.5 (stated)"}
rg["equation"] = rg["fit"].map(FORMS).fillna("not stated in the source")
rg["soil_or_line"] = rg["fit"].map({"reg_sand": "sand", "reg_clay": "clay"}).fillna(rg["fit"])
rg["source"] = SOURCE
rg["processed_on"] = TODAY
rg.to_csv(OUT / "vs_regressions.csv", index=False)
note(f"vs_regressions.csv: {rg['fit'].nunique()} fits; equation form inferred for reg_sand and reg_clay "
     "(Vs = a + b*z^c), stated for power_NDE/NDW, not stated for the other minivib fits.")

(OUT / "vs_prepare_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
