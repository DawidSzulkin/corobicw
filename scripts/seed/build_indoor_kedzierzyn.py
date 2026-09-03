import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.utils.helpers import haversine

import json
import urllib.request
import urllib.parse
from pathlib import Path
import math

CITY = "Kędzierzyn-Koźle"
OUTPUT_DIR = Path("data/kedzierzyn_kozle")
OUTPUT_FILE = OUTPUT_DIR / "indoor_atrakcje.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Użycie bbox zamiast area - omija błędy timeoutu Overpass
OVERPASS_QUERY = """
[out:json][timeout:60];
(
  nwr["amenity"~"cinema|theatre|arts_centre|community_centre"](50.28,18.08,50.36,18.28);
  nwr["tourism"~"museum|gallery"](50.28,18.08,50.36,18.28);
  nwr["leisure"~"sports_centre|indoor_play|escape_game|bowling_alley|ice_rink|trampoline_park"](50.28,18.08,50.36,18.28);
  nwr["leisure"~"swimming_pool|water_park|fitness_centre"]["covered"="yes"](50.28,18.08,50.36,18.28);
  nwr["amenity"="parking"](50.28,18.08,50.36,18.28);
);
out center tags;
"""

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[1/3] Pobieranie danych dla '{CITY}' przez bbox...")
    
    data = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "CityPortalIndoor/3.0"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            elements = json.loads(resp.read().decode("utf-8")).get("elements", [])
    except Exception as e:
        print(f"[BŁĄD] Serwer Overpass nie odpowiedział: {e}")
        return

    print(f"[2/3] Przetwarzanie {len(elements)} surowych rekordów...")
    pois = []
    parkings = []

    for el in elements:
        tags = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        name = tags.get("name", "").strip()
        
        if not lat or not lon:
            continue
            
        if tags.get("amenity") == "parking":
            parkings.append((lat, lon))
        elif name:
            pois.append({"id": el["id"], "name": name, "tags": tags, "lat": lat, "lon": lon})

    clean_results = []
    seen = set()

    for poi in pois:
        name = poi["name"]
        if name.lower() in seen:
            continue
        seen.add(name.lower())

        min_dist = float('inf')
        for plat, plon in parkings:
            dist = haversine(poi["lat"], poi["lon"], plat, plon)
            if dist < min_dist:
                min_dist = dist

        wheelchair = poi["tags"].get("wheelchair", "unknown")
        if wheelchair == "yes":
            wheelchair_status = "Pełny dostęp"
        elif wheelchair == "limited":
            wheelchair_status = "Ograniczony"
        elif wheelchair == "no":
            wheelchair_status = "Brak dostępu"
        else:
            wheelchair_status = "Brak danych"

        leisure = poi["tags"].get("leisure", "")
        age_group = "Bez ograniczeń"
        if leisure == "indoor_play": 
            age_group = "1 - 8 lat"
        elif leisure == "escape_game": 
            age_group = "12+ lat"
        
        clean_results.append({
            "name": name,
            "category": leisure or poi["tags"].get("amenity") or poi["tags"].get("tourism", "rozrywka"),
            "coordinates": {"lat": round(poi["lat"], 6), "lon": round(poi["lon"], 6)},
            "logistics": {
                "parking_distance_meters": round(min_dist) if min_dist != float('inf') else None,
                "wheelchair": wheelchair_status,
                "age_group": age_group
            }
        })

    clean_results.sort(key=lambda x: x["logistics"]["parking_distance_meters"] if x["logistics"]["parking_distance_meters"] is not None else 9999)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(clean_results, f, ensure_ascii=False, indent=2)

    print(f"\n[3/3] Sukces! Zapisano {len(clean_results)} obiektów do: {OUTPUT_FILE}")
    print("--- TOP OBIEKTÓW POD DACHEM ---")
    for r in clean_results[:5]:
        p_dist = f"{r['logistics']['parking_distance_meters']}m" if r['logistics']['parking_distance_meters'] is not None else "brak danych"
        print(f" - {r['name']} | Parking: {p_dist} | Wózki: {r['logistics']['wheelchair']}")

if __name__ == "__main__":
    main()

