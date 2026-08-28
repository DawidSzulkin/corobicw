import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_raw.json"
CLEAN_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_clean.json"
PARKINGS_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "parkings.json"

with open(RAW_FILE, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

clean_places = []
parkings = []

# Tagi wykluczające szum sportowy (szkolne i małe osiedlowe boiska bez nazwy)
EXCLUDE_NAMES = ["Obiekt nienazwany", "Boisko", "Siłownia plenerowa", "Plac zabaw"]

for item in raw_data:
    group = item["group"]
    name = item["name"].strip()
    tags = item["raw_tags"]
    
    # 1. Parkingi do osobnego pliku
    if group == "parking":
        parkings.append({
            "osm_id": item["osm_id"],
            "geo": item["geo"],
            "capacity": tags.get("capacity"),
            "fee": tags.get("fee", "no") == "yes",
            "access": tags.get("access", "public")
        })
        continue

    # 2. Odrzucenie obiektów bez nazwy lub o nazwach generycznych
    if not item["has_custom_name"] or name in EXCLUDE_NAMES:
        continue
        
    # 3. Flagi logiczne
    is_free = tags.get("fee") == "no" or group in ["natura", "historia"]
    if tags.get("fee") == "yes" or group == "gastronomia":
        is_free = False

    is_indoor = group in ["gastronomia", "kultura"] or tags.get("indoor") == "yes" or tags.get("building") is not None
    if tags.get("leisure") in ["park", "nature_reserve", "bathing_place"]:
        is_indoor = False

    clean_places.append({
        "id": f"kk_{group}_{len(clean_places)+1:03d}",
        "name": name,
        "group": group,
        "geo": item["geo"],
        "address": item["address"],
        "is_free": is_free,
        "is_indoor": is_indoor,
        "website": item["website"],
        "phone": item["phone"],
        "opening_hours": item["opening_hours"],
        "wheelchair": item["wheelchair"],
        "raw_amenity": tags.get("amenity") or tags.get("tourism") or tags.get("historic") or tags.get("leisure") or tags.get("sport")
    })

with open(PARKINGS_FILE, "w", encoding="utf-8") as f:
    json.dump(parkings, f, ensure_ascii=False, indent=2)

with open(CLEAN_FILE, "w", encoding="utf-8") as f:
    json.dump(clean_places, f, ensure_ascii=False, indent=2)

print(f"[OK] Wyodrębniono {len(parkings)} parkingów -> data/kedzierzyn_kozle/parkings.json")
print(f"[OK] Zbudowano czystą bazę {len(clean_places)} obiektów -> data/kedzierzyn_kozle/places_clean.json")
