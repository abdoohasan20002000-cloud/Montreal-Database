"""Insights: what the data says across the whole island."""
import html

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from geotech import catalogue, config, data, insight, ui

ui.hero("Insights",
        "The whole dataset at a glance: how stiff the ground is, how velocity grows with depth in each soil, "
        "where data is dense or thin, and what still needs checking.",
        chips=["Measured, derived and interpolated values labelled", "Source: Rosset compilation + archive"])

with st.sidebar:
    ui.sidebar_label("Filters")
    regions = st.multiselect("Regions", catalogue.region_options(), placeholder="All boroughs and cities",
                             key="ins_regions", help="Boroughs and linked cities; each point's region is derived from "
                                                     "its coordinates and the City's limits.")
    show_far = st.toggle("Include Vs sites off the island", value=False)

bh, samples, label = ui.load_archive(False)
sites, prof = ui.load_vs()
reg = insight.load_regressions()
if not show_far and config.OFF_ISLAND not in regions:  # picking "Off the island" is asking for those sites
    sites, prof = data.keep_on_island(sites), data.keep_on_island(prof)
sites, prof, bh = data.in_regions(sites, regions), data.in_regions(prof, regions), data.in_regions(bh, regions)
if regions:
    st.markdown(f'<div class="gx-note" style="margin:-4px 0 10px">Showing {len(regions)} region'
                f'{"s" if len(regions) > 1 else ""}: {html.escape(", ".join(regions))}.</div>', unsafe_allow_html=True)
sites = sites.assign(site_class=sites["vs30_ms"].map(ui.nbcc_class))
measured = sites.dropna(subset=["vs30_ms"])

# ---- headline numbers -----------------------------------------------------------------
if measured.empty:
    st.info("No measured Vs30 site in the chosen regions yet. Pick other regions, or contribute data for these.",
            icon=":material/filter_alt_off:")
    st.stop()
soft = int(measured["site_class"].isin(["D", "E"]).sum())
ui.kpis([
    (f"{len(measured):,}", "Sites with measured Vs30", f"{len(sites) - len(measured)} more without a value", ui.VS_COLOUR),
    (f"{measured['vs30_ms'].median():.0f} m/s", "Median measured Vs30",
     f"middle half {measured['vs30_ms'].quantile(.25):.0f}–{measured['vs30_ms'].quantile(.75):.0f} m/s", ui.VS_COLOUR),
    (f"{soft / max(len(measured), 1):.0%}", "Sites in class D or E", f"{soft} sites; class derived from measured Vs30",
     ui.SITE_CLASS_COLOURS["D"]),
    (f"{len(prof):,}", "Vs-depth readings", f"{prof['site_id'].nunique()} sites and lines, to "
     f"{prof['depth_m'].max():.0f} m" if not prof.empty else "none here", ui.ACCENT),
    (f"{len(bh):,}" if not bh.empty else "–", "Archive boreholes",
     "not loaded; 6,961 expected" if bh.empty else f"{int((bh['data_era'] == 'pre-1960').sum()):,} pre-1960",
     ui.ERA_COLOURS["1960 and later"]),
], cols=5)
st.write("")

# ---- velocity with depth: one small panel per soil, the published fits on each ------------
ui.panel_title("Shear-wave velocity with depth, by soil type")
st.markdown(f'<div class="gx-note" style="margin:-2px 0 6px"><span style="color:{ui.CATEGORICAL[0]}">●</span> measured '
            f'or derived Vs reading &nbsp;&nbsp;<span style="color:{ui.INK}">━━</span> clay fit (Rosset) &nbsp;&nbsp;'
            f'<span style="color:{ui.INK}">╍╍</span> sand fit (Rosset)</div>', unsafe_allow_html=True)
SOILS = ["clay", "silt", "sand", "till"]
all_pts = prof[prof["profile_source"] == "01_Vs_POINTS"]
n_other = int((~all_pts["soil_type"].isin(SOILS)).sum())  # fill, rock or no soil type in the source
pts = all_pts[all_pts["soil_type"].isin(SOILS)]
n_fast = int((pts["vs_ms"] > 1000).sum())
pts = pts[(pts["vs_ms"] <= 1000) & (pts["depth_m"] <= 40)]
curves = insight.regression_curves(reg[reg["fit"].isin(["reg_sand", "reg_clay"])]) if not reg.empty else pd.DataFrame()
x_scale, y_scale = alt.Scale(domain=[0, 1000]), alt.Scale(reverse=True, domain=[0, 40])
wide = st.container(key="soilpanels").columns(4, gap="small")  # two by two on narrow screens (CSS in ui.py)
for i, soil in enumerate(SOILS):
    p = pts[pts["soil_type"] == soil]
    with wide[i]:
        chart = alt.Chart(p).mark_circle(size=34, opacity=0.7, color=ui.CATEGORICAL[0], stroke=ui.SURFACE,
                                         strokeWidth=0.6).encode(
            x=alt.X("vs_ms:Q", title="Vs (m/s)", scale=x_scale,
                    axis=alt.Axis(values=[0, 500, 1000], labelOverlap="greedy", labelSeparation=4)),
            y=alt.Y("depth_m:Q", title="Depth (m)", scale=y_scale),
            tooltip=["site_id", "soil_type", alt.Tooltip("depth_m:Q", format=".1f"), alt.Tooltip("vs_ms:Q", format=".0f"),
                     "vs_status"])
        if not curves.empty:
            chart = chart + alt.Chart(curves).mark_line(strokeWidth=2, color=ui.INK).encode(
                x=alt.X("vs_ms:Q", scale=x_scale), y=alt.Y("depth_m:Q", scale=y_scale), order="depth_m:Q",
                strokeDash=alt.StrokeDash("fit:N", legend=None, scale=alt.Scale(
                    domain=["clay (Rosset fit)", "sand (Rosset fit)"], range=[[1, 0], [5, 4]])),
                tooltip=["fit", "equation"])
        st.altair_chart(chart.properties(height=300, title=alt.TitleParams(f"{soil} ({len(p)})", anchor="start",
                                                                            fontSize=13, limit=0)),
                        width="stretch")
st.markdown('<div class="gx-note">Each panel shows the readings logged in one soil (downhole, MASW and minivib; sheet '
            f'01_Vs_POINTS, duplicates removed; the number in brackets counts them; {n_fast} readings above 1,000 m/s '
            f'and {n_other} in fill, rock or with no soil type are not drawn). The two lines, the same in '
            'every panel, are the Rosset sand (dashed) and clay (solid) regressions, Vs = a + b·z<sup>c</sup>; the '
            'equation form is inferred from the fitted coefficients, which match the published Table 3.</div>',
            unsafe_allow_html=True)
st.write("")

# ---- areas and classes --------------------------------------------------------------------
a, b = st.columns([1.3, 1], gap="large")
with a:
    ui.panel_title("Measured Vs30 by survey area or region")
    group = st.segmented_control("Group by", ["Survey area", "Region"], default="Survey area", key="ins_group",
                                 label_visibility="collapsed") or "Survey area"
    gcol = "area" if group == "Survey area" else "region"
    order = measured.groupby(gcol)["vs30_ms"].median().sort_values().index.tolist()
    log_x = alt.Scale(type="log", domain=[100, 2000])
    box = alt.Chart(measured).mark_boxplot(size=16, color=ui.CATEGORICAL[0], median={"color": "#ffffff"},
                                           rule={"color": ui.INK_2}, outliers={"color": ui.INK_2}).encode(
        y=alt.Y(f"{gcol}:N", sort=order, title=None, axis=alt.Axis(labelLimit=220, labelPadding=8)),
        x=alt.X("vs30_ms:Q", title="Vs30 (m/s, measured)", scale=log_x,
                axis=alt.Axis(values=[100, 180, 360, 760, 1500])))
    ticks = alt.Chart(measured).mark_tick(color=ui.INK, opacity=0.55, thickness=1.5).encode(
        y=alt.Y(f"{gcol}:N", sort=order), x=alt.X("vs30_ms:Q", scale=log_x),
        tooltip=["site_id", "area", "region", alt.Tooltip("vs30_ms:Q", format=".0f"), "survey_type"])
    st.altair_chart((box + ticks).properties(height=max(160, 26 * len(order) + 50),
                                             padding={"left": 12, "right": 8, "top": 4, "bottom": 4}), width="stretch")
    st.markdown('<div class="gx-note">Log scale, marked at the NBCC class limits (180, 360, 760, 1500 m/s). Each tick '
                'is one site; boxes show the middle half.</div>', unsafe_allow_html=True)
    by_type = measured.groupby("survey_type")["vs30_ms"].agg(["count", "median"]).round(0).reset_index()
    by_type.columns = ["Survey type", "Sites", "Median Vs30 (m/s)"]
    st.dataframe(by_type, hide_index=True, width="stretch",
                 column_config={"Median Vs30 (m/s)": st.column_config.NumberColumn(format="%.0f")})
with b:
    ui.panel_title("NBCC site class, derived from measured Vs30")
    cls = measured["site_class"].value_counts().reindex(list("ABCDE"), fill_value=0).rename_axis("class").reset_index(name="sites")
    cls["meaning"] = cls["class"].map(insight.CLASS_WORDS)
    bars = alt.Chart(cls).mark_bar(cornerRadiusEnd=4, height=22).encode(
        y=alt.Y("class:N", title=None, sort=list("ABCDE")),
        x=alt.X("sites:Q", title="Sites", axis=alt.Axis(tickMinStep=1, format="d")),
        color=alt.Color("class:N", legend=None, scale=alt.Scale(domain=list("ABCDE"),
                                                                range=[ui.SITE_CLASS_COLOURS[k] for k in "ABCDE"])),
        tooltip=["class", "meaning", "sites"])
    labels = bars.mark_text(align="left", dx=6, color=ui.INK_2, fontSize=12).encode(text="sites:Q", color=alt.value(ui.INK_2))
    st.altair_chart((bars + labels).properties(height=210, padding={"left": 4, "right": 28}), width="stretch")
    ui.class_tags()

# ---- coverage and quality -------------------------------------------------------------------
c, d = st.columns([1.3, 1], gap="large")
with c:
    ui.panel_title("Where the data is: measurement locations per 600 m cell (3D)")
    pts3 = pd.concat([sites[["lon", "lat"]].assign(kind="Vs30 site"),
                      prof.dropna(subset=["lon"])[["lon", "lat"]].drop_duplicates().assign(kind="Vs profile")]
                     + ([bh[["lon", "lat"]].assign(kind="borehole")] if not bh.empty else []))
    layer = pdk.Layer("HexagonLayer", pts3, get_position=["lon", "lat"], radius=600, elevation_scale=4,
                      elevation_range=[0, 1000], extruded=True, coverage=0.88, pickable=True,
                      color_range=[[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in ui.SEQUENTIAL])
    st.pydeck_chart(pdk.Deck(layers=[layer], map_provider="carto", map_style=pdk.map_styles.CARTO_LIGHT,
                             initial_view_state=pdk.ViewState(latitude=45.53, longitude=-73.63, zoom=9.8, pitch=50,
                                                              bearing=-20),
                             tooltip={"html": "{elevationValue} data points in this 600 m cell (Vs30 sites, profile "
                                              "positions, boreholes)"}),
                    height=360, width="stretch")
    st.markdown('<div class="gx-note">Each column is a 600 m hexagon; height and colour count the Vs30 sites, distinct '
                'Vs-profile positions and boreholes inside it. A profile counts once however many depths it has, and '
                'profiles placed at the same site or line centroid share one position. A site with both a Vs30 and a '
                'profile counts twice. Gaps are where new measurements would help most.</div>', unsafe_allow_html=True)
with d:
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
        q["meaning"] = q["flag"].map({
            "no Vs30": "Site listed without a Vs30 value; kept, not used in statistics.",
            "unlocated": "No coordinates in the source; appears only in whole-island downloads.",
            "duplicate of an earlier sheet": "Repeated between source sheets; removed from counts.",
            "bad depth": "Depth below zero (LM04-1, -0.04 m); kept and flagged.",
            "method blank in source": "Method not stated (MM09-2); not called measured.",
            "off the island": "Site lies outside the agglomeration limits (plus 250 m); hidden unless you include off-island sites.",
            "Rougemont area but on the island": "Named in the Rougemont area, but its coordinates in the source fall "
                                                "on the island (ROU); kept as given, check with the source.",
        }).fillna("")
        st.markdown("".join(
            f'<div class="gx-status"><div class="i todo">!</div><div><div class="t">{html.escape(r.flag)} · '
            f'{r.rows} in {html.escape(r.table)}</div><div class="d">{html.escape(r.meaning)}</div></div></div>'
            for r in q.itertuples()), unsafe_allow_html=True)
    if bh.empty:
        st.info("Borehole and SPT insights (N-value trends, refusal rates, pre-1960 share) appear here once the "
                "archive CSVs are added.", icon=":material/info:")
