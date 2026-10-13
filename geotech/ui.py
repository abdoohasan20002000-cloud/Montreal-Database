"""Helpers shared by the Streamlit pages: colours, page style, headers, cards and cached data."""
import html

import folium
import streamlit as st

from . import config, data, storage
from .insight import nbcc_class  # noqa: F401  (re-exported for the pages)

# ---- colours ---------------------------------------------------------------------------
# Data colours are checked against the dark page (#0a1520) with the dataviz palette validator:
# the first three categorical slots pass all-pairs (colour-blind separation and contrast).
CATEGORICAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
ERA_COLOURS = {"1960 and later": CATEGORICAL[0], "pre-1960": CATEGORICAL[1], "undated": "#898781"}
UPLOAD_COLOUR = CATEGORICAL[2]
# NBCC site class is ordered, so it is one violet hue stepped dark (A, hard rock) to light (E, soft soil):
# the softest ground, where shaking is amplified most, stands out most on the dark map.
SITE_CLASS_COLOURS = {"A": "#61489b", "B": "#7f61c5", "C": "#9c82e2", "D": "#b9a6f3", "E": "#d7ccfe", "F": "#898781"}
VS_COLOUR = SITE_CLASS_COLOURS["C"]
SEQUENTIAL = ["#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"]  # low (dark) to high (light)
INK, INK_2, MUTED, ACCENT = "#e6edf3", "#a9b8c6", "#7d8fa0", "#22d3ee"
SURFACE = "#0a1520"

ART_URL = "app/static/hero_contours.webp"  # made by scripts/make_hero_art.py

_CSS = """
<style>
:root { --bg:#0a1520; --card:#0f1d2b; --line:#1c3a4d; --glow:rgba(34,211,238,0.24); --ink:#e6edf3; --ink2:#a9b8c6;
  --muted:#7d8fa0; --accent:#22d3ee; --art:url("%(art)s"); }

/* page: a faint engineering grid and the island's contours on the right */
[data-testid="stApp"] { background:
    radial-gradient(1100px 520px at 80%% -8%%, rgba(34,211,238,0.08), transparent 62%%),
    linear-gradient(rgba(125,211,252,0.03) 1px, transparent 1px) 0 0 / 46px 46px,
    linear-gradient(90deg, rgba(125,211,252,0.03) 1px, transparent 1px) 0 0 / 46px 46px,
    #0a1520; }
[data-testid="stMain"]::before { content:""; position:fixed; right:-8vw; top:4vh; width:58vw; height:92vh;
  background: var(--art) center / contain no-repeat; opacity:0.13; pointer-events:none; z-index:0;
  -webkit-mask-image: radial-gradient(closest-side, #000 50%%, transparent);
  mask-image: radial-gradient(closest-side, #000 50%%, transparent); }
.block-container { position:relative; z-index:1; padding-top:1.4rem; padding-bottom:3rem; max-width:1480px; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display:none; }
h1, h2, h3, h4 { letter-spacing:-0.01em; }

/* sidebar: navigation as outlined buttons under small spaced-out section labels */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0d1a26 0%%, #0b1621 100%%); }
[data-testid="stSidebarNav"] { padding: 0 6px; }
[data-testid="stNavSectionHeader"] { pointer-events:none; margin:14px 0 8px; padding:0 2px; min-height:0; }
[data-testid="stNavSectionHeader"] p { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:0.68rem;
  letter-spacing:0.26em; text-transform:uppercase; color:var(--muted); font-weight:500; }
[data-testid="stNavSectionHeader"] > div:last-child { display:none; }
[data-testid="stSidebarNavLink"] { border:1px solid rgba(34,211,238,0.30); background:rgba(17,33,48,0.7);
  border-radius:12px; min-height:46px; padding:0.55rem 0.9rem; margin:0 0 10px; justify-content:center;
  transition: border-color .15s, background .15s, box-shadow .15s; }
[data-testid="stSidebarNavLink"]:hover { border-color:var(--accent); background:rgba(34,211,238,0.08); }
[data-testid="stSidebarNavLink"] p { font-size:0.97rem; font-weight:500; color:var(--ink); }
[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] { color:#67e8f9 !important; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background:var(--accent); border-color:var(--accent);
  box-shadow:0 0 26px rgba(34,211,238,0.28); }
[data-testid="stSidebarNavLink"][aria-current="page"] p,
[data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stIconMaterial"] { color:#04161d !important; font-weight:600; }
[data-testid="stSidebarNavSeparator"] { display:none; }
[data-testid="stSidebarUserContent"] [data-testid="stElementContainer"]:has(.gx-credit) { order:99; }
.gx-side-label { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:0.68rem; letter-spacing:0.26em;
  text-transform:uppercase; color:var(--muted); margin:6px 0 2px; }
.gx-credit { border-top:1px solid var(--line); margin-top:22px; padding-top:16px; }
.gx-credit .n { font-family:"Space Grotesk", sans-serif; font-weight:700; color:#fff; font-size:1rem; }
.gx-credit .r { color:var(--muted); font-size:0.8rem; line-height:1.5; margin-top:3px; }

/* header card */
.gx-hero { position:relative; overflow:hidden; border:1px solid var(--glow); border-radius:22px;
  padding:26px 36px 24px; margin:2px 0 22px;
  background: radial-gradient(700px 320px at 92%% 20%%, rgba(34,211,238,0.10), transparent 70%%),
    linear-gradient(180deg, #0d1b28, #0a1621);
  box-shadow: 0 24px 60px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04); }
.gx-hero::after { content:""; position:absolute; top:-10%%; bottom:-10%%; right:-4%%; width:62%%; z-index:0;
  background: var(--art) center / cover no-repeat; opacity:0.85; filter: brightness(1.5) saturate(1.15);
  -webkit-mask-image: linear-gradient(90deg, transparent 0%%, rgba(0,0,0,0.35) 30%%, #000 70%%);
  mask-image: linear-gradient(90deg, transparent 0%%, rgba(0,0,0,0.35) 30%%, #000 70%%); pointer-events:none; }
.gx-hero > * { position:relative; z-index:1; }
.gx-hero.lg { padding:54px 48px 40px; min-height:360px; }
.gx-hero.lg::after { width:68%%; opacity:1; }
.gx-eyebrow { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:0.72rem; letter-spacing:0.28em;
  text-transform:uppercase; color:var(--accent); margin-bottom:10px; }
.gx-hero h1 { font-family:"Space Grotesk", sans-serif; color:#fff; font-weight:700; font-size:2.1rem; line-height:1.1;
  margin:0 0 10px 0; padding:0; }
.gx-hero.lg h1 { font-size:3.3rem; margin-bottom:24px; }
.gx-hero p { color:#b7c4d0; margin:0; font-size:1rem; line-height:1.6; max-width:780px; }
.gx-hero.lg p { font-size:1.16rem; max-width:720px; }
.gx-rule { width:150px; height:3px; border-radius:3px; margin:18px 0 14px;
  background:linear-gradient(90deg, #22d3ee 0%%, #60a5fa 35%%, #f472b6 70%%, #a78bfa 100%%); }
.gx-hero:not(.lg) .gx-rule { width:110px; margin:14px 0 2px; }
.gx-byline { color:#93a4b4; font-size:0.92rem; }
.gx-byline b { font-family:"Space Grotesk", sans-serif; color:#fff; font-size:1rem; }
.gx-byline .dot { margin:0 10px; color:#4b6276; }
.gx-chips { margin-top:14px; display:flex; flex-wrap:wrap; gap:8px; }
.gx-chip { font-size:0.78rem; padding:4px 11px; border-radius:999px; background:rgba(34,211,238,0.07);
  border:1px solid rgba(34,211,238,0.22); color:#cfe9ef; }
.gx-chip b { color:#fff; font-weight:600; }

/* KPI cards: label, big number, one line of context */
.gx-kpis { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px; margin:2px 0 8px; }
.gx-kpi { position:relative; overflow:hidden; border:1px solid var(--line); border-radius:14px;
  padding:13px 16px 12px 18px; background:linear-gradient(180deg, rgba(17,33,48,0.92), rgba(12,25,37,0.92)); }
.gx-kpi::before { content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--c, var(--accent)); }
.gx-kpi .l { font-size:0.8rem; color:var(--ink2); }
.gx-kpi .v { font-family:"Space Grotesk", sans-serif; font-size:1.8rem; font-weight:600; color:#fff; line-height:1.15;
  margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.gx-kpi .s { font-size:0.76rem; color:var(--muted); margin-top:3px; }

/* value chips (site classes, value status) */
.gx-tags { display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 8px; }
.gx-tag { display:inline-flex; align-items:center; gap:6px; font-size:0.8rem; font-weight:600; padding:4px 11px;
  border-radius:999px; }

/* cards on the home page */
[class*="st-key-gxcard"] { background:linear-gradient(180deg, rgba(17,33,48,0.85), rgba(11,22,33,0.85));
  border-radius:16px; transition:border-color .15s, transform .15s; }
[class*="st-key-gxcard"]:hover { border-color:var(--accent) !important; transform:translateY(-2px); }
.gx-card-icon { width:40px; height:40px; border-radius:11px; display:flex; align-items:center; justify-content:center;
  background:rgba(34,211,238,0.10); border:1px solid rgba(34,211,238,0.3); color:var(--accent); font-size:1.25rem;
  margin-bottom:10px; font-family:"Material Symbols Rounded"; }
.gx-card-title { font-family:"Space Grotesk", sans-serif; font-weight:600; font-size:1.12rem; color:#fff; }
.gx-card-text { color:var(--ink2); font-size:0.88rem; line-height:1.5; min-height:7.6em; margin:4px 0 12px; }
.gx-status { display:flex; gap:10px; align-items:flex-start; padding:9px 0; border-bottom:1px solid rgba(28,58,77,0.6); }
.gx-status:last-child { border-bottom:none; }
.gx-status .i { width:22px; height:22px; flex:none; border-radius:50%%; display:flex; align-items:center;
  justify-content:center; font-size:0.78rem; font-weight:700; margin-top:1px; }
.gx-status .i.ok { background:rgba(12,163,12,0.18); color:#4ade80; border:1px solid rgba(74,222,128,0.4); }
.gx-status .i.todo { background:rgba(250,178,25,0.12); color:#fbbf24; border:1px solid rgba(251,191,36,0.4); }
.gx-status .t { color:var(--ink); font-weight:600; font-size:0.92rem; }
.gx-status .d { color:var(--muted); font-size:0.82rem; }
.gx-step { display:flex; gap:14px; }
.gx-step .num { flex:none; width:34px; height:34px; border-radius:50%%; display:flex; align-items:center;
  justify-content:center; font-family:"Space Grotesk", sans-serif; font-weight:700; color:#04161d; background:var(--accent); }

/* panels and notes */
.gx-panel-title { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:0.7rem; letter-spacing:0.18em;
  text-transform:uppercase; color:#8fb3c4; font-weight:500; margin:6px 0 8px; }
.gx-note { font-size:0.82rem; color:var(--muted); line-height:1.5; }
.gx-badge { display:inline-block; font-size:0.7rem; font-weight:700; letter-spacing:0.06em; padding:2px 8px;
  border-radius:6px; margin-right:8px; border:1px solid transparent; }
.gx-measured { background:rgba(57,135,229,0.16); color:#9cc5f6; border-color:rgba(57,135,229,0.45); }
.gx-estimated { background:rgba(217,89,38,0.16); color:#f3a684; border-color:rgba(217,89,38,0.45); }
.gx-derived { background:rgba(169,184,198,0.12); color:#cdd7e0; border-color:rgba(169,184,198,0.35); }
.gx-interpolated { background:rgba(144,133,233,0.16); color:#c4bdf7; border-color:rgba(144,133,233,0.45); }

/* maps and widgets */
iframe[title="streamlit_folium.st_folium"] { border-radius:16px; border:1px solid var(--line); }
[data-testid="stDeckGlJsonChart"] { border-radius:16px; overflow:hidden; border:1px solid var(--line); }
.stTabs [data-baseweb="tab-list"] { gap:6px; border-bottom:1px solid var(--line); }
.stTabs [data-baseweb="tab"] { padding:8px 14px; font-weight:500; }
button[kind="primary"], [data-testid="stBaseButton-primary"] { color:#04161d !important; font-weight:600; }
[data-testid="stPageLink"] a { border:1px solid rgba(34,211,238,0.35); border-radius:10px; padding:4px 12px;
  justify-content:center; }
[data-testid="stPageLink"] a:hover { background:rgba(34,211,238,0.08); border-color:var(--accent); }
</style>
"""

LEAFLET_CSS = """
<style>
.leaflet-container { background:#0a1520; font-family:Inter, system-ui, sans-serif; }
.leaflet-control-zoom a { background:#112130 !important; color:#e6edf3 !important; border-color:#1c3a4d !important; }
.leaflet-control-zoom a:hover { background:#163049 !important; }
.leaflet-bar { border:1px solid #1c3a4d !important; box-shadow:none !important; }
.leaflet-control-layers { background:#0f1d2b !important; color:#dbe5ee !important; border:1px solid #1c3a4d !important;
  border-radius:10px !important; box-shadow:none !important; }
.leaflet-control-layers-separator { border-top-color:#1c3a4d !important; }
.leaflet-control-attribution { background:rgba(10,21,32,0.75) !important; color:#7d8fa0 !important; }
.leaflet-control-attribution a { color:#67e8f9 !important; }
.leaflet-control-scale-line { background:rgba(10,21,32,0.7) !important; color:#dbe5ee !important;
  border-color:#a9b8c6 !important; }
.leaflet-tooltip { background:#0f1d2b; color:#e6edf3; border:1px solid #1c3a4d; border-radius:8px;
  box-shadow:0 6px 18px rgba(0,0,0,0.4); }
.leaflet-tooltip-top:before { border-top-color:#1c3a4d; }
.leaflet-tooltip-bottom:before { border-bottom-color:#1c3a4d; }
.leaflet-tooltip-left:before { border-left-color:#1c3a4d; }
.leaflet-tooltip-right:before { border-right-color:#1c3a4d; }
</style>
"""

CARTO_ATTR = "© OpenStreetMap contributors © CARTO"
TILES = {
    "Dark": ("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", CARTO_ATTR, 20),
    "Light": ("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", CARTO_ATTR, 20),
    "Satellite": ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                  "Imagery © Esri", 19),
    "Topographic (relief)": ("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                             "© OpenStreetMap contributors, SRTM · style © OpenTopoMap (CC-BY-SA)", 17),
    "Streets": ("OpenStreetMap", None, 19),
}


def apply_style():
    st.markdown(_CSS % {"art": ART_URL}, unsafe_allow_html=True)


# ---- headers, cards, chips -------------------------------------------------------------
def hero(title, subtitle, chips=(), eyebrow="Montréal Geotechnical Atlas", large=False, byline=None):
    """Header card. `chips` and `byline` may hold simple HTML written by the app (never user input)."""
    chip_html = "".join(f'<span class="gx-chip">{c}</span>' for c in chips)
    st.markdown(f'<div class="gx-hero{" lg" if large else ""}"><div class="gx-eyebrow">{html.escape(eyebrow)}</div>'
                f'<h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p><div class="gx-rule"></div>'
                + (f'<div class="gx-byline">{byline}</div>' if byline else "")
                + (f'<div class="gx-chips">{chip_html}</div>' if chips else "")
                + "</div>", unsafe_allow_html=True)


def credit_byline():
    c = config.CREDITS
    parts = [f"<b>{html.escape(c['name'])}</b>" if c.get("name") else "",
             html.escape(c.get("role") or ""), html.escape(f"Supervisor: {c['supervisor']}") if c.get("supervisor") else ""]
    parts = [p for p in parts if p]
    return '<span class="dot">·</span>'.join(parts) if parts else html.escape(config.DATA_CREDIT)


def sidebar_credit():
    c = config.CREDITS
    if c.get("name"):
        body = (f'<div class="n">{html.escape(c["name"])}</div>'
                + (f'<div class="r">{html.escape(c["role"])}</div>' if c.get("role") else "")
                + (f'<div class="r">Supervisor: {html.escape(c["supervisor"])}</div>' if c.get("supervisor") else ""))
    else:
        body = ('<div class="n">Montréal Geotechnical Atlas</div>'
                f'<div class="r">{html.escape(config.DATA_CREDIT)}</div>')
    with st.sidebar:
        st.markdown(f'<div class="gx-credit">{body}</div>', unsafe_allow_html=True)


def sidebar_label(text):
    st.markdown(f'<div class="gx-side-label">{html.escape(text)}</div>', unsafe_allow_html=True)


def kpis(items, cols=2):
    """items: (value, label, sub, colour). Label on top, the number, then one line of context."""
    cards = "".join(
        f'<div class="gx-kpi" style="--c:{c}"><div class="l">{html.escape(l)}</div>'
        f'<div class="v" title="{html.escape(str(v))}">{html.escape(str(v))}</div><div class="s">{html.escape(s)}</div></div>'
        for v, l, s, c in items)
    st.markdown(f'<div class="gx-kpis" style="grid-template-columns:repeat({cols},minmax(0,1fr))">{cards}</div>',
                unsafe_allow_html=True)


def _text_on(hex_colour):
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lum = sum(w * (v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4) for w, v in zip((0.2126, 0.7152, 0.0722), (r, g, b)))
    return "#0a1520" if lum > 0.32 else "#ffffff"


def class_tags(suffix=""):
    """NBCC site-class chips, A to E, in the map colours."""
    from .insight import CLASS_WORDS
    tags = "".join(f'<span class="gx-tag" style="background:{c};color:{_text_on(c)}">{k} · {CLASS_WORDS[k]}</span>'
                   for k, c in SITE_CLASS_COLOURS.items() if k in CLASS_WORDS)
    st.markdown(f'<div class="gx-tags">{tags}</div>'
                + (f'<div class="gx-note">{html.escape(suffix)}</div>' if suffix else ""), unsafe_allow_html=True)


STATUS_WORDS = {
    "measured": ("MEASURED", "gx-measured", "read in the field (SPT N, downhole Vs, Vs30 from surveys)"),
    "derived": ("DERIVED", "gx-derived", "computed from measurements (MASW inversion, site class from a measured Vs30)"),
    "estimated": ("ESTIMATED", "gx-estimated", "from a lookup, not a test (archive Vs30 and site class from lithology)"),
    "interpolated": ("INTERPOLATED", "gx-interpolated", "between measured sites (site-report Vs30 estimate)"),
}


def status_legend():
    st.markdown("".join(f'<div style="margin:0 0 9px"><span class="gx-badge {cls}">{word}</span>'
                        f'<span class="gx-note">{html.escape(text)}</span></div>'
                        for word, cls, text in STATUS_WORDS.values()), unsafe_allow_html=True)


def panel_title(text):
    st.markdown(f'<div class="gx-panel-title">{html.escape(text)}</div>', unsafe_allow_html=True)


# ---- maps --------------------------------------------------------------------------------
def base_map(location=(45.55, -73.66), zoom=11, layers=("Dark", "Light", "Satellite", "Topographic (relief)", "Streets")):
    """A folium map on the dark basemap, with the other basemaps one click away, and dark map controls."""
    m = folium.Map(location=list(location), zoom_start=zoom, tiles=None, control_scale=True)
    for i, name in enumerate(layers):
        url, attr, max_zoom = TILES[name]
        folium.TileLayer(url, name=name, attr=attr, max_zoom=max_zoom, show=i == 0).add_to(m)
    m.get_root().header.add_child(folium.Element(LEAFLET_CSS))
    return m


def pin_icon(colour, size=16):
    """A teardrop pin in one of the data colours (folium's built-in icons only come in a few fixed colours)."""
    return folium.DivIcon(icon_size=(size, size), icon_anchor=(size // 2, size),
                          html=f'<div style="width:{size}px;height:{size}px;background:{colour};border:2px solid #fff;'
                               f'border-radius:50% 50% 50% 0;transform:rotate(-45deg);'
                               f'box-shadow:0 2px 6px rgba(0,0,0,0.5)"></div>')


def target_icon(size=26):
    return folium.DivIcon(icon_size=(size, size), icon_anchor=(size // 2, size // 2),
                          html=f'<div style="width:{size}px;height:{size}px;border-radius:50%;border:2px solid {ACCENT};'
                               f'box-shadow:0 0 0 4px rgba(34,211,238,0.25),0 0 18px rgba(34,211,238,0.6);'
                               f'display:flex;align-items:center;justify-content:center"><div style="width:6px;height:6px;'
                               f'border-radius:50%;background:{ACCENT}"></div></div>')


# ---- data and settings -------------------------------------------------------------------
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
