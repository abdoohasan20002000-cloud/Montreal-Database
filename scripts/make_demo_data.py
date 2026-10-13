"""Write synthetic DEMO boreholes so the app can be tried before the real archive is added.

Every value here is random. Files are named *_DEMO.csv and the app labels them as demo data.
Usage: python scripts/make_demo_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

rng = np.random.default_rng(42)
out = Path(__file__).resolve().parent.parent / "data" / "demo"
out.mkdir(parents=True, exist_ok=True)

# Random points in a box over central Montréal, converted to MTM 8.
n = 400
lon = rng.uniform(-73.75, -73.53, n)
lat = rng.uniform(45.45, 45.60, n)
x, y = Transformer.from_crs("EPSG:4326", "EPSG:32188", always_xy=True).transform(lon, lat)
year = rng.integers(1927, 2010, n)
vs30 = rng.uniform(190, 1600, n).round(0)
site = np.select([vs30 > 1500, vs30 > 760, vs30 > 360, vs30 > 180], ["A", "B", "C", "D"], "E")
bh = pd.DataFrame({
    "hole_id": [f"DEMO-{i:04d}" for i in range(n)], "x_mtm8": np.round(x, 2), "y_mtm8": np.round(y, 2),
    "year": year, "source": rng.choice(["City of Montréal", "MTQ", "MELCC"], n),
    "depth_m": rng.uniform(3, 30, n).round(1), "vs30_ms": vs30,
    "vs30_status": "DEMO value (synthetic)", "site_class": site,
})
bh.to_csv(out / "boreholes_DEMO.csv", index=False)

rows = []
for h, d in zip(bh["hole_id"], bh["depth_m"]):
    for top in np.arange(0.6, d - 0.6, 1.5):
        refusal = rng.random() < 0.08
        rows.append({"hole_id": h, "depth_top_m": round(top, 2), "depth_bot_m": round(top + 0.6, 2),
                     "n_field": None if refusal else int(rng.integers(2, 60)), "refusal": refusal,
                     "uscs": rng.choice(["CL", "ML", "SM", "SP", "GW"])})
pd.DataFrame(rows).to_csv(out / "spt_samples_DEMO.csv", index=False)
print(f"wrote {len(bh)} demo boreholes and {len(rows)} demo samples to {out}")
