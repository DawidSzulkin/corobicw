import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.utils.helpers import slugify

import json, re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "bielsko_biala"

RAW_FILE = DATA_DIR / "places_raw.json"
CLEAN_FILE = DATA_DIR / "places_clean.json"
PARKINGS_FILE = DATA_DIR / "parkings.json"

with open(RAW_FILE, "r", encoding="utf-8") as f:
    raw_items = json.load(f)

# Wykluczenia wyłącznie dla cmentarzy, tablic i mogił
HISTORY_BLACKLIST = [
    "poległych", "rozstrzelanych", "ofiar", "mogiła", "tablica", "pamięci",
    "upamiętniająca", "fundamenty", "pomnik ofiar", "w hołdzie", "hitlerowc",
    "jan nepomucen", "kapliczka", "krzyż", "stół ołtarzowy", "kamień"
]

# Obiekty turystyczne i rzeźby do bezwzględnego zachowania
TOURISM_WHITELIST = [
    "reksio", "bolek i lolek", "pampalini", "baltazar gąbka", "smok wawelski",
    "don pedro", "bartolini", "zamek sułkowskich", "stary ratusz", "teatr polski",
    "banialuka", "cavatina", "szyndzielnia", "dębowiec", "kolej linowa"
]

# Wykluczenia dla nazw czysto generycznych (bez marki)
GENERIC_NAMES = {
    "kebab", "fast food", "zapiekanki", "lody", "restauracja", "bar", "pub",
    "obiekt nienazwany", "boisko", "siłownia plenerowa", "plac zabaw", "stół piknikowy"
}

clean_places = []
parkings = []
seen_names = set()

for item in raw_items:
    group = item.get("group", "inne")
    name = item.get("name", "").strip()
    tags = item.get("raw_tags", {})
    coords = item.get("geo")

    if not coords or not name or len(name) < 2:
        continue

    name_lower = name.lower()

    # 1. Parkingi do osobnej bazy logistycznej
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

    # 2. Filtracja cmentarzy i mikro-memoriali
    if group == "historia":
        is_whitelisted = any(w in name_lower for w in TOURISM_WHITELIST)
        is_blacklisted = any(b in name_lower for b in HISTORY_BLACKLIST)
        raw_hist = tags.get("historic", "")

        if (is_blacklisted or raw_hist in ["memorial", "tomb", "wayside_cross", "wayside_shrine"]) and not is_whitelisted:
            continue

    # 3. Odrzucenie nazw bez własnej tożsamości
    if name_lower in GENERIC_NAMES:
        continue

    # Deduplikacja przestrzenna (np. węzeł + obrys budynku o tej samej nazwie)
    norm_key = f"{name_lower}_{round(coords['lat'], 3)}_{round(coords['lon'], 3)}"
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

    addr = item.get("address", {})
    # Flaga ułatwiająca późniejszą identyfikację rekordów do uzupełnienia
    is_incomplete = not addr.get("street")

    clean_places.append({
        "id": p_id,
        "place_id": slug_id,
        "name": name,
        "group": group,
        "geo": coords,
        "lat": coords["lat"],
        "lon": coords["lon"],
        "address": addr,
        "is_free": is_free,
        "is_indoor": is_indoor,
        "is_incomplete": is_incomplete,
        "website": item.get("website"),
        "phone": item.get("phone"),
        "opening_hours": item.get("opening_hours"),
        "wheelchair": item.get("wheelchair"),
        "raw_amenity": raw_amenity
    })

with open(PARKINGS_FILE, "w", encoding="utf-8") as f:
    json.dump(parkings, f, ensure_ascii=False, indent=2)

with open(CLEAN_FILE, "w", encoding="utf-8") as f:
    json.dump(clean_places, f, ensure_ascii=False, indent=2)

print(f"[OK] Baza miejsc Bielska-Białej przeliczona: {len(clean_places)} obiektów.")
