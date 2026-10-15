"""Helpers shared by the Streamlit pages: colours, page style, headers, cards, maps and cached data."""
import base64
import html
import mimetypes
import uuid

import folium
import streamlit as st

from . import config, data, geo, storage
from .insight import nbcc_class  # noqa: F401  (re-exported for the pages)

# ---- colours ---------------------------------------------------------------------------
# Data colours are checked on white with the dataviz palette validator: the first three categorical slots pass
# all-pairs colour-blind separation; aqua is below 3:1 contrast, so it is always drawn with a white ring and a legend.
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
ERA_COLOURS = {"1960 and later": CATEGORICAL[0], "pre-1960": CATEGORICAL[1], "undated": "#898781"}
UPLOAD_COLOUR = CATEGORICAL[2]
# NBCC site class is ordered, so it is one violet hue stepped light (A, hard rock) to dark (E, soft soil):
# the softest ground, where shaking is amplified most, stands out most.
SITE_CLASS_COLOURS = {"A": "#af9ee4", "B": "#9379d7", "C": "#7756c0", "D": "#5b3a9b", "E": "#3e256e", "F": "#898781"}
VS_COLOUR = SITE_CLASS_COLOURS["C"]
SEQUENTIAL = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]  # low (light) to high (dark)
# Coverage chart (what kind of data sits in each region): an all-pairs pass on white; the aqua/magenta pair is in the
# colour-blind floor band, so the chart always carries a legend, tooltips and white gaps between segments.
COVERAGE_COLOURS = {"Boreholes": CATEGORICAL[0], "Measured Vs30 sites": CATEGORICAL[4],
                    "Vs profile locations": CATEGORICAL[3], "Contributed files": CATEGORICAL[2]}
INK, INK_2, MUTED, ACCENT, ACCENT_DARK = "#0f1b2d", "#475569", "#566476", "#0891b2", "#0e7490"
SURFACE = "#ffffff"

ART_URL = "app/static/hero_contours.webp"  # made by scripts/make_hero_art.py

_CSS = """
<style>
:root { --bg:#f5f8fb; --card:#ffffff; --line:#dbe4ec; --soft:#eef6f9; --ink:#0f1b2d; --ink2:#475569; --muted:#566476;
  --accent:#0891b2; --accent-dark:#0e7490; --art:url("%(art)s"); }

/* page: a faint survey grid and a soft cyan glow */
[data-testid="stApp"] { background:
    radial-gradient(1000px 480px at 82%% -10%%, rgba(8,145,178,0.08), transparent 62%%),
    linear-gradient(rgba(14,116,144,0.035) 1px, transparent 1px) 0 0 / 46px 46px,
    linear-gradient(90deg, rgba(14,116,144,0.035) 1px, transparent 1px) 0 0 / 46px 46px,
    #f5f8fb; }
.block-container { position:relative; z-index:1; padding-top:1.4rem; padding-bottom:3rem; max-width:1480px; }
[data-testid="stHeader"] { background: transparent; }
h1, h2, h3, h4 { letter-spacing:-0.01em; color:var(--ink); }

/* sidebar: navigation as outlined buttons under small spaced-out section labels */
[data-testid="stSidebar"] { background:#ffffff; }
[data-testid="stSidebarNav"] { padding:0 6px; }
[data-testid="stNavSectionHeader"] { pointer-events:none; margin:14px 0 8px; padding:0 2px; min-height:0; }
[data-testid="stNavSectionHeader"] p { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:0.68rem;
  letter-spacing:0.26em; text-transform:uppercase; color:var(--muted); font-weight:500; }
[data-testid="stNavSectionHeader"] > div:last-child { display:none; }
[data-testid="stSidebarNavLink"] { border:1px solid #cfe1e8; background:#f8fbfc; border-radius:12px; min-height:46px;
  padding:0.55rem 0.9rem; margin:0 0 10px; justify-content:center;
  transition: border-color .15s, background .15s, box-shadow .15s; }
[data-testid="stSidebarNavLink"]:hover { border-color:var(--accent); background:#ecf8fb; }
[data-testid="stSidebarNavLink"] p { font-size:0.97rem; font-weight:500; color:var(--ink); }
[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] { color:var(--accent-dark) !important; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background:linear-gradient(135deg, #0e7490, #0b7c98);
  border-color:#0e7490; box-shadow:0 8px 22px rgba(8,145,178,0.28); }
[data-testid="stSidebarNavLink"][aria-current="page"] p,
[data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stIconMaterial"] { color:#ffffff !important; font-weight:600; }
[data-testid="stSidebarNavSeparator"] { display:none; }
[data-testid="stSidebarUserContent"] [data-testid="stElementContainer"]:has(.gx-credit) { order:99; }
.gx-side-label { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:0.68rem; letter-spacing:0.26em;
  text-transform:uppercase; color:var(--muted); margin:6px 0 2px; }
.gx-credit { border-top:1px solid var(--line); margin-top:22px; padding-top:16px; }
.gx-credit .p { width:52px; height:52px; border-radius:50%%; object-fit:cover; display:block; margin-bottom:10px;
  border:2px solid var(--line); }
.gx-credit .n { font-family:"Space Grotesk", sans-serif; font-weight:700; color:var(--ink); font-size:1rem; }
.gx-credit .r { color:var(--muted); font-size:0.8rem; line-height:1.5; margin-top:3px; }

/* header card */
.gx-hero { position:relative; overflow:hidden; border:1px solid #cfe3ea; border-radius:22px; padding:26px 36px 24px;
  margin:2px 0 22px; background: radial-gradient(700px 320px at 92%% 15%%, rgba(34,211,238,0.14), transparent 70%%),
    linear-gradient(180deg, #ffffff, #f4fafc);
  box-shadow: 0 18px 50px rgba(15,27,45,0.08), 0 1px 0 rgba(255,255,255,0.8) inset; }
.gx-hero::after { content:""; position:absolute; top:-10%%; bottom:-10%%; right:-4%%; width:62%%; z-index:0;
  background: var(--art) center / cover no-repeat; opacity:0.9; pointer-events:none;
  -webkit-mask-image: linear-gradient(90deg, transparent 0%%, rgba(0,0,0,0.35) 30%%, #000 70%%);
  mask-image: linear-gradient(90deg, transparent 0%%, rgba(0,0,0,0.35) 30%%, #000 70%%); }
.gx-hero > * { position:relative; z-index:1; }
.gx-hero.lg { padding:54px 48px 40px; min-height:360px; }
.gx-hero.lg::after { width:68%%; opacity:1; }
.gx-eyebrow { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:0.72rem; letter-spacing:0.28em;
  text-transform:uppercase; color:var(--accent-dark); margin-bottom:10px; font-weight:500; }
.gx-hero h1 { font-family:"Space Grotesk", sans-serif; color:var(--ink); font-weight:700; font-size:2.1rem; line-height:1.1;
  margin:0 0 10px 0; padding:0; }
.gx-hero.lg h1 { font-size:clamp(2rem, 7vw, 3.3rem); margin-bottom:24px; overflow-wrap:normal; hyphens:manual; }
@media (max-width: 640px) { .gx-hero.lg { padding:28px 20px 24px; min-height:0; } .gx-hero { padding:20px 18px; }
  .gx-hero.lg p { font-size:1rem; } }
.gx-hero p { color:#334155; margin:0; font-size:1rem; line-height:1.6; max-width:780px; }
.gx-hero.lg p { font-size:1.16rem; max-width:720px; }
.gx-rule { width:150px; height:3px; border-radius:3px; margin:18px 0 14px;
  background:linear-gradient(90deg, #0891b2 0%%, #3b82f6 35%%, #ec4899 70%%, #8b5cf6 100%%); }
.gx-hero:not(.lg) .gx-rule { width:110px; margin:14px 0 2px; }
.gx-byline { color:var(--muted); font-size:0.92rem; }
.gx-byline b { font-family:"Space Grotesk", sans-serif; color:var(--ink); font-size:1rem; }
.gx-byline .dot { margin:0 10px; color:#9aa9b8; }
.gx-chips { margin-top:14px; display:flex; flex-wrap:wrap; gap:8px; }
.gx-chip { font-size:0.78rem; padding:4px 11px; border-radius:999px; background:#ecf8fb; border:1px solid #c5e4ec; color:#155e75; }
.gx-chip b { color:#0c4a5e; font-weight:600; }

/* segmented controls and pills wrap in narrow columns instead of hiding options off the edge */
[data-testid="stButtonGroup"] > [role="radiogroup"], [data-testid="stButtonGroup"] > [role="toolbar"] {
  flex-wrap:wrap; overflow:visible; gap:4px; }
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] { border-radius:10px; }

/* home cards wrap onto more rows rather than squeezing below a readable width */
.st-key-homecards [data-testid="stHorizontalBlock"] { flex-wrap:wrap; row-gap:12px; }
.st-key-homecards [data-testid="stColumn"] { min-width:200px; }

/* the four soil panels on Insights go two by two when four would be too narrow to read */
@media (max-width: 1250px) {
  .st-key-soilpanels [data-testid="stHorizontalBlock"] { flex-wrap:wrap; row-gap:12px; }
  .st-key-soilpanels [data-testid="stColumn"] { min-width:calc(50%% - 1rem); } }

/* KPI cards: label, big number, one line of context */
.gx-kpis { display:grid; grid-template-columns:repeat(auto-fit,
    minmax(min(100%%, max(11rem, calc((100%% - (var(--cols, 2) - 1) * 12px) / var(--cols, 2)))), 1fr)); gap:12px;
  margin:2px 0 8px; }
.gx-kpi { position:relative; overflow:hidden; border:1px solid var(--line); border-radius:14px; background:#ffffff;
  padding:13px 16px 12px 18px; box-shadow:0 4px 14px rgba(15,27,45,0.04); }
.gx-kpi::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--c, var(--accent)); }
.gx-kpi .l { font-size:0.8rem; color:var(--ink2); }
.gx-kpi .v { font-family:"Space Grotesk", sans-serif; font-size:1.8rem; font-weight:600; color:var(--ink); line-height:1.15;
  margin-top:4px; overflow-wrap:anywhere; }
.gx-kpi .s { font-size:0.76rem; color:var(--muted); margin-top:3px; }

/* value chips (site classes, value status, regions) */
.gx-tags { display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 8px; }
.gx-tag { display:inline-flex; align-items:center; gap:6px; font-size:0.8rem; font-weight:600; padding:4px 11px;
  border-radius:999px; }

/* cards on the home and catalogue pages */
[class*="st-key-gxcard"] { background:#ffffff; border-radius:16px; box-shadow:0 6px 20px rgba(15,27,45,0.05);
  transition:border-color .15s, transform .15s, box-shadow .15s; }
[class*="st-key-gxcard"]:hover { border-color:var(--accent) !important; transform:translateY(-2px);
  box-shadow:0 12px 28px rgba(8,145,178,0.12); }
.gx-card-icon { width:40px; height:40px; border-radius:11px; display:flex; align-items:center; justify-content:center;
  background:#ecf8fb; border:1px solid #c5e4ec; color:var(--accent-dark); font-size:1.25rem; margin-bottom:10px;
  font-family:"Material Symbols Rounded"; }
.gx-card-title { font-family:"Space Grotesk", sans-serif; font-weight:600; font-size:1.12rem; color:var(--ink); }
.gx-card-text { color:var(--ink2); font-size:0.88rem; line-height:1.5; padding-bottom:10px; margin-top:4px; }
.gx-card-title, .gx-card-text { overflow-wrap:normal; word-break:normal; hyphens:auto; }
[data-testid="stColumn"]:has(> div > [class*="st-key-gxcard"]) > div,
[data-testid="stColumn"]:has(> div > [class*="st-key-gxcard"]) [class*="st-key-gxcard"] { height:100%%; }
[class*="st-key-gxcard"] [data-testid="stElementContainer"]:has([data-testid="stPageLink"]) { margin-top:auto; }
.gx-status { display:flex; gap:10px; align-items:flex-start; padding:9px 0; border-bottom:1px solid #e8eef3; }
.gx-status:last-child { border-bottom:none; }
.gx-status .i { width:22px; height:22px; flex:none; border-radius:50%%; display:flex; align-items:center;
  justify-content:center; font-size:0.78rem; font-weight:700; margin-top:1px; }
.gx-status .i.ok { background:#e7f6e7; color:#006300; border:1px solid #9ad49a; }
.gx-status .i.todo { background:#fff4dc; color:#8a5a00; border:1px solid #f2cf7a; }
.gx-status .t { color:var(--ink); font-weight:600; font-size:0.92rem; }
.gx-status .d { color:var(--muted); font-size:0.82rem; }
.gx-flow { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; margin:4px 0 8px; }
@media (max-width: 900px) { .gx-flow { grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); } }
.gx-flow .st { position:relative; background:#ffffff; border:1px solid var(--line); border-radius:14px; padding:13px 16px; }
.gx-flow .n { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:0.68rem; letter-spacing:0.16em;
  color:var(--accent-dark); }
.gx-flow .t { font-family:"Space Grotesk", sans-serif; font-weight:600; font-size:1rem; color:var(--ink); margin:3px 0 4px; }
.gx-flow .d { font-size:0.84rem; color:var(--ink2); line-height:1.45; }
@media (min-width: 901px) { .gx-flow .st:not(:last-child)::after { content:"→"; position:absolute; right:-13px;
  top:50%%; transform:translateY(-50%%); width:12px; text-align:center; color:var(--accent); font-weight:700; } }
.gx-step { display:flex; gap:14px; }
.gx-step .num { flex:none; width:34px; height:34px; border-radius:50%%; display:flex; align-items:center;
  justify-content:center; font-family:"Space Grotesk", sans-serif; font-weight:700; color:#ffffff;
  background:linear-gradient(135deg, #0e7490, #0b7c98); }
.gx-step ul { margin:6px 0 12px 0; padding-left:18px; color:#334155; }

/* panels and notes */
.gx-panel-title { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:0.7rem; letter-spacing:0.18em;
  text-transform:uppercase; color:#36687a; font-weight:500; margin:6px 0 8px; }
.gx-note { font-size:0.82rem; color:var(--muted); line-height:1.5; }
.gx-badge { display:inline-block; font-size:0.7rem; font-weight:700; letter-spacing:0.06em; padding:2px 8px;
  border-radius:6px; margin-right:8px; border:1px solid transparent; }
.gx-measured { background:#e5effb; color:#1c5cab; border-color:#b5cff2; }
.gx-estimated { background:#fdeee6; color:#a3401a; border-color:#f5c3ab; }
.gx-derived { background:#eef2f6; color:#334155; border-color:#cfd8e1; }
.gx-interpolated { background:#efebfa; color:#5b3a9b; border-color:#d3c8f1; }
.gx-mixed { background:#fff7e0; color:#7a5300; border-color:#f2d58a; }
.gx-meta { display:grid; grid-template-columns:118px 1fr; gap:5px 14px; font-size:0.86rem; margin:10px 0 12px; }
.gx-meta dt { color:var(--muted); font-size:0.78rem; padding-top:1px; }
.gx-meta dd { margin:0; color:var(--ink); }
.gx-detail-title { font-family:"Space Grotesk", sans-serif; font-weight:600; font-size:1.18rem; color:var(--ink);
  margin:2px 0 6px; line-height:1.25; }

/* maps and widgets */
iframe[title="streamlit_folium.st_folium"] { border-radius:16px; border:1px solid var(--line);
  box-shadow:0 6px 20px rgba(15,27,45,0.06); }
[data-testid="stDeckGlJsonChart"] { border-radius:16px; overflow:hidden; border:1px solid var(--line); }
[data-testid="stTabs"] [role="tablist"] { gap:6px; border-bottom:1px solid var(--line); }
[data-testid="stTab"] { padding:8px 14px; font-weight:500; }
button[kind="primary"], [data-testid="stBaseButton-primary"] { background:linear-gradient(135deg, #0e7490, #0b7c98) !important;
  border-color:#0e7490 !important; color:#ffffff !important; font-weight:600; }
[data-testid="stPageLink"] a { border:1px solid #c5e4ec; border-radius:10px; padding:4px 12px; justify-content:center;
  background:#f8fbfc; }
[data-testid="stPageLink"] a:hover { background:#ecf8fb; border-color:var(--accent); }
</style>
"""

LEAFLET_CSS = """
<style>
.leaflet-container { font-family:Inter, system-ui, sans-serif; font-size:12px; }
.leaflet-container .leaflet-control-attribution, .leaflet-container .leaflet-control-scale-line { font-size:11px; }
.leaflet-tooltip { border-radius:8px; border:1px solid #dbe4ec; box-shadow:0 6px 18px rgba(15,27,45,0.15); color:#0f1b2d; }
.leaflet-control-layers, .leaflet-bar { border-radius:10px !important; }
</style>
"""

CARTO_ATTR = "© OpenStreetMap contributors © CARTO"
TILES = {
    "Light": ("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", CARTO_ATTR, 20),
    "Streets": ("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", CARTO_ATTR, 20),
    "Satellite": ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                  "Imagery © Esri", 19),
    "Topographic (relief)": ("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                             "© OpenStreetMap contributors, SRTM · style © OpenTopoMap (CC-BY-SA)", 17),
    "Dark": ("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", CARTO_ATTR, 20),
}


def apply_style():
    st.markdown(_CSS % {"art": ART_URL}, unsafe_allow_html=True)


# ---- headers, cards, chips -------------------------------------------------------------
def hero(title, subtitle, chips=(), eyebrow=None, large=False, byline=None):
    """Header card. `chips` and `byline` may hold simple HTML written by the app (never user input)."""
    eyebrow = config.APP_NAME if eyebrow is None else eyebrow
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


@st.cache_data(show_spinner=False, max_entries=2)
def _portrait_src(name, stamp):
    """The portrait as a data: URL, so it survives in the HTML the sidebar writes. Empty when there is no file."""
    f = config.ASSETS / name
    try:
        kind = mimetypes.guess_type(name)[0] or "image/jpeg"
        return f"data:{kind};base64," + base64.b64encode(f.read_bytes()).decode("ascii")
    except OSError:  # no portrait saved yet
        return ""


def portrait_src():
    f = config.ASSETS / (config.CREDITS.get("photo") or "")
    if not config.CREDITS.get("photo") or not f.exists():
        return ""
    return _portrait_src(config.CREDITS["photo"], f.stat().st_mtime_ns)


def sidebar_credit():
    c = config.CREDITS
    if c.get("name"):
        src = portrait_src()
        body = ((f'<img class="p" src="{src}" alt="">' if src else "")
                + f'<div class="n">{html.escape(c["name"])}</div>'
                + (f'<div class="r">{html.escape(c["role"])}</div>' if c.get("role") else "")
                + (f'<div class="r">Supervisor: {html.escape(c["supervisor"])}</div>' if c.get("supervisor") else ""))
    else:
        body = (f'<div class="n">{html.escape(config.APP_NAME)}</div>'
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
    st.markdown(f'<div class="gx-kpis" style="--cols:{int(cols)}">{cards}</div>', unsafe_allow_html=True)


def _lum(hex_colour):
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return sum(w * (v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4) for w, v in zip((0.2126, 0.7152, 0.0722), (r, g, b)))


def _text_on(hex_colour):
    """Ink or white, whichever contrasts more with the background colour."""
    lum = _lum(hex_colour)
    return INK if (lum + 0.05) / (_lum(INK) + 0.05) >= 1.05 / (lum + 0.05) else "#ffffff"


def class_tags(suffix=""):
    """NBCC site-class chips, A to E, in the map colours."""
    from .insight import CLASS_WORDS
    tags = "".join(f'<span class="gx-tag" style="background:{c};color:{_text_on(c)}">{k} · {CLASS_WORDS[k]}</span>'
                   for k, c in SITE_CLASS_COLOURS.items() if k in CLASS_WORDS)
    st.markdown(f'<div class="gx-tags">{tags}</div>'
                + (f'<div class="gx-note">{html.escape(suffix)}</div>' if suffix else ""), unsafe_allow_html=True)


STATUS_WORDS = {
    "measured": ("MEASURED", "gx-measured", "from a test at that spot (SPT N, downhole Vs, a site's Vs30 from a seismic "
                                           "survey there)"),
    "derived": ("DERIVED", "gx-derived", "computed from measurements (a Vs-depth curve inverted from MASW, site class "
                                         "from a measured Vs30, region from coordinates)"),
    "estimated": ("ESTIMATED", "gx-estimated", "from a lookup, not a test (archive Vs30 and site class from lithology)"),
    "interpolated": ("INTERPOLATED", "gx-interpolated", "between measured sites (site-report Vs30 estimate)"),
}


VALUE_BADGES = {"Measured": "gx-measured", "Derived": "gx-derived", "Estimated": "gx-estimated",
                "Interpolated": "gx-interpolated", "Mixed": "gx-mixed"}


def value_badge(status):
    """A coloured badge for a dataset's value status (measured, derived, ...)."""
    s = str(status or "not stated")
    word = s.split(" (")[0].upper()
    return f'<span class="gx-badge {VALUE_BADGES.get(s.split(" ")[0], "gx-derived")}">{html.escape(word)}</span>'


def can_download(record):
    """Contributed files marked Registered users or Restricted are listed but not served (no sign-in yet)."""
    return (record.get("access_level") or "Public") == "Public"


def status_legend():
    st.markdown("".join(f'<div style="margin:0 0 9px"><span class="gx-badge {cls}">{word}</span>'
                        f'<span class="gx-note">{html.escape(text)}</span></div>'
                        for word, cls, text in STATUS_WORDS.values()), unsafe_allow_html=True)


def flow(steps):
    """A numbered left-to-right flow of (title, detail) steps, with arrows between them on wide screens."""
    st.markdown('<div class="gx-flow">' + "".join(
        f'<div class="st"><div class="n">STEP {i}</div><div class="t">{html.escape(t)}</div>'
        f'<div class="d">{html.escape(d)}</div></div>' for i, (t, d) in enumerate(steps, 1)) + "</div>",
        unsafe_allow_html=True)


def panel_title(text):
    st.markdown(f'<div class="gx-panel-title">{html.escape(text)}</div>', unsafe_allow_html=True)


def status_rows(items):
    """items: (ok, title, detail). A tick or a warning sign, a bold title and one line of detail."""
    st.markdown("".join(
        f'<div class="gx-status"><div class="i {"ok" if ok else "todo"}">{"✓" if ok else "!"}</div>'
        f'<div><div class="t">{html.escape(t)}</div><div class="d">{html.escape(d)}</div></div></div>'
        for ok, t, d in items), unsafe_allow_html=True)


# ---- maps --------------------------------------------------------------------------------
def base_map(location=(45.55, -73.66), zoom=11, layers=("Light", "Streets", "Satellite", "Topographic (relief)")):
    """A folium map on a light basemap, with the other basemaps one click away."""
    m = folium.Map(location=list(location), zoom_start=zoom, tiles=None, control_scale=True, font_size="12px")
    for i, name in enumerate(layers):
        url, attr, max_zoom = TILES[name]
        folium.TileLayer(url, name=name, attr=attr, max_zoom=max_zoom, show=i == 0).add_to(m)
    m.get_root().header.add_child(folium.Element(LEAFLET_CSS))
    return m


def add_regions(m, selected=(), show=True, interactive=True):
    """Borough and city outlines, with the selected ones filled. Hover shows the name when interactive; maps that
    take clicks (placing a point, drawing) pass interactive=False so a click never picks up a whole region."""
    gj = geo.regions_geojson()
    if not gj:
        return
    sel = set(selected)
    extra = {} if interactive else {"interactive": False}
    folium.GeoJson(
        gj, name="Boroughs and cities", show=show,
        style_function=lambda f: {"color": ACCENT_DARK if f["properties"]["region"] in sel else "#5b7083",
                                  "weight": 2.2 if f["properties"]["region"] in sel else 0.8,
                                  "dashArray": None if f["properties"]["region"] in sel else "3 3",
                                  "fillColor": ACCENT, "fillOpacity": 0.10 if f["properties"]["region"] in sel else 0.0,
                                  **extra},
        **({"highlight_function": lambda f: {"weight": 2.2, "color": ACCENT_DARK, "fillOpacity": 0.06},
            "tooltip": folium.GeoJsonTooltip(fields=["region", "kind"], aliases=["", ""], labels=False)}
           if interactive else {}),
    ).add_to(m)


def safe_tip(text):
    """Text for a folium tooltip or popup. Folium pastes it into a JavaScript template literal unescaped, so
    contributor text is escaped as HTML and the characters that would end or alter that literal are encoded."""
    return (html.escape(str(text)).replace("`", "&#96;").replace("$", "&#36;").replace("\\", "&#92;"))


def class_chips_html(classes="ABCDE"):
    """Small A to E swatches in the class colours, for a compact key under a chart or on a map."""
    return '<span style="display:inline-flex;gap:3px;vertical-align:middle">' + "".join(
        f'<span title="Class {k}" style="display:inline-flex;align-items:center;justify-content:center;width:20px;'
        f'height:15px;background:{SITE_CLASS_COLOURS[k]};color:{_text_on(SITE_CLASS_COLOURS[k])};font-size:10px;'
        f'font-weight:700;border-radius:3px">{k}</span>' for k in classes) + "</span>"


def pin_icon(colour, size=16):
    """A teardrop pin in one of the data colours (folium's built-in icons only come in a few fixed colours)."""
    return folium.DivIcon(icon_size=(size, size), icon_anchor=(size // 2, size),
                          html=f'<div style="width:{size}px;height:{size}px;background:{colour};border:2px solid #fff;'
                               f'border-radius:50% 50% 50% 0;transform:rotate(-45deg);'
                               f'box-shadow:0 2px 6px rgba(15,27,45,0.45)"></div>')


def target_icon(size=26):
    return folium.DivIcon(icon_size=(size, size), icon_anchor=(size // 2, size // 2),
                          html=f'<div style="width:{size}px;height:{size}px;border-radius:50%;border:2.5px solid {ACCENT_DARK};'
                               f'background:rgba(255,255,255,0.75);box-shadow:0 0 0 4px rgba(8,145,178,0.25);'
                               f'display:flex;align-items:center;justify-content:center"><div style="width:7px;height:7px;'
                               f'border-radius:50%;background:{ACCENT_DARK}"></div></div>')


# ---- data and settings -------------------------------------------------------------------
def secrets():
    try:
        return dict(st.secrets)
    except Exception:  # no secrets file
        return {}


def require_app_password():
    """One shared password for the whole app, read from APP_PASSWORD in the secrets.

    Without that secret the app stays open to anyone with the link, which is the usual setting for a shared archive.
    With it, nothing is shown until the password is typed: the visitor is stopped here, before the pages are built.
    It is remembered for the browser tab only, so closing the tab asks again."""
    pw = secrets().get("APP_PASSWORD")
    if not pw or st.session_state.get("_unlocked"):
        return
    hero(config.APP_NAME, "A shared archive of geotechnical data collected on the island since 2001. "
         "Ask the curator for the password.", eyebrow="Private")
    typed = st.text_input("Password", type="password")
    if typed == pw:
        st.session_state["_unlocked"] = True
        st.rerun()
    if typed:
        st.error("That password is not right.")
    st.stop()


# Names this load of the geotech modules. Map.py reloads them all together after an update, so the shared caches
# below are keyed on it: a visitor whose run still has the old modules can only fill entries for the old code, never
# the entries the new code reads (keying on the files on disk would let it do that).
LOADED = uuid.uuid4().hex


@st.cache_resource(max_entries=2, show_spinner=False)
def _store(loaded):
    return storage.get_store(secrets())


def get_store():
    """The shared store for contributed files, built by the code this page runs with."""
    return _store(LOADED)


def _stamp(*paths):
    """Cache key part for tables: the data files as they are now, and this load of the code (which also covers the
    region limits and island outline, since a change to them reloads the modules)."""
    return tuple((str(f), f.stat().st_mtime_ns if f.exists() else 0) for f in paths) + (LOADED,)


# A few entries each: the stamp changes with every update, and older copies would otherwise stay in memory.
@st.cache_data(show_spinner="Loading the borehole archive…", max_entries=4)
def _load_archive(use_demo, stamp):
    return data.load_archive(use_demo)


def load_archive(use_demo):
    return _load_archive(use_demo, _stamp(config.BOREHOLES_CSV, config.SAMPLES_CSV, config.DEMO_BOREHOLES_CSV,
                                          config.DEMO_SAMPLES_CSV))


@st.cache_data(max_entries=2)
def _load_vs(stamp):
    return data.load_vs()


def load_vs():
    return _load_vs(_stamp(config.VS30_SITES_CSV, config.VS_PROFILES_CSV))


def region_names():
    return geo.region_names()


def archive_banner(label):
    if label == "none":
        st.info("The borehole archive is not loaded yet, so only measured Vs and contributed files are shown.",
                icon=":material/info:")
    elif label.startswith("DEMO"):
        st.error("Showing DEMO boreholes: synthetic points to try the app, not real data. "
                 "Add data/boreholes.csv and data/spt_samples.csv to show the archive.")


def mime_of(record):
    """The file's media type for its download button (files are fetched only when the button is pressed)."""
    return record.get("mime") or mimetypes.guess_type(record.get("file_name") or "")[0] or "application/octet-stream"


def storage_banner(store):
    if store.temporary:
        st.info("Uploads are kept in a temporary local folder and are lost when the app restarts. "
                "Add Supabase settings to the app's secrets for permanent shared storage.")
