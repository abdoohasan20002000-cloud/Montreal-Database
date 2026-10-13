"""Insights: what the data says across the whole island."""
import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from geotech import insight, ui

ui.hero("Insights",
        "The whole dataset at a glance: how stiff the ground is, how velocity grows with depth in each soil, "
        "where data is dense or thin, and what still needs checking.",
        chips=["Measured, derived and interpolated values labelled", "Source: Rosset compilation + archive"])

with st.sidebar:
    st.markdown("#### Filters")
    show_far = st.toggle("Include Vs sites off the island", value=False)

bh, samples, label = ui.load_archive(False)
sites, prof = ui.load_vs()
reg = insight.load_regressions()
if not show_far:
    sites = sites[sites["on_island"]]
    prof = prof[prof["on_island"].astype(str).isin(["True", "nan", "None"])]
sites = sites.assign(site_class=sites["vs30_ms"].map(ui.nbcc_class))
measured = sites.dropna(subset=["vs30_ms"])

# ---- headline numbers -----------------------------------------------------------------
soft = int(measured["site_class"].isin(["D", "E"]).sum())
ui.kpis([
    (f"{len(measured):,}", "Sites with measured Vs30", f"{len(sites) - len(measured)} more without a value", ui.VS_COLOUR),
    (f"{measured['vs30_ms'].median():.0f} m/s", "Median measured Vs30",
     f"middle half {measured['vs30_ms'].quantile(.25):.0f}–{measured['vs30_ms'].quantile(.75):.0f} m/s", ui.VS_COLOUR),
    (f"{soft / max(len(measured), 1):.0%}", "Sites in class D or E", "class derived from measured Vs30",
     ui.SITE_CLASS_COLOURS["D"]),
    (f"{len(prof):,}", "Vs-depth readings", f"{prof['site_id'].nunique()} sites and lines, to "
     f"{prof['depth_m'].max():.0f} m", ui.SITE_CLASS_COLOURS["C"]),
    (f"{len(bh):,}" if not bh.empty else "not loaded", "Archive boreholes",
     "6,961 expected" if bh.empty else f"{int((bh['data_era'] == 'pre-1960').sum()):,} pre-1960",
     ui.ERA_COLOURS["1960 and later"]),
], cols=5)
st.write("")

# ---- row 1: depth trend and areas -----------------------------------------------------
a, b = st.columns([1.35, 1], gap="large")
with a:
    ui.panel_title("Shear-wave velocity with depth, by soil type")
    pts = prof[(prof["profile_source"] == "01_Vs_POINTS") & prof["soil_type"].isin(["sand", "clay", "silt", "till"])]
    n_fast = int((pts["vs_ms"] > 1000).sum())
    pts = pts[(pts["vs_ms"] <= 1000) & (pts["depth_m"] <= 40)]
    soil_colours = {"clay": "#7f95a3", "silt": "#b9a77f", "sand": "#e0b25c", "till": "#8d7b68"}
    scatter = alt.Chart(pts).mark_circle(size=26, opacity=0.55).encode(
        x=alt.X("vs_ms:Q", title="Vs (m/s)", scale=alt.Scale(domain=[0, 1000])),
        y=alt.Y("depth_m:Q", title="Depth (m)", scale=alt.Scale(reverse=True, domain=[0, 40])),
        color=alt.Color("soil_type:N", title="Soil", scale=alt.Scale(domain=list(soil_colours),
                                                                      range=list(soil_colours.values()))),
        tooltip=["site_id", "soil_type", "depth_m", "vs_ms", "vs_status"])
    curves = insight.regression_curves(reg[reg["fit"].isin(["reg_sand", "reg_clay"])]) if not reg.empty else pd.DataFrame()
    chart = scatter
    if not curves.empty:
        chart = scatter + alt.Chart(curves).mark_line(strokeWidth=2.5).encode(
            x="vs_ms:Q", y="depth_m:Q", order="depth_m:Q",
            strokeDash=alt.StrokeDash("fit:N", title="Published fit"),
            color=alt.value("#1c2430"), tooltip=["fit", "equation"])
    st.altair_chart(chart.properties(height=380), width="stretch")
    st.markdown('<div class="gx-note">Points: downhole, MASW and minivib readings grouped by soil (01_Vs_POINTS, '
                f'duplicates removed; {n_fast} readings above 1,000 m/s not drawn). Lines: Rosset sand and clay regressions, Vs = a + b·z<sup>c</sup>; the equation '
                'form is inferred from the fitted coefficients, which match the published Table 3.</div>',
                unsafe_allow_html=True)
with b:
    ui.panel_title("Measured Vs30 by area")
    order = measured.groupby("area")["vs30_ms"].median().sort_values().index.tolist()
    box = alt.Chart(measured).mark_boxplot(size=16, color=ui.VS_COLOUR, median={"color": "#ffffff"}).encode(
        y=alt.Y("area:N", sort=order, title=None),
        x=alt.X("vs30_ms:Q", title="Vs30 (m/s, measured)", scale=alt.Scale(type="log", domain=[100, 2000]), axis=alt.Axis(values=[100, 180, 360, 760, 1500])))
    dots = alt.Chart(measured).mark_tick(color="#1c2430", opacity=0.5, thickness=1.5).encode(
        y=alt.Y("area:N", sort=order),
        x=alt.X("vs30_ms:Q", scale=alt.Scale(type="log", domain=[100, 2000])), tooltip=["site_id", "area", "vs30_ms", "survey_type"])
    st.altair_chart((box + dots).properties(height=380), width="stretch")
    st.markdown('<div class="gx-note">Log scale, marked at the NBCC class limits (180, 360, 760, 1500 m/s). Each tick is '
                'one site; boxes show the middle half.</div>',
                unsafe_allow_html=True)

# ---- row 2: classes and coverage -------------------------------------------------------
c, d = st.columns([1, 1.35], gap="large")
with c:
    ui.panel_title("NBCC site class, derived from measured Vs30")
    cls = measured["site_class"].value_counts().reindex(list("ABCDE"), fill_value=0).rename_axis("class").reset_index(name="sites")
    cls["meaning"] = cls["class"].map(insight.CLASS_WORDS)
    st.altair_chart(alt.Chart(cls).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("class:N", title=None, sort=list("ABCDE")), x=alt.X("sites:Q", title="Sites"),
        color=alt.Color("class:N", legend=None, scale=alt.Scale(domain=list(ui.SITE_CLASS_COLOURS),
                                                                range=list(ui.SITE_CLASS_COLOURS.values()))),
        tooltip=["class", "meaning", "sites"]).properties(height=230), width="stretch")
    by_type = measured.groupby("survey_type")["vs30_ms"].agg(["count", "median"]).round(0).reset_index()
    by_type.columns = ["Survey type", "Sites", "Median Vs30 (m/s)"]
    st.dataframe(by_type, hide_index=True, width="stretch")
with d:
    ui.panel_title("Where the data is: measurement locations per 600 m cell (3D)")
    pts3 = pd.concat([sites[["lon", "lat"]].assign(kind="Vs30 site"),
                      prof.dropna(subset=["lon"])[["lon", "lat"]].drop_duplicates().assign(kind="Vs profile")]
                     + ([bh[["lon", "lat"]].assign(kind="borehole")] if not bh.empty else []))
    layer = pdk.Layer("HexagonLayer", pts3, get_position=["lon", "lat"], radius=600, elevation_scale=4,
                      elevation_range=[0, 1000], extruded=True, coverage=0.88, pickable=True,
                      color_range=[[222, 235, 247], [158, 202, 225], [107, 174, 214], [66, 146, 198],
                                   [33, 113, 181], [8, 69, 148]])
    st.pydeck_chart(pdk.Deck(layers=[layer], map_provider="carto", map_style=pdk.map_styles.CARTO_LIGHT,
                             initial_view_state=pdk.ViewState(latitude=45.53, longitude=-73.63, zoom=9.8, pitch=50,
                                                              bearing=-20),
                             tooltip={"html": "{elevationValue} measurement locations in this 600 m cell"}),
                    height=330, width="stretch")
    st.markdown('<div class="gx-note">Each column is a 600 m hexagon; height counts Vs30 sites, Vs profile locations and '
                'boreholes inside it (a profile counts once, however many depths it has). Gaps are where new measurements would help most.</div>', unsafe_allow_html=True)

# ---- row 3: data quality --------------------------------------------------------------
ui.panel_title("Data quality: what still needs checking")
flags = []
for name, df in (("Vs30 sites", sites), ("Vs readings", prof)):
    for f in df["qa_flags"].fillna("").str.split(";").explode():
        if f:
            flags.append({"table": name, "flag": f})
q = pd.DataFrame(flags)
if q.empty:
    st.write("No open flags.")
else:
    q = q.value_counts().rename("rows").reset_index()
    q["what it means"] = q["flag"].map({
        "no Vs30": "Site listed without a Vs30 value; kept, not used in statistics.",
        "unlocated": "No coordinates in the source; appears only in whole-island downloads.",
        "duplicate of an earlier sheet": "Repeated between source sheets; removed from counts.",
        "bad depth": "Depth below zero (LM04-1, -0.04 m); kept and flagged.",
        "method blank in source": "Method not stated (MM09-2); not called measured.",
        "outside island box": "Site lies off the island.",
    }).fillna("")
    st.dataframe(q, hide_index=True, width="stretch")
if bh.empty:
    st.info("Borehole and SPT insights (N-value trends, refusal rates, pre-1960 share) appear here once the "
            "archive CSVs are added.", icon=":material/info:")
