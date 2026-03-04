"""
Simplify tribal_boundaries.geojson using Shapely's Douglas-Peucker algorithm.
Tolerance of 0.01 degrees (~1 km) is imperceptible at the zoom levels used.
"""
import json, os
from shapely.geometry import shape, mapping
from shapely.validation import make_valid

TOLERANCE = 0.01   # degrees (~1 km)
PRECISION = 4      # decimal places after simplify

with open("tribal_boundaries.geojson") as f:
    gj = json.load(f)

out_features = []
errors = 0
for feat in gj["features"]:
    geom = feat.get("geometry")
    if not geom:
        out_features.append(feat)
        continue
    try:
        s = shape(geom)
        if not s.is_valid:
            s = make_valid(s)
        s = s.simplify(TOLERANCE, preserve_topology=True)
        def round_geom(obj):
            if isinstance(obj, (list, tuple)):
                if obj and isinstance(obj[0], (int, float)):
                    return [round(c, PRECISION) for c in obj]
                return [round_geom(i) for i in obj]
            return obj
        mapped = mapping(s)
        mapped = dict(mapped)
        mapped["coordinates"] = round_geom(mapped["coordinates"])
        out_features.append({**feat, "geometry": mapped})
    except Exception as e:
        errors += 1
        out_features.append(feat)

result = {**gj, "features": out_features}
with open("tribal_boundaries_simple.geojson", "w") as f:
    json.dump(result, f, separators=(",", ":"))

orig = os.path.getsize("tribal_boundaries.geojson")
simp = os.path.getsize("tribal_boundaries_simple.geojson")
print(f"Original : {orig/1e6:.1f} MB")
print(f"Simplified: {simp/1e6:.1f} MB  ({100*simp/orig:.0f}%)")
print(f"Errors   : {errors}")
