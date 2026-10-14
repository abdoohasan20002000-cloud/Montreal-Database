"""User guide: how to use each page, and how to read the data."""
import html

import pandas as pd
import streamlit as st

from geotech import config, ui

ui.hero("User guide", "How to use each page, how to share and add data, and how to read the values the atlas shows.",
        chips=["Measured, derived, estimated and interpolated values are labelled",
               "Coordinates in <b>MTM 8</b> · EPSG:32188"])

how, share, read, src = st.tabs(["Getting started", "Sharing and contributing", "Reading the data",
                                 "Sources and rebuilding"])

STEPS = [
    ("Data catalogue", "views/catalogue.py", [
        "Every dataset in the atlas, built in or contributed, one row each: type, <b>where</b> (the boroughs and "
        "cities it touches), years, records, value status, source and licence.",
        "Filter by data type, <b>region</b>, <b>years</b> (all, <b>since 2001</b>, or a custom range) and value "
        "status, or search by words. Island-wide datasets match every region.",
        "Click a row for its details and downloads (cut to the chosen regions), or <b>Show on the map</b>."]),
    ("Map and 3D", "views/explore.py", [
        "Choose <b>2D map</b> or <b>3D relief</b> at the top. In 3D, drag to pan, right-drag to tilt, scroll to zoom.",
        "Pick the area: the <b>whole island</b>, one or more <b>regions</b> (boroughs or linked cities), a "
        "<b>circle</b> (click the map to place it) or <b>draw</b> a rectangle or polygon.",
        "Turn layers on and off: boreholes, measured Vs30 sites, contributed files. Change the basemap with the "
        "layer button at the top right of the map.",
        "The panel on the right counts what is in the area. <b>Prepare zip</b> bundles the tables (MTM 8 with a "
        "WGS84 copy), the original files, a manifest and a README with the caveats."]),
    ("Insights", "views/insights.py", [
        "Headline numbers for the whole island or the regions picked in the sidebar, then Vs against depth for "
        "each soil with the published sand and clay fits drawn for comparison.",
        "Measured Vs30 by survey area or by region, the NBCC class mix, and a 3D map of where measurements are "
        "dense or thin.",
        "The data-quality table lists what still needs checking and what each flag means."]),
    ("Site report", "views/site_report.py", [
        "Click the map or type coordinates (latitude and longitude, or MTM 8). Set the search radius.",
        "You get the region, the nearest measured Vs30, an <b>interpolated</b> Vs30 at the point, the NBCC class "
        "that follows from it, the Vs profiles nearby and a plain-language summary.",
        "Download the report as Markdown or CSV. Every value carries its status, method, source and date. "
        "For design, measure Vs30 at the site."]),
    ("Contribute data", "views/contribute.py", [
        "Place it on the map: click a point, draw a line or an area, type coordinates or give an existing hole ID. "
        "The region is found from the location.",
        "Describe it once: data type, the years it was collected, source, whether values are measured, derived, "
        "interpolated or estimated, licence and who may download it. Then add one or more files of any format.",
        "Automatic checks run at once; a curator reviews the report before the data appears in the catalogue."]),
]
with how:
    for i, (title, target, tips) in enumerate(STEPS, 1):
        with st.container(border=True):
            st.markdown(f'<div class="gx-step"><div class="num">{i}</div><div><div class="gx-card-title">'
                        f'{html.escape(title)}</div><ul>'
                        + "".join(f"<li>{t}</li>" for t in tips) + "</ul></div></div>", unsafe_allow_html=True)
            st.page_link(target, label=f"Open {title}", icon=":material/arrow_forward:")

with share:
    a, b = st.columns([1.5, 1], gap="large")
    with a:
        st.markdown("""
**Anyone can look.** The atlas is a web page: send the link and it opens in any browser, no account needed.
Every download carries the data's source, method, licence and a README with the caveats.

**Anyone can contribute.** Open *Contribute data*, place the data on the map, describe it once and add the files.
Any format is accepted (PDF, Excel, CSV, GIS files, images, raw instrument files). Tables are read and checked
against the project rules; other files are stored unchanged.

**A curator approves.** Nothing appears until a curator has read the check report. The approval, its date and
the curator's name are stored with the data.

**Who may download.** Each contribution says who may download it:
- *Public*: listed and downloadable by anyone with the link.
- *Registered users* and *Restricted*: listed in the catalogue so people know it exists, but not served by the app
  until sign-in is set up; a curator shares it on request.

**Licences.** Contributors pick a licence (CC BY 4.0, Québec open government licence, restricted, or another
stated in the notes). The catalogue shows it on every entry.

**Larger datasets or code.** Scripted datasets (like the measured Vs tables and the region limits) live in the
project's GitHub repository, are rebuilt by scripts, and can be proposed there as a pull request.
""")
    with b:
        ui.panel_title("Data types the atlas accepts")
        st.markdown("".join(f'<span class="gx-chip" style="display:inline-block;margin:0 6px 6px 0">'
                            f'{html.escape(t)}</span>' for t in config.DATA_TYPES), unsafe_allow_html=True)

bh, samples, _ = ui.load_archive(False)
vs_sites, vs_prof = ui.load_vs()
if bh.empty:
    archive_text = ("Expected: 6,961 boreholes and 39,285 SPT samples, 1927–2009 (not loaded in this deployment yet), "
                    "compiled from")
else:
    yrs = pd.to_numeric(bh.get("year"), errors="coerce").dropna()
    archive_text = (f"{len(bh):,} boreholes and {len(samples):,} SPT samples"
                    + (f", {int(yrs.min())}–{int(yrs.max())}" if len(yrs) else "") + ", compiled from")
status = vs_prof["vs_status"].fillna("").str.split(" ").str[0].value_counts() if not vs_prof.empty else pd.Series()
n_meas, n_der = int(status.get("measured", 0)), int(status.get("derived", 0))
n_other = len(vs_prof) - n_meas - n_der
other_text = f", plus {n_other} with no method stated" if n_other else ""
n_with_vs30 = int(vs_sites["vs30_ms"].notna().sum()) if not vs_sites.empty else 0
with read:
    a, b = st.columns([1.5, 1], gap="large")
    with a:
        st.markdown(f"""
**Borehole archive.** {archive_text} the
City of Montréal, the Ministère des Transports (MTQ) and the Ministère de l'Environnement (MELCC).

**Coordinates.** Stored in MTM zone 8 (EPSG:32188), metres. The map shows a WGS84 copy;
downloads carry both, with MTM 8 as the reference.

**Measured, derived, estimated.**
- `n_field` is the raw SPT N as recorded in the field. The app never corrects it.
- Refusals are flagged in `refusal`. They are censored values (the true N is higher), not N = 999.
- Vs30 and NBCC site class in the archive are **estimated** from a lithology lookup
  (Rosset et al. 2023), not measured. `vs30_status` says so on every row.
- Every contributed file states whether its values are measured, derived, interpolated or estimated.

**Measured Vs (Rosset compilation).** {len(vs_sites)} sites, {n_with_vs30} of them with
a Vs30 from a seismic survey at the site (mostly landstreamer and MASW lines, some downhole tests). Unlike the
archive's Vs30, these come from field tests. The {len(vs_prof):,} Vs-depth rows are {n_meas:,} **measured**
(downhole) and {n_der:,} **derived** (MASW inversion, minivib travel times){other_text}; `vs_status` says which. Sites outside the
agglomeration (the LM, PL and VM lines in Laval and on the South Shore, and the Rougemont area) are in the files
but hidden until you tick the box. Profiles with no location in the source (for example MM05, MM11 to MM20, MP11)
are only in the whole-island selection.

**Regions.** Each point's region (one of 19 boroughs or 15 linked cities) is **derived** from its coordinates
and the City of Montréal's administrative limits (open data, CC BY 4.0). Points outside them all are
"Off the island". Contributed data takes every region its footprint touches.

**Pre-1960 data.** Before 1960, SPT N-values read about half of modern ones (era multiplier about 1.7).
These holes are marked `data_era = pre-1960` and shown in orange on the map. Their raw N is kept.

**Interpolated values.** The site report's Vs30 at a point is a distance-weighted average of the nearest measured
sites. It ignores the geology between them and is labelled INTERPOLATED wherever it appears.

**Checks on every upload.** Duplicate file, location on the island, file opens; for tables also unique
hole IDs, coordinates on the island (and swapped X/Y), depth and layer consistency, refusals coded as 999,
Vs30 outside 100–3000 m/s, and pre-1960 dates. A curator reviews the report before the file goes live.

**Provenance.** Each contributed file records its source, original reference, year of the work,
who uploaded it and when, and who approved it and when.
""")
    with b:
        ui.panel_title("Value labels")
        ui.status_legend()
        ui.panel_title("NBCC site classes")
        ui.class_tags("A > 1500 m/s · B 760–1500 · C 360–760 · D 180–360 · E < 180 (Vs30).")

with src:
    st.markdown(f"""
**Sources.** {html.escape(config.DATA_CREDIT)}. Terrain in the 3D view and the header art: AWS Terrain Tiles
(SRTM and other public elevation models). Basemaps: © OpenStreetMap contributors, © CARTO, Esri imagery,
OpenTopoMap.

**Region limits.** "Limites administratives de l'agglomération de Montréal" (arrondissements et villes liées),
Ville de Montréal open data portal, CC BY 4.0. A GitHub Action runs `scripts/fetch_regions.py` to download them,
simplifies them by 2 m and commits `data/regions.geojson` with the date and source; the island outline used for
the on-island checks is their union.

**Rebuilding the data.** Every table is made by a script, not by hand:
- `python scripts/prepare_rosset_vs.py` rebuilds `data/vs30_sites.csv`, `data/vs_profiles.csv` and
  `data/vs_regressions.csv` from the Rosset workbook, and writes the checks to `data/vs_prepare_report.txt`.
- `python scripts/make_hero_art.py` redraws the contour art in the page headers (decoration only).
- `python scripts/make_demo_data.py` makes the synthetic DEMO boreholes for trying the app.
""")
