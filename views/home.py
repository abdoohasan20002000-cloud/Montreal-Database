"""Home: what the atlas is, what it holds, how data gets in, and where to start."""
import html

import streamlit as st

from geotech import catalogue, config, geo, insight, storage, ui

bh, samples, label = ui.load_archive(False)
sites, prof = ui.load_vs()
store = ui.get_store()
approved, pending = store.list(status="approved"), store.list(status="pending")
cat = catalogue.table(catalogue.builtin(sites, prof, insight.load_regressions(), bh, samples)
                      + catalogue.contributed(approved))

ui.hero("Montréal Geotechnical Atlas",
        "A shared store for the ground data collected in Montréal: boreholes and SPT, CPT, lab tests, shear-wave "
        "velocity and other geophysics, groundwater, monitoring, reports and maps, from any year. Find it by type, "
        "borough or city and year, see it on a 2D or 3D map, get a report for any location, download it with its "
        "source, and add what you have.",
        eyebrow="Island of Montréal · Shared subsurface data", large=True, byline=ui.credit_byline())

# ---- headline numbers ----------------------------------------------------------------------
with_vs = sites.dropna(subset=["vs30_ms"])
on_island = int(with_vs["on_island"].sum())
cover = catalogue.points_by_region(sites, prof, bh, approved)
names = geo.region_names()
with_data = len(set(cover["region"]) & set(names))
ui.kpis([
    (f"{len(cat)}", "Datasets in the catalogue",
     f"{int((cat['origin'] == 'Built in').sum())} built in, {int((cat['origin'] == 'Contributed').sum())} contributed",
     ui.ACCENT),
    (f"{with_data} of {len(names)}", "Regions with data", "boroughs and linked cities", ui.CATEGORICAL[0]),
    (f"{len(with_vs):,}", "Sites with measured Vs30", f"{on_island} on the island, {len(with_vs) - on_island} off it",
     ui.VS_COLOUR),
    (f"{len(bh):,}" if not bh.empty else "not loaded", "Archive boreholes",
     f"{int((bh['data_era'] == 'pre-1960').sum()):,} pre-1960" if not bh.empty else "6,961 expected, 1927–2009",
     ui.ERA_COLOURS["1960 and later"]),
    (f"{len(pending)}", "Waiting for review", "submitted, not yet approved", ui.UPLOAD_COLOUR),
], cols=5)
st.write("")

# ---- how data gets in ---------------------------------------------------------------------------
ui.panel_title("How data gets in")
ui.flow([
    ("Anyone uploads", "Any file and format, placed on the map and described once: type, years, source, licence."),
    ("Automatic checks", "Location on the island, duplicates, file opens; for tables also IDs, depths, refusals "
                         "and Vs30 range."),
    ("Curator review", "A curator reads the check report and approves or rejects. Every decision is recorded."),
    ("Shared", "Approved data appears in the catalogue, on the maps and in downloads, with its source and licence."),
])
st.write("")

# ---- where to start -------------------------------------------------------------------------
ui.panel_title("Where to start")
CARDS = [
    ("dataset", "Data catalogue", "Every dataset with its type, region, years, source and licence. Filter, read "
     "the details, download.", "views/catalogue.py"),
    ("map", "Map and 3D", "Pick a borough, a circle or a drawn area on a 2D map or a 3D relief. Download it as one "
     "zip.", "views/explore.py"),
    ("insights", "Insights", "How stiff the ground is, how velocity grows with depth in each soil, and where data "
     "is dense or thin.", "views/insights.py"),
    ("location_searching", "Site report", "Any location: the nearest measurements, an interpolated Vs30, its NBCC "
     "class and a summary.", "views/site_report.py"),
    ("upload_file", "Contribute data", "Add what you have, from any year. It is checked at once and shown after a "
     "curator approves it.", "views/contribute.py"),
]
for col, (icon, title, text, target) in zip(st.columns(len(CARDS), gap="small"), CARDS):
    with col, st.container(border=True, key=f"gxcard_{icon}"):
        st.markdown(f'<div class="gx-card-icon">{icon}</div><div class="gx-card-title">{html.escape(title)}</div>'
                    f'<div class="gx-card-text">{html.escape(text)}</div>', unsafe_allow_html=True)
        st.page_link(target, label="Open", icon=":material/arrow_forward:", width="stretch")
st.write("")

# ---- what is loaded, and how values are labelled --------------------------------------------
a, b = st.columns([1.1, 1], gap="large")
with a:
    ui.panel_title("What is loaded")
    gj = geo.regions_geojson()
    fetched = str(gj["features"][0]["properties"].get("fetched_on", ""))[:10] if gj else ""
    ui.status_rows([
        (True, "Measured Vs (Rosset compilation)",
         f"{len(sites)} sites, {len(prof):,} Vs-depth readings and the published sand and clay regressions."),
        (gj is not None, "Borough and linked-city limits",
         f"{len(names)} regions from City of Montréal open data (CC BY 4.0), downloaded {fetched}." if gj else
         "Missing: run the Fetch regions action (scripts/fetch_regions.py) to add data/regions.geojson."),
        (not bh.empty, "Borehole archive",
         f"{len(bh):,} boreholes and {len(samples):,} SPT samples." if not bh.empty else
         "Not loaded yet. Add data/boreholes.csv and data/spt_samples.csv to the repository to show it."),
        (not isinstance(store, storage.LocalStore), "Storage for contributed data",
         "Permanent shared storage (Supabase)." if not isinstance(store, storage.LocalStore) else
         "Temporary: uploads are lost when the app restarts until Supabase settings are added."),
    ])
with b:
    ui.panel_title("How every value is labelled")
    ui.status_legend()
    ui.panel_title("NBCC site classes on the maps")
    ui.class_tags("Class colours run light (rock) to dark (soft soil, where shaking is amplified most).")

st.markdown(f'<div class="gx-note" style="margin-top:18px">Coordinates are stored in MTM zone 8 (EPSG:32188); the '
            f'maps use a WGS84 copy. Regions come from each point\'s coordinates and the City\'s administrative limits. '
            f'{html.escape(config.DATA_CREDIT)}.</div>', unsafe_allow_html=True)
