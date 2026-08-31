import sys
import os
from pathlib import Path

BASE_DIR = Path(".").resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 1. Czyszczenie BOM
for py_file in BASE_DIR.rglob("*.py"):
    if any(ignore_dir in py_file.parts for ignore_dir in [".venv", "venv", ".git"]):
        continue
    try:
        content = py_file.read_text(encoding="utf-8-sig")
        py_file.write_text(content, encoding="utf-8")
    except Exception:
        pass

# 2. Test scrapera i matchera
from src.infrastructure.scrapers.national.kupbilecik_pl import KupBilecikPlScraper
from src.domain.pipeline import _resolve_place, _load_places_dict

print("=== WYNIK TESTU DLA BARTOSZA MŁYNARSKIEGO ===")
scraper = KupBilecikPlScraper(city_tag="opole")
ev_data = scraper._scrape_detail_page(
    "https://www.kupbilecik.pl/imprezy/212738/Opole/Bartosz+M%C5%82ynarski/",
    "Bartosz Młynarski", "2026-10-04", "18:00", "Miejsce X"
)

if ev_data:
    print(f"Tytuł:      {ev_data.get('title')}")
    print(f"Data:       {ev_data.get('date_start')} {ev_data.get('time_start')}")
    print(f"Miejsce:    {ev_data.get('venue')}")
    print(f"Adres:      {ev_data.get('address')}")
    print(f"Plakat:     {ev_data.get('image_url')}")
else:
    print("[!] Błąd: Scraper zwrócił None.")

print("\n=== WERYFIKACJA MATCHER ===")
places = _load_places_dict("opole")
matched = _resolve_place(ev_data, places, {}) if ev_data else None

if matched:
    print(f"[!] BŁĄD: Fałszywe dopasowanie -> '{matched.get('name')}' (ID: {matched.get('place_id') or matched.get('id')})")
else:
    print("[OK] SUKCES: Obiekt nie został fałszywie powiązany ze słowem 'miejsce'. Trafi czysto do kwarantanny.")
