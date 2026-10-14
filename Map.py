"""Entry point: page setup, shared style and navigation."""
import importlib
import sys
import threading
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
PACKAGE = "geotech"
# Data files the geotech modules read once and keep in memory: a commit that changes them reloads the modules too.
READ_ONCE = [ROOT / "data" / "regions.geojson", ROOT / "data" / "island_outline.geojson"]


@st.cache_resource(show_spinner=False)
def _loader_state():
    """One per server process, kept across reruns and module reloads: a lock, and the files the loaded modules came
    from."""
    return {"lock": threading.Lock(), "loaded_from": None}


def _files_now():
    """{file: (modification time, size)} for every geotech source file and the data files it keeps in memory."""
    out = {}
    for f in sorted((ROOT / PACKAGE).glob("*.py")) + READ_ONCE:
        try:
            s = f.stat()
            out[f.relative_to(ROOT).as_posix()] = (s.st_mtime_ns, s.st_size)
        except OSError:  # a missing data file is a state too
            out[f.relative_to(ROOT).as_posix()] = None
    return out


def _module_names(files):
    stems = [Path(f).stem for f in files if f.startswith(PACKAGE + "/")]
    return [PACKAGE] + [f"{PACKAGE}.{s}" for s in stems if s != "__init__"]


def _current(state, files):
    return state["loaded_from"] == files and all(name in sys.modules for name in _module_names(files))


def load_current_modules():
    """Make sure the geotech modules in memory are the ones in the files on disk.

    Streamlit Cloud pulls each new commit into the running app. The pages rerun with the new code, but the modules
    they import stay as first loaded, so a page can call a helper the old module does not have (AttributeError).
    When the files differ from those the modules were loaded from, this unloads every geotech module and imports them
    all again, so the pages never start a real import of their own.

    - One lock for the whole process, so two visitors never unload modules the other is still importing.
    - The files are read before importing, so a commit that lands during the import is picked up on the next run.
    - Streamlit's own reloader is told to leave geotech/ alone (server.folderWatchBlacklist in .streamlit/config.toml),
      so nothing else unloads these modules."""
    state = _loader_state()
    if _current(state, _files_now()):
        return
    with state["lock"]:
        for attempt in range(3):
            files = _files_now()
            if _current(state, files):  # another visitor's run reloaded them while this one waited
                return
            for name in [n for n in sys.modules if n == PACKAGE or n.startswith(PACKAGE + ".")]:
                sys.modules.pop(name, None)
            try:
                for name in _module_names(files):
                    importlib.import_module(name)
            except (KeyError, ImportError):  # an import outside this lock raced this one: start again
                if attempt == 2:
                    raise
                continue
            state["loaded_from"] = files
            return


load_current_modules()
from geotech import ui  # noqa: E402  (after the module check on purpose)

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
page.run()
