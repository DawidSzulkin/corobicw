import sqlite3
import json
from pathlib import Path

def run_system_audit():
    print("=== AUDYT SYSTEMU ===")
    db_path = Path("data/events.db")
    if not db_path.exists():
        print("[BŁĄD] Brak bazy danych.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events")
    print(f"[OK] Liczba wpisów w bazie: {cursor.fetchone()[0]}")

    cursor.execute("SELECT title, city_tag, payload FROM events LIMIT 10")
    for idx, (title, city_tag, payload_str) in enumerate(cursor.fetchall(), 1):
        payload = json.loads(payload_str)
        w_acc = payload.get("wheelchair_accessible", False)
        h_loop = payload.get("hearing_loop", False)
        source = payload.get("source", "nieznane")
        print(f"  {idx}. [{source}] {title[:40]}... -> Wózki: {w_acc}, Pętla: {h_loop}")

    conn.close()

if __name__ == "__main__":
    run_system_audit()
