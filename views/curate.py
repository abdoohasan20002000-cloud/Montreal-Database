"""Curator page: read the check report, approve or reject pending uploads."""
from functools import partial

import streamlit as st

from geotech import ui
from geotech.storage import now_iso

ui.hero("Curate", "Read each upload's check report, inspect the file, then approve or reject it. "
        "Only approved files appear on the map.")
store = ui.get_store()
ui.storage_banner(store)

pw = ui.secrets().get("CURATOR_PASSWORD")
if not pw:
    st.warning("Set CURATOR_PASSWORD in the app's secrets to enable this page.")
    st.stop()
if st.text_input("Curator password", type="password") != pw:
    st.stop()
curator = st.text_input("Your name (recorded with each decision)")

pending = store.list(status="pending")
st.write(f"{len(pending)} upload(s) waiting.")
for r in pending:
    with st.expander(f"{r['data_type']} · {r['title']} · from {r['uploaded_by']} · {r['uploaded_at']}", expanded=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.write(f"**File:** {r['file_name']} ({r['file_size'] / 1e6:.2f} MB)  \n"
                     f"**Source:** {r['source_org']} · {r.get('original_reference') or 'no reference'} · {r['work_year']}"
                     f"{'–' + str(r['work_year_end']) if r.get('work_year_end') else ''} ({r['data_era']})  \n"
                     f"**Region:** {r.get('region') or 'not recorded'}"
                     f"{' · part of a submission of several files' if r.get('submission_id') else ''}  \n"
                     f"**Values:** {r['value_status']} · **Licence:** {r['licence']} · **Access:** {r['access_level']}  \n"
                     f"**Location (MTM 8):** {r['x_mtm8']:,.1f} E, {r['y_mtm8']:,.1f} N ({r['geom_type']})  \n"
                     f"**Notes:** {r.get('notes') or '—'}")
            for item in r.get("check_report") or []:
                {"block": st.error, "warn": st.warning, "ok": st.success}[item["level"]](item["message"])
        with c2:
            st.map([{"lat": r["lat"], "lon": r["lon"]}], zoom=13, height=200)
            st.download_button("Download to inspect", partial(store.get_bytes, r), file_name=r["file_name"],
                               mime=ui.mime_of(r), key=f"get_{r['id']}")
            note = st.text_input("Review note", key=f"note_{r['id']}")
            a, b = st.columns(2)
            for col, verdict, text in ((a, "approved", "Approve"), (b, "rejected", "Reject")):
                if col.button(text, key=f"{verdict}_{r['id']}", disabled=not curator):
                    store.update(r["id"], status=verdict, reviewed_by=curator, reviewed_at=now_iso(), review_note=note or None)
                    st.rerun()
if pending and not curator:
    st.caption("Enter your name to enable the approve and reject buttons.")
