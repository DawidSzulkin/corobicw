import sqlite3
import json

print("=== OSTATECZNA WERYFIKACJA OSIEROCONYCH WYDARZEŃ ===")
try:
    conn = sqlite3.connect("data/events.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT title, payload FROM events WHERE city_tag = 'kedzierzyn_kozle'")
    
    orphans = 0
    for r in cur.fetchall():
        payload = json.loads(r["payload"]) if r["payload"] else {}
        if not payload.get("place_id"):
            orphans += 1
            print(f"[OSTRZEŻENIE] Nadal brak miejsca: {r['title']}")
            
    print(f"\nBrakujące place_id w Kędzierzynie-Koźlu: {orphans}")
    if orphans == 0:
        print("[OK] Wszystkie wydarzenia z Kędzierzyna mają przypisane miejsce.")
    conn.close()
except Exception as e:
    print(f"[BŁĄD WERYFIKACJI] {e}")