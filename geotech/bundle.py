"""Build the download zip for a selection."""
import io
import zipfile

import pandas as pd

from .storage import now_iso

MANIFEST_FIELDS = ["id", "title", "data_type", "file_name", "file_size", "sha256", "source_org",
                   "original_reference", "work_year", "data_era", "value_status", "licence",
                   "access_level", "uploaded_by", "uploaded_at", "x_mtm8", "y_mtm8", "lon", "lat",
                   "footprint_wkt_mtm8", "status", "reviewed_by", "reviewed_at", "notes"]


def readme(area_label, data_label, n_bh, n_s, n_files):
    return f"""Montréal geotechnical data: download
Created {now_iso()} for: {area_label}
Archive source: {data_label}

Contents
  boreholes.csv     {n_bh} boreholes. x_mtm8 / y_mtm8 are MTM zone 8 (EPSG:32188), metres.
                    lon / lat (WGS84) are a convenience copy for web maps.
  spt_samples.csv   {n_s} SPT samples. n_field is the raw field N, never corrected here.
                    refusal = True marks a refusal: a censored value, not N = 999.
  manifest.csv      one row per contributed file: metadata card, licence, check status.
  files/            the contributed files, unchanged.

Read before use
  - Vs30 and NBCC site class in the archive are ESTIMATED from a lithology lookup
    (Rosset et al. 2023), not measured. See vs30_status.
  - Holes with data_era = pre-1960: SPT N read about half of modern values
    (era multiplier about 1.7). Raw n_field is kept as recorded.
  - Contributed files carry their own value_status (measured / derived / interpolated / estimated).
"""


def build_zip(boreholes, samples, uploads, get_bytes, area_label, data_label):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", readme(area_label, data_label, len(boreholes), len(samples), len(uploads)))
        if len(boreholes):
            z.writestr("boreholes.csv", boreholes.to_csv(index=False))
        if len(samples):
            z.writestr("spt_samples.csv", samples.to_csv(index=False))
        if uploads:
            man = pd.DataFrame(uploads)
            z.writestr("manifest.csv", man.reindex(columns=MANIFEST_FIELDS).to_csv(index=False))
            for r in uploads:
                z.writestr(f"files/{r['id']}_{r['file_name']}", get_bytes(r))
    return buf.getvalue()
