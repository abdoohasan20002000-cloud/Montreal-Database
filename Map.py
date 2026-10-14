"""Entry point: page setup, shared style and navigation."""
import sys
from pathlib import Path

import streamlit as st

PACKAGE = "geotech"


def _own_modules():
    return {n: m for n, m in list(sys.modules.items()) if n == PACKAGE or n.startswith(PACKAGE + ".")}


def _mtime(module):
    try:
        return Path(module.__file__).stat().st_mtime_ns
    except (AttributeError, TypeError, OSError):  # no file, or the file was removed
        return None


def unload_changed_modules():
    """Unload the geotech modules when any of their files changed since they were loaded.

    Streamlit Cloud pulls each new commit into the running app. The pages rerun with the new code, but the modules
    they import can stay as first loaded, so a page calls a helper the old module does not have (AttributeError).
    Unloading them before anything imports them makes this run load the current files. A module with no stamp was
    loaded by older code, so it counts as changed too."""
    if any(getattr(m, "_loaded_mtime_ns", None) != _mtime(m) for m in _own_modules().values()):
        for name in _own_modules():
            sys.modules.pop(name, None)


def stamp_modules():
    """Record each geotech module's file time once, after the run that loaded it."""
    for m in _own_modules().values():
        if not hasattr(m, "_loaded_mtime_ns"):
            m._loaded_mtime_ns = _mtime(m)


unload_changed_modules()
from geotech import ui  # noqa: E402  (after the stale-module check on purpose)

st.set_page_config(page_title="Montréal Geotechnical Atlas", page_icon="🪨", layout="wide",
                   initial_sidebar_state="auto")
ui.apply_style()

pages = {
    "Navigate": [
        st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("views/guide.py", title="User guide", icon=":material/menu_book:"),
    ],
    "Explore the data": [
        st.Page("views/catalogue.py", title="Data catalogue", icon=":material/dataset:"),
        st.Page("views/explore.py", title="Map and 3D", icon=":material/map:"),
        st.Page("views/insights.py", title="Insights", icon=":material/insights:"),
        st.Page("views/site_report.py", title="Site report", icon=":material/location_searching:"),
    ],
    "Contribute": [
        st.Page("views/contribute.py", title="Contribute data", icon=":material/upload_file:"),
        st.Page("views/curate.py", title="Curate", icon=":material/fact_check:"),
    ],
}
page = st.navigation(pages, position="sidebar", expanded=True)
ui.sidebar_credit()  # pinned to the foot of the sidebar by CSS, after any page filters
try:
    page.run()
finally:  # also after st.stop() or st.rerun(), which end a run by raising
    stamp_modules()
