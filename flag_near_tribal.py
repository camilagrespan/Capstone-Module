"""
flag_near_tribal.py
-------------------
Uses geopandas to flag any project in all_threats.csv that falls within
50 miles (~80,467 m) of a federally recognised Tribal reservation boundary.

Adds two columns to all_threats.csv:
  Near_Tribal_Land  – True / False
  Nearest_Tribe     – name of the closest tribal area (or empty string)

Run this after build_all_threats.py whenever either input file changes.
"""

import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

MILES_50_M = 80_467          # 50 miles in metres
CRS_MEASURE = "EPSG:5070"    # Conus Albers equal-area (accurate distances for CONUS)
CRS_WGS84   = "EPSG:4326"

# ── Load inputs ────────────────────────────────────────────────────────────────
print("Loading tribal boundaries…")
tribes = gpd.read_file("tribal_boundaries.geojson").to_crs(CRS_WGS84)
tribes = tribes[tribes.geometry.notna()].copy()
tribes_proj = tribes.to_crs(CRS_MEASURE)

print(f"  {len(tribes_proj)} tribal boundary polygons loaded.")

print("Loading all_threats.csv…")
df = pd.read_csv("all_threats.csv")

# Only projects with coordinates can be spatially tested
has_coords = df["Latitude"].notna() & df["Longitude"].notna()
df_geo  = df[has_coords].copy()
df_none = df[~has_coords].copy()
print(f"  {len(df_geo)} projects with coordinates, {len(df_none)} without.")

# ── Build project GeoDataFrame ─────────────────────────────────────────────────
gdf_projects = gpd.GeoDataFrame(
    df_geo,
    geometry=[Point(lon, lat) for lat, lon in zip(df_geo["Latitude"], df_geo["Longitude"])],
    crs=CRS_WGS84,
).to_crs(CRS_MEASURE)

# ── Buffer tribal boundaries by 50 miles ──────────────────────────────────────
print(f"Buffering tribal boundaries by 50 miles ({MILES_50_M:,} m)…")
tribes_buffered = tribes_proj.copy()
tribes_buffered["geometry"] = tribes_proj.geometry.buffer(MILES_50_M)

# ── Spatial join: find projects inside any 50-mile buffer ─────────────────────
print("Running spatial join…")
joined = gpd.sjoin(
    gdf_projects[["geometry"]],
    tribes_buffered[["geometry", "NAME"]],
    how="left",
    predicate="within",
)

# A project may match multiple tribes; keep the first match per project index
first_match = joined[~joined.index.duplicated(keep="first")]

df_geo["Near_Tribal_Land"] = first_match["NAME"].notna().values
df_geo["Nearest_Tribe"]    = first_match["NAME"].fillna("").values

# ── For projects without coordinates, mark as unknown ─────────────────────────
df_none["Near_Tribal_Land"] = False
df_none["Nearest_Tribe"]    = ""

# ── Now find the true nearest tribe for flagged projects ──────────────────────
# (optional detail: compute which tribe was closest for popup labelling)
flagged = gdf_projects[df_geo["Near_Tribal_Land"].values].copy()

if not flagged.empty:
    print(f"Computing nearest tribe name for {len(flagged)} flagged projects…")
    tribe_union = tribes_proj.copy()

    nearest_names = []
    for geom in flagged.geometry:
        dists = tribe_union.geometry.distance(geom)
        nearest_names.append(tribe_union.loc[dists.idxmin(), "NAME"])

    df_geo.loc[df_geo["Near_Tribal_Land"], "Nearest_Tribe"] = nearest_names

# ── Combine and save ───────────────────────────────────────────────────────────
combined = pd.concat([df_geo, df_none], ignore_index=True)
combined.to_csv("all_threats.csv", index=False)

flagged_count = combined["Near_Tribal_Land"].sum()
print(f"\n✓ Saved all_threats.csv  ({len(combined):,} total projects)")
print(f"  🚨 {flagged_count} projects flagged within 50 miles of a Tribal boundary")
print(f"  ✓  {len(combined) - flagged_count} projects outside the 50-mile zone")

if flagged_count:
    print("\nSample flagged projects:")
    sample = combined[combined["Near_Tribal_Land"]].head(8)[
        ["Project_Name", "Technology", "Nearest_Tribe"]
    ]
    print(sample.to_string(index=False))
