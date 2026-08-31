import json
import sqlite3
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "events.db"
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"

print("\n" + "="*70)
print(" PEŁNY AUDYT JAKOŚCI DANYCH: AGREGATORY (BILETYNA, KUPBILECIK) I MAPOWANIA")
print("="*70)

cities = [d.name for d in DATA_DIR.iterdir() if d.is_dir() and (d / "places_clean.json").exists()]
places_by_city = {}

print("\n[1] KONTROLA BAZY MIEJSC (places_clean.json) - Pominięto dla czytelności")
for city in cities:
    p_path = DATA_DIR / city / "places_clean.json"
    with open(p_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    places_by_city[city] = {p.get("place_id") or p.get("id"): p for p in (data if isinstance(data, list) else data.values())}

print("\n[2] KONTROLA REGUŁ DOPASOWAŃ (config/*.yaml) - Pominięto dla czytelności")

print("\n[3] AUDYT REKORDÓW ZE SCRAPERÓW AGREGATORÓW W BAZIE SQLITE")
if not DB_PATH.exists():
    print("[!] Brak pliku events.db")
    exit(1)

with sqlite3.connect(DB_PATH) as conn:
    c = conn.cursor()
    c.execute("SELECT id, city_tag, payload FROM events")
    rows = c.fetchall()

filtered_rows = []
for ev_id, city, payload_str in rows:
    p = json.loads(payload_str)
    source = p.get("source", "")
    if "biletyna" in source or "kupbilecik" in source:
        filtered_rows.append((ev_id, city, source, payload_str, p))

print(f" -> Łącznie pobranych rekordów z agregatorów: {len(filtered_rows)}")

anomalies = []
mapped_venues_summary = {}

for ev_id, city, source, payload_str, p in filtered_rows:
    title = p.get("title", "")
    raw_venue = p.get("venue", "")
    place_id = p.get("place_id") or p.get("analysis", {}).get("ticket_info", {}).get("place_id")
    
    key = f"[{city.upper()}] Raw: '{raw_venue}' -> Target: '{place_id}'"
    mapped_venues_summary[key] = mapped_venues_summary.get(key, 0) + 1
    
    if any(trash in title.lower() for trash in ["bilety online", "opis, recenzje", "kup bilet", "2026/2027", "2026, 2027"]):
        anomalies.append(f"[ŚMIECI W TYTULE] ID: {ev_id} | Tytuł: {title}")
        
    if raw_venue.lower() in [city.replace('_', ' '), city.replace('_', '-'), "obiekt widowiskowy", "wydarzenie"]:
        anomalies.append(f"[MIEJSCE = MIASTO] ID: {ev_id} | Źródło: {source} | Venue: '{raw_venue}'")
        
    if place_id and place_id not in places_by_city.get(city, {}):
        anomalies.append(f"[MARTWY KLUCZ OBCY] ID: {ev_id} | place_id '{place_id}' nie istnieje w {city}/places_clean.json!")

    if len(raw_venue) > 60:
        anomalies.append(f"[PRZEŁADOWANE VENUE] ID: {ev_id} | Długość: {len(raw_venue)} zn. | Venue: '{raw_venue[:60]}...'")

print("\n[4] PODSUMOWANIE MAPOWAŃ MIEJSC ZE SCRAPERÓW (TOP 15):")
for mapping, count in sorted(mapped_venues_summary.items(), key=lambda x: x[1], reverse=True)[:15]:
    print(f"   {count:3d}x | {mapping}")

print(f"\n[5] WYKRYTE ANOMALIE I BŁĘDY ({len(anomalies)}):")
if not anomalies:
    print("   Brak krytycznych anomalii logicznych.")
else:
    for a in anomalies[:20]:
        print(f"   * {a}")
    if len(anomalies) > 20:
        print(f"   ... oraz {len(anomalies) - 20} innych błędów.")

print("="*70 + "\n")
