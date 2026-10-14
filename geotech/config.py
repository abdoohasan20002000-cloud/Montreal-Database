"""Settings shared by every page. Change column names here, not in the pages."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# Archive files kept in the repo (small enough for git: about 7k holes, 39k samples).
BOREHOLES_CSV = DATA_DIR / "boreholes.csv"
SAMPLES_CSV = DATA_DIR / "spt_samples.csv"
VS30_SITES_CSV = DATA_DIR / "vs30_sites.csv"        # measured Vs30 sites (Rosset compilation)
VS_PROFILES_CSV = DATA_DIR / "vs_profiles.csv"      # Vs-depth profiles
ISLAND_OUTLINE = DATA_DIR / "island_outline.geojson"  # optional, enables the precise island check
REGIONS_GEOJSON = DATA_DIR / "regions.geojson"  # boroughs and linked cities (scripts/fetch_regions.py)
OFF_ISLAND = "Off the island"  # region label for points outside every borough and city
DEMO_BOREHOLES_CSV = DATA_DIR / "demo" / "boreholes_DEMO.csv"
DEMO_SAMPLES_CSV = DATA_DIR / "demo" / "spt_samples_DEMO.csv"

# Coordinates: storage and analysis in MTM zone 8; WGS84 only for the web map.
CRS_MTM8 = "EPSG:32188"
CRS_WGS84 = "EPSG:4326"

# Rough island box (WGS84), used only when no outline file is present.
ISLAND_BBOX = {"lon_min": -73.99, "lon_max": -73.46, "lat_min": 45.40, "lat_max": 45.71}
SHORE_TOLERANCE_M = 250

# Credit shown on the home page and at the foot of the sidebar. Leave a field empty to hide it.
CREDITS = {"name": "", "role": "", "supervisor": ""}
DATA_CREDIT = ("Measured Vs: Rosset et al. compilation · Borehole archive: City of Montréal, MTQ and MELCC")

PRE_MODERN_YEAR = 1960  # pre-1960 SPT N reads about half of modern values (era multiplier ~1.7)
VS30_MIN, VS30_MAX = 100, 3000

# Accepted spellings for archive columns. The first match wins.
BOREHOLE_COLUMNS = {
    "hole_id": ["hole_id", "HOLE_ID", "borehole_id", "id_forage"],
    "x_mtm8": ["x_mtm8", "X_MTM8", "x", "X", "easting"],
    "y_mtm8": ["y_mtm8", "Y_MTM8", "y", "Y", "northing"],
    "year": ["year", "YEAR", "drill_year", "annee"],
    "source": ["source", "SOURCE", "source_org"],
    "data_era": ["data_era", "DATA_ERA"],
    "depth_m": ["depth_m", "total_depth_m", "DEPTH"],
    "bedrock_depth_m": ["bedrock_depth_m", "depth_to_bedrock_m"],
    "bedrock_position": ["bedrock_position"],
    "vs30_ms": ["vs30_ms", "VS30", "vs30"],
    "vs30_status": ["vs30_status"],
    "site_class": ["site_class", "nbcc_site_class", "SITE_CLASS"],
    "main_unit": ["main_unit"],
    "region": ["region", "borough"],
    "qa_flags": ["qa_flags"],
}
SAMPLE_COLUMNS = {
    "hole_id": ["hole_id", "HOLE_ID", "borehole_id"],
    "sample_no": ["sample_no", "SAMPLE_NO"],
    "depth_top_m": ["depth_top_m", "top_m", "DEPTH_TOP"],
    "depth_bot_m": ["depth_bot_m", "bottom_m", "DEPTH_BOT"],
    "n_field": ["n_field", "N_FIELD"],
    "refusal": ["refusal", "REFUSAL", "is_refusal"],
    "uscs": ["uscs", "USCS"],
    "qa_flags": ["qa_flags"],
}

# Any kind of ground data collected in Montréal. Older uploads may carry earlier names ("Lab results", "Geophysics").
DATA_TYPES = [
    "Borehole log", "SPT (standard penetration test)", "CPT / CPTu (cone penetration)",
    "Lab tests (index, strength, consolidation)", "Shear-wave velocity (Vs, Vs30)", "Ambient vibration (H/V, f0)",
    "Other geophysics (ERT, GPR, refraction)", "Groundwater (piezometers, levels)", "Bedrock depth or outcrop",
    "Monitoring (settlement, inclinometers, vibration)", "Ground deformation (InSAR, levelling)",
    "Earthquake or strong-motion record", "Environmental sampling (soil, water)", "Map / GIS layer", "Report",
    "Photo or scan", "Other",
]
SOURCE_ORGS = ["City of Montréal", "MTQ", "MELCC", "Consultant", "University", "Private", "Other"]
VALUE_STATUS = ["Measured", "Derived", "Interpolated", "Estimated", "Mixed", "Not applicable (no numerical values)"]
LICENCES = ["CC BY 4.0", "Open Government Licence – Québec", "Restricted, no reuse", "Not stated (ask the source)",
            "Other (see notes)"]
ACCESS_LEVELS = ["Public", "Registered users", "Restricted"]
SINCE_YEAR = 2001  # the "since 2001" preset in the catalogue year filter


TIMEZONE = ZoneInfo("America/Montreal")


def today():
    """Today's date in Montréal. The server's clock is on UTC, which is already tomorrow from 20:00 EDT."""
    return datetime.now(TIMEZONE).date()
