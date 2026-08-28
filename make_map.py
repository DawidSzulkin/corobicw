import json
from pathlib import Path

PLACES_FILE = Path("places_clean.json")
OUTPUT_MAP = Path("public/verify_map.html")

with open(PLACES_FILE, "r", encoding="utf-8") as f:
    places = json.load(f)

# Szukamy Parku Pojednania
park = next((p for p in places if "pojednania" in p["name"].lower()), places[0])

stops = park.get("logistics", {}).get("transit_stops", [])

html_map = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>Weryfikacja Geometrii: {park['name']}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin:0; padding:0; font-family:sans-serif; }}
        #map {{ height: 100vh; width: 100vw; }}
        .legend {{ position: absolute; bottom: 20px; left: 20px; background: white; padding: 12px 16px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 1000; font-size: 13px; line-height: 1.6; }}
    </style>
</head>
<body>
<div id="map"></div>
<div class="legend">
    <strong>Weryfikacja Geometrii OSM</strong><br>
    🔴 <strong>{park['name']}</strong> (Cel)<br>
    🔵 <strong>Przystanki MZK</strong> (Top 2 najbliższe)
</div>
<script>
    var map = L.map('map').setView([{park['lat']}, {park['lon']}], 17);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19,
        attribution: '© OpenStreetMap'
    }}).addTo(map);

    // Marker parku
    var parkMarker = L.circleMarker([{park['lat']}, {park['lon']}], {{
        color: '#ff385c', fillColor: '#ff385c', fillOpacity: 0.9, radius: 10
    }}).addTo(map).bindPopup("<strong>{park['name']}</strong><br>Centroid obiektu").openPopup();

    // Promień 300m
    L.circle([{park['lat']}, {park['lon']}], {{
        color: '#ff385c', fillColor: '#ff385c', fillOpacity: 0.05, radius: 300, weight: 1, dashArray: '4'
    }}).addTo(map);

    // Przystanki
    var stopsData = {json.dumps(stops, ensure_ascii=False)};
    // Znajdźmy współrzędne przystanków z bazy surowej jeśli są
</script>
</body>
</html>
"""

OUTPUT_MAP.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_MAP, "w", encoding="utf-8") as f:
    f.write(html_map)

print(f"[OK] Wygenerowano mapę: {OUTPUT_MAP}")
