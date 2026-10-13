"""Helpers shared by the Streamlit pages."""
import streamlit as st

from . import data, storage

ERA_COLOURS = {"pre-1960": "#d95f02", "1960 and later": "#1b9e77", "undated": "#7f7f7f"}
SITE_CLASS_COLOURS = {"A": "#08306b", "B": "#2171b5", "C": "#6baed6", "D": "#fdae6b", "E": "#e6550d", "F": "#a50f15"}
UPLOAD_COLOUR = "#7b3294"
VS_COLOUR = "#08519c"


def secrets():
    try:
        return dict(st.secrets)
    except Exception:  # no secrets file
        return {}


@st.cache_resource
def get_store():
    return storage.get_store(secrets())


@st.cache_data(show_spinner="Loading the borehole archive…")
def load_archive(use_demo):
    return data.load_archive(use_demo)


@st.cache_data
def load_vs():
    return data.load_vs()


def archive_banner(label):
    if label == "none":
        st.warning("No borehole archive in `data/` yet. See data/README.md for the files to add.")
    elif label.startswith("DEMO"):
        st.error("Showing DEMO boreholes: synthetic points to try the app, not real data. "
                 "Add data/boreholes.csv and data/spt_samples.csv to show the archive.")


def storage_banner(store):
    if isinstance(store, storage.LocalStore):
        st.info("Uploads are kept in a temporary local folder and are lost when the app restarts. "
                "Add Supabase settings to the app's secrets for permanent shared storage.")
