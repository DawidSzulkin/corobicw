import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

RAW_FILE = "raw_places_osm.json"
CLEAN_JSON_FILE = "places_clean.json"

ALLOWED_POI_MAP = {
    "amenity": {
        "restaurant": ("Gastronomia", True),
        "cafe": ("Gastronomia", True),
        "fast_food": ("Gastronomia", True),
        "bar": ("Gastronomia", True),
        "pub": ("Gastronomia", True),
        "ice_cream": ("Gastronomia", False),
        "biergarten": ("Gastronomia", False),
        "cinema": ("Kultura i Rozrywka", True),
        "theatre": ("Kultura i Rozrywka", True),
        "nightclub": ("Kultura i Rozrywka", True),
        "events_venue": ("Kultura i Rozrywka", True),
        "community_centre": ("Kultura i Rozrywka", True),
        "library": ("Kultura i Rozrywka", True),
    },
    "tourism": {
        "museum": ("Kultura i Rozrywka", True),
        "gallery": ("Kultura i Rozrywka", True),
        "viewpoint": ("Turystyka i Atrakcje", False),
        "theme_park": ("Turystyka i Atrakcje", False),
        "zoo": ("Turystyka i Atrakcje", False),
        "aquarium": ("Turystyka i Atrakcje", True),
        "attraction": ("Turystyka i Atrakcje", False),
    },
    "leisure": {
        "park": ("Parki i Natura", False),
        "dog_park": ("Parki i Natura", False),
        "playground": ("Dla Dzieci", False),
        "sports_centre": ("Sport i Rekreacja", True),
        "swimming_pool": ("Sport i Rekreacja", True),
        "water_park": ("Sport i Rekreacja", True),
        "ice_rink": ("Sport i Rekreacja", True),
        "fitness_centre": ("Sport i Rekreacja", True),
        "escape_game": ("Kultura i Rozrywka", True),
        "bowling_alley": ("Kultura i Rozrywka", True),
    },
    "historic": {
        "castle": ("Historia i Zabytki", False),
        "ruins": ("Historia i Zabytki", False),
        "monument": ("Historia i Zabytki", False),
    }
}

PARKING_TYPE_MAP = {
    "surface": "Plac parkingowy",
    "street_side": "Miejsca postojowe przy ulicy",
    "lane": "Miejsca wzdłuż jezdni",
    "underground": "Parking podziemny",
    "multi-storey": "Parking wielopoziomowy",
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    return r * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def extract_coords(element: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    if "center" in element and "lat" in element["center"]:
        return float(element["center"]["lat"]), float(element["center"]["lon"])
    return None


def find_nearest_address(poi_coords: Tuple[float, float], address_list: List[Dict[str, Any]], max_dist: float = 40.0) -> Optional[Tuple[str, str]]:
    poi_lat, poi_lon = poi_coords
    best_addr = None
    min_dist = float("inf")
    for addr in address_list:
        coords = addr["_coords"]
        dist = haversine_distance(poi_lat, poi_lon, coords[0], coords[1])
        if dist < min_dist and dist <= max_dist:
            min_dist = dist
            tags = addr.get("tags", {})
            street = tags.get("addr:street", "")
            housenumber = tags.get("addr:housenumber", "")
            if street:
                best_addr = (street, housenumber)
    return best_addr


def format_parking_info(parking_el: Dict[str, Any], dist: int, addresses: List[Dict[str, Any]]) -> Dict[str, Any]:
    tags = parking_el.get("tags", {})
    coords = parking_el["_coords"]

    street = tags.get("addr:street", "")
    if not street:
        inherited = find_nearest_address(coords, addresses, max_dist=60.0)
        if inherited:
            street = inherited[0]

    raw_p_type = tags.get("parking", "surface")
    p_type_label = PARKING_TYPE_MAP.get(raw_p_type, "Plac parkingowy")

    is_fee = tags.get("fee") == "yes"
    fee_label = "Płatny" if is_fee else "Bezpłatny"
    capacity = tags.get("capacity")
    mins = max(1, math.ceil(dist / 80))

    street_formatted = f" przy ul. {street}" if street else ""
    display_text = f"{fee_label}{street_formatted} ({p_type_label.lower()}) • {dist}m (~{mins} min pieszo)"

    return {
        "type": p_type_label,
        "street": street,
        "fee": is_fee,
        "fee_label": fee_label,
        "capacity": capacity,
        "distance_m": dist,
        "approx_walk_min": mins,
        "lat": coords[0],
        "lon": coords[1],
        "display_text": display_text,
        "maps_url": f"https://maps.google.com/?q={coords[0]},{coords[1]}"
    }


def resolve_poi_data(el: Dict[str, Any], addresses: List[Dict[str, Any]]) -> Optional[Tuple[str, str, bool, Dict[str, bool]]]:
    """
    Zwraca (Nazwa, Kategoria, indoor, Matryca_flag_intencji) lub None jeśli obiekt odpada.
    """
    tags = el.get("tags", {})
    coords = el["_coords"]

    cat = None
    default_indoor = False
    raw_key = None
    raw_val = None

    for main_key, mapping in ALLOWED_POI_MAP.items():
        val = tags.get(main_key)
        if val in mapping:
            cat, default_indoor = mapping[val]
            raw_key, raw_val = main_key, val
            break

    if not cat:
        return None

    # Ustalamy nazwę obiektu
    name = tags.get("name")
    if not name:
        if raw_val == "playground":
            inherited_addr = find_nearest_address(coords, addresses, max_dist=50.0)
            street_name = f"ul. {inherited_addr[0]}" if inherited_addr else "osiedlowy"
            name = f"Plac zabaw ({street_name})"
        elif raw_val == "dog_park":
            name = "Wybieg dla psów"
        else:
            return None  # Bezimienne restauracje/muzea odrzucamy

    # Flaga Indoor
    if tags.get("indoor") == "yes":
        is_indoor = True
    elif tags.get("indoor") == "no":
        is_indoor = False
    else:
        is_indoor = default_indoor

    # Matryca intencji (Multi-tagging)
    # 1. Dla Dzieci
    for_kids = False
    if cat == "Dla Dzieci" or raw_val in ["playground", "theme_park", "aquarium", "water_park", "ice_rink"]:
        for_kids = True
    elif cat == "Parki i Natura":
        for_kids = True  # Każdy park jest miejscem rekreacji z dziećmi
    elif raw_val in ["museum", "library", "community_centre", "swimming_pool", "cinema"]:
        for_kids = True
    elif raw_val in ["nightclub", "bar", "pub", "casino"]:
        for_kids = False

    # 2. Z Psem
    for_dogs = False
    if raw_val == "dog_park" or tags.get("dog") in ["yes", "leashed"]:
        for_dogs = True
    elif cat == "Parki i Natura" and tags.get("dog") != "no":
        for_dogs = True

    # 3. Za Darmo
    is_free = False
    if cat == "Gastronomia":
        is_free = False
    elif tags.get("fee") == "no" or raw_val in ["park", "dog_park", "playground", "viewpoint", "monument", "ruins"]:
        is_free = True
    elif tags.get("fee") == "yes":
        is_free = False

    flags = {
        "for_kids": for_kids,
        "for_dogs": for_dogs,
        "is_free": is_free,
        "indoor": is_indoor,
        "is_food": cat == "Gastronomia"
    }

    return name, cat, is_indoor, flags


def process_osm_database():
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    elements = data.get("elements", [])
    pois = []
    parkings = []
    addresses = []

    for el in elements:
        coords = extract_coords(el)
        if not coords:
            continue

        tags = el.get("tags", {})
        el["_coords"] = coords

        if tags.get("addr:street"):
            addresses.append(el)

        if tags.get("amenity") == "parking":
            if tags.get("access") not in ["private", "permit", "no"]:
                parkings.append(el)
        else:
            pois.append(el)

    processed_places = []

    for el in pois:
        resolved = resolve_poi_data(el, addresses)
        if not resolved:
            continue

        name, category, indoor, flags = resolved
        tags = el.get("tags", {})
        coords = el["_coords"]

        street = tags.get("addr:street", "")
        housenumber = tags.get("addr:housenumber", "")
        if not street:
            inherited = find_nearest_address(coords, addresses, max_dist=40.0)
            if inherited:
                street, housenumber = inherited

        # Najbliższe parkingi
        parking_matches = []
        for p_el in parkings:
            p_coords = p_el["_coords"]
            dist = haversine_distance(coords[0], coords[1], p_coords[0], p_coords[1])
            if dist <= 500.0:
                parking_matches.append((p_el, int(dist)))

        parking_matches.sort(key=lambda x: x[1])
        top_parkings = [format_parking_info(p_obj, p_dist, addresses) for p_obj, p_dist in parking_matches[:2]]
        parking_display = top_parkings[0]["display_text"] if top_parkings else "Brak parkingu <500m"

        wheelchair_val = tags.get("wheelchair")
        wheelchair_desc = (
            "Dostępny bez barier" if wheelchair_val == "yes"
            else ("Częściowy dostęp" if wheelchair_val == "limited" else ("Brak dostępu" if wheelchair_val == "no" else None))
        )

        place_record = {
            "id": f"osm_{el['type']}_{el['id']}",
            "name": name,
            "category": category,
            "cuisine": tags.get("cuisine", ""),
            "indoor": flags["indoor"],
            "for_kids": flags["for_kids"],
            "for_dogs": flags["for_dogs"],
            "is_free": flags["is_free"],
            "lat": coords[0],
            "lon": coords[1],
            "street": street,
            "housenumber": housenumber,
            "wheelchair": wheelchair_desc,
            "pet_friendly": flags["for_dogs"],
            "opening_hours": tags.get("opening_hours") if tags.get("opening_hours") else None,
            "website": tags.get("website") or tags.get("contact:website") or "",
            "phone": tags.get("phone") or tags.get("contact:phone") or "",
            "logistics": {
                "parking": parking_display,
                "parking_details": top_parkings
            },
        }
        processed_places.append(place_record)

    with open(CLEAN_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(processed_places, f, ensure_ascii=False, indent=2)

    logging.info("Zapisano %d wyselekcjonowanych miejsc z matrycą cech do %s", len(processed_places), CLEAN_JSON_FILE)


if __name__ == "__main__":
    process_osm_database()
