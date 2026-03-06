"""
download_drought_data.py
------------------------
Downloads the most recent US Drought Monitor (USDM) shapefile and converts
it to a GeoJSON file for display in the app.

Source: https://droughtmonitor.unl.edu
USDM releases new maps each Tuesday (Midnight Tuesday / end of Monday).

Output
------
  usdm_drought.geojson  – Drought polygons with DM field (0=D0 … 4=D4)
"""

import io
import os
import zipfile
import tempfile
import requests
import geopandas as gpd
from datetime import date, timedelta
from typing import Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

def most_recent_usdm_tuesday(ref: Optional[date] = None) -> date:
    """Return the most recent Tuesday (USDM release day)."""
    d = ref or date.today()
    days_back = (d.weekday() - 1) % 7   # Mon=0, Tue=1 → 0 days back on Tue
    return d - timedelta(days=days_back)


# ── US Drought Monitor ────────────────────────────────────────────────────────

# Official USDM drought category colors
USDM_COLORS = {0: "#FFFF00", 1: "#FCD37F", 2: "#FFAA00", 3: "#E60000", 4: "#730000"}
USDM_LABELS = {
    0: "D0 – Abnormally Dry",
    1: "D1 – Moderate Drought",
    2: "D2 – Severe Drought",
    3: "D3 – Extreme Drought",
    4: "D4 – Exceptional Drought",
}


def download_usdm_geojson(out_path: str = "usdm_drought.geojson") -> None:
    """
    Download the most recent USDM weekly shapefile and save as GeoJSON.

    The shapefile contains polygons for each drought category (DM 0–4).
    If the most recent Tuesday's file isn't up yet, falls back one week.
    """
    tuesday = most_recent_usdm_tuesday()

    for attempt in range(3):
        date_str = tuesday.strftime("%Y%m%d")
        url = f"https://droughtmonitor.unl.edu/data/shapefiles_m/USDM_{date_str}_M.zip"
        print(f"Downloading USDM shapefile for {date_str} …")
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200:
            break
        print(f"  {resp.status_code} – trying previous week …")
        tuesday -= timedelta(weeks=1)
    else:
        raise RuntimeError("Could not download USDM shapefile after 3 attempts.")

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            z.extractall(tmp)
        shp_files = [f for f in os.listdir(tmp) if f.endswith(".shp")]
        if not shp_files:
            raise FileNotFoundError("No .shp file found in USDM zip.")
        gdf = gpd.read_file(os.path.join(tmp, shp_files[0]))

    # Ensure WGS84 (already EPSG:4326 in practice, but be safe)
    gdf = gdf.to_crs(epsg=4326)

    # Add human-readable label and hex colour for folium
    gdf["dm_category"] = gdf["DM"].astype(int)
    gdf["dm_label"] = gdf["dm_category"].map(USDM_LABELS)
    gdf["dm_color"] = gdf["dm_category"].map(USDM_COLORS)
    gdf["map_date"] = date_str

    gdf.to_file(out_path, driver="GeoJSON")
    print(f"  ✓ {len(gdf)} drought polygons  →  {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    download_usdm_geojson()
    print("\nDone. usdm_drought.geojson is ready for app.py.")
