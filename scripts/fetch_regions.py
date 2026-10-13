"""Download the boroughs and linked cities of the Montréal agglomeration and save them as the app's regions.

Source: Ville de Montréal open data, "Limites administratives de l'agglomération de Montréal (arrondissements et
villes liées)", licence CC BY 4.0. Found through the portal's CKAN API so a changed file name does not break it.

Writes
    data/regions.geojson        one feature per borough or linked city (WGS84), with name, kind, source and date
    data/island_outline.geojson the union of all regions, used by the on-island checks
    data/regions_report.txt     what was downloaded and what was done to it

Boundaries are simplified by 2 m (in MTM 8) to keep the file small; a point within 2 m of a boundary can fall in
the neighbouring region. Runs in the GitHub Action .github/workflows/fetch-regions.yml, or locally:

    python scripts/fetch_regions.py
"""
import json
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
import shapely

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
API = "https://donnees.montreal.ca/api/3/action/"
SLUG = "limites-administratives-agglomeration"
LICENCE = "CC BY 4.0 (Ville de Montréal open data)"
SIMPLIFY_M = 2.0

to_mtm = Transformer.from_crs("EPSG:4326", "EPSG:32188", always_xy=True)
to_wgs = Transformer.from_crs("EPSG:32188", "EPSG:4326", always_xy=True)


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "montreal-geotech-atlas/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def find_geojson():
    """(dataset title, resource url) of the GeoJSON boundary file."""
    packages = []
    try:
        packages.append(json.loads(get(API + "package_show?id=" + SLUG))["result"])
    except Exception as e:  # slug changed: search instead
        print(f"package_show failed ({e}); searching")
    if not packages:
        q = urllib.parse.quote("limites administratives agglomération")
        packages = json.loads(get(API + f"package_search?q={q}&rows=20"))["result"]["results"]
    found = []
    for pkg in packages:
        if "limite" not in (pkg.get("title", "") + pkg.get("name", "")).lower():
            continue
        for res in pkg.get("resources", []):
            url = res.get("url", "")
            if (res.get("format") or "").lower() == "geojson" or url.lower().endswith(".geojson"):
                # prefer the plain WGS84 file over projected copies
                penalty = sum(k in url.lower() for k in ("mtm", "nad83", "32188", "2950"))
                found.append((penalty, pkg.get("title", ""), url))
    if not found:
        raise SystemExit("No GeoJSON resource found in the boundaries dataset")
    found.sort()
    return found[0][1], found[0][2]


def pick(props, *names):
    low = {k.lower(): v for k, v in props.items()}
    for n in names:
        if low.get(n.lower()) not in (None, ""):
            return low[n.lower()]
    return None


def main():
    title, url = find_geojson()
    raw = json.loads(get(url))
    feats = raw["features"]
    geoms = [shape(f["geometry"]) for f in feats]
    projected = all(abs(g.bounds[0]) > 180 for g in geoms)  # metres, not degrees
    rows = []
    for f, g in zip(feats, geoms):
        p = f.get("properties") or {}
        name = pick(p, "NOM", "nom", "NOM_OFFICIEL", "name")
        kind_raw = str(pick(p, "TYPE", "type") or "")
        kind = "Borough" if kind_raw.lower().startswith("arr") else "City" if "ville" in kind_raw.lower() else kind_raw
        g_mtm = g if projected else shapely.transform(g, to_mtm.transform, interleaved=False)
        g_mtm = g_mtm.buffer(0).simplify(SIMPLIFY_M, preserve_topology=True)
        rows.append({"name": str(name), "kind": kind, "code": pick(p, "CODEID", "CODE_3C", "ABREV", "NUM"),
                     "g_mtm": g_mtm})
    # one feature per name (some territories come as several pieces)
    merged = {}
    for r in rows:
        if r["name"] in merged:
            merged[r["name"]]["g_mtm"] = merged[r["name"]]["g_mtm"].union(r["g_mtm"])
        else:
            merged[r["name"]] = r
    today = date.today().isoformat()
    out = []
    for r in sorted(merged.values(), key=lambda r: (r["kind"] != "Borough", r["name"])):
        g_wgs = shapely.set_precision(shapely.transform(r["g_mtm"], to_wgs.transform, interleaved=False), 1e-6)
        out.append({"type": "Feature", "geometry": mapping(g_wgs),
                    "properties": {"region": r["name"], "kind": r["kind"], "code": r["code"],
                                   "area_km2": round(r["g_mtm"].area / 1e6, 2), "source": title, "source_url": url,
                                   "licence": LICENCE, "fetched_on": today,
                                   "method": f"downloaded, simplified {SIMPLIFY_M:g} m in MTM 8 (EPSG:32188)"}})
    (DATA / "regions.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": out},
                                                     ensure_ascii=False), encoding="utf-8")
    island = unary_union([r["g_mtm"] for r in merged.values()])
    island_wgs = shapely.set_precision(shapely.transform(island, to_wgs.transform, interleaved=False), 1e-6)
    (DATA / "island_outline.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": mapping(island_wgs),
        "properties": {"name": "Montréal agglomeration (union of regions)", "source": title, "source_url": url,
                       "licence": LICENCE, "fetched_on": today}}]}, ensure_ascii=False), encoding="utf-8")
    kinds = {}
    for r in merged.values():
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    report = [f"regions.geojson: {len(out)} regions from {len(feats)} features ({', '.join(f'{v} {k}' for k, v in kinds.items())})",
              f"source: {title}", f"url: {url}", f"licence: {LICENCE}", f"fetched on: {today}",
              f"input coordinates: {'projected metres (taken as MTM 8)' if projected else 'WGS84'}",
              f"simplified {SIMPLIFY_M:g} m in MTM 8; island outline = union of all regions, "
              f"{island.area / 1e6:.1f} km²",
              "regions: " + "; ".join(r["name"] for r in sorted(merged.values(), key=lambda r: r["name"]))]
    (DATA / "regions_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
