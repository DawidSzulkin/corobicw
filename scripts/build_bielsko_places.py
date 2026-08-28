import json
import logging
import math
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "bielsko_biala"
DATA_DIR.mkdir(parents=True, exist_ok=True)

RAW_FILE = DATA_DIR / "places_raw.json"
CLEAN_FILE = DATA_DIR / "places_clean.json"
PARKINGS_FILE = DATA_DIR / "parkings.json"

# BBOX Bielska-Białej (od Szyndzielni/Dębowca na południu po Komorowice/Hałcnów na północy, Wapienica - Lipnik)
BBOX = "49.74,18.95,49.88,19.15"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter"
]

QUERY = f"""
[out:json][timeout:45];
(
  // 1. Gastronomia
  nwr["amenity"~"restaurant|cafe|pub|bar|ice_cream|fast_food|biergarten|food_court"]({BBOX});
  
  // 2. Kultura, sztuka i rozrywka
  nwr["amenity"~"cinema|theatre|arts_centre|community_centre|library|nightclub|events_venue"]({BBOX});
  nwr["tourism"~"museum|gallery|viewpoint|attraction|theme_park"]({BBOX});
  
  // 3. Historia i zabytki
  nwr["historic"~"castle|fort|monument|memorial|ruins|industrial|locomotive"]({BBOX});
  nwr["man_made"~"water_tower|tower"]({BBOX});
  
  // 4. Natura i rekreacja plenerowa
  nwr["leisure"~"park|nature_reserve|bathing_place|beach_resort|picnic_table"]({BBOX});
  
  // 5. Sport, góry i aktywność
  nwr["leisure"~"sports_centre|water_park|swimming_pool|skatepark|pumptrack|pitch|track|fitness_centre|ice_rink|climbing"]({BBOX});
  nwr["sport"~"climbing|tennis|squash|swimming|skiing|cycling"]({BBOX});
  nwr["aerialway"~"cable_car|chair_lift"]({BBOX});
  
  // 6. Parkingi publiczne
  nwr["amenity"="parking"]["access"!~"private|customers|no"]({BBOX});
);
out center tags;
"""

EXCLUDE_NAMES = {
    "Obiekt nienazwany", "Boisko", "Siłownia plenerowa", "Plac zabaw",
    "Stół piknikowy", "Miejsce na ognisko", "Punkt widokowy"
}


def slugify(text: str) -> str:
    text = text.lower().strip()
    replacements = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ź": "z", "ż": "z"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text).strip("-")


def get_group(tags: Dict[str, str]) -> str:
    amenity = tags.get("amenity", "")
    tourism = tags.get("tourism", "")
    historic = tags.get("historic", "")
    leisure = tags.get("leisure", "")

    if amenity in ["restaurant", "cafe", "pub", "bar", "ice_cream", "fast_food", "biergarten", "food_court"]:
        return "gastronomia"
    if amenity in ["cinema", "theatre", "arts_centre", "community_centre", "library", "nightclub", "events_venue"] or tourism in ["museum", "gallery"]:
        return "kultura"
    if historic or tags.get("man_made") in ["water_tower", "tower"]:
        return "historia"
    if leisure in ["park", "nature_reserve", "bathing_place", "beach_resort"] or tourism in ["viewpoint", "attraction", "theme_park"]:
        return "natura"
    if leisure in ["sports_centre", "water_park", "swimming_pool", "skatepark", "pumptrack", "pitch", "track", "fitness_centre", "ice_rink", "climbing"] or "sport" in tags or "aerialway" in tags:
        return "sport"
    if amenity == "parking":
        return "parking"
    return "inne"


def fetch_osm():
    logging.info("Wysyłanie zapytania Overpass dla Bielska-Białej (BBOX: %s)...", BBOX)
    data = urllib.parse.urlencode({"data": QUERY}).encode("utf-8")
    payload = None

    for endpoint in OVERPASS_ENDPOINTS:
        logging.info("Próba połączenia: %s", endpoint)
        try:
            req = urllib.request.Request(
                endpoint,
                data=data,
                headers={"User-Agent": "CoRobicW-BielskoExtractor/1.0 (https://corobicw.pl)"}
            )
            with urllib.request.urlopen(req, timeout=50) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            logging.info("Pomyślnie odebrano dane z %s", endpoint)
            break
        except Exception as e:
            logging.warning("Błąd endpointu %s: %s", endpoint, e)

    if not payload:
        logging.error("Żaden endpoint Overpass nie odpowiedział.")
        sys.exit(1)

    elements = payload.get("elements", [])
    logging.info("Odebrano %d surowych obiektów OSM.", len(elements))

    raw_items = []
    for el in elements:
        tags = el.get("tags", {})
        coords = None
        if "lat" in el and "lon" in el:
            coords = {"lat": float(el["lat"]), "lon": float(el["lon"])}
        elif "center" in el:
            coords = {"lat": float(el["center"]["lat"]), "lon": float(el["center"]["lon"])}

        if not coords:
            continue

        osm_id = f"{el.get('type', 'node')}/{el.get('id', '')}"
        name = tags.get("name") or tags.get("alt_name") or tags.get("official_name") or ""
        group = get_group(tags)

        raw_items.append({
            "osm_id": osm_id,
            "name": name.strip(),
            "has_custom_name": bool(name.strip()),
            "group": group,
            "geo": coords,
            "address": {
                "street": tags.get("addr:street"),
                "housenumber": tags.get("addr:housenumber"),
                "city": tags.get("addr:city") or "Bielsko-Biała"
            },
            "opening_hours": tags.get("opening_hours"),
            "website": tags.get("website") or tags.get("contact:website"),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "wheelchair": tags.get("wheelchair"),
            "raw_tags": tags
        })

    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(raw_items, f, ensure_ascii=False, indent=2)
    logging.info("Zapisano %s (%d rekordów)", RAW_FILE, len(raw_items))

    # Czyszczenie i budowa bazy produkcyjnej
    clean_places = []
    parkings = []

    seen_names = set()

    for item in raw_items:
        group = item["group"]
        name = item["name"]
        tags = item["raw_tags"]
        coords = item["geo"]

        if group == "parking":
            parkings.append({
                "osm_id": item["osm_id"],
                "geo": coords,
                "lat": coords["lat"],
                "lon": coords["lon"],
                "capacity": tags.get("capacity"),
                "fee": tags.get("fee", "no") == "yes",
                "access": tags.get("access", "public")
            })
            continue

        if not item["has_custom_name"] or name in EXCLUDE_NAMES or len(name) < 3:
            continue

        # Prosta deduplikacja tożsamych obiektów węzeł/obszar
        norm_key = f"{name.lower()}_{round(coords['lat'], 3)}_{round(coords['lon'], 3)}"
        if norm_key in seen_names:
            continue
        seen_names.add(norm_key)

        is_free = tags.get("fee") == "no" or group in ["natura", "historia"]
        if tags.get("fee") == "yes" or group == "gastronomia":
            is_free = False

        is_indoor = group in ["gastronomia", "kultura"] or tags.get("indoor") == "yes" or tags.get("building") is not None
        if tags.get("leisure") in ["park", "nature_reserve", "bathing_place"]:
            is_indoor = False

        p_id = f"bb_{group}_{len(clean_places)+1:03d}"
        slug_id = f"bb-{slugify(name)}"

        raw_amenity = (
            tags.get("amenity")
            or tags.get("tourism")
            or tags.get("historic")
            or tags.get("leisure")
            or tags.get("sport")
            or tags.get("aerialway")
        )

        clean_places.append({
            "id": p_id,
            "place_id": slug_id,
            "name": name,
            "group": group,
            "geo": coords,
            "lat": coords["lat"],
            "lon": coords["lon"],
            "address": item["address"],
            "is_free": is_free,
            "is_indoor": is_indoor,
            "website": item["website"],
            "phone": item["phone"],
            "opening_hours": item["opening_hours"],
            "wheelchair": item["wheelchair"],
            "raw_amenity": raw_amenity
        })

    with open(PARKINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(parkings, f, ensure_ascii=False, indent=2)

    with open(CLEAN_FILE, "w", encoding="utf-8") as f:
        json.dump(clean_places, f, ensure_ascii=False, indent=2)

    logging.info("=== PODSUMOWANIE BIELSKO-BIAŁA ===")
    logging.info("Wyodrębniono parkingów: %d -> %s", len(parkings), PARKINGS_FILE)
    logging.info("Wygenerowano czystych miejsc: %d -> %s", len(clean_places), CLEAN_FILE)


if __name__ == "__main__":
    fetch_osm()
