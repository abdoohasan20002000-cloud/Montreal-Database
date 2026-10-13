"""Helpers shared by the Streamlit pages."""
import streamlit as st

from . import data, storage

import html

ERA_COLOURS = {"pre-1960": "#c8641e", "1960 and later": "#0e7c86", "undated": "#8a94a0"}
# NBCC site classes, stiff (A) to soft (E): rock greys/blues into warm soft-soil colours.
SITE_CLASS_COLOURS = {"A": "#2b3a55", "B": "#3f6e9e", "C": "#79a7c7", "D": "#e3b04b", "E": "#d0612f", "F": "#9c2d2d"}
UPLOAD_COLOUR = "#7a4fa3"
VS_COLOUR = "#2e5aac"
# Stratigraphy stripe under the header: fill, clay, silt, sand, till, rock.
STRATA = ["#8d7b68", "#7f95a3", "#b9a77f", "#e0c58f", "#9b8c74", "#4b5563"]


from .insight import nbcc_class  # noqa: E402,F401  (re-exported for the pages)


_CSS = """
<style>
:root { --ink:#1c2430; --muted:#5d6876; --line:#e3e0d8; --card:#ffffff; --accent:#0e7c86; }
.block-container { padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1500px; }
[data-testid="stHeader"] { background: transparent; }
h1, h2, h3 { letter-spacing: -0.01em; }

/* header band */
.gx-hero { background: linear-gradient(120deg, #14202b 0%, #1d3442 60%, #0e5560 100%);
  color: #f4f6f7; border-radius: 14px; padding: 22px 28px 18px; margin-bottom: 18px; position: relative; overflow: hidden; }
.gx-eyebrow { font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; color: #8fd3d6; font-weight: 600; margin-bottom: 4px; }
.gx-hero h1 { color:#fff; font-size: 1.9rem; margin: 0 0 4px 0; padding: 0; }
.gx-hero p { color: #c9d4da; margin: 0; font-size: 0.98rem; max-width: 900px; }
.gx-strata { display:flex; height:6px; margin: 16px -28px -18px; }
.gx-strata span { flex:1; }
.gx-chips { margin-top: 12px; display:flex; flex-wrap:wrap; gap:8px; }
.gx-chip { font-size: 0.78rem; padding: 3px 10px; border-radius: 999px; background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.18); color: #e6eef1; }
.gx-chip b { color:#fff; font-weight:600; }

/* KPI cards */
.gx-kpis { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 2px 0 6px; }
.gx-kpi { background: var(--card); border:1px solid var(--line); border-radius: 12px; padding: 12px 14px 10px;
  border-left: 4px solid var(--c, var(--accent)); }
.gx-kpi .v { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 1.55rem; font-weight: 500; color: var(--ink); line-height:1.1; }
.gx-kpi .l { font-size: 0.82rem; color: var(--ink); font-weight: 600; margin-top: 4px; }
.gx-kpi .s { font-size: 0.74rem; color: var(--muted); }

/* panels */
.gx-panel-title { font-size: 0.74rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted);
  font-weight: 600; margin: 4px 0 6px; }
.gx-note { font-size: 0.82rem; color: var(--muted); }
.gx-badge { display:inline-block; font-size:0.72rem; font-weight:600; padding:2px 8px; border-radius:6px; margin-right:6px; }
.gx-measured { background:#e3edf9; color:#2e5aac; }
.gx-estimated { background:#fbeee0; color:#a2531a; }
.gx-derived { background:#eef0f2; color:#4b5563; }

/* map frame */
iframe[title="streamlit_folium.st_folium"] { border-radius: 12px; border: 1px solid var(--line); }

/* tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { padding: 8px 14px; font-weight: 500; }

/* sidebar brand */
.gx-brand { padding: 4px 4px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); margin-bottom: 8px; }
.gx-brand .t { font-family: "Space Grotesk", sans-serif; font-weight: 700; font-size: 1.15rem; color: #fff; }
.gx-brand .s { font-size: 0.75rem; color: #9fb0bb; }
.gx-brand .strata { display:flex; height:4px; border-radius:2px; overflow:hidden; margin-top:8px; }
.gx-brand .strata span { flex:1; }
</style>
"""


def _strata(cls):
    return f'<div class="{cls}">' + "".join(f'<span style="background:{c}"></span>' for c in STRATA) + "</div>"


def apply_style():
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_brand():
    st.markdown('<div class="gx-brand"><div class="t">Montréal Geotechnical Atlas</div>'
                '<div class="s">Boreholes · SPT · measured Vs · contributed files</div>'
                + _strata("strata") + "</div>", unsafe_allow_html=True)


def hero(title, subtitle, chips=()):
    chip_html = "".join(f'<span class="gx-chip">{c}</span>' for c in chips)
    st.markdown(f'<div class="gx-hero"><div class="gx-eyebrow">Montréal Geotechnical Atlas</div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p>'
                + (f'<div class="gx-chips">{chip_html}</div>' if chips else "")
                + _strata("gx-strata") + "</div>", unsafe_allow_html=True)


def kpis(items, cols=2):
    """items: (value, label, sub, colour)."""
    cards = "".join(
        f'<div class="gx-kpi" style="--c:{c}"><div class="v">{html.escape(str(v))}</div>'
        f'<div class="l">{html.escape(l)}</div><div class="s">{html.escape(s)}</div></div>'
        for v, l, s, c in items)
    st.markdown(f'<div class="gx-kpis" style="grid-template-columns:repeat({cols},minmax(0,1fr))">{cards}</div>',
                unsafe_allow_html=True)


def panel_title(text):
    st.markdown(f'<div class="gx-panel-title">{html.escape(text)}</div>', unsafe_allow_html=True)


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
        st.info("The borehole archive is not loaded yet, so only measured Vs and contributed files are shown.",
                icon=":material/info:")
    elif label.startswith("DEMO"):
        st.error("Showing DEMO boreholes: synthetic points to try the app, not real data. "
                 "Add data/boreholes.csv and data/spt_samples.csv to show the archive.")


def storage_banner(store):
    if isinstance(store, storage.LocalStore):
        st.info("Uploads are kept in a temporary local folder and are lost when the app restarts. "
                "Add Supabase settings to the app's secrets for permanent shared storage.")
