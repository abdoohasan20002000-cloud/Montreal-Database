"""Home: what the atlas is, what is loaded, and where to start."""
import html

import streamlit as st

from geotech import config, storage, ui

bh, samples, label = ui.load_archive(False)
sites, prof = ui.load_vs()
store = ui.get_store()
approved, pending = store.list(status="approved"), store.list(status="pending")

ui.hero("Montréal Geotechnical Atlas",
        "One place for what is known about the ground under the island: the borehole archive with its SPT "
        "samples, measured shear-wave velocities and their depth profiles, and files that engineers contribute. "
        "Explore it on a 2D or 3D map, read the trends, get a report for any location and download what you need.",
        eyebrow="Island of Montréal · Subsurface intelligence", large=True, byline=ui.credit_byline())

# ---- headline numbers ----------------------------------------------------------------------
with_vs = sites.dropna(subset=["vs30_ms"])
on_island = int(with_vs["on_island"].sum())
ui.kpis([
    (f"{len(bh):,}" if not bh.empty else "not loaded", "Archive boreholes",
     f"{int((bh['data_era'] == 'pre-1960').sum()):,} pre-1960" if not bh.empty else "6,961 expected, 1927–2009",
     ui.ERA_COLOURS["1960 and later"]),
    (f"{len(samples):,}" if not samples.empty else "not loaded", "SPT samples",
     "raw N kept, refusals flagged" if not samples.empty else "39,285 expected", ui.ERA_COLOURS["pre-1960"]),
    (f"{len(with_vs):,}", "Sites with measured Vs30", f"{on_island} on the island, {len(with_vs) - on_island} off it", ui.VS_COLOUR),
    (f"{len(prof):,}", "Vs-depth readings", f"{prof['site_id'].nunique()} profiles and seismic lines",
     ui.SITE_CLASS_COLOURS["D"]),
    (f"{len(approved):,}", "Contributed files", f"{len(pending)} waiting for review", ui.UPLOAD_COLOUR),
], cols=5)
st.write("")

# ---- where to start -------------------------------------------------------------------------
ui.panel_title("Where to start")
CARDS = [
    ("map", "Map and 3D", "Boreholes, measured Vs30 sites and files on a dark map or a 3D relief of the island. "
     "Pick an area and download it as one zip.", "views/explore.py"),
    ("insights", "Insights", "How stiff the ground is, how velocity grows with depth in each soil, where data is "
     "dense or thin, and what still needs checking.", "views/insights.py"),
    ("location_searching", "Site report", "Pick any location for the nearest measurements, an interpolated Vs30, "
     "its NBCC class and a summary you can download.", "views/site_report.py"),
    ("upload_file", "Contribute data", "Add a log, lab sheet, report or GIS file. It is checked automatically and "
     "appears once a curator approves it.", "views/contribute.py"),
]
for col, (icon, title, text, target) in zip(st.columns(len(CARDS), gap="medium"), CARDS):
    with col, st.container(border=True, key=f"gxcard_{icon}"):
        st.markdown(f'<div class="gx-card-icon">{icon}</div><div class="gx-card-title">{html.escape(title)}</div>'
                    f'<div class="gx-card-text">{html.escape(text)}</div>', unsafe_allow_html=True)
        st.page_link(target, label="Open", icon=":material/arrow_forward:", width="stretch")
st.write("")

# ---- what is loaded, and how values are labelled --------------------------------------------
a, b = st.columns([1.1, 1], gap="large")
with a:
    ui.panel_title("What is loaded")
    items = [
        (True, "Measured Vs (Rosset compilation)",
         f"{len(sites)} sites, {len(prof):,} Vs-depth readings and the published sand and clay regressions."),
        (not bh.empty, "Borehole archive",
         f"{len(bh):,} boreholes and {len(samples):,} SPT samples." if not bh.empty else
         "Not loaded yet. Add data/boreholes.csv and data/spt_samples.csv to the repository to show it."),
        (not isinstance(store, storage.LocalStore), "Storage for contributed files",
         "Permanent shared storage (Supabase)." if not isinstance(store, storage.LocalStore) else
         "Temporary: files are lost when the app restarts until Supabase settings are added."),
        (config.ISLAND_OUTLINE.exists(), "Island outline",
         "Precise outline used for the on-island checks." if config.ISLAND_OUTLINE.exists() else
         "A rough box is used for the on-island checks until data/island_outline.geojson is added."),
    ]
    st.markdown("".join(
        f'<div class="gx-status"><div class="i {"ok" if ok else "todo"}">{"✓" if ok else "!"}</div>'
        f'<div><div class="t">{html.escape(t)}</div><div class="d">{html.escape(d)}</div></div></div>'
        for ok, t, d in items), unsafe_allow_html=True)
with b:
    ui.panel_title("How every value is labelled")
    ui.status_legend()
    ui.panel_title("NBCC site classes on the maps")
    ui.class_tags("Class colours run dark (rock) to light (soft soil, where shaking is amplified most).")

st.markdown(f'<div class="gx-note" style="margin-top:18px">Coordinates are stored in MTM zone 8 (EPSG:32188); the '
            f'maps use a WGS84 copy. {html.escape(config.DATA_CREDIT)}.</div>', unsafe_allow_html=True)
