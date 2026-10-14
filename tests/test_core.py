import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point

from geotech import data, geo, validate
from geotech.storage import LocalStore


def test_round_trip_mtm8():
    x, y = geo.wgs84_to_mtm8(-73.5673, 45.5017)  # downtown
    lon, lat = geo.mtm8_to_wgs84(x, y)
    assert abs(lon + 73.5673) < 1e-6 and abs(lat - 45.5017) < 1e-6
    assert geo.on_island(x, y)
    assert not geo.on_island(*geo.wgs84_to_mtm8(-73.0, 45.5))


def test_table_checks_flag_project_rules():
    x, y = geo.wgs84_to_mtm8(-73.6, 45.5)
    df = pd.DataFrame({"HOLE_ID": ["A", "A", "B"], "depth_top_m": [0, 1.0, 2], "depth_bot_m": [1.5, 0.5, 2.6],
                       "N_FIELD": [10, 999, 20]})
    msgs = " ".join(m for _, m in validate.check_table(df))
    assert "N = 999" in msgs and "No refusal column" in msgs and "bottom not below top" in msgs
    bh = pd.DataFrame({"hole_id": ["A", "A"], "x_mtm8": [x, y], "y_mtm8": [y, x], "vs30_ms": [50, 400], "year": [1950, 1980]})
    msgs = " ".join(m for _, m in validate.check_table(bh))
    assert "repeat" in msgs and "swapped" in msgs and "Vs30" in msgs and "vs30_status" in msgs and "before 1960" in msgs


def test_upload_blocks_duplicate_and_off_island():
    on = Point(*geo.wgs84_to_mtm8(-73.6, 45.5))
    off = Point(*geo.wgs84_to_mtm8(-72.0, 46.0))
    rep, h = validate.check_upload(b"abc", "x.jpg", on, 1955, {})
    assert not any(l == "block" for l, _ in rep) and any("pre-1960" in m for _, m in rep)
    rep, _ = validate.check_upload(b"abc", "x.jpg", off, 2000, {h: "u1"})
    assert sum(l == "block" for l, _ in rep) == 2


def test_refusal_blank_is_false():
    assert data._as_bool(float("nan")) is False and data._as_bool("1") is True


def test_selection_and_local_store(tmp_path):
    x, y = geo.wgs84_to_mtm8(-73.6, 45.5)
    bh = pd.DataFrame({"hole_id": ["near", "far"], "x_mtm8": [x + 100, x + 5000], "y_mtm8": [y, y]})
    area = data.selection_from_inputs("Point and radius", click={"lat": 45.5, "lng": -73.6}, radius_m=500)
    assert list(data.points_in(bh, area)["hole_id"]) == ["near"]
    assert data.selection_from_inputs("Whole island") is None
    s = LocalStore(tmp_path)
    s.add({"id": "u1", "file_name": "a b.pdf", "status": "pending", "footprint_wkt_mtm8": Point(x, y).wkt}, b"%PDF")
    assert s.get_bytes(s.list()[0]) == b"%PDF"
    s.update("u1", status="approved")
    assert len(data.uploads_in(s.list("approved"), area)) == 1


def test_zip_bundle_contents():
    import io, zipfile
    from geotech import bundle
    bh = pd.DataFrame({"hole_id": ["A"], "x_mtm8": [1.0], "y_mtm8": [2.0]})
    s = pd.DataFrame({"hole_id": ["A"], "n_field": [12], "refusal": [False]})
    up = [{"id": "u1", "file_name": "log.pdf", "title": "t"}]
    z = zipfile.ZipFile(io.BytesIO(bundle.build_zip(bh, s, up, lambda r: b"%PDF", "whole island", "archive")))
    assert set(z.namelist()) == {"README.txt", "boreholes.csv", "spt_samples.csv", "manifest.csv", "files/u1_log.pdf"}
    assert "ESTIMATED" in z.read("README.txt").decode()


def test_measured_vs_tables_follow_project_rules():
    sites, prof = data.load_vs()
    assert len(sites) == 159 and sites["site_id"].is_unique
    assert sites["vs30_status"].str.startswith(("measured", "no value")).all()
    assert sites["vs30_ms"].dropna().between(100, 3000).all()
    assert {"method", "source", "processed_on"} <= set(sites.columns)
    assert prof["vs_status"].notna().all() and not prof["duplicate_of_earlier_sheet"].astype(bool).any()
    assert set(prof["vs_status"]) == {"measured (downhole seismic)",
                                      "derived (inversion of surface-wave dispersion)",
                                      "derived (interval velocity from two-way travel times)",
                                      "method not stated in the source (do not call measured)"}


def test_no_archive_means_empty_not_demo():
    bh, _, label = data.load_archive(False)
    assert bh.empty and label == "none"


def test_site_report_estimates_are_labelled_and_sane():
    from geotech import insight
    sites, _ = data.load_vs()
    x, y = geo.wgs84_to_mtm8(-73.556, 45.557)  # Botanical Garden line
    near = insight.neighbours(sites, x, y, 2000)
    est, n = insight.idw_vs30(near)
    assert n > 0 and near["vs30_ms"].min() <= est <= near["vs30_ms"].max()
    table = insight.report_table(45.557, -73.556, x, y, 2000, near, est, n)
    assert set(table["status"]) >= {"measured", "interpolated", "derived"}
    text = insight.summary(45.557, -73.556, 2000, near, est, n, 0, 0, None, True)
    assert "INTERPOLATED" in text and "not a measurement" in text
    empty = insight.neighbours(sites, *geo.wgs84_to_mtm8(-74.5, 46.5), 1000)
    assert insight.idw_vs30(empty) == (None, 0)


def test_regression_curves_match_published_coefficients():
    from geotech import insight
    c = insight.regression_curves(insight.load_regressions())
    sand = c[c["fit"].str.startswith("sand")].set_index("depth_m")["vs_ms"]
    z = sand.index[0]
    assert abs(sand.iloc[0] - (144.808986 + 36.806129 * z ** 0.570622)) < 1e-6


def test_regions_are_assigned_from_city_limits():
    pts = [(-73.5673, 45.5017), (-73.80, 45.47), (-73.0, 45.5)]  # downtown, Pointe-Claire, east of the river
    xy = [geo.wgs84_to_mtm8(lon, lat) for lon, lat in pts]
    names = geo.region_of([p[0] for p in xy], [p[1] for p in xy])
    assert list(names) == ["Ville-Marie", "Pointe-Claire", "Off the island"]
    assert geo.region_of(float("nan"), float("nan"))[0] == ""
    assert geo.regions_touching(Point(*xy[0]).buffer(10)) == ["Ville-Marie"]
    assert len(geo.region_names()) == 34
    shp = data.selection_from_inputs("Region", click=["Ville-Marie"])
    assert shp.contains(Point(*xy[0])) and data.selection_from_inputs("Region", click=["Nowhere"]) == "incomplete"


def test_catalogue_filters_by_region_and_years():
    from geotech import catalogue
    sites = pd.DataFrame({"site_id": ["a", "b"], "vs30_ms": [300, None], "region": ["Ville-Marie", "Off the island"]})
    prof = pd.DataFrame({"site_id": ["a"], "region": ["Ville-Marie"]})
    up = [{"id": "u1", "submission_id": "s1", "title": "CPT", "data_type": "CPT / CPTu (cone penetration)",
           "work_year": 2005, "work_year_end": 2007, "region": "LaSalle", "file_size": 1e6, "access_level": "Public"},
          {"id": "u2", "submission_id": "s1", "title": "CPT", "data_type": "CPT / CPTu (cone penetration)",
           "work_year": 2005, "region": "LaSalle; Verdun", "file_size": 1e6}]
    cat = catalogue.table(catalogue.builtin(sites, prof, pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
                          + catalogue.contributed(up))
    cpt = cat[cat["origin"] == "Contributed"].iloc[0]
    assert (cpt["year_from"], cpt["year_to"], cpt["regions"]) == (2005, 2007, ["LaSalle", "Verdun"])
    assert cpt["records"].startswith("2 files")
    pick = lambda **kw: set(cat[catalogue.matches(cat, **kw)]["key"])
    assert "up_s1" in pick(regions=["Verdun"]) and "vs30_sites" not in pick(regions=["Verdun"])
    assert "regions" in pick(regions=["Verdun"])  # island-wide entries match every region
    assert "up_s1" in pick(years=(2001, 2026)) and "up_s1" not in pick(years=(1990, 2000))
    assert "vs30_sites" in pick(years=(2001, 2026)) and "vs30_sites" not in pick(years=(2001, 2026), include_undated=False)
    assert pick(text="cone") == {"up_s1"}
    assert set(cat.loc[cat["key"] == "vs30_sites", "where"]) == {"Ville-Marie + off the island"}


def test_zip_lists_but_leaves_out_restricted_files():
    import io, zipfile
    from geotech import bundle
    up = [{"id": "u1", "file_name": "a.pdf", "access_level": "Public"},
          {"id": "u2", "file_name": "b.pdf", "access_level": "Restricted"}]
    z = zipfile.ZipFile(io.BytesIO(bundle.build_zip(pd.DataFrame(), pd.DataFrame(), up, lambda r: b"%PDF",
                                                    "Ville-Marie", "none")))
    assert "files/u1_a.pdf" in z.namelist() and "files/u2_b.pdf" not in z.namelist()
    man = pd.read_csv(z.open("manifest.csv"))
    assert list(man["in_zip"]) == [True, False]


def test_on_island_filter_keeps_unlocated_rows():
    df = pd.DataFrame({"on_island": pd.Series([True, False, None], dtype=object)})
    assert len(data.keep_on_island(df)) == 2


def test_tooltip_text_cannot_break_out_of_folium_template():
    from geotech import ui
    tip = ui.safe_tip("x`);alert(1);(`<img src=x onerror=alert(2)> ${y} C:\\users")
    assert not any(c in tip for c in "`$<>\\")


def test_shore_band_points_take_the_nearest_region():
    x, y = geo.wgs84_to_mtm8(-73.70307, 45.54655)  # inside the island check's 250 m tolerance, outside every region
    assert geo.on_island(x, y)
    assert geo.region_of(x, y)[0] == geo.regions_touching(Point(x, y))[0] != "Off the island"


def test_french_csv_decimal_commas_are_read_as_numbers():
    # pandas 3 reads text columns as its own string type, not object; both must be converted.
    x, y = geo.wgs84_to_mtm8(-73.6, 45.5)
    body = f"hole_id;x_mtm8;y_mtm8;depth_top_m;depth_bot_m\nA;{x:.2f};{y:.2f};1,5;0,5\n".replace(".", ",")
    df = validate._read_table(body.encode(), "trous.csv")
    assert df["depth_top_m"].tolist() == [1.5] and abs(df["x_mtm8"].iloc[0] - x) < 0.01
    msgs = " ".join(m for _, m in validate.check_table(df))
    assert "bottom not below top" in msgs and "All coordinates are on the island" in msgs


def test_large_tables_are_checked_on_their_first_rows(monkeypatch):
    monkeypatch.setattr(validate, "CHECK_ROWS", 5)
    body = "hole_id,n_field\n" + "".join(f"H{i},{i}\n" for i in range(20))
    rep = validate._check_content(body.encode(), "big.csv")
    assert "first 5 rows" in rep[0][1]


def test_island_check_on_many_points_matches_one_by_one():
    pts = [geo.wgs84_to_mtm8(lon, lat) for lon, lat in [(-73.6, 45.5), (-72.0, 46.0), (-73.95, 45.45), (-73.5, 45.7)]]
    xs, ys = zip(*pts)
    assert geo.on_island_many(xs, ys).tolist() == [geo.on_island(x, y) for x, y in pts]


def test_local_store_keeps_every_record_when_written_at_once(tmp_path):
    import threading
    store = LocalStore(tmp_path)
    assert store.temporary
    threads = [threading.Thread(target=store.add, args=({"id": f"u{i}", "file_name": "a.txt", "status": "pending"}, b"x"))
               for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r["id"] for r in store.list()) == sorted(f"u{i}" for i in range(20))


def test_supabase_store_is_marked_permanent():
    try:
        from supabase import create_client  # noqa: F401  (the repo's supabase/ folder alone does not count)
    except ImportError:
        pytest.skip("supabase is not installed")
    from geotech.storage import SupabaseStore
    store = SupabaseStore("https://example.supabase.co", "aaa.bbb.ccc")
    assert store.temporary is False and store.bucket == "uploads"


def test_terrain_retries_a_tile_that_failed(monkeypatch):
    from geotech import terrain
    calls = []

    def flaky(z, x, y):
        calls.append((z, x, y))
        if len(calls) == 1:
            raise OSError("timed out")
        return np.full((256, 256), 42.0)
    monkeypatch.setattr(terrain, "_read_tile", flaky)
    monkeypatch.setattr(terrain, "_failed_at", {})
    assert np.isnan(terrain.elevation(-73.6, 45.5)[0])
    assert np.isnan(terrain.elevation(-73.6, 45.5)[0]) and len(calls) == 1  # not retried at once
    monkeypatch.setattr(terrain, "RETRY_AFTER_S", 0)
    assert terrain.elevation(-73.6, 45.5)[0] == 42.0


def test_today_is_montreal_date():
    from datetime import datetime, timezone
    from geotech import config
    assert config.today() == datetime.now(timezone.utc).astimezone(config.TIMEZONE).date()
