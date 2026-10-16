"""Explore: the map, a selection, what is in it, and one download."""
from functools import partial

import altair as alt
import folium
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import mapping
from streamlit_folium import st_folium

from geotech import bundle, config, data, geo, scene3d, terrain, ui
from geotech.config import PRE_MODERN_YEAR

# 3D view: what the ground is draped with, what shows behind it, and the column sizes
SURFACES = {
    "Light map": ui.esri_tiles("Canvas/World_Light_Gray_Base"),
    "Streets": ui.esri_tiles("World_Street_Map"),
    "Satellite": ui.esri_tiles("World_Imagery"),
    "Relief only": None,
}
BACKDROP = "app/static/blank_map_style.json"  # one flat colour behind the 3D view
PROFILE_RADIUS_M, VS30_RADIUS_M, BOREHOLE_RADIUS_M = 110, 110, 50
FAN_SPACING_M = 330  # profiles that share a position are spread this far apart


state = st.session_state
if "goto_regions" in state:  # sent here from the catalogue's "Show on the map"
    picked = [r for r in state.pop("goto_regions") if r in geo.region_names()]
    state["mode"], state["region_pick"] = ("Region", picked) if picked else ("Whole island", [])

ui.hero("Map and 3D",
        "Pick a borough or city, a spot, a drawn area or the whole island to see the boreholes, SPT samples, measured "
        "shear-wave velocities and contributed data there, then download them in one zip.",
        chips=["Coordinates <b>MTM 8</b> · EPSG:32188", "Vs30 <b>measured</b> and <b>estimated</b> kept apart",
               "Raw <b>N<sub>field</sub></b> kept · pre-1960 flagged"])

# ---- controls row, with the data filters behind a button at its end ------------------
controls = st.container(border=True)
c0, c1, c2, c3, c4 = controls.columns([1.0, 1.75, 1.3, 0.95, 0.62], vertical_alignment="bottom")
filters = c4.popover("Filters", icon=":material/tune:", width="stretch")

# ---- data ---------------------------------------------------------------------
with filters:
    eras = st.multiselect("Borehole era", ["pre-1960", "1960 and later", "undated"],
                          default=["pre-1960", "1960 and later", "undated"],
                          help=f"Before {PRE_MODERN_YEAR}, SPT N read about half of modern values.")
    show_far = st.toggle("Include Vs sites off the island", value=False,
                         help="The LM, PL and VM seismic lines (Laval and the South Shore) and the Rougemont area "
                              "lie outside the agglomeration.")
    demo = st.toggle("Demo boreholes", value=False, help="400 synthetic points for trying the app. Not real data.")

bh, samples, label = ui.load_archive(demo)
ui.archive_banner(label)
store = ui.get_store()
uploads = store.list(status="approved")
vs_sites, vs_prof = ui.load_vs()

if not bh.empty:
    bh = bh[bh["data_era"].isin(eras)]
    if "source" in bh.columns:
        src = bh["source"].fillna("not stated").astype(str)
        with filters:
            sources = sorted(src.unique())
            pick_src = st.multiselect("Borehole source", sources, default=sources)
        bh = bh[src.isin(pick_src)]
if not vs_sites.empty and not show_far:
    vs_sites, vs_prof = data.keep_on_island(vs_sites), data.keep_on_island(vs_prof)
if not vs_sites.empty:
    vs_sites = vs_sites.assign(site_class_from_measured=vs_sites["vs30_ms"].map(ui.nbcc_class).fillna("–"))

# ---- controls -------------------------------------------------------------------
with controls:
    view = c0.segmented_control("View", ["2D map", "3D relief"], default="2D map", key="view") or "2D map"
    is_3d = view == "3D relief"
    mode = c1.segmented_control("Area", ["Whole island", "Region", "Circle", "Draw"],
                                default="Whole island", key="mode", disabled=is_3d) or "Whole island"
    radius = 500
    picked = []
    if mode == "Region":
        picked = c2.multiselect("Boroughs and cities", geo.region_names(), key="region_pick", disabled=is_3d,
                                placeholder="Pick one or more")
    else:
        radius = c2.slider("Radius (m)", 100, 5000, 500, 100, disabled=mode != "Circle" or is_3d)
    colour_by = c3.selectbox("Colour boreholes by", ["Era", "Site class (estimated)"])
    e1, e2, e3, e4, e5 = st.columns([1.6, 1.0, 0.95, 0.95, 0.95], vertical_alignment="bottom")
    layers = e1.pills("Layers", ["Boreholes", "Measured Vs30", "Files"], selection_mode="multi",
                      default=["Boreholes", "Measured Vs30", "Files"], key="layers")
    hint = {"Circle": "Click the map to place the centre of the circle.",
            "Region": "Pick boroughs or linked cities above. Their limits are dashed on the map; hover one for its name.",
            "Draw": "Use the rectangle or polygon tool at the top left of the map.",
            "Whole island": "Everything on the island is selected."}[mode]
    if is_3d:
        hint = ("3D view: drag to pan, right-drag (or Ctrl-drag) to tilt and rotate, scroll to zoom. "
                "Switch to 2D map to change the selection.")
        surface = e2.selectbox("Surface", list(SURFACES), key="surface")
        exaggeration = e3.slider("Relief stretch", 1, 15, 6,
                                 help="Montréal is fairly flat (Mont Royal is about 230 m), so relief is stretched "
                                      "to be visible.")
        depth_stretch = e4.slider("Depth stretch", 5, 80, 30,
                                  help="Depths below the ground are drawn this many times deeper than they are, so a "
                                       "30 m profile can be seen at the scale of the island.")
        ground_pct = e5.slider("Ground opacity", 10, 100, 25, 5, format="%d%%",
                               help="The ground is see-through so what hangs below it shows. Lower it to see the "
                                    "profiles and boreholes better, raise it to read the map.")
    st.markdown(f'<div class="gx-note">{hint}</div>', unsafe_allow_html=True)

area = data.selection_from_inputs({"Circle": "Point and radius", "Draw": "Draw an area"}.get(mode, mode),
                                  state.get("drawing"), picked if mode == "Region" else state.get("click"), radius)

# ---- map ------------------------------------------------------------------------
def build_map():
    m = ui.base_map((45.55, -73.68), 11)
    if area not in (None, "incomplete"):  # keep the selection in view; a 500 m circle is a dot at island zoom
        x0, y0, x1, y1 = area.bounds  # MTM 8 metres
        pad = max(300.0, 0.15 * max(x1 - x0, y1 - y0))
        (lon0, lat0), (lon1, lat1) = geo.mtm8_to_wgs84(x0 - pad, y0 - pad), geo.mtm8_to_wgs84(x1 + pad, y1 + pad)
        m.fit_bounds([[lat0, lon0], [lat1, lon1]])
    else:
        b = config.ISLAND_BBOX
        m.fit_bounds([[b["lat_min"], b["lon_min"]], [b["lat_max"], b["lon_max"]]])
    ui.add_regions(m, picked if mode == "Region" else (), interactive=mode in ("Region", "Whole island"))

    if "Boreholes" in (layers or []) and not bh.empty:
        def colour(row):
            if colour_by == "Era":
                return ui.ERA_COLOURS.get(row["data_era"], ui.ERA_COLOURS["undated"])
            return ui.SITE_CLASS_COLOURS.get(str(row.get("site_class", ""))[:1], ui.ERA_COLOURS["undated"])
        tip_labels = {"hole_id": "Hole", "year": "Year", "source": "Source", "data_era": "Era",
                      "vs30_ms": "Vs30, ESTIMATED from lithology (m/s)", "site_class": "Site class (ESTIMATED)"}
        tip_cols = [c for c in tip_labels if c in bh.columns]
        feats = []
        for rec in bh.assign(_c=bh.apply(colour, axis=1))[tip_cols + ["lon", "lat", "_c"]].to_dict("records"):
            props = {c: (None if pd.isna(rec[c]) else str(rec[c])) for c in tip_cols}
            props["_c"] = rec["_c"]
            feats.append({"type": "Feature", "properties": props,
                          "geometry": {"type": "Point", "coordinates": [rec["lon"], rec["lat"]]}})
        folium.GeoJson({"type": "FeatureCollection", "features": feats}, name="Boreholes",
                       marker=folium.CircleMarker(radius=3, weight=0, fill=True, fill_opacity=0.9),
                       style_function=lambda f: {"fillColor": f["properties"]["_c"], "color": f["properties"]["_c"]},
                       tooltip=folium.GeoJsonTooltip(fields=tip_cols, aliases=[tip_labels[c] for c in tip_cols])
                       ).add_to(m)

    if "Measured Vs30" in (layers or []) and not vs_sites.empty:
        fg = folium.FeatureGroup(name="Measured Vs30 sites").add_to(m)
        for r in vs_sites.to_dict("records"):
            has = pd.notna(r["vs30_ms"])
            fill = ui.SITE_CLASS_COLOURS.get(r["site_class_from_measured"], ui.SURFACE) if has else ui.SURFACE
            head = f"<b>{ui.safe_tip(r['site_id'])}</b> · {ui.safe_tip(r['area'])}<br>"
            tip = head + (f"Vs30 {r['vs30_ms']:.0f} m/s (measured), class {r['site_class_from_measured']}<br>"
                          f"{ui.safe_tip(r['survey_type'])}" if has else "no Vs30 value in the source")
            folium.CircleMarker([r["lat"], r["lon"]], radius=6, color="#ffffff" if has else ui.VS_COLOUR, weight=1.6,
                                fill=True, fill_color=fill, fill_opacity=0.95, tooltip=tip).add_to(fg)

    if "Files" in (layers or []) and uploads:
        fg = folium.FeatureGroup(name="Contributed files").add_to(m)
        for r in uploads:
            folium.Marker([r["lat"], r["lon"]], tooltip=ui.safe_tip(f"{r['data_type']}: {r['title']}"),
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
    items = "".join(
        f'<div style="display:flex;align-items:center;gap:7px;margin:2px 0">'
        f'<span style="width:10px;height:10px;border-radius:50%;background:{c};'
        f'{"border:2px solid #fff;box-shadow:0 0 0 1px " + c + ";" if kind == "ring" else ""}'
        f'{"border-radius:50% 50% 50% 0;transform:rotate(-45deg);" if kind == "pin" else ""}"></span>{t}</div>'
        for c, t, kind in rows)
    return ('<div style="position:absolute;bottom:44px;left:10px;z-index:800;background:rgba(255,255,255,0.95);'
            f'padding:10px 13px;border-radius:12px;font:12px/1.4 Inter,system-ui,sans-serif;color:{ui.INK};'
            'border:1px solid #dbe4ec;box-shadow:0 8px 24px rgba(15,27,45,0.12)">'
            f'<div style="font:500 10px/1.2 \'JetBrains Mono\',monospace;letter-spacing:.2em;color:{ui.MUTED};'
            'text-transform:uppercase;margin-bottom:6px">Legend</div>'
            + items + f'<div style="margin-top:6px;color:{ui.INK_2}">Vs30 site fill = NBCC class</div>'
            f'<div style="margin-top:3px">{ui.class_chips_html()}</div>'
            '<div style="display:flex;align-items:center;gap:7px;margin-top:7px"><span style="width:16px;height:0;'
            'border-top:1.5px dashed #5b7083"></span>Borough or city limit</div></div>')


def rgb(hex_colour, alpha=235):
    h = hex_colour.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def band_colour(vs):
    return rgb(ui.SITE_CLASS_COLOURS.get(scene3d.vs_band(vs) or "", ui.ERA_COLOURS["undated"]), 255)


def build_3d():
    """Terrain from AWS Terrain Tiles, made see-through, with each measurement hanging below the ground to the depth
    it describes. Things below the surface are drawn first and the ground last, so the ground tints them instead of
    hiding them."""
    ex, dx = float(exaggeration), float(depth_stretch)
    below, on_top = [], []

    def ground(df):
        return np.nan_to_num(terrain.elevation(df["lon"].to_numpy(), df["lat"].to_numpy()), nan=0.0) * ex

    def hang(df, top_m, bot_m):
        """Columns stand on their base, so the base goes at the bottom of the interval."""
        g = ground(df)
        return df.assign(gz=g, z=g - np.asarray(bot_m, dtype=float) * dx,
                         h=np.maximum((np.asarray(bot_m, dtype=float) - np.asarray(top_m, dtype=float)) * dx, 0.5))

    def column(df, radius, **kw):
        return pdk.Layer("ColumnLayer", df[["lon", "lat", "z", "h", "fill", "t1", "t2", "t3"]],
                         get_position=["lon", "lat", "z"], get_elevation="h", elevation_scale=1, radius=radius,
                         disk_resolution=16, extruded=True, get_fill_color="fill", pickable=True, auto_highlight=True,
                         material=False, **kw)  # unlit, so the colour of each band reads true through the ground

    def disc(df, radius, fill, line, line_px):
        return pdk.Layer("ScatterplotLayer", df[["lon", "lat", "z", "t1", "t2", "t3"] + (["fill"] if fill == "fill" else [])],
                         get_position=["lon", "lat", "z"], get_radius=radius, radius_min_pixels=4,
                         get_fill_color=fill, stroked=True, get_line_color=line, get_line_width=line_px,
                         line_width_units='"pixels"', pickable=True, auto_highlight=True)

    lift = 3 * ex + 4  # surface marks sit just above the ground they mark
    if "Measured Vs30" in (layers_on or []):
        seg = scene3d.fan_out(scene3d.profile_segments(vs_prof), "site_id", FAN_SPACING_M) if not vs_prof.empty else pd.DataFrame()
        if not seg.empty:
            seg = hang(seg, seg["top_m"], seg["bot_m"])
            seg["fill"] = [band_colour(v) for v in seg["vs_ms"]]
            seg["t1"] = seg["site_id"].astype(str) + " · Vs profile"
            seg["t2"] = seg.apply(lambda r: f"{r.depth_m:g} m deep: Vs {r.vs_ms:.0f} m/s (measured"
                                            f"{', ' + str(r.method).lower() if isinstance(r.method, str) else ''})", axis=1)
            seg["t3"] = (seg["soil_type"].fillna("").astype(str)
                         + np.where(seg["shared_position"], " · drawn beside its true position, which it shares", ""))
            ends = seg.groupby(scene3d.PROFILE).agg(lon=("lon", "first"), lat=("lat", "first"), gz=("gz", "first"),
                                                    deepest=("bot_m", "max"))
            ends["src"] = [[x, y, z] for x, y, z in zip(ends["lon"], ends["lat"], ends["gz"])]
            ends["dst"] = [[x, y, z - d * dx] for x, y, z, d in zip(ends["lon"], ends["lat"], ends["gz"], ends["deepest"])]
            # a thin grey line from the surface to the deepest reading; it shows where a profile has no reading
            below.append(pdk.Layer("LineLayer", ends[["src", "dst"]], get_source_position="src",
                                   get_target_position="dst", get_color=[110, 124, 140, 255], get_width=1.5,
                                   width_units='"pixels"'))
            below.append(column(seg, PROFILE_RADIUS_M))
        if not vs_sites.empty:
            v = vs_sites.dropna(subset=["vs30_ms"]).copy()
            v["fill"] = [rgb(ui.SITE_CLASS_COLOURS.get(c, ui.ERA_COLOURS["undated"]), 255)
                         for c in v["site_class_from_measured"]]
            v["t1"] = v["site_id"].astype(str) + " · " + v["area"].astype(str)
            v["t2"] = v.apply(lambda r: f"Vs30 {r.vs30_ms:.0f} m/s (measured), class {r.site_class_from_measured}", axis=1)
            has_profile = v["site_id"].isin(seg["site_id"]) if not seg.empty else pd.Series(False, index=v.index)
            v["t3"] = np.where(has_profile, "Its Vs profile hangs below.",
                               f"No profile here: the column shows the top {scene3d.VS30_DEPTH_M} m that Vs30 averages over.")
            sticks = v[~has_profile]
            if not sticks.empty:
                below.append(column(hang(sticks, 0.0, float(scene3d.VS30_DEPTH_M)), VS30_RADIUS_M))
            v["z"] = ground(v) + lift
            on_top.append(disc(v, 170, "fill", [255, 255, 255, 255], 2))
    if "Boreholes" in (layers_on or []) and not bh.empty:
        b = bh.copy()
        b["depth"] = scene3d.borehole_depths(b, samples).to_numpy()
        sc = b["site_class"] if "site_class" in b.columns else pd.Series("", index=b.index)
        b["fill"] = [rgb(ui.ERA_COLOURS.get(e, ui.ERA_COLOURS["undated"]) if colour_by == "Era"
                         else ui.SITE_CLASS_COLOURS.get(str(c)[:1], ui.ERA_COLOURS["undated"]), 255)
                     for e, c in zip(b["data_era"], sc)]
        b["t1"] = b["hole_id"].astype(str)
        b["t2"] = b["data_era"].astype(str) + np.where(b["depth"].notna(),
                                                       " · drilled to " + b["depth"].round(1).astype(str) + " m",
                                                       " · depth not recorded")
        b["t3"] = ("Site class " + sc.fillna("–").astype(str) + " (estimated)") if colour_by != "Era" else ""
        deep = b[b["depth"].notna()]
        if not deep.empty:
            below.append(column(hang(deep, 0.0, deep["depth"]), BOREHOLE_RADIUS_M))
        flat = b[b["depth"].isna()].copy()
        if not flat.empty:  # no depth to hang: a dot on the surface
            flat["z"] = ground(flat) + lift
            on_top.append(disc(flat, 70, "fill", [255, 255, 255, 255], 1))
    if "Files" in (layers_on or []) and uploads:
        f = pd.DataFrame([{"lon": r["lon"], "lat": r["lat"], "t1": r["title"], "t2": r["data_type"],
                           "t3": "Contributed file (no depth recorded)"} for r in uploads])
        f["z"] = ground(f) + lift
        on_top.append(disc(f, 150, [255, 255, 255, 255], rgb(ui.UPLOAD_COLOUR, 255), 3))
    if area not in (None, "incomplete"):
        shp = geo.shp_transform_to_wgs84(area)
        paths = []
        for poly in getattr(shp, "geoms", [shp]):  # a region pick can be several polygons
            ring = np.asarray(poly.exterior.coords)
            zr = np.nan_to_num(terrain.elevation(ring[:, 0], ring[:, 1]), nan=0.0) * ex + lift
            paths.append({"path": [[x, y, z] for (x, y), z in zip(ring, zr)]})
        # pydeck reads a bare string as a data field; quoted, it is passed through as the value "pixels".
        on_top.append(pdk.Layer("PathLayer", paths, get_path="path", get_color=rgb(ui.ACCENT_DARK, 255), get_width=4,
                                width_units='"pixels"'))
    ground_layer = pdk.Layer(
        "TerrainLayer",
        elevation_decoder={"rScaler": 256 * ex, "gScaler": ex, "bScaler": ex / 256, "offset": -32768 * ex},
        elevation_data=terrain.TERRARIUM_URL,
        texture=SURFACES[surface], color=[176, 196, 212], max_zoom=14, opacity=ground_pct / 100,
    )
    view_state = pdk.ViewState(latitude=45.535, longitude=-73.62, zoom=11.0, pitch=58, bearing=-28, max_pitch=80)
    # a plain backdrop, not a basemap: seen through the ground, a basemap would be a second, flat copy of the map
    return pdk.Deck(layers=below + on_top + [ground_layer], initial_view_state=view_state, map_style=BACKDROP,
                    map_provider=None, tooltip={"html": "<b>{t1}</b><br/>{t2}<br/>{t3}", "style": {"fontSize": "12px"}})


def band_key_html():
    """Swatches for the velocity bands, softest (darkest) first."""
    return '<span style="display:inline-flex;flex-wrap:wrap;gap:4px 10px;vertical-align:middle">' + "".join(
        f'<span style="display:inline-flex;align-items:center;gap:4px;white-space:nowrap">'
        f'<span style="width:12px;height:12px;border-radius:3px;background:{ui.SITE_CLASS_COLOURS[k]}"></span>'
        f'{scene3d.VS_BAND_LABELS[k]}</span>' for k in "EDCBA") + " m/s</span>"


layers_on = layers
left, right = st.columns([2.35, 1], gap="medium")
out = None
with left:
    if is_3d:
        st.pydeck_chart(build_3d(), height=640, width="stretch")
        key3d = ("blue = 1960 and later, orange = pre-1960, grey = undated" if colour_by == "Era"
                 else "estimated site class, light (A) to dark (E)")
        st.markdown(
            '<div class="gx-note">The ground is see-through and every measurement hangs below it to the depth it '
            f'describes. <b>Vs profiles</b> are coloured by the velocity measured at each depth: {band_key_html()}; '
            'the thin grey line shows depths with no reading. A <b>measured Vs30 site</b> is the disc on the surface, '
            f'in its NBCC class colour {ui.class_chips_html()}; where it has no profile, a column in the same colour '
            f'shows the top {scene3d.VS30_DEPTH_M} m that Vs30 averages over. <b>Boreholes</b> hang to their drilled '
            f'depth ({key3d}). Green rings are contributed files, which carry no depth. Profiles that share one '
            'position are fanned out around it. Terrain: AWS Terrain Tiles (SRTM and other public DEMs), relief '
            f'stretched {exaggeration}×, depths stretched {depth_stretch}×, for display only.</div>',
            unsafe_allow_html=True)
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
    else (picked[0] if len(picked) == 1 else f"{len(picked)} regions") if mode == "Region"
    else f"drawn area ({area.area / 1e6:.2f} km²)")

with right:
    ui.panel_title(f"In this selection · {area_label}")
    n_pre = int((sel_bh["data_era"] == "pre-1960").sum()) if not sel_bh.empty else 0
    n_ref = int(sel_s["refusal"].sum()) if "refusal" in sel_s.columns else 0
    vs_med = sel_vs["vs30_ms"].median() if not sel_vs.empty else None
    ui.kpis([
        (f"{len(sel_bh):,}", "Boreholes", f"{n_pre:,} pre-1960", ui.ERA_COLOURS["1960 and later"]),
        (f"{len(sel_s):,}", "SPT samples", f"{n_ref:,} refusals (censored)", ui.ACCENT),
        (f"{int(sel_vs['vs30_ms'].notna().sum()) if not sel_vs.empty else 0:,}", "Sites with measured Vs30",
         (f"median {vs_med:.0f} m/s" if vs_med == vs_med and vs_med is not None else "no values")
         + (f"; {int(sel_vs['vs30_ms'].isna().sum())} more without a value" if not sel_vs.empty
            and sel_vs["vs30_ms"].isna().any() else ""), ui.VS_COLOUR),
        (f"{len(sel_up):,}", "Contributed files", "approved by a curator", ui.UPLOAD_COLOUR),
    ])

    vs_vals = sel_vs.dropna(subset=["vs30_ms"])
    if not vs_vals.empty:
        ui.panel_title("Measured Vs30 distribution")
        chart = alt.Chart(vs_vals).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2, binSpacing=0,
                                            stroke=ui.SURFACE, strokeWidth=1).encode(
            x=alt.X("vs30_ms:Q", bin=alt.Bin(step=100), title="Vs30 (m/s, measured)",
                  axis=alt.Axis(labelOverlap="greedy", labelSeparation=6, format="d", labelFlush=True)),
            y=alt.Y("count():Q", title="Sites", axis=alt.Axis(tickMinStep=1, format="d")),
            color=alt.Color("site_class_from_measured:N", title="Class", legend=None,
                            scale=alt.Scale(domain=list("ABCDE"), range=[ui.SITE_CLASS_COLOURS[k] for k in "ABCDE"])),
            tooltip=[alt.Tooltip("count():Q", title="Sites"), alt.Tooltip("site_class_from_measured:N", title="Class")],
        ).properties(height=230)
        st.altair_chart(chart, width="stretch")
        st.markdown(f'<div class="gx-note">Bar colour = NBCC class {ui.class_chips_html()}</div>',
                    unsafe_allow_html=True)

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
    if st.button("Prepare zip", icon=":material/folder_zip:", width="stretch"):
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
n_with = int(sel_vs["vs30_ms"].notna().sum()) if not sel_vs.empty else 0
n_without = len(sel_vs) - n_with
tv, tb, ts, tf = st.tabs([f"Measured Vs · {n_with} sites" + (f" (+{n_without} without Vs30)" if n_without else ""),
                          f"Boreholes · {len(sel_bh):,}",
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
            shown_vs = sel_vs.assign(_none=sel_vs["vs30_ms"].isna()).sort_values(["_none", "site_id"])
            st.dataframe(shown_vs[["site_id", "area", "region", "survey_type", "vs30_ms", "site_class_from_measured",
                                   "f0_hz", "x_mtm8", "y_mtm8", "qa_flags"]],
                         hide_index=True, width="stretch", height=380,
                         column_config={"site_id": "Site", "area": "Area", "survey_type": "Survey", "qa_flags": "Flags",
                                        "vs30_ms": st.column_config.NumberColumn("Vs30 (m/s)", format="%.0f"),
                                        "site_class_from_measured": "Class", "region": "Region (derived)",
                                        "f0_hz": st.column_config.NumberColumn("f0 (Hz)", format="%.2f"),
                                        "x_mtm8": st.column_config.NumberColumn("X MTM8", format="%.0f"),
                                        "y_mtm8": st.column_config.NumberColumn("Y MTM8", format="%.0f")})
            if n_without:
                st.markdown(f'<div class="gx-note">{n_without} site{"s" if n_without > 1 else ""} at the end of the list '
                            'have no Vs30 value in the source; they are kept but left out of every statistic.</div>',
                            unsafe_allow_html=True)
        with b:
            if sel_prof.empty:
                st.write("No Vs-depth profiles here.")
            else:
                ids = sorted(sel_prof["site_id"].unique())
                pick = st.selectbox("Vs-depth profile", ids, help="Sites and seismic lines with depth profiles.")
                p = sel_prof[sel_prof["site_id"] == pick].sort_values("depth_m")
                base = alt.Chart(p).encode(
                    x=alt.X("vs_ms:Q", title="Vs (m/s)", axis=alt.Axis(labelOverlap="greedy", labelSeparation=6)),
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
        y0, y1 = data.upload_years(r)
        when = "undated" if y0 is None else str(y0) if y0 == y1 else f"{y0}–{y1}"
        with st.expander(f"{r['data_type']} · {r['title']} ({when})", icon=":material/description:"):
            st.write(f"**Source:** {r.get('source_org')} · {r.get('original_reference') or ''}  \n"
                     f"**Where:** {', '.join(data.upload_regions(r)) or 'not located'}  \n"
                     f"**Values:** {r.get('value_status')} · **Licence:** {r.get('licence')} · "
                     f"**Access:** {r.get('access_level') or 'Public'}  \n"
                     f"**File:** {r['file_name']} ({(r.get('file_size') or 0) / 1e6:.2f} MB) · uploaded {r.get('uploaded_at')}")
            if r.get("data_era") == "pre-1960":
                st.warning("Pre-1960 work: SPT N read about half of modern values.")
            if ui.can_download(r):
                st.download_button("Download this file", partial(store.get_bytes, r), file_name=r["file_name"],
                                   mime=ui.mime_of(r), key=f"dl_{r['id']}")
            else:
                st.caption("Listed only: its access level is not Public. Ask a curator for a copy.")
