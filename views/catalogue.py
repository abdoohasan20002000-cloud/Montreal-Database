"""Data catalogue: every dataset in the atlas, filtered by type, region and years, with its details and downloads."""
import html
import json
from functools import partial

import altair as alt
import pandas as pd
import streamlit as st

from geotech import catalogue, config, geo, insight, ui

state = st.session_state
kinds = pd.Series(geo.region_kinds()).value_counts()
ui.hero("Data catalogue",
        "Every dataset the atlas holds, built in or contributed: what it is, where and when it was collected, who it "
        "comes from and how it may be reused. Filter by type, region and years, then open it on the map or download it.",
        chips=[f"<b>{kinds.get('Borough', 0)}</b> boroughs · <b>{kinds.get('City', 0)}</b> linked cities",
               "Any data type, any year", "Source, method and licence on every entry"])

bh, samples, label = ui.load_archive(False)
sites, prof = ui.load_vs()
reg = insight.load_regressions()
store = ui.get_store()
uploads = store.list(status="approved")
cat = catalogue.table(catalogue.builtin(sites, prof, reg, bh, samples) + catalogue.contributed(uploads))

# ---- filters (one row above everything they filter) ------------------------------------------
this_year = config.today().year
dated = pd.to_numeric(cat["year_from"], errors="coerce").dropna()
y_min = int(min([config.SINCE_YEAR] + dated.tolist()))
present = set(cat["data_type"])
type_options = [t for t in config.DATA_TYPES if t in present] + sorted(present - set(config.DATA_TYPES))
with st.container(border=True):
    c1, c2, c3 = st.columns([1.3, 1.3, 1.5])
    text = c1.text_input("Search", placeholder="Title, source or method", key="cat_text")
    types = c2.multiselect("Data type", type_options, placeholder="All types", key="cat_types")
    regions = c3.multiselect("Region", catalogue.region_options(), placeholder="All boroughs and cities",
                             key="cat_regions", help="Boroughs and linked cities of the Montréal agglomeration "
                                                     "(City of Montréal open data). Island-wide datasets always match.")
    d1, d2, d3 = st.columns([1.5, 1.6, 1.3])
    since = f"Since {config.SINCE_YEAR}"
    span = d1.segmented_control("Years", ["All years", since, "Custom"], default="All years", key="cat_span") \
        or "All years"
    custom = d2.slider("Year range", y_min, this_year, (config.SINCE_YEAR, this_year), disabled=span != "Custom",
                       key="cat_years")
    years = None if span == "All years" else (config.SINCE_YEAR, this_year) if span == since else custom
    statuses = d3.multiselect("Values", sorted(cat["value_status"].dropna().unique()), placeholder="Any status",
                              key="cat_status")
    undated = d2.toggle("Undated too", value=True, disabled=years is None, key="cat_undated",
                        help="Keep datasets whose source gives no collection years.")

shown = cat[catalogue.matches(cat, types, regions, years, undated, statuses, text)]
keys = set(shown["key"])

# ---- what the filters leave ------------------------------------------------------------------
cover = catalogue.points_by_region(
    sites if "vs30_sites" in keys else sites.iloc[0:0], prof if "vs_profiles" in keys else prof.iloc[0:0],
    bh if "boreholes" in keys else bh.iloc[0:0],
    [u for u in uploads if f"up_{u.get('submission_id') or u['id']}" in keys])
if regions:
    cover = cover[cover["region"].isin(regions)]
d_years = shown.dropna(subset=["year_from"])
ui.kpis([
    (f"{len(shown)}", "Datasets shown", f"of {len(cat)}; {int((cat['origin'] == 'Contributed').sum())} contributed",
     ui.ACCENT),
    (f"{int(cover['n'].sum()):,}", "Located records", "boreholes, Vs sites, profiles and files", ui.CATEGORICAL[0]),
    (f"{shown['data_type'].nunique()}", "Data types", f"of {len(config.DATA_TYPES)} the atlas accepts", ui.CATEGORICAL[4]),
    (f"{int(d_years['year_from'].min())}–{int(d_years['year_to'].max())}" if not d_years.empty else "–",
     "Years covered", f"{len(shown) - len(d_years)} dataset(s) undated", ui.CATEGORICAL[3]),
], cols=4)
st.write("")

if shown.empty:
    st.info("No dataset matches these filters. Clear a filter, or add the data you have under Contribute data.",
            icon=":material/filter_alt_off:")
    st.page_link("views/contribute.py", label="Contribute data", icon=":material/upload_file:")
    st.stop()

# ---- list and details --------------------------------------------------------------------------
ui.panel_title(f"Datasets · {len(shown)}")
view = shown.assign(origin=shown.apply(lambda r: r["origin"] if r["available"] else "Not loaded yet", axis=1))
cols = ["title", "data_type", "where", "years", "records", "value_status", "source", "origin"]
if regions:  # how much of each dataset lies in the chosen regions
    in_sel = {"vs30_sites": (sites, "sites"), "vs_profiles": (prof, "readings"), "boreholes": (bh, "boreholes")}

    def here(r):
        if r["key"] in in_sel:
            df, word = in_sel[r["key"]]
            return f"{int(df['region'].isin(regions).sum()):,} {word}"
        if r["key"] == "samples":
            return f"{int(samples['hole_id'].isin(bh.loc[bh['region'].isin(regions), 'hole_id']).sum()):,} samples"
        if r["origin"] == "Contributed":
            return f"{len(r['files'])} file(s)"
        return "island-wide" if not r["regions"] else "–"
    view = view.assign(here=view.apply(here, axis=1))
    cols.insert(3, "here")
pick = st.dataframe(
    view[cols],
    hide_index=True, width="stretch", height=min(40 + 35 * len(view), 460), on_select="rerun",
    selection_mode="single-row", key="cat_table_" + str(abs(hash(tuple(view["key"])))),  # new list, fresh selection
    column_config={"title": st.column_config.TextColumn("Dataset", width="medium", pinned=True),
                   "data_type": "Type", "where": "Where", "here": "In chosen regions", "years": "Years",
                   "records": "Records (all)" if regions else "Records",
                   "value_status": "Values", "source": "Source", "origin": "Origin"})
st.markdown('<div class="gx-note">Click a row for its details and downloads. <b>Where</b> lists the boroughs and '
            'cities a dataset touches, found from its coordinates.</div>', unsafe_allow_html=True)

# Remember the picked dataset, not its row number: a filter change can shorten the table under a stale selection.
rows = [i for i in (pick.selection.rows if pick and pick.selection else []) if i < len(view)]
if rows:
    state["cat_pick"] = view.iloc[rows[0]]["key"]
entry = view[view["key"] == state["cat_pick"]].iloc[0] if state.get("cat_pick") in set(view["key"]) else view.iloc[0]


def frame_csv(df):
    """CSV of a table, cut to the chosen regions when there are any, and its row count. The CSV is written only when
    the button is pressed, not on every rerun."""
    if regions and "region" in df.columns:
        df = df[df["region"].isin(regions)]
    return (lambda: df.to_csv(index=False).encode("utf-8")), len(df)


st.write("")
right, charts = st.columns([1, 1.35], gap="large")
with right:
    ui.panel_title("Details")
    names = [r for r in entry["regions"] if r != config.OFF_ISLAND]
    where = html.escape(entry["where"]) + (f'<div class="gx-note">{html.escape(", ".join(names))}</div>'
                                           if len(names) > 1 else "")
    meta = [("Type", entry["data_type"]), ("Where", where), ("Years", entry["years"]), ("Records", entry["records"]),
            ("Source", entry["source"]), ("Method", entry["method"]), ("Licence", entry["licence"]),
            ("Access", entry["access"])]
    st.markdown(f'<div class="gx-detail-title">{html.escape(entry["title"])}</div>{ui.value_badge(entry["value_status"])}'
                f'<span class="gx-note">{html.escape(entry["origin"])}</span>'
                '<dl class="gx-meta">' + "".join(f"<dt>{k}</dt><dd>{v if k == 'Where' else html.escape(str(v or '–'))}</dd>"
                                                 for k, v in meta)
                + "</dl>" + (f'<div class="gx-note">{html.escape(entry["description"])}</div>'
                             if entry["description"] else ""), unsafe_allow_html=True)
    if isinstance(entry.get("url"), str) and entry["url"]:
        st.markdown(f'<div class="gx-note">Original: <a href="{html.escape(entry["url"])}">{html.escape(entry["source"])}'
                    '</a></div>', unsafe_allow_html=True)
    st.write("")
    k = entry["key"]
    suffix = f" ({len(regions)} region{'s' if len(regions) > 1 else ''})" if regions else ""
    tables = {"vs30_sites": (sites, "vs30_sites.csv"), "vs_profiles": (prof, "vs_profiles.csv"),
              "boreholes": (bh, "boreholes.csv"), "vs_regressions": (reg, "vs_regressions.csv")}
    if k in tables:
        df, name = tables[k]
        body, n = frame_csv(df)
        st.download_button(f"Download CSV · {n:,} rows{suffix}", body, file_name=name, mime="text/csv",
                           icon=":material/download:", type="primary", width="stretch", key=f"dl_{k}")
    elif k == "samples":
        holes = bh if not regions else bh[bh["region"].isin(regions)]
        def body():
            return samples[samples["hole_id"].isin(holes["hole_id"])].to_csv(index=False).encode("utf-8")
        st.download_button(f"Download CSV{suffix}", body, file_name="spt_samples.csv", mime="text/csv",
                           icon=":material/download:", type="primary", width="stretch", key="dl_samples")
    elif k == "regions":
        gj = geo.regions_geojson()
        if regions:
            gj = {**gj, "features": [f for f in gj["features"] if f["properties"]["region"] in regions]}
        st.download_button(f"Download GeoJSON · {len(gj['features'])} regions", json.dumps(gj, ensure_ascii=False),
                           file_name="montreal_regions.geojson", mime="application/geo+json",
                           icon=":material/download:", type="primary", width="stretch", key="dl_regions")
    elif k == "archive":
        st.info("The archive CSVs are not in the repository yet. Once data/boreholes.csv and data/spt_samples.csv "
                "are added, this entry fills in by itself.", icon=":material/hourglass_top:")
    else:
        for r in entry["files"]:
            if ui.can_download(r):
                st.download_button(f"{r['file_name']} · {(r.get('file_size') or 0) / 1e6:.2f} MB",
                                   partial(store.get_bytes, r), file_name=r["file_name"], mime=ui.mime_of(r),
                                   icon=":material/download:", width="stretch", key=f"dlf_{r['id']}")
            else:
                st.caption(f"{r['file_name']}: access is {r.get('access_level')}; ask a curator for a copy.")
    if entry["available"] and k != "vs_regressions":
        if st.button("Show on the map", icon=":material/map:", width="stretch", key="cat_to_map"):
            state["goto_regions"] = regions or entry["regions"] or []
            st.switch_page("views/explore.py")

    st.write("")
    with st.container(border=True, key="gxcard_add"):
        st.markdown('<div class="gx-card-title">Have data that is not here?</div><div class="gx-note">Logs, lab '
                    'sheets, CPT, geophysics, piezometers, monitoring, reports, maps or photos, from any year. Upload '
                    'it with a short description; a curator checks it before it appears.</div>',
                    unsafe_allow_html=True)
        st.page_link("views/contribute.py", label="Contribute data", icon=":material/upload_file:", width="stretch")

# ---- coverage ---------------------------------------------------------------------------------
with charts:
    ui.panel_title("Located records per region, for the datasets shown")
    if cover.empty:
        st.write("None of the datasets shown has located records.")
    else:
        order = cover.groupby("region")["n"].sum().sort_values(ascending=False).index.tolist()
        kinds_shown = [c for c in ui.COVERAGE_COLOURS if c in set(cover["kind"])]
        bars = alt.Chart(cover).mark_bar(height={"band": 0.72}, stroke=ui.SURFACE, strokeWidth=1.5).encode(
            y=alt.Y("region:N", sort=order, title=None, axis=alt.Axis(labelLimit=250, labelPadding=6)),
            x=alt.X("sum(n):Q", title="Located records", stack="zero"),
            color=alt.Color("kind:N", title=None, sort=kinds_shown,
                            scale=alt.Scale(domain=kinds_shown, range=[ui.COVERAGE_COLOURS[c] for c in kinds_shown]),
                            legend=alt.Legend(orient="bottom", columns=1, labelLimit=200,
                                              symbolType="square")),
            order=alt.Order("kind:N"),
            tooltip=[alt.Tooltip("region:N", title="Region"), alt.Tooltip("kind:N", title="Kind"),
                     alt.Tooltip("sum(n):Q", title="Records")])
        st.altair_chart(bars.properties(height=alt.Step(24), padding={"left": 40, "right": 8}), width="stretch")
        st.markdown('<div class="gx-note">A Vs profile counts once however many depths it has; a file counts once in '
                    'each region its footprint touches. Regions with nothing yet are where new data helps most.</div>',
                    unsafe_allow_html=True)
    st.write("")
    ui.panel_title("Years each dataset covers")
    if d_years.empty:
        st.write("No dated dataset among those shown.")
    else:
        t = d_years.assign(y0=d_years["year_from"].astype(int), y1=d_years["year_to"].astype(int) + 1)
        span_chart = alt.Chart(t).mark_bar(cornerRadius=4, height=14, color=ui.CATEGORICAL[0]).encode(
            x=alt.X("y0:Q", title="Year", scale=alt.Scale(domain=[min(1920, int(t["y0"].min())), this_year + 1]),
                    axis=alt.Axis(format="d", values=[y for y in range(1920, this_year + 1, 20) if abs(y - config.SINCE_YEAR) > 5]
                                  + [config.SINCE_YEAR])),
            x2="y1:Q", y=alt.Y("title:N", title=None, axis=alt.Axis(labelLimit=240, labelPadding=6)),
            tooltip=[alt.Tooltip("title:N", title="Dataset"), alt.Tooltip("years:N", title="Years")])
        rule = alt.Chart(pd.DataFrame({"x": [config.SINCE_YEAR]})).mark_rule(color=ui.INK_2, strokeDash=[4, 4]) \
            .encode(x="x:Q")
        dots = alt.Chart(t[t["y1"] - t["y0"] <= 1]).mark_point(filled=True, size=70, color=ui.CATEGORICAL[0],
                                                                 opacity=1).encode(x="y0:Q", y="title:N",
                                                                                   tooltip=["title", "years"])
        st.altair_chart((span_chart + dots + rule).properties(height=alt.Step(30), padding={"left": 40, "right": 8}),
                        width="stretch")
        st.markdown(f'<div class="gx-note">The dashed line marks {config.SINCE_YEAR}. Undated datasets '
                    f'({len(shown) - len(d_years)}) are not drawn.</div>', unsafe_allow_html=True)
