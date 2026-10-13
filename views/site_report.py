"""Site report: pick one location and get what is known about the ground there."""
import altair as alt
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from geotech import geo, insight, ui

state = st.session_state
ui.hero("Site report",
        "Pick a location to see the nearest measurements, an interpolated Vs30 with its NBCC class, the Vs "
        "profiles nearby and a plain-language summary you can download.",
        chips=["Interpolated values are labelled", "Every value carries method, source and date"])

bh, samples, label = ui.load_archive(False)
sites, prof = ui.load_vs()
reg = insight.load_regressions()

# ---- location ---------------------------------------------------------------------------
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1.2], vertical_alignment="bottom")
    how = c1.segmented_control("Location", ["Click the map", "Type coordinates"], default="Click the map",
                               key="sr_how") or "Click the map"
    radius = c4.slider("Search radius (m)", 250, 5000, 2000, 250)
    if how == "Type coordinates":
        crs = c1.radio("In", ["Lat / long", "MTM 8"], horizontal=True, label_visibility="collapsed")
        if crs == "MTM 8":
            x_in = c2.number_input("X (m)", value=299540.0, format="%.1f")
            y_in = c3.number_input("Y (m)", value=5040200.0, format="%.1f")
            lon, lat = geo.mtm8_to_wgs84(x_in, y_in)
        else:
            lat = c2.number_input("Latitude", value=45.5017, format="%.5f")
            lon = c3.number_input("Longitude", value=-73.5673, format="%.5f")
        state["sr_point"] = {"lat": float(lat), "lng": float(lon)}

pt = state.get("sr_point")
left, right = st.columns([1.15, 1], gap="large")
with left:
    m = ui.base_map((pt["lat"], pt["lng"]) if pt else (45.55, -73.66), 13 if pt else 11)
    for r in sites.dropna(subset=["vs30_ms"]).to_dict("records"):
        folium.CircleMarker([r["lat"], r["lon"]], radius=5, color="#ffffff", weight=1.2, fill=True, fill_opacity=0.95,
                            fill_color=ui.SITE_CLASS_COLOURS.get(ui.nbcc_class(r["vs30_ms"]), ui.ERA_COLOURS["undated"]),
                            tooltip=f"{r['site_id']} · {r['vs30_ms']:.0f} m/s").add_to(m)
    if pt:
        folium.Circle([pt["lat"], pt["lng"]], radius=radius, color=ui.ACCENT, weight=2, dash_array="6 4",
                      fill=True, fill_color=ui.ACCENT, fill_opacity=0.06).add_to(m)
        folium.Marker([pt["lat"], pt["lng"]], icon=ui.target_icon(), tooltip="Report location").add_to(m)
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    out = st_folium(m, height=470, use_container_width=True, returned_objects=["last_clicked"], key="sr_map")
    if how == "Click the map" and out and out.get("last_clicked") and out["last_clicked"] != state.get("sr_point"):
        state["sr_point"] = out["last_clicked"]
        st.rerun()

if not pt:
    with right:
        st.info("Click anywhere on the map, or type coordinates, to build a report.", icon=":material/touch_app:")
    st.stop()

# ---- analysis ---------------------------------------------------------------------------
lat, lon = pt["lat"], pt["lng"]
x, y = geo.wgs84_to_mtm8(lon, lat)
near = insight.neighbours(sites, x, y, radius)
est, n_used = insight.idw_vs30(near)
cls = insight.nbcc_class(est)
p_near = prof.dropna(subset=["x_mtm8"]).copy()
p_near = p_near[((p_near["x_mtm8"] - x) ** 2 + (p_near["y_mtm8"] - y) ** 2) <= radius ** 2]
bh_near = None
if not bh.empty:
    bh_near = bh[((bh["x_mtm8"] - x) ** 2 + (bh["y_mtm8"] - y) ** 2) <= radius ** 2]
on_island = geo.on_island(x, y)

with right:
    ui.panel_title(f"Report · {lat:.5f}, {lon:.5f} · MTM 8 {x:,.0f} E {y:,.0f} N")
    nearest = near.iloc[0] if not near.empty else None
    ui.kpis([
        (f"{nearest['vs30_ms']:.0f} m/s" if nearest is not None else "none",
         "Nearest measured Vs30", f"{nearest['site_id']}, {nearest['distance_m']:.0f} m away" if nearest is not None
         else f"nothing within {radius} m", ui.VS_COLOUR),
        (f"≈ {est:.0f} m/s" if est else "–", "Vs30 here (interpolated)",
         f"from {n_used} sites, not measured" if est else "no sites in radius", ui.SITE_CLASS_COLOURS["C"]),
        (cls or "–", "NBCC class (derived)", insight.CLASS_WORDS.get(cls, "needs a Vs30"),
         ui.SITE_CLASS_COLOURS.get(cls, ui.ERA_COLOURS["undated"])),
        (f"{p_near['site_id'].nunique()}", "Vs profiles nearby", f"{len(p_near)} depth readings", ui.SITE_CLASS_COLOURS["D"]),
    ])
    text = insight.summary(lat, lon, radius, near, est, n_used, len(p_near), p_near["site_id"].nunique(), bh_near, on_island)
    st.markdown('<span class="gx-badge gx-interpolated">SUMMARY</span><span class="gx-note">includes interpolated '
                'and derived values, labelled in the text</span>', unsafe_allow_html=True)
    st.write(text)

# ---- details -----------------------------------------------------------------------------
st.write("")
a, b = st.columns([1, 1.15], gap="large")
with a:
    ui.panel_title("Measured sites within the radius")
    if near.empty:
        st.write(f"No measured Vs30 within {radius} m.")
    else:
        shown = near.head(10)[["site_id", "area", "survey_type", "vs30_ms", "distance_m"]].copy()
        shown.insert(0, "used", [i < n_used for i in range(len(shown))])
        st.dataframe(shown, hide_index=True, width="stretch",
                     column_config={"used": st.column_config.CheckboxColumn("In estimate", width="small"),
                                    "site_id": "Site", "area": "Area", "survey_type": "Survey",
                                    "vs30_ms": st.column_config.NumberColumn("Vs30 (m/s)", format="%.0f"),
                                    "distance_m": st.column_config.ProgressColumn("Distance (m)", format="%.0f",
                                                                                  min_value=0, max_value=radius)})
with b:
    ui.panel_title("Vs profiles nearby, with the published sand and clay fits")
    curves = insight.regression_curves(reg[reg["fit"].isin(["reg_sand", "reg_clay"])]) if not reg.empty else pd.DataFrame()
    if p_near.empty and curves.empty:
        st.write("No profiles nearby.")
    else:
        layers = []
        if not p_near.empty:
            layers.append(alt.Chart(p_near).mark_circle(size=30, opacity=0.75).encode(
                x=alt.X("vs_ms:Q", title="Vs (m/s)"), y=alt.Y("depth_m:Q", title="Depth (m)", scale=alt.Scale(reverse=True)),
                color=alt.Color("site_id:N", title="Profile", scale=alt.Scale(range=ui.CATEGORICAL)),
                tooltip=["site_id", "method", "depth_m", "vs_ms", "vs_status"]))
        if not curves.empty:
            layers.append(alt.Chart(curves).mark_line(strokeWidth=2, color=ui.INK).encode(
                x="vs_ms:Q", y=alt.Y("depth_m:Q", scale=alt.Scale(reverse=True)), order="depth_m:Q",
                strokeDash=alt.StrokeDash("fit:N", title="Fit", scale=alt.Scale(
                    domain=["clay (Rosset fit)", "sand (Rosset fit)"], range=[[1, 0], [5, 4]])),
                tooltip=["fit", "equation"]))
        st.altair_chart(alt.layer(*layers).properties(height=320), width="stretch")

table = insight.report_table(lat, lon, x, y, radius, near, est, n_used)
with st.expander("Report table: every value with its status, method, source and date", icon=":material/table:"):
    st.dataframe(table, hide_index=True, width="stretch")
md = (f"# Site report\n\n{text}\n\nInterpolation method: {insight.IDW_METHOD}.\n\n"
      + "| " + " | ".join(table.columns) + " |\n|" + "---|" * len(table.columns) + "\n"
      + "\n".join("| " + " | ".join(str(v) for v in r) + " |" for r in table.itertuples(index=False)))
d1, d2, _ = st.columns([1, 1, 2])
d1.download_button("Download report (Markdown)", md, file_name="site_report.md", icon=":material/description:",
                   width="stretch")
d2.download_button("Download table (CSV)", table.to_csv(index=False), file_name="site_report.csv",
                   icon=":material/download:", width="stretch")
