"""Contribute a file: place it on the map, fill the metadata card, run the checks."""
import mimetypes

import folium
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import Point, shape
from streamlit_folium import st_folium

from geotech import config, geo, ui, validate
from geotech.data import era_label
from geotech.storage import new_id, now_iso

st.set_page_config(page_title="Upload · Montréal geotechnical data", page_icon="📤", layout="wide")
st.title("Contribute a file")
st.caption("Any file type: borehole logs, lab sheets, reports, scans, GIS files, photos. "
           "The original is stored unchanged. A curator approves it before it appears on the map.")
store = ui.get_store()
ui.storage_banner(store)
state = st.session_state

# ---- 1. location ---------------------------------------------------------------
st.subheader("1. Where is it?")
how = st.radio("Place it by", ["Clicking or drawing on the map", "Typing coordinates", "An existing hole ID"],
               horizontal=True)
footprint = None  # shapely geometry, MTM 8

if how == "Clicking or drawing on the map":
    m = folium.Map(location=[45.55, -73.70], zoom_start=11)
    Draw(export=False, draw_options={"polyline": True, "circlemarker": False, "circle": False}).add_to(m)
    if state.get("up_geom"):
        folium.GeoJson(state["up_geom"]).add_to(m)
    out = st_folium(m, height=420, use_container_width=True, returned_objects=["last_active_drawing", "last_clicked"])
    if out and out.get("last_active_drawing"):
        state["up_geom"] = out["last_active_drawing"]["geometry"]
    elif out and out.get("last_clicked"):
        state["up_geom"] = {"type": "Point", "coordinates": [out["last_clicked"]["lng"], out["last_clicked"]["lat"]]}
    if state.get("up_geom"):
        footprint = geo.geom_wgs84_to_mtm8(shape(state["up_geom"]))
    st.caption("Click once for a point, or use the marker, line, rectangle or polygon tools (top left).")
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

if footprint is not None:
    st.caption(f"Location (MTM 8): {footprint.centroid.x:,.1f} E, {footprint.centroid.y:,.1f} N · {footprint.geom_type}")

# ---- 2. file and metadata card ----------------------------------------------------
st.subheader("2. File and description")
with st.form("upload"):
    f = st.file_uploader("File", accept_multiple_files=False)
    c1, c2 = st.columns(2)
    title = c1.text_input("Title *", placeholder="e.g. Borehole logs, Rue Sherbrooke sewer, 1964")
    data_type = c2.selectbox("Data type *", config.DATA_TYPES)
    source_org = c1.selectbox("Source organisation *", config.SOURCE_ORGS)
    original_reference = c2.text_input("Original report or project number")
    work_year = c1.number_input("Year the work was done *", min_value=1850, max_value=2100, value=None, step=1)
    value_status = c2.selectbox("Values in this file are *", config.VALUE_STATUS,
                                help="Measured in the field or lab, derived from measurements, interpolated, or estimated.")
    licence = c1.selectbox("Licence *", config.LICENCES)
    access_level = c2.selectbox("Who may download it", config.ACCESS_LEVELS)
    uploaded_by = c1.text_input("Your name and organisation *")
    notes = c2.text_area("Notes (method, datum, anything a user should know)")
    submitted = st.form_submit_button("Check and submit")

if submitted:
    missing = [n for n, v in [("file", f), ("title", title), ("year", work_year), ("your name", uploaded_by)] if not v]
    if missing:
        st.error("Please fill in: " + ", ".join(missing) + ".")
        st.stop()
    data = f.getvalue()
    hashes = {r["sha256"]: r["id"] for r in store.list()}
    report, digest = validate.check_upload(data, f.name, footprint, work_year, hashes)

    st.subheader("Check report")
    for level, msg in report:
        {"block": st.error, "warn": st.warning, "ok": st.success}[level](msg)
    if any(level == "block" for level, _ in report):
        st.error("Not submitted. Fix the blocking items above and try again.")
        st.stop()

    c = footprint.centroid
    lon, lat = geo.mtm8_to_wgs84(c.x, c.y)
    record = {
        "id": new_id(), "title": title.strip(), "data_type": data_type, "file_name": f.name,
        "file_size": len(data), "mime": f.type or mimetypes.guess_type(f.name)[0], "sha256": digest,
        "source_org": source_org, "original_reference": original_reference.strip() or None,
        "work_year": int(work_year), "data_era": era_label(work_year), "value_status": value_status,
        "licence": licence, "access_level": access_level, "notes": notes.strip() or None,
        "uploaded_by": uploaded_by.strip(), "uploaded_at": now_iso(),
        "geom_type": "point" if footprint.geom_type == "Point" else "area",
        "x_mtm8": round(c.x, 2), "y_mtm8": round(c.y, 2), "lon": round(lon, 6), "lat": round(lat, 6),
        "footprint_wkt_mtm8": footprint.wkt, "status": "pending",
        "check_report": [{"level": lv, "message": ms} for lv, ms in report],
    }
    store.add(record, data)
    state.pop("up_geom", None)
    st.success("Submitted. A curator will review it; it appears on the map once approved.")
