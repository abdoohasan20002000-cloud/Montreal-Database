# Montréal Database

A shared store for the ground data collected on the Island of Montréal: boreholes and SPT, CPT, lab tests, shear-wave
velocity and other geophysics, groundwater, monitoring, ground deformation, earthquake records, environmental
sampling, reports, maps and photos, from any year. Anyone can find it by type, region and year, see it on a map,
download it with its source, and contribute what they have.

## Pages

- **Home**: what is loaded, how data gets in, and where to start.
- **Data catalogue**: every dataset, built in or contributed, with its type, regions, years, source, method,
  licence and access. Filter by data type, region (19 boroughs and 15 linked cities), years (all, since 2001, or a
  custom range) and value status; open a row for its details and downloads (cut to the chosen regions), or show it
  on the map.
- **Map and 3D**: a 2D map or a 3D relief view. Pick the whole island, one or more regions, a point and radius, or a
  drawn area; see counts and tables; download one zip (tables in MTM 8 with a WGS84 copy, the Public contributed
  files, a manifest and a README).
- **Insights**: headline numbers, Vs with depth by soil against the Rosset sand and clay fits, measured Vs30 by
  survey area or by region, the NBCC class mix, data density and open data-quality flags. A sidebar filter limits
  every chart to chosen regions.
- **Site report**: pick a point; it gives the region, the measured Vs30 sites nearby, an inverse-distance Vs30
  labelled INTERPOLATED, the NBCC class derived from it, the Vs profiles nearby and a plain-language summary. Every
  value carries status, method, source and date; download as Markdown or CSV.
- **Contribute data**: place the data on the map (click, line, area, coordinates in MTM 8 or lat/long, or an
  existing hole ID), describe it once (title, one of 17 data types, years collected, source, value status, licence,
  who may download it, notes), and add one or more files of any format, up to 50 MB each (the most a free Supabase
  project accepts). Checks run at once on every file: duplicates, location on the island, file opens, and for tables
  (CSV, Excel .xlsx or .xls; the first 200,000 rows) hole IDs, coordinates, depths, refusals coded as 999, Vs30 range
  and pre-1960 dates. A submission is all or nothing.
- **Curate**: a curator reads each file's check report and approves or rejects it. Only approved data is shown.
- **User guide**: getting started, sharing and contributing, how to read the data, sources and rebuilding.

## Regions

Every point gets its region (borough or linked city) from its MTM 8 coordinates and the City's administrative
limits, *Limites administratives de l'agglomération de Montréal* (Ville de Montréal open data, CC BY 4.0). Points
outside all 34 regions are labelled "Off the island". A contributed line or area takes every region it touches;
island-wide datasets match every region.

The limits are in `data/regions.geojson`. They are downloaded, simplified and dated by `scripts/fetch_regions.py`,
which the **Fetch region boundaries** GitHub Action runs (Actions tab → Run workflow); the run report is in
`data/regions_report.txt`.

## Where things are stored

| What | Where | Why |
| --- | --- | --- |
| Code, built-in tables, region limits | this GitHub repo (`data/`) | small, versioned, rebuilt by scripts |
| Contributed files and their descriptions | Supabase: private Storage bucket + `uploads` table | GitHub is not made for many large uploads, and Streamlit Cloud erases its own disk on every restart |

Without Supabase settings the app keeps uploads in a local folder: fine for trying it, lost on restart.

Files marked "Registered users" or "Restricted" are listed in the catalogue and the zip manifest but not served
until sign-in is added; a curator can share them on request.

## Built-in data

- `data/vs30_sites.csv`, `data/vs_profiles.csv`, `data/vs_regressions.csv`: measured Vs from the Rosset workbook.
  Rebuild with `python scripts/prepare_rosset_vs.py`; the checks are in `data/vs_prepare_report.txt`.
- `data/boreholes.csv`, `data/spt_samples.csv`: the borehole archive (6,961 boreholes, 39,285 SPT samples,
  1927–2009), not added yet. Columns are in `data/README.md`.

## Run it on your computer

```bash
pip install -r requirements.txt
python scripts/make_demo_data.py      # optional synthetic DEMO points
streamlit run Map.py
```

## Put it online (Streamlit Community Cloud, free)

1. Add the archive CSVs (above) and push.
2. Create a Supabase project (free tier: 1 GB of files). In its SQL editor run `supabase/schema.sql`. In Storage
   create a **private** bucket named `uploads`. If you set it up before regions were added, run the schema file
   again: its `alter table ... add column if not exists` lines add the new columns.
3. Go to https://share.streamlit.io, sign in with GitHub, **Create app**, pick this repo, branch `main`, main file
   `Map.py`.
4. In the app's **Settings → Secrets**, paste the contents of `.streamlit/secrets.toml.example` with your Supabase
   URL, service-role key and a curator password.

## Tests

```bash
pip install pytest && pytest -q
```

## Project rules the code follows

- Coordinates stored in MTM zone 8 (EPSG:32188); WGS84 only for the web maps and as a copy in downloads.
- Vs30 and site class in the archive are estimates (lithology lookup, Rosset et al. 2023), labelled as such.
- Raw `n_field` is never altered; pre-1960 holes are flagged; refusals are a flag, never N = 999.
- Measured, derived, interpolated and estimated values are labelled and kept apart.
- Every contribution records source, value status, years of work, region, uploader, upload date, reviewer and
  review date.
