import urllib.request
import json
import time

BASE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/AIANNHA/MapServer"
# 2=Federal reservations, 3=Off-res trust lands, 4=State reservations,
# 7=Oklahoma tribal statistical areas, 8=State designated, 9=Tribal designated
LAYERS = [2, 3, 4, 7, 8, 9]

all_features = []
for layer_id in LAYERS:
    offset = 0
    while True:
        url = (
            f"{BASE}/{layer_id}/query?where=1%3D1&outFields=NAME"
            f"&returnGeometry=true&outSR=4326&f=geojson&resultOffset={offset}"
        )
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read())
        feats = data.get("features", [])
        all_features.extend(feats)
        print(f"Layer {layer_id}, offset {offset}: +{len(feats)} (total {len(all_features)})")
        if not feats or not data.get("exceededTransferLimit", False):
            break
        offset += len(feats)
        time.sleep(0.2)

geojson = {"type": "FeatureCollection", "features": all_features}
with open("tribal_boundaries.geojson", "w") as f:
    json.dump(geojson, f)
print(f"Done. Total features: {len(all_features)}")
