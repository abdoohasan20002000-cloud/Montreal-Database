"""Montréal geotechnical data: explore the map, select an area, download what is there."""
import folium
import pandas as pd
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import mapping
from streamlit_folium import st_folium

from geotech import bundle, data, geo, ui
from geotech.config import PRE_MODERN_YEAR

st.set_page_config(page_title="Montréal geotechnical data", page_icon="🗺️", layout="wide")
st.title("Montréal geotechnical data")
st.caption("Boreholes, SPT samples and contributed files on the Island of Montréal. "
           "Pick a spot, draw an area, or take the whole island, then download what is there.")

# ---- data -------------------------------------------------------------------
with st.sidebar:
    st.header("Data")
    demo = st.toggle("Use demo data", value=False, help="Synthetic points for trying the app.")
bh, samples, label = ui.load_archive(demo)
ui.archive_banner(label)
store = ui.get_store()
uploads = store.list(status="approved")

# ---- filters and selection --------------------------------------------------
with st.sidebar:
    st.header("Filters")
    eras = st.multiselect("Era", ["pre-1960", "1960 and later", "undated"],
                          default=["pre-1960", "1960 and later", "undated"],
                          help=f"Before {PRE_MODERN_YEAR}, SPT N read about half of modern values.")
    if not bh.empty and "source" in bh.columns:
        sources = sorted(bh["source"].dropna().astype(str).unique())
        pick_src = st.multiselect("Source", sources, default=sources)
    else:
        pick_src = None
    colour_by = st.radio("Colour boreholes by", ["Era", "Site class (estimated)"], horizontal=True)

    st.header("Selection")
    mode = st.radio("Area", ["Whole island", "Point and radius", "Draw an area"])
    radius = st.slider("Radius (m)", 100, 5000, 500, 100, disabled=mode != "Point and radius")
    if mode == "Point and radius":
        st.caption("Click the map to place the point.")
    elif mode == "Draw an area":
        st.caption("Use the rectangle or polygon tool on the map (top left).")

if not bh.empty:
    bh = bh[bh["data_era"].isin(eras)]
    if pick_src is not None:
        bh = bh[bh["source"].astype(str).isin(pick_src)]

# ---- map ----------------------------------------------------------------------
state = st.session_state
area = data.selection_from_inputs(mode, state.get("drawing"), state.get("click"), radius)

m = folium.Map(location=[45.55, -73.70], zoom_start=11, control_scale=True)
if not bh.empty:
    def colour(row):
        if colour_by == "Era":
            return ui.ERA_COLOURS.get(row["data_era"], "#7f7f7f")
        return ui.SITE_CLASS_COLOURS.get(str(row.get("site_class", ""))[:1], "#bdbdbd")

    pts = bh.assign(_c=bh.apply(colour, axis=1))
    tip_cols = [c for c in ["hole_id", "year", "source", "data_era", "vs30_ms", "site_class"] if c in pts.columns]
    features = []
    for rec in pts[tip_cols + ["lon", "lat", "_c"]].to_dict("records"):
        props = {c: (None if pd.isna(rec[c]) else str(rec[c])) for c in tip_cols}
        props["_c"] = rec["_c"]
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [rec["lon"], rec["lat"]]},
                         "properties": props})
    folium.GeoJson(
        {"type": "FeatureCollection", "features": features}, name="Boreholes",
        marker=folium.CircleMarker(radius=3, weight=0, fill=True, fill_opacity=0.8),
        style_function=lambda f: {"fillColor": f["properties"]["_c"], "color": f["properties"]["_c"]},
        tooltip=folium.GeoJsonTooltip(fields=tip_cols),
    ).add_to(m)

for r in uploads:
    folium.Marker([r["lat"], r["lon"]], tooltip=f"{r['data_type']}: {r['title']}",
                  icon=folium.Icon(color="purple", icon="file", prefix="fa")).add_to(m)

if area not in (None, "incomplete"):
    folium.GeoJson(mapping(geo.shp_transform_to_wgs84(area)), name="Selection",
                   style_function=lambda f: {"color": "#1f6f8b", "weight": 2, "fillOpacity": 0.05}).add_to(m)
if mode == "Draw an area":
    Draw(export=False, draw_options={"polyline": False, "circlemarker": False, "marker": False,
                                     "circle": False}).add_to(m)

legend = ("Orange: pre-1960 · Green: 1960 and later · Grey: undated" if colour_by == "Era"
          else "Site class (estimated): A dark blue → E orange, F red · Grey: none")
st.caption(f"{legend} · Purple pins: contributed files")
out = st_folium(m, height=560, use_container_width=True, returned_objects=["last_clicked", "last_active_drawing"])
if out:
    changed = False
    if mode == "Point and radius" and out.get("last_clicked") and out["last_clicked"] != state.get("click"):
        state["click"] = out["last_clicked"]
        changed = True
    if mode == "Draw an area" and out.get("last_active_drawing") and out["last_active_drawing"] != state.get("drawing"):
        state["drawing"] = out["last_active_drawing"]
        changed = True
    if changed:
        st.rerun()

# ---- results ------------------------------------------------------------------
if area == "incomplete":
    st.info("Place a point or draw an area on the map to make a selection.")
    st.stop()

sel_bh = data.points_in(bh, area)
sel_s = samples[samples["hole_id"].isin(sel_bh["hole_id"])] if not samples.empty and not sel_bh.empty else samples.iloc[0:0]
sel_up = data.uploads_in(uploads, area)
area_label = "whole island" if area is None else (
    f"{radius} m around {state['click']['lat']:.5f}, {state['click']['lng']:.5f}" if mode == "Point and radius"
    else "drawn area (" + f"{area.area / 1e6:.2f} km²)")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Boreholes", f"{len(sel_bh):,}")
c2.metric("SPT samples", f"{len(sel_s):,}")
c3.metric("Pre-1960 boreholes", f"{int((sel_bh['data_era'] == 'pre-1960').sum()) if not sel_bh.empty else 0:,}")
c4.metric("Contributed files", f"{len(sel_up):,}")

t1, t2, t3, t4 = st.tabs(["Boreholes", "SPT samples", "Files", "Download"])
with t1:
    if sel_bh.empty:
        st.write("No boreholes in this selection.")
    else:
        st.caption("Vs30 and site class are estimates from a lithology lookup (Rosset et al. 2023), not measurements.")
        st.dataframe(sel_bh, width="stretch", hide_index=True)
with t2:
    if sel_s.empty:
        st.write("No SPT samples in this selection.")
    else:
        st.caption("n_field is the raw field N. Refusals are flagged in `refusal` (censored values), never N = 999.")
        if "refusal" in sel_s.columns:
            st.write(f"{int(sel_s['refusal'].sum()):,} of {len(sel_s):,} samples are refusals.")
        st.dataframe(sel_s, width="stretch", hide_index=True)
with t3:
    if not sel_up:
        st.write("No contributed files in this selection yet. Add one on the Upload page.")
    for r in sel_up:
        with st.expander(f"{r['data_type']} · {r['title']} ({r.get('work_year') or 'undated'})"):
            st.write(f"**Source:** {r.get('source_org')} · {r.get('original_reference') or ''}  \n"
                     f"**Values:** {r.get('value_status')} · **Licence:** {r.get('licence')}  \n"
                     f"**File:** {r['file_name']} ({r.get('file_size', 0) / 1e6:.2f} MB) · uploaded {r.get('uploaded_at')}")
            if r.get("data_era") == "pre-1960":
                st.warning("Pre-1960 work: SPT N read about half of modern values.")
            st.download_button("Download this file", store.get_bytes(r), file_name=r["file_name"], key=f"dl_{r['id']}")
with t4:
    st.write(f"One zip for **{area_label}**: boreholes and SPT samples as CSV (MTM 8, with a WGS84 copy), "
             "contributed files, a manifest of their metadata, and a README with the caveats.")
    zip_key = (area_label, label, len(sel_bh), len(sel_up))
    if st.button("Prepare zip"):
        with st.spinner("Building zip…"):
            state["zip"] = (zip_key, bundle.build_zip(sel_bh, sel_s, sel_up, store.get_bytes, area_label, label))
    if state.get("zip") and state["zip"][0] == zip_key:
        st.download_button("Download zip", state["zip"][1], file_name="montreal_geotech_selection.zip",
                           mime="application/zip")
