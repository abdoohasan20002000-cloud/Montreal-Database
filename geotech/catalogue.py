"""The data catalogue: one row per dataset in the atlas, whether it ships with the app or was contributed.

Built-in datasets are described from the loaded tables (counts, regions, years), so the catalogue cannot drift from
the data. Contributed files are grouped by submission: one card, one or more files.
"""
import pandas as pd

from . import config, data, geo

ISLAND_WIDE = "Island-wide"


def _regions(df):
    if df is None or df.empty or "region" not in df.columns:
        return []
    return sorted(r for r in df["region"].dropna().astype(str).unique() if r)


def _years(y0, y1, note=""):
    if y0 is None and y1 is None:
        return note or "not stated"
    return f"{y0}" if y0 == y1 else f"{y0}–{y1}"


def _entry(**kw):
    kw.setdefault("files", [])
    kw["years"] = _years(kw.get("year_from"), kw.get("year_to"), kw.pop("years_note", ""))
    return kw


def builtin(sites, prof, reg, bh, samples):
    """Datasets that ship with the app, described from the loaded tables."""
    out = []
    with_vs = sites.dropna(subset=["vs30_ms"]) if not sites.empty else sites
    out.append(_entry(
        key="vs30_sites", title="Measured Vs30 sites", data_type="Shear-wave velocity (Vs, Vs30)",
        origin="Built in", source="Rosset et al. compilation", year_from=None, year_to=None,
        years_note="not stated", regions=_regions(sites),
        records=f"{len(sites)} sites, {len(with_vs)} with a Vs30", value_status="Measured",
        licence="Not stated (ask the source)", access="Public", available=not sites.empty,
        description="Vs30 from a seismic survey at each site (mostly landstreamer and MASW lines, some downhole "
                    "tests), as compiled in the source, with the resonance frequency f0 where it is given. Measured "
                    "here means surveyed at the site, unlike the archive's Vs30 estimated from lithology. Survey "
                    "years are not in the source; the compilation sheet is dated 2021.",
        method="Sheet 06b_SITE_VS30_2021 of ROSSET_Vs_ALL_CONSOLIDATED.xlsx, rebuilt by scripts/prepare_rosset_vs.py"))
    out.append(_entry(
        key="vs_profiles", title="Vs-depth profiles", data_type="Shear-wave velocity (Vs, Vs30)",
        origin="Built in", source="Rosset et al. compilation", year_from=None, year_to=None,
        years_note="not stated", regions=_regions(prof),
        records=(f"{len(prof):,} readings at {prof['site_id'].nunique()} sites and lines" if not prof.empty else "none"),
        value_status="Mixed", licence="Not stated (ask the source)", access="Public", available=not prof.empty,
        description="Shear-wave velocity against depth. Downhole readings are measured; MASW and minivib profiles are "
                    "derived (inversion, travel times). The vs_status column says which.",
        method="Sheets 01 to 03 and R01 to R61 of the Rosset workbook, duplicates between sheets removed"))
    out.append(_entry(
        key="vs_regressions", title="Vs-depth regressions by soil", data_type="Shear-wave velocity (Vs, Vs30)",
        origin="Built in", source="Rosset et al. (2023)", year_from=None, year_to=None,
        years_note="not stated", regions=[], value_status="Derived", licence="Not stated (ask the source)",
        records=(f"{reg['fit'].nunique()} fits: 2 published (sand, clay), {reg['fit'].nunique() - 2} minivib line fits"
                 if not reg.empty else "none"), access="Public", available=not reg.empty,
        description="The published Rosset fits for sand and clay (Vs = a + b·z^c; the form is inferred, the workbook "
                    "does not state it) and minivib line fits (form stated for 2, not stated for 4). They describe "
                    "the whole island rather than one place.",
        method="Sheet 04_REGRESSION_FITS of the Rosset workbook; sand and clay coefficients match the published "
               "Table 3, the line fits are not checked against a publication"))
    gj = geo.regions_geojson()
    if gj:
        props = [f["properties"] for f in gj["features"]]
        fetched = str(props[0].get("fetched_on", ""))[:10]
        year = int(fetched[:4]) if fetched[:4].isdigit() else None
        kinds = pd.Series([p.get("kind", "") for p in props]).value_counts()
        out.append(_entry(
            key="regions", title="Borough and linked-city limits", data_type="Map / GIS layer",
            origin="Built in", source="Ville de Montréal open data", year_from=year, year_to=year,
            regions=[], records=f"{len(props)} regions ({kinds.get('Borough', 0)} boroughs, "
                                f"{kinds.get('City', 0)} linked cities)",
            value_status="Not applicable (no numerical values)", licence="CC BY 4.0", access="Public", available=True,
            description="Administrative limits of the Montréal agglomeration. The atlas uses them to give every "
                        "point its region and to filter by region.",
            method=f"Downloaded {fetched} by scripts/fetch_regions.py (GitHub Action), simplified 2 m in MTM 8",
            url=props[0].get("source_url", "")))
    if bh.empty:
        out.append(_entry(
            key="archive", title="Borehole archive with SPT samples", data_type="Borehole log",
            origin="Built in", source="City of Montréal, MTQ and MELCC", year_from=1927, year_to=2009, regions=[],
            records="not loaded yet (6,961 boreholes and 39,285 SPT samples expected)",
            value_status="Mixed", licence="Not stated (ask the source)", access="Public", available=False,
            description="Boreholes with SPT N-values. Raw N is kept; pre-1960 holes are flagged; archive Vs30 and "
                        "site class are estimated from lithology (Rosset et al. 2023), not measured.",
            method="Waiting for data/boreholes.csv and data/spt_samples.csv"))
    else:
        yrs = pd.to_numeric(bh.get("year"), errors="coerce").dropna() if "year" in bh.columns else pd.Series(dtype=float)
        y0, y1 = (int(yrs.min()), int(yrs.max())) if len(yrs) else (None, None)
        out.append(_entry(
            key="boreholes", title="Borehole archive", data_type="Borehole log",
            origin="Built in", source="City of Montréal, MTQ and MELCC", year_from=y0, year_to=y1,
            regions=_regions(bh), records=f"{len(bh):,} boreholes, {int((bh['data_era'] == 'pre-1960').sum()):,} "
                                         "pre-1960",
            value_status="Mixed", licence="Not stated (ask the source)", access="Public", available=True,
            description="Borehole locations, depths and bedrock. Archive Vs30 and site class are ESTIMATED from "
                        "lithology (Rosset et al. 2023), not measured.",
            method="data/boreholes.csv"))
        if not samples.empty:
            out.append(_entry(
                key="samples", title="SPT samples", data_type="SPT (standard penetration test)",
                origin="Built in", source="City of Montréal, MTQ and MELCC", year_from=y0, year_to=y1,
                regions=_regions(bh), records=f"{len(samples):,} samples",
                value_status="Measured", licence="Not stated (ask the source)", access="Public", available=True,
                description="Raw field N (n_field), never corrected. Refusals are flagged as censored values, "
                            "never N = 999. Pre-1960 N reads about half of modern values.",
                method="data/spt_samples.csv"))
    return out


def contributed(uploads):
    """Approved uploads, one entry per submission (files sent together share one description)."""
    groups = {}
    for r in uploads:
        groups.setdefault(r.get("submission_id") or r["id"], []).append(r)
    out = []
    for sid, recs in groups.items():
        r = recs[0]
        years = [data.upload_years(x) for x in recs]
        y0 = min((a for a, _ in years if a is not None), default=None)
        y1 = max((b for _, b in years if b is not None), default=None)
        regions = sorted({g for x in recs for g in data.upload_regions(x)})
        size = sum(x.get("file_size") or 0 for x in recs) / 1e6
        ref = f" · {r['original_reference']}" if r.get("original_reference") else ""
        out.append(_entry(
            key=f"up_{sid}", title=r["title"], data_type=r["data_type"], origin="Contributed",
            source=f"{r.get('source_org') or ''}{ref}", year_from=y0, year_to=y1, regions=regions,
            records=f"{len(recs)} file{'s' if len(recs) > 1 else ''}, "
                    + (f"{size:.1f} MB" if size >= 0.1 else f"{size * 1000:.0f} kB" if size >= 0.001 else "under 1 kB"),
            value_status=r.get("value_status"),
            licence=r.get("licence"), access=r.get("access_level"), available=True,
            description=r.get("notes") or "",
            method=(f"Uploaded by {r.get('uploaded_by')} on {str(r.get('uploaded_at'))[:10]}"
                    + (f"; approved by {r['reviewed_by']} on {str(r.get('reviewed_at'))[:10]}" if r.get("reviewed_by")
                       else "")),
            files=recs))
    return out


def table(entries):
    df = pd.DataFrame(entries)
    if df.empty:
        return df
    df["where"] = df["regions"].map(_where)
    return df


def _where(regions):
    """Short text for the regions a dataset touches: one name, or a count (off-island points noted apart)."""
    if not regions:
        return ISLAND_WIDE
    inside = [r for r in regions if r != config.OFF_ISLAND]
    off = " + off the island" if len(inside) < len(regions) else ""
    if not inside:
        return config.OFF_ISLAND
    return (inside[0] if len(inside) == 1 else f"{len(inside)} regions") + off


def matches(df, types=(), regions=(), years=None, include_undated=True, statuses=(), text=""):
    """Boolean mask over a catalogue table. Island-wide entries match every region; a year range keeps entries
    whose years overlap it (undated ones only when include_undated)."""
    if df.empty:
        return pd.Series(dtype=bool)
    keep = pd.Series(True, index=df.index)
    if types:
        keep &= df["data_type"].isin(types)
    if statuses:
        keep &= df["value_status"].isin(statuses)
    if regions:
        sel = set(regions)
        keep &= df["regions"].map(lambda r: not r or bool(sel & set(r)))
    if years is not None:
        lo, hi = years
        def ok(row):
            a, b = row["year_from"], row["year_to"]
            a = None if a is None or pd.isna(a) else a
            b = None if b is None or pd.isna(b) else b
            if a is None and b is None:
                return include_undated
            return (a if a is not None else b) <= hi and (b if b is not None else a) >= lo
        keep &= df.apply(ok, axis=1)
    if text:
        t = text.lower()
        keep &= df[["title", "data_type", "source", "description", "method"]].fillna("").astype(str) \
            .apply(lambda c: c.str.lower().str.contains(t, regex=False)).any(axis=1)
    return keep


def points_by_region(sites, prof, bh, uploads):
    """Count of located things per region and kind, for the coverage chart."""
    parts = []
    if not bh.empty:
        parts.append(bh["region"].value_counts().rename_axis("region").reset_index(name="n").assign(kind="Boreholes"))
    if not sites.empty:
        parts.append(sites["region"].value_counts().rename_axis("region").reset_index(name="n")
                     .assign(kind="Measured Vs30 sites"))
    if not prof.empty:
        loc = prof.dropna(subset=["x_mtm8"]).drop_duplicates("site_id")
        parts.append(loc["region"].value_counts().rename_axis("region").reset_index(name="n")
                     .assign(kind="Vs profile locations"))
    if uploads:
        regs = pd.Series([g for r in uploads for g in data.upload_regions(r)], dtype=object)
        if len(regs):
            parts.append(regs.value_counts().rename_axis("region").reset_index(name="n").assign(kind="Contributed files"))
    if not parts:
        return pd.DataFrame(columns=["region", "n", "kind"])
    out = pd.concat(parts, ignore_index=True)
    return out[out["region"].astype(str) != ""]


def region_options():
    """Region names for filters: boroughs and cities, then the off-island label."""
    names = geo.region_names()
    return names + [config.OFF_ISLAND] if names else []
