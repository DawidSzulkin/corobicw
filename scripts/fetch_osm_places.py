import json
from pathlib import Path
import sys
import urllib.request
import urllib.parse

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_raw.json"

# Lista serwerów na wypadek przeciążenia
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter"
]

# BBOX obejmujący Kędzierzyn-Koźle, Sławięcice, Blachownię oraz Akwen Dębowa: (min_lat, min_lon, max_lat, max_lon)
BBOX = "50.28,18.08,50.41,18.36"

QUERY = f"""
[out:json][timeout:30];
(
  // 1. Gastronomia i życie nocne
  nwr["amenity"~"restaurant|cafe|pub|bar|ice_cream|fast_food|biergarten|food_court"]({BBOX});
  
  // 2. Kultura, sztuka i rozrywka
  nwr["amenity"~"cinema|theatre|arts_centre|community_centre|library|nightclub|events_venue"]({BBOX});
  nwr["tourism"~"museum|gallery|viewpoint|attraction|picnic_site|theme_park"]({BBOX});
  
  // 3. Historia, zabytki i inżynieria
  nwr["historic"~"castle|fort|bunker|monument|memorial|ruins|industrial|archaeological_site|locomotive"]({BBOX});
  nwr["waterway"~"lock|dam"]({BBOX});
  nwr["man_made"~"water_tower|tower"]({BBOX});
  
  // 4. Natura i rekreacja plenerowa
  nwr["leisure"~"park|nature_reserve|bathing_place|beach_resort|picnic_table"]({BBOX});
  
  // 5. Sport i aktywność fizyczna
  nwr["leisure"~"sports_centre|water_park|swimming_pool|skatepark|pumptrack|pitch|track|fitness_centre"]({BBOX});
  nwr["sport"~"climbing|canoe|karting|wakeboard|tennis|squash|swimming"]({BBOX});
  
  // 6. Parkingi (wyłącznie publiczne)
  nwr["amenity"="parking"]["access"!~"private|customers|no"]({BBOX});
);
out center tags;
"""

def fetch_osm_data():
    print(f"[1/3] Wysyłanie zapytania BBOX ({BBOX})...")
    data = urllib.parse.urlencode({"data": QUERY}).encode("utf-8")
    
    payload = None
    for endpoint in OVERPASS_ENDPOINTS:
        print(f" -> Próba połączenia: {endpoint}")
        try:
            req = urllib.request.Request(
                endpoint, 
                data=data, 
                headers={"User-Agent": "CoRobicWPortal/1.0 (places-extractor)"}
            )
            with urllib.request.urlopen(req, timeout=40) as response:
                payload = json.loads(response.read().decode("utf-8"))
            print(f" -> Połączono z {endpoint}!")
            break
        except Exception as e:
            print(f" [OSTRZEŻENIE] Błąd dla {endpoint}: {e}")
            continue

    if not payload:
        print("[BŁĄD] Żaden serwer Overpass nie odpowiedział poprawnie.")
        sys.exit(1)

    elements = payload.get("elements", [])
    print(f"[2/3] Odebrano {len(elements)} surowych rekordów z OSM.")

    parsed_places = []
    stats = {
        "gastronomia": 0,
        "kultura": 0,
        "historia": 0,
        "natura": 0,
        "sport": 0,
        "parking": 0,
        "inne": 0
    }

    for el in elements:
        tags = el.get("tags", {})
        
        lat = el.get("lat") or (el.get("center", {}).get("lat") if "center" in el else None)
        lon = el.get("lon") or (el.get("center", {}).get("lon") if "center" in el else None)
        
        if not lat or not lon:
            continue

        osm_id = f"{el.get('type', 'node')}/{el.get('id')}"
        name = tags.get("name")
        amenity = tags.get("amenity", "")
        tourism = tags.get("tourism", "")
        historic = tags.get("historic", "")
        leisure = tags.get("leisure", "")
        sport = tags.get("sport", "")

        if amenity == "parking":
            cat_group = "parking"
        elif amenity in ["restaurant", "cafe", "pub", "bar", "ice_cream", "fast_food", "biergarten", "food_court"]:
            cat_group = "gastronomia"
        elif amenity in ["cinema", "theatre", "arts_centre", "community_centre", "library", "nightclub", "events_venue"] or tourism in ["museum", "gallery"]:
            cat_group = "kultura"
        elif historic or tags.get("waterway") in ["lock", "dam"] or tags.get("man_made") in ["water_tower", "tower"]:
            cat_group = "historia"
        elif leisure in ["park", "nature_reserve", "bathing_place", "beach_resort"] or tourism in ["viewpoint", "picnic_site"]:
            cat_group = "natura"
        elif leisure in ["sports_centre", "water_park", "swimming_pool", "skatepark", "pumptrack", "pitch", "track", "fitness_centre"] or sport:
            cat_group = "sport"
        else:
            cat_group = "inne"

        stats[cat_group] += 1

        parsed_places.append({
            "osm_id": osm_id,
            "name": name if name else f"Parking ({tags.get('parking', 'terenowy')})" if cat_group == "parking" else "Obiekt nienazwany",
            "has_custom_name": bool(name),
            "group": cat_group,
            "geo": {"lat": lat, "lon": lon},
            "address": {
                "street": tags.get("addr:street"),
                "housenumber": tags.get("addr:housenumber"),
                "city": tags.get("addr:city", "Kędzierzyn-Koźle")
            },
            "opening_hours": tags.get("opening_hours"),
            "website": tags.get("website") or tags.get("contact:website"),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "wheelchair": tags.get("wheelchair"),
            "raw_tags": tags
        })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(parsed_places, f, ensure_ascii=False, indent=2)

    print(f"\n[3/3] Zapisano bazę: {OUTPUT_FILE}")
    print("\n--- PODSUMOWANIE ZEBRANYCH OBIEKTÓW ---")
    for group_name, count in stats.items():
        print(f" * {group_name.upper():<14}: {count} szt.")
    print(f" * SUMA          : {len(parsed_places)} obiektów")


if __name__ == "__main__":
    fetch_osm_data()
