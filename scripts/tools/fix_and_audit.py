import json
import sqlite3
import yaml
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.domain.pipeline import _resolve_place, _load_places_index
from src.infrastructure.db import DB_PATH

def clean_places_json(city_tag: str):
    places_file = BASE_DIR / "data" / city_tag / "places_clean.json"
    if not places_file.exists():
        return
    with open(places_file, "r", encoding="utf-8") as f:
        places = json.load(f)

    junk_words = [
        "gibon", "goryl", "kapibara", "lama", "lew", "marmozeta", "małpy", "malpy", 
        "miał ćwir", "ostronos", "sajmirki", "siamang", "tamaryna", "tygrys", 
        "uchatka", "wilk grzywiasty", "wyderki", "żyrafiarnia", "zyrafiarnia", 
        "mini zoo", "kraina bioróżnorodności", "stawonogi", "płazy", "plazy", 
        "ptaszek festiwalowy", "peryskop", "krzywe zwierciadła", "kalejdoskop", 
        "drezyna", "lokomotywa", "fontanna", "mara patagońska"
    ]

    cleaned = {}
    removed = 0
    for pid, pdata in places.items():
        name_lower = pdata.get("name", "").lower()
        if any(w in name_lower for w in junk_words):
            removed += 1
            continue
        cleaned[pid] = pdata

    with open(places_file, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    print(f"[OK] Trwale wyczyszczono places_clean.json (usunięto {removed} zbędnych obiektów).")

def sync_db_places(city_tag: str):
    cfg_file = BASE_DIR / "config" / f"{city_tag}.yaml"
    with open(cfg_file, "r", encoding="utf-8") as f:
        city_cfg = yaml.safe_load(f) or {}

    places_by_id = _load_places_index(city_tag)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, payload FROM events WHERE city_tag = ?", (city_tag,))
        rows = cursor.fetchall()
        
        updated_count = 0
        for ev_id, payload_str in rows:
            try:
                payload = json.loads(payload_str)
                matched = _resolve_place(payload, places_by_id, city_cfg)
                if matched:
                    p_id = matched.get("place_id") or matched.get("id")
                    payload["place_id"] = p_id
                    if "analysis" not in payload:
                        payload["analysis"] = {}
                    if "ticket_info" not in payload["analysis"]:
                        payload["analysis"]["ticket_info"] = {}
                    payload["analysis"]["ticket_info"]["place_id"] = p_id
                    payload["analysis"]["ticket_info"]["venue_name"] = matched.get("name")
                    
                    cursor.execute(
                        "UPDATE events SET payload = ? WHERE id = ?",
                        (json.dumps(payload, ensure_ascii=False), ev_id)
                    )
                    updated_count += 1
            except Exception:
                continue
        conn.commit()
    print(f"[OK] Zsynchronizowano bazę SQLite: {updated_count}/{len(rows)} wydarzeń przypisano do obiektów OSM.")

clean_places_json("opole")
sync_db_places("opole")
