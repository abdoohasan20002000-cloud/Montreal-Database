"""Build the download zip for a selection."""
import io
import zipfile

import pandas as pd

from .storage import now_iso

MANIFEST_FIELDS = ["id", "submission_id", "title", "data_type", "file_name", "file_size", "sha256", "source_org",
                   "original_reference", "work_year", "work_year_end", "data_era", "value_status", "licence",
                   "access_level", "uploaded_by", "uploaded_at", "x_mtm8", "y_mtm8", "lon", "lat", "region",
                   "footprint_wkt_mtm8", "status", "reviewed_by", "reviewed_at", "notes", "in_zip"]


def readme(area_label, data_label, n_bh, n_s, n_files, n_vs=0, n_prof=0, n_vs_value=None):
    return f"""Montréal geotechnical data: download
Created {now_iso()} for: {area_label}
Archive source: {data_label}

Contents
  boreholes.csv     {n_bh} boreholes. x_mtm8 / y_mtm8 are MTM zone 8 (EPSG:32188), metres.
                    lon / lat (WGS84) are a convenience copy for web maps.
  spt_samples.csv   {n_s} SPT samples. n_field is the raw field N, never corrected here.
                    refusal = True marks a refusal: a censored value, not N = 999.
  vs30_sites.csv    {n_vs} sites, {n_vs if n_vs_value is None else n_vs_value} of them with a Vs30 from a seismic survey at
                    the site (Rosset compilation). MEASURED, unlike the borehole Vs30 below; sites with a blank
                    vs30_ms have no value in the source. Columns method/source/processed_on say how each was made.
  vs_profiles.csv   {n_prof} Vs-depth rows. vs_status says measured (downhole) or derived (MASW inversion,
                    minivib travel times). Rows with no location are left out of area selections.
  manifest.csv      one row per contributed file: metadata card, licence, check status.
                    in_zip = False marks files whose access level is not Public (listed, not included).
  files/            the contributed files, unchanged.

  region            in every table: the borough or linked city that contains the point, DERIVED from the
                    coordinates and the City of Montréal administrative limits (open data, CC BY 4.0).
                    "Off the island" = outside the agglomeration; blank = no coordinates.

Read before use
  - Vs30 and NBCC site class in the archive are ESTIMATED from a lithology lookup
    (Rosset et al. 2023), not measured. See vs30_status.
  - Holes with data_era = pre-1960: SPT N read about half of modern values
    (era multiplier about 1.7). Raw n_field is kept as recorded.
  - Contributed files carry their own value_status (measured / derived / interpolated / estimated).
"""


def build_zip(boreholes, samples, uploads, get_bytes, area_label, data_label, vs_sites=None, vs_prof=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        n_vs = 0 if vs_sites is None else len(vs_sites)
        n_prof = 0 if vs_prof is None else len(vs_prof)
        n_value = 0 if vs_sites is None or "vs30_ms" not in vs_sites else int(vs_sites["vs30_ms"].notna().sum())
        z.writestr("README.txt", readme(area_label, data_label, len(boreholes), len(samples), len(uploads), n_vs, n_prof,
                                        n_value))
        if n_vs:
            z.writestr("vs30_sites.csv", vs_sites.to_csv(index=False))
        if n_prof:
            z.writestr("vs_profiles.csv", vs_prof.to_csv(index=False))
        if len(boreholes):
            z.writestr("boreholes.csv", boreholes.to_csv(index=False))
        if len(samples):
            z.writestr("spt_samples.csv", samples.to_csv(index=False))
        if uploads:
            public = [(r.get("access_level") or "Public") == "Public" for r in uploads]
            man = pd.DataFrame(uploads).assign(in_zip=public)
            z.writestr("manifest.csv", man.reindex(columns=MANIFEST_FIELDS).to_csv(index=False))
            for r, ok in zip(uploads, public):
                if ok:
                    z.writestr(f"files/{r['id']}_{r['file_name']}", get_bytes(r))
    return buf.getvalue()
