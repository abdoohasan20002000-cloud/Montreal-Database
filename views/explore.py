"""Explore: the map, a selection, what is in it, and one download."""
import altair as alt
import folium
import pandas as pd
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import mapping
from streamlit_folium import st_folium

from geotech import bundle, config, data, geo, ui
from geotech.config import PRE_MODERN_YEAR

state = st.session_state

ui.hero("Explore the island",
        "Pick a spot, draw an area or take the whole island to see the boreholes, SPT samples, measured shear-wave "
        "velocities and contributed files there, then download them in one zip.",
        chips=["Coordinates <b>MTM 8</b> · EPSG:32188", "Vs30 <b>measured</b> and <b>estimated</b> kept apart",
               "Raw <b>N<sub>field</sub></b> kept · pre-1960 flagged"])

# ---- data ---------------------------------------------------------------------
with st.sidebar:
    st.markdown("#### Filters")
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
    c1, c2, c3, c4 = st.columns([1.5, 1.2, 1.6, 1.1], vertical_alignment="bottom")
    mode = c1.segmented_control("Area", ["Whole island", "Circle", "Draw"],
                                default="Whole island", key="mode") or "Whole island"
    radius = c2.slider("Radius (m)", 100, 5000, 500, 100, disabled=mode != "Circle")
    layers = c3.pills("Layers", ["Boreholes", "Measured Vs30", "Files"], selection_mode="multi",
                      default=["Boreholes", "Measured Vs30", "Files"], key="layers")
    colour_by = c4.selectbox("Colour boreholes by", ["Era", "Site class (estimated)"])
    hint = {"Circle": "Click the map to place the centre of the circle.",
            "Draw": "Use the rectangle or polygon tool at the top left of the map.",
            "Whole island": "Everything on the island is selected."}[mode]
    st.markdown(f'<div class="gx-note">{hint}</div>', unsafe_allow_html=True)

area = data.selection_from_inputs({"Circle": "Point and radius", "Draw": "Draw an area"}.get(mode, mode),
                                  state.get("drawing"), state.get("click"), radius)

# ---- map ------------------------------------------------------------------------
def build_map():
    m = folium.Map(location=[45.55, -73.68], zoom_start=11, tiles=None, control_scale=True)
    folium.TileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", name="Light",
                     attr="© OpenStreetMap contributors © CARTO", max_zoom=20).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     name="Satellite", attr="Imagery © Esri", max_zoom=19, show=False).add_to(m)
    folium.TileLayer("OpenStreetMap", name="Streets", show=False).add_to(m)
    b = config.ISLAND_BBOX
    m.fit_bounds([[b["lat_min"], b["lon_min"]], [b["lat_max"], b["lon_max"]]])

    if "Boreholes" in (layers or []) and not bh.empty:
        def colour(row):
            if colour_by == "Era":
                return ui.ERA_COLOURS.get(row["data_era"], "#8a94a0")
            return ui.SITE_CLASS_COLOURS.get(str(row.get("site_class", ""))[:1], "#c4c9cf")
        tip_cols = [c for c in ["hole_id", "year", "source", "data_era", "vs30_ms", "site_class"] if c in bh.columns]
        feats = []
        for rec in bh.assign(_c=bh.apply(colour, axis=1))[tip_cols + ["lon", "lat", "_c"]].to_dict("records"):
            props = {c: (None if pd.isna(rec[c]) else str(rec[c])) for c in tip_cols}
            props["_c"] = rec["_c"]
            feats.append({"type": "Feature", "properties": props,
                          "geometry": {"type": "Point", "coordinates": [rec["lon"], rec["lat"]]}})
        folium.GeoJson({"type": "FeatureCollection", "features": feats}, name="Boreholes",
                       marker=folium.CircleMarker(radius=3, weight=0, fill=True, fill_opacity=0.85),
                       style_function=lambda f: {"fillColor": f["properties"]["_c"], "color": f["properties"]["_c"]},
                       tooltip=folium.GeoJsonTooltip(fields=tip_cols)).add_to(m)

    if "Measured Vs30" in (layers or []) and not vs_sites.empty:
        fg = folium.FeatureGroup(name="Measured Vs30 sites").add_to(m)
        for r in vs_sites.to_dict("records"):
            has = pd.notna(r["vs30_ms"])
            fill = ui.SITE_CLASS_COLOURS.get(r["site_class_from_measured"], "#ffffff") if has else "#ffffff"
            tip = (f"<b>{r['site_id']}</b> · {r['area']}<br>Vs30 {r['vs30_ms']:.0f} m/s (measured), class "
                   f"{r['site_class_from_measured']}<br>{r['survey_type']}" if has
                   else f"<b>{r['site_id']}</b> · {r['area']}<br>no Vs30 value in the source")
            folium.CircleMarker([r["lat"], r["lon"]], radius=6, color="#ffffff" if has else ui.VS_COLOUR, weight=1.5,
                                fill=True, fill_color=fill, fill_opacity=0.95, tooltip=tip).add_to(fg)

    if "Files" in (layers or []) and uploads:
        fg = folium.FeatureGroup(name="Contributed files").add_to(m)
        for r in uploads:
            folium.Marker([r["lat"], r["lon"]], tooltip=f"{r['data_type']}: {r['title']}",
                          icon=folium.Icon(color="purple", icon="file", prefix="fa")).add_to(fg)

    if area not in (None, "incomplete"):
        folium.GeoJson(mapping(geo.shp_transform_to_wgs84(area)), name="Selection",
                       style_function=lambda f: {"color": "#0e7c86", "weight": 2.5, "dashArray": "6 4",
                                                 "fillColor": "#0e7c86", "fillOpacity": 0.08}).add_to(m)
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
    rows += [("#3f6e9e", "Measured Vs30 site", "ring"), (ui.UPLOAD_COLOUR, "Contributed file", "pin")]
    classes = "".join(f'<span title="Class {k}" style="display:inline-flex;align-items:center;justify-content:center;'
                      f'width:18px;height:14px;background:{c};color:#fff;font-size:10px;border-radius:2px">{k}</span>'
                      for k, c in ui.SITE_CLASS_COLOURS.items() if k != "F")
    items = "".join(
        f'<div style="display:flex;align-items:center;gap:7px;margin:2px 0">'
        f'<span style="width:10px;height:10px;border-radius:50%;background:{c};'
        f'{"border:2px solid #fff;box-shadow:0 0 0 1px " + c + ";" if kind == "ring" else ""}'
        f'{"border-radius:2px;" if kind == "pin" else ""}"></span>{t}</div>' for c, t, kind in rows)
    return ('<div style="position:absolute;top:88px;left:10px;z-index:9999;background:rgba(255,255,255,0.94);'
            'padding:9px 12px;border-radius:10px;font:12px/1.35 \'IBM Plex Sans\',system-ui,sans-serif;color:#1c2430;'
            'box-shadow:0 1px 6px rgba(0,0,0,0.15)"><div style="font-weight:600;margin-bottom:4px">Legend</div>'
            + items + '<div style="margin-top:5px;color:#5d6876">Vs30 site fill = NBCC class</div>'
            f'<div style="display:flex;gap:2px;margin-top:2px">{classes}</div></div>')


left, right = st.columns([2.35, 1], gap="medium")
with left:
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
            x=alt.X("vs30_ms:Q", bin=alt.Bin(step=100), title="Vs30 (m/s, measured)"),
            y=alt.Y("count():Q", title="Sites"),
            color=alt.Color("site_class_from_measured:N", title="Class",
                            scale=alt.Scale(domain=list(ui.SITE_CLASS_COLOURS),
                                            range=list(ui.SITE_CLASS_COLOURS.values())),
                            legend=alt.Legend(orient="bottom", direction="horizontal", title="NBCC class")),
            tooltip=[alt.Tooltip("count():Q", title="Sites"), alt.Tooltip("site_class_from_measured:N", title="Class")],
        ).properties(height=210)
        st.altair_chart(chart, use_container_width=True)

    if not sel_bh.empty:
        ui.panel_title("Boreholes by era")
        era = sel_bh["data_era"].value_counts().rename_axis("era").reset_index(name="n")
        st.altair_chart(alt.Chart(era).mark_bar(cornerRadiusEnd=3).encode(
            y=alt.Y("era:N", title=None, sort="-x"), x=alt.X("n:Q", title="Boreholes"),
            color=alt.Color("era:N", legend=None, scale=alt.Scale(domain=list(ui.ERA_COLOURS),
                                                                  range=list(ui.ERA_COLOURS.values()))),
        ).properties(height=110), use_container_width=True)

    ui.panel_title("Download")
    zip_key = (area_label, label, len(sel_bh), len(sel_up), len(sel_vs), len(sel_prof), show_far)
    if st.button("Prepare zip for this selection", icon=":material/folder_zip:", use_container_width=True):
        with st.spinner("Building zip…"):
            state["zip"] = (zip_key, bundle.build_zip(sel_bh, sel_s, sel_up, store.get_bytes, area_label, label,
                                                      sel_vs, sel_prof))
    if state.get("zip") and state["zip"][0] == zip_key:
        st.download_button("Download zip", state["zip"][1], file_name="montreal_geotech_selection.zip",
                           mime="application/zip", icon=":material/download:", type="primary",
                           use_container_width=True)
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
                st.altair_chart(chart.properties(height=330), use_container_width=True)
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
