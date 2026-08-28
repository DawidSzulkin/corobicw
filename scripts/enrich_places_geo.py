import json
import math
from pathlib import Path
import time
import urllib.request
import urllib.parse

BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_clean.json"
PARKINGS_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "parkings.json"
ENRICHED_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_enriched.json"

def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    R = 6371000  # promień Ziemi w metrach
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

def reverse_geocode(lat, lon):
    url = f"https://photon.komoot.io/reverse?lat={lat}&lon={lon}"
    req = urllib.request.Request(url, headers={"User-Agent": "CoRobicWPortal/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            features = data.get("features", [])
            if features:
                props = features[0].get("properties", {})
                street = props.get("street") or props.get("name")
                housenumber = props.get("housenumber")
                district = props.get("district") or props.get("locality") or props.get("city")
                return street, housenumber, district
    except Exception:
        pass
    return None, None, None

with open(CLEAN_FILE, "r", encoding="utf-8") as f:
    places = json.load(f)

with open(PARKINGS_FILE, "r", encoding="utf-8") as f:
    parkings = json.load(f)

print(f"[1/2] Przetwarzanie {len(places)} obiektów (Haversine + Reverse Geocoding)...")

for idx, p in enumerate(places, 1):
    lat = p["geo"]["lat"]
    lon = p["geo"]["lon"]
    
    # 1. Obliczanie najbliższego parkingu
    min_dist = float("inf")
    nearest_pkg = None
    for pkg in parkings:
        p_lat = pkg["geo"]["lat"]
        p_lon = pkg["geo"]["lon"]
        d = haversine_distance(lat, lon, p_lat, p_lon)
        if d < min_dist:
            min_dist = d
            nearest_pkg = {
                "distance_m": int(d),
                "is_fee": pkg.get("fee", False),
                "geo": pkg["geo"]
            }
    p["nearest_parking"] = nearest_pkg

    # 2. Uzupełnianie brakujących adresów
    if not p["address"]["street"]:
        street, housenumber, district = reverse_geocode(lat, lon)
        if street:
            p["address"]["street"] = street
        if housenumber and not p["address"]["housenumber"]:
            p["address"]["housenumber"] = housenumber
        if district:
            p["address"]["district"] = district
        time.sleep(0.05)  # drobny odstęp między zapytaniami

    if idx % 25 == 0 or idx == len(places):
        print(f" -> Przetworzono {idx}/{len(places)} obiektów...")

with open(ENRICHED_FILE, "w", encoding="utf-8") as f:
    json.dump(places, f, ensure_ascii=False, indent=2)

print(f"\n[2/2] Sukces! Zapisano wzbogaconą bazę: {ENRICHED_FILE}")

# Podgląd pierwszych 5 rekordów
print("\n=== PODGLĄD PO WZBOGACENIU ===")
for p in places[:5]:
    street = p['address'].get('street') or 'Brak'
    nr = p['address'].get('housenumber') or ''
    dist = p['nearest_parking']['distance_m']
    print(f"[{p['id']}] {p['name']} -> Adres: {street} {nr} | Parking: {dist} m stąd")
