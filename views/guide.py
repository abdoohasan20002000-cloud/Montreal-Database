"""User guide: how to use each page, and how to read the data."""
import html

import streamlit as st

from geotech import config, ui

ui.hero("User guide", "How to use each page, and how to read the values the atlas shows.",
        chips=["Measured, derived, estimated and interpolated values are labelled",
               "Coordinates in <b>MTM 8</b> · EPSG:32188"])

how, read, src = st.tabs(["Getting started", "Reading the data", "Sources and rebuilding"])

STEPS = [
    ("Map and 3D", "views/explore.py", [
        "Choose <b>2D map</b> or <b>3D relief</b> at the top. In 3D, drag to pan, right-drag to tilt, scroll to zoom.",
        "Pick the area: the <b>whole island</b>, a <b>circle</b> (click the map to place it) or <b>draw</b> a "
        "rectangle or polygon.",
        "Turn layers on and off: boreholes, measured Vs30 sites, contributed files. Change the basemap with the "
        "layer button at the top right of the map.",
        "The panel on the right counts what is in the area. <b>Prepare zip</b> bundles the tables (MTM 8 with a "
        "WGS84 copy), the original files, a manifest and a README with the caveats."]),
    ("Insights", "views/insights.py", [
        "Headline numbers for the whole island, then Vs against depth for each soil with the published sand and "
        "clay fits drawn for comparison.",
        "Measured Vs30 by area, the NBCC class mix, and a 3D map of where measurements are dense or thin.",
        "The data-quality table lists what still needs checking and what each flag means."]),
    ("Site report", "views/site_report.py", [
        "Click the map or type coordinates (latitude and longitude, or MTM 8). Set the search radius.",
        "You get the nearest measured Vs30, an <b>interpolated</b> Vs30 at the point, the NBCC class that follows "
        "from it, the Vs profiles nearby and a plain-language summary.",
        "Download the report as Markdown or CSV. Every value carries its status, method, source and date. "
        "For design, measure Vs30 at the site."]),
    ("Contribute data", "views/contribute.py", [
        "Place the file on the map (click, draw, type coordinates or give an existing hole ID).",
        "Describe it: source, year of the work, whether values are measured, derived or estimated, licence.",
        "Automatic checks run at once; a curator reviews the report before the file appears on the map."]),
]
with how:
    for i, (title, target, tips) in enumerate(STEPS, 1):
        with st.container(border=True):
            left, right = st.columns([5, 1], vertical_alignment="center")
            left.markdown(f'<div class="gx-step"><div class="num">{i}</div><div><div class="gx-card-title">'
                          f'{html.escape(title)}</div><ul style="margin:6px 0 0 0;padding-left:18px;color:#c3cfda">'
                          + "".join(f"<li>{t}</li>" for t in tips) + "</ul></div></div>", unsafe_allow_html=True)
            right.page_link(target, label="Open", icon=":material/arrow_forward:", width="stretch")

with read:
    a, b = st.columns([1.5, 1], gap="large")
    with a:
        st.markdown("""
**Borehole archive.** 6,961 boreholes and 39,285 SPT samples, 1927–2009, compiled from the
City of Montréal, the Ministère des Transports (MTQ) and the Ministère de l'Environnement (MELCC).

**Coordinates.** Stored in MTM zone 8 (EPSG:32188), metres. The map shows a WGS84 copy;
downloads carry both, with MTM 8 as the reference.

**Measured, derived, estimated.**
- `n_field` is the raw SPT N as recorded in the field. The app never corrects it.
- Refusals are flagged in `refusal`. They are censored values (the true N is higher), not N = 999.
- Vs30 and NBCC site class in the archive are **estimated** from a lithology lookup
  (Rosset et al. 2023), not measured. `vs30_status` says so on every row.
- Every contributed file states whether its values are measured, derived, interpolated or estimated.

**Measured Vs (Rosset compilation).** 159 sites, 149 of them with a Vs30 from field seismic surveys
(landstreamer/MASW lines, downhole tests), and 2,273 Vs-depth rows. These are the only **measured** Vs values here. Downhole Vs is measured;
MASW and minivib profiles are derived (inversion, travel times), and `vs_status` says which. Sites far off the
island (Rougemont area and two others) are in the files but hidden until you tick the box. Profiles with no
location in the source (for example MM05, MM11 to MM20, MP11) are only in the whole-island selection.

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

**Rebuilding the data.** Every table is made by a script, not by hand:
- `python scripts/prepare_rosset_vs.py` rebuilds `data/vs30_sites.csv`, `data/vs_profiles.csv` and
  `data/vs_regressions.csv` from the Rosset workbook, and writes the checks to `data/vs_prepare_report.txt`.
- `python scripts/make_hero_art.py` redraws the contour art in the page headers (decoration only).
- `python scripts/make_demo_data.py` makes the synthetic DEMO boreholes for trying the app.
""")
