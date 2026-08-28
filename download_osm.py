import json
import logging
import sys
import time
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BBOX = "50.264,18.118,50.395,18.328"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter"
]

TARGET_TAGS = {
    "amenity": [
        "restaurant", "cafe", "fast_food", "bar", "pub", "ice_cream", "food_court", "biergarten",
        "cinema", "theatre", "nightclub", "events_venue", "casino", "community_centre", "library",
        "parking", "bicycle_parking", "toilets", "atm"
    ],
    "tourism": [
        "museum", "gallery", "theme_park", "zoo", "aquarium", "viewpoint", "attraction"
    ],
    "leisure": [
        "water_park", "escape_game", "bowling_alley", "amusement_arcade", "miniature_golf",
        "park", "playground", "sports_centre", "swimming_pool", "ice_rink", "fitness_centre",
        "trampoline_park", "climbing", "horse_riding", "dog_park", "marina"
    ],
    "historic": [
        "castle", "ruins", "monument"
    ],
    "highway": [
        "bus_stop"
    ],
    "railway": [
        "station", "halt"
    ]
}


def build_overpass_query() -> str:
    query_lines = ["[out:json][timeout:120];", "("]
    
    # 1. Pobieranie obiektów POI i infrastruktury
    for key, values in TARGET_TAGS.items():
        val_regex = "|".join(values)
        query_lines.append(f'  nwr["{key}"~"^({val_regex})$"]({BBOX});')
        
    # 2. Pobieranie siatki adresowej do przestrzennego łączenia
    query_lines.append(f'  nwr["addr:street"]({BBOX});')
    
    query_lines.append(");")
    query_lines.append("out center;")
    return "\n".join(query_lines)


def download_osm_data(output_file: str, max_retries: int = 3):
    query = build_overpass_query()
    headers = {
        "User-Agent": "CoRobicW-ETL/1.0 (https://corobicw.pl; data-pipeline)",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    for endpoint in OVERPASS_ENDPOINTS:
        logging.info("Odpytywanie instancji Overpass: %s", endpoint)
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    endpoint,
                    data={"data": query},
                    headers=headers,
                    timeout=130
                )

                if response.status_code == 429:
                    time.sleep(10 * attempt)
                    continue

                if response.status_code == 406:
                    break

                response.raise_for_status()
                data = response.json()

                elements_count = len(data.get("elements", []))
                logging.info("Pobrano %d obiektów (POI + Adresy).", elements_count)

                out_path = Path(output_file)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                logging.info("Zapisano dane do: %s", out_path)
                return

            except requests.exceptions.RequestException as e:
                logging.error("Błąd połączenia: %s", e)
                time.sleep(3 * attempt)

    sys.exit(1)


if __name__ == "__main__":
    download_osm_data("raw_places_osm.json")
