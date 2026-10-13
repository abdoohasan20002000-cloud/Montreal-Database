"""Explore: the map, a selection, what is in it, and one download."""
import altair as alt
import folium
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import mapping
from streamlit_folium import st_folium

from geotech import bundle, config, data, geo, terrain, ui
from geotech.config import PRE_MODERN_YEAR

state = st.session_state

ui.hero("Map and 3D",
        "Pick a spot, draw an area or take the whole island to see the boreholes, SPT samples, measured shear-wave "
        "velocities and contributed files there, then download them in one zip.",
        chips=["Coordinates <b>MTM 8</b> · EPSG:32188", "Vs30 <b>measured</b> and <b>estimated</b> kept apart",
               "Raw <b>N<sub>field</sub></b> kept · pre-1960 flagged"])

# ---- data ---------------------------------------------------------------------
with st.sidebar:
    ui.sidebar_label("Filters")
    eras = st.multiselect("Borehole era", ["pre-1960", "1960 and later", "undated"],
                          default=["pre-1960", "1960 and later", "undated"],
                          help=f"Before {PRE_MODERN_YEAR}, SPT N read about half of modern values.")
    show_far = st.toggle("Include Vs sites off the island", value=False,
                         help="Rougemont area and two LM-line sites lie outside the island.")
    demo = st.toggle("Demo boreholes", value=False, help="400 synthetic points for trying the app. Not real data.")

bh, samples, label = ui.load_archive(demo)
ui.archive_banner(label)
store = ui.get_store()
uploads = store.list(status="approved")
vs_sites, vs_prof = ui.load_vs()

if not bh.empty:
    bh = bh[bh["data_era"].isin(eras)]
    if "source" in bh.columns:
        with st.sidebar:
            sources = sorted(bh["source"].dropna().astype(str).unique())
            pick_src = st.multiselect("Borehole source", sources, default=sources)
        bh = bh[bh["source"].astype(str).isin(pick_src)]
if not vs_sites.empty and not show_far:
    vs_sites = vs_sites[vs_sites["on_island"]]
    vs_prof = vs_prof[vs_prof["on_island"].astype(str).isin(["True", "nan", "None"])]
if not vs_sites.empty:
    vs_sites = vs_sites.assign(site_class_from_measured=vs_sites["vs30_ms"].map(ui.nbcc_class).fillna("–"))

# ---- controls -------------------------------------------------------------------
with st.container(border=True):
    c0, c1, c2, c3 = st.columns([0.9, 1.6, 1.3, 1.2], vertical_alignment="bottom")
    view = c0.segmented_control("View", ["2D map", "3D relief"], default="2D map", key="view") or "2D map"
    is_3d = view == "3D relief"
    mode = c1.segmented_control("Area", ["Whole island", "Circle", "Draw"],
                                default="Whole island", key="mode", disabled=is_3d) or "Whole island"
    radius = c2.slider("Radius (m)", 100, 5000, 500, 100, disabled=mode != "Circle" or is_3d)
    colour_by = c3.selectbox("Colour boreholes by", ["Era", "Site class (estimated)"])
    e1, e2, e3 = st.columns([1.9, 1.2, 1.3], vertical_alignment="bottom")
    layers = e1.pills("Layers", ["Boreholes", "Measured Vs30", "Files"], selection_mode="multi",
                      default=["Boreholes", "Measured Vs30", "Files"], key="layers")
    hint = {"Circle": "Click the map to place the centre of the circle.",
            "Draw": "Use the rectangle or polygon tool at the top left of the map.",
            "Whole island": "Everything on the island is selected."}[mode]
    if is_3d:
        hint = ("3D view: drag to pan, right-drag (or Ctrl-drag) to tilt and rotate, scroll to zoom. "
                "Switch to 2D map to change the selection.")
        surface = e2.selectbox("Surface", ["Dark map", "Satellite", "Relief only"], key="surface")
        exaggeration = e3.slider("Vertical exaggeration", 1, 15, 6,
                                 help="Montréal is fairly flat (Mont Royal is about 230 m), so relief is stretched "
                                      "to be visible. Symbol heights are not to scale.")
    st.markdown(f'<div class="gx-note">{hint}</div>', unsafe_allow_html=True)

area = data.selection_from_inputs({"Circle": "Point and radius", "Draw": "Draw an area"}.get(mode, mode),
                                  state.get("drawing"), state.get("click"), radius)

# ---- map ------------------------------------------------------------------------
def build_map():
    m = ui.base_map((45.55, -73.68), 11)
    b = config.ISLAND_BBOX
    m.fit_bounds([[b["lat_min"], b["lon_min"]], [b["lat_max"], b["lon_max"]]])

    if "Boreholes" in (layers or []) and not bh.empty:
        def colour(row):
            if colour_by == "Era":
                return ui.ERA_COLOURS.get(row["data_era"], ui.ERA_COLOURS["undated"])
            return ui.SITE_CLASS_COLOURS.get(str(row.get("site_class", ""))[:1], ui.ERA_COLOURS["undated"])
        tip_cols = [c for c in ["hole_id", "year", "source", "data_era", "vs30_ms", "site_class"] if c in bh.columns]
        feats = []
        for rec in bh.assign(_c=bh.apply(colour, axis=1))[tip_cols + ["lon", "lat", "_c"]].to_dict("records"):
            props = {c: (None if pd.isna(rec[c]) else str(rec[c])) for c in tip_cols}
            props["_c"] = rec["_c"]
            feats.append({"type": "Feature", "properties": props,
                          "geometry": {"type": "Point", "coordinates": [rec["lon"], rec["lat"]]}})
        folium.GeoJson({"type": "FeatureCollection", "features": feats}, name="Boreholes",
                       marker=folium.CircleMarker(radius=3, weight=0, fill=True, fill_opacity=0.9),
                       style_function=lambda f: {"fillColor": f["properties"]["_c"], "color": f["properties"]["_c"]},
                       tooltip=folium.GeoJsonTooltip(fields=tip_cols)).add_to(m)

    if "Measured Vs30" in (layers or []) and not vs_sites.empty:
        fg = folium.FeatureGroup(name="Measured Vs30 sites").add_to(m)
        for r in vs_sites.to_dict("records"):
            has = pd.notna(r["vs30_ms"])
            fill = ui.SITE_CLASS_COLOURS.get(r["site_class_from_measured"], ui.SURFACE) if has else ui.SURFACE
            tip = (f"<b>{r['site_id']}</b> · {r['area']}<br>Vs30 {r['vs30_ms']:.0f} m/s (measured), class "
                   f"{r['site_class_from_measured']}<br>{r['survey_type']}" if has
                   else f"<b>{r['site_id']}</b> · {r['area']}<br>no Vs30 value in the source")
            folium.CircleMarker([r["lat"], r["lon"]], radius=6, color="#ffffff" if has else ui.VS_COLOUR, weight=1.6,
                                fill=True, fill_color=fill, fill_opacity=0.95, tooltip=tip).add_to(fg)

    if "Files" in (layers or []) and uploads:
        fg = folium.FeatureGroup(name="Contributed files").add_to(m)
        for r in uploads:
            folium.Marker([r["lat"], r["lon"]], tooltip=f"{r['data_type']}: {r['title']}",
                          icon=ui.pin_icon(ui.UPLOAD_COLOUR)).add_to(fg)

    if area not in (None, "incomplete"):
        folium.GeoJson(mapping(geo.shp_transform_to_wgs84(area)), name="Selection",
                       style_function=lambda f: {"color": ui.ACCENT, "weight": 2.5, "dashArray": "6 4",
                                                 "fillColor": ui.ACCENT, "fillOpacity": 0.07}).add_to(m)
    if mode == "Draw":
        Draw(export=False, draw_options={"polyline": False, "circlemarker": False, "marker": False,
                                         "circle": False}).add_to(m)
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    m.get_root().html.add_child(folium.Element(legend_html()))
    return m


def legend_html():
    rows = []
    if colour_by == "Era":
        rows += [(c, k, "dot") for k, c in ui.ERA_COLOURS.items()]
    else:
        rows += [(c, f"Class {k} (estimated)", "dot") for k, c in ui.SITE_CLASS_COLOURS.items() if k != "F"]
    rows += [(ui.VS_COLOUR, "Measured Vs30 site", "ring"), (ui.UPLOAD_COLOUR, "Contributed file", "pin")]
    classes = "".join(f'<span title="Class {k}" style="display:inline-flex;align-items:center;justify-content:center;'
                      f'width:20px;height:15px;background:{c};color:{ui._text_on(c)};font-size:10px;font-weight:700;'
                      f'border-radius:3px">{k}</span>' for k, c in ui.SITE_CLASS_COLOURS.items() if k != "F")
    items = "".join(
        f'<div style="display:flex;align-items:center;gap:7px;margin:2px 0">'
        f'<span style="width:10px;height:10px;border-radius:50%;background:{c};'
        f'{"border:2px solid #fff;box-shadow:0 0 0 1px " + c + ";" if kind == "ring" else ""}'
        f'{"border-radius:50% 50% 50% 0;transform:rotate(-45deg);" if kind == "pin" else ""}"></span>{t}</div>'
        for c, t, kind in rows)
    return ('<div style="position:absolute;top:88px;left:10px;z-index:9999;background:rgba(10,21,32,0.92);'
            'padding:10px 13px;border-radius:12px;font:12px/1.4 Inter,system-ui,sans-serif;color:#e6edf3;'
            'border:1px solid #1c3a4d;box-shadow:0 8px 24px rgba(0,0,0,0.45)">'
            '<div style="font:500 10px/1.2 \'JetBrains Mono\',monospace;letter-spacing:.2em;color:#7d8fa0;'
            'text-transform:uppercase;margin-bottom:6px">Legend</div>'
            + items + '<div style="margin-top:6px;color:#a9b8c6">Vs30 site fill = NBCC class</div>'
            f'<div style="display:flex;gap:3px;margin-top:3px">{classes}</div></div>')


SURFACES = {
    "Dark map": "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    "Satellite": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "Relief only": None,
}


def rgb(hex_colour, alpha=235):
    h = hex_colour.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def build_3d():
    """Terrain from AWS Terrain Tiles, with data standing on it as columns."""
    ex = float(exaggeration)
    layers = [pdk.Layer(
        "TerrainLayer",
        elevation_decoder={"rScaler": 256 * ex, "gScaler": ex, "bScaler": ex / 256, "offset": -32768 * ex},
        elevation_data=terrain.TERRARIUM_URL,
        texture=SURFACES[surface], color=[64, 98, 124], max_zoom=14, strategy="no-overlap",
    )]

    def ground(df):
        return np.nan_to_num(terrain.elevation(df["lon"].to_numpy(), df["lat"].to_numpy()), nan=0.0) * ex

    if "Measured Vs30" in (layers_on or []) and not vs_sites.empty:
        v = vs_sites.dropna(subset=["vs30_ms"]).copy()
        v["z"] = ground(v)
        v["h"] = v["vs30_ms"] * 1.5
        v["fill"] = [rgb(ui.SITE_CLASS_COLOURS.get(c, ui.ERA_COLOURS["undated"])) for c in v["site_class_from_measured"]]
        v["tip"] = v.apply(lambda r: f"{r.site_id} · {r.area}<br/>Vs30 {r.vs30_ms:.0f} m/s (measured), "
                                     f"class {r.site_class_from_measured}<br/>{r.survey_type}", axis=1)
        layers.append(pdk.Layer("ColumnLayer", v[["lon", "lat", "z", "h", "fill", "tip"]],
                                get_position=["lon", "lat", "z"], get_elevation="h", elevation_scale=1,
                                radius=110, disk_resolution=16, extruded=True, get_fill_color="fill",
                                pickable=True, auto_highlight=True))
    if "Boreholes" in (layers_on or []) and not bh.empty:
        b = bh.copy()
        b["z"] = ground(b)
        b["fill"] = [rgb(ui.ERA_COLOURS.get(e, ui.ERA_COLOURS["undated"])) for e in b["data_era"]]
        b["tip"] = b["hole_id"].astype(str) + "<br/>" + b["data_era"].astype(str)
        layers.append(pdk.Layer("ColumnLayer", b[["lon", "lat", "z", "fill", "tip"]], get_position=["lon", "lat", "z"],
                                get_elevation=120, radius=28, disk_resolution=8, extruded=True,
                                get_fill_color="fill", pickable=True))
    if "Files" in (layers_on or []) and uploads:
        f = pd.DataFrame([{"lon": r["lon"], "lat": r["lat"], "tip": f"{r['data_type']}: {r['title']}"} for r in uploads])
        f["z"] = ground(f)
        layers.append(pdk.Layer("ColumnLayer", f, get_position=["lon", "lat", "z"], get_elevation=260, radius=60,
                                disk_resolution=4, extruded=True, get_fill_color=rgb(ui.UPLOAD_COLOUR),
                                pickable=True))
    if area not in (None, "incomplete"):
        ring = np.asarray(geo.shp_transform_to_wgs84(area).exterior.coords)
        zr = np.nan_to_num(terrain.elevation(ring[:, 0], ring[:, 1]), nan=0.0) * ex + 25
        layers.append(pdk.Layer("PathLayer", [{"path": [[x, y, z] for (x, y), z in zip(ring, zr)]}],
                                get_path="path", get_color=rgb(ui.ACCENT, 255), get_width=5, width_units="pixels"))
    view_state = pdk.ViewState(latitude=45.525, longitude=-73.64, zoom=10.8, pitch=60, bearing=-25)
    return pdk.Deck(layers=layers, initial_view_state=view_state, map_style=None,
                    tooltip={"html": "{tip}", "style": {"fontSize": "12px"}})


layers_on = layers
left, right = st.columns([2.35, 1], gap="medium")
out = None
with left:
    if is_3d:
        st.pydeck_chart(build_3d(), height=640, width="stretch")
        st.markdown('<div class="gx-note">Terrain: AWS Terrain Tiles (SRTM and other public DEMs), stretched '
                    f'{exaggeration}× vertically. Column height shows measured Vs30 (taller = stiffer ground); '
                    'columns stand on the terrain surface for display only.</div>', unsafe_allow_html=True)
    else:
        out = st_folium(build_map(), height=640, use_container_width=True,
                        returned_objects=["last_clicked", "last_active_drawing"], key="atlas_map")
if out:
    changed = False
    if mode == "Circle" and out.get("last_clicked") and out["last_clicked"] != state.get("click"):
        state["click"] = out["last_clicked"]
        changed = True
    if mode == "Draw" and out.get("last_active_drawing") and out["last_active_drawing"] != state.get("drawing"):
        state["drawing"] = out["last_active_drawing"]
        changed = True
    if changed:
        st.rerun()

# ---- selection ------------------------------------------------------------------
if area == "incomplete":
    with right:
        st.info(hint, icon=":material/touch_app:")
    st.stop()

sel_bh = data.points_in(bh, area)
sel_s = samples[samples["hole_id"].isin(sel_bh["hole_id"])] if not samples.empty and not sel_bh.empty else samples.iloc[0:0]
sel_up = data.uploads_in(uploads, area)
sel_vs = data.points_in(vs_sites, area)
sel_prof = vs_prof if (area is None or vs_prof.empty) else data.points_in(vs_prof.dropna(subset=["x_mtm8", "y_mtm8"]), area)
area_label = "whole island" if area is None else (
    f"{radius} m around {state['click']['lat']:.5f}, {state['click']['lng']:.5f}" if mode == "Circle"
    else f"drawn area ({area.area / 1e6:.2f} km²)")

with right:
    ui.panel_title(f"In this selection · {area_label}")
    n_pre = int((sel_bh["data_era"] == "pre-1960").sum()) if not sel_bh.empty else 0
    n_ref = int(sel_s["refusal"].sum()) if "refusal" in sel_s.columns else 0
    vs_med = sel_vs["vs30_ms"].median() if not sel_vs.empty else None
    ui.kpis([
        (f"{len(sel_bh):,}", "Boreholes", f"{n_pre:,} pre-1960", ui.ERA_COLOURS["1960 and later"]),
        (f"{len(sel_s):,}", "SPT samples", f"{n_ref:,} refusals (censored)", ui.ERA_COLOURS["pre-1960"]),
        (f"{len(sel_vs):,}", "Measured Vs30 sites",
         f"median {vs_med:.0f} m/s" if vs_med == vs_med and vs_med is not None else "no values", ui.VS_COLOUR),
        (f"{len(sel_up):,}", "Contributed files", "approved by a curator", ui.UPLOAD_COLOUR),
    ])

    vs_vals = sel_vs.dropna(subset=["vs30_ms"])
    if not vs_vals.empty:
        ui.panel_title("Measured Vs30 distribution")
        chart = alt.Chart(vs_vals).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("vs30_ms:Q", bin=alt.Bin(step=100), title="Vs30 (m/s, measured)",
                  axis=alt.Axis(labelOverlap="greedy", values=[0, 500, 1000, 1500])),
            y=alt.Y("count():Q", title="Sites"),
            color=alt.Color("site_class_from_measured:N", title="Class",
                            scale=alt.Scale(domain=list(ui.SITE_CLASS_COLOURS),
                                            range=list(ui.SITE_CLASS_COLOURS.values())),
                            legend=alt.Legend(orient="bottom", direction="horizontal", title="NBCC class")),
            tooltip=[alt.Tooltip("count():Q", title="Sites"), alt.Tooltip("site_class_from_measured:N", title="Class")],
        ).properties(height=250)
        st.altair_chart(chart, width="stretch")

    if not sel_bh.empty:
        ui.panel_title("Boreholes by era")
        era = sel_bh["data_era"].value_counts().rename_axis("era").reset_index(name="n")
        st.altair_chart(alt.Chart(era).mark_bar(cornerRadiusEnd=3).encode(
            y=alt.Y("era:N", title=None, sort="-x"), x=alt.X("n:Q", title="Boreholes"),
            color=alt.Color("era:N", legend=None, scale=alt.Scale(domain=list(ui.ERA_COLOURS),
                                                                  range=list(ui.ERA_COLOURS.values()))),
        ).properties(height=110), width="stretch")

    ui.panel_title("Download")
    zip_key = (area_label, label, len(sel_bh), len(sel_up), len(sel_vs), len(sel_prof), show_far)
    if st.button("Prepare zip for this selection", icon=":material/folder_zip:", width="stretch"):
        with st.spinner("Building zip…"):
            state["zip"] = (zip_key, bundle.build_zip(sel_bh, sel_s, sel_up, store.get_bytes, area_label, label,
                                                      sel_vs, sel_prof))
    if state.get("zip") and state["zip"][0] == zip_key:
        st.download_button("Download zip", state["zip"][1], file_name="montreal_geotech_selection.zip",
                           mime="application/zip", icon=":material/download:", type="primary",
                           width="stretch")
    st.markdown('<div class="gx-note">CSV in MTM 8 with a WGS84 copy, the original files, a manifest and a '
                'README with the caveats.</div>', unsafe_allow_html=True)

# ---- details --------------------------------------------------------------------
st.write("")
tv, tb, ts, tf = st.tabs([f"Measured Vs · {len(sel_vs)} sites", f"Boreholes · {len(sel_bh):,}",
                          f"SPT samples · {len(sel_s):,}", f"Files · {len(sel_up)}"])
with tv:
    st.markdown('<span class="gx-badge gx-measured">MEASURED</span><span class="gx-note">Vs30 at these sites comes '
                'from field seismic surveys (Rosset compilation). Profiles are measured (downhole) or derived '
                '(MASW inversion, minivib travel times); see <code>vs_status</code>.</span>', unsafe_allow_html=True)
    if sel_vs.empty and sel_prof.empty:
        st.write("No measured Vs in this selection.")
    else:
        a, b = st.columns([1.25, 1], gap="large")
        with a:
            st.dataframe(sel_vs[["site_id", "area", "survey_type", "vs30_ms", "site_class_from_measured", "f0_hz",
                                 "x_mtm8", "y_mtm8", "qa_flags"]],
                         hide_index=True, width="stretch", height=380,
                         column_config={"vs30_ms": st.column_config.NumberColumn("Vs30 (m/s)", format="%.0f"),
                                        "site_class_from_measured": "Class",
                                        "f0_hz": st.column_config.NumberColumn("f0 (Hz)", format="%.2f"),
                                        "x_mtm8": st.column_config.NumberColumn("X MTM8", format="%.0f"),
                                        "y_mtm8": st.column_config.NumberColumn("Y MTM8", format="%.0f")})
        with b:
            if sel_prof.empty:
                st.write("No Vs-depth profiles here.")
            else:
                ids = sorted(sel_prof["site_id"].unique())
                pick = st.selectbox("Vs-depth profile", ids, help="Sites and seismic lines with depth profiles.")
                p = sel_prof[sel_prof["site_id"] == pick].sort_values("depth_m")
                base = alt.Chart(p).encode(
                    x=alt.X("vs_ms:Q", title="Vs (m/s)"),
                    y=alt.Y("depth_m:Q", title="Depth (m)", scale=alt.Scale(reverse=True)),
                    color=alt.Color("vs_status:N", title=None, legend=alt.Legend(orient="bottom", labelLimit=320)),
                    tooltip=["site_id", "method", "soil_type", "depth_m", "vs_ms", "vs_status"])
                chart = base.mark_point(filled=True, size=36, opacity=0.85)
                if p["method"].iloc[0] != "Minivib":  # one vertical profile: join it; minivib lines mix many CMPs
                    chart = base.mark_line(strokeWidth=1.5, interpolate="step-before").encode(order="depth_m:Q") + chart
                st.altair_chart(chart.properties(height=330), width="stretch")
                loc = p["location_basis"].iloc[0]
                st.markdown(f'<div class="gx-note">{len(p)} points · location: {loc}</div>', unsafe_allow_html=True)
with tb:
    if sel_bh.empty:
        st.write("No boreholes in this selection." + (" The archive is not loaded yet." if label == "none" else ""))
    else:
        st.markdown('<span class="gx-badge gx-estimated">ESTIMATED</span><span class="gx-note">Borehole Vs30 and '
                    'site class come from a lithology lookup (Rosset et al. 2023), not measurements.</span>',
                    unsafe_allow_html=True)
        st.dataframe(sel_bh, width="stretch", hide_index=True, height=420)
with ts:
    if sel_s.empty:
        st.write("No SPT samples in this selection.")
    else:
        st.markdown('<span class="gx-note"><code>n_field</code> is the raw field N. Refusals are flagged in '
                    '<code>refusal</code> (censored values), never N = 999.</span>', unsafe_allow_html=True)
        st.dataframe(sel_s, width="stretch", hide_index=True, height=420)
with tf:
    if not sel_up:
        st.write("No contributed files here yet. Add one under Contribute data.")
    for r in sel_up:
        with st.expander(f"{r['data_type']} · {r['title']} ({r.get('work_year') or 'undated'})", icon=":material/description:"):
            st.write(f"**Source:** {r.get('source_org')} · {r.get('original_reference') or ''}  \n"
                     f"**Values:** {r.get('value_status')} · **Licence:** {r.get('licence')}  \n"
                     f"**File:** {r['file_name']} ({r.get('file_size', 0) / 1e6:.2f} MB) · uploaded {r.get('uploaded_at')}")
            if r.get("data_era") == "pre-1960":
                st.warning("Pre-1960 work: SPT N read about half of modern values.")
            st.download_button("Download this file", store.get_bytes(r), file_name=r["file_name"], key=f"dl_{r['id']}")
