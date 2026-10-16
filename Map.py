"""Entry point: page setup, shared style and navigation."""
import importlib
import importlib.util
import sys
import threading
import time
from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitPageNotFoundError

ROOT = Path(__file__).parent
PACKAGE = "geotech"
# Data files the geotech modules read once and keep in memory: a commit that changes them reloads the modules too.
READ_ONCE = [ROOT / "data" / "regions.geojson", ROOT / "data" / "island_outline.geojson"]


@st.cache_resource(show_spinner=False)
def _loader_state():
    """One per server process, kept across reruns and module reloads: a lock, the files the loaded modules and the
    compiled pages came from, and the modules that failed to import."""
    return {"lock": threading.Lock(), "loaded_from": None, "failed": set(), "pages_from": None}


def _stamps(paths):
    """{file: (modification time, size)}; None for a file that is missing (or was just removed)."""
    out = {}
    for f in paths:
        try:
            s = f.stat()
            out[f.relative_to(ROOT).as_posix()] = (s.st_mtime_ns, s.st_size)
        except OSError:
            out[f.relative_to(ROOT).as_posix()] = None
    return out


def _files_now():
    """Every geotech source file and the data files it keeps in memory."""
    return _stamps(sorted((ROOT / PACKAGE).glob("*.py")) + READ_ONCE)


def _page_files():
    return _stamps(sorted((ROOT / "views").glob("*.py")))


def _module_names(files):
    stems = [Path(f).stem for f in files if f.startswith(PACKAGE + "/")]
    return [PACKAGE] + [f"{PACKAGE}.{s}" for s in stems if s != "__init__"]


def _current(state, files):
    return state["loaded_from"] == files and all(name in sys.modules or name in state["failed"]
                                                 for name in _module_names(files))


def _forget_bytecode(files):
    """Python reuses a module's cached bytecode when the source has the same size and the same whole second, so two
    updates within one second could bring back the older code. Remove it before reloading."""
    for f in files:
        if f.endswith(".py"):
            try:
                Path(importlib.util.cache_from_source(str(ROOT / f))).unlink(missing_ok=True)
            except OSError:  # a read-only folder: no bytecode is written there either
                pass
    importlib.invalidate_caches()  # and see modules added since the import system last listed the folder


def _forget_compiled_pages():
    """Streamlit keeps each page's compiled code until a connected visitor's file watcher sees the page change, which a
    live update can slip past. Drop it, so pages are compiled from the same commit as the modules."""
    try:
        from streamlit import runtime
        runtime.get_instance()._script_cache.clear()  # Streamlit 1.65 has no public call for this
    except Exception:  # another Streamlit version: the watcher still clears it in most cases
        pass


def load_current_modules():
    """Make sure the geotech modules in memory, and the compiled pages, are the ones in the files on disk.

    Streamlit Cloud pulls each new commit into the running app. The pages rerun with the new code, but the modules
    they import stay as first loaded, so a page can call a helper the old module does not have (AttributeError).
    When the files differ from those the modules were loaded from, this unloads every geotech module and imports them
    all again, so the pages never start a real import of their own.

    - One lock for the whole process, so two visitors never unload modules the other is still importing.
    - The files are read before importing, so a commit that lands during the import is picked up on the next run.
    - Streamlit's own reloader is told to leave geotech/ alone (server.folderWatchBlacklist in .streamlit/config.toml),
      so nothing else unloads these modules.
    - A module that fails to import is left out, so only the pages that use it show the error (and import it again)."""
    state = _loader_state()
    if _current(state, _files_now()) and state["pages_from"] == _page_files():
        return
    with state["lock"]:
        files, pages = _files_now(), _page_files()
        if not _current(state, files):  # another visitor's run may have reloaded them while this one waited
            for name in [n for n in list(sys.modules) if n == PACKAGE or n.startswith(PACKAGE + ".")]:
                sys.modules.pop(name, None)
            _forget_bytecode(files)
            failed = set()
            for name in _module_names(files):
                try:
                    importlib.import_module(name)
                except Exception:  # broken in this commit: the pages that import it show the error themselves
                    failed.add(name)
            state["loaded_from"], state["failed"] = files, failed
            state["pages_from"] = None
        if state["pages_from"] != pages:
            _forget_compiled_pages()
            state["pages_from"] = pages


def _app_files():
    return _files_now(), _page_files(), _stamps([ROOT / "Map.py"])


def _newest(files):
    return max((v[0] for part in files for v in part.values() if v), default=0)


def _changed_since(files_at_start, wait_s=2.0):
    """Whether any app file changed since this run started. Right after a pull it waits a moment, because a pull writes
    geotech/ before views/ and the page that failed may still be on its way."""
    deadline = time.monotonic() + wait_s
    while _app_files() == files_at_start:
        if time.monotonic() > deadline or time.time_ns() - _newest(files_at_start) > 10e9:
            return False
        time.sleep(0.1)
    return True


def _worth_retrying(files_at_start):
    """After a failure: whether this run may have mixed code from two commits, so that running it again could work.
    Yes if an app file changed during the run, or once per visitor while the files are fresh from a pull (the run
    may have used page code Streamlit compiled before the pull)."""
    if _changed_since(files_at_start):
        return True
    key = hash(repr(files_at_start))
    if time.time_ns() - _newest(files_at_start) < 30e9 and st.session_state.get("_retried_after_update") != key:
        st.session_state["_retried_after_update"] = key
        return True
    return False


def main():
    load_current_modules()
    from geotech import ui  # after the module check on purpose

    from geotech import config

    st.set_page_config(page_title=config.APP_NAME, page_icon="🪨", layout="wide",
                       initial_sidebar_state="collapsed")
    ui.apply_style()
    ui.require_app_password()  # stops here, before any page is built, when APP_PASSWORD is in the secrets
    pages = [  # one row across the top, in reading order
        st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("views/guide.py", title="User guide", icon=":material/menu_book:"),
        st.Page("views/catalogue.py", title="Data catalogue", icon=":material/dataset:"),
        st.Page("views/explore.py", title="Map and 3D", icon=":material/map:"),
        st.Page("views/insights.py", title="Insights", icon=":material/insights:"),
        st.Page("views/site_report.py", title="Site report", icon=":material/location_searching:"),
        st.Page("views/contribute.py", title="Contribute data", icon=":material/upload_file:"),
        st.Page("views/curate.py", title="Curate", icon=":material/fact_check:"),
    ]
    page = st.navigation(pages, position="top")
    ui.page_footer()  # written before the page so a page that stops early still has it; CSS moves it to the end
    page.run()


# Errors that code from two commits typically raises when it meets (a missing helper, column, argument or page).
# Anything else, such as a failed upload, is shown as usual.
MIXED_CODE_ERRORS = (AttributeError, ImportError, NameError, KeyError, TypeError, SyntaxError, StreamlitPageNotFoundError)

files_at_start = _app_files()  # before the module check, so a commit landing after it is noticed
try:
    main()
except MIXED_CODE_ERRORS:  # st.rerun() and st.stop() raise BaseException subclasses, so they pass through
    if _worth_retrying(files_at_start):
        _forget_compiled_pages()
        st.rerun()
    raise
