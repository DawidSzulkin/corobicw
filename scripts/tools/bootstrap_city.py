import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
import requests
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.utils.helpers import slugify, haversine

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

def fetch_osm_data(city_name: str) -> dict:
    query = f"""
    [out:json][timeout:90];
    area["name"="{city_name}"]["admin_level"~"^(7|8|9)$"]->.searchArea;
    (
      node["amenity"~"^(theatre|cinema|arts_centre|community_centre|library|planetarium|restaurant|cafe|pub|fast_food|bar|parking)$"](area.searchArea);
      way["amenity"~"^(theatre|cinema|arts_centre|community_centre|library|planetarium|restaurant|cafe|pub|fast_food|bar|parking)$"](area.searchArea);
      
      node["tourism"~"^(museum|gallery|attraction|theme_park|viewpoint)$"](area.searchArea);
      way["tourism"~"^(museum|gallery|attraction|theme_park|viewpoint)$"](area.searchArea);
      
      node["leisure"~"^(sports_centre|stadium|park|water_park|ice_rink)$"](area.searchArea);
      way["leisure"~"^(sports_centre|stadium|park|water_park|ice_rink)$"](area.searchArea);
    );
    out center tags;
    """
    
    headers = {
        "User-Agent": "PortalWydarzen-Bootstrap/1.0",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    for endpoint in OVERPASS_ENDPOINTS:
        print(f"[OSM] Próba pobrania z: {endpoint}")
        for attempt in range(1, 4):
            try:
                resp = requests.post(endpoint, data={"data": query}, headers=headers, timeout=120)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    print(f"  [!] Limit zapytań (429). Czekam 10 sekund...")
                    time.sleep(10)
                else:
                    print(f"  [!] Błąd {resp.status_code}. Próba {attempt}/3...")
                    time.sleep(2)
            except requests.exceptions.RequestException as e:
                print(f"  [!] Błąd połączenia: {e}. Próba {attempt}/3...")
                time.sleep(3)
                
    raise Exception(f"Nie udało się pobrać danych dla '{city_name}' z żadnego serwera Overpass.")

def process_osm_elements(city_tag: str, city_name: str, elements: list) -> dict:
    places = {}
    parkings = []

    for el in elements:
        tags = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")

        if not lat or not lon:
            continue

        amenity = tags.get("amenity", "")
        name = tags.get("name", "").strip()

        if amenity == "parking":
            parkings.append({
                "lat": float(lat),
                "lon": float(lon),
                "street": tags.get("addr:street", ""),
                "is_fee": tags.get("fee") in ["yes", "interval", "paid"],
                "fee_label": "Płatny parking" if tags.get("fee") in ["yes", "interval", "paid"] else "Bezpłatny parking"
            })
            continue

        if not name or len(name) < 3:
            continue

        group = "inne"
        if tags.get("tourism") in ["museum", "gallery", "attraction"] or amenity in ["theatre", "cinema", "arts_centre", "community_centre", "planetarium"]:
            group = "kultura"
        elif amenity in ["restaurant", "cafe", "pub", "fast_food", "bar"]:
            group = "gastronomia"
        elif tags.get("leisure") in ["sports_centre", "stadium", "water_park", "ice_rink"]:
            group = "sport"
        elif amenity == "library":
            group = "edukacja"

        prefix = "".join([w[0] for w in city_tag.split("_")])
        safe_slug = slugify(name)
        place_id = f"{prefix}-{safe_slug}"

        places[place_id] = {
            "place_id": place_id,
            "id": place_id,
            "name": name,
            "group": group,
            "category": tags.get("tourism") or tags.get("amenity") or tags.get("leisure") or group,
            "raw_amenity": amenity,
            "geo": {"lat": float(lat), "lon": float(lon)},
            "address": {
                "street": tags.get("addr:street", ""),
                "housenumber": tags.get("addr:housenumber", ""),
                "city": tags.get("addr:city", city_name)
            },
            "logistics": {
                "wheelchair": tags.get("wheelchair", "nieznane"),
                "parking_details": []
            }
        }

    print(f"[LOGISTYKA] Dopasowywanie {len(parkings)} parkingów do {len(places)} miejsc...")
    for p_id, p in places.items():
        v_lat, v_lon = p["geo"]["lat"], p["geo"]["lon"]
        matched_parkings = []

        for prk in parkings:
            dist = int(haversine(v_lat, v_lon, prk["lat"], prk["lon"]))
            if dist <= 800:
                matched_parkings.append({
                    "distance_m": dist,
                    "is_fee": prk["is_fee"],
                    "fee_label": prk["fee_label"],
                    "street": prk["street"]
                })

        matched_parkings.sort(key=lambda x: x["distance_m"])
        p["logistics"]["parking_details"] = matched_parkings[:3]
        if matched_parkings:
            p["nearest_parking"] = matched_parkings[0]

    return places

def bootstrap_city(city_tag: str, city_name: str):
    city_tag = city_tag.strip().lower().replace("-", "_")
    city_dir = BASE_DIR / "data" / city_tag
    city_dir.mkdir(parents=True, exist_ok=True)

    osm_raw = fetch_osm_data(city_name)
    clean_places = process_osm_elements(city_tag, city_name, osm_raw.get("elements", []))

    output_places = city_dir / "places_clean.json"
    with open(output_places, "w", encoding="utf-8") as f:
        json.dump(clean_places, f, ensure_ascii=False, indent=2)
    print(f"[OK] Zapisano {len(clean_places)} miejsc do: {output_places}")

    cfg_file = BASE_DIR / "config" / f"{city_tag}.yaml"
    if not cfg_file.exists():
        default_cfg = {
            "city_tag": city_tag,
            "city": city_name,
            "description": f"Wydarzenia, koncerty, spektakle i atrakcje w mieście {city_name}.",
            "seo_keywords": f"{city_name} wydarzenia, koncerty {city_name}, teatr {city_name}, imprezy {city_name}",
            "color_primary": "#1A365D",
            "color_secondary": "#2B6CB0",
            "color_accent": "#E53E3E",
            "theme": "modern",
            "sources": {
                "kupbilecik_pl": {"enabled": True, "name": f"KupBilecik ({city_name})"},
                "biletyna_pl": {"enabled": True, "name": f"Biletyna ({city_name})"}
            },
            "venue_match_rules": []
        }
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.dump(default_cfg, f, allow_unicode=True, sort_keys=False)
        print(f"[OK] Utworzono plik konfiguracyjny: {cfg_file}")

    scrapers_dir = BASE_DIR / "src" / "infrastructure" / "scrapers" / city_tag
    scrapers_dir.mkdir(parents=True, exist_ok=True)
    init_py = scrapers_dir / "__init__.py"
    if not init_py.exists():
        init_py.touch()
    print(f"[OK] Utworzono katalog scraperów: {scrapers_dir}")

    print(f"\n[SUKCES] Miasto '{city_name}' ({city_tag}) jest gotowe do zaciągania danych!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap nowego miasta z OpenStreetMap")
    parser.add_argument("--tag", type=str, required=True, help="Tag miasta")
    parser.add_argument("--name", type=str, required=True, help="Nazwa miasta")
    args = parser.parse_args()

    bootstrap_city(args.tag, args.name)
