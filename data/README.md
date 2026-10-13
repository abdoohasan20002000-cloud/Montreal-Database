# Data folder

The app reads the archive from this folder. These files are small enough to keep in git.

| File | Required columns | Optional columns |
| --- | --- | --- |
| `boreholes.csv` | `hole_id`, `x_mtm8`, `y_mtm8` (EPSG:32188, metres) | `year`, `source`, `data_era`, `depth_m`, `bedrock_depth_m`, `bedrock_position`, `vs30_ms`, `vs30_status`, `site_class`, `main_unit`, `region`, `qa_flags` |
| `spt_samples.csv` | `hole_id`, `depth_top_m`, `depth_bot_m`, `n_field` | `sample_no`, `refusal`, `uscs`, `qa_flags` |
| `island_outline.geojson` | island outline (WGS84), e.g. `regions_montreal_island.geojson` from the portal package | |

Other spellings (`HOLE_ID`, `N_FIELD`, `X`, `Y`, …) are accepted; add more in `geotech/config.py`.

The `borehole_archive` layers made by `prepare_archive.py` (portal package v2) fit these columns.

Rules the app relies on:
- `n_field` is the raw field N. Do not replace it with a corrected value.
- `refusal` is True/False (or 1/0). Never encode a refusal as N = 999. Blank means not a refusal.
- `vs30_status` must say "estimated" for the archive (lithology lookup, Rosset et al. 2023).
- If `data_era` is missing it is computed from `year` (before 1960 = `pre-1960`).

`demo/` holds synthetic points made by `scripts/make_demo_data.py`, only for trying the app.
They are labelled DEMO everywhere and are not real data.
