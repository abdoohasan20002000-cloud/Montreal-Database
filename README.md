# Montréal geotechnical data portal

A Streamlit app for the Island of Montréal borehole archive (6,961 boreholes, 39,285 SPT samples,
1927–2009) and for files that contributors add.

- **Explore**: a 2D map or a 3D relief view. Boreholes coloured by era or (estimated) site class, contributed files as pins.
  Pick the whole island, a point and radius, or draw an area; see counts and tables; download one zip
  (boreholes and SPT samples as CSV in MTM 8 with a WGS84 copy, the contributed files, a manifest, a README).
- **Measured Vs**: 159 measured-Vs30 sites (blue rings) and Vs profiles from the Rosset workbook, kept apart from the
  archive's estimated Vs30. Rebuild with `python scripts/prepare_rosset_vs.py`; the checks are in `data/vs_prepare_report.txt`.
- **Insights**: headline numbers, Vs with depth by soil against the Rosset sand and clay fits, measured Vs30 by area,
  NBCC class mix (derived from measured Vs30), a 3D map of where measurements are dense or thin, and open data-quality flags.
- **Site report**: pick a point (click, lat/long or MTM 8). It lists the measured Vs30 sites nearby, gives an
  inverse-distance estimate of Vs30 labelled INTERPOLATED, the NBCC class derived from it, the Vs profiles nearby and a
  plain-language summary. Every value carries status, method, source and date; download as Markdown or CSV.
- **Upload**: any file type, placed on the map by click, drawing, coordinates (MTM 8 or lat/long) or an
  existing hole ID, with a metadata card (source, year of work, measured/derived/estimated, licence).
  Checks run at once: duplicate file, on the island, file opens, and for tables hole IDs, coordinates,
  depths, refusals coded as 999, Vs30 range, pre-1960 dates.
- **Review**: a curator reads the check report and approves or rejects. Only approved files appear.
- **About the data**: how to read N-values, refusals, Vs30 and pre-1960 data.

## Where things are stored

| What | Where | Why |
| --- | --- | --- |
| Code and the borehole archive CSVs | this GitHub repo (`data/`) | small (a few MB), versioned |
| Contributed files and their metadata cards | Supabase: private Storage bucket + `uploads` table | GitHub is not made for many large binary uploads, and Streamlit Cloud erases its own disk on every restart |

Without Supabase settings the app keeps uploads in a local folder: fine for trying it, lost on restart.

## Run it on your computer

```bash
pip install -r requirements.txt
python scripts/make_demo_data.py      # optional synthetic DEMO points
streamlit run Map.py
```

## Put it online (Streamlit Community Cloud, free)

1. Add the archive: `data/boreholes.csv` and `data/spt_samples.csv` (columns in `data/README.md`),
   and `data/island_outline.geojson` for the precise island check. Commit and push.
2. Create a Supabase project (free tier: 1 GB of files). In its SQL editor run `supabase/schema.sql`.
   In Storage create a **private** bucket named `uploads`.
3. Go to https://share.streamlit.io, sign in with GitHub, **Create app**, pick this repo,
   branch `main`, main file `Map.py`.
4. In the app's **Settings → Secrets**, paste the contents of `.streamlit/secrets.toml.example`
   with your Supabase URL, service-role key and a curator password.

## Tests

```bash
pip install pytest && pytest -q
```

## Project rules the code follows

- Coordinates stored in MTM zone 8 (EPSG:32188); WGS84 only for the web map and as a copy in downloads.
- Vs30 and site class in the archive are estimates (lithology lookup, Rosset et al. 2023), labelled as such.
- Raw `n_field` is never altered; pre-1960 holes are flagged; refusals are a flag, never N = 999.
- Every contributed file records source, value status, year of work, uploader, upload date,
  reviewer and review date.
