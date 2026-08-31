import sqlite3
import subprocess
import sys
from pathlib import Path

# SYSTEMOWY RESET ZEPSUTYCH DANYCH
db_path = Path("data/events.db")
if db_path.exists():
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE source_url LIKE '%biletyna.pl%'")
        deleted = cur.rowcount
        conn.commit()
        print(f"\n[SYSTEM] Wyczyszczono {deleted} przestarzałych/skonfliktowanych rekordów Biletyny z bazy danych.")

# URUCHOMIENIE POTOKU
print("\n=== START GŁÓWNEGO PIPELINE ===")
subprocess.run([sys.executable, "-u", "src/main.py", "--skip-enrich"])
