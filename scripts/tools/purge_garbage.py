import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/events.db")

print("\n" + "="*50)
print(" CZYSZCZENIE BAZY: USUWANIE ŚMIECI Z AGREGATORÓW")
print("="*50)

with sqlite3.connect(DB_PATH) as conn:
    c = conn.cursor()
    c.execute("SELECT id, payload FROM events")
    rows = c.fetchall()
    
    deleted = 0
    for ev_id, p_str in rows:
        try:
            p = json.loads(p_str)
        except Exception:
            continue
            
        source = str(p.get("source", "")).lower()
        if "biletyna" not in source and "kupbilecik" not in source:
            continue
            
        title = str(p.get("title", "")).lower().strip()
        venue = str(p.get("venue", "")).strip()
        
        is_garbage = False
        
        # 1. Tytuł będący tekstem przycisku lub zawierający spam SEO
        if title in ["kup bilet", "kup bilety", "bilety", "szczegóły"] or any(
            trash in title for trash in ["bilety online", "opis, recenzje", "2026, 2027", "2026/2027"]
        ):
            is_garbage = True
            
        # 2. Sklejony wiersz tekstu lub generyczny placeholder zamiast nazwy obiektu
        if len(venue) > 60 or venue.lower() in ["obiekt widowiskowy", "wydarzenie"]:
            is_garbage = True
            
        if is_garbage:
            c.execute("DELETE FROM events WHERE id = ?", (ev_id,))
            deleted += 1

    conn.commit()
    print(f"[OK] Trwale usunięto {deleted} uszkodzonych rekordów z bazy danych.")
print("="*50 + "\n")
