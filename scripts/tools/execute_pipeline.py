import sqlite3
import subprocess
import sys
from pathlib import Path

# Czyszczenie starych rekordów Biletyny z konfliktami miast
db_path = Path("data/events.db")
if db_path.exists():
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE source_url LIKE '%biletyna.pl%'")
        deleted = cur.rowcount
        conn.commit()
        print(f"[DB] Usunięto {deleted} rekordów Biletyny do ponownej, czystej synchronizacji.")

print("\n=== START GŁÓWNEGO PIPELINE (src/main.py) ===")
subprocess.run([sys.executable, "src/main.py"])
