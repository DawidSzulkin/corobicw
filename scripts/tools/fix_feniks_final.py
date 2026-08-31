import sqlite3
import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

print("\n" + "="*50)
print(" ROZPOCZĘCIE CZYSZCZENIA DANYCH: FENIKS")
print("="*50)

# 1. Czyszczenie bazy (Data Poisoning)
db_path = BASE_DIR / "data" / "events.db"
with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT id, payload FROM events WHERE city_tag = 'bielsko_biala'")
    rows = cursor.fetchall()
    
    cleaned = 0
    for ev_id, p_str in rows:
        p = json.loads(p_str)
        raw_v = p.get("venue", "").strip().lower()
        if p.get("place_id") == "bb-feniks-bielsko-biala" or raw_v in ["bielsko-biała", "bielsko biała", "bielsko"]:
            p["place_id"] = None
            p["venue"] = ""  # Zerujemy bezużyteczne venue, co obudzi logikę "wydarzenia w plenerze"
            if "analysis" in p and "ticket_info" in p["analysis"]:
                p["analysis"]["ticket_info"]["place_id"] = None
                p["analysis"]["ticket_info"]["venue_name"] = None
            cursor.execute("UPDATE events SET payload = ? WHERE id = ?", (json.dumps(p, ensure_ascii=False), ev_id))
            cleaned += 1
    conn.commit()
    print(f"[OK] Wyczyszczono {cleaned} zablokowanych przypisań w bazie SQLite.")

# 2. Twarde usunięcie martwej wizytówki HTML z dysku
bad_folder = BASE_DIR / "public" / "bielsko_biala" / "miejsca" / "bb-feniks-bielsko-biala"
if bad_folder.exists():
    shutil.rmtree(bad_folder)
    print("[OK] Skasowano stary, zepsuty folder HTML Feniksa z dysku.")

# 3. Zabezpieczenie pipeline.py (aby problem nie wrócił przy kolejnym scrapowaniu)
pipe_path = BASE_DIR / "src" / "domain" / "pipeline.py"
if pipe_path.exists():
    content = pipe_path.read_text(encoding="utf-8")
    patch = """
    # ZABEZPIECZENIE ARCHITEKTONICZNE: Odcięcie nazw miast od obiektów
    raw_v = str(event.get("venue", "")).strip().lower()
    c_name = city_cfg.get("city", "").strip().lower()
    if raw_v in [c_name, city_cfg.get("city_tag", ""), "obiekt widowiskowy", "wydarzenie"]:
        event["venue"] = ""
"""
    if "ZABEZPIECZENIE ARCHITEKTONICZNE" not in content:
        target = "def _resolve_place(event: Dict[str, Any], places_by_id: Dict[str, Dict[str, Any]], city_cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:"
        content = content.replace(target, target + patch)
        pipe_path.write_text(content, encoding="utf-8")
        print("[OK] Dodano żelazną bramkę do silnika dopasowań w pipeline.py.")

print("="*50 + "\n")
