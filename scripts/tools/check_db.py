import sqlite3
from pathlib import Path
db_path = next(Path(".").glob("*.db"), Path("data/events.db"))
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT id, title, venue_name, place_id, source FROM events WHERE title LIKE '%rooftop%' OR title LIKE '%paint%'")
rows = cur.fetchall()
print("--- DANE WYDARZENIA W BAZIE ---")
for r in rows:
    print(dict(r))

