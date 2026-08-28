import json
import urllib.request
import urllib.parse
from pathlib import Path
import sys

# Domyślny obszar (możesz zmienić na "Warszawa", "Kraków", "Opole")
CITY_NAME = "Kędzierzyn-Koźle"
CITY_SLUG = "kedzierzyn_kozle"

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / CITY_SLUG
OUTPUT_FILE = OUTPUT_DIR / "places_leisure_clean.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# 1. ZAPYTANIE OVERPASS: PRECYZYJNY LEJEK DLA REKREACJI, SPORTU I KULTURY
OVERPASS_QUERY = f"""
[out:json][timeout:60];
area["name"="{CITY_NAME}"]["admin_level"~"8|7|6"]->.searchArea;
(
  // Sport, adrenalina, gokarty, wspinaczka, skateparki
  nwr["sport"~"karting|climbing|climbing_adventure|skateboarding|bmx|shooting|billiards|laser_tag|paintball|swimming"](area.searchArea);
  nwr["leisure"~"ice_rink|track|bowling_alley|trampoline_park|disc_golf_course|paddel_court|fitness_station"](area.searchArea);

  // Woda, kąpieliska, natura, biwaki
  nwr["leisure"~"water_park|swimming_pool|bathing_place|dog_park|nature_reserve|park"](area.searchArea);
  nwr["natural"~"beach"](area.searchArea);
  nwr["tourism"~"camp_site|viewpoint"](area.searchArea);
  nwr["waterway"="lock"](area.searchArea);

  // Dzieci, rodzina, gry, rozrywka
  nwr["leisure"~"playground|indoor_play|escape_game"](area.searchArea);
  nwr["amenity"~"cinema|theatre|arts_centre|boat_rental|bicycle_rental|bbq"](area.searchArea);
  nwr["tourism"~"zoo|artwork|museum|gallery|attraction"](area.searchArea);

  // Historia i fortyfikacje
  nwr["historic"~"bunker|fort|castle|ruins|monument|memorial"](area.searchArea);
  nwr["man_made"="water_tower"](area.searchArea);
);
out center tags;
"""

def fetch_osm_data(query: str) -> list:
    print(f"[1/4] Pobieranie obiektów rekreacyjnych dla '{CITY_NAME}' z Overpass API...")
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "CityLeisurePortalMatrix/2.0"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("elements", [])

def classify_record(tags: dict) -> dict:
    name = tags.get("name", "").lower()
    sport = tags.get("sport", "").lower()
    leisure = tags.get("leisure", "").lower()
    tourism = tags.get("tourism", "").lower()
    amenity = tags.get("amenity", "").lower()
    historic = tags.get("historic", "").lower()
    man_made = tags.get("man_made", "").lower()
    waterway = tags.get("waterway", "").lower()
    wheelchair = tags.get("wheelchair", "").lower()
    covered = tags.get("covered", "").lower()

    # Domyślny stan
    res = {
        "cluster": "natura_relaks",
        "sub_category": "park",
        "context": ["rodzina", "solo"],
        "time": ["popoludnie"],
        "weather": "outdoor",
        "season": "caly_rok",
        "accessibility": None
    }

    # Dostępność
    if wheelchair == "yes":
        res["accessibility"] = True
    elif wheelchair == "no" or historic == "bunker":
        res["accessibility"] = False
    elif leisure in ["park", "playground"]:
        res["accessibility"] = True

    # -- KLASTROWANIE I MATRYCA 6 OSI --

    # 1. Adrenalina i Sport
    if "karting" in sport or "gokart" in name:
        res.update({"cluster": "aktywnosc_adrenalina", "sub_category": "karting", "context": ["nastolatki", "znajomi"], "time": ["popoludnie", "wieczor"], "weather": "indoor" if covered == "yes" else "outdoor"})
    elif "climbing" in sport or "park linowy" in name:
        res.update({"cluster": "aktywnosc_adrenalina", "sub_category": "park_linowy_wspinaczka", "context": ["nastolatki", "rodzina", "znajomi"], "season": "lato", "time": ["popoludnie"], "weather": "outdoor"})
    elif "skate" in sport or "bmx" in sport or "skatepark" in name or "pumptrack" in name or leisure == "track":
        res.update({"cluster": "aktywnosc_adrenalina", "sub_category": "skatepark_pumptrack", "context": ["nastolatki", "znajomi"], "time": ["popoludnie", "wieczor"], "weather": "outdoor"})
    elif sport in ["laser_tag", "paintball", "shooting"]:
        res.update({"cluster": "aktywnosc_adrenalina", "sub_category": "strzelectwo_militaria", "context": ["nastolatki", "znajomi"], "time": ["popoludnie", "wieczor"]})
    elif leisure in ["ice_rink", "bowling_alley", "trampoline_park"] or sport == "billiards":
        sub = "lodowisko" if leisure == "ice_rink" else "kregielnia_trampoliny"
        res.update({"cluster": "aktywnosc_adrenalina", "sub_category": sub, "context": ["nastolatki", "rodzina", "znajomi"], "time": ["popoludnie", "wieczor"], "weather": "indoor", "season": "zima" if leisure == "ice_rink" else "caly_rok"})

    # 2. Woda i Kąpieliska
    elif leisure in ["water_park", "swimming_pool"] or sport == "swimming":
        res.update({"cluster": "woda_rekreacja", "sub_category": "basen_aquapark", "context": ["dzieci_mlodsze", "nastolatki", "rodzina"], "time": ["poranek", "popoludnie", "wieczor"], "weather": "indoor" if covered == "yes" else "outdoor"})
    elif leisure == "bathing_place" or tags.get("natural") == "beach" or "debowa" in name or "kąpielisko" in name:
        res.update({"cluster": "woda_rekreacja", "sub_category": "plaza_kapielisko", "context": ["dzieci_mlodsze", "nastolatki", "rodzina", "znajomi"], "season": "lato", "time": ["poranek", "popoludnie", "wieczor"], "weather": "outdoor"})
    elif waterway == "lock" or man_made == "water_tower" or "syfon" in name:
        res.update({"cluster": "historia_inzynieria", "sub_category": "inzynieria_wodna", "context": ["dorosli", "rodzina", "solo"], "time": ["poranek", "popoludnie"], "weather": "outdoor"})

    # 3. Rodzina i Dzieci
    elif leisure in ["playground", "indoor_play"] or amenity == "boat_rental":
        sub = "sala_zabaw" if leisure == "indoor_play" else "plac_zabaw"
        res.update({"cluster": "rodzina_dzieci", "sub_category": sub, "context": ["dzieci_mlodsze", "rodzina"], "time": ["poranek", "popoludnie"], "weather": "indoor" if leisure == "indoor_play" else "outdoor"})

    # 4. Kultura, Historia, Eksploracja
    elif amenity in ["cinema", "theatre", "arts_centre"] or tourism in ["museum", "gallery"]:
        sub = "kino" if amenity == "cinema" else "instytucja_kultury"
        res.update({"cluster": "rozrywka_kultura", "sub_category": sub, "context": ["dorosli", "randka", "rodzina"], "time": ["popoludnie", "wieczor"], "weather": "indoor"})
    elif historic in ["bunker", "fort", "castle", "ruins"]:
        res.update({"cluster": "historia_inzynieria", "sub_category": "militaria_fortyfikacje", "context": ["nastolatki", "dorosli", "solo"], "time": ["poranek", "popoludnie"], "weather": "outdoor"})
    elif tourism == "viewpoint":
        res.update({"cluster": "natura_relaks", "sub_category": "punkt_widokowy", "context": ["randka", "solo", "rodzina"], "time": ["popoludnie", "wieczor"], "weather": "outdoor"})
    elif historic in ["monument", "memorial"]:
        res.update({"cluster": "historia_inzynieria", "sub_category": "miejsce_pamieci", "context": ["dorosli", "solo"], "time": ["poranek", "popoludnie"], "weather": "outdoor"})

    return res

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_elements = fetch_osm_data(OVERPASS_QUERY)
    print(f"[2/4] Pobrano {len(raw_elements)} surowych rekordów geometrycznych.")

    clean_places = []
    seen_names = set()
    stats_cluster = {}

    print("[3/4] Czyszczenie i deterministyczna klasyfikacja 6-osiowa...")
    for el in raw_elements:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()

        # Odrzucanie bezimiennych obiektów (eliminuje 95% śmieci)
        if not name:
            # Wyjątek: nazwane typy infrastruktury
            if tags.get("historic") == "bunker":
                name = "Schron bojowy (obiekt fortyfikacyjny)"
            elif tags.get("waterway") == "lock":
                name = "Śluza wodna"
            else:
                continue

        # Prosta deduplikacja po nazwie i klastrze
        dedup_key = f"{name.lower()}_{tags.get('leisure')}_{tags.get('historic')}"
        if dedup_key in seen_names:
            continue
        seen_names.add(dedup_key)

        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if not lat or not lon:
            continue

        axes = classify_record(tags)

        # Gotowa, ustrukturyzowana karta
        record = {
            "id": f"poi_{el['type'][0]}_{el['id']}",
            "name": name,
            "coordinates": {"lat": round(lat, 6), "lon": round(lon, 6)},
            "cluster": axes["cluster"],
            "sub_category": axes["sub_category"],
            "tags": {
                "context": axes["context"],
                "time": axes["time"],
                "weather": axes["weather"],
                "season": axes["season"],
                "accessibility": axes["accessibility"]
            },
            "osm_metadata": {
                "osm_type": el["type"],
                "osm_id": el["id"],
                "wikipedia": tags.get("wikipedia"),
                "wikidata": tags.get("wikidata"),
                "wheelchair": tags.get("wheelchair")
            }
        }

        clean_places.append(record)
        c = axes["cluster"]
        stats_cluster[c] = stats_cluster.get(c, 0) + 1

    print(f"[4/4] Zapisywanie czystej bazy {len(clean_places)} obiektów do: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(clean_places, f, ensure_ascii=False, indent=2)

    print("\n=== RAPORT KLASTROWY (GOTOWE POD FILTRY PORTALU) ===")
    for k, v in sorted(stats_cluster.items(), key=lambda x: x[1], reverse=True):
        print(f" - {k.upper():<25}: {v} miejsc")

if __name__ == "__main__":
    main()
