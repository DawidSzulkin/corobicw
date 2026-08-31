import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.infrastructure.db import DB_PATH

def load_osm_places(city_tag: str) -> dict:
    places_file = BASE_DIR / "data" / city_tag / "places_clean.json"
    if not places_file.exists():
        print(f"[BŁĄD] Brak pliku {places_file}. Uruchom bootstrap_city.py.")
        return {}
    
    with open(places_file, "r", encoding="utf-8") as f:
        return json.load(f)

def audit_city(city_tag: str):
    city_tag = city_tag.strip().lower().replace("-", "_")
    places_osm = load_osm_places(city_tag)
    
    rows = []
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT payload FROM events WHERE city_tag = ?", (city_tag,))
            rows = cursor.fetchall()

    venue_counter = Counter()
    unmapped_venues = Counter()
    
    for row in rows:
        try:
            payload = json.loads(row[0])
            analysis = payload.get("analysis", {})
            ticket_info = analysis.get("ticket_info", {})
            
            venue_name = ticket_info.get("venue_name") or payload.get("venue") or "Nieznane miejsce"
            venue_name = venue_name.strip()
            place_id = ticket_info.get("place_id") or payload.get("place_id")
            
            if place_id and place_id in places_osm:
                venue_counter[place_id] += 1
            else:
                unmapped_venues[venue_name] += 1
        except Exception:
            continue

    print(f"\n{'='*55}")
    print(f" AUDYT MIASTA: {city_tag.upper()} (Suma wydarzeń w bazie: {len(rows)})")
    print(f"{'='*55}")

    print("\n[FAZA 1] TOP OBIEKTY WEDŁUG AGREGATORÓW:")
    if not rows:
        print(" -> Brak wydarzeń w bazie. Agregatory ogólnopolskie nie mają biletów lub nie zwróciły danych.")
    else:
        combined_top = []
        for pid, count in venue_counter.items():
            name = places_osm[pid]["name"]
            combined_top.append((name, count, "OSM_MAPPED"))
            
        for v_name, count in unmapped_venues.items():
            combined_top.append((v_name, count, "UNMAPPED_RAW"))
                
        combined_top.sort(key=lambda x: x[1], reverse=True)
        
        for name, count, status in combined_top[:15]:
            flag = "[MAPOWANE]" if status == "OSM_MAPPED" else "[BRAK W OSM]"
            print(f" - {count:02d} wydarzeń | {name} {flag}")

    print("\n[FAZA 2] ŚLEPE PUNKTY (Główne cele na własne scrapery):")
    print("Obiekty kulturalne i edukacyjne z OSM bez ani jednego wydarzenia w bazie:")
    
    blind_spots = []
    for pid, data in places_osm.items():
        if pid not in venue_counter and data.get("group") in ["kultura", "edukacja"]:
            blind_spots.append(data)

    if not blind_spots:
        print(" -> Brak zidentyfikowanych ślepych punktów. Sprawdź plik places_clean.json.")
    else:
        for spot in sorted(blind_spots, key=lambda x: x.get("name", "")):
            cat = spot.get("category", "nieznana")
            grp = spot.get("group", "")
            print(f" - [BRAK EVENTÓW] {spot['name']} [{grp.upper()}] (Kategoria: {cat})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audytor luk eventowych dla miasta")
    parser.add_argument("--tag", type=str, required=True, help="Tag miasta")
    args = parser.parse_args()
    
    audit_city(args.tag)
