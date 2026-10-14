"""Contribute data: place it on the map, describe it once, add one or more files, run the checks."""
import html
import mimetypes

import folium
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import Point, shape
from streamlit_folium import st_folium

from geotech import config, geo, ui, validate
from geotech.data import era_label
from geotech.storage import new_id, now_iso

ui.hero("Contribute data",
        "Whatever ground data you have for Montréal, from any year: borehole logs, SPT or CPT, lab sheets, "
        "geophysics, piezometer readings, monitoring, reports, GIS layers, scans or photos. Files are stored "
        "unchanged, checked automatically and shown once a curator approves them.",
        chips=["1 · Place it on the map", "2 · Describe it once", "3 · Add one or more files",
               "4 · Automatic checks", "5 · Curator review"])
store = ui.get_store()
ui.storage_banner(store)
state = st.session_state

# ---- 1. location ---------------------------------------------------------------
st.subheader(":material/pin_drop: 1. Where was it collected?")
how = st.radio("Place it by", ["Clicking or drawing on the map", "Typing coordinates", "An existing hole ID"],
               horizontal=True)
footprint = None  # shapely geometry, MTM 8

if how == "Clicking or drawing on the map":
    m = ui.base_map((45.55, -73.70), 11, layers=("Light", "Streets", "Satellite"))
    ui.add_regions(m, interactive=False)
    Draw(export=False, draw_options={"polyline": True, "circlemarker": False, "circle": False}).add_to(m)
    g = state.get("up_geom")
    if g and g["type"] == "Point":
        folium.Marker(g["coordinates"][::-1], icon=ui.target_icon(), tooltip="This location").add_to(m)
    elif g:
        folium.GeoJson(g, style_function=lambda f: {"color": ui.ACCENT_DARK, "fillColor": ui.ACCENT,
                                                    "fillOpacity": 0.15, "weight": 2.5}).add_to(m)
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    out = st_folium(m, height=420, use_container_width=True, returned_objects=["last_active_drawing", "last_clicked"])
    picked = None
    if out and out.get("last_active_drawing"):
        picked = out["last_active_drawing"]["geometry"]
    elif out and out.get("last_clicked"):
        picked = {"type": "Point", "coordinates": [out["last_clicked"]["lng"], out["last_clicked"]["lat"]]}
    if picked and picked != state.get("up_geom"):
        state["up_geom"] = picked
        st.rerun()  # redraw the map with the new location on it
    if state.get("up_geom"):
        footprint = geo.geom_wgs84_to_mtm8(shape(state["up_geom"]))
    st.caption("Click once for a point, or use the marker, line, rectangle or polygon tools (top left) for a site, "
               "a survey line or a whole study area.")
elif how == "Typing coordinates":
    crs = st.radio("Coordinates in", ["MTM zone 8 (EPSG:32188), metres", "Latitude / longitude (WGS84)"], horizontal=True)
    c1, c2 = st.columns(2)
    if crs.startswith("MTM"):
        x = c1.number_input("X (easting, m)", value=0.0, format="%.2f")
        y = c2.number_input("Y (northing, m)", value=0.0, format="%.2f")
        if x and y:
            footprint = Point(x, y)
    else:
        lat = c1.number_input("Latitude", value=0.0, format="%.6f")
        lon = c2.number_input("Longitude (negative, west)", value=0.0, format="%.6f")
        if lat and lon:
            footprint = Point(*geo.wgs84_to_mtm8(lon, lat))
else:
    bh, _, label = ui.load_archive(False)
    hid = st.text_input("Hole ID as in the archive")
    if hid:
        hit = bh[bh["hole_id"] == hid.strip()] if not bh.empty else bh
        if len(hit):
            footprint = Point(float(hit.iloc[0]["x_mtm8"]), float(hit.iloc[0]["y_mtm8"]))
            st.success(f"Found {hid} in the {label}.")
        else:
            st.error("No such hole ID in the archive.")

regions = geo.regions_touching(footprint) if footprint is not None else []
if footprint is not None:
    st.markdown(f'<div class="gx-note">Location (MTM 8): {footprint.centroid.x:,.1f} E, {footprint.centroid.y:,.1f} N · '
                f'{footprint.geom_type} · <b>Region:</b> {html.escape(", ".join(regions) or "unknown")} '
                '(derived from the location and the City\'s limits)</div>', unsafe_allow_html=True)

# ---- 2. description and files ----------------------------------------------------------
st.subheader(":material/description: 2. Describe it and add the files")
with st.form("upload"):
    c1, c2 = st.columns(2)
    title = c1.text_input("Title *", placeholder="e.g. CPTu soundings, Turcot interchange, 2010–2012")
    data_type = c2.selectbox("Data type *", config.DATA_TYPES,
                             help="Pick the closest; say more in the notes. Use Other if nothing fits.")
    source_org = c1.selectbox("Source organisation *", config.SOURCE_ORGS)
    original_reference = c2.text_input("Original report or project number")
    y1, y2 = c1.columns(2)
    work_year = y1.number_input("Collected in (year) *", min_value=1850, max_value=2100, value=None, step=1)
    work_year_end = y2.number_input("Until (if several years)", min_value=1850, max_value=2100, value=None, step=1)
    value_status = c2.selectbox("Values in these files are *", config.VALUE_STATUS,
                                help="Measured in the field or lab, derived from measurements, interpolated, or estimated.")
    licence = c1.selectbox("Licence *", config.LICENCES)
    access_level = c2.selectbox("Who may download it", config.ACCESS_LEVELS,
                                help="Registered users and Restricted files are listed in the catalogue but not served "
                                     "until sign-in is set up; a curator can share them on request.")
    uploaded_by = c1.text_input("Your name and organisation *")
    notes = c2.text_area("Notes (method, equipment, datum, anything a user should know)")
    files = st.file_uploader("Files * (one or more; any format)", accept_multiple_files=True,
                             help="Up to 50 MB each. For a larger file, put a link to it in the notes.")
    submitted = st.form_submit_button("Check and submit", type="primary", icon=":material/task_alt:")

if submitted:
    missing = [n for n, v in [("files", files), ("title", title), ("year", work_year), ("your name", uploaded_by)] if not v]
    if missing:
        st.error("Please fill in: " + ", ".join(missing) + ".")
        st.stop()
    if work_year_end and work_year_end < work_year:
        st.error("The last year is before the first year.")
        st.stop()
    hashes = {r["sha256"]: r["id"] for r in store.list()}
    checked = []
    for f in files:
        data = f.getvalue()
        report, digest = validate.check_upload(data, f.name, footprint, work_year, hashes)
        hashes.setdefault(digest, f"{f.name}, earlier in this submission")
        checked.append((f, data, report, digest))

    st.subheader("Check report")
    for f, _, report, _ in checked:
        bad = any(level == "block" for level, _ in report)
        with st.expander(f"{f.name} · {'blocked' if bad else 'passed'}", expanded=bad,
                         icon=":material/error:" if bad else ":material/check_circle:"):
            for level, msg in report:
                {"block": st.error, "warn": st.warning, "ok": st.success}[level](msg)
    if any(level == "block" for _, _, report, _ in checked for level, _ in report):
        st.error("Nothing was submitted. Fix the blocked files above (or leave them out) and try again.")
        st.stop()

    c = footprint.centroid
    lon, lat = geo.mtm8_to_wgs84(c.x, c.y)
    submission = new_id()
    for f, data, report, digest in checked:
        record = {
            "id": new_id(), "submission_id": submission, "title": title.strip(), "data_type": data_type,
            "file_name": f.name, "file_size": len(data), "mime": f.type or mimetypes.guess_type(f.name)[0],
            "sha256": digest, "source_org": source_org, "original_reference": original_reference.strip() or None,
            "work_year": int(work_year), "work_year_end": int(work_year_end) if work_year_end else None,
            "data_era": era_label(work_year), "value_status": value_status, "licence": licence,
            "access_level": access_level, "notes": notes.strip() or None,
            "uploaded_by": uploaded_by.strip(), "uploaded_at": now_iso(),
            "geom_type": "point" if footprint.geom_type == "Point" else "area",
            "x_mtm8": round(c.x, 2), "y_mtm8": round(c.y, 2), "lon": round(lon, 6), "lat": round(lat, 6),
            "footprint_wkt_mtm8": footprint.wkt, "region": "; ".join(regions), "status": "pending",
            "check_report": [{"level": lv, "message": ms} for lv, ms in report],
        }
        store.add(record, data)
    state.pop("up_geom", None)
    st.success(f"Submitted {len(checked)} file{'s' if len(checked) > 1 else ''}. A curator will review "
               f"{'them' if len(checked) > 1 else 'it'}; approved data appears in the catalogue and on the map.")
